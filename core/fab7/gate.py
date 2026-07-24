"""One fail-closed rule: the latest claim needs fresh passing evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import git
from .errors import Fab7Error, Result
from .ledger import RECORDS_DIR, normalize_work_item, read, read_all


def check(
    root: Path,
    work_item: str,
    *,
    base: str | None = None,
    head: str | None = None,
) -> Result:
    result = Result()
    normalized = normalize_work_item(work_item)
    try:
        read_all(root)
    except Fab7Error as exc:
        result.errors.append(exc)
        return result

    dirty = [path for path in git.dirty_paths(root) if not _is_record_path(path)]
    if dirty:
        result.fail("FAB7_REPOSITORY_DIRTY", "Merge readiness cannot evaluate uncommitted code", paths=dirty)

    proposed = git.head(root, head or "HEAD")
    try:
        comparison_base = _comparison_base(root, base, head or "HEAD")
        if comparison_base:
            _check_append_only(root, comparison_base, head, result)
    except Fab7Error as exc:
        result.errors.append(exc)

    records = read(root, normalized)
    claims = [record for record in records if record["type"] == "claim"]
    if not claims:
        result.fail("FAB7_CLAIM_MISSING", "No completion claim exists", work_item=normalized)
        return result
    claim = claims[-1]
    linked = [
        record
        for record in records
        if record["type"] == "evidence" and record["claim"] == claim["id"] and record["exit_code"] == 0
    ]
    if not any(_fresh(root, evidence, proposed, head) for evidence in linked):
        result.fail(
            "FAB7_EVIDENCE_MISSING",
            "Latest claim has no fresh passing evidence",
            work_item=normalized,
            record_id=claim["id"],
        )
    return result


def audit(root: Path, work_item: str) -> dict[str, Any]:
    normalized = normalize_work_item(work_item)
    records = read(root, normalized)
    if not records:
        raise Fab7Error("FAB7_WORK_ITEM_UNKNOWN", "No ledger exists for this work item")
    claims = [record for record in records if record["type"] == "claim"]
    latest = claims[-1] if claims else None
    evidence = [record for record in records if record["type"] == "evidence"]
    readiness = check(root, normalized)
    return readiness.to_dict(
        work_item=normalized,
        latest_claim=latest,
        evidence=evidence,
        record_count=len(records),
    )


def doctor(root: Path) -> dict[str, Any]:
    result = Result()
    checks: list[dict[str, Any]] = [{"name": "git", "ok": True, "detail": str(root)}]
    try:
        from .install import fab7_home, selected_release
        from .toolchain import RECOMMENDED_UV_VERSION, inspect_toolchain

        _release, manifest = selected_release()
        toolchain = inspect_toolchain(fab7_home())
        compared_fields = (
            "python",
            "pyinstaller",
            "pyinstaller_hooks",
            "target",
            "build_requirements_sha256",
        )
        if any(toolchain[field] != manifest["toolchain"][field] for field in compared_fields):
            raise Fab7Error(
                "FAB7_TOOLCHAIN_DRIFT",
                "The selected Fab7 release toolchain differs from the host toolchain",
            )
        uv_version = toolchain["uv"]["version"]
        advisory = (
            ""
            if uv_version == RECOMMENDED_UV_VERSION
            else f"; tested with uv {RECOMMENDED_UV_VERSION}"
        )
        checks.append(
            {
                "name": "toolchain",
                "ok": True,
                "detail": f"{toolchain['target']}; uv {uv_version}{advisory}",
            }
        )
    except Fab7Error as exc:
        result.errors.append(exc)
        checks.append({"name": "toolchain", "ok": False, "detail": exc.message})
    records_dir = root / RECORDS_DIR
    checks.append({"name": "workspace", "ok": records_dir.is_dir(), "detail": str(records_dir)})
    if not records_dir.is_dir():
        result.fail("FAB7_NOT_INITIALIZED", "Run fab7 init first")
    else:
        try:
            ledgers = read_all(root)
            checks.append({"name": "ledger", "ok": True, "detail": f"{len(ledgers)} work item(s)"})
        except Fab7Error as exc:
            result.errors.append(exc)
            checks.append({"name": "ledger", "ok": False, "detail": exc.message})
    return result.to_dict(checks=checks)


def _comparison_base(root: Path, base: str | None, proposed_head: str) -> str | None:
    if base:
        return git.merge_base(root, git.head(root, base), git.head(root, proposed_head))
    return git.default_base(root, proposed_head)


def _check_append_only(root: Path, base: str, head: str | None, result: Result) -> None:
    for status, path in git.diff_status(root, base, head, RECORDS_DIR):
        target = git.show_file(root, head, path) if head else (root / path).read_bytes() if (root / path).exists() else None
        if status == "A" and target is not None and (not target or target.endswith(b"\n")):
            continue
        if status == "M":
            original = git.show_file(root, base, path)
            if original is not None and target is not None and target.startswith(original) and target.endswith(b"\n"):
                continue
        result.fail("FAB7_LEDGER_REWRITE", "Ledger changes must only append complete lines", path=path, status=status)


def _fresh(root: Path, evidence: dict[str, Any], proposed: str, head: str | None) -> bool:
    try:
        evidence_ref = git.head(root, evidence["git_ref"])
        if not git.is_ancestor(evidence_ref, proposed, root):
            return False
        changed = git.changed_files(root, evidence_ref, proposed if head else None)
        return not any(not _is_record_path(path) for path in changed)
    except Fab7Error:
        return False


def _is_record_path(path: str) -> bool:
    return path.replace("\\", "/").startswith(RECORDS_DIR + "/")
