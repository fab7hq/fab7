from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from fab7.errors import Fab7Error
from fab7.ledger import append, create_claim, init, read, read_all, verify


def test_append_preserves_order_and_rejects_unknown_fields(repo: Path) -> None:
    init(repo)
    first = create_claim(repo, "work-1", "First")
    second = create_claim(repo, "work-1", "Second")
    append(repo, first)
    append(repo, second)
    assert [record["id"] for record in read(repo, "work-1")] == [first["id"], second["id"]]

    invalid = {**second, "extra": True}
    with pytest.raises(Fab7Error, match="FAB7_LEDGER_INVALID"):
        append(repo, invalid)


def test_invalid_json_and_unknown_claim_fail_closed(repo: Path) -> None:
    directory = init(repo)
    (directory / "broken.jsonl").write_text("{not json}\n")
    with pytest.raises(Fab7Error, match="FAB7_LEDGER_INVALID"):
        read_all(repo)

    (directory / "broken.jsonl").unlink()
    evidence = {
        "actor": "human:test@example.com",
        "claim": "rec_" + "0" * 32,
        "command_digest": "sha256:" + "2" * 64,
        "created_at": "2026-07-19T00:00:00Z",
        "exit_code": 0,
        "git_ref": "a" * 40,
        "id": "rec_" + "1" * 32,
        "output_digest": "sha256:" + "0" * 64,
        "summary": "true",
        "type": "evidence",
        "v": 1,
        "work_item": "work-1",
    }
    (directory / "work-1.jsonl").write_text(json.dumps(evidence) + "\n")
    with pytest.raises(Fab7Error, match="unknown claim"):
        read(repo, "work-1")


def test_verify_runs_the_command_and_records_both_outcomes(repo: Path) -> None:
    init(repo)
    claim = create_claim(repo, "work-1", "Done")
    append(repo, claim)

    passed = verify(repo, "work-1", claim["id"], [sys.executable, "-c", "print('proved')"])
    failed = verify(repo, "work-1", claim["id"], [sys.executable, "-c", "raise SystemExit(7)"])

    assert passed.record["exit_code"] == 0
    assert passed.stdout == b"proved\n"
    assert failed.record["exit_code"] == 7
    assert [record["type"] for record in read(repo, "work-1")] == ["claim", "evidence", "evidence"]


def test_verify_refuses_dirty_code(repo: Path) -> None:
    init(repo)
    claim = create_claim(repo, "work-1", "Done")
    append(repo, claim)
    (repo / "app.py").write_text("VALUE = 2\n")

    with pytest.raises(Fab7Error, match="FAB7_REPOSITORY_DIRTY"):
        verify(repo, "work-1", claim["id"], [sys.executable, "-c", "pass"])


def test_ledger_symlink_is_rejected(repo: Path, tmp_path: Path) -> None:
    directory = init(repo)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("")
    (directory / "work-1.jsonl").symlink_to(outside)

    with pytest.raises(Fab7Error, match="FAB7_PATH_INVALID"):
        read(repo, "work-1")
