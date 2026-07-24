"""Closed extension source, package, and installed-receipt contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import tomllib
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from ..errors import Fab7Error
from ..install import fab7_home
from ..native_build import build_native_executable
from ..plugin.adapter import PluginAction, PluginMetadata
from ..plugin.build import build_plugin_roots
from ..toolchain import PYPI_INDEX, PYTHON_VERSION


FAB7_API = 1
SOURCE_FIELDS = {"schema", "name", "publisher", "version"}
IDENTITY_FIELDS = {
    "name",
    "publisher",
    "version",
    "fab7_api",
    "hosts",
}
BUILD_FIELDS = {
    "target",
    "source_sha256",
    "toolchain_sha256",
    "dependency_lock_sha256",
    "dependency_requirements_sha256",
    "dependency_root_sha256",
    "executable_sha256",
}
PACKAGE_FIELDS = {"schema", *IDENTITY_FIELDS, "build", "files"}
FILE_FIELDS = {"path", "mode", "sha256"}
RECEIPT_FIELDS = {
    "schema",
    "install_id",
    "origin",
    "integrations",
    "package_sha256",
    *IDENTITY_FIELDS,
    "build",
    "files",
}
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
INSTALL_ID_RE = re.compile(
    r"^(?:dev-[0-9a-f]{64}|[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{64})$"
)
SUPPORTED_HOSTS = {"claude", "codex"}
MAX_SOURCE_FILES = 512
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PACKAGE_FILES = 256
MAX_PACKAGE_BYTES = 96 * 1024 * 1024
IGNORED_SOURCE_DIRECTORIES = {"__pycache__", ".venv", "dist"}
IGNORED_SOURCE_SUFFIXES = {".pyc", ".pyo"}
ENTRYPOINT = "src/extension.py"


def source_identity_from(value: dict[str, Any], code: str) -> dict[str, Any]:
    fields = ("name", "publisher", "version")
    identity = {field: value.get(field) for field in fields}
    if any(field not in value for field in fields):
        _fail(code, "Extension identity fields are invalid")
    for field in ("name", "publisher"):
        item = identity[field]
        if not isinstance(item, str) or not NAME_RE.fullmatch(item):
            _fail(code, f"Extension {field} is invalid")
    if identity["name"] == "fab7":
        _fail(code, "Extension name is invalid")
    parse_version(identity["version"], code, "Extension version")
    return identity


def identity_from(value: dict[str, Any], code: str) -> dict[str, Any]:
    identity = source_identity_from(value, code)
    if type(value.get("fab7_api")) is not int or value["fab7_api"] != FAB7_API:
        _fail(code, "Extension Fab7 API is incompatible")
    hosts = value.get("hosts")
    if (
        not isinstance(hosts, list)
        or not hosts
        or not all(isinstance(item, str) and NAME_RE.fullmatch(item) for item in hosts)
        or hosts != sorted(hosts)
        or len(hosts) != len(set(hosts))
        or not set(hosts).issubset(SUPPORTED_HOSTS)
    ):
        _fail(code, "Extension hosts are invalid")
    return {**identity, "fab7_api": FAB7_API, "hosts": hosts}


def require_compatible(identity: dict[str, Any]) -> None:
    if identity.get("fab7_api") != FAB7_API:
        _fail("FAB7_EXTENSION_INCOMPATIBLE", "Extension Fab7 API is incompatible")


def validate_package(root: Path, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package root is missing or symlinked")
    root = root.resolve()
    manifest_path = root / "extension.json"
    manifest = _read_json(manifest_path, "FAB7_EXTENSION_PACKAGE_INVALID")
    if set(manifest) != PACKAGE_FIELDS or manifest.get("schema") != 1:
        _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package manifest fields are invalid")
    identity = identity_from(manifest, "FAB7_EXTENSION_PACKAGE_INVALID")
    if expected is not None and identity != expected:
        _fail("FAB7_EXTENSION_PACKAGE_INVALID", "Extension package identity does not match its source")
    build = _validate_build(manifest.get("build"), "FAB7_EXTENSION_PACKAGE_INVALID")
    files = _validate_file_rows(manifest["files"], "FAB7_EXTENSION_PACKAGE_INVALID")
    _validate_tree(root, files, "extension.json", "FAB7_EXTENSION_PACKAGE_INVALID")
    _validate_required_files(root, identity, files, "FAB7_EXTENSION_PACKAGE_INVALID")
    executable = root / "bin" / identity["name"]
    if digest_bytes(executable.read_bytes()) != build["executable_sha256"]:
        _fail(
            "FAB7_EXTENSION_PACKAGE_INVALID",
            "Extension build executable digest does not match",
        )
    return {**identity, "build": build, "files": files}


def _build_package(
    source_root: Path,
    output_root: Path,
    identity: dict[str, Any],
    native_executable: Path,
    build: dict[str, str],
    skills: list[dict[str, str]],
    skill_files: list[str],
    *,
    include_license: bool,
) -> None:
    if output_root.is_symlink() or output_root.exists():
        raise Fab7Error(
            "FAB7_PLUGIN_BUILD_CONFLICT",
            f"Plugin output already exists: {output_root}",
        )
    output_root.mkdir(parents=True)
    executable = output_root / "bin" / identity["name"]
    executable.parent.mkdir(parents=True)
    if native_executable.is_symlink() or not native_executable.is_file():
        _fail("FAB7_NATIVE_BUILD_FAILED", "Native extension executable is missing")
    shutil.copyfile(native_executable, executable)
    executable.chmod(0o755)

    if include_license:
        license_path = output_root / "LICENSE"
        shutil.copyfile(_source_file(source_root, "LICENSE"), license_path)
        license_path.chmod(0o644)

    actions = tuple(
        PluginAction(
            name=row["name"],
            template=_source_file(source_root, row["source"]).read_text(),
            surface="skill",
        )
        for row in skills
    )
    display_name = " ".join(part.capitalize() for part in identity["name"].split("-"))
    description = f"{display_name} extension for Fab7."
    metadata = PluginMetadata(
        name=identity["name"],
        display_name=display_name,
        version=identity["version"],
        description=description,
        publisher=identity["publisher"],
        publisher_url=f"https://github.com/{identity['publisher']}",
        repository=f"https://github.com/{identity['publisher']}/{identity['name']}",
        license="MIT",
        capabilities=(),
        default_prompt=f"Start {display_name}.",
    )
    build_plugin_roots(output_root / "hosts", metadata, identity["hosts"], actions)
    skill_names = {row["name"] for row in skills}
    for relative in skill_files:
        parts = PurePosixPath(relative).parts
        if len(parts) < 3 or parts[0] != "skills" or parts[1] not in skill_names:
            raise Fab7Error(
                "FAB7_EXTENSION_SOURCE_INVALID",
                "Extension skill source layout is invalid",
            )
        if parts[2:] == ("SKILL.md",):
            continue
        for host in identity["hosts"]:
            destination = (
                output_root
                / "hosts"
                / host
                / "plugins"
                / identity["name"]
                / "skills"
                / parts[1]
            ).joinpath(*parts[2:])
            if destination.exists() or destination.is_symlink():
                raise Fab7Error(
                    "FAB7_PLUGIN_BUILD_CONFLICT",
                    "Extension skill source paths conflict",
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_source_file(source_root, relative), destination)
            destination.chmod(0o644)

    rows = []
    for path in sorted(candidate for candidate in output_root.rglob("*") if candidate.is_file()):
        rows.append(
            {
                "path": path.relative_to(output_root).as_posix(),
                "mode": "0755" if path == executable else "0644",
                "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest = {"schema": 1, **identity, "build": build, "files": rows}
    manifest_path = output_root / "extension.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    manifest_path.chmod(0o644)


def build_local_package(
    source: Path,
    temporary: Path,
    hosts: Iterable[str] | None = None,
    *,
    home: Path | None = None,
    uv_executable: str | Path | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    if source.is_symlink() or not source.is_dir():
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source is missing or symlinked")
    source = source.resolve()
    manifest = _read_json(source / "fab7-extension.json", "FAB7_EXTENSION_SOURCE_INVALID")
    if set(manifest) != SOURCE_FIELDS or manifest.get("schema") != 1:
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source manifest fields are invalid")
    selected_hosts = _build_targets(SUPPORTED_HOSTS if hosts is None else hosts)
    identity = identity_from(
        {**manifest, "fab7_api": FAB7_API, "hosts": selected_hosts},
        "FAB7_EXTENSION_SOURCE_INVALID",
    )
    _validate_project(source, identity)
    files, skills = _discover_source(source)

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

    selected_home = home or fab7_home()
    native_executable = temporary / "native" / identity["name"]
    native = build_native_executable(
        staged,
        staged / ENTRYPOINT,
        native_executable,
        name=identity["name"],
        home=selected_home,
        search_paths=(staged / "src",),
        extension_project=staged,
        smoke_args=("--help",),
        uv_executable=uv_executable,
    )
    source_sha256 = "sha256:" + digest.hexdigest()
    dependency = native["dependencies"]
    build = {
        "target": native["target"],
        "source_sha256": source_sha256,
        "toolchain_sha256": native["toolchain"]["sha256"],
        "dependency_lock_sha256": dependency["lock_sha256"],
        "dependency_requirements_sha256": dependency["requirements_sha256"],
        "dependency_root_sha256": dependency["root_sha256"],
        "executable_sha256": native["executable_sha256"],
    }
    output = temporary / "package"
    skill_files = [relative for relative in files if relative.startswith("skills/")]
    _build_package(
        staged,
        output,
        identity,
        native_executable,
        build,
        skills,
        skill_files,
        include_license="LICENSE" in files,
    )
    package = validate_package(output, identity)
    return output, source_sha256, package


def build_extension_archive(
    source: Path,
    output: Path | None = None,
    *,
    hosts: Iterable[str],
    home: Path | None = None,
    uv_executable: str | Path | None = None,
) -> dict[str, Any]:
    if output is not None and (output.expanduser().exists() or output.expanduser().is_symlink()):
        _fail("FAB7_EXTENSION_OUTPUT_INVALID", "Extension build output already exists")
    with tempfile.TemporaryDirectory(prefix="fab7-extension-build-") as directory:
        package_root, source_sha256, package = build_local_package(
            source,
            Path(directory),
            hosts,
            home=home,
            uv_executable=uv_executable,
        )
        destination = output
        if destination is None:
            destination = source.expanduser().resolve() / "dist" / (
                f"{package['name']}-{package['version']}-{package['build']['target']}-"
                f"{'-'.join(package['hosts'])}.zip"
            )
        destination = _write_package_archive(package_root, destination)
        content = destination.read_bytes()
        return {
            "ok": True,
            "status": "built",
            "name": package["name"],
            "version": package["version"],
            "hosts": package["hosts"],
            "target": package["build"]["target"],
            "output": str(destination),
            "source_sha256": source_sha256,
            "toolchain_sha256": package["build"]["toolchain_sha256"],
            "dependency_lock_sha256": package["build"]["dependency_lock_sha256"],
            "package_sha256": digest_bytes(content),
        }


def _discover_source(source: Path) -> tuple[list[str], list[dict[str, str]]]:
    files = ["fab7-extension.json", "pyproject.toml", "uv.lock"]
    discovered: dict[str, list[str]] = {}
    for root_name in ("src", "tests", "skills"):
        root = source / root_name
        if root.is_symlink() or not root.is_dir():
            _fail(
                "FAB7_EXTENSION_SOURCE_INVALID",
                f"Local extension source requires a {root_name}/ directory",
            )
        root_files: list[str] = []
        for path in sorted(root.rglob("*")):
            relative_to_root = path.relative_to(root)
            relative = path.relative_to(source).as_posix()
            if path.is_symlink():
                _fail(
                    "FAB7_EXTENSION_SOURCE_INVALID",
                    "Local extension source files must not be symlinked",
                )
            if any(part in IGNORED_SOURCE_DIRECTORIES for part in relative_to_root.parts):
                continue
            if path.is_dir():
                continue
            if not path.is_file():
                _fail(
                    "FAB7_EXTENSION_SOURCE_INVALID",
                    "Local extension source contains an unsupported path",
                )
            if path.suffix in IGNORED_SOURCE_SUFFIXES:
                continue
            root_files.append(relative)
        if not root_files:
            _fail(
                "FAB7_EXTENSION_SOURCE_INVALID",
                f"Local extension source {root_name}/ directory is empty",
            )
        discovered[root_name] = root_files
        files.extend(root_files)

    if ENTRYPOINT not in discovered["src"] or "src/__main__.py" in discovered["src"]:
        _fail(
            "FAB7_EXTENSION_SOURCE_INVALID",
            f"Local extension source requires canonical entrypoint {ENTRYPOINT}",
        )

    skill_root = source / "skills"
    skill_names: list[str] = []
    for path in sorted(skill_root.iterdir()):
        if path.name in IGNORED_SOURCE_DIRECTORIES:
            continue
        if path.is_symlink() or not path.is_dir() or not NAME_RE.fullmatch(path.name):
            _fail(
                "FAB7_EXTENSION_SOURCE_INVALID",
                "Local extension skill directories are invalid",
            )
        skill_names.append(path.name)
    if not skill_names or skill_names != sorted(skill_names) or len(skill_names) != len(
        set(skill_names)
    ):
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension skills are invalid")
    skills = []
    for name in skill_names:
        relative = f"skills/{name}/SKILL.md"
        if relative not in discovered["skills"]:
            _fail(
                "FAB7_EXTENSION_SOURCE_INVALID",
                "Local extension skill entrypoint is missing",
            )
        skills.append({"name": name, "source": relative})

    license_path = source / "LICENSE"
    if license_path.is_symlink():
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension LICENSE must not be symlinked")
    if license_path.exists():
        if not license_path.is_file():
            _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension LICENSE is invalid")
        files.append("LICENSE")

    files = sorted(files)
    if len(files) > MAX_SOURCE_FILES or len(files) != len(set(files)):
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source exceeds the file limit")
    return files, skills


def _validate_project(source: Path, identity: dict[str, Any]) -> None:
    pyproject_path = _source_file(source, "pyproject.toml")
    lock_path = _source_file(source, "uv.lock")
    try:
        pyproject = tomllib.loads(pyproject_path.read_text())
        lock = tomllib.loads(lock_path.read_text())
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise Fab7Error(
            "FAB7_EXTENSION_DEPENDENCY_INVALID",
            "Extension pyproject.toml or uv.lock is invalid",
        ) from exc
    if set(pyproject) != {"project"} or not isinstance(pyproject["project"], dict):
        _fail(
            "FAB7_EXTENSION_DEPENDENCY_INVALID",
            "Extension pyproject.toml must contain only the closed project table",
        )
    project = pyproject["project"]
    if set(project) != {"name", "version", "requires-python", "dependencies"}:
        _fail(
            "FAB7_EXTENSION_DEPENDENCY_INVALID",
            "Extension project fields are invalid",
        )
    dependencies = project.get("dependencies")
    if (
        project.get("name") != identity["name"]
        or project.get("version") != identity["version"]
        or project.get("requires-python") != "==3.14.*"
        or not isinstance(dependencies, list)
        or not all(isinstance(item, str) and 0 < len(item) <= 512 for item in dependencies)
        or dependencies != sorted(dependencies)
        or len(dependencies) != len(set(dependencies))
    ):
        _fail(
            "FAB7_EXTENSION_DEPENDENCY_INVALID",
            "Extension project identity or dependencies are invalid",
        )
    prohibited = (" @ ", "git+", "file:", "http://", "https://", "../", "./")
    if any(any(token in dependency.lower() for token in prohibited) for dependency in dependencies):
        _fail(
            "FAB7_EXTENSION_DEPENDENCY_INVALID",
            "Extension dependencies must come only from the public Python package index",
        )
    if (
        lock.get("version") != 1
        or lock.get("requires-python") != "==3.14.*"
        or not isinstance(lock.get("package"), list)
    ):
        _fail(
            "FAB7_EXTENSION_LOCK_INVALID",
            "Extension uv.lock identity is invalid",
        )
    project_rows = [
        row
        for row in lock["package"]
        if isinstance(row, dict)
        and row.get("name") == identity["name"]
        and row.get("version") == identity["version"]
    ]
    if len(project_rows) != 1 or project_rows[0].get("source") != {"virtual": "."}:
        _fail(
            "FAB7_EXTENSION_LOCK_INVALID",
            "Extension uv.lock project identity is invalid",
        )
    seen: set[tuple[str, str]] = set()
    for row in lock["package"]:
        if not isinstance(row, dict):
            _fail("FAB7_EXTENSION_LOCK_INVALID", "Extension uv.lock packages are invalid")
        name = row.get("name")
        version = row.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            _fail("FAB7_EXTENSION_LOCK_INVALID", "Extension uv.lock packages are invalid")
        key = (name, version)
        if key in seen:
            _fail("FAB7_EXTENSION_LOCK_INVALID", "Extension uv.lock package identities repeat")
        seen.add(key)
        if row is project_rows[0]:
            continue
        if row.get("source") != {"registry": PYPI_INDEX}:
            _fail(
                "FAB7_EXTENSION_LOCK_INVALID",
                "Extension uv.lock contains a non-public registry source",
            )
        wheels = row.get("wheels")
        if not isinstance(wheels, list) or not wheels:
            _fail(
                "FAB7_EXTENSION_LOCK_INVALID",
                "Every locked extension dependency must publish a wheel",
            )
        for wheel in wheels:
            if (
                not isinstance(wheel, dict)
                or not isinstance(wheel.get("url"), str)
                or not wheel["url"].startswith("https://files.pythonhosted.org/")
                or not isinstance(wheel.get("hash"), str)
                or not SHA256_RE.fullmatch(wheel["hash"])
            ):
                _fail(
                    "FAB7_EXTENSION_LOCK_INVALID",
                    "Extension uv.lock wheel identity is invalid",
                )


def _validate_build(value: Any, code: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != BUILD_FIELDS:
        _fail(code, "Extension build fields are invalid")
    for field in BUILD_FIELDS - {"target"}:
        if not isinstance(value.get(field), str) or not SHA256_RE.fullmatch(value[field]):
            _fail(code, "Extension build digest is invalid")
    target = value.get("target")
    if (
        not isinstance(target, str)
        or not re.fullmatch(
            rf"(?:macos|linux)-(?:arm64|x86_64)-cpython-{re.escape(PYTHON_VERSION)}",
            target,
        )
    ):
        _fail(code, "Extension build target is invalid")
    return {field: value[field] for field in sorted(BUILD_FIELDS)}


def _build_targets(hosts: Iterable[str]) -> list[str]:
    selected = tuple(hosts)
    if not selected or len(selected) != len(set(selected)):
        _fail(
            "FAB7_EXTENSION_TARGET_INVALID",
            "Extension build targets must be unique and non-empty",
        )
    if any(host not in SUPPORTED_HOSTS for host in selected):
        _fail("FAB7_HOST_UNSUPPORTED", "Supported extension build hosts are claude and codex")
    return sorted(selected)


def _write_package_archive(package_root: Path, output: Path) -> Path:
    if output.suffix != ".zip":
        _fail("FAB7_EXTENSION_OUTPUT_INVALID", "Extension build output must end in .zip")
    parent = output.expanduser().absolute().parent
    if parent.is_symlink():
        _fail("FAB7_EXTENSION_OUTPUT_INVALID", "Extension build output parent is symlinked")
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent.resolve() / output.name
    if destination.exists() or destination.is_symlink():
        _fail("FAB7_EXTENSION_OUTPUT_INVALID", "Extension build output already exists")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w+b",
            dir=destination.parent,
            prefix=f".{destination.name}-",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        temporary.write_bytes(_package_archive_bytes(package_root))
        temporary.chmod(0o644)
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def package_archive_digest(package_root: Path) -> str:
    return digest_bytes(_package_archive_bytes(package_root))


def _package_archive_bytes(package_root: Path) -> bytes:
    rows = [
        (
            path.relative_to(package_root).as_posix(),
            stat.S_IMODE(path.stat().st_mode),
            path.read_bytes(),
        )
        for path in sorted(candidate for candidate in package_root.rglob("*") if candidate.is_file())
    ]
    return _archive_rows_bytes(rows)


def _archive_rows_bytes(rows: Iterable[tuple[str, int, bytes]]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_STORED,
        strict_timestamps=True,
    ) as archive:
        for relative, mode, content in sorted(rows):
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, content)
    return output.getvalue()


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


def extract_source_archive(content: bytes, destination: Path) -> Path:
    if len(content) > MAX_SOURCE_BYTES:
        _fail(
            "FAB7_EXTENSION_SOURCE_INVALID",
            "Extension source archive exceeds the size limit",
        )
    if destination.exists() or destination.is_symlink():
        _fail(
            "FAB7_EXTENSION_SOURCE_INVALID",
            "Extension source extraction target already exists",
        )
    destination.mkdir(parents=True)
    total = 0
    names: set[str] = set()
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_SOURCE_FILES:
                _fail(
                    "FAB7_EXTENSION_SOURCE_INVALID",
                    "Extension source archive entries are invalid",
                )
            for info in entries:
                if info.is_dir() or info.filename in names:
                    _fail(
                        "FAB7_EXTENSION_SOURCE_INVALID",
                        "Extension source archive entries are invalid",
                    )
                parts = _relative_parts(info.filename, "FAB7_EXTENSION_SOURCE_INVALID")
                mode = info.external_attr >> 16
                permissions = stat.S_IMODE(mode)
                if info.create_system != 3 or not stat.S_ISREG(mode) or permissions not in {
                    0o644,
                    0o755,
                }:
                    _fail(
                        "FAB7_EXTENSION_SOURCE_INVALID",
                        "Extension source archive mode is invalid",
                    )
                total += info.file_size
                if total > MAX_SOURCE_BYTES:
                    _fail(
                        "FAB7_EXTENSION_SOURCE_INVALID",
                        "Extension source archive expands beyond the size limit",
                    )
                names.add(info.filename)
                target = destination.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
                target.chmod(permissions)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise Fab7Error(
            "FAB7_EXTENSION_SOURCE_INVALID",
            "Extension source archive is invalid",
        ) from exc
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
            "package_sha256": package_archive_digest(package_root),
            **{field: package[field] for field in IDENTITY_FIELDS},
            "build": package["build"],
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
    build = _validate_build(receipt.get("build"), "FAB7_EXTENSION_INVALID")
    if (
        not isinstance(receipt.get("package_sha256"), str)
        or not SHA256_RE.fullmatch(receipt["package_sha256"])
    ):
        _fail("FAB7_EXTENSION_INVALID", "Extension package digest is invalid")
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
        package_manifest = {
            "schema": 1,
            **identity,
            "build": build,
            "files": files,
        }
        rows = [
            (
                row["path"],
                int(row["mode"], 8),
                root.joinpath(*PurePosixPath(row["path"]).parts).read_bytes(),
            )
            for row in files
        ]
        rows.append(
            (
                "extension.json",
                0o644,
                (json.dumps(package_manifest, sort_keys=True, indent=2) + "\n").encode(),
            )
        )
        if digest_bytes(_archive_rows_bytes(rows)) != receipt["package_sha256"]:
            _fail("FAB7_EXTENSION_INVALID", "Extension package digest does not match")
    return {**receipt, "build": build, "files": files}


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


def _source_file(root: Path, relative: Any) -> Path:
    parts = _relative_parts(relative, "FAB7_EXTENSION_SOURCE_INVALID")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source files must not be symlinked")
    if not current.is_file():
        _fail("FAB7_EXTENSION_SOURCE_INVALID", "Local extension source file is missing")
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
    executable = f"bin/{identity['name']}"
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
        set(value)
        != {
            "type",
            "catalog_version",
            "source_url",
            "source_bundle_sha256",
            "source_sha256",
        }
        or not isinstance(value.get("catalog_version"), str)
        or not isinstance(value.get("source_url"), str)
        or not isinstance(value.get("source_bundle_sha256"), str)
        or not SHA256_RE.fullmatch(value["source_bundle_sha256"])
        or not isinstance(value.get("source_sha256"), str)
        or not SHA256_RE.fullmatch(value["source_sha256"])
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
