from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from fab7.errors import Fab7Error
from fab7.install import init_project, validate_project


ROOT = Path(__file__).resolve().parents[2]


def _run_installer(test_home: Path, source: Path = ROOT) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "HOME": str(test_home),
        "SHELL": "/bin/zsh",
    }
    return subprocess.run(
        [
            "bash",
            str(ROOT / "install.sh"),
            "--source",
            str(source),
            "--fab7-home",
            str(test_home / ".fab7"),
            "--profile",
            str(test_home / ".zshrc"),
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _copy_build_source(target: Path, version: str = "0.1.0") -> Path:
    (target / "core").mkdir(parents=True)
    shutil.copytree(ROOT / "core/fab7", target / "core/fab7")
    shutil.copytree(ROOT / "scripts", target / "scripts")
    shutil.copytree(ROOT / "plugins", target / "plugins")
    if version != "0.1.0":
        init = target / "core/fab7/__init__.py"
        init.write_text(init.read_text().replace('"0.1.0"', f'"{version}"'))
        for manifest in (
            target / "plugins/claude/fab7/.claude-plugin/plugin.json",
            target / "plugins/codex/fab7/.codex-plugin/plugin.json",
        ):
            data = json.loads(manifest.read_text())
            data["version"] = version
            manifest.write_text(json.dumps(data, indent=2) + "\n")
    return target


def test_installer_is_idempotent_and_updates_path_after_success(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()

    first = _run_installer(test_home)
    assert first.returncode == 0, first.stderr
    profile = test_home / ".zshrc"
    first_profile = profile.read_text()
    assert first_profile.count("# >>> fab7 >>>") == 1
    assert list(sorted(path.name for path in (test_home / ".fab7").iterdir())) == ["bin", "runtime"]

    second = _run_installer(test_home)
    assert second.returncode == 0, second.stderr
    assert profile.read_text() == first_profile
    executable = test_home / ".fab7/bin/fab7"
    assert executable.is_symlink()
    version = subprocess.run(
        [str(executable), "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert version.returncode == 0
    assert version.stdout.strip() == "0.1.0"


def test_failed_build_does_not_mutate_install_or_profile(tmp_path: Path) -> None:
    source = _copy_build_source(tmp_path / "source")
    manifest = source / "plugins/claude/fab7/.claude-plugin/plugin.json"
    data = json.loads(manifest.read_text())
    data["version"] = "9.9.9"
    manifest.write_text(json.dumps(data) + "\n")
    test_home = tmp_path / "user"
    test_home.mkdir()
    profile = test_home / ".zshrc"
    profile.write_text("unchanged\n")

    failed = _run_installer(test_home, source)
    assert failed.returncode != 0
    assert profile.read_text() == "unchanged\n"
    assert not (test_home / ".fab7").exists()


def test_installer_rejects_empty_fab7_home(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()
    process = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--source", str(ROOT), "--profile", str(test_home / ".zshrc")],
        cwd=ROOT,
        env={**os.environ, "HOME": str(test_home), "SHELL": "/bin/zsh", "FAB7_HOME": ""},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode != 0
    assert "must not be empty" in process.stderr
    assert not (test_home / ".zshrc").exists()


def test_profile_failure_restores_selection_and_removes_new_release(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()
    assert _run_installer(test_home).returncode == 0
    selector = test_home / ".fab7/bin/fab7"
    prior_target = os.readlink(selector)
    profile = test_home / ".zshrc"
    profile.write_text(profile.read_text().replace("# <<< fab7 <<<", "# malformed fab7 end"))
    malformed = profile.read_text()
    next_source = _copy_build_source(tmp_path / "next-source", "0.1.1")

    failed = _run_installer(test_home, next_source)
    assert failed.returncode != 0
    assert os.readlink(selector) == prior_target
    assert profile.read_text() == malformed
    assert not (test_home / ".fab7/runtime/0.1.1").exists()


def test_project_init_creates_pin_and_repairs_binary(repo: Path, fab7_home: Path) -> None:
    records = repo / ".fab7/records"
    records.mkdir(parents=True)
    retained = records / "retained.jsonl"
    retained.write_text("")

    result = init_project(repo)
    assert result["status"] == "initialized"
    assert retained.exists()
    assert (repo / ".fab7/.gitignore").read_text() == "/bin/\n"
    project = json.loads((repo / ".fab7/project.json").read_text())
    assert set(project) == {"schema", "fab7_version", "executable_sha256"}
    local = repo / ".fab7/bin/fab7"
    assert local.is_file() and not local.is_symlink()
    validate_project(repo)

    local.unlink()
    repaired = init_project(repo)
    assert repaired["status"] == "repaired"
    assert local.is_file()
    assert retained.exists()


def test_global_command_dispatches_to_project_binary(repo: Path, fab7_home: Path) -> None:
    global_fab7 = fab7_home / "bin/fab7"
    initialized = subprocess.run(
        [str(global_fab7), "init", "--json"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout)["status"] == "initialized"

    claimed = subprocess.run(
        [str(global_fab7), "claim", "--work-item", "work-1", "--summary", "Done", "--json"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert claimed.returncode == 0, claimed.stderr
    assert json.loads(claimed.stdout)["record"]["work_item"] == "work-1"

    local = repo / ".fab7/bin/fab7"
    local.write_bytes(b"corrupt")
    rejected_environment = {**os.environ, "FAB7_PROJECT_DISPATCHED": "1"}
    rejected = subprocess.run(
        [str(global_fab7), "doctor", "--json"],
        cwd=repo,
        env=rejected_environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["errors"][0]["code"] == "FAB7_PROJECT_EXECUTABLE_INVALID"


def test_existing_project_manifest_is_closed(repo: Path, fab7_home: Path) -> None:
    init_project(repo)
    path = repo / ".fab7/project.json"
    data = json.loads(path.read_text())
    data["unexpected"] = True
    path.write_text(json.dumps(data) + "\n")

    with pytest.raises(Fab7Error, match="FAB7_PROJECT_PIN_INVALID"):
        init_project(repo)
