from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from fab7 import __version__
from fab7.release_build import build_release


ROOT = Path(__file__).resolve().parents[2]


def _build(target: Path) -> None:
    build_release(ROOT, target)


def _snapshot(root: Path) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode & 0o777
        if path.is_symlink():
            content = f"link:{os.readlink(path)}"
        elif path.is_file():
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            content = "directory"
        rows.append((relative, mode, content))
    return rows


def test_release_tree_is_deterministic_and_executable(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _build(first)
    _build(second)

    assert _snapshot(first) == _snapshot(second)
    assert not list(first.rglob("__pycache__"))
    assert not list(first.rglob("*.pyc"))
    executable = first / "bin" / "fab7"
    assert executable.stat().st_mode & 0o111
    result = subprocess.run(
        [str(executable), "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == __version__
    with zipfile.ZipFile(executable) as archive:
        assert {
            "fab7/templates/extension/fab7-extension.json.tmpl",
            "fab7/templates/extension/skills/start/SKILL.md.tmpl",
            "fab7/templates/extension/src/extension.py.tmpl",
            "fab7/templates/extension/tests/test_extension.py.tmpl",
            "fab7/plugin/__init__.py",
            "fab7/plugin/adapter.py",
            "fab7/plugin/build.py",
            "fab7/plugin/claude_adapter.py",
            "fab7/plugin/codex_adapter.py",
        }.issubset(archive.namelist())

    manifest = json.loads((first / "manifest.json").read_text())
    assert set(manifest) == {
        "schema", "name", "version", "source_sha256", "executable_sha256", "python"
    }
    assert manifest["executable_sha256"] == "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    assert (first / "hosts/claude/.claude-plugin/marketplace.json").is_file()
    assert (first / "hosts/codex/.agents/plugins/marketplace.json").is_file()
    assert (first / "hosts/claude/plugins/fab7/commands/ext-list.md").is_file()
    assert (first / "hosts/claude/plugins/fab7/commands/ext-install.md").is_file()
    claude_install = (first / "hosts/claude/plugins/fab7/commands/ext-install.md").read_text()
    assert "--host claude" in claude_install
    assert "--host codex" not in claude_install
    ext_create = first / "hosts/claude/plugins/fab7/skills/ext-create"
    assert (ext_create / "SKILL.md").is_file()
    assert sorted(path.name for path in (ext_create / "references").iterdir()) == [
        "distribution.md",
        "ledger.md",
        "overview.md",
    ]
    for name in ("overview.md", "distribution.md", "ledger.md"):
        assert (ext_create / "references" / name).read_bytes() == (
            ROOT / "docs/architecture" / name
        ).read_bytes()
    assert not (ext_create / "scripts").exists()
    assert not (ext_create / "templates").exists()
    assert (first / "hosts/codex/plugins/fab7/skills/ext-list/SKILL.md").is_file()
    assert (first / "hosts/codex/plugins/fab7/skills/ext-install/SKILL.md").is_file()
    codex_install = (first / "hosts/codex/plugins/fab7/skills/ext-install/SKILL.md").read_text()
    assert "--host codex" in codex_install
    assert "--host claude" not in codex_install
    codex_create = first / "hosts/codex/plugins/fab7/skills/ext-create"
    assert (codex_create / "SKILL.md").is_file()
    assert sorted(path.name for path in (codex_create / "references").iterdir()) == [
        "distribution.md",
        "ledger.md",
        "overview.md",
    ]
    for name in ("overview.md", "distribution.md", "ledger.md"):
        assert (codex_create / "references" / name).read_bytes() == (
            ROOT / "docs/architecture" / name
        ).read_bytes()


def test_builder_check_mode_is_clean() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "fab7.release_build", "--check"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "core")},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "deterministic" in process.stdout.lower()


def test_plugin_sources_have_one_shared_action_owner() -> None:
    assert not (ROOT / "scripts").exists()
    plugin_root = ROOT / "plugins/fab7"
    assert sorted(path.name for path in (plugin_root / "actions").iterdir()) == [
        "ext-create",
        "ext-install",
        "ext-list",
        "init",
    ]
    for action in ("init", "ext-create", "ext-list", "ext-install"):
        template = plugin_root / "actions" / action / "SKILL.md.tmpl"
        assert template.is_file()
        assert "{{invocation}}" in template.read_text()
    assert not (plugin_root / "shared").exists()
    assert not (plugin_root / "actions/ext-create/references").exists()
    assert not (plugin_root / "hosts").exists()
    assert not (ROOT / "plugins/claude").exists()
    assert not (ROOT / "plugins/codex").exists()

    for module in ("adapter.py", "build.py", "claude_adapter.py", "codex_adapter.py"):
        assert (ROOT / "core/fab7/plugin" / module).is_file()


def test_release_digest_tracks_injected_architecture_documents(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "core").mkdir(parents=True)
    shutil.copytree(ROOT / "core/fab7", source / "core/fab7")
    shutil.copytree(ROOT / "plugins/fab7", source / "plugins/fab7")
    shutil.copytree(ROOT / "docs/architecture", source / "docs/architecture")

    first = build_release(source, tmp_path / "first")
    overview = source / "docs/architecture/overview.md"
    overview.write_text(overview.read_text() + "\n")
    second = build_release(source, tmp_path / "second")

    assert first["source_sha256"] != second["source_sha256"]
    for host in ("claude", "codex"):
        built = tmp_path / f"second/hosts/{host}/plugins/fab7/skills/ext-create/references/overview.md"
        assert built.read_bytes() == overview.read_bytes()
