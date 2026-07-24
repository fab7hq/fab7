from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from fab7.errors import Fab7Error
from fab7.toolchain import (
    PYINSTALLER_HOOKS_VERSION,
    PYINSTALLER_VERSION,
    PYTHON_VERSION,
    RECOMMENDED_UV_VERSION,
    native_target,
    python_environment,
    require_uv,
    toolchain_roots,
    uv_environment,
)


ROOT = Path(__file__).resolve().parents[2]


def test_toolchain_recommendation_and_pins_match_all_surfaces() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    requirements = (ROOT / "core/fab7/build-requirements.txt").read_text()
    installer = (ROOT / "install.sh").read_text()
    workflow = (ROOT / ".github/workflows/ci.yaml").read_text()

    assert project["project"]["requires-python"] == f"=={PYTHON_VERSION.rsplit('.', 1)[0]}.*"
    assert "uv" not in project["tool"]
    assert (
        project["tool"]["fab7"]["recommended-uv-version"]
        == RECOMMENDED_UV_VERSION
    )
    assert project["dependency-groups"]["build"] == [f"pyinstaller=={PYINSTALLER_VERSION}"]
    assert (ROOT / ".python-version").read_text() == f"{PYTHON_VERSION}\n"
    assert f'fab7_recommended_uv="{RECOMMENDED_UV_VERSION}"' in installer
    assert f'fab7_required_python="{PYTHON_VERSION}"' in installer
    assert f'version: "{RECOMMENDED_UV_VERSION}"' in workflow
    assert f"uv sync --python {PYTHON_VERSION} --locked" in workflow
    assert f"pyinstaller=={PYINSTALLER_VERSION}" in requirements
    assert f"pyinstaller-hooks-contrib=={PYINSTALLER_HOOKS_VERSION}" in requirements
    assert "--hash=sha256:" in requirements


def test_toolchain_environments_drop_ambient_python_and_uv_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "/ambient/venv")
    monkeypatch.setenv("PYTHONPATH", "/ambient/python")
    monkeypatch.setenv("UV_INDEX_URL", "https://private.example/simple")
    monkeypatch.setenv("PIP_INDEX_URL", "https://private.example/simple")
    monkeypatch.setenv("UV_CONFIG_FILE", "/ambient/uv.toml")
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    roots = toolchain_roots(tmp_path / ".fab7")

    uv_env = uv_environment(roots, pyinstaller_config=tmp_path / "pyinstaller")
    python_env = python_environment()

    for name in (
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "UV_INDEX_URL",
        "PIP_INDEX_URL",
        "UV_CONFIG_FILE",
    ):
        assert name not in uv_env
        assert name not in python_env
    assert uv_env["UV_CACHE_DIR"] == str(tmp_path / ".fab7/cache/uv")
    assert uv_env["UV_PYTHON_INSTALL_DIR"] == str(tmp_path / ".fab7/toolchains/python")
    assert uv_env["UV_PYTHON_INSTALL_BIN"] == "0"
    assert uv_env["UV_PYTHON_DOWNLOADS"] == "never"
    assert uv_env["PYINSTALLER_CONFIG_DIR"] == str(tmp_path / "pyinstaller")
    assert uv_env["HOME"] == str(tmp_path / "user")


def test_require_uv_accepts_nonrecommended_version(tmp_path: Path) -> None:
    executable = tmp_path / "uv"
    executable.write_text("#!/bin/sh\nprintf 'uv 0.0.1\\n'\n")
    executable.chmod(0o755)

    selected = require_uv(executable)

    assert selected["version"] == "0.0.1"
    assert selected["path"] == str(executable)


def test_require_uv_rejects_invalid_version_output(tmp_path: Path) -> None:
    executable = tmp_path / "uv"
    executable.write_text("#!/bin/sh\nprintf 'uv development\\n'\n")
    executable.chmod(0o755)

    with pytest.raises(Fab7Error, match="FAB7_UV_INVALID"):
        require_uv(executable)


def test_require_uv_rejects_missing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")

    with pytest.raises(Fab7Error, match="FAB7_UV_MISSING"):
        require_uv()


def test_native_target_is_closed_to_supported_platforms() -> None:
    assert (
        native_target({"platform": "darwin", "architecture": "arm64"})
        == f"macos-arm64-cpython-{PYTHON_VERSION}"
    )
    assert (
        native_target({"platform": "linux", "architecture": "x86_64"})
        == f"linux-x86_64-cpython-{PYTHON_VERSION}"
    )
    with pytest.raises(Fab7Error, match="FAB7_TARGET_UNSUPPORTED"):
        native_target({"platform": "windows", "architecture": "x86_64"})


def test_fab7_home_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "home"
    os.symlink(target, link)

    with pytest.raises(Fab7Error, match="FAB7_HOME_INVALID"):
        toolchain_roots(link)
