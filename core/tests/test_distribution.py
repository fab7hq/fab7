from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from fab7 import __version__
from fab7.errors import Fab7Error
from fab7.install import init_project, validate_project


ROOT = Path(__file__).resolve().parents[2]


def _run_installer(
    test_home: Path,
    source: Path = ROOT,
    *,
    command_path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "HOME": str(test_home),
        "SHELL": "/bin/zsh",
        "VIRTUAL_ENV": "/ambient/venv",
        "PYTHONHOME": "/ambient/python-home",
        "PYTHONPATH": "/ambient/python-path",
        "PIP_INDEX_URL": "https://private.example/simple",
        "UV_INDEX_URL": "https://private.example/simple",
        "UV_CONFIG_FILE": "/ambient/uv.toml",
    }
    if command_path is not None:
        environment["PATH"] = command_path
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


def _copy_build_source(target: Path, version: str = __version__) -> Path:
    (target / "core").mkdir(parents=True)
    shutil.copytree(ROOT / "core/fab7", target / "core/fab7")
    shutil.copytree(ROOT / "plugins", target / "plugins")
    shutil.copytree(ROOT / "docs/architecture", target / "docs/architecture")
    shutil.copyfile(ROOT / "pyproject.toml", target / "pyproject.toml")
    shutil.copyfile(ROOT / "uv.lock", target / "uv.lock")
    if version != __version__:
        init = target / "core/fab7/__init__.py"
        init.write_text(init.read_text().replace(f'"{__version__}"', f'"{version}"'))
    return target


def test_installer_is_idempotent_and_updates_path_after_success(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()

    first = _run_installer(test_home)
    assert first.returncode == 0, first.stderr
    profile = test_home / ".zshrc"
    first_profile = profile.read_text()
    assert first_profile.count("# >>> fab7 >>>") == 1
    assert list(sorted(path.name for path in (test_home / ".fab7").iterdir())) == [
        "bin",
        "builds",
        "cache",
        "runtime",
        "toolchains",
    ]
    assert not (test_home / ".local").exists()

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
    assert version.stdout.strip() == __version__


def test_failed_build_does_not_mutate_install_or_profile(tmp_path: Path) -> None:
    source = _copy_build_source(tmp_path / "source")
    action = source / "plugins/fab7/actions/init/SKILL.md.tmpl"
    action.write_text(action.read_text() + "{{unknown}}\n")
    test_home = tmp_path / "user"
    test_home.mkdir()
    profile = test_home / ".zshrc"
    profile.write_text("unchanged\n")

    failed = _run_installer(test_home, source)
    assert failed.returncode != 0
    assert profile.read_text() == "unchanged\n"
    assert not (test_home / ".fab7/bin").exists()
    assert not (test_home / ".fab7/runtime").exists()
    assert (test_home / ".fab7/toolchains/python").is_dir()
    assert (test_home / ".fab7/cache/uv").is_dir()


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


def test_installer_rejects_missing_uv_before_mutation(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()
    process = subprocess.run(
        [
            "/bin/bash",
            str(ROOT / "install.sh"),
            "--source",
            str(ROOT),
            "--fab7-home",
            str(test_home / ".fab7"),
            "--profile",
            str(test_home / ".zshrc"),
        ],
        cwd=ROOT,
        env={
            "HOME": str(test_home),
            "PATH": "/usr/bin:/bin",
            "SHELL": "/bin/zsh",
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode != 0
    assert "requires uv on PATH" in process.stderr
    assert not (test_home / ".fab7").exists()
    assert not (test_home / ".zshrc").exists()


def test_installer_rejects_invalid_uv_before_mutation(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text("#!/bin/sh\nprintf 'uv development\\n'\n")
    uv.chmod(0o755)

    process = subprocess.run(
        [
            "/bin/bash",
            str(ROOT / "install.sh"),
            "--source",
            str(ROOT),
            "--fab7-home",
            str(test_home / ".fab7"),
            "--profile",
            str(test_home / ".zshrc"),
        ],
        cwd=ROOT,
        env={
            "HOME": str(test_home),
            "PATH": f"{tools}:/usr/bin:/bin",
            "SHELL": "/bin/zsh",
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode != 0
    assert "invalid uv --version response" in process.stderr
    assert not (test_home / ".fab7").exists()
    assert not (test_home / ".zshrc").exists()


def test_installer_accepts_nonrecommended_uv_version(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    actual_uv = shutil.which("uv")
    assert actual_uv is not None
    wrapper = tools / "uv"
    wrapper.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"--version\" ]; then\n"
        "  printf 'uv 99.0.0\\n'\n"
        "  exit 0\n"
        "fi\n"
        f"exec {shlex.quote(str(Path(actual_uv).resolve()))} \"$@\"\n"
    )
    wrapper.chmod(0o755)

    process = _run_installer(
        test_home,
        command_path=f"{tools}:{os.environ['PATH']}",
    )

    assert process.returncode == 0, process.stderr
    assert "tested with uv 0.11.29; continuing with uv 99.0.0" in process.stderr
    manifest = json.loads(
        (test_home / ".fab7/runtime/0.4.0/manifest.json").read_text()
    )
    assert manifest["toolchain"]["uv"]["version"] == "99.0.0"


def test_profile_failure_restores_selection_and_removes_new_release(tmp_path: Path) -> None:
    test_home = tmp_path / "user"
    test_home.mkdir()
    assert _run_installer(test_home).returncode == 0
    selector = test_home / ".fab7/bin/fab7"
    prior_target = os.readlink(selector)
    profile = test_home / ".zshrc"
    profile.write_text(profile.read_text().replace("# <<< fab7 <<<", "# malformed fab7 end"))
    malformed = profile.read_text()
    major, minor, patch = (int(part) for part in __version__.split("."))
    next_version = f"{major}.{minor}.{patch + 1}"
    next_source = _copy_build_source(tmp_path / "next-source", next_version)

    failed = _run_installer(test_home, next_source)
    assert failed.returncode != 0
    assert os.readlink(selector) == prior_target
    assert profile.read_text() == malformed
    assert not (test_home / ".fab7/runtime" / next_version).exists()


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
