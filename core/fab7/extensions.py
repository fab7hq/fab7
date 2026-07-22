"""Closed extension catalog, installation, and lifecycle operations."""

from __future__ import annotations

import base64
import errno
import fcntl
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable
from urllib.parse import SplitResult, urlsplit
from urllib.request import Request, urlopen

from .errors import Fab7Error
from .extension_package import (
    MAX_PACKAGE_BYTES,
    build_local_package,
    digest_bytes,
    extract_package_archive,
    identity_from,
    materialize_installation,
    parse_version,
    require_compatible,
    set_integrations,
    validate_installation,
    validate_package,
)
from .hosts import install_plugin, uninstall_plugin
from .install import fab7_home


CATALOG_FIELDS = {"schema", "registry", "catalog_version", "extensions"}
ENTRY_FIELDS = {
    "name",
    "publisher",
    "repository",
    "version",
    "fab7_min",
    "fab7_max_exclusive",
    "executable",
    "capabilities",
    "hosts",
    "artifact",
}
ARTIFACT_FIELDS = {"url", "sha256"}
REGISTRY_ID = "fab7hq/ext-registry"
MAX_CATALOG_BYTES = 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,199}$")
SUPPORTED_HOSTS = {"claude", "codex"}
CATALOG_LOCK_FIELDS = {
    "schema", "registry", "ref", "blob_sha", "content_sha256"
}
CATALOG_API_URL = (
    "https://api.github.com/repos/fab7hq/ext-registry/contents/catalog.yaml?ref=main"
)
MAX_GITHUB_RESPONSE_BYTES = 2 * 1024 * 1024
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
Fetcher = Callable[[str, int], bytes]
PluginInstaller = Callable[[str, str, Path], dict[str, Any]]
PluginUninstaller = Callable[[str, str, Path], dict[str, Any]]


def load_catalog(path: Path) -> dict[str, Any]:
    candidate = path.expanduser()
    if candidate.is_symlink() or not candidate.is_file():
        raise Fab7Error("FAB7_CATALOG_MISSING", "Extension catalog is missing or symlinked")
    try:
        content = candidate.read_bytes()
    except OSError as exc:
        raise Fab7Error("FAB7_CATALOG_MISSING", "Extension catalog could not be read") from exc
    if len(content) > MAX_CATALOG_BYTES:
        raise Fab7Error("FAB7_CATALOG_INVALID", "Extension catalog exceeds the size limit")
    return parse_catalog(content)


def parse_catalog(content: bytes) -> dict[str, Any]:
    if len(content) > MAX_CATALOG_BYTES:
        raise Fab7Error("FAB7_CATALOG_INVALID", "Extension catalog exceeds the size limit")
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise Fab7Error(
            "FAB7_CATALOG_INVALID",
            "catalog.yaml must use the closed JSON-compatible YAML v1 syntax",
        ) from exc
    _validate_catalog(value)
    return value


def catalog_listing(
    path: Path | None = None,
    *,
    home: Path | None = None,
    include_installed: bool = False,
) -> dict[str, Any]:
    if path is None:
        path = _extension_home(home) / "catalog.yaml"
    catalog = load_catalog(path)
    extensions = catalog["extensions"]
    listing = {
        "ok": True,
        "catalog": str(path.expanduser().resolve()),
        "catalog_version": catalog["catalog_version"],
        "registry": catalog["registry"],
        "count": len(extensions),
        "extensions": extensions,
    }
    if include_installed:
        listing["installed"] = installed_extensions(home=home)
    return listing


def refresh_catalog(
    *,
    home: Path | None = None,
    url: str = CATALOG_API_URL,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    if url != CATALOG_API_URL:
        raise Fab7Error("FAB7_CATALOG_SOURCE_INVALID", "Fab7 accepts only the reviewed ext-registry source")
    raw = (fetcher or _fetch)(url, MAX_GITHUB_RESPONSE_BYTES)
    try:
        response = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise Fab7Error("FAB7_CATALOG_SOURCE_INVALID", "Registry source returned invalid JSON") from exc
    if not isinstance(response, dict):
        raise Fab7Error("FAB7_CATALOG_SOURCE_INVALID", "Registry source response is invalid")
    content = response.get("content")
    sha = response.get("sha")
    size = response.get("size")
    if (
        response.get("type") != "file"
        or response.get("encoding") != "base64"
        or not isinstance(content, str)
        or not isinstance(sha, str)
        or not GIT_SHA_RE.fullmatch(sha)
        or type(size) is not int
        or size < 0
        or size > MAX_CATALOG_BYTES
    ):
        raise Fab7Error("FAB7_CATALOG_SOURCE_INVALID", "Registry source identity is invalid")
    try:
        encoded = "".join(content.split())
        candidate = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise Fab7Error("FAB7_CATALOG_SOURCE_INVALID", "Registry source content is invalid") from exc
    if len(candidate) != size:
        raise Fab7Error("FAB7_CATALOG_SOURCE_INVALID", "Registry source size does not match")
    catalog = parse_catalog(candidate)
    extension_home = _extension_home(home)
    with _mutation_lock(extension_home):
        return _store_catalog(extension_home, candidate, catalog, sha)


def _store_catalog(
    extension_home: Path,
    candidate: bytes,
    catalog: dict[str, Any],
    sha: str,
) -> dict[str, Any]:
    catalog_path = extension_home / "catalog.yaml"
    lock_path = extension_home / "catalog.lock.json"
    if catalog_path.is_symlink() or lock_path.is_symlink():
        raise Fab7Error("FAB7_CATALOG_INVALID", "Catalog state must not be symlinked")
    prior_catalog: bytes | None = None
    prior_lock = lock_path.read_bytes() if lock_path.is_file() and not lock_path.is_symlink() else None
    status = "refreshed"
    if catalog_path.exists():
        current_bytes = catalog_path.read_bytes()
        prior_catalog = current_bytes
        current = parse_catalog(current_bytes)
        candidate_version = parse_version(
            catalog["catalog_version"], "FAB7_CATALOG_INVALID", "Catalog version"
        )
        current_version = parse_version(
            current["catalog_version"], "FAB7_CATALOG_INVALID", "Catalog version"
        )
        if candidate_version < current_version or (
            candidate_version == current_version and candidate != current_bytes
        ):
            raise Fab7Error(
                "FAB7_CATALOG_ROLLBACK",
                "Registry refresh would replace the last-known-good catalog with conflicting history",
            )
        if candidate == current_bytes:
            status = "already_current"
    lock = {
        "schema": 1,
        "registry": REGISTRY_ID,
        "ref": "main",
        "blob_sha": sha,
        "content_sha256": digest_bytes(candidate),
    }
    extension_home.mkdir(parents=True, exist_ok=True)
    _write_atomic(catalog_path, candidate, 0o644)
    try:
        _write_atomic(lock_path, json.dumps(lock, sort_keys=True, indent=2).encode() + b"\n", 0o644)
    except Exception:
        if prior_catalog is None and catalog_path.exists():
            catalog_path.unlink()
        elif prior_catalog is not None:
            _write_atomic(catalog_path, prior_catalog, 0o644)
        if prior_lock is not None:
            _write_atomic(lock_path, prior_lock, 0o644)
        raise
    return {
        "ok": True,
        "status": status,
        "catalog": str(catalog_path),
        "catalog_version": catalog["catalog_version"],
        "blob_sha": sha,
    }


def install_local_extension(
    source: Path,
    host: str,
    *,
    home: Path | None = None,
    plugin_installer: PluginInstaller | None = None,
    plugin_uninstaller: PluginUninstaller | None = None,
) -> dict[str, Any]:
    _host(host)
    with tempfile.TemporaryDirectory(prefix="fab7-extension-build-") as directory:
        temporary = Path(directory)
        package_root, source_sha256, package = build_local_package(source, temporary)
        install_id = "dev-" + source_sha256.removeprefix("sha256:")
        origin = {"type": "local", "source_sha256": source_sha256}
        return _install_prepared(
            package_root,
            package,
            install_id,
            origin,
            host,
            home=home,
            plugin_installer=plugin_installer,
            plugin_uninstaller=plugin_uninstaller,
        )


def install_registry_extension(
    name: str,
    host: str,
    *,
    catalog_path: Path | None = None,
    home: Path | None = None,
    fetcher: Fetcher | None = None,
    plugin_installer: PluginInstaller | None = None,
    plugin_uninstaller: PluginUninstaller | None = None,
) -> dict[str, Any]:
    _canonical_name(name)
    _host(host)
    path = catalog_path or (_extension_home(home) / "catalog.yaml")
    catalog = load_catalog(path)
    entry = next((item for item in catalog["extensions"] if item["name"] == name), None)
    if entry is None:
        raise Fab7Error("FAB7_EXTENSION_NOT_FOUND", f"Extension is not in the catalog: {name}")
    identity = identity_from(entry, "FAB7_CATALOG_INVALID")
    require_compatible(identity)
    if host not in identity["hosts"]:
        raise Fab7Error("FAB7_EXTENSION_HOST_UNSUPPORTED", f"Extension does not support {host}")
    artifact = entry["artifact"]
    archive = (fetcher or _fetch)(artifact["url"], MAX_PACKAGE_BYTES)
    if digest_bytes(archive) != artifact["sha256"]:
        raise Fab7Error("FAB7_EXTENSION_DIGEST_MISMATCH", "Extension artifact digest does not match")
    with tempfile.TemporaryDirectory(prefix="fab7-extension-package-") as directory:
        package_root = extract_package_archive(archive, Path(directory) / "package")
        package = validate_package(package_root, identity)
        origin = {
            "type": "registry",
            "catalog_version": catalog["catalog_version"],
            "artifact_url": artifact["url"],
            "artifact_sha256": artifact["sha256"],
        }
        return _install_prepared(
            package_root,
            package,
            identity["version"],
            origin,
            host,
            home=home,
            plugin_installer=plugin_installer,
            plugin_uninstaller=plugin_uninstaller,
        )


def installed_extensions(*, home: Path | None = None) -> list[dict[str, Any]]:
    extension_home = _extension_home(home)
    bin_root = extension_home / "bin"
    extensions_root = extension_home / "extensions"
    if bin_root.is_symlink() or extensions_root.is_symlink():
        raise Fab7Error("FAB7_HOME_INVALID", "Fab7 extension directories must not be symlinked")
    if not bin_root.exists():
        return []
    if not bin_root.is_dir() or (extensions_root.exists() and not extensions_root.is_dir()):
        raise Fab7Error("FAB7_HOME_INVALID", "Fab7 extension directories are invalid")
    installed: list[dict[str, Any]] = []
    for selector in sorted(bin_root.iterdir()):
        if selector.name == "fab7":
            continue
        if not selector.is_symlink():
            raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension selector must be a symlink")
        installation = _selected_installation(selector, extension_home)
        receipt = validate_installation(installation)
        if receipt["name"] != selector.name:
            raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension selector identity does not match")
        installed.append(
            {
                "name": receipt["name"],
                "version": receipt["version"],
                "install_id": receipt["install_id"],
                "origin": receipt["origin"]["type"],
                "hosts": receipt["hosts"],
                "integrations": receipt["integrations"],
            }
        )
    return installed


def extension_doctor(*, home: Path | None = None) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    try:
        installed = installed_extensions(home=home)
    except Fab7Error as exc:
        installed = []
        errors.append(exc.to_dict())
    extension_home = _extension_home(home)
    try:
        snapshot_count = _validate_installation_store(extension_home)
    except Fab7Error as exc:
        snapshot_count = 0
        errors.append(exc.to_dict())
    catalog_path = extension_home / "catalog.yaml"
    lock_path = extension_home / "catalog.lock.json"
    if catalog_path.exists() or lock_path.exists():
        try:
            catalog = load_catalog(catalog_path)
            lock = _read_lock(lock_path)
            if lock["content_sha256"] != digest_bytes(catalog_path.read_bytes()):
                raise Fab7Error("FAB7_CATALOG_INVALID", "Catalog lock digest does not match")
            catalog_version = catalog["catalog_version"]
        except Fab7Error as exc:
            errors.append(exc.to_dict())
            catalog_version = None
    else:
        catalog_version = None
    return {
        "ok": not errors,
        "errors": errors,
        "catalog_version": catalog_version,
        "installed": installed,
        "snapshot_count": snapshot_count,
    }


def uninstall_extension(
    name: str,
    host: str,
    *,
    home: Path | None = None,
    plugin_uninstaller: PluginUninstaller | None = None,
) -> dict[str, Any]:
    _canonical_name(name)
    _host(host)
    extension_home = _extension_home(home)
    with _mutation_lock(extension_home):
        return _uninstall_extension_locked(
            name,
            host,
            extension_home,
            plugin_uninstaller,
        )


def _uninstall_extension_locked(
    name: str,
    host: str,
    extension_home: Path,
    plugin_uninstaller: PluginUninstaller | None,
) -> dict[str, Any]:
    selector = extension_home / "bin" / name
    if not selector.is_symlink():
        raise Fab7Error("FAB7_EXTENSION_NOT_INSTALLED", f"Extension is not installed: {name}")
    installation = _selected_installation(selector, extension_home)
    receipt = validate_installation(installation, verify_files=False)
    if host not in receipt["hosts"]:
        raise Fab7Error("FAB7_EXTENSION_HOST_UNSUPPORTED", f"Extension does not support {host}")
    uninstaller = plugin_uninstaller or (
        lambda selected_host, selected_name, root: uninstall_plugin(
            selected_host, selected_name, host_root=root
        )
    )
    if host not in receipt["integrations"]:
        raise Fab7Error(
            "FAB7_EXTENSION_HOST_NOT_INSTALLED",
            f"Extension is not integrated with {host}",
        )
    uninstaller(host, name, installation / "hosts" / host)
    remaining = [item for item in receipt["integrations"] if item != host]
    if remaining:
        set_integrations(installation, remaining)
        return {
            "ok": True,
            "status": "host_uninstalled",
            "name": name,
            "host": host,
            "remaining_hosts": remaining,
        }
    selector.unlink()
    extension_root = extension_home / "extensions" / name
    if extension_root.is_symlink() or extension_root.resolve().parent != (
        extension_home / "extensions"
    ).resolve():
        raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension removal path is invalid")
    shutil.rmtree(extension_root)
    return {"ok": True, "status": "uninstalled", "name": name, "host": host}


def _install_prepared(
    package_root: Path,
    package: dict[str, Any],
    install_id: str,
    origin: dict[str, Any],
    host: str,
    *,
    home: Path | None,
    plugin_installer: PluginInstaller | None,
    plugin_uninstaller: PluginUninstaller | None,
) -> dict[str, Any]:
    extension_home = _extension_home(home)
    with _mutation_lock(extension_home):
        return _install_prepared_locked(
            package_root,
            package,
            install_id,
            origin,
            host,
            extension_home,
            plugin_installer,
            plugin_uninstaller,
        )


def _install_prepared_locked(
    package_root: Path,
    package: dict[str, Any],
    install_id: str,
    origin: dict[str, Any],
    host: str,
    extension_home: Path,
    plugin_installer: PluginInstaller | None,
    plugin_uninstaller: PluginUninstaller | None,
) -> dict[str, Any]:
    name = package["name"]
    if host not in package["hosts"]:
        raise Fab7Error("FAB7_EXTENSION_HOST_UNSUPPORTED", f"Extension does not support {host}")
    bin_root = extension_home / "bin"
    extensions_root = extension_home / "extensions"
    name_root = extensions_root / name
    for path in (bin_root, extensions_root, name_root):
        if path.is_symlink():
            raise Fab7Error("FAB7_HOME_INVALID", "Fab7 extension directories must not be symlinked")
    bin_root.mkdir(parents=True, exist_ok=True)
    name_root.mkdir(parents=True, exist_ok=True)
    target = name_root / install_id
    installed_new = False
    if target.exists() or target.is_symlink():
        receipt = validate_installation(target)
        if (
            {field: receipt[field] for field in package if field != "files"}
            != {field: package[field] for field in package if field != "files"}
            or receipt["files"] != package["files"]
            or receipt["origin"] != origin
        ):
            raise Fab7Error("FAB7_EXTENSION_IMMUTABLE", "Installed extension identity differs")
    else:
        stage = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=name_root))
        staged_installation = stage / install_id
        try:
            materialize_installation(package_root, staged_installation, install_id, origin)
            os.replace(staged_installation, target)
            installed_new = True
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        receipt = validate_installation(target)

    already_integrated = host in receipt["integrations"]

    selector = bin_root / name
    if selector.exists() and not selector.is_symlink():
        if installed_new:
            shutil.rmtree(target)
        raise Fab7Error("FAB7_EXTENSION_SELECTOR_CONFLICT", f"Refusing to replace non-symlink selector: {name}")
    previous = os.readlink(selector) if selector.is_symlink() else None
    previous_installation = (
        _selected_installation(selector, extension_home) if selector.is_symlink() else None
    )
    previous_receipt = (
        validate_installation(previous_installation) if previous_installation is not None else None
    )
    migrating = previous_installation is not None and previous_installation != target
    if migrating and previous_receipt is not None:
        other_hosts = [item for item in previous_receipt["integrations"] if item != host]
        if other_hosts:
            if installed_new:
                shutil.rmtree(target)
            raise Fab7Error(
                "FAB7_EXTENSION_HOSTS_ACTIVE",
                "Uninstall other host integrations before selecting a changed extension snapshot",
                {"hosts": other_hosts},
            )
    relative_target = Path("../extensions") / name / install_id / "bin" / name
    _replace_symlink(selector, relative_target)
    installer = plugin_installer or (
        lambda selected_host, selected_name, root: install_plugin(
            selected_host, selected_name, host_root=root
        )
    )
    uninstaller = plugin_uninstaller or (
        lambda selected_host, selected_name, root: uninstall_plugin(
            selected_host, selected_name, host_root=root
        )
    )
    previous_host_removed = False
    new_host_installed = False
    try:
        if migrating and previous_receipt is not None and host in previous_receipt["integrations"]:
            uninstaller(host, name, previous_installation / "hosts" / host)
            previous_host_removed = True
        host_result = installer(host, name, target / "hosts" / host)
        new_host_installed = True
        set_integrations(target, sorted({*receipt["integrations"], host}))
        if previous_host_removed and previous_installation is not None:
            set_integrations(previous_installation, [])
    except Exception as exc:
        rollback_errors: list[str] = []
        if new_host_installed:
            try:
                uninstaller(host, name, target / "hosts" / host)
                set_integrations(target, receipt["integrations"])
            except Exception as rollback_exc:
                rollback_errors.append(type(rollback_exc).__name__)
        if previous_host_removed and previous_installation is not None:
            try:
                installer(host, name, previous_installation / "hosts" / host)
                set_integrations(previous_installation, previous_receipt["integrations"])
            except Exception as rollback_exc:
                rollback_errors.append(type(rollback_exc).__name__)
        if previous is None:
            if selector.is_symlink():
                selector.unlink()
        else:
            _replace_symlink(selector, Path(previous))
        if installed_new:
            shutil.rmtree(target)
        if rollback_errors:
            raise Fab7Error(
                "FAB7_EXTENSION_ROLLBACK_FAILED",
                "Extension activation failed and host rollback did not complete",
                {"failures": rollback_errors},
            ) from exc
        raise
    return {
        "ok": True,
        "status": (
            "installed"
            if installed_new
            else ("already_installed" if already_integrated else "integrated")
        ),
        "name": name,
        "version": package["version"],
        "install_id": install_id,
        "origin": origin["type"],
        "host": host,
        "executable": str(selector),
        "activation": host_result.get("activation"),
    }


def _extension_home(home: Path | None) -> Path:
    if home is None:
        candidate = fab7_home()
    else:
        if home.is_symlink():
            raise Fab7Error("FAB7_HOME_INVALID", "FAB7_HOME must not be a symlink")
        candidate = home.expanduser().resolve()
    if candidate.exists() and not candidate.is_dir():
        raise Fab7Error("FAB7_HOME_INVALID", "FAB7_HOME must be a directory")
    return candidate


@contextmanager
def _mutation_lock(home: Path):
    if home.is_symlink():
        raise Fab7Error("FAB7_HOME_INVALID", "FAB7_HOME must not be a symlink")
    home.mkdir(parents=True, exist_ok=True)
    lock = home / ".extension.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError as exc:
        raise Fab7Error("FAB7_HOME_INVALID", "Fab7 extension lock could not be opened") from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise Fab7Error("FAB7_EXTENSION_BUSY", "Another extension mutation is running") from exc
            raise Fab7Error("FAB7_HOME_INVALID", "Fab7 extension lock could not be acquired") from exc
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _validate_installation_store(home: Path) -> int:
    root = home / "extensions"
    if not root.exists():
        return 0
    if root.is_symlink() or not root.is_dir():
        raise Fab7Error("FAB7_HOME_INVALID", "Fab7 extension installation root is invalid")
    selected: dict[str, Path] = {}
    bin_root = home / "bin"
    if bin_root.exists():
        if bin_root.is_symlink() or not bin_root.is_dir():
            raise Fab7Error("FAB7_HOME_INVALID", "Fab7 extension executable root is invalid")
        for selector in bin_root.iterdir():
            if selector.name != "fab7" and selector.is_symlink():
                selected[selector.name] = _selected_installation(selector, home)
    count = 0
    for name_root in sorted(root.iterdir()):
        if name_root.is_symlink() or not name_root.is_dir():
            raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension installation name root is invalid")
        try:
            _canonical_name(name_root.name)
        except Fab7Error as exc:
            raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension installation name is invalid") from exc
        for installation in sorted(name_root.iterdir()):
            receipt = validate_installation(installation)
            if receipt["name"] != name_root.name:
                raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension installation identity does not match")
            if receipt["integrations"] and selected.get(name_root.name) != installation.resolve():
                raise Fab7Error(
                    "FAB7_EXTENSION_INVALID",
                    "Only the selected extension snapshot may own host integrations",
                )
            count += 1
    return count


def _selected_installation(selector: Path, home: Path) -> Path:
    try:
        executable = selector.resolve(strict=True)
    except OSError as exc:
        raise Fab7Error("FAB7_EXTENSION_INVALID", "Selected extension executable is missing") from exc
    extensions_root = (home / "extensions").resolve()
    try:
        relative = executable.relative_to(extensions_root)
    except ValueError as exc:
        raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension selector escapes the installation root") from exc
    if (
        len(relative.parts) != 4
        or relative.parts[0] != selector.name
        or relative.parts[2] != "bin"
        or relative.parts[3] != selector.name
    ):
        raise Fab7Error("FAB7_EXTENSION_INVALID", "Extension selector path is invalid")
    return executable.parent.parent


def _replace_symlink(selector: Path, target: Path) -> None:
    temporary = selector.parent / f".{selector.name}-selector-{os.getpid()}"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(target)
    os.replace(temporary, selector)


def _read_lock(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise Fab7Error("FAB7_CATALOG_INVALID", "Catalog lock is missing or symlinked")
    try:
        value = json.loads(path.read_text(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise Fab7Error("FAB7_CATALOG_INVALID", "Catalog lock is invalid") from exc
    if (
        not isinstance(value, dict)
        or set(value) != CATALOG_LOCK_FIELDS
        or value.get("schema") != 1
        or value.get("registry") != REGISTRY_ID
        or value.get("ref") != "main"
        or not isinstance(value.get("blob_sha"), str)
        or not GIT_SHA_RE.fullmatch(value["blob_sha"])
        or not isinstance(value.get("content_sha256"), str)
        or not SHA256_RE.fullmatch(value["content_sha256"])
    ):
        raise Fab7Error("FAB7_CATALOG_INVALID", "Catalog lock identity is invalid")
    return value


def _fetch(url: str, limit: int) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fab7-extension-distribution",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            hostname = urlsplit(response.geturl()).hostname
            if hostname not in {
                "api.github.com",
                "github.com",
                "objects.githubusercontent.com",
                "release-assets.githubusercontent.com",
            }:
                raise Fab7Error("FAB7_EXTENSION_DOWNLOAD_FAILED", "Extension download redirected unexpectedly")
            content = response.read(limit + 1)
    except Fab7Error:
        raise
    except OSError as exc:
        raise Fab7Error("FAB7_EXTENSION_DOWNLOAD_FAILED", f"Extension download failed: {exc}") from exc
    if len(content) > limit:
        raise Fab7Error("FAB7_EXTENSION_DOWNLOAD_FAILED", "Extension download exceeds the size limit")
    return content


def _write_atomic(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _canonical_name(name: str) -> None:
    if not NAME_RE.fullmatch(name) or name == "fab7":
        raise Fab7Error("FAB7_EXTENSION_NAME_INVALID", "Extension name is invalid")


def _host(host: str) -> None:
    if host not in SUPPORTED_HOSTS:
        raise Fab7Error("FAB7_HOST_UNSUPPORTED", "Supported hosts are claude and codex")


def _validate_catalog(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != CATALOG_FIELDS:
        _invalid("Catalog fields are invalid")
    if type(value["schema"]) is not int or value["schema"] != 1:
        _invalid("Catalog schema is invalid")
    if value["registry"] != REGISTRY_ID:
        _invalid("Catalog registry identity is invalid")
    _version(value["catalog_version"], "Catalog version")
    extensions = value["extensions"]
    if not isinstance(extensions, list):
        _invalid("Catalog extensions must be a list")
    for entry in extensions:
        _validate_entry(entry)
    names = [entry["name"] for entry in extensions]
    if names != sorted(names) or len(names) != len(set(names)):
        _invalid("Catalog extensions must have unique canonical ordering")


def _validate_entry(entry: Any) -> None:
    if not isinstance(entry, dict) or set(entry) != ENTRY_FIELDS:
        _invalid("Extension fields are invalid")
    try:
        identity = identity_from(entry, "FAB7_CATALOG_INVALID")
    except Fab7Error as exc:
        raise Fab7Error("FAB7_CATALOG_INVALID", exc.message) from exc
    version = _version(identity["version"], "Extension version")
    repository_path = f"{identity['publisher']}/{identity['name']}"
    _artifact(entry["artifact"], repository_path, version)


def _artifact(value: Any, repository_path: str, version: tuple[int, int, int]) -> None:
    if not isinstance(value, dict) or set(value) != ARTIFACT_FIELDS:
        _invalid("Extension artifact fields are invalid")
    url = value["url"]
    digest = value["sha256"]
    if not isinstance(url, str) or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        _invalid("Extension artifact identity is invalid")
    parsed = _url(url, "Extension artifact identity is invalid")
    version_text = ".".join(str(part) for part in version)
    prefix = f"/{repository_path}/releases/download/v{version_text}/"
    asset_name = parsed.path.removeprefix(prefix)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(prefix)
        or not ASSET_RE.fullmatch(asset_name)
        or url != f"https://github.com{parsed.path}"
    ):
        _invalid("Extension artifact URL is not an immutable GitHub release asset")


def _version(value: Any, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) > 32 or not VERSION_RE.fullmatch(value):
        _invalid(f"{label} is invalid")
    parsed = tuple(int(part) for part in value.split("."))
    if value != ".".join(str(part) for part in parsed):
        _invalid(f"{label} is not canonical")
    return parsed


def _url(value: str, message: str) -> SplitResult:
    try:
        return urlsplit(value)
    except ValueError:
        _invalid(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _invalid(message: str) -> None:
    raise Fab7Error("FAB7_CATALOG_INVALID", message)
