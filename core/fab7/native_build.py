"""One isolated uv and PyInstaller path for Fab7 native executables."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, Iterable

from .errors import Fab7Error
from .toolchain import (
    PYPI_INDEX,
    digest_file,
    digest_tree,
    provision_toolchain,
    run_tool,
    toolchain_roots,
    uv_environment,
)


BUILD_TIMEOUT = 300
SMOKE_TIMEOUT = 30
MAX_NATIVE_BYTES = 64 * 1024 * 1024
HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")


def build_native_executable(
    source_root: Path,
    entrypoint: Path,
    output: Path,
    *,
    name: str,
    home: Path,
    search_paths: Iterable[Path] = (),
    collect_data: Iterable[str] = (),
    data_files: Iterable[tuple[Path, str]] = (),
    extension_project: Path | None = None,
    smoke_args: Iterable[str] | None = None,
    uv_executable: str | Path | None = None,
) -> dict[str, Any]:
    """Build one native executable in a fresh environment and discard it."""

    source_root = source_root.resolve()
    entrypoint = entrypoint.resolve()
    if not source_root.is_dir() or not entrypoint.is_file() or entrypoint.is_symlink():
        raise Fab7Error("FAB7_NATIVE_BUILD_FAILED", "Native build source or entrypoint is invalid")
    roots = toolchain_roots(home)
    roots["builds"].mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        bundled_requirements = stack.enter_context(
            as_file(files("fab7").joinpath("build-requirements.txt"))
        )
        requirements = Path(bundled_requirements)
        toolchain = provision_toolchain(
            home,
            uv_executable=uv_executable,
            requirements=requirements,
        )
        task = Path(tempfile.mkdtemp(prefix="native-", dir=roots["builds"]))
        stack.callback(shutil.rmtree, task, True)
        builder = task / "builder" / ".venv"
        dependencies = task / "dependencies"
        work = task / "work"
        dist = task / "output"
        spec = task / "spec"
        config = task / "config"
        for path in (builder.parent, dependencies, work, dist, spec, config):
            path.mkdir(parents=True, exist_ok=True)
        environment = uv_environment(roots, pyinstaller_config=config)
        run_tool(
            [
                toolchain["uv"]["path"],
                "venv",
                str(builder),
                "--python",
                toolchain["python"]["path"],
                "--managed-python",
                "--no-python-downloads",
                "--no-project",
                "--no-config",
            ],
            environment,
            "FAB7_BUILD_ENVIRONMENT_FAILED",
            "Fab7 could not create the isolated builder environment",
        )
        builder_python = builder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run_tool(
            [
                toolchain["uv"]["path"],
                "pip",
                "install",
                "--python",
                str(builder_python),
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--default-index",
                PYPI_INDEX,
                "--index-strategy",
                "first-index",
                "--no-python-downloads",
                "--no-config",
                "-r",
                str(requirements),
            ],
            environment,
            "FAB7_BUILD_ENVIRONMENT_FAILED",
            "Fab7 could not synchronize the locked PyInstaller toolchain",
        )

        dependency_record: dict[str, Any] = {
            "lock_sha256": None,
            "requirements_sha256": None,
            "root_sha256": None,
            "hashes": [],
        }
        if extension_project is not None:
            dependency_record = _materialize_dependencies(
                extension_project.resolve(),
                dependencies,
                task,
                toolchain,
                environment,
            )

        command = [
            str(builder_python),
            "-m",
            "PyInstaller",
            "--onefile",
            "--clean",
            "--noupx",
            "--name",
            name,
            "--distpath",
            str(dist),
            "--workpath",
            str(work),
            "--specpath",
            str(spec),
        ]
        for path in search_paths:
            command.extend(["--paths", str(path.resolve())])
        if extension_project is not None:
            command.extend(["--paths", str(dependencies)])
        for package in collect_data:
            command.extend(["--collect-data", package])
        for path, destination in data_files:
            selected = path.resolve()
            if not selected.exists() or selected.is_symlink():
                raise Fab7Error(
                    "FAB7_NATIVE_BUILD_FAILED",
                    "Native build data input is missing or symlinked",
                )
            command.extend(["--add-data", f"{selected}:{destination}"])
        command.append(str(entrypoint))
        run_tool(
            command,
            environment,
            "FAB7_NATIVE_BUILD_FAILED",
            "PyInstaller could not build the native executable",
            cwd=source_root,
            timeout=BUILD_TIMEOUT,
        )
        built = dist / name
        if (
            built.is_symlink()
            or not built.is_file()
            or not os.access(built, os.X_OK)
            or built.stat().st_size > MAX_NATIVE_BYTES
            or len(list(dist.iterdir())) != 1
        ):
            raise Fab7Error("FAB7_NATIVE_BUILD_FAILED", "PyInstaller output is invalid")
        if smoke_args is not None:
            _smoke(built, tuple(smoke_args))
        if output.exists() or output.is_symlink():
            raise Fab7Error("FAB7_NATIVE_BUILD_FAILED", "Native executable output already exists")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.parent / f".{output.name}-{os.getpid()}"
        try:
            shutil.copyfile(built, temporary)
            temporary.chmod(0o755)
            os.replace(temporary, output)
        finally:
            if temporary.exists():
                temporary.unlink()
        return {
            "target": toolchain["target"],
            "toolchain": toolchain,
            "dependencies": dependency_record,
            "executable_sha256": digest_file(output),
        }


def _materialize_dependencies(
    project: Path,
    destination: Path,
    task: Path,
    toolchain: dict[str, Any],
    environment: dict[str, str],
) -> dict[str, Any]:
    pyproject = project / "pyproject.toml"
    lock = project / "uv.lock"
    if not pyproject.is_file() or pyproject.is_symlink() or not lock.is_file() or lock.is_symlink():
        raise Fab7Error(
            "FAB7_EXTENSION_DEPENDENCY_INVALID",
            "Extension pyproject.toml and uv.lock are required regular files",
        )
    run_tool(
        [
            toolchain["uv"]["path"],
            "lock",
            "--check",
            "--project",
            str(project),
            "--python",
            toolchain["python"]["path"],
            "--managed-python",
            "--no-python-downloads",
            "--no-config",
        ],
        environment,
        "FAB7_EXTENSION_LOCK_INVALID",
        "Extension uv.lock is missing, stale, or incompatible",
    )
    requirements = task / "extension-requirements.txt"
    run_tool(
        [
            toolchain["uv"]["path"],
            "export",
            "--project",
            str(project),
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--no-sources",
            "--no-header",
            "--output-file",
            str(requirements),
            "--no-python-downloads",
            "--no-config",
        ],
        environment,
        "FAB7_EXTENSION_LOCK_INVALID",
        "Fab7 could not export the locked extension dependency closure",
    )
    content = requirements.read_text()
    if content.strip():
        run_tool(
            [
                toolchain["uv"]["path"],
                "pip",
                "install",
                "--target",
                str(destination),
                "--python",
                toolchain["python"]["path"],
                "--require-hashes",
                "--no-deps",
                "--only-binary",
                ":all:",
                "--default-index",
                PYPI_INDEX,
                "--index-strategy",
                "first-index",
                "--no-python-downloads",
                "--no-config",
                "-r",
                str(requirements),
            ],
            environment,
            "FAB7_EXTENSION_DEPENDENCY_FAILED",
            "Fab7 could not materialize the locked extension wheels",
        )
    for direct_url in destination.rglob("direct_url.json"):
        raise Fab7Error(
            "FAB7_EXTENSION_DEPENDENCY_INVALID",
            f"Extension dependency uses a non-registry source: {direct_url.parent.name}",
        )
    hashes = sorted(set(HASH_RE.findall(content)))
    return {
        "lock_sha256": digest_file(lock),
        "requirements_sha256": digest_file(requirements),
        "root_sha256": digest_tree(destination),
        "hashes": [f"sha256:{value}" for value in hashes],
    }


def _smoke(executable: Path, arguments: tuple[str, ...]) -> None:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONNOUSERSITE": "1",
    }
    try:
        process = subprocess.run(
            [str(executable), *arguments],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=SMOKE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fab7Error("FAB7_NATIVE_SMOKE_FAILED", "Native executable smoke test could not run") from exc
    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()
        raise Fab7Error(
            "FAB7_NATIVE_SMOKE_FAILED",
            "Native executable smoke test failed",
            {"detail": detail[-2000:]},
        )
