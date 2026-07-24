"""User-global release selection and project-local Fab7 installation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .errors import Fab7Error
from .ledger import init as init_records


MANIFEST_FIELDS = {
    "schema",
    "name",
    "version",
    "source_sha256",
    "executable_sha256",
    "target",
    "toolchain",
}
TOOLCHAIN_FIELDS = {
    "uv",
    "python",
    "pyinstaller",
    "pyinstaller_hooks",
    "target",
    "build_requirements_sha256",
    "sha256",
}
UV_FIELDS = {"path", "version", "sha256"}
PYTHON_FIELDS = {
    "path",
    "implementation",
    "version",
    "platform",
    "architecture",
    "sha256",
}
PROJECT_FIELDS = {"schema", "fab7_version", "executable_sha256"}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PROJECT_COMMANDS = {"claim", "verify", "ci-check", "audit", "doctor"}


def fab7_home() -> Path:
    configured = os.environ.get("FAB7_HOME")
    if configured == "":
        raise Fab7Error("FAB7_HOME_INVALID", "FAB7_HOME must not be empty")
    raw = Path(configured) if configured is not None else Path.home() / ".fab7"
    raw = raw.expanduser()
    if raw.is_symlink():
        raise Fab7Error("FAB7_HOME_INVALID", "FAB7_HOME must not be a symlink")
    return raw.resolve()


def validate_release(release_root: Path) -> dict[str, Any]:
    if release_root.is_symlink() or not release_root.is_dir():
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release directory is missing or symlinked")
    manifest_path = release_root / "manifest.json"
    executable = release_root / "bin" / "fab7"
    if manifest_path.is_symlink() or executable.is_symlink() or not executable.is_file():
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release manifest or executable is invalid")
    manifest = _read_json(manifest_path, "FAB7_RELEASE_INVALID")
    if set(manifest) != MANIFEST_FIELDS:
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release manifest fields are invalid")
    if (
        manifest.get("schema") != 1
        or manifest.get("name") != "fab7"
        or not isinstance(manifest.get("version"), str)
        or not VERSION_RE.fullmatch(manifest["version"])
        or not isinstance(manifest.get("target"), str)
    ):
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release identity is invalid")
    for field in ("source_sha256", "executable_sha256"):
        if not isinstance(manifest.get(field), str) or not SHA256_RE.fullmatch(manifest[field]):
            raise Fab7Error("FAB7_RELEASE_INVALID", f"Fab7 release {field} is invalid")
    if manifest["version"] != release_root.name:
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release directory does not match its version")
    _validate_toolchain(manifest["toolchain"], manifest["target"], release_root)
    if not os.access(executable, os.X_OK):
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release executable is not executable")
    if _digest(executable) != manifest["executable_sha256"]:
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release executable digest does not match")
    for host in ("claude", "codex"):
        if not (release_root / "hosts" / host).is_dir():
            raise Fab7Error("FAB7_RELEASE_INVALID", f"Fab7 release is missing its {host} host root")
    return manifest


def _validate_toolchain(value: Any, target: str, release_root: Path) -> None:
    from .toolchain import (
        PYINSTALLER_HOOKS_VERSION,
        PYINSTALLER_VERSION,
        PYTHON_VERSION,
        UV_VERSION_RE,
    )

    if not isinstance(value, dict) or set(value) != TOOLCHAIN_FIELDS:
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release toolchain fields are invalid")
    uv = value.get("uv")
    python = value.get("python")
    if (
        not isinstance(uv, dict)
        or set(uv) != UV_FIELDS
        or not isinstance(uv.get("version"), str)
        or UV_VERSION_RE.fullmatch(uv["version"]) is None
        or not isinstance(uv.get("path"), str)
        or not isinstance(uv.get("sha256"), str)
        or not SHA256_RE.fullmatch(uv["sha256"])
        or not isinstance(python, dict)
        or set(python) != PYTHON_FIELDS
        or python.get("implementation") != "CPython"
        or python.get("version") != PYTHON_VERSION
        or python.get("platform") not in {"darwin", "linux"}
        or python.get("architecture") not in {"arm64", "x86_64"}
        or not isinstance(python.get("path"), str)
        or not isinstance(python.get("sha256"), str)
        or not SHA256_RE.fullmatch(python["sha256"])
        or value.get("pyinstaller") != PYINSTALLER_VERSION
        or value.get("pyinstaller_hooks") != PYINSTALLER_HOOKS_VERSION
        or value.get("target") != target
        or not isinstance(value.get("build_requirements_sha256"), str)
        or not SHA256_RE.fullmatch(value["build_requirements_sha256"])
        or not isinstance(value.get("sha256"), str)
        or not SHA256_RE.fullmatch(value["sha256"])
    ):
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release toolchain identity is invalid")
    encoded = json.dumps(
        {key: item for key, item in value.items() if key != "sha256"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if "sha256:" + hashlib.sha256(encoded).hexdigest() != value["sha256"]:
        raise Fab7Error("FAB7_RELEASE_INVALID", "Fab7 release toolchain digest does not match")
    home = release_root.parent.parent
    try:
        Path(python["path"]).resolve().relative_to((home / "toolchains" / "python").resolve())
    except ValueError as exc:
        raise Fab7Error(
            "FAB7_RELEASE_INVALID",
            "Fab7 release Python path escapes the owned toolchain",
        ) from exc


def selected_release(home: Path | None = None) -> tuple[Path, dict[str, Any]]:
    home = home or fab7_home()
    if (home / "bin").is_symlink() or (home / "runtime").is_symlink():
        raise Fab7Error("FAB7_HOME_INVALID", "Fab7 bin and runtime directories must not be symlinks")
    selector = home / "bin" / "fab7"
    if not selector.is_symlink():
        raise Fab7Error("FAB7_GLOBAL_NOT_INSTALLED", "Run the Fab7 install script first")
    try:
        executable = selector.resolve(strict=True)
    except OSError as exc:
        raise Fab7Error("FAB7_GLOBAL_NOT_INSTALLED", "Selected Fab7 executable is missing") from exc
    runtime = (home / "runtime").resolve()
    try:
        executable.relative_to(runtime)
    except ValueError as exc:
        raise Fab7Error("FAB7_RELEASE_INVALID", "Selected Fab7 executable escapes the runtime directory") from exc
    if executable.name != "fab7" or executable.parent.name != "bin":
        raise Fab7Error("FAB7_RELEASE_INVALID", "Selected Fab7 executable path is invalid")
    release_root = executable.parent.parent
    manifest = validate_release(release_root)
    return release_root, manifest


def init_project(root: Path, home: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    workspace = root / ".fab7"
    if workspace.is_symlink():
        raise Fab7Error("FAB7_PATH_INVALID", "The project .fab7 directory must not be a symlink")
    project_path = workspace / "project.json"
    ignore_path = workspace / ".gitignore"
    local = workspace / "bin" / "fab7"
    existed = project_path.exists()

    if existed:
        project = _read_project(project_path)
        release_root = (home or fab7_home()) / "runtime" / project["fab7_version"]
        manifest = validate_release(release_root)
        if manifest["executable_sha256"] != project["executable_sha256"]:
            raise Fab7Error("FAB7_PROJECT_PIN_INVALID", "Project pin does not match the installed Fab7 release")
    else:
        release_root, manifest = selected_release(home)
        project = {
            "schema": 1,
            "fab7_version": manifest["version"],
            "executable_sha256": manifest["executable_sha256"],
        }

    _validate_workspace_paths(workspace, project_path, ignore_path, local)
    if local.exists() and not local.is_file():
        raise Fab7Error("FAB7_PATH_INVALID", "Project Fab7 executable path must be a regular file")
    if ignore_path.exists() and ignore_path.read_text() != "/bin/\n":
        raise Fab7Error("FAB7_PROJECT_IGNORE_INVALID", ".fab7/.gitignore must contain only /bin/")

    source = release_root / "bin" / "fab7"
    local_valid = local.is_file() and not local.is_symlink() and _digest(local) == project["executable_sha256"]
    workspace.mkdir(parents=True, exist_ok=True)
    if not local_valid:
        _copy_executable(source, local, project["executable_sha256"])
    if not existed:
        _write_json_atomic(project_path, project)
    if not ignore_path.exists():
        _write_text_atomic(ignore_path, "/bin/\n", 0o644)
    records = init_records(root)

    status = "initialized" if not existed else ("already_initialized" if local_valid else "repaired")
    return {
        "ok": True,
        "status": status,
        "project": str(project_path),
        "records": str(records),
        "executable": str(local),
        "fab7_version": project["fab7_version"],
        "executable_sha256": project["executable_sha256"],
        "next_action": "Commit .fab7/project.json and .fab7/.gitignore before recording evidence.",
    }


def validate_project(root: Path, home: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    workspace = root / ".fab7"
    project_path = workspace / "project.json"
    ignore_path = workspace / ".gitignore"
    local = workspace / "bin" / "fab7"
    _validate_workspace_paths(workspace, project_path, ignore_path, local)
    if not project_path.is_file():
        raise Fab7Error("FAB7_PROJECT_NOT_INITIALIZED", "Run fab7 init first")
    project = _read_project(project_path)
    if not ignore_path.is_file() or ignore_path.read_text() != "/bin/\n":
        raise Fab7Error("FAB7_PROJECT_IGNORE_INVALID", ".fab7/.gitignore must contain only /bin/")
    release_root = (home or fab7_home()) / "runtime" / project["fab7_version"]
    manifest = validate_release(release_root)
    if manifest["executable_sha256"] != project["executable_sha256"]:
        raise Fab7Error("FAB7_PROJECT_PIN_INVALID", "Project pin does not match the installed Fab7 release")
    if not local.is_file() or local.is_symlink() or not os.access(local, os.X_OK):
        raise Fab7Error("FAB7_PROJECT_EXECUTABLE_INVALID", "Run fab7 init to repair the local executable")
    if _digest(local) != project["executable_sha256"]:
        raise Fab7Error("FAB7_PROJECT_EXECUTABLE_INVALID", "Run fab7 init to repair the local executable")
    return {**project, "executable": str(local), "release": str(release_root)}


def dispatch_project(root: Path, command: str, argv: list[str], current_executable: Path) -> int | None:
    if command not in PROJECT_COMMANDS:
        return None
    local = root / ".fab7" / "bin" / "fab7"
    try:
        if not local.is_symlink() and current_executable.resolve() == local.resolve(strict=True):
            return None
    except OSError:
        pass
    project = validate_project(root)
    try:
        process = subprocess.run([project["executable"], *argv], cwd=root, env=os.environ.copy(), check=False)
    except OSError as exc:
        raise Fab7Error("FAB7_PROJECT_EXECUTABLE_INVALID", f"Project Fab7 could not start: {exc}") from exc
    return process.returncode


def _read_project(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise Fab7Error("FAB7_PROJECT_PIN_INVALID", "Project manifest must not be a symlink")
    project = _read_json(path, "FAB7_PROJECT_PIN_INVALID")
    if set(project) != PROJECT_FIELDS:
        raise Fab7Error("FAB7_PROJECT_PIN_INVALID", "Project manifest fields are invalid")
    if (
        project.get("schema") != 1
        or not isinstance(project.get("fab7_version"), str)
        or not VERSION_RE.fullmatch(project["fab7_version"])
        or not isinstance(project.get("executable_sha256"), str)
        or not SHA256_RE.fullmatch(project["executable_sha256"])
    ):
        raise Fab7Error("FAB7_PROJECT_PIN_INVALID", "Project manifest identity is invalid")
    return project


def _validate_workspace_paths(workspace: Path, project: Path, ignore: Path, executable: Path) -> None:
    for path in (workspace, project, ignore, workspace / "records", workspace / "bin", executable):
        if path.is_symlink():
            raise Fab7Error("FAB7_PATH_INVALID", "Fab7 project paths must not be symlinks", {"path": str(path)})


def _copy_executable(source: Path, destination: Path, expected_digest: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, prefix=".fab7-", delete=False) as handle:
            temporary = Path(handle.name)
            with source.open("rb") as input_handle:
                shutil.copyfileobj(input_handle, handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o755)
        if _digest(temporary) != expected_digest:
            raise Fab7Error("FAB7_RELEASE_INVALID", "Copied Fab7 executable digest does not match")
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _write_json_atomic(path: Path, value: object) -> None:
    _write_text_atomic(path, json.dumps(value, sort_keys=True, indent=2) + "\n", 0o644)


def _write_text_atomic(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise Fab7Error(code, f"Invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Fab7Error(code, f"JSON document must be an object: {path}")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate key: {key}")
        value[key] = item
    return value


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
