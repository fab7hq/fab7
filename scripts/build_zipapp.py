#!/usr/bin/env python3
"""Build a deterministic Fab7 executable and its release-bundled host roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


FIXED_TIME = (1980, 1, 1, 0, 0, 0)
SHEBANG = b"#!/usr/bin/env python3\n"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def build_release(source_root: Path, release_root: Path, source_sha256: str | None = None) -> dict[str, object]:
    source_root = source_root.resolve()
    if release_root.exists() and any(release_root.iterdir()):
        raise ValueError(f"release root is not empty: {release_root}")
    release_root.mkdir(parents=True, exist_ok=True)

    version = _source_version(source_root)
    executable = release_root / "bin" / "fab7"
    executable.parent.mkdir(parents=True)
    inputs = _zip_inputs(source_root)
    _build_executable(executable, inputs)

    _build_host_root(source_root, release_root / "hosts" / "claude", "claude", version)
    _build_host_root(source_root, release_root / "hosts" / "codex", "codex", version)

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
        "python": ">=3.11",
    }
    _write_json(release_root / "manifest.json", manifest)
    return manifest


def _zip_inputs(source_root: Path) -> list[tuple[str, Path]]:
    package_root = source_root / "core" / "fab7"
    main = source_root / "scripts" / "zipapp_main.py"
    if not package_root.is_dir() or not main.is_file():
        raise ValueError("source root does not contain the Fab7 package and zipapp entry point")
    rows = [("__main__.py", main)]
    rows.extend((f"fab7/{path.name}", path) for path in sorted(package_root.glob("*.py")))
    return rows


def _build_executable(output: Path, inputs: Iterable[tuple[str, Path]]) -> None:
    with tempfile.NamedTemporaryFile("w+b", delete=False, dir=output.parent, prefix=".fab7-zip-") as handle:
        temporary = Path(handle.name)
    try:
        with temporary.open("wb") as raw:
            raw.write(SHEBANG)
            with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as archive:
                for archive_name, source in sorted(inputs):
                    info = zipfile.ZipInfo(archive_name, FIXED_TIME)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    info.compress_type = zipfile.ZIP_STORED
                    archive.writestr(info, source.read_bytes())
        temporary.chmod(0o755)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def _build_host_root(source_root: Path, host_root: Path, host: str, version: str) -> None:
    plugin_source = source_root / "plugins" / host / "fab7"
    if not plugin_source.is_dir():
        raise ValueError(f"missing {host} plugin source")
    _validate_plugin_version(plugin_source, host, version)
    plugin_target = host_root / "plugins" / "fab7"
    _copy_tree(plugin_source, plugin_target)
    if host == "claude":
        marketplace = {
            "name": "fab7",
            "description": "Fab7 proof-gate plugins for supported agentic CLIs.",
            "owner": {"name": "Fab7", "url": "https://github.com/fab7hq/fab7"},
            "plugins": [
                {
                    "name": "fab7",
                    "source": "./plugins/fab7",
                    "description": "Initialize and use a project-pinned Fab7 proof gate.",
                    "version": version,
                }
            ],
        }
        _write_json(host_root / ".claude-plugin" / "marketplace.json", marketplace)
    else:
        marketplace = {
            "name": "fab7",
            "interface": {"displayName": "Fab7"},
            "plugins": [
                {
                    "name": "fab7",
                    "source": {"source": "local", "path": "./plugins/fab7"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity",
                }
            ],
        }
        _write_json(host_root / ".agents" / "plugins" / "marketplace.json", marketplace)


def _validate_plugin_version(plugin: Path, host: str, version: str) -> None:
    manifest_path = plugin / (".claude-plugin/plugin.json" if host == "claude" else ".codex-plugin/plugin.json")
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {host} plugin manifest") from exc
    if manifest.get("name") != "fab7" or manifest.get("version") != version:
        raise ValueError(f"{host} plugin identity does not match Fab7 {version}")


def _copy_tree(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"plugin sources must not contain symlinks: {path}")
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            destination.chmod(0o755)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            destination.chmod(0o644)
        else:
            raise ValueError(f"unsupported plugin source: {path}")


def _source_version(source_root: Path) -> str:
    text = (source_root / "core" / "fab7" / "__init__.py").read_text()
    match = re.search(r'^__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$', text, re.MULTILINE)
    if not match:
        raise ValueError("Fab7 source version is missing or invalid")
    return match.group(1)


def _source_digest(source_root: Path, zip_inputs: Iterable[tuple[str, Path]]) -> str:
    paths = [path for _, path in zip_inputs]
    paths.append(source_root / "scripts" / "build_zipapp.py")
    for host in ("claude", "codex"):
        paths.extend(path for path in (source_root / "plugins" / host / "fab7").rglob("*") if path.is_file())
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
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--release-root", type=Path)
    parser.add_argument("--source-sha256")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="fab7-build-check-") as directory:
            temporary = Path(directory)
            first = temporary / "first"
            second = temporary / "second"
            build_release(args.source_root, first, args.source_sha256)
            build_release(args.source_root, second, args.source_sha256)
            if _snapshot(first) != _snapshot(second):
                raise SystemExit("Fab7 release build is not deterministic")
        print("Fab7 release build is deterministic.")
        return 0
    if args.release_root is None:
        parser.error("--release-root is required unless --check is used")
    manifest = build_release(args.source_root, args.release_root, args.source_sha256)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
