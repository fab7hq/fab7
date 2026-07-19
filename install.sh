#!/usr/bin/env bash
set -euo pipefail

fab7_default_version="0.1.0"
fab7_version=""
fab7_source=""
fab7_home_path="$HOME/.fab7"
if [[ ${FAB7_HOME+x} == x ]]; then
  fab7_home_path="$FAB7_HOME"
fi
fab7_profile="${FAB7_PROFILE:-}"

usage() {
  cat <<'EOF'
Usage: install.sh [--version VERSION] [--source PATH] [--fab7-home PATH] [--profile PATH]

Without --source, the installer downloads and verifies the immutable Fab7
release archive and checksum for the selected version. --source is for a
reviewed local checkout and integration testing.
EOF
}

while (($#)); do
  case "$1" in
    --version)
      fab7_version="${2:?--version requires a value}"
      shift 2
      ;;
    --source)
      fab7_source="${2:?--source requires a value}"
      shift 2
      ;;
    --fab7-home)
      fab7_home_path="${2:?--fab7-home requires a value}"
      shift 2
      ;;
    --profile)
      fab7_profile="${2:?--profile requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$fab7_home_path" ]]; then
  printf 'FAB7_HOME must not be empty.\n' >&2
  exit 1
fi

case "$(uname -s)" in
  Darwin|Linux) ;;
  *)
    printf 'Fab7 supports macOS and Linux.\n' >&2
    exit 1
    ;;
esac

command -v git >/dev/null 2>&1 || { printf 'Fab7 requires Git.\n' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { printf 'Fab7 requires Python 3.11 or newer.\n' >&2; exit 1; }
fab7_python="$(command -v python3)"
"$fab7_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
  printf 'Fab7 requires Python 3.11 or newer.\n' >&2
  exit 1
}

if [[ -z "$fab7_profile" ]]; then
  case "${SHELL:-}" in
    */zsh) fab7_profile="$HOME/.zshrc" ;;
    */bash) fab7_profile="$HOME/.bashrc" ;;
    *)
      printf 'Set SHELL to Bash or Zsh, or pass --profile.\n' >&2
      exit 1
      ;;
  esac
fi

fab7_temp="$(mktemp -d "${TMPDIR:-/tmp}/fab7-install.XXXXXX")"
fab7_install_temp=""
fab7_lock=""
cleanup() {
  if [[ -n "$fab7_install_temp" && -d "$fab7_install_temp" ]]; then
    rm -rf -- "$fab7_install_temp"
  fi
  if [[ -n "$fab7_lock" && -d "$fab7_lock" ]]; then
    rmdir "$fab7_lock" 2>/dev/null || true
  fi
  rm -rf -- "$fab7_temp"
}
trap cleanup EXIT

fab7_source_sha=""
if [[ -n "$fab7_source" ]]; then
  fab7_source_root="$(cd "$fab7_source" && pwd -P)"
else
  fab7_version="${fab7_version:-$fab7_default_version}"
  fab7_archive_url="https://github.com/fab7hq/fab7/archive/refs/tags/v${fab7_version}.tar.gz"
  fab7_checksum_url="https://github.com/fab7hq/fab7/releases/download/v${fab7_version}/fab7-${fab7_version}.source.sha256"
  fab7_archive="$fab7_temp/fab7.tar.gz"
  fab7_checksum="$fab7_temp/fab7.source.sha256"
  "$fab7_python" - "$fab7_archive_url" "$fab7_archive" "$fab7_checksum_url" "$fab7_checksum" <<'PY'
import pathlib
import sys
import urllib.request

for url, destination in ((sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])):
    request = urllib.request.Request(url, headers={"User-Agent": "fab7-installer"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl() != url:
            from urllib.parse import urlparse
            if urlparse(response.geturl()).hostname not in {"github.com", "codeload.github.com", "release-assets.githubusercontent.com"}:
                raise SystemExit(f"Refusing unexpected redirect: {response.geturl()}")
        data = response.read(128 * 1024 * 1024 + 1)
    if len(data) > 128 * 1024 * 1024:
        raise SystemExit("Fab7 download is too large")
    pathlib.Path(destination).write_bytes(data)
PY
  fab7_expected="$($fab7_python - "$fab7_checksum" <<'PY'
import pathlib
import re
import sys

fields = pathlib.Path(sys.argv[1]).read_text().split()
if not fields or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
    raise SystemExit("Invalid Fab7 checksum document")
print(fields[0])
PY
)"
  fab7_actual="$($fab7_python - "$fab7_archive" <<'PY'
import hashlib
import pathlib
import sys

print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
  if [[ "$fab7_actual" != "$fab7_expected" ]]; then
    printf 'Fab7 source checksum mismatch.\n' >&2
    exit 1
  fi
  fab7_source_sha="sha256:$fab7_actual"
  fab7_source_root="$($fab7_python - "$fab7_archive" "$fab7_temp/source" <<'PY'
import pathlib
import shutil
import sys
import tarfile

archive = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
destination.mkdir()
with tarfile.open(archive, "r:gz") as handle:
    for member in handle.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise SystemExit("Unsafe path in Fab7 source archive")
        target = destination.joinpath(*path.parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(0o755)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            source = handle.extractfile(member)
            if source is None:
                raise SystemExit("Unreadable file in Fab7 source archive")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o644)
        else:
            raise SystemExit("Unsupported entry in Fab7 source archive")
roots = [path for path in destination.iterdir() if path.is_dir()]
if len(roots) != 1:
    raise SystemExit("Fab7 source archive must contain one root directory")
print(roots[0])
PY
)"
fi

fab7_source_version="$(PYTHONPATH="$fab7_source_root/core" "$fab7_python" -c 'from fab7 import __version__; print(__version__)')"
fab7_version="${fab7_version:-$fab7_source_version}"
if [[ "$fab7_version" != "$fab7_source_version" ]]; then
  printf 'Requested Fab7 version does not match the source.\n' >&2
  exit 1
fi

fab7_release="$fab7_temp/release"
fab7_build_args=("$fab7_python" "$fab7_source_root/scripts/build_zipapp.py" --source-root "$fab7_source_root" --release-root "$fab7_release")
if [[ -n "$fab7_source_sha" ]]; then
  fab7_build_args+=(--source-sha256 "$fab7_source_sha")
fi
"${fab7_build_args[@]}" >/dev/null
if [[ "$($fab7_release/bin/fab7 --version)" != "$fab7_version" ]]; then
  printf 'Built Fab7 executable failed its version smoke test.\n' >&2
  exit 1
fi

if [[ -L "$fab7_home_path" || -L "$fab7_home_path/runtime" || -L "$fab7_home_path/bin" ]]; then
  printf 'Fab7 installation directories must not be symlinks.\n' >&2
  exit 1
fi
mkdir -p "$fab7_home_path"
fab7_lock="$fab7_home_path/.install-lock"
fab7_lock_acquired=false
for _ in {1..100}; do
  if mkdir "$fab7_lock" 2>/dev/null; then
    fab7_lock_acquired=true
    break
  fi
  sleep 0.05
done
if [[ "$fab7_lock_acquired" != true ]]; then
  printf 'Another Fab7 installation is running.\n' >&2
  exit 1
fi
mkdir -p "$fab7_home_path/runtime" "$fab7_home_path/bin"
fab7_target="$fab7_home_path/runtime/$fab7_version"

if [[ -L "$fab7_target" ]]; then
  printf 'Fab7 release directories must not be symlinks.\n' >&2
  exit 1
fi
if [[ -e "$fab7_target" ]]; then
  "$fab7_python" - "$fab7_release" "$fab7_target" <<'PY'
import hashlib
import pathlib
import stat
import sys

def snapshot(root):
    rows = []
    for path in sorted(pathlib.Path(root).rglob("*")):
        if path.is_symlink():
            raise SystemExit("Installed Fab7 releases must not contain symlinks")
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.stat().st_mode)
        value = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "directory"
        rows.append((relative, mode, value))
    return rows

if snapshot(sys.argv[1]) != snapshot(sys.argv[2]):
    raise SystemExit("Installed Fab7 version is immutable and differs from this build")
PY
else
  fab7_install_temp="$(mktemp -d "$fab7_home_path/runtime/.fab7-${fab7_version}.XXXXXX")"
  "$fab7_python" - "$fab7_release" "$fab7_install_temp/release" <<'PY'
import pathlib
import shutil
import sys

shutil.copytree(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), copy_function=shutil.copy2)
PY
  mv "$fab7_install_temp/release" "$fab7_target"
  rmdir "$fab7_install_temp"
  fab7_install_temp=""
  fab7_installed_new=true
fi

fab7_installed_new="${fab7_installed_new:-false}"

fab7_selector="$fab7_home_path/bin/fab7"
if [[ -e "$fab7_selector" && ! -L "$fab7_selector" ]]; then
  printf 'Refusing to replace a non-symlink Fab7 selector.\n' >&2
  exit 1
fi
fab7_had_selector=false
fab7_previous_target=""
if [[ -L "$fab7_selector" ]]; then
  fab7_had_selector=true
  fab7_previous_target="$(readlink "$fab7_selector")"
fi
fab7_selector_temp="$fab7_home_path/bin/.fab7-selector.$$"
rm -f -- "$fab7_selector_temp"
ln -s "../runtime/$fab7_version/bin/fab7" "$fab7_selector_temp"
mv -f "$fab7_selector_temp" "$fab7_selector"

if ! "$fab7_python" - "$fab7_profile" "$fab7_home_path" "$HOME" <<'PY'
import pathlib
import shlex
import sys

profile = pathlib.Path(sys.argv[1])
fab7_home = pathlib.Path(sys.argv[2]).resolve()
user_home = pathlib.Path(sys.argv[3]).resolve()
start = "# >>> fab7 >>>"
end = "# <<< fab7 <<<"
if fab7_home == user_home / ".fab7":
    path_line = 'export PATH="$HOME/.fab7/bin:$PATH"'
else:
    path_line = f"export PATH={shlex.quote(str(fab7_home / 'bin'))}:$PATH"
block = f"{start}\n{path_line}\n{end}\n"
text = profile.read_text() if profile.exists() else ""
if start in text or end in text:
    if text.count(start) != 1 or text.count(end) != 1 or block not in text:
        raise SystemExit("Refusing malformed existing Fab7 PATH block")
else:
    profile.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if not text or text.endswith("\n") else "\n"
    profile.write_text(text + separator + block)
PY
then
  if [[ "$fab7_had_selector" == true ]]; then
    fab7_restore="$fab7_home_path/bin/.fab7-restore.$$"
    ln -s "$fab7_previous_target" "$fab7_restore"
    mv -f "$fab7_restore" "$fab7_selector"
  else
    rm -f -- "$fab7_selector"
  fi
  if [[ "$fab7_installed_new" == true ]]; then
    rm -rf -- "$fab7_target"
  fi
  exit 1
fi

printf 'Fab7 %s installed at %s\n' "$fab7_version" "$fab7_home_path"
printf 'Reload with: exec %s -l\n' "${SHELL:-/bin/sh}"
