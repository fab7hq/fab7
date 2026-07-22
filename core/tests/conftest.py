from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from fab7 import __version__


ROOT = Path(__file__).resolve().parents[2]


def git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Fab7 Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "app.py").write_text("VALUE = 1\n")
    git(tmp_path, "add", "app.py")
    git(tmp_path, "commit", "-qm", "baseline")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def fab7_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path_factory.mktemp("fab7-home") / ".fab7"
    release = home / "runtime" / __version__
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_zipapp.py"), "--release-root", str(release)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    (home / "bin").mkdir(parents=True)
    (home / "bin" / "fab7").symlink_to(Path(f"../runtime/{__version__}/bin/fab7"))
    monkeypatch.setenv("FAB7_HOME", str(home))
    return home
