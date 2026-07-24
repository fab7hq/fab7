"""Host uv identity and pinned CPython ownership for native Fab7 builds."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

from .errors import Fab7Error


RECOMMENDED_UV_VERSION = "0.11.29"
PYTHON_VERSION = "3.14.6"
PYINSTALLER_VERSION = "6.21.0"
PYINSTALLER_HOOKS_VERSION = "2026.6"
UV_INSTALL_URL = "https://docs.astral.sh/uv/getting-started/installation/"
PYPI_INDEX = "https://pypi.org/simple"
COMMAND_TIMEOUT = 300
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
UV_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")

_ENV_ALLOWLIST = {
    "HOME",
    "PATH",
    "TMPDIR",
    "TMP",
    "TEMP",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "https_proxy",
    "http_proxy",
    "no_proxy",
}


def require_uv(executable: str | Path | None = None) -> dict[str, str]:
    """Resolve uv and record the actual executable used for this build."""

    selected = str(executable) if executable is not None else shutil.which("uv")
    if not selected:
        raise Fab7Error(
            "FAB7_UV_MISSING",
            f"Fab7 requires uv on PATH; install it from {UV_INSTALL_URL}",
        )
    path = Path(selected).expanduser()
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise Fab7Error(
            "FAB7_UV_MISSING",
            f"Fab7 requires uv on PATH; install it from {UV_INSTALL_URL}",
        ) from exc
    if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
        raise Fab7Error("FAB7_UV_INVALID", "The selected uv executable is invalid")
    try:
        process = subprocess.run(
            [str(path), "--version"],
            env=_base_environment(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fab7Error("FAB7_UV_INVALID", "The selected uv executable could not run") from exc
    match = re.fullmatch(r"uv ([^ \n]+)(?: .*)?\n?", process.stdout)
    if (
        process.returncode != 0
        or match is None
        or UV_VERSION_RE.fullmatch(match.group(1)) is None
    ):
        raise Fab7Error("FAB7_UV_INVALID", "The selected uv version output is invalid")
    return {
        "path": str(path),
        "version": match.group(1),
        "sha256": digest_file(path),
    }


def install_python(home: Path, uv: dict[str, str]) -> dict[str, Any]:
    """Install and validate Fab7's exact managed CPython."""

    roots = toolchain_roots(home)
    roots["cache"].mkdir(parents=True, exist_ok=True)
    roots["python"].mkdir(parents=True, exist_ok=True)
    install_environment = uv_environment(roots, allow_python_downloads=True)
    run_tool(
        [
            uv["path"],
            "python",
            "install",
            PYTHON_VERSION,
            "--install-dir",
            str(roots["python"]),
            "--cache-dir",
            str(roots["cache"]),
            "--no-bin",
            "--no-config",
        ],
        install_environment,
        "FAB7_PYTHON_INSTALL_FAILED",
        "Fab7 could not install its pinned CPython",
    )
    return find_python(home, uv)


def find_python(home: Path, uv: dict[str, str]) -> dict[str, Any]:
    """Find only the already installed Fab7-managed CPython."""

    roots = toolchain_roots(home)
    process = run_tool(
        [
            uv["path"],
            "python",
            "find",
            PYTHON_VERSION,
            "--managed-python",
            "--no-python-downloads",
            "--no-config",
            "--no-project",
        ],
        uv_environment(roots),
        "FAB7_PYTHON_MISSING",
        "Fab7's pinned CPython is not installed",
    )
    raw = process.stdout.strip()
    if not raw:
        raise Fab7Error("FAB7_PYTHON_INVALID", "uv returned no managed Python path")
    try:
        executable = Path(raw).resolve(strict=True)
    except OSError as exc:
        raise Fab7Error("FAB7_PYTHON_INVALID", "Fab7's managed Python path is invalid") from exc
    try:
        executable.relative_to(roots["python"])
    except ValueError as exc:
        raise Fab7Error(
            "FAB7_PYTHON_INVALID",
            "Fab7's managed Python escapes the owned toolchain root",
        ) from exc
    script = (
        "import json,platform,sys,sysconfig;"
        "print(json.dumps({"
        "'implementation':platform.python_implementation(),"
        "'version':platform.python_version(),"
        "'platform':platform.system().lower(),"
        "'architecture':platform.machine().lower(),"
        "'gil_disabled':bool(sysconfig.get_config_var('Py_GIL_DISABLED'))"
        "},sort_keys=True))"
    )
    result = run_tool(
        [str(executable), "-I", "-c", script],
        python_environment(),
        "FAB7_PYTHON_INVALID",
        "Fab7's managed Python could not be validated",
    )
    try:
        record = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Fab7Error("FAB7_PYTHON_INVALID", "Fab7's managed Python returned invalid metadata") from exc
    if (
        record.get("implementation") != "CPython"
        or record.get("version") != PYTHON_VERSION
        or record.get("gil_disabled") is not False
        or record.get("platform") not in {"darwin", "linux"}
        or record.get("architecture") not in {"arm64", "aarch64", "x86_64", "amd64"}
    ):
        raise Fab7Error(
            "FAB7_PYTHON_INVALID",
            "Fab7 requires standard GIL-enabled CPython 3.14.6 on macOS or Linux",
        )
    return {
        "path": str(executable),
        "implementation": "CPython",
        "version": PYTHON_VERSION,
        "platform": record["platform"],
        "architecture": _architecture(record["architecture"]),
        "sha256": digest_file(executable),
    }


def provision_toolchain(
    home: Path,
    *,
    uv_executable: str | Path | None = None,
    install: bool = True,
    requirements: Path | None = None,
) -> dict[str, Any]:
    """Return the closed toolchain record, installing Python only when requested."""

    uv = require_uv(uv_executable)
    python = install_python(home, uv) if install else find_python(home, uv)
    requirements_digest = digest_file(requirements) if requirements is not None else None
    record: dict[str, Any] = {
        "uv": uv,
        "python": python,
        "pyinstaller": PYINSTALLER_VERSION,
        "pyinstaller_hooks": PYINSTALLER_HOOKS_VERSION,
        "target": native_target(python),
    }
    if requirements_digest is not None:
        record["build_requirements_sha256"] = requirements_digest
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    record["sha256"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return record


def inspect_toolchain(
    home: Path,
    *,
    uv_executable: str | Path | None = None,
) -> dict[str, Any]:
    requirements = Path(__file__).with_name("build-requirements.txt")
    if requirements.is_symlink() or not requirements.is_file():
        raise Fab7Error(
            "FAB7_BUILD_ENVIRONMENT_FAILED",
            "Fab7's locked build requirements are missing",
        )
    return provision_toolchain(
        home,
        uv_executable=uv_executable,
        install=False,
        requirements=requirements,
    )


def native_target(python: dict[str, Any] | None = None) -> str:
    system = (python or {}).get("platform") or platform.system().lower()
    machine = (python or {}).get("architecture") or _architecture(platform.machine().lower())
    operating_system = {"darwin": "macos", "linux": "linux"}.get(system)
    if operating_system is None or machine not in {"arm64", "x86_64"}:
        raise Fab7Error(
            "FAB7_TARGET_UNSUPPORTED",
            "Fab7 native builds support macOS and Linux on arm64 or x86_64",
        )
    return f"{operating_system}-{machine}-cpython-{PYTHON_VERSION}"


def toolchain_roots(home: Path) -> dict[str, Path]:
    if home.is_symlink():
        raise Fab7Error("FAB7_HOME_INVALID", "FAB7_HOME must not be a symlink")
    resolved = home.expanduser().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise Fab7Error("FAB7_HOME_INVALID", "FAB7_HOME must be a directory")
    return {
        "home": resolved,
        "cache": resolved / "cache" / "uv",
        "python": resolved / "toolchains" / "python",
        "builds": resolved / "builds",
    }


def uv_environment(
    roots: dict[str, Path],
    *,
    allow_python_downloads: bool = False,
    pyinstaller_config: Path | None = None,
) -> dict[str, str]:
    environment = _base_environment()
    environment.update(
        {
            "UV_CACHE_DIR": str(roots["cache"]),
            "UV_PYTHON_INSTALL_DIR": str(roots["python"]),
            "UV_PYTHON_INSTALL_BIN": "0",
            "UV_MANAGED_PYTHON": "1",
            "UV_NO_CONFIG": "1",
            "UV_LINK_MODE": "copy",
            "UV_PYTHON_DOWNLOADS": "automatic" if allow_python_downloads else "never",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": "0",
            "TZ": "UTC",
            "LC_ALL": "C",
        }
    )
    if pyinstaller_config is not None:
        environment["PYINSTALLER_CONFIG_DIR"] = str(pyinstaller_config)
    return environment


def python_environment() -> dict[str, str]:
    environment = _base_environment()
    environment.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": "0",
            "TZ": "UTC",
            "LC_ALL": "C",
        }
    )
    return environment


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def digest_tree(root: Path, paths: Iterable[Path] | None = None) -> str:
    digest = hashlib.sha256()
    selected = paths if paths is not None else sorted(path for path in root.rglob("*") if path.is_file())
    for path in selected:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def run_tool(
    command: list[str],
    environment: dict[str, str],
    code: str,
    message: str,
    *,
    cwd: Path | None = None,
    timeout: int = COMMAND_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fab7Error(code, message) from exc
    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()
        if len(detail) > 2000:
            detail = detail[-2000:]
        raise Fab7Error(code, message, {"detail": detail})
    return process


def _base_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key in _ENV_ALLOWLIST}


def _architecture(value: str) -> str:
    return {"aarch64": "arm64", "amd64": "x86_64"}.get(value, value)
