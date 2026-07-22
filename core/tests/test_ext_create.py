from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from fab7 import __version__
from fab7.errors import Fab7Error
from fab7.extension_package import build_extension_archive, extract_package_archive, validate_package
from fab7.extension_scaffold import create_extension_source


ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "plugins/fab7/actions/ext-create/SKILL.md.tmpl"
REFERENCES = ACTION.parent / "references"


def test_generic_scaffold_is_host_neutral_and_build_targets_are_explicit(tmp_path: Path) -> None:
    existing = tmp_path / "pyproject.toml"
    existing.write_text('[project]\nname = "retained"\n')

    result = create_extension_source(
        tmp_path,
        name="thread-check",
        publisher="fab7hq",
    )

    assert result["template"] == "basic"
    assert result["extension"] == {
        "name": "thread-check",
        "publisher": "fab7hq",
        "repository": "https://github.com/fab7hq/thread-check",
        "version": "0.1.0",
        "fab7_min": __version__,
        "fab7_max_exclusive": "0.3.0",
    }
    assert existing.read_text() == '[project]\nname = "retained"\n'
    assert result["test_command"] == ["python3", str(tmp_path / "tests/test_extension.py")]
    assert result["build_command_template"] == [
        "fab7",
        "ext",
        "build",
        str(tmp_path),
        "--host",
        "HOST",
        "--json",
    ]

    source = json.loads((tmp_path / "fab7-extension.json").read_text())
    assert (tmp_path / "fab7-extension.json").read_text() == (
        json.dumps(source, sort_keys=True, indent=2) + "\n"
    )
    assert source["schema"] == 2
    assert "hosts" not in source
    assert source["build"]["files"] == sorted(source["build"]["files"])
    assert source["build"]["entrypoint"] == "src/extension.py"
    assert source["build"]["skills"] == [
        {"name": "start", "source": "skills/start/SKILL.md"}
    ]
    assert not (tmp_path / "scripts").exists()
    assert not (tmp_path / "plugins").exists()

    generated_test = subprocess.run(
        result["test_command"],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert generated_test.returncode == 0, generated_test.stderr

    built = build_extension_archive(
        tmp_path,
        tmp_path / "thread-check-claude.zip",
        hosts=("claude",),
    )
    assert built["status"] == "built"
    assert built["hosts"] == ["claude"]
    package = extract_package_archive(
        (tmp_path / "thread-check-claude.zip").read_bytes(), tmp_path / "package"
    )
    manifest = validate_package(package)
    assert manifest["name"] == "thread-check"
    assert manifest["hosts"] == ["claude"]
    claude = package / "hosts/claude/plugins/thread-check/skills/start/SKILL.md"
    assert "disable-model-invocation: true" in claude.read_text()
    assert "/thread-check:start" in claude.read_text()
    assert not (package / "hosts/codex").exists()

    codex_built = build_extension_archive(
        tmp_path,
        tmp_path / "thread-check-codex.zip",
        hosts=("codex",),
    )
    assert codex_built["hosts"] == ["codex"]
    codex_package = extract_package_archive(
        (tmp_path / "thread-check-codex.zip").read_bytes(),
        tmp_path / "codex-package",
    )
    codex = codex_package / "hosts/codex/plugins/thread-check/skills/start/SKILL.md"
    assert "disable-model-invocation" not in codex.read_text()
    assert "$thread-check:start" in codex.read_text()
    assert not (codex_package / "hosts/claude").exists()


def test_generic_scaffold_rejects_conflicts_before_writing(tmp_path: Path) -> None:
    marker = tmp_path / "fab7-extension.json"
    marker.write_text("retained\n")

    with pytest.raises(Fab7Error) as raised:
        create_extension_source(
            tmp_path,
            name="thread-check",
            publisher="fab7hq",
        )

    assert raised.value.code == "FAB7_EXTENSION_CREATE_CONFLICT"
    assert marker.read_text() == "retained\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["fab7-extension.json"]


@pytest.mark.parametrize(
    "name,publisher",
    [
        ("Thread_Check", "fab7hq"),
        ("thread-check", "Fab7 HQ"),
    ],
)
def test_generic_scaffold_rejects_invalid_identity(
    tmp_path: Path,
    name: str,
    publisher: str,
) -> None:
    with pytest.raises(Fab7Error) as raised:
        create_extension_source(tmp_path, name=name, publisher=publisher)

    assert raised.value.code == "FAB7_EXTENSION_CREATE_INVALID"
    assert list(tmp_path.iterdir()) == []


def test_shared_skill_is_thin_and_keeps_progressive_architecture_guides() -> None:
    skill = ACTION.read_text()

    assert "disable-model-invocation: true" in skill
    assert "{{invocation}}" in skill
    assert "--host {{host}}" in skill
    create_section, build_section = skill.split("## Verify and install", 1)
    assert "fab7 ext create" in create_section
    assert "--host" not in create_section
    assert "fab7 ext build" in build_section
    assert "fab7 ext build <target> --host {{host}}" in build_section
    assert "scripts/scaffold.py" not in skill
    assert not REFERENCES.exists()
    assert "references/overview.md" in skill
    assert "references/distribution.md" in skill
    assert "references/ledger.md" in skill
    assert "github.com/fab7hq/fab7/blob/main/docs/architecture" not in skill
