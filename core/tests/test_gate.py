from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import fab7.toolchain as toolchain_module
from fab7.gate import check, doctor
from fab7.install import selected_release
from fab7.ledger import append, create_claim, init, record_path, verify

from conftest import git


def _claim(repo: Path) -> dict[str, object]:
    init(repo)
    claim = create_claim(repo, "work-1", "Implementation complete")
    append(repo, claim)
    return claim


def test_gate_requires_a_claim_and_fresh_passing_evidence(repo: Path) -> None:
    init(repo)
    assert [error.code for error in check(repo, "work-1").errors] == ["FAB7_CLAIM_MISSING"]

    claim = _claim(repo)
    assert [error.code for error in check(repo, "work-1").errors] == ["FAB7_EVIDENCE_MISSING"]

    verify(repo, "work-1", str(claim["id"]), [sys.executable, "-c", "print('ok')"])
    assert check(repo, "work-1").ok


def test_failed_evidence_does_not_back_a_claim(repo: Path) -> None:
    claim = _claim(repo)
    verify(repo, "work-1", str(claim["id"]), [sys.executable, "-c", "raise SystemExit(1)"])
    assert [error.code for error in check(repo, "work-1").errors] == ["FAB7_EVIDENCE_MISSING"]


def test_code_change_after_verification_makes_evidence_stale(repo: Path) -> None:
    claim = _claim(repo)
    verify(repo, "work-1", str(claim["id"]), [sys.executable, "-c", "pass"])
    git(repo, "add", ".fab7")
    git(repo, "commit", "-qm", "record proof")
    (repo / "app.py").write_text("VALUE = 2\n")
    git(repo, "add", "app.py")
    git(repo, "commit", "-qm", "change implementation")

    assert [error.code for error in check(repo, "work-1").errors] == ["FAB7_EVIDENCE_MISSING"]


def test_ledger_rewrite_is_rejected(repo: Path) -> None:
    claim = _claim(repo)
    verify(repo, "work-1", str(claim["id"]), [sys.executable, "-c", "pass"])
    git(repo, "add", ".fab7")
    git(repo, "commit", "-qm", "record proof")

    path = record_path(repo, "work-1")
    rows = path.read_text().splitlines()
    record = json.loads(rows[0])
    record["summary"] = "rewritten"
    rows[0] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(rows) + "\n")

    errors = check(repo, "work-1", base="HEAD").errors
    assert "FAB7_LEDGER_REWRITE" in [error.code for error in errors]


def test_doctor_checks_toolchain_workspace_and_ledger(
    repo: Path,
    fab7_home: Path,
) -> None:
    assert not doctor(repo)["ok"]
    init(repo)
    result = doctor(repo)
    assert result["ok"]
    assert [check["name"] for check in result["checks"]] == [
        "git",
        "toolchain",
        "workspace",
        "ledger",
    ]


def test_doctor_accepts_a_different_valid_uv_version(
    repo: Path,
    fab7_home: Path,
    monkeypatch,
) -> None:
    init(repo)
    _release, manifest = selected_release(fab7_home)
    current = copy.deepcopy(manifest["toolchain"])
    current["uv"]["version"] = "99.0.0"
    current["uv"]["sha256"] = "sha256:" + hashlib.sha256(b"different uv").hexdigest()
    encoded = json.dumps(
        {key: value for key, value in current.items() if key != "sha256"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    current["sha256"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    monkeypatch.setattr(toolchain_module, "inspect_toolchain", lambda _home: current)

    result = doctor(repo)

    assert result["ok"]
    toolchain = next(check for check in result["checks"] if check["name"] == "toolchain")
    assert "uv 99.0.0; tested with uv 0.11.29" in toolchain["detail"]
