"""Codex build adapter."""

from __future__ import annotations

from pathlib import Path

from .adapter import HostAdapter, PluginAction, PluginMetadata, canonical_skill


class CodexAdapter(HostAdapter):
    host = "codex"
    invocation_prefix = "$"
    manifest_path = ".codex-plugin/plugin.json"
    marketplace_path = ".agents/plugins/marketplace.json"

    def plugin_manifest(
        self,
        metadata: PluginMetadata,
        actions: tuple[PluginAction, ...],
    ) -> dict[str, object]:
        interface = {
            "displayName": metadata.display_name,
            "shortDescription": metadata.description,
            "longDescription": metadata.description,
            "developerName": metadata.publisher,
            "category": "Productivity",
            "defaultPrompt": metadata.default_prompt,
        }
        if metadata.capabilities:
            interface["capabilities"] = list(metadata.capabilities)
        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "author": {"name": metadata.publisher, "url": metadata.publisher_url},
            "homepage": metadata.repository,
            "repository": metadata.repository,
            "license": metadata.license,
            "skills": "./skills/",
            "interface": interface,
        }

    def marketplace(self, metadata: PluginMetadata) -> dict[str, object]:
        return {
            "name": metadata.name,
            "interface": {"displayName": metadata.display_name},
            "plugins": [
                {
                    "name": metadata.name,
                    "source": {
                        "source": "local",
                        "path": f"./plugins/{metadata.name}",
                    },
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity",
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
        return Path("skills") / action.name / "SKILL.md", canonical_skill(metadata, body)
