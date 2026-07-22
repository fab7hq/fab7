"""Closed extension source, package, and installed-receipt contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import signal
import shutil
import stat
import subprocess
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from . import __version__
from .errors import Fab7Error


IDENTITY_FIELDS = {
    "name",
    "publisher",
    "repository",
    "version",
    "fab7_min",
    "fab7_max_exclusive",
    "executable",
    "capabilities",
    "hosts",
}
PACKAGE_FIELDS = {"schema", *IDENTITY_FIELDS, "files"}
SOURCE_FIELDS = {"schema", *IDENTITY_FIELDS, "build"}
BUILD_FIELDS = {"command", "files"}
FILE_FIELDS = {"path", "mode", "sha256"}
RECEIPT_FIELDS = {
    "schema", "install_id", "origin", "integrations", *IDENTITY_FIELDS, "files"
}
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
INSTALL_ID_RE = re.compile(r"^(?:[0-9]+\.[0-9]+\.[0-9]+|dev-[0-9a-f]{64})$")
SUPPORTED_HOSTS = {"claude", "codex"}
MAX_SOURCE_FILES = 512
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PACKAGE_FILES = 256
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_BUILD_OUTPUT = 64 * 1024
MAX_BUILD_SECONDS = 300


def identity_from(value: dict[str, Any], code: str) -> dict[str, Any]:
    identity = {field: value.get(field) for field in IDENTITY_FIELDS}
    if any(field not in value for field in IDENTITY_FIELDS):
        _fail(code, "Extension identity fields are invalid")
    for field in ("name", "publisher", "executable"):
        item = identity[field]
        if not isinstance(item, str) or not NAME_RE.fullmatch(item):
            _fail(code, f"Extension {field} is invalid")
    if identity["name"] == "fab7" or identity["executable"] != identity["name"]:
        _fail(code, "Extension executable identity is invalid")
    for field in ("version", "fab7_min", "fab7_max_exclusive"):
        parse_version(identity[field], code, f"Extension {field}")
    if parse_version(identity["fab7_min"], code, "Fab7 minimum") >= parse_version(
        identity["fab7_max_exclusive"], code, "Fab7 maximum"
    ):
        _fail(code, "Fab7 compatibility range is empty")
    repository = identity["repository"]
    expected_repository = f"https://github.com/{identity['publisher']}/{identity['name']}"
    if repository != expected_repository:
        _fail(code, "Extension repository identity is invalid")
    for field in ("capabilities", "hosts"):
        items = identity[field]
        if (
            not isinstance(items, list)
            or not all(isinstance(item, str) and NAME_RE.fullmatch(item) for item in items)
            or items != sorted(items)
            or len(items) != len(set(items))
        ):
            _fail(code, f"Extension {field} must have unique canonical ordering")
    if not identity["hosts"] or not set(identity["hosts"]).issubset(SUPPORTED_HOSTS):
        _fail(code, "Extension hosts are invalid")
    return identity


def require_compatible(identity: dict[str, Any]) -> None:
    current = parse_version(__version__, "FAB7_EXTENSION_INCOMPATIBLE", "Fab7 version")
    minimum = parse_version(identity["fab7_min"], "FAB7_EXTENSION_INCOMPATIBLE", "Fab7 minimum")
    maximum = parse_version(
        identity["fab7_max_exclusive"], "FAB7_EXTENSION_INCOMPATIBLE", "Fab7 maximum"
    )
    if not minimum <= current < maximum:
        _fail(
            "FAB7_EXTENSION_INCOMPATIBLE",
            f"Extension requires Fab7 >= {identity['fab7_min']} and < {identity['fab7_max_exclusive']}",
        )


def validate_package(root: Path, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package root is missing or symlinked")
    root = root.resolve()
    manifest_path = root / "extension.json"
    manifest = _read_json(manifest_path, "FAB7_EXTENSION_PACKAGE_INVALID")
    if set(manifest) != PACKAGE_FIELDS or manifest.get("schema") != 1:
        _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package manifest fields are invalid")
    identity = identity_from(manifest, "FAB7_EXTENSION_PACKAGE_INVALID")
    require_compatible(identity)
    if expected is not None and identity != expected:
        _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package identity does not match its source")
    files = _validate_file_rows(manifest["files"], "FAB7_EXTENSION_PACKAGE_INVALID")
    _validate_tree(root, files, "extension.json", "FAB7_EXTENSION_PACKAGE_INVALID")
    _validate_required_files(root, identity, files, "FAB7_EXTENSION_PACKAGE_INVALID")
    return {**identity, "files": files}


def build_local_package(source: Path, temporary: Path) -> tuple[Path, str, dict[str, Any]]:
    if source.is_symlink() or not source.is_dir():
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source is missing or symlinked")
    source = source.resolve()
    manifest = _read_json(source / "fab7-extension.json", "FAB7_EXTENSION_SOURCE_INVALID")
    if set(manifest) != SOURCE_FIELDS or manifest.get("schema") != 1:
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source manifest fields are invalid")
    identity = identity_from(manifest, "FAB7_EXTENSION_SOURCE_INVALID")
    require_compatible(identity)
    build = manifest.get("build")
    if not isinstance(build, dict) or set(build) != BUILD_FIELDS:
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension build fields are invalid")
    command = build.get("command")
    files = build.get("files")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) and item and "\x00" not in item for item in command)
        or sum(item.count("{output}") for item in command) != 1
    ):
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension build command is invalid")
    if (
        not isinstance(files, list)
        or not files
        or len(files) > MAX_SOURCE_FILES
        or files != sorted(files)
        or len(files) != len(set(files))
        or "fab7-extension.json" not in files
    ):
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension build files are invalid")

    staged = temporary / "source"
    staged.mkdir(parents=True)
    digest = hashlib.sha256()
    total = 0
    for relative in files:
        path = _source_file(source, relative)
        content = path.read_bytes()
        total += len(content)
        if total > MAX_SOURCE_BYTES:
            _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source exceeds the size limit")
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode not in {0o644, 0o755}:
            _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source file mode is invalid")
        destination = staged.joinpath(*PurePosixPath(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        destination.chmod(mode)
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(f"{mode:04o}".encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")

    output = temporary / "package"
    argv = [
        item.replace("{python}", sys.executable).replace("{output}", str(output))
        for item in command
    ]
    returncode, stdout, stderr = _run_build(argv, staged)
    if returncode != 0:
        detail = (stderr or stdout).strip()
        _fail(
            "FAB7_EXTENSION_BUILD_FAILED",
            "Local extension build failed" + (f": {detail}" if detail else ""),
        )
    package = validate_package(output, identity)
    return output, "sha256:" + digest.hexdigest(), package


def extract_package_archive(content: bytes, destination: Path) -> Path:
    if len(content) > MAX_PACKAGE_BYTES:
        _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package archive exceeds the size limit")
    destination.mkdir(parents=True)
    total = 0
    names: set[str] = set()
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_PACKAGE_FILES + 1:
                _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package archive entries are invalid")
            for info in entries:
                if info.is_dir() or info.filename in names:
                    _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package archive entries are invalid")
                parts = _relative_parts(info.filename, "FAB7_EXTENSION_PACKAGE_INVALID")
                mode = info.external_attr >> 16
                if info.create_system != 3 or not stat.S_ISREG(mode):
                    _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package archive mode is invalid")
                permissions = stat.S_IMODE(mode)
                if permissions not in {0o644, 0o755}:
                    _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package archive mode is invalid")
                total += info.file_size
                if total > MAX_PACKAGE_BYTES:
                    _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package archive expands beyond the size limit")
                names.add(info.filename)
                target = destination.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
                target.chmod(permissions)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise Fab7Error("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package archive is invalid") from exc
    return destination


def materialize_installation(
    package_root: Path,
    destination: Path,
    install_id: str,
    origin: dict[str, Any],
) -> dict[str, Any]:
    package = validate_package(package_root)
    if not INSTALL_ID_RE.fullmatch(install_id):
        _fail("FAB7_EXTENSION_INVALID", "Extension install identity is invalid")
    if destination.exists() or destination.is_symlink():
        _fail("FAB7_EXTENSION_INVALID", "Extension installation target already exists")
    destination.mkdir(parents=True)
    try:
        for row in package["files"]:
            source = package_root.joinpath(*PurePosixPath(row["path"]).parts)
            target = destination.joinpath(*PurePosixPath(row["path"]).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(int(row["mode"], 8))
        receipt = {
            "schema": 1,
            "install_id": install_id,
            "origin": origin,
            "integrations": [],
            **{field: package[field] for field in IDENTITY_FIELDS},
            "files": package["files"],
        }
        _write_json(destination / "manifest.json", receipt)
        return validate_installation(destination)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def validate_installation(root: Path, *, verify_files: bool = True) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        _fail("FAB7_EXTENSION_INVALID", "Extension installation is missing or symlinked")
    root = root.resolve()
    receipt = _read_json(root / "manifest.json", "FAB7_EXTENSION_INVALID")
    if set(receipt) != RECEIPT_FIELDS or receipt.get("schema") != 1:
        _fail("FAB7_EXTENSION_INVALID", "Extension installation receipt fields are invalid")
    identity = identity_from(receipt, "FAB7_EXTENSION_INVALID")
    if receipt.get("install_id") != root.name or not INSTALL_ID_RE.fullmatch(receipt["install_id"]):
        _fail("FAB7_EXTENSION_INVALID", "Extension installation identity is invalid")
    origin = receipt.get("origin")
    _validate_origin(origin)
    integrations = receipt.get("integrations")
    if (
        not isinstance(integrations, list)
        or integrations != sorted(integrations)
        or len(integrations) != len(set(integrations))
        or not set(integrations).issubset(identity["hosts"])
    ):
        _fail("FAB7_EXTENSION_INVALID", "Extension host integrations are invalid")
    files = _validate_file_rows(receipt.get("files"), "FAB7_EXTENSION_INVALID")
    if verify_files:
        _validate_tree(root, files, "manifest.json", "FAB7_EXTENSION_INVALID")
        _validate_required_files(root, identity, files, "FAB7_EXTENSION_INVALID")
    return {**receipt, "files": files}


def set_integrations(root: Path, hosts: list[str]) -> dict[str, Any]:
    receipt = validate_installation(root, verify_files=False)
    if hosts != sorted(hosts) or len(hosts) != len(set(hosts)) or not set(hosts).issubset(
        receipt["hosts"]
    ):
        _fail("FAB7_EXTENSION_INVALID", "Extension host integrations are invalid")
    receipt["integrations"] = hosts
    _write_json_atomic(root / "manifest.json", receipt)
    return validate_installation(root)


def parse_version(value: Any, code: str, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) > 32 or not VERSION_RE.fullmatch(value):
        _fail(code, f"{label} is invalid")
    parsed = tuple(int(part) for part in value.split("."))
    if value != ".".join(str(part) for part in parsed):
        _fail(code, f"{label} is not canonical")
    return parsed


def digest_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _run_build(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        raise Fab7Error(
            "FAB7_EXTENSION_BUILD_FAILED",
            f"Local extension build could not start: {exc}",
        ) from exc
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    assert process.stdout is not None and process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    deadline = time.monotonic() + MAX_BUILD_SECONDS
    failure: str | None = None
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "Local extension build exceeded the time limit"
                break
            events = selector.select(remaining)
            if not events:
                failure = "Local extension build exceeded the time limit"
                break
            for key, _mask in events:
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                streams[key.data].extend(chunk)
                if sum(len(value) for value in streams.values()) > MAX_BUILD_OUTPUT:
                    failure = "Local extension build exceeded the output limit"
                    break
            if failure is not None:
                break
    except OSError as exc:
        failure = f"Local extension build could not complete: {exc}"
    finally:
        selector.close()
    returncode: int | None = None
    if failure is None:
        try:
            returncode = process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            failure = "Local extension build exceeded the time limit"
    if failure is not None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()
        process.stderr.close()
        _fail("FAB7_EXTENSION_BUILD_FAILED", failure)
    assert returncode is not None
    process.stdout.close()
    process.stderr.close()
    return (
        returncode,
        streams["stdout"].decode(errors="replace"),
        streams["stderr"].decode(errors="replace"),
    )


def _source_file(root: Path, relative: Any) -> Path:
    parts = _relative_parts(relative, "FAB7_EXTENSION_SOURCE_INVALID")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension build files must not be symlinked")
    if not current.is_file():
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension build file is missing")
    return current


def _validate_file_rows(value: Any, code: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value or len(value) > MAX_PACKAGE_FILES:
        _fail(code, "Extension package files are invalid")
    rows: list[dict[str, str]] = []
    total_paths: list[str] = []
    for row in value:
        if not isinstance(row, dict) or set(row) != FILE_FIELDS:
            _fail(code, "Extension package file fields are invalid")
        path = row.get("path")
        _relative_parts(path, code)
        if not isinstance(row.get("sha256"), str) or not SHA256_RE.fullmatch(row["sha256"]):
            _fail(code, "Extension package file digest is invalid")
        if row.get("mode") not in {"0644", "0755"}:
            _fail(code, "Extension package file mode is invalid")
        total_paths.append(path)
        rows.append({"path": path, "mode": row["mode"], "sha256": row["sha256"]})
    if total_paths != sorted(total_paths) or len(total_paths) != len(set(total_paths)):
        _fail(code, "Extension package files must have unique canonical ordering")
    return rows


def _validate_tree(root: Path, files: list[dict[str, str]], manifest_name: str, code: str) -> None:
    expected = {row["path"]: row for row in files}
    actual: set[str] = set()
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            _fail(code, "Extension package paths must not be symlinked")
        if path.is_dir():
            continue
        if not path.is_file():
            _fail(code, "Extension package contains an unsupported path")
        relative = path.relative_to(root).as_posix()
        if relative == manifest_name:
            continue
        actual.add(relative)
        total += path.stat().st_size
        if total > MAX_PACKAGE_BYTES:
            _fail(code, "Extension package exceeds the size limit")
        row = expected.get(relative)
        if row is None:
            _fail(code, "Extension package contains an undeclared file")
        if stat.S_IMODE(path.stat().st_mode) != int(row["mode"], 8):
            _fail(code, "Extension package file mode does not match")
        if digest_bytes(path.read_bytes()) != row["sha256"]:
            _fail(code, "Extension package file digest does not match")
    if actual != set(expected):
        _fail(code, "Extension package is missing a declared file")


def _validate_required_files(
    root: Path,
    identity: dict[str, Any],
    files: list[dict[str, str]],
    code: str,
) -> None:
    paths = {row["path"]: row for row in files}
    executable = f"bin/{identity['executable']}"
    if executable not in paths or paths[executable]["mode"] != "0755":
        _fail(code, "Extension package executable is missing or not executable")
    for path, row in paths.items():
        if path != executable and row["mode"] != "0644":
            _fail(code, "Only the extension executable may be executable")
        if path not in {executable, "LICENSE"} and not path.startswith("hosts/"):
            _fail(code, "Extension package contains an unsupported file")
        parts = PurePosixPath(path).parts
        if path not in {executable, "LICENSE"} and (
            len(parts) < 3 or parts[1] not in identity["hosts"]
        ):
            _fail(code, "Extension package contains an undeclared host payload")
    for host in identity["hosts"]:
        if host == "claude":
            marketplace_path = root / "hosts/claude/.claude-plugin/marketplace.json"
            manifest_path = root / f"hosts/claude/plugins/{identity['name']}/.claude-plugin/plugin.json"
        else:
            marketplace_path = root / "hosts/codex/.agents/plugins/marketplace.json"
            manifest_path = root / f"hosts/codex/plugins/{identity['name']}/.codex-plugin/plugin.json"
        marketplace = _read_json(marketplace_path, code)
        plugin = _read_json(manifest_path, code)
        if marketplace.get("name") != identity["name"] or plugin.get("name") != identity["name"]:
            _fail(code, "Extension host identity is invalid")
        if plugin.get("version") != identity["version"]:
            _fail(code, "Extension host version is invalid")
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
            _fail(code, "Extension host marketplace is invalid")
        entry = plugins[0]
        expected_source: str | dict[str, str]
        if host == "claude":
            expected_source = f"./plugins/{identity['name']}"
        else:
            expected_source = {
                "source": "local",
                "path": f"./plugins/{identity['name']}",
            }
        if entry.get("name") != identity["name"] or entry.get("source") != expected_source:
            _fail(code, "Extension host marketplace source is invalid")


def _validate_origin(value: Any) -> None:
    if not isinstance(value, dict) or value.get("type") not in {"local", "registry"}:
        _fail("FAB7_EXTENSION_INVALID", "Extension origin is invalid")
    if value["type"] == "local":
        if set(value) != {"type", "source_sha256"} or not isinstance(
            value.get("source_sha256"), str
        ) or not SHA256_RE.fullmatch(value["source_sha256"]):
            _fail("FAB7_EXTENSION_INVALID", "Local extension origin is invalid")
    elif (
        set(value) != {"type", "catalog_version", "artifact_url", "artifact_sha256"}
        or not isinstance(value.get("catalog_version"), str)
        or not isinstance(value.get("artifact_url"), str)
        or not isinstance(value.get("artifact_sha256"), str)
        or not SHA256_RE.fullmatch(value["artifact_sha256"])
    ):
        _fail("FAB7_EXTENSION_INVALID", "Registry extension origin is invalid")
    elif value["type"] == "registry":
        parse_version(value["catalog_version"], "FAB7_EXTENSION_INVALID", "Catalog version")


def _relative_parts(value: Any, code: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        _fail(code, "Extension path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts or path.as_posix() != value:
        _fail(code, "Extension path is invalid")
    return path.parts


def _read_json(path: Path, code: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        _fail(code, f"Extension JSON is missing or symlinked: {path.name}")
    try:
        if path.stat().st_size > MAX_PACKAGE_BYTES:
            _fail(code, f"Extension JSON exceeds the size limit: {path.name}")
        value = json.loads(path.read_text(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise Fab7Error(code, f"Invalid extension JSON: {path}") from exc
    if not isinstance(value, dict):
        _fail(code, "Extension JSON must be an object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    path.chmod(0o644)


def _write_json_atomic(path: Path, value: object) -> None:
    temporary = path.parent / f".{path.name}-{os.getpid()}"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    try:
        _write_json(temporary, value)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate key: {key}")
        value[key] = item
    return value


def _fail(code: str, message: str) -> None:
    raise Fab7Error(code, message)
