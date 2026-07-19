"""Literal, bounded Claude Code and Codex plugin registration commands."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .errors import Fab7Error
from .install import selected_release


HOSTS = {"claude", "codex"}
PLUGIN_ID = "fab7@fab7"
MAX_OUTPUT = 64 * 1024


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str]], CommandResult]


def install_host(host: str, *, host_root: Path | None = None, runner: Runner | None = None) -> dict[str, Any]:
    if host not in HOSTS:
        raise Fab7Error("FAB7_HOST_UNSUPPORTED", "Supported hosts are claude and codex")
    if host_root is None:
        release, _ = selected_release()
        host_root = release / "hosts" / host
    if host_root.is_symlink():
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled host root must not be a symlink")
    host_root = host_root.resolve()
    _validate_host_root(host, host_root)
    run = runner or _run_command

    if host == "claude":
        _require_success(run(["claude", "plugin", "validate", "--strict", str(host_root)]), "validation")
    marketplaces = _json_result(run([host, "plugin", "marketplace", "list", "--json"]), "marketplace list")
    configured = _find_marketplace(marketplaces, "fab7")
    marketplace_added = False
    plugin_added = False
    if configured is not None:
        configured_root = _marketplace_root(configured)
        if configured_root is None or configured_root.resolve() != host_root:
            raise Fab7Error(
                "FAB7_HOST_MARKETPLACE_CONFLICT",
                "A different marketplace already owns the fab7 name",
                {"host": host},
            )
    else:
        if host == "claude":
            command = ["claude", "plugin", "marketplace", "add", str(host_root), "--scope", "user"]
        else:
            command = ["codex", "plugin", "marketplace", "add", str(host_root), "--json"]
        _require_success(run(command), "marketplace add")
        marketplace_added = True

    try:
        plugins = _json_result(run([host, "plugin", "list", "--json"]), "plugin list")
        if _plugin_installed(plugins):
            return _result(host, "already_installed", host_root)
        if host == "claude":
            command = ["claude", "plugin", "install", PLUGIN_ID, "--scope", "user"]
        else:
            command = ["codex", "plugin", "add", PLUGIN_ID, "--json"]
        _require_success(run(command), "plugin install")
        plugin_added = True
        installed = _json_result(run([host, "plugin", "list", "--json"]), "plugin verification")
        if not _plugin_installed(installed):
            raise Fab7Error("FAB7_HOST_INSTALL_FAILED", "Host did not report the Fab7 plugin as installed")
    except Fab7Error:
        if plugin_added:
            if host == "claude":
                _best_effort(run, ["claude", "plugin", "uninstall", PLUGIN_ID, "--scope", "user"])
            else:
                _best_effort(run, ["codex", "plugin", "remove", PLUGIN_ID, "--json"])
        if marketplace_added:
            if host == "claude":
                _best_effort(run, ["claude", "plugin", "marketplace", "remove", "fab7", "--scope", "user"])
            else:
                _best_effort(run, ["codex", "plugin", "marketplace", "remove", "fab7", "--json"])
        raise
    return _result(host, "installed", host_root)


def _run_command(command: list[str]) -> CommandResult:
    if shutil.which(command[0]) is None:
        raise Fab7Error("FAB7_HOST_MISSING", f"Host executable is not available: {command[0]}")
    try:
        process = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fab7Error("FAB7_HOST_COMMAND_FAILED", f"Host command could not complete: {exc}") from exc
    return CommandResult(process.returncode, process.stdout[-MAX_OUTPUT:], process.stderr[-MAX_OUTPUT:])


def _validate_host_root(host: str, root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled host root is missing or symlinked")
    if host == "claude":
        marketplace_path = root / ".claude-plugin" / "marketplace.json"
        manifest_path = root / "plugins" / "fab7" / ".claude-plugin" / "plugin.json"
        component = root / "plugins" / "fab7" / "commands" / "init.md"
    else:
        marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
        manifest_path = root / "plugins" / "fab7" / ".codex-plugin" / "plugin.json"
        component = root / "plugins" / "fab7" / "skills" / "init" / "SKILL.md"
    for path in (marketplace_path, manifest_path, component):
        if path.is_symlink() or not path.is_file():
            raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", f"Bundled host artifact is missing: {path.name}")
    marketplace = _read_json(marketplace_path)
    manifest = _read_json(manifest_path)
    if marketplace.get("name") != "fab7" or manifest.get("name") != "fab7":
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled host identity is invalid")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", f"Invalid host JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", f"Host JSON must be an object: {path}")
    return value


def _json_result(result: CommandResult, operation: str) -> Any:
    _require_success(result, operation)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Fab7Error("FAB7_HOST_RESPONSE_INVALID", f"Host returned invalid JSON for {operation}") from exc


def _require_success(result: CommandResult, operation: str) -> None:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        if len(detail) > 500:
            detail = detail[-500:]
        raise Fab7Error(
            "FAB7_HOST_COMMAND_FAILED",
            f"Host {operation} failed" + (f": {detail}" if detail else ""),
        )


def _best_effort(run: Runner, command: list[str]) -> None:
    try:
        run(command)
    except (Fab7Error, OSError):
        pass


def _find_marketplace(value: Any, name: str) -> dict[str, Any] | None:
    entries = value.get("marketplaces", []) if isinstance(value, dict) else value
    if not isinstance(entries, list):
        raise Fab7Error("FAB7_HOST_RESPONSE_INVALID", "Host marketplace list has an invalid shape")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return None


def _marketplace_root(entry: dict[str, Any]) -> Path | None:
    for key in ("root", "path"):
        if isinstance(entry.get(key), str):
            return Path(entry[key])
    source = entry.get("source")
    if isinstance(source, str):
        return Path(source)
    if isinstance(source, dict):
        for key in ("source", "path"):
            if isinstance(source.get(key), str):
                return Path(source[key])
    marketplace_source = entry.get("marketplaceSource")
    if isinstance(marketplace_source, dict) and isinstance(marketplace_source.get("source"), str):
        return Path(marketplace_source["source"])
    return None


def _plugin_installed(value: Any) -> bool:
    entries = value.get("installed", []) if isinstance(value, dict) else value
    if not isinstance(entries, list):
        raise Fab7Error("FAB7_HOST_RESPONSE_INVALID", "Host plugin list has an invalid shape")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        identity = entry.get("pluginId") or entry.get("id")
        if identity == PLUGIN_ID and entry.get("installed", True) is not False:
            return True
    return False


def _result(host: str, status: str, root: Path) -> dict[str, Any]:
    activation = "Run /reload-plugins in Claude Code." if host == "claude" else "Start a new Codex session."
    return {
        "ok": True,
        "host": host,
        "plugin": PLUGIN_ID,
        "marketplace": str(root),
        "status": status,
        "activation": activation,
    }
