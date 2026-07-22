"""Claude Code build adapter."""

from __future__ import annotations

from pathlib import Path

from .adapter import HostAdapter, PluginAction, PluginMetadata


class ClaudeAdapter(HostAdapter):
    host = "claude"
    invocation_prefix = "/"
    manifest_path = ".claude-plugin/plugin.json"
    marketplace_path = ".claude-plugin/marketplace.json"

    def plugin_manifest(
        self,
        metadata: PluginMetadata,
        actions: tuple[PluginAction, ...],
    ) -> dict[str, object]:
        manifest: dict[str, object] = {
            "name": metadata.name,
            "displayName": metadata.display_name,
            "version": metadata.version,
            "description": metadata.description,
            "author": {"name": metadata.publisher, "url": metadata.publisher_url},
            "homepage": metadata.repository,
            "repository": metadata.repository,
            "license": metadata.license,
        }
        if any(action.surface == "native" for action in actions):
            manifest["commands"] = "./commands/"
        return manifest

    def marketplace(self, metadata: PluginMetadata) -> dict[str, object]:
        return {
            "name": metadata.name,
            "description": metadata.description,
            "owner": {"name": metadata.publisher, "url": metadata.publisher_url},
            "plugins": [
                {
                    "name": metadata.name,
                    "source": f"./plugins/{metadata.name}",
                    "description": metadata.description,
                    "version": metadata.version,
                }
            ],
        }

    def action_file(
        self,
        action: PluginAction,
        rendered: str,
        metadata: dict[str, str],
        body: str,
    ) -> tuple[Path, str]:
        if action.surface == "skill":
            return Path("skills") / action.name / "SKILL.md", rendered
        allowed_tools = action.claude_allowed_tools or metadata.get("allowed-tools")
        frontmatter = ["---", f"description: {metadata['description']}"]
        if allowed_tools is not None:
            frontmatter.append(f"allowed-tools: {allowed_tools}")
        frontmatter.extend(("---", ""))
        return Path("commands") / f"{action.name}.md", "\n".join(frontmatter) + "\n" + body.lstrip()
