from __future__ import annotations

import hashlib
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import fab7.extension_package as extension_package
from fab7 import __version__
from fab7.errors import Fab7Error
from fab7.extension_package import validate_package
from fab7.extensions import (
    extension_doctor,
    install_local_extension,
    install_registry_extension,
    installed_extensions,
    uninstall_extension,
)


def _identity(version: str = "0.1.0") -> dict[str, object]:
    major, minor, _patch = (int(part) for part in __version__.split("."))
    return {
        "name": "muslin",
        "publisher": "fab7hq",
        "repository": "https://github.com/fab7hq/muslin",
        "version": version,
        "fab7_min": __version__,
        "fab7_max_exclusive": f"{major}.{minor + 1}.0",
        "executable": "muslin",
        "capabilities": ["smoke-test"],
        "hosts": ["claude", "codex"],
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _make_package(root: Path, version: str = "0.1.0") -> Path:
    identity = _identity(version)
    executable = root / "bin/muslin"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, subprocess\n"
        "p = subprocess.run(['fab7', '--version'], text=True, capture_output=True)\n"
        "print(json.dumps({'ok': p.returncode == 0, 'extension': 'muslin', 'fab7': p.stdout.strip()}))\n"
    )
    executable.chmod(0o755)

    _write_json(
        root / "hosts/claude/.claude-plugin/marketplace.json",
        {"name": "muslin", "plugins": [{"name": "muslin", "source": "./plugins/muslin"}]},
    )
    _write_json(
        root / "hosts/claude/plugins/muslin/.claude-plugin/plugin.json",
        {"name": "muslin", "version": version, "commands": "./commands/"},
    )
    command = root / "hosts/claude/plugins/muslin/commands/start.md"
    command.parent.mkdir(parents=True)
    command.write_text("---\ndescription: Start Muslin\n---\n\nRun `muslin start --json`.\n")

    _write_json(
        root / "hosts/codex/.agents/plugins/marketplace.json",
        {"name": "muslin", "plugins": [{"name": "muslin", "source": {"source": "local", "path": "./plugins/muslin"}}]},
    )
    _write_json(
        root / "hosts/codex/plugins/muslin/.codex-plugin/plugin.json",
        {"name": "muslin", "version": version, "skills": "./skills/"},
    )
    skill = root / "hosts/codex/plugins/muslin/skills/start/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: start\ndescription: Start Muslin\n---\n\nRun `muslin start --json`.\n"
    )

    files = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "mode": "0755" if path == executable else "0644",
                "sha256": _digest(path),
            }
        )
    _write_json(root / "extension.json", {"schema": 1, **identity, "files": files})
    return root


def _make_source(root: Path) -> Path:
    template = _make_package(root / "template")
    builder = root / "build.py"
    builder.write_text(
        "import pathlib, shutil, sys\n"
        "shutil.copytree(pathlib.Path('template'), pathlib.Path(sys.argv[1]))\n"
    )
    files = ["build.py", "fab7-extension.json"]
    files.extend(path.relative_to(root).as_posix() for path in sorted(template.rglob("*")) if path.is_file())
    _write_json(
        root / "fab7-extension.json",
        {
            "schema": 1,
            **_identity(),
            "build": {
                "command": ["{python}", "build.py", "{output}"],
                "files": sorted(files),
            },
        },
    )
    return root


def _archive(package: Path, destination: Path) -> bytes:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(candidate for candidate in package.rglob("*") if candidate.is_file()):
            relative = path.relative_to(package).as_posix()
            mode = stat.S_IFREG | (0o755 if relative == "bin/muslin" else 0o644)
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = mode << 16
            archive.writestr(info, path.read_bytes())
    return destination.read_bytes()


class PluginRecorder:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, str, Path]] = []

    def __call__(self, host: str, name: str, root: Path) -> dict[str, object]:
        self.calls.append((host, name, root))
        if self.fail:
            raise Fab7Error("FAB7_HOST_COMMAND_FAILED", "synthetic host failure")
        return {"ok": True, "status": "installed", "activation": "restart"}


class ManagedPluginRecorder:
    def __init__(self):
        self.active: dict[str, Path] = {}
        self.events: list[tuple[str, str, Path]] = []

    def install(self, host: str, name: str, root: Path) -> dict[str, object]:
        self.events.append(("install", host, root))
        if host in self.active and self.active[host] != root:
            raise Fab7Error("FAB7_HOST_MARKETPLACE_CONFLICT", "synthetic marketplace conflict")
        self.active[host] = root
        return {"ok": True, "status": "installed", "activation": "restart"}

    def uninstall(self, host: str, name: str, root: Path) -> dict[str, object]:
        self.events.append(("uninstall", host, root))
        if self.active.get(host) != root:
            raise Fab7Error("FAB7_HOST_MARKETPLACE_CONFLICT", "synthetic uninstall conflict")
        del self.active[host]
        return {"ok": True, "status": "uninstalled"}


def test_local_install_is_immutable_selected_and_diagnosable(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "muslin")
    plugin = PluginRecorder()

    result = install_local_extension(source, "claude", home=home, plugin_installer=plugin)

    assert result["origin"] == "local"
    assert result["install_id"].startswith("dev-")
    selector = home / "bin/muslin"
    assert selector.is_symlink()
    installation = selector.resolve().parent.parent
    assert installation.name == result["install_id"]
    receipt = json.loads((installation / "manifest.json").read_text())
    assert receipt["origin"]["type"] == "local"
    assert "source" not in receipt["origin"]
    assert plugin.calls == [("claude", "muslin", installation / "hosts/claude")]
    assert installed_extensions(home=home)[0]["name"] == "muslin"
    assert extension_doctor(home=home)["ok"] is True


def test_registry_install_verifies_artifact_and_uses_same_layout(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    package = _make_package(tmp_path / "package")
    archive = _archive(package, tmp_path / "muslin.zip")
    digest = "sha256:" + hashlib.sha256(archive).hexdigest()
    entry = {
        **_identity(),
        "artifact": {
            "url": "https://github.com/fab7hq/muslin/releases/download/v0.1.0/muslin-0.1.0.zip",
            "sha256": digest,
        },
    }
    catalog = tmp_path / "catalog.yaml"
    _write_json(
        catalog,
        {"schema": 1, "registry": "fab7hq/ext-registry", "catalog_version": "0.1.0", "extensions": [entry]},
    )
    plugin = PluginRecorder()

    result = install_registry_extension(
        "muslin",
        "codex",
        catalog_path=catalog,
        home=home,
        fetcher=lambda _url, _limit: archive,
        plugin_installer=plugin,
    )

    assert result["origin"] == "registry"
    assert result["install_id"] == "0.1.0"
    receipt = json.loads((home / "extensions/muslin/0.1.0/manifest.json").read_text())
    assert receipt["origin"] == {
        "artifact_sha256": digest,
        "artifact_url": entry["artifact"]["url"],
        "catalog_version": "0.1.0",
        "type": "registry",
    }

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_DIGEST_MISMATCH"):
        install_registry_extension(
            "muslin",
            "codex",
            catalog_path=catalog,
            home=tmp_path / "other-home",
            fetcher=lambda _url, _limit: archive + b"corrupt",
            plugin_installer=plugin,
        )


def test_registry_version_upgrade_migrates_host_and_retains_previous_snapshot(
    tmp_path: Path,
) -> None:
    home = tmp_path / ".fab7"
    plugins = ManagedPluginRecorder()
    installations: list[Path] = []
    statuses: list[str] = []

    for version in ("0.1.0", "0.2.0"):
        package = _make_package(tmp_path / f"package-{version}", version)
        archive = _archive(package, tmp_path / f"muslin-{version}.zip")
        entry = {
            **_identity(version),
            "artifact": {
                "url": (
                    "https://github.com/fab7hq/muslin/releases/download/"
                    f"v{version}/muslin-{version}.zip"
                ),
                "sha256": "sha256:" + hashlib.sha256(archive).hexdigest(),
            },
        }
        catalog = tmp_path / f"catalog-{version}.yaml"
        _write_json(
            catalog,
            {
                "schema": 1,
                "registry": "fab7hq/ext-registry",
                "catalog_version": version,
                "extensions": [entry],
            },
        )

        result = install_registry_extension(
            "muslin",
            "codex",
            catalog_path=catalog,
            home=home,
            fetcher=lambda _url, _limit, data=archive: data,
            plugin_installer=plugins.install,
            plugin_uninstaller=plugins.uninstall,
        )
        assert result["install_id"] == version
        statuses.append(result["status"])
        installations.append(home / "extensions/muslin" / version)

    assert statuses == ["installed", "migrated"]
    assert (home / "bin/muslin").resolve().parent.parent == installations[1]
    assert json.loads((installations[0] / "manifest.json").read_text())["integrations"] == []
    assert json.loads((installations[1] / "manifest.json").read_text())["integrations"] == ["codex"]
    assert plugins.events == [
        ("install", "codex", installations[0] / "hosts/codex"),
        ("uninstall", "codex", installations[0] / "hosts/codex"),
        ("install", "codex", installations[1] / "hosts/codex"),
    ]
    assert extension_doctor(home=home)["snapshot_count"] == 2


def test_host_failure_preserves_previous_selection(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "muslin")
    plugins = ManagedPluginRecorder()
    install_local_extension(
        source,
        "claude",
        home=home,
        plugin_installer=plugins.install,
        plugin_uninstaller=plugins.uninstall,
    )
    selector = home / "bin/muslin"
    previous = os.readlink(selector)
    previous_root = selector.resolve().parent.parent

    def fail_new(host: str, name: str, root: Path) -> dict[str, object]:
        if root != previous_root / "hosts" / host:
            raise Fab7Error("FAB7_HOST_COMMAND_FAILED", "synthetic host failure")
        return plugins.install(host, name, root)

    (source / "build.py").write_text((source / "build.py").read_text() + "# changed\n")
    with pytest.raises(Fab7Error, match="FAB7_HOST_COMMAND_FAILED"):
        install_local_extension(
            source,
            "claude",
            home=home,
            plugin_installer=fail_new,
            plugin_uninstaller=plugins.uninstall,
        )

    assert os.readlink(selector) == previous
    assert len(list((home / "extensions/muslin").iterdir())) == 1
    assert plugins.active["claude"] == previous_root / "hosts/claude"


def test_changed_local_source_migrates_one_host_and_retains_clean_rollback_snapshot(
    tmp_path: Path,
) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "muslin")
    plugins = ManagedPluginRecorder()
    first = install_local_extension(
        source,
        "claude",
        home=home,
        plugin_installer=plugins.install,
        plugin_uninstaller=plugins.uninstall,
    )
    previous = (home / "bin/muslin").resolve().parent.parent

    (source / "build.py").write_text((source / "build.py").read_text() + "# changed\n")
    second = install_local_extension(
        source,
        "claude",
        home=home,
        plugin_installer=plugins.install,
        plugin_uninstaller=plugins.uninstall,
    )

    selected = (home / "bin/muslin").resolve().parent.parent
    assert second["install_id"] != first["install_id"]
    assert selected != previous
    assert json.loads((previous / "manifest.json").read_text())["integrations"] == []
    assert json.loads((selected / "manifest.json").read_text())["integrations"] == ["claude"]
    assert len(list((home / "extensions/muslin").iterdir())) == 2
    assert extension_doctor(home=home)["snapshot_count"] == 2

    (previous / "bin/muslin").write_text("tampered\n")
    diagnosis = extension_doctor(home=home)
    assert diagnosis["ok"] is False
    assert diagnosis["errors"][-1]["code"] == "FAB7_EXTENSION_INVALID"


def test_changed_snapshot_rejects_implicit_migration_of_another_host(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "muslin")
    plugins = ManagedPluginRecorder()
    for host in ("claude", "codex"):
        install_local_extension(
            source,
            host,
            home=home,
            plugin_installer=plugins.install,
            plugin_uninstaller=plugins.uninstall,
        )
    previous = os.readlink(home / "bin/muslin")
    (source / "build.py").write_text((source / "build.py").read_text() + "# changed\n")

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_HOSTS_ACTIVE"):
        install_local_extension(
            source,
            "claude",
            home=home,
            plugin_installer=plugins.install,
            plugin_uninstaller=plugins.uninstall,
        )

    assert os.readlink(home / "bin/muslin") == previous
    assert len(list((home / "extensions/muslin").iterdir())) == 1


def test_doctor_detects_tampering_and_uninstall_is_bounded(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "muslin")
    install_local_extension(source, "claude", home=home, plugin_installer=PluginRecorder())
    selected = (home / "bin/muslin").resolve()
    selected.write_text("tampered\n")

    diagnosis = extension_doctor(home=home)
    assert diagnosis["ok"] is False
    assert diagnosis["errors"][0]["code"] == "FAB7_EXTENSION_INVALID"

    removed: list[tuple[str, str, Path]] = []
    result = uninstall_extension(
        "muslin",
        "claude",
        home=home,
        plugin_uninstaller=lambda host, name, root: removed.append((host, name, root)) or {"ok": True},
    )
    assert result["status"] == "uninstalled"
    assert not (home / "bin/muslin").exists()
    assert not (home / "extensions/muslin").exists()
    assert removed and removed[0][0:2] == ("claude", "muslin")


def test_selector_must_stay_under_its_matching_extension_name(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "muslin")
    install_local_extension(source, "claude", home=home, plugin_installer=PluginRecorder())
    selector = home / "bin/muslin"
    selected = selector.resolve().parent.parent
    other = home / "extensions/other" / selected.name
    shutil.copytree(selected, other)
    selector.unlink()
    selector.symlink_to(Path("../extensions/other") / selected.name / "bin/muslin")

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_INVALID"):
        installed_extensions(home=home)


def test_uninstall_preserves_package_until_last_host_is_removed(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "muslin")
    install_local_extension(source, "claude", home=home, plugin_installer=PluginRecorder())
    install_local_extension(source, "codex", home=home, plugin_installer=PluginRecorder())
    selected = (home / "bin/muslin").resolve().parent.parent
    assert json.loads((selected / "manifest.json").read_text())["integrations"] == [
        "claude",
        "codex",
    ]

    first = uninstall_extension(
        "muslin",
        "claude",
        home=home,
        plugin_uninstaller=lambda *_args: {"ok": True},
    )
    assert first["status"] == "host_uninstalled"
    assert (home / "bin/muslin").is_symlink()
    assert json.loads((selected / "manifest.json").read_text())["integrations"] == ["codex"]

    second = uninstall_extension(
        "muslin",
        "codex",
        home=home,
        plugin_uninstaller=lambda *_args: {"ok": True},
    )
    assert second["status"] == "uninstalled"
    assert not (home / "extensions/muslin").exists()


def test_package_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape", "bad")
    catalog = tmp_path / "catalog.yaml"
    data = archive_path.read_bytes()
    entry = {
        **_identity(),
        "artifact": {
            "url": "https://github.com/fab7hq/muslin/releases/download/v0.1.0/muslin.zip",
            "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        },
    }
    _write_json(catalog, {"schema": 1, "registry": "fab7hq/ext-registry", "catalog_version": "0.1.0", "extensions": [entry]})

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_PACKAGE_INVALID"):
        install_registry_extension(
            "muslin",
            "claude",
            catalog_path=catalog,
            home=tmp_path / ".fab7",
            fetcher=lambda _url, _limit: data,
            plugin_installer=PluginRecorder(),
        )


def test_package_rejects_payload_for_an_undeclared_host(tmp_path: Path) -> None:
    package = _make_package(tmp_path / "package")
    payload = package / "hosts/other/payload.txt"
    payload.parent.mkdir(parents=True)
    payload.write_text("unexpected\n")
    manifest = json.loads((package / "extension.json").read_text())
    manifest["files"].append(
        {"path": "hosts/other/payload.txt", "mode": "0644", "sha256": _digest(payload)}
    )
    manifest["files"] = sorted(manifest["files"], key=lambda row: row["path"])
    _write_json(package / "extension.json", manifest)

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_PACKAGE_INVALID"):
        validate_package(package)


def test_package_rejects_host_marketplace_source_escape(tmp_path: Path) -> None:
    package = _make_package(tmp_path / "package")
    marketplace_path = package / "hosts/codex/.agents/plugins/marketplace.json"
    marketplace = json.loads(marketplace_path.read_text())
    marketplace["plugins"][0]["source"]["path"] = "../../outside"
    _write_json(marketplace_path, marketplace)
    manifest = json.loads((package / "extension.json").read_text())
    for row in manifest["files"]:
        if row["path"] == "hosts/codex/.agents/plugins/marketplace.json":
            row["sha256"] = _digest(marketplace_path)
    _write_json(package / "extension.json", manifest)

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_PACKAGE_INVALID"):
        validate_package(package)


def test_mutations_fail_fast_while_lock_is_held_and_recover_after_release(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    home.mkdir()
    source = _make_source(tmp_path / "muslin")
    descriptor = os.open(home / ".extension.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(Fab7Error, match="FAB7_EXTENSION_BUSY"):
            install_local_extension(
                source,
                "claude",
                home=home,
                plugin_installer=PluginRecorder(),
            )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    result = install_local_extension(
        source,
        "claude",
        home=home,
        plugin_installer=PluginRecorder(),
    )
    assert result["status"] == "installed"


def test_local_build_output_is_bounded(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "muslin")
    builder = source / "build.py"
    builder.write_text("print('x' * 70000)\n" + builder.read_text())

    with pytest.raises(Fab7Error, match="exceeded the output limit"):
        install_local_extension(
            source,
            "claude",
            home=tmp_path / ".fab7",
            plugin_installer=PluginRecorder(),
        )


def test_local_build_time_is_bounded_after_output_streams_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _make_source(tmp_path / "muslin")
    builder = source / "build.py"
    builder.write_text(
        "import os, time\nos.close(1)\nos.close(2)\ntime.sleep(1)\n" + builder.read_text()
    )
    monkeypatch.setattr(extension_package, "MAX_BUILD_SECONDS", 0.05)

    with pytest.raises(Fab7Error, match="exceeded the time limit"):
        install_local_extension(
            source,
            "claude",
            home=tmp_path / ".fab7",
            plugin_installer=PluginRecorder(),
        )
