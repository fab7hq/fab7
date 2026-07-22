from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from fab7 import __version__


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts" / "build_zipapp.py"


def _build(target: Path) -> None:
    process = subprocess.run(
        [sys.executable, str(BUILDER), "--release-root", str(target)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode == 0, process.stderr


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

    manifest = json.loads((first / "manifest.json").read_text())
    assert set(manifest) == {
        "schema", "name", "version", "source_sha256", "executable_sha256", "python"
    }
    assert manifest["executable_sha256"] == "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    assert (first / "hosts/claude/.claude-plugin/marketplace.json").is_file()
    assert (first / "hosts/codex/.agents/plugins/marketplace.json").is_file()
    assert (first / "hosts/claude/plugins/fab7/commands/ext-list.md").is_file()
    assert (first / "hosts/claude/plugins/fab7/commands/ext-install.md").is_file()
    assert (first / "hosts/codex/plugins/fab7/skills/ext-list/SKILL.md").is_file()
    assert (first / "hosts/codex/plugins/fab7/skills/ext-install/SKILL.md").is_file()


def test_builder_check_mode_is_clean() -> None:
    process = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "deterministic" in process.stdout.lower()
