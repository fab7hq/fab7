"""Append-only claim and executed-evidence records."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from . import git
from .errors import Fab7Error


RECORDS_DIR = ".fab7/records"
WORK_ITEM_RE = re.compile(r"^[a-z0-9_.-]{1,120}$")
RECORD_ID_RE = re.compile(r"^rec_[0-9a-f]{32}$")
COMMON_FIELDS = {"v", "id", "type", "work_item", "created_at", "actor", "git_ref", "summary"}


@dataclass(frozen=True)
class Verification:
    record: dict[str, Any]
    stdout: bytes
    stderr: bytes
    timed_out: bool = False


def normalize_work_item(value: str | None) -> str:
    if value is None:
        raise Fab7Error("FAB7_WORK_ITEM_REQUIRED", "A work item is required")
    normalized = re.sub(r"[^a-z0-9_.-]+", "-", value.strip().lower()).strip("-")
    if not normalized or normalized in {".", ".."} or not WORK_ITEM_RE.fullmatch(normalized):
        raise Fab7Error("FAB7_WORK_ITEM_INVALID", "Work item must be a short repository-safe name")
    return normalized


def derive_work_item(root: Path, explicit: str | None) -> str:
    if explicit:
        return normalize_work_item(explicit)
    pr = os.environ.get("FAB7_PR_NUMBER") or os.environ.get("GITHUB_PR_NUMBER")
    if pr:
        return normalize_work_item(f"pr-{pr}")
    current = git.branch(root)
    if current:
        return normalize_work_item(current)
    raise Fab7Error("FAB7_WORK_ITEM_REQUIRED", "Pass --work-item when Git has no current branch")


def init(root: Path) -> Path:
    path = root / RECORDS_DIR
    if (root / ".fab7").is_symlink() or path.is_symlink():
        raise Fab7Error("FAB7_PATH_INVALID", "Fab7 workspace directories must not be symlinks")
    path.mkdir(parents=True, exist_ok=True)
    return path


def record_path(root: Path, work_item: str) -> Path:
    return root / RECORDS_DIR / f"{normalize_work_item(work_item)}.jsonl"


def create_claim(root: Path, work_item: str, summary: str, actor: str | None = None) -> dict[str, Any]:
    return {
        **_base_record(root, "claim", work_item, summary, actor),
    }


def verify(
    root: Path,
    work_item: str,
    claim_id: str,
    command: list[str],
    *,
    timeout: float = 300,
    actor: str | None = None,
) -> Verification:
    if not command:
        raise Fab7Error("FAB7_COMMAND_REQUIRED", "Pass a verification command after --")
    if not math.isfinite(timeout) or timeout <= 0:
        raise Fab7Error("FAB7_TIMEOUT_INVALID", "Verification timeout must be a positive number")
    records = read(root, work_item)
    if not any(record["type"] == "claim" and record["id"] == claim_id for record in records):
        raise Fab7Error("FAB7_CLAIM_UNKNOWN", "Evidence must link to a claim in the same work item")
    _require_clean_code(root)
    tested_ref = git.head(root)
    timed_out = False
    try:
        process = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        exit_code = process.returncode
        stdout = process.stdout
        stderr = process.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = _as_bytes(exc.stdout)
        stderr = _as_bytes(exc.stderr)
    except OSError as exc:
        raise Fab7Error("FAB7_COMMAND_FAILED", f"Verification command could not start: {exc}") from exc
    if git.head(root) != tested_ref:
        raise Fab7Error("FAB7_REPOSITORY_CHANGED", "Verification command changed HEAD; no evidence was recorded")
    _require_clean_code(root)
    digest = "sha256:" + hashlib.sha256(stdout + b"\0" + stderr).hexdigest()
    command_digest = "sha256:" + hashlib.sha256(_canonical(command).encode()).hexdigest()
    record = {
        **_base_record(root, "evidence", work_item, Path(command[0]).name, actor, git_ref=tested_ref),
        "claim": claim_id,
        "command_digest": command_digest,
        "exit_code": exit_code,
        "output_digest": digest,
    }
    append(root, record)
    return Verification(record, stdout, stderr, timed_out)


def append(root: Path, record: dict[str, Any]) -> tuple[Path, int]:
    path = record_path(root, record.get("work_item"))
    directory = root / RECORDS_DIR
    if not directory.is_dir():
        raise Fab7Error("FAB7_NOT_INITIALIZED", "Run fab7 init first")
    if directory.is_symlink() or path.is_symlink():
        raise Fab7Error("FAB7_PATH_INVALID", "Fab7 ledgers must not be symlinks")
    validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock(path):
        existing = path.read_bytes() if path.exists() else b""
        records = _parse(existing, path)
        line = len(records) + 1
        content = existing + (_canonical(record) + "\n").encode()
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.stem}.", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    return path, line


def read(root: Path, work_item: str) -> list[dict[str, Any]]:
    path = record_path(root, work_item)
    if not path.exists():
        return []
    if path.is_symlink():
        raise Fab7Error("FAB7_PATH_INVALID", "Fab7 ledgers must not be symlinks")
    return _parse(path.read_bytes(), path)


def read_all(root: Path) -> dict[str, list[dict[str, Any]]]:
    directory = root / RECORDS_DIR
    if not directory.is_dir():
        raise Fab7Error("FAB7_NOT_INITIALIZED", "Run fab7 init first")
    if directory.is_symlink():
        raise Fab7Error("FAB7_PATH_INVALID", "Fab7 records directory must not be a symlink")
    ledgers: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(directory.glob("*.jsonl")):
        if path.is_symlink():
            raise Fab7Error("FAB7_PATH_INVALID", "Fab7 ledgers must not be symlinks", {"path": str(path)})
        work_item = normalize_work_item(path.stem)
        records = _parse(path.read_bytes(), path)
        if any(record["work_item"] != work_item for record in records):
            raise Fab7Error("FAB7_LEDGER_INVALID", "Record work item does not match its ledger", {"path": str(path)})
        ledgers[work_item] = records
    return ledgers


def validate_record(record: Any) -> None:
    if not isinstance(record, dict):
        raise Fab7Error("FAB7_LEDGER_INVALID", "Each JSONL line must be an object")
    record_type = record.get("type")
    allowed = COMMON_FIELDS if record_type == "claim" else COMMON_FIELDS | {
        "claim", "command_digest", "exit_code", "output_digest"
    }
    if record_type not in {"claim", "evidence"} or set(record) != allowed:
        raise Fab7Error("FAB7_LEDGER_INVALID", "Record fields or type are invalid", {"record_id": record.get("id")})
    if record.get("v") != 1 or not isinstance(record.get("id"), str) or not RECORD_ID_RE.fullmatch(record["id"]):
        raise Fab7Error("FAB7_LEDGER_INVALID", "Record version or id is invalid")
    if normalize_work_item(record.get("work_item")) != record["work_item"]:
        raise Fab7Error("FAB7_LEDGER_INVALID", "Work item is not canonical")
    for field in ("created_at", "actor", "git_ref", "summary"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise Fab7Error("FAB7_LEDGER_INVALID", f"Record {field} must be a nonempty string")
    if not record["created_at"].endswith("Z"):
        raise Fab7Error("FAB7_LEDGER_INVALID", "created_at must be a UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise Fab7Error("FAB7_LEDGER_INVALID", "created_at must be an ISO timestamp") from exc
    if record_type == "evidence":
        if not isinstance(record["claim"], str) or not RECORD_ID_RE.fullmatch(record["claim"]):
            raise Fab7Error("FAB7_LEDGER_INVALID", "Evidence claim link is invalid")
        if type(record["exit_code"]) is not int:
            raise Fab7Error("FAB7_LEDGER_INVALID", "Evidence exit_code must be an integer")
        for field in ("command_digest", "output_digest"):
            if not isinstance(record[field], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", record[field]):
                raise Fab7Error("FAB7_LEDGER_INVALID", f"Evidence {field} is invalid")


def _base_record(
    root: Path,
    record_type: str,
    work_item: str,
    summary: str,
    actor: str | None,
    *,
    git_ref: str | None = None,
) -> dict[str, Any]:
    if not summary.strip():
        raise Fab7Error("FAB7_SUMMARY_REQUIRED", "Summary must not be empty")
    return {
        "v": 1,
        "id": "rec_" + uuid.uuid4().hex,
        "type": record_type,
        "work_item": normalize_work_item(work_item),
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "actor": actor or os.environ.get("FAB7_ACTOR") or f"human:{git.user_email(root) or 'unknown'}",
        "git_ref": git_ref or git.head(root),
        "summary": summary.strip(),
    }


def _parse(content: bytes, path: Path) -> list[dict[str, Any]]:
    if not content:
        return []
    if not content.endswith(b"\n"):
        raise Fab7Error("FAB7_LEDGER_INVALID", "JSONL ledger must end with a newline", {"path": str(path)})
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(content.splitlines(), 1):
        try:
            record = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
            validate_record(record)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise Fab7Error(
                "FAB7_LEDGER_INVALID", "Ledger contains invalid JSON", {"path": str(path), "line": line_number}
            ) from exc
        except Fab7Error as exc:
            raise Fab7Error(exc.code, exc.message, {**exc.context, "path": str(path), "line": line_number}) from exc
        records.append(record)
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise Fab7Error("FAB7_LEDGER_INVALID", "Ledger contains duplicate record ids", {"path": str(path)})
    claims: set[str] = set()
    for record in records:
        if record["type"] == "claim":
            claims.add(record["id"])
        elif record["claim"] not in claims:
            raise Fab7Error("FAB7_LEDGER_INVALID", "Evidence links to an unknown claim", {"record_id": record["id"]})
    return records


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"duplicate JSON key: {key}")
        data[key] = value
    return data


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _require_clean_code(root: Path) -> None:
    dirty = [path for path in git.dirty_paths(root) if not path.startswith(RECORDS_DIR + "/")]
    if dirty:
        raise Fab7Error(
            "FAB7_REPOSITORY_DIRTY",
            "Commit or remove non-ledger changes before verification",
            {"paths": dirty},
        )


def _as_bytes(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    return value if isinstance(value, bytes) else value.encode()


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    lock = path.with_suffix(".lock")
    deadline = time.monotonic() + 5
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise Fab7Error("FAB7_LEDGER_BUSY", "Another writer holds the ledger lock")
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.rmdir()
