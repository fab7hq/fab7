from __future__ import annotations

import json
import sys
from pathlib import Path

from fab7.cli import main


def test_cli_complete_path(repo: Path, capsys) -> None:
    assert main(["init", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]

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


def test_plain_verify_replays_command_output(repo: Path, capsys) -> None:
    main(["init"])
    capsys.readouterr()
    main(["claim", "--work-item", "work-1", "--summary", "Done", "--json"])
    claim = json.loads(capsys.readouterr().out)["record"]

    assert main([
        "verify", "--work-item", "work-1", "--claim", claim["id"], "--",
        sys.executable, "-c", "print('visible')",
    ]) == 0
    assert "visible" in capsys.readouterr().out
