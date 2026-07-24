from __future__ import annotations

import hashlib
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import fab7.extension.package as package_module
import fab7.extension.lifecycle as lifecycle_module
from fab7.native_build import build_native_executable as real_native_builder
from fab7.errors import Fab7Error
from fab7.extension.lifecycle import (
    extension_doctor,
    install_local_extension,
    install_registry_extension,
    installed_extensions,
    uninstall_extension,
)
from fab7.extension.package import (
    build_extension_archive,
    build_local_package,
    extract_package_archive,
    validate_package,
)


def _identity(version: str = "0.1.0") -> dict[str, object]:
    return {
        "name": "muslin",
        "publisher": "fab7hq",
        "version": version,
        "fab7_api": 1,
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
    executable_sha256 = _digest(executable)
    build = {
        "target": "macos-arm64-cpython-3.14.6",
        "source_sha256": "sha256:" + "1" * 64,
        "toolchain_sha256": "sha256:" + "2" * 64,
        "dependency_lock_sha256": "sha256:" + "3" * 64,
        "dependency_requirements_sha256": "sha256:" + "4" * 64,
        "dependency_root_sha256": "sha256:" + "5" * 64,
        "executable_sha256": executable_sha256,
    }
    _write_json(
        root / "extension.json",
        {"schema": 1, **identity, "build": build, "files": files},
    )
    return root


def _make_source(root: Path, version: str = "0.1.0") -> Path:
    entrypoint = root / "src/extension.py"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text(
        "#!/usr/bin/env python3\n"
        "from muslin.cli import main\n"
        "import sys\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    if sys.argv[1:] == ['--help']:\n"
        "        print('usage: muslin start --json')\n"
        "        raise SystemExit(0)\n"
        "    raise SystemExit(main())\n"
    )
    package = root / "src/muslin"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "cli.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "\n"
        "\n"
        "def main() -> int:\n"
        "    print(json.dumps({'extension': 'muslin'}, sort_keys=True))\n"
        "    return 0\n"
    )
    skill = root / "skills/start/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        "name: start\n"
        "description: Start Muslin through {{invocation}}.\n"
        "disable-model-invocation: true\n"
        "---\n\n"
        "Run `muslin start --json` for {{host}}.\n"
    )
    test = root / "tests/test_extension.py"
    test.parent.mkdir(parents=True)
    test.write_text(
        "def test_extension_source() -> None:\n"
        "    assert True\n"
    )
    _write_json(
        root / "fab7-extension.json",
        {
            "schema": 1,
            "name": "muslin",
            "publisher": "fab7hq",
            "version": version,
        },
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "muslin"\n'
        f'version = "{version}"\n'
        'requires-python = "==3.14.*"\n'
        "dependencies = []\n"
    )
    (root / "uv.lock").write_text(
        "version = 1\n"
        "revision = 3\n"
        'requires-python = "==3.14.*"\n'
        "\n"
        "[[package]]\n"
        'name = "muslin"\n'
        f'version = "{version}"\n'
        'source = { virtual = "." }\n'
    )
    return root


@pytest.fixture(autouse=True)
def _fast_native_unit_builder(monkeypatch: pytest.MonkeyPatch):
    empty_digest = "sha256:" + hashlib.sha256(b"").hexdigest()

    def build(
        source_root: Path,
        entrypoint: Path,
        output: Path,
        **_kwargs,
    ) -> dict[str, object]:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("#!/bin/sh\nprintf 'muslin\\n'\n")
        output.chmod(0o755)
        return {
            "target": "macos-arm64-cpython-3.14.6",
            "toolchain": {"sha256": "sha256:" + "2" * 64},
            "dependencies": {
                "lock_sha256": _digest(source_root / "uv.lock"),
                "requirements_sha256": empty_digest,
                "root_sha256": empty_digest,
                "hashes": [],
            },
            "executable_sha256": _digest(output),
        }

    monkeypatch.setattr(package_module, "build_native_executable", build)
    monkeypatch.setattr(
        lifecycle_module,
        "inspect_toolchain",
        lambda _home: {
            "target": "macos-arm64-cpython-3.14.6",
            "sha256": "sha256:" + "2" * 64,
        },
    )


def test_builtin_adapter_build_is_deterministic_and_installable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(package_module, "build_native_executable", real_native_builder)
    source = _make_source(tmp_path / "source")
    (source / "pyproject.toml").write_text(
        "[project]\n"
        'name = "muslin"\n'
        'version = "0.1.0"\n'
        'requires-python = "==3.14.*"\n'
        'dependencies = ["pyyaml==6.0.3"]\n'
    )
    (source / "src/helper.py").write_text(
        "import yaml\n"
        "\n"
        "NAME = yaml.safe_load('name: muslin')['name']\n"
    )
    entrypoint = source / "src/extension.py"
    entrypoint.write_text("from helper import NAME\n" + entrypoint.read_text())
    locked = subprocess.run(
        [
            "uv",
            "lock",
            "--project",
            str(source),
            "--python",
            sys.executable,
            "--managed-python",
            "--no-python-downloads",
            "--no-config",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert locked.returncode == 0, locked.stderr
    home = tmp_path / ".fab7"
    with tempfile.TemporaryDirectory(prefix="fab7-build-test-") as directory:
        package_root, source_sha256, package = build_local_package(
            source,
            Path(directory),
            home=home,
        )
        assert source_sha256.startswith("sha256:")
        assert package["name"] == "muslin"
        assert (package_root / "bin/muslin").stat().st_mode & 0o111
        smoke = subprocess.run(
            [str(package_root / "bin/muslin"), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert smoke.returncode == 0, smoke.stderr
        assert not list(package_root.rglob(".venv"))
        assert not list(package_root.rglob("yaml"))
        assert (
            package_root / "hosts/claude/plugins/muslin/skills/start/SKILL.md"
        ).is_file()
        assert (
            package_root / "hosts/codex/plugins/muslin/skills/start/SKILL.md"
        ).is_file()

    first = build_extension_archive(
        source,
        tmp_path / "first.zip",
        hosts=("claude",),
        home=home,
    )
    second = build_extension_archive(
        source,
        tmp_path / "second.zip",
        hosts=("claude",),
        home=home,
    )
    assert (tmp_path / "first.zip").read_bytes() == (tmp_path / "second.zip").read_bytes()
    assert first["package_sha256"] == second["package_sha256"]
    extracted = extract_package_archive(
        (tmp_path / "first.zip").read_bytes(), tmp_path / "extracted"
    )
    built_package = validate_package(extracted)
    assert built_package["name"] == "muslin"
    assert built_package["hosts"] == ["claude"]
    assert not (extracted / "hosts/codex").exists()

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_TARGET_INVALID"):
        build_extension_archive(source, tmp_path / "missing-target.zip", hosts=(), home=home)
    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_TARGET_INVALID"):
        build_extension_archive(
            source,
            tmp_path / "duplicate-target.zip",
            hosts=("claude", "claude"),
            home=home,
        )
    with pytest.raises(Fab7Error, match="FAB7_HOST_UNSUPPORTED"):
        build_extension_archive(
            source,
            tmp_path / "unsupported-target.zip",
            hosts=("cursor",),
            home=home,
        )

    plugin = PluginRecorder()
    installed = install_local_extension(
        source,
        "claude",
        home=home,
        plugin_installer=plugin,
    )
    assert installed["status"] == "installed"
    assert installed["origin"] == "local"


def _make_dependency_source(
    root: Path,
    *,
    name: str,
    dependency: str,
) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "src/extension.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "import packaging\n"
        "import sys\n"
        "\n"
        "if sys.argv[1:] == ['--help']:\n"
        "    print(packaging.__version__)\n"
        "    raise SystemExit(0)\n"
        "print(json.dumps({'extension': '" + name + "', 'dependency': packaging.__version__}, sort_keys=True))\n"
    )
    skill = root / "skills/start/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        "name: start\n"
        f"description: Start {name} through {{{{invocation}}}}.\n"
        "disable-model-invocation: true\n"
        "---\n\n"
        f"Run `{name}` for {{{{host}}}}.\n"
    )
    test = root / "tests/test_extension.py"
    test.parent.mkdir(parents=True)
    test.write_text("def test_source() -> None:\n    assert True\n")
    _write_json(
        root / "fab7-extension.json",
        {
            "schema": 1,
            "name": name,
            "publisher": "fab7hq",
            "version": "0.1.0",
        },
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        'requires-python = "==3.14.*"\n'
        f'dependencies = ["{dependency}"]\n'
    )
    locked = subprocess.run(
        [
            "uv",
            "lock",
            "--project",
            str(root),
            "--python",
            sys.executable,
            "--managed-python",
            "--no-python-downloads",
            "--no-config",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert locked.returncode == 0, locked.stderr
    return root


def test_conflicting_extension_dependencies_build_concurrently_in_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(package_module, "build_native_executable", real_native_builder)
    first_source = _make_dependency_source(
        tmp_path / "alpha",
        name="alpha",
        dependency="packaging==24.2",
    )
    second_source = _make_dependency_source(
        tmp_path / "beta",
        name="beta",
        dependency="packaging==25.0",
    )
    home = tmp_path / ".fab7"

    def build(source: Path, output: Path) -> dict[str, object]:
        return build_extension_archive(
            source,
            output,
            hosts=("codex",),
            home=home,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(build, first_source, tmp_path / "alpha.zip")
        second_future = executor.submit(build, second_source, tmp_path / "beta.zip")
        first = first_future.result()
        second = second_future.result()

    assert first["package_sha256"] != second["package_sha256"]
    assert (home / "cache/uv").is_dir()
    assert (home / "toolchains/python").is_dir()
    assert list((home / "builds").iterdir()) == []
    for archive, name, expected in (
        (tmp_path / "alpha.zip", "alpha", "24.2"),
        (tmp_path / "beta.zip", "beta", "25.0"),
    ):
        extracted = extract_package_archive(
            archive.read_bytes(),
            tmp_path / f"extract-{expected}",
        )
        process = subprocess.run(
            [str(extracted / "bin" / name), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert process.returncode == 0, process.stderr
        assert process.stdout.strip() == expected
        assert not list(extracted.rglob(".venv"))
        assert not list(extracted.rglob("site-packages"))


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
    assert set(receipt) == {
        "schema",
        "name",
        "publisher",
        "version",
        "fab7_api",
        "hosts",
        "install_id",
        "origin",
        "integrations",
        "package_sha256",
        "build",
        "files",
    }
    assert receipt["origin"]["type"] == "local"
    assert "source" not in receipt["origin"]
    assert plugin.calls == [("claude", "muslin", installation / "hosts/claude")]
    assert installed_extensions(home=home)[0]["name"] == "muslin"
    assert extension_doctor(home=home)["ok"] is True


def test_registry_install_verifies_source_and_uses_same_local_builder(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    source = _make_source(tmp_path / "source")
    archive = _archive(source, tmp_path / "muslin-source.zip")
    digest = "sha256:" + hashlib.sha256(archive).hexdigest()
    local = build_extension_archive(
        source,
        tmp_path / "local-package.zip",
        hosts=("claude", "codex"),
        home=home,
    )
    entry = {
        **_identity(),
        "source": {
            "url": "https://github.com/fab7hq/muslin/releases/download/v0.1.0/muslin-0.1.0.source.zip",
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
    assert result["install_id"].startswith("0.1.0-")
    receipt = json.loads(
        (home / "extensions/muslin" / result["install_id"] / "manifest.json").read_text()
    )
    assert receipt["origin"] == {
        "catalog_version": "0.1.0",
        "source_bundle_sha256": digest,
        "source_sha256": receipt["build"]["source_sha256"],
        "source_url": entry["source"]["url"],
        "type": "registry",
    }
    assert receipt["package_sha256"] == local["package_sha256"]

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
        source = _make_source(tmp_path / f"source-{version}", version)
        archive = _archive(source, tmp_path / f"muslin-{version}.source.zip")
        entry = {
            **_identity(version),
            "source": {
                "url": (
                    "https://github.com/fab7hq/muslin/releases/download/"
                    f"v{version}/muslin-{version}.source.zip"
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
        assert result["install_id"].startswith(version + "-")
        statuses.append(result["status"])
        installations.append(home / "extensions/muslin" / result["install_id"])

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

    implementation = source / "src/muslin/cli.py"
    implementation.write_text(implementation.read_text() + "# changed\n")
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

    implementation = source / "src/muslin/cli.py"
    implementation.write_text(implementation.read_text() + "# changed\n")
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
    implementation = source / "src/muslin/cli.py"
    implementation.write_text(implementation.read_text() + "# changed\n")

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


def test_source_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape", "bad")
    catalog = tmp_path / "catalog.yaml"
    data = archive_path.read_bytes()
    entry = {
        **_identity(),
        "source": {
            "url": "https://github.com/fab7hq/muslin/releases/download/v0.1.0/muslin.source.zip",
            "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        },
    }
    _write_json(catalog, {"schema": 1, "registry": "fab7hq/ext-registry", "catalog_version": "0.1.0", "extensions": [entry]})

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_SOURCE_INVALID"):
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


def test_schema_one_rejects_manual_build_fields(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "muslin")
    manifest = json.loads((source / "fab7-extension.json").read_text())
    manifest["build"] = {
        "entrypoint": "src/extension.py",
        "files": ["fab7-extension.json", "src/extension.py"],
    }
    _write_json(source / "fab7-extension.json", manifest)

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_SOURCE_INVALID"):
        install_local_extension(
            source,
            "claude",
            home=tmp_path / ".fab7",
            plugin_installer=PluginRecorder(),
        )


def test_source_rejects_every_other_schema(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "muslin")
    manifest = json.loads((source / "fab7-extension.json").read_text())
    manifest["schema"] = 2
    _write_json(source / "fab7-extension.json", manifest)

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_SOURCE_INVALID"):
        build_local_package(source, tmp_path / "schema-build")


def test_automatic_discovery_hashes_tests_without_shipping_them(
    tmp_path: Path,
) -> None:
    source = _make_source(tmp_path / "muslin")
    with tempfile.TemporaryDirectory(prefix="fab7-source-first-") as first_directory:
        first_root, first_digest, _first_package = build_local_package(
            source,
            Path(first_directory),
        )
        first_executable = (first_root / "bin/muslin").read_bytes()

    test = source / "tests/test_extension.py"
    test.write_text(test.read_text() + "# proof changed\n")
    with tempfile.TemporaryDirectory(prefix="fab7-source-second-") as second_directory:
        second_root, second_digest, _second_package = build_local_package(
            source,
            Path(second_directory),
        )
        second_executable = (second_root / "bin/muslin").read_bytes()

    assert second_digest != first_digest
    assert second_executable == first_executable
    assert b"proof changed" not in second_executable


def test_automatic_discovery_rejects_symlinks_and_source_overflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _make_source(tmp_path / "muslin")
    link = source / "src/muslin/escape.py"
    link.symlink_to(tmp_path / "outside.py")

    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_SOURCE_INVALID"):
        build_local_package(source, tmp_path / "symlink-build")

    link.unlink()
    monkeypatch.setattr(package_module, "MAX_SOURCE_FILES", 3)
    with pytest.raises(Fab7Error, match="FAB7_EXTENSION_SOURCE_INVALID"):
        build_local_package(source, tmp_path / "overflow-build")


def test_automatic_discovery_ignores_generated_python_caches(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "muslin")
    with tempfile.TemporaryDirectory(prefix="fab7-cache-first-") as first_directory:
        first_root, first_digest, _first_package = build_local_package(
            source,
            Path(first_directory),
        )
        first_executable = (first_root / "bin/muslin").read_bytes()

    cache = source / "src/muslin/__pycache__"
    cache.mkdir()
    (cache / "cli.cpython-312.pyc").write_bytes(b"generated")
    (source / "tests/test_extension.pyc").write_bytes(b"generated")
    with tempfile.TemporaryDirectory(prefix="fab7-cache-second-") as second_directory:
        second_root, second_digest, _second_package = build_local_package(
            source,
            Path(second_directory),
        )
        second_executable = (second_root / "bin/muslin").read_bytes()

    assert second_digest == first_digest
    assert second_executable == first_executable
