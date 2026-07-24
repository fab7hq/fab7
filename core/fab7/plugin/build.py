"""Shared deterministic native plugin assembly."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable

from ..errors import Fab7Error
from .adapter import HostAdapter, PluginAction, PluginMetadata
from .claude_adapter import ClaudeAdapter
from .codex_adapter import CodexAdapter


NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ADAPTERS: dict[str, HostAdapter] = {
    "claude": ClaudeAdapter(),
    "codex": CodexAdapter(),
}
FAB7_ACTIONS = (
    ("ext-create", "skill", None),
    ("ext-install", "native", "Bash(fab7 ext install:*)"),
    ("ext-list", "native", "Bash(fab7 ext list:*)"),
    ("init", "native", "Bash(fab7 init:*)"),
)
FAB7_ARCHITECTURE_REFERENCES = (
    "distribution.md",
    "ledger.md",
    "overview.md",
)


def build_plugin_roots(
    output_root: Path,
    metadata: PluginMetadata,
    hosts: Iterable[str],
    actions: Iterable[PluginAction],
) -> None:
    selected_hosts = tuple(hosts)
    selected_actions = tuple(actions)
    _validate_inputs(metadata, selected_hosts, selected_actions)
    _empty_output(output_root)
    output_root.mkdir(parents=True)
    for host in selected_hosts:
        host_root = output_root / host
        ADAPTERS[host].build(host_root, metadata, selected_actions)


def build_fab7_plugin_roots(
    source_root: Path,
    output_root: Path,
    version: str,
    hosts: Iterable[str] = ADAPTERS,
) -> None:
    selected_hosts = tuple(hosts)
    architecture_root = source_root / "docs/architecture"
    references = tuple(architecture_root / name for name in FAB7_ARCHITECTURE_REFERENCES)
    if any(path.is_symlink() or not path.is_file() for path in references):
        raise Fab7Error(
            "FAB7_PLUGIN_BUILD_INVALID",
            "Fab7 architecture references are missing or invalid",
        )
    actions = tuple(
        PluginAction(
            name=name,
            template=(source_root / "plugins/fab7/actions" / name / "SKILL.md.tmpl").read_text(),
            surface=surface,
            claude_allowed_tools=allowed_tools,
        )
        for name, surface, allowed_tools in FAB7_ACTIONS
    )
    metadata = PluginMetadata(
        name="fab7",
        display_name="Fab7",
        version=version,
        description="Create, initialize, and manage verified Fab7 extensions.",
        publisher="Fab7",
        publisher_url="https://github.com/fab7hq/fab7",
        repository="https://github.com/fab7hq/fab7",
        license="MIT",
        capabilities=("Execute local Fab7 commands", "Manage verified Fab7 extensions"),
        default_prompt="Initialize Fab7 in this repository.",
    )
    build_plugin_roots(output_root, metadata, selected_hosts, actions)
    for host in selected_hosts:
        target = output_root / host / "plugins/fab7/skills/ext-create/references"
        target.mkdir(parents=True)
        for source in references:
            destination = target / source.name
            if destination.exists():
                raise Fab7Error(
                    "FAB7_PLUGIN_BUILD_CONFLICT",
                    "Fab7 architecture reference paths conflict",
                )
            shutil.copyfile(source, destination)
            destination.chmod(0o644)


def plugin_source_files(source_root: Path) -> list[Path]:
    plugin_root = source_root / "plugins/fab7"
    paths = [
        path
        for path in plugin_root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.relative_to(plugin_root).parts
        and path.suffix != ".pyc"
    ]
    paths.extend(
        source_root / "docs/architecture" / name
        for name in FAB7_ARCHITECTURE_REFERENCES
    )
    return paths


def _validate_inputs(
    metadata: PluginMetadata,
    hosts: tuple[str, ...],
    actions: tuple[PluginAction, ...],
) -> None:
    if not NAME_RE.fullmatch(metadata.name) or not VERSION_RE.fullmatch(metadata.version):
        raise Fab7Error("FAB7_PLUGIN_BUILD_INVALID", "Plugin identity is invalid")
    if not hosts or len(hosts) != len(set(hosts)) or any(host not in ADAPTERS for host in hosts):
        raise Fab7Error(
            "FAB7_HOST_UNSUPPORTED",
            "Supported plugin build hosts are claude and codex",
        )
    names = [action.name for action in actions]
    if names != sorted(names) or len(names) != len(set(names)):
        raise Fab7Error("FAB7_PLUGIN_BUILD_INVALID", "Plugin actions must be canonically ordered")
    if any(not NAME_RE.fullmatch(name) for name in names):
        raise Fab7Error("FAB7_PLUGIN_BUILD_INVALID", "Plugin action name is invalid")


def _empty_output(output_root: Path) -> None:
    if output_root.is_symlink() or output_root.exists():
        raise Fab7Error("FAB7_PLUGIN_BUILD_CONFLICT", f"Plugin output already exists: {output_root}")
