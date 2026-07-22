from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from fab7 import __version__
from fab7.errors import Fab7Error
from fab7.hosts import CommandResult, install_host, install_plugin, uninstall_plugin


class FakeRunner:
    def __init__(
        self,
        host: str,
        root: Path,
        *,
        configured: bool = False,
        installed: bool = False,
        fail_install: bool = False,
        fail_install_roots: set[Path] | None = None,
        name: str = "fab7",
    ):
        self.host = host
        self.root = root
        self.configured = configured
        self.installed = installed
        self.fail_install = fail_install
        self.fail_install_roots = fail_install_roots or set()
        self.name = name
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str]) -> CommandResult:
        self.calls.append(command)
        if command[1:4] == ["plugin", "marketplace", "list"]:
            if self.host == "codex":
                data = {"marketplaces": [{"name": self.name, "root": str(self.root)}] if self.configured else []}
            else:
                data = [{"name": self.name, "source": str(self.root)}] if self.configured else []
            return CommandResult(0, json.dumps(data), "")
        if command[1:4] == ["plugin", "marketplace", "add"]:
            self.root = Path(command[4]).resolve()
            self.configured = True
            return CommandResult(0, "{}", "")
        if command[1:3] == ["plugin", "validate"]:
            return CommandResult(0, "valid", "")
        if command[1:3] == ["plugin", "list"]:
            if self.host == "codex":
                data = {"installed": [{"pluginId": f"{self.name}@{self.name}", "installed": True}] if self.installed else []}
            else:
                data = [{"id": f"{self.name}@{self.name}", "scope": "user"}] if self.installed else []
            return CommandResult(0, json.dumps(data), "")
        if command[1:3] in (["plugin", "add"], ["plugin", "install"]):
            if self.fail_install or self.root in self.fail_install_roots:
                return CommandResult(1, "", "install failed")
            self.installed = True
            return CommandResult(0, "{}", "")
        if command[1:3] in (["plugin", "remove"], ["plugin", "uninstall"]):
            self.installed = False
            return CommandResult(0, "{}", "")
        if command[1:4] == ["plugin", "marketplace", "remove"]:
            self.configured = False
            return CommandResult(0, "{}", "")
        raise AssertionError(command)


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_host_install_is_literal_and_idempotent(host: str, tmp_path: Path, fab7_home: Path) -> None:
    root = fab7_home / "runtime" / __version__ / "hosts" / host
    runner = FakeRunner(host, root)

    first = install_host(host, host_root=root, runner=runner)
    assert first["status"] == "installed"
    assert first["activation"]

    runner.calls.clear()
    second = install_host(host, host_root=root, runner=runner)
    assert second["status"] == "already_installed"
    assert not any(call[1:3] in (["plugin", "add"], ["plugin", "install"]) for call in runner.calls)


def test_host_install_rejects_marketplace_name_collision(tmp_path: Path, fab7_home: Path) -> None:
    root = fab7_home / "runtime" / __version__ / "hosts/codex"
    runner = FakeRunner("codex", tmp_path / "other", configured=True)
    with pytest.raises(Fab7Error, match="FAB7_HOST_MARKETPLACE_CONFLICT"):
        install_host("codex", host_root=root, runner=runner)


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_host_install_migrates_previous_managed_release(host: str, fab7_home: Path) -> None:
    current = fab7_home / "runtime" / __version__ / "hosts" / host
    previous = fab7_home / "runtime" / "0.1.0" / "hosts" / host
    shutil.copytree(current, previous)
    runner = FakeRunner(host, previous, configured=True, installed=True)

    result = install_host(host, host_root=current, runner=runner)

    assert result["status"] == "migrated"
    assert runner.root == current.resolve()
    assert runner.configured is True
    assert runner.installed is True
    assert any(call[1:3] in (["plugin", "remove"], ["plugin", "uninstall"]) for call in runner.calls)
    assert any(call[1:4] == ["plugin", "marketplace", "remove"] for call in runner.calls)


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_extension_plugin_migrates_previous_managed_snapshot(
    host: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / ".fab7"
    previous = home / "extensions/muslin/0.1.0/hosts" / host
    current = home / "extensions/muslin/0.2.0/hosts" / host
    _make_host_root(previous, host, "muslin")
    _make_host_root(current, host, "muslin")
    monkeypatch.setenv("FAB7_HOME", str(home))
    runner = FakeRunner(host, previous, configured=True, installed=True, name="muslin")

    result = install_plugin(host, "muslin", host_root=current, runner=runner)

    assert result["status"] == "migrated"
    assert runner.root == current.resolve()
    assert runner.configured is True
    assert runner.installed is True


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_managed_marketplace_migration_rolls_back_on_new_plugin_failure(
    host: str, fab7_home: Path
) -> None:
    current = (fab7_home / "runtime" / __version__ / "hosts" / host).resolve()
    previous = fab7_home / "runtime" / "0.1.0" / "hosts" / host
    shutil.copytree(current, previous)
    previous = previous.resolve()
    runner = FakeRunner(
        host,
        previous,
        configured=True,
        installed=True,
        fail_install_roots={current},
    )

    with pytest.raises(Fab7Error, match="FAB7_HOST_COMMAND_FAILED"):
        install_host(host, host_root=current, runner=runner)

    assert runner.root == previous
    assert runner.configured is True
    assert runner.installed is True


def test_host_install_rejects_invalid_previous_managed_release(fab7_home: Path) -> None:
    current = fab7_home / "runtime" / __version__ / "hosts/codex"
    previous = fab7_home / "runtime/0.1.0/hosts/codex"
    previous.mkdir(parents=True)
    runner = FakeRunner("codex", previous, configured=True, installed=True)

    with pytest.raises(Fab7Error, match="FAB7_HOST_MARKETPLACE_CONFLICT"):
        install_host("codex", host_root=current, runner=runner)

    assert runner.root == previous.resolve()
    assert runner.configured is True
    assert runner.installed is True


def test_managed_marketplace_reports_incomplete_rollback(fab7_home: Path) -> None:
    current = (fab7_home / "runtime" / __version__ / "hosts/codex").resolve()
    previous = fab7_home / "runtime/0.1.0/hosts/codex"
    shutil.copytree(current, previous)
    previous = previous.resolve()
    runner = FakeRunner(
        "codex",
        previous,
        configured=True,
        installed=True,
        fail_install_roots={current, previous},
    )

    with pytest.raises(Fab7Error, match="FAB7_HOST_ROLLBACK_FAILED") as caught:
        install_host("codex", host_root=current, runner=runner)

    assert caught.value.context == {
        "host": "codex",
        "failures": ["FAB7_HOST_COMMAND_FAILED"],
    }
    assert runner.root == previous
    assert runner.configured is True
    assert runner.installed is False


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_host_install_failure_removes_new_marketplace(host: str, fab7_home: Path) -> None:
    root = fab7_home / "runtime" / __version__ / "hosts" / host
    runner = FakeRunner(host, root, fail_install=True)

    with pytest.raises(Fab7Error, match="FAB7_HOST_COMMAND_FAILED"):
        install_host(host, host_root=root, runner=runner)
    assert runner.configured is False
    assert any(call[1:4] == ["plugin", "marketplace", "remove"] for call in runner.calls)


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_extension_plugin_install_and_uninstall_use_own_marketplace(
    host: str, tmp_path: Path
) -> None:
    root = tmp_path / host
    if host == "claude":
        _write_json(
            root / ".claude-plugin/marketplace.json",
            {"name": "muslin", "plugins": [{"name": "muslin", "source": "./plugins/muslin"}]},
        )
        _write_json(root / "plugins/muslin/.claude-plugin/plugin.json", {"name": "muslin"})
    else:
        _write_json(
            root / ".agents/plugins/marketplace.json",
            {
                "name": "muslin",
                "plugins": [
                    {
                        "name": "muslin",
                        "source": {"source": "local", "path": "./plugins/muslin"},
                    }
                ],
            },
        )
        _write_json(root / "plugins/muslin/.codex-plugin/plugin.json", {"name": "muslin"})
    runner = FakeRunner(host, root, name="muslin")

    installed = install_plugin(host, "muslin", host_root=root, runner=runner)
    assert installed["plugin"] == "muslin@muslin"
    assert runner.configured and runner.installed

    removed = uninstall_plugin(host, "muslin", host_root=root, runner=runner)
    assert removed["status"] == "uninstalled"
    assert not runner.configured and not runner.installed


def _make_host_root(root: Path, host: str, name: str) -> None:
    if host == "claude":
        _write_json(
            root / ".claude-plugin/marketplace.json",
            {"name": name, "plugins": [{"name": name, "source": f"./plugins/{name}"}]},
        )
        _write_json(root / f"plugins/{name}/.claude-plugin/plugin.json", {"name": name})
    else:
        _write_json(
            root / ".agents/plugins/marketplace.json",
            {
                "name": name,
                "plugins": [
                    {
                        "name": name,
                        "source": {"source": "local", "path": f"./plugins/{name}"},
                    }
                ],
            },
        )
        _write_json(root / f"plugins/{name}/.codex-plugin/plugin.json", {"name": name})


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_extension_plugin_rejects_marketplace_source_escape(host: str, tmp_path: Path) -> None:
    root = tmp_path / host
    if host == "claude":
        marketplace = {"name": "muslin", "plugins": [{"name": "muslin", "source": "../../outside"}]}
        manifest = root / "plugins/muslin/.claude-plugin/plugin.json"
        marketplace_path = root / ".claude-plugin/marketplace.json"
    else:
        marketplace = {
            "name": "muslin",
            "plugins": [
                {"name": "muslin", "source": {"source": "local", "path": "../../outside"}}
            ],
        }
        manifest = root / "plugins/muslin/.codex-plugin/plugin.json"
        marketplace_path = root / ".agents/plugins/marketplace.json"
    _write_json(marketplace_path, marketplace)
    _write_json(manifest, {"name": "muslin"})

    with pytest.raises(Fab7Error, match="FAB7_HOST_ARTIFACT_INVALID"):
        install_plugin(host, "muslin", host_root=root, runner=FakeRunner(host, root, name="muslin"))


def test_uninstall_does_not_remove_plugin_owned_by_another_marketplace(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    runner = FakeRunner(
        "codex",
        tmp_path / "other",
        configured=True,
        installed=True,
        name="muslin",
    )

    with pytest.raises(Fab7Error, match="FAB7_HOST_MARKETPLACE_CONFLICT"):
        uninstall_plugin("codex", "muslin", host_root=expected, runner=runner)

    assert runner.installed is True
    assert not any(call[1:3] == ["plugin", "remove"] for call in runner.calls)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")
