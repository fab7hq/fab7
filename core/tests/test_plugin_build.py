from __future__ import annotations

import json
from pathlib import Path

from fab7.plugin.adapter import PluginAction, PluginMetadata
from fab7.plugin.build import build_plugin_roots


def _metadata() -> PluginMetadata:
    return PluginMetadata(
        name="thread-check",
        display_name="Thread Check",
        version="0.1.0",
        description="Thread Check extension for Fab7.",
        publisher="fab7hq",
        publisher_url="https://github.com/fab7hq",
        repository="https://github.com/fab7hq/thread-check",
        license="MIT",
        capabilities=("Start Thread Check",),
        default_prompt="Start Thread Check.",
    )


def test_adapters_render_shared_skills_into_native_plugin_roots(tmp_path: Path) -> None:
    action = PluginAction(
        name="start",
        template=(
            "---\n"
            "name: start\n"
            "description: Start Thread Check through {{invocation}}.\n"
            "disable-model-invocation: true\n"
            "allowed-tools: Bash(thread-check start:*)\n"
            "---\n\n"
            "Run `thread-check start --json` for {{host}}.\n"
        ),
        surface="skill",
    )

    build_plugin_roots(tmp_path / "hosts", _metadata(), ("claude", "codex"), (action,))

    claude = tmp_path / "hosts/claude"
    codex = tmp_path / "hosts/codex"
    claude_skill = claude / "plugins/thread-check/skills/start/SKILL.md"
    codex_skill = codex / "plugins/thread-check/skills/start/SKILL.md"
    assert "/thread-check:start" in claude_skill.read_text()
    assert "disable-model-invocation: true" in claude_skill.read_text()
    assert "$thread-check:start" in codex_skill.read_text()
    assert "disable-model-invocation" not in codex_skill.read_text()
    assert "allowed-tools" not in codex_skill.read_text()

    claude_manifest = json.loads(
        (claude / "plugins/thread-check/.claude-plugin/plugin.json").read_text()
    )
    codex_manifest = json.loads(
        (codex / "plugins/thread-check/.codex-plugin/plugin.json").read_text()
    )
    assert claude_manifest["name"] == codex_manifest["name"] == "thread-check"
    assert codex_manifest["skills"] == "./skills/"
    assert json.loads((claude / ".claude-plugin/marketplace.json").read_text())["plugins"][0][
        "source"
    ] == "./plugins/thread-check"
    assert json.loads((codex / ".agents/plugins/marketplace.json").read_text())["plugins"][0][
        "source"
    ] == {"source": "local", "path": "./plugins/thread-check"}


def test_native_action_adapter_keeps_host_specific_surface(tmp_path: Path) -> None:
    action = PluginAction(
        name="init",
        template=(
            "---\n"
            "name: init\n"
            "description: Initialize through {{invocation}}.\n"
            "---\n\n"
            "Run `fab7 init --json`.\n"
        ),
        surface="native",
        claude_allowed_tools="Bash(fab7 init:*)",
    )

    build_plugin_roots(tmp_path / "hosts", _metadata(), ("claude", "codex"), (action,))

    command = tmp_path / "hosts/claude/plugins/thread-check/commands/init.md"
    skill = tmp_path / "hosts/codex/plugins/thread-check/skills/init/SKILL.md"
    assert command.is_file()
    assert "allowed-tools: Bash(fab7 init:*)" in command.read_text()
    assert skill.is_file()
    assert not (tmp_path / "hosts/claude/plugins/thread-check/skills/init").exists()
    assert not (tmp_path / "hosts/codex/plugins/thread-check/commands").exists()
