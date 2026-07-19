"""Fab7's intentionally small command line surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__, git
from .errors import Fab7Error
from .gate import audit, check, doctor
from .ledger import append, create_claim, derive_work_item, init, verify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fab7")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init", help="create .fab7/records")
    initialize.add_argument("--json", action="store_true")

    claim = commands.add_parser("claim", help="record a completion claim")
    claim.add_argument("--work-item")
    claim.add_argument("--summary", required=True)
    claim.add_argument("--actor")
    claim.add_argument("--json", action="store_true")

    verification = commands.add_parser("verify", help="run a command and record its result")
    verification.add_argument("--work-item")
    verification.add_argument("--claim", required=True)
    verification.add_argument("--timeout", type=float, default=300)
    verification.add_argument("--actor")
    verification.add_argument("--json", action="store_true")
    verification.add_argument("verification_command", nargs=argparse.REMAINDER)

    ci = commands.add_parser("ci-check", help="require fresh evidence for the latest claim")
    ci.add_argument("--work-item")
    ci.add_argument("--base")
    ci.add_argument("--head")
    ci.add_argument("--json", action="store_true")

    report = commands.add_parser("audit", help="show claims, evidence, and readiness")
    report.add_argument("--work-item")
    report.add_argument("--json", action="store_true")

    diagnosis = commands.add_parser("doctor", help="validate Git and Fab7 records")
    diagnosis.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = git.repo_root()
        if args.command == "init":
            path = init(root)
            return _finish(args, {"ok": True, "records": str(path)}, f"Initialized Fab7 at {path}")
        if args.command == "claim":
            work_item = derive_work_item(root, args.work_item)
            record = create_claim(root, work_item, args.summary, args.actor)
            path, line = append(root, record)
            return _finish(
                args,
                {"ok": True, "record": record, "path": str(path), "line": line},
                f"Claim {record['id']} recorded for {work_item}",
            )
        if args.command == "verify":
            command = args.verification_command
            if command[:1] == ["--"]:
                command = command[1:]
            work_item = derive_work_item(root, args.work_item)
            verification = verify(
                root,
                work_item,
                args.claim,
                command,
                timeout=args.timeout,
                actor=args.actor,
            )
            data = {
                "ok": verification.record["exit_code"] == 0,
                "record": verification.record,
                "timed_out": verification.timed_out,
            }
            if args.json:
                print(json.dumps(data, sort_keys=True, indent=2))
            else:
                _replay(verification.stdout, sys.stdout)
                _replay(verification.stderr, sys.stderr)
                print(
                    f"Evidence {verification.record['id']} recorded: "
                    f"exit {verification.record['exit_code']}"
                )
            return 0 if data["ok"] else 1
        if args.command == "ci-check":
            work_item = derive_work_item(root, args.work_item)
            result = check(root, work_item, base=args.base, head=args.head)
            return _finish_result(args, result.to_dict(work_item=work_item), "Fab7 merge readiness")
        if args.command == "audit":
            work_item = derive_work_item(root, args.work_item)
            data = audit(root, work_item)
            return _finish_result(args, data, f"Fab7 audit for {work_item}")
        if args.command == "doctor":
            data = doctor(root)
            return _finish_result(args, data, "Fab7 doctor")
        parser.error("unknown command")
    except Fab7Error as exc:
        data = {"ok": False, "errors": [exc.to_dict()]}
        if getattr(args, "json", False):
            print(json.dumps(data, sort_keys=True, indent=2))
        else:
            print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"FAB7_UNEXPECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    return 2


def _finish(args: argparse.Namespace, data: dict[str, Any], message: str) -> int:
    if args.json:
        print(json.dumps(data, sort_keys=True, indent=2))
    else:
        print(message)
    return 0


def _finish_result(args: argparse.Namespace, data: dict[str, Any], label: str) -> int:
    if args.json:
        print(json.dumps(data, sort_keys=True, indent=2))
    else:
        print(f"{label}: {'PASS' if data['ok'] else 'FAIL'}")
        for error in data.get("errors", []):
            print(f"ERROR {error['code']}: {error['message']}")
    return 0 if data["ok"] else 1


def _replay(content: bytes, stream: Any) -> None:
    if content:
        stream.write(content.decode(errors="replace"))
        if not content.endswith(b"\n"):
            stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
