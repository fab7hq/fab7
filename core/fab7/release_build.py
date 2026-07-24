"""Build a deterministic native Fab7 executable and its host roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Iterable

from .install import fab7_home
from .native_build import build_native_executable
from .plugin.build import build_fab7_plugin_roots, plugin_source_files


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def build_release(
    source_root: Path,
    release_root: Path,
    source_sha256: str | None = None,
    *,
    home: Path | None = None,
    uv_executable: str | Path | None = None,
) -> dict[str, object]:
    source_root = source_root.resolve()
    if release_root.exists() and any(release_root.iterdir()):
        raise ValueError(f"release root is not empty: {release_root}")
    release_root.mkdir(parents=True, exist_ok=True)

    version = _source_version(source_root)
    executable = release_root / "bin" / "fab7"
    executable.parent.mkdir(parents=True)
    inputs = _source_inputs(source_root)
    native = build_native_executable(
        source_root,
        source_root / "core" / "fab7" / "__main__.py",
        executable,
        name="fab7",
        home=home or fab7_home(),
        search_paths=(source_root / "core",),
        data_files=(
            (source_root / "core" / "fab7" / "templates", "fab7/templates"),
            (
                source_root / "core" / "fab7" / "build-requirements.txt",
                "fab7",
            ),
        ),
        smoke_args=("--version",),
        uv_executable=uv_executable,
    )
    build_fab7_plugin_roots(source_root, release_root / "hosts", version)

    digest = source_sha256 or _source_digest(source_root, inputs)
    if not SHA256_RE.fullmatch(digest):
        raise ValueError("source digest must use sha256:<64 lowercase hex>")
    executable_digest = "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    manifest = {
        "schema": 1,
        "name": "fab7",
        "version": version,
        "source_sha256": digest,
        "executable_sha256": executable_digest,
        "target": native["target"],
        "toolchain": native["toolchain"],
    }
    _write_json(release_root / "manifest.json", manifest)
    return manifest


def _source_inputs(source_root: Path) -> list[tuple[str, Path]]:
    package_root = source_root / "core" / "fab7"
    if not package_root.is_dir():
        raise ValueError("source root does not contain the Fab7 package")
    rows: list[tuple[str, Path]] = []
    for path in sorted(package_root.rglob("*")):
        relative = path.relative_to(package_root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"Fab7 package inputs must not be symlinked: {relative}")
        if path.is_file():
            rows.append((f"fab7/{relative.as_posix()}", path))
        elif not path.is_dir():
            raise ValueError(f"Fab7 package input is unsupported: {relative}")
    for relative in ("pyproject.toml", "uv.lock"):
        path = source_root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Fab7 source input is missing or symlinked: {relative}")
        rows.append((relative, path))
    return rows


def _source_version(source_root: Path) -> str:
    text = (source_root / "core" / "fab7" / "__init__.py").read_text()
    match = re.search(
        r'^__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$',
        text,
        re.MULTILINE,
    )
    if not match:
        raise ValueError("Fab7 source version is missing or invalid")
    return match.group(1)


def _source_digest(
    source_root: Path,
    source_inputs: Iterable[tuple[str, Path]],
) -> str:
    paths = [path for _name, path in source_inputs]
    paths.extend(plugin_source_files(source_root))
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        relative = path.relative_to(source_root).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    path.chmod(0o644)


def _snapshot(root: Path) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode & 0o777
        if path.is_file():
            value = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            value = "directory"
        else:
            value = "unsupported"
        rows.append((relative, mode, value))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--release-root", type=Path)
    parser.add_argument("--source-sha256")
    parser.add_argument("--fab7-home", type=Path)
    parser.add_argument("--uv", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="fab7-build-check-") as directory:
            temporary = Path(directory)
            first = temporary / "first"
            second = temporary / "second"
            build_home = args.fab7_home or Path(
                tempfile.mkdtemp(prefix="fab7-build-toolchain-", dir=temporary)
            )
            build_release(
                args.source_root,
                first,
                args.source_sha256,
                home=build_home,
                uv_executable=args.uv,
            )
            build_release(
                args.source_root,
                second,
                args.source_sha256,
                home=build_home,
                uv_executable=args.uv,
            )
            if _snapshot(first) != _snapshot(second):
                raise SystemExit("Fab7 release build is not deterministic")
        print("Fab7 release build is deterministic.")
        return 0
    if args.release_root is None:
        parser.error("--release-root is required unless --check is used")
    manifest = build_release(
        args.source_root,
        args.release_root,
        args.source_sha256,
        home=args.fab7_home,
        uv_executable=args.uv,
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
