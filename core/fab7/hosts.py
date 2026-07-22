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
MAX_OUTPUT = 64 * 1024


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str]], CommandResult]


def install_host(host: str, *, host_root: Path | None = None, runner: Runner | None = None) -> dict[str, Any]:
    if host_root is None:
        release, _ = selected_release()
        host_root = release / "hosts" / host
    return install_plugin(host, "fab7", host_root=host_root, runner=runner)


def install_plugin(
    host: str,
    name: str,
    *,
    host_root: Path,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if host not in HOSTS:
        raise Fab7Error("FAB7_HOST_UNSUPPORTED", "Supported hosts are claude and codex")
    if not _canonical_name(name):
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Plugin name is invalid")
    if host_root.is_symlink():
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled host root must not be a symlink")
    host_root = host_root.resolve()
    _validate_host_root(host, name, host_root)
    run = runner or _run_command
    plugin_id = f"{name}@{name}"

    if host == "claude":
        _require_success(run(["claude", "plugin", "validate", "--strict", str(host_root)]), "validation")
    marketplaces = _json_result(run([host, "plugin", "marketplace", "list", "--json"]), "marketplace list")
    configured = _find_marketplace(marketplaces, name)
    marketplace_added = False
    plugin_added = False
    if configured is not None:
        configured_root = _marketplace_root(configured)
        if configured_root is None or configured_root.resolve() != host_root:
            raise Fab7Error(
                "FAB7_HOST_MARKETPLACE_CONFLICT",
                f"A different marketplace already owns the {name} name",
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
        if _plugin_installed(plugins, plugin_id):
            return _result(host, name, "already_installed", host_root)
        if host == "claude":
            command = ["claude", "plugin", "install", plugin_id, "--scope", "user"]
        else:
            command = ["codex", "plugin", "add", plugin_id, "--json"]
        _require_success(run(command), "plugin install")
        plugin_added = True
        installed = _json_result(run([host, "plugin", "list", "--json"]), "plugin verification")
        if not _plugin_installed(installed, plugin_id):
            raise Fab7Error("FAB7_HOST_INSTALL_FAILED", f"Host did not report {name} as installed")
    except Fab7Error:
        if plugin_added:
            if host == "claude":
                _best_effort(run, ["claude", "plugin", "uninstall", plugin_id, "--scope", "user"])
            else:
                _best_effort(run, ["codex", "plugin", "remove", plugin_id, "--json"])
        if marketplace_added:
            if host == "claude":
                _best_effort(run, ["claude", "plugin", "marketplace", "remove", name, "--scope", "user"])
            else:
                _best_effort(run, ["codex", "plugin", "marketplace", "remove", name, "--json"])
        raise
    return _result(host, name, "installed", host_root)


def uninstall_plugin(
    host: str,
    name: str,
    *,
    host_root: Path,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if host not in HOSTS:
        raise Fab7Error("FAB7_HOST_UNSUPPORTED", "Supported hosts are claude and codex")
    if not _canonical_name(name):
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Plugin name is invalid")
    if host_root.is_symlink():
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled host root must not be a symlink")
    host_root = host_root.resolve()
    run = runner or _run_command
    plugin_id = f"{name}@{name}"
    marketplaces = _json_result(run([host, "plugin", "marketplace", "list", "--json"]), "marketplace list")
    configured = _find_marketplace(marketplaces, name)
    if configured is not None:
        configured_root = _marketplace_root(configured)
        if configured_root is None or configured_root.resolve() != host_root:
            raise Fab7Error(
                "FAB7_HOST_MARKETPLACE_CONFLICT",
                f"A different marketplace owns the {name} name",
                {"host": host},
            )
    plugins = _json_result(run([host, "plugin", "list", "--json"]), "plugin list")
    installed = _plugin_installed(plugins, plugin_id)
    if installed and configured is None:
        raise Fab7Error(
            "FAB7_HOST_MARKETPLACE_CONFLICT",
            f"Installed {name} plugin has no matching managed marketplace",
            {"host": host},
        )
    if installed:
        if host == "claude":
            command = ["claude", "plugin", "uninstall", plugin_id, "--scope", "user"]
        else:
            command = ["codex", "plugin", "remove", plugin_id, "--json"]
        _require_success(run(command), "plugin uninstall")
    if configured is not None:
        if host == "claude":
            command = ["claude", "plugin", "marketplace", "remove", name, "--scope", "user"]
        else:
            command = ["codex", "plugin", "marketplace", "remove", name, "--json"]
        _require_success(run(command), "marketplace remove")
    return _result(host, name, "uninstalled", host_root)


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


def _validate_host_root(host: str, name: str, root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled host root is missing or symlinked")
    if host == "claude":
        marketplace_path = root / ".claude-plugin" / "marketplace.json"
        manifest_path = root / "plugins" / name / ".claude-plugin" / "plugin.json"
    else:
        marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
        manifest_path = root / "plugins" / name / ".codex-plugin" / "plugin.json"
    for path in (marketplace_path, manifest_path):
        if path.is_symlink() or not path.is_file():
            raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", f"Bundled host artifact is missing: {path.name}")
    marketplace = _read_json(marketplace_path)
    manifest = _read_json(manifest_path)
    if marketplace.get("name") != name or manifest.get("name") != name:
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled host identity is invalid")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled marketplace plugins are invalid")
    entry = plugins[0]
    expected_source: str | dict[str, str]
    if host == "claude":
        expected_source = f"./plugins/{name}"
    else:
        expected_source = {"source": "local", "path": f"./plugins/{name}"}
    if entry.get("name") != name or entry.get("source") != expected_source:
        raise Fab7Error("FAB7_HOST_ARTIFACT_INVALID", "Bundled marketplace source is invalid")


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


def _plugin_installed(value: Any, plugin_id: str) -> bool:
    entries = value.get("installed", []) if isinstance(value, dict) else value
    if not isinstance(entries, list):
        raise Fab7Error("FAB7_HOST_RESPONSE_INVALID", "Host plugin list has an invalid shape")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        identity = entry.get("pluginId") or entry.get("id")
        if identity == plugin_id and entry.get("installed", True) is not False:
            return True
    return False


def _result(host: str, name: str, status: str, root: Path) -> dict[str, Any]:
    activation = "Run /reload-plugins in Claude Code." if host == "claude" else "Start a new Codex session."
    return {
        "ok": True,
        "host": host,
        "plugin": f"{name}@{name}",
        "marketplace": str(root),
        "status": status,
        "activation": activation,
    }


def _canonical_name(name: str) -> bool:
    return bool(name) and len(name) <= 63 and all(
        character.islower() or character.isdigit() or character == "-" for character in name
    ) and name[0].isalnum() and name[-1].isalnum()
