from __future__ import annotations

import json
from pathlib import Path

import pytest

from fab7.errors import Fab7Error
from fab7.hosts import CommandResult, install_host


class FakeRunner:
    def __init__(
        self,
        host: str,
        root: Path,
        *,
        configured: bool = False,
        installed: bool = False,
        fail_install: bool = False,
    ):
        self.host = host
        self.root = root
        self.configured = configured
        self.installed = installed
        self.fail_install = fail_install
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str]) -> CommandResult:
        self.calls.append(command)
        if command[1:4] == ["plugin", "marketplace", "list"]:
            if self.host == "codex":
                data = {"marketplaces": [{"name": "fab7", "root": str(self.root)}] if self.configured else []}
            else:
                data = [{"name": "fab7", "source": str(self.root)}] if self.configured else []
            return CommandResult(0, json.dumps(data), "")
        if command[1:4] == ["plugin", "marketplace", "add"]:
            self.configured = True
            return CommandResult(0, "{}", "")
        if command[1:3] == ["plugin", "validate"]:
            return CommandResult(0, "valid", "")
        if command[1:3] == ["plugin", "list"]:
            if self.host == "codex":
                data = {"installed": [{"pluginId": "fab7@fab7", "installed": True}] if self.installed else []}
            else:
                data = [{"id": "fab7@fab7", "scope": "user"}] if self.installed else []
            return CommandResult(0, json.dumps(data), "")
        if command[1:3] in (["plugin", "add"], ["plugin", "install"]):
            if self.fail_install:
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
    root = fab7_home / "runtime/0.1.0/hosts" / host
    runner = FakeRunner(host, root)

    first = install_host(host, host_root=root, runner=runner)
    assert first["status"] == "installed"
    assert first["activation"]

    runner.calls.clear()
    second = install_host(host, host_root=root, runner=runner)
    assert second["status"] == "already_installed"
    assert not any(call[1:3] in (["plugin", "add"], ["plugin", "install"]) for call in runner.calls)


def test_host_install_rejects_marketplace_name_collision(tmp_path: Path, fab7_home: Path) -> None:
    root = fab7_home / "runtime/0.1.0/hosts/codex"
    runner = FakeRunner("codex", tmp_path / "other", configured=True)
    with pytest.raises(Fab7Error, match="FAB7_HOST_MARKETPLACE_CONFLICT"):
        install_host("codex", host_root=root, runner=runner)


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_host_install_failure_removes_new_marketplace(host: str, fab7_home: Path) -> None:
    root = fab7_home / "runtime/0.1.0/hosts" / host
    runner = FakeRunner(host, root, fail_install=True)

    with pytest.raises(Fab7Error, match="FAB7_HOST_COMMAND_FAILED"):
        install_host(host, host_root=root, runner=runner)
    assert runner.configured is False
    assert any(call[1:4] == ["plugin", "marketplace", "remove"] for call in runner.calls)
