from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import git

import fab7.cli as cli
from fab7.cli import main


def test_cli_complete_path(repo: Path, fab7_home: Path, capsys) -> None:
    assert main(["init", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    git(repo, "add", ".fab7/project.json", ".fab7/.gitignore")
    git(repo, "commit", "-qm", "initialize fab7")

    assert main(["claim", "--work-item", "work-1", "--summary", "Done", "--json"]) == 0
    claim = json.loads(capsys.readouterr().out)["record"]

    assert main([
        "verify", "--work-item", "work-1", "--claim", claim["id"], "--json", "--",
        sys.executable, "-c", "print('verified')",
    ]) == 0
    evidence = json.loads(capsys.readouterr().out)["record"]
    assert evidence["exit_code"] == 0

    assert main(["ci-check", "--work-item", "work-1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert main(["audit", "--work-item", "work-1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["record_count"] == 2
    assert main(["doctor", "--json"]) == 0


def test_cli_returns_failure_for_missing_setup(repo: Path, capsys) -> None:
    assert main(["ci-check", "--work-item", "work-1", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["errors"][0]["code"] == "FAB7_NOT_INITIALIZED"


def test_plain_verify_replays_command_output(repo: Path, fab7_home: Path, capsys) -> None:
    main(["init"])
    capsys.readouterr()
    git(repo, "add", ".fab7/project.json", ".fab7/.gitignore")
    git(repo, "commit", "-qm", "initialize fab7")
    main(["claim", "--work-item", "work-1", "--summary", "Done", "--json"])
    claim = json.loads(capsys.readouterr().out)["record"]

    assert main([
        "verify", "--work-item", "work-1", "--claim", claim["id"], "--",
        sys.executable, "-c", "print('visible')",
    ]) == 0
    assert "visible" in capsys.readouterr().out


def test_extension_cli_routes_refresh_local_install_doctor_and_uninstall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        cli,
        "refresh_catalog",
        lambda: calls.append(("refresh",)) or {"ok": True, "status": "refreshed"},
    )
    monkeypatch.setattr(
        cli,
        "catalog_listing",
        lambda path, include_installed: {
            "ok": True,
            "catalog": "/catalog.yaml",
            "catalog_version": "0.1.0",
            "registry": "fab7hq/ext-registry",
            "count": 0,
            "extensions": [],
            "installed": [],
        },
    )
    monkeypatch.setattr(
        cli,
        "install_local_extension",
        lambda path, host: calls.append(("install", path, host))
        or {
            "ok": True,
            "name": "muslin",
            "status": "installed",
            "activation": "restart",
        },
    )
    monkeypatch.setattr(
        cli,
        "extension_doctor",
        lambda: {"ok": True, "errors": [], "installed": []},
    )
    monkeypatch.setattr(
        cli,
        "uninstall_extension",
        lambda name, host: calls.append(("uninstall", name, host))
        or {"ok": True, "name": name, "status": "uninstalled"},
    )

    assert main(["ext", "list", "--refresh", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert main(["ext", "install", "--local", str(tmp_path), "--host", "claude", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "muslin"
    assert main(["ext", "doctor", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert main(["ext", "uninstall", "muslin", "--host", "claude", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "uninstalled"
    assert calls == [
        ("refresh",),
        ("install", tmp_path, "claude"),
        ("uninstall", "muslin", "claude"),
    ]
