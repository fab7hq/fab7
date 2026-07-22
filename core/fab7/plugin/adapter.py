"""Small build-time adapter contract for native agentic-CLI plugins."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..errors import Fab7Error


PLACEHOLDER_RE = re.compile(r"\{\{[a-z_]+\}\}")
ACTION_METADATA = {"name", "description", "disable-model-invocation", "allowed-tools"}


@dataclass(frozen=True)
class PluginMetadata:
    name: str
    display_name: str
    version: str
    description: str
    publisher: str
    publisher_url: str
    repository: str
    license: str
    capabilities: tuple[str, ...]
    default_prompt: str


@dataclass(frozen=True)
class PluginAction:
    name: str
    template: str
    surface: str = "skill"
    claude_allowed_tools: str | None = None


class HostAdapter(ABC):
    """Render one complete native host root from shared plugin metadata."""

    host: str
    invocation_prefix: str
    manifest_path: str
    marketplace_path: str

    def build(
        self,
        host_root: Path,
        metadata: PluginMetadata,
        actions: tuple[PluginAction, ...],
    ) -> None:
        plugin_root = host_root / "plugins" / metadata.name
        write_new_json(plugin_root / self.manifest_path, self.plugin_manifest(metadata, actions))
        for action in actions:
            rendered, action_metadata, body = render_action(
                action,
                self.host,
                f"{self.invocation_prefix}{metadata.name}:{action.name}",
            )
            relative, content = self.action_file(
                action,
                rendered,
                action_metadata,
                body,
            )
            write_new_text(plugin_root / relative, content)
        write_new_json(host_root / self.marketplace_path, self.marketplace(metadata))

    @abstractmethod
    def plugin_manifest(
        self,
        metadata: PluginMetadata,
        actions: tuple[PluginAction, ...],
    ) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def marketplace(self, metadata: PluginMetadata) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def action_file(
        self,
        action: PluginAction,
        rendered: str,
        metadata: dict[str, str],
        body: str,
    ) -> tuple[Path, str]:
        raise NotImplementedError


def render_action(
    action: PluginAction,
    host: str,
    invocation: str,
) -> tuple[str, dict[str, str], str]:
    if action.surface not in {"native", "skill"}:
        raise Fab7Error("FAB7_PLUGIN_BUILD_INVALID", "Plugin action surface is invalid")
    rendered = action.template.replace("{{host}}", host).replace("{{invocation}}", invocation)
    if PLACEHOLDER_RE.search(rendered):
        raise Fab7Error("FAB7_PLUGIN_BUILD_INVALID", "Plugin action has unresolved placeholders")
    metadata, body = parse_action(rendered, action.name)
    return rendered, metadata, body


def parse_action(source: str, name: str) -> tuple[dict[str, str], str]:
    if not source.startswith("---\n"):
        raise Fab7Error("FAB7_PLUGIN_BUILD_INVALID", "Plugin action frontmatter is missing")
    try:
        frontmatter, body = source[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise Fab7Error(
            "FAB7_PLUGIN_BUILD_INVALID",
            "Plugin action frontmatter is invalid",
        ) from exc
    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        key, separator, value = line.partition(":")
        value = value.strip()
        if not separator or key not in ACTION_METADATA or not value or key in metadata:
            raise Fab7Error(
                "FAB7_PLUGIN_BUILD_INVALID",
                "Plugin action metadata is invalid",
            )
        metadata[key] = value
    if metadata.get("name") != name or "description" not in metadata:
        raise Fab7Error("FAB7_PLUGIN_BUILD_INVALID", "Plugin action identity is invalid")
    return metadata, body


def canonical_skill(metadata: dict[str, str], body: str) -> str:
    return (
        "---\n"
        f"name: {metadata['name']}\n"
        f"description: {metadata['description']}\n"
        "---\n\n"
        f"{body.lstrip()}"
    )


def write_new_json(path: Path, value: object) -> None:
    write_new_text(path, json.dumps(value, sort_keys=True, indent=2) + "\n")


def write_new_text(path: Path, value: str) -> None:
    if path.exists() or path.is_symlink():
        raise Fab7Error("FAB7_PLUGIN_BUILD_CONFLICT", f"Plugin output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    path.chmod(0o644)
