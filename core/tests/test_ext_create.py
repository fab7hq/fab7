from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import fab7.extension.package as package_module
import fab7.extension.scaffold as scaffold_module
from fab7.errors import Fab7Error
from fab7.extension.package import (
    build_extension_archive,
    extract_package_archive,
    validate_package,
)
from fab7.extension.scaffold import create_extension_source


ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "plugins/fab7/actions/ext-create/SKILL.md.tmpl"
REFERENCES = ACTION.parent / "references"


@pytest.fixture(autouse=True)
def _fast_native_builder(monkeypatch: pytest.MonkeyPatch):
    empty = "sha256:" + "0" * 64

    def build(source_root: Path, entrypoint: Path, output: Path, **_kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' '{\"extension\": \"thread-check\", \"nested\": true}'\n"
        )
        output.chmod(0o755)
        return {
            "target": "macos-arm64-cpython-3.14.6",
            "toolchain": {"sha256": "sha256:" + "2" * 64},
            "dependencies": {
                "lock_sha256": "sha256:" + "3" * 64,
                "requirements_sha256": empty,
                "root_sha256": empty,
                "hashes": [],
            },
            "executable_sha256": (
                "sha256:"
                + __import__("hashlib").sha256(output.read_bytes()).hexdigest()
            ),
        }

    monkeypatch.setattr(package_module, "build_native_executable", build)
    monkeypatch.setattr(
        scaffold_module,
        "provision_toolchain",
        lambda *_args, **_kwargs: {
            "uv": {"path": "uv"},
            "python": {"path": "python3.14"},
        },
    )

    def lock(command, _environment, _code, _message):
        target = Path(command[command.index("--project") + 1])
        manifest = json.loads((target / "fab7-extension.json").read_text())
        (target / "uv.lock").write_text(
            "version = 1\n"
            "revision = 3\n"
            'requires-python = "==3.14.*"\n'
            "\n"
            "[[package]]\n"
            f'name = "{manifest["name"]}"\n'
            f'version = "{manifest["version"]}"\n'
            'source = { virtual = "." }\n'
        )

    monkeypatch.setattr(scaffold_module, "run_tool", lock)


def test_generic_scaffold_is_host_neutral_and_build_targets_are_explicit(tmp_path: Path) -> None:

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
    }
    assert result["test_command"] == [
        "uv",
        "run",
        "--isolated",
        "--locked",
        "--python",
        "3.14.6",
        "python",
        str(tmp_path / "tests/test_extension.py"),
    ]
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
    assert source == {
        "name": "thread-check",
        "publisher": "fab7hq",
        "schema": 1,
        "version": "0.1.0",
    }
    assert (tmp_path / "pyproject.toml").read_text() == (
        "[project]\n"
        'name = "thread-check"\n'
        'version = "0.1.0"\n'
        'requires-python = "==3.14.*"\n'
        "dependencies = []\n"
    )
    assert 'requires-python = "==3.14.*"' in (tmp_path / "uv.lock").read_text()
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

    package_root = tmp_path / "src/thread_check"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("")
    (package_root / "cli.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "import subprocess\n"
        "\n"
        "\n"
        "def main() -> int:\n"
        "    process = subprocess.run(\n"
        "        ['fab7', '--version'], text=True, capture_output=True, check=False\n"
        "    )\n"
        "    print(json.dumps({'extension': 'thread-check', 'nested': True}))\n"
        "    return process.returncode\n"
    )
    (tmp_path / "src/extension.py").write_text(
        "#!/usr/bin/env python3\n"
        "from thread_check.cli import main\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )
    (tmp_path / "tests/test_nested.py").write_text(
        "def test_nested_source_is_discovered() -> None:\n"
        "    assert True\n"
    )
    reference = tmp_path / "skills/start/references/usage.md"
    reference.parent.mkdir()
    reference.write_text("# Usage\n")

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
    assert set(json.loads((package / "extension.json").read_text())) == {
        "schema",
        "name",
        "publisher",
        "version",
        "fab7_api",
        "hosts",
        "build",
        "files",
    }
    assert manifest["name"] == "thread-check"
    assert manifest["hosts"] == ["claude"]
    assert manifest["fab7_api"] == 1
    assert "capabilities" not in manifest
    assert "fab7_min" not in manifest
    assert "fab7_max_exclusive" not in manifest
    claude = package / "hosts/claude/plugins/thread-check/skills/start/SKILL.md"
    assert "disable-model-invocation: true" in claude.read_text()
    assert "/thread-check:start" in claude.read_text()
    assert (
        package / "hosts/claude/plugins/thread-check/skills/start/references/usage.md"
    ).read_text() == "# Usage\n"
    assert not (package / "hosts/codex").exists()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_fab7 = fake_bin / "fab7"
    fake_fab7.write_text("#!/bin/sh\nexit 0\n")
    fake_fab7.chmod(0o755)
    executable = subprocess.run(
        [str(package / "bin/thread-check")],
        env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert executable.returncode == 0, executable.stderr
    assert json.loads(executable.stdout) == {
        "extension": "thread-check",
        "nested": True,
    }

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
    codex_plugin = json.loads(
        (
            codex_package
            / "hosts/codex/plugins/thread-check/.codex-plugin/plugin.json"
        ).read_text()
    )
    assert "capabilities" not in codex_plugin["interface"]
    assert (
        codex_package / "hosts/codex/plugins/thread-check/skills/start/references/usage.md"
    ).read_text() == "# Usage\n"
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
