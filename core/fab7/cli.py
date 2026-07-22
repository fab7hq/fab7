"""Fab7's intentionally small command line surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__, git
from .errors import Fab7Error
from .extension_package import build_extension_archive
from .extension_scaffold import create_extension_source
from .extensions import (
    catalog_listing,
    extension_doctor,
    install_local_extension,
    install_registry_extension,
    refresh_catalog,
    uninstall_extension,
)
from .gate import audit, check, doctor
from .hosts import install_host
from .install import dispatch_project, init_project
from .ledger import append, create_claim, derive_work_item, verify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fab7")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init", help="create .fab7/records")
    initialize.add_argument("--json", action="store_true")

    host_install = commands.add_parser("install", help="register the Fab7 plugin with an agentic CLI")
    host_install.add_argument("host", choices=("claude", "codex"))
    host_install.add_argument("--json", action="store_true")

    extension = commands.add_parser("ext", help="inspect and manage Fab7 extensions")
    extension_commands = extension.add_subparsers(dest="extension_command", required=True)
    extension_list = extension_commands.add_parser("list", help="validate and list available extensions")
    extension_list.add_argument("--catalog", type=Path)
    extension_list.add_argument("--refresh", action="store_true")
    extension_list.add_argument("--json", action="store_true")
    extension_refresh = extension_commands.add_parser("refresh", help="refresh the reviewed extension catalog")
    extension_refresh.add_argument("--json", action="store_true")
    extension_create = extension_commands.add_parser("create", help="create extension source files")
    extension_create.add_argument("target", nargs="?", type=Path, default=Path("."))
    extension_create.add_argument("--name", required=True)
    extension_create.add_argument("--publisher", required=True)
    extension_create.add_argument("--version", default="0.1.0")
    extension_create.add_argument("--json", action="store_true")
    extension_build = extension_commands.add_parser("build", help="build a deterministic extension ZIP")
    extension_build.add_argument("source", nargs="?", type=Path, default=Path("."))
    extension_build.add_argument("--host", required=True, action="append", choices=("claude", "codex"))
    extension_build.add_argument("--output", type=Path)
    extension_build.add_argument("--json", action="store_true")
    extension_install = extension_commands.add_parser("install", help="install a registry or local extension")
    extension_install.add_argument("name", nargs="?")
    extension_install.add_argument("--local", type=Path)
    extension_install.add_argument("--catalog", type=Path)
    extension_install.add_argument("--host", required=True, choices=("claude", "codex"))
    extension_install.add_argument("--json", action="store_true")
    extension_doctor_parser = extension_commands.add_parser("doctor", help="validate extension state")
    extension_doctor_parser.add_argument("--json", action="store_true")
    extension_uninstall = extension_commands.add_parser("uninstall", help="uninstall one extension")
    extension_uninstall.add_argument("name")
    extension_uninstall.add_argument("--host", required=True, choices=("claude", "codex"))
    extension_uninstall.add_argument("--json", action="store_true")

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
    direct_invocation = argv is None
    raw_argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(raw_argv)
    try:
        if args.command == "install":
            data = install_host(args.host)
            return _finish(args, data, f"Fab7 plugin for {args.host}: {data['status']}")
        if args.command == "ext" and args.extension_command == "list":
            if args.refresh:
                if args.catalog is not None:
                    raise Fab7Error(
                        "FAB7_CATALOG_SOURCE_INVALID",
                        "--refresh cannot be combined with --catalog",
                    )
                refresh_catalog()
            data = catalog_listing(args.catalog, include_installed=True)
            return _finish_extension_list(args, data)
        if args.command == "ext" and args.extension_command == "refresh":
            data = refresh_catalog()
            return _finish(args, data, f"Fab7 extension catalog: {data['status']}")
        if args.command == "ext" and args.extension_command == "create":
            data = create_extension_source(
                args.target,
                name=args.name,
                publisher=args.publisher,
                version=args.version,
            )
            return _finish(args, data, f"Fab7 extension {data['name']}: {data['status']}")
        if args.command == "ext" and args.extension_command == "build":
            data = build_extension_archive(args.source, args.output, hosts=tuple(args.host))
            return _finish(args, data, f"Fab7 extension built: {data['output']}")
        if args.command == "ext" and args.extension_command == "install":
            if (args.name is None) == (args.local is None):
                raise Fab7Error(
                    "FAB7_EXTENSION_SOURCE_REQUIRED",
                    "Choose exactly one registry name or --local PATH",
                )
            if args.local is not None:
                if args.catalog is not None:
                    raise Fab7Error(
                        "FAB7_EXTENSION_SOURCE_INVALID",
                        "--catalog cannot be combined with --local",
                    )
                data = install_local_extension(args.local, args.host)
            else:
                data = install_registry_extension(
                    args.name,
                    args.host,
                    catalog_path=args.catalog,
                )
            return _finish(args, data, f"Fab7 extension {data['name']}: {data['status']}")
        if args.command == "ext" and args.extension_command == "doctor":
            data = extension_doctor()
            return _finish_result(args, data, "Fab7 extension doctor")
        if args.command == "ext" and args.extension_command == "uninstall":
            data = uninstall_extension(args.name, args.host)
            return _finish(args, data, f"Fab7 extension {data['name']}: {data['status']}")
        root = git.repo_root()
        if direct_invocation:
            dispatched = dispatch_project(root, args.command, raw_argv, Path(sys.argv[0]))
            if dispatched is not None:
                return dispatched
        if args.command == "init":
            data = init_project(root)
            return _finish(args, data, f"Fab7 project: {data['status']}")
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
        next_action = data.get("next_action") or data.get("activation")
        if isinstance(next_action, str):
            print(next_action)
    return 0


def _finish_result(args: argparse.Namespace, data: dict[str, Any], label: str) -> int:
    if args.json:
        print(json.dumps(data, sort_keys=True, indent=2))
    else:
        print(f"{label}: {'PASS' if data['ok'] else 'FAIL'}")
        for error in data.get("errors", []):
            print(f"ERROR {error['code']}: {error['message']}")
    return 0 if data["ok"] else 1


def _finish_extension_list(args: argparse.Namespace, data: dict[str, Any]) -> int:
    if args.json:
        print(json.dumps(data, sort_keys=True, indent=2))
    else:
        print(f"Fab7 extensions: {data['count']}")
        for extension in data["extensions"]:
            print(f"{extension['name']} {extension['version']} {extension['repository']}")
        for installed in data.get("installed", []):
            print(
                f"installed {installed['name']} {installed['version']} "
                f"{installed['origin']} {installed['install_id']}"
            )
    return 0


def _replay(content: bytes, stream: Any) -> None:
    if content:
        stream.write(content.decode(errors="replace"))
        if not content.endswith(b"\n"):
            stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
