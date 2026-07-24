"""Collision-safe source scaffolding for Fab7 extensions."""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from string import Template

from .. import __version__
from ..errors import Fab7Error
from ..install import fab7_home
from ..toolchain import (
    PYTHON_VERSION,
    provision_toolchain,
    run_tool,
    toolchain_roots,
    uv_environment,
)
from .package import parse_version, source_identity_from


TEMPLATE = "basic"


def create_extension_source(
    target: Path,
    *,
    name: str,
    publisher: str,
    version: str = "0.1.0",
    home: Path | None = None,
    uv_executable: str | Path | None = None,
) -> dict[str, object]:
    """Render the built-in source template without replacing existing files."""

    try:
        parse_version(version, "FAB7_EXTENSION_CREATE_INVALID", "Extension version")
        identity = source_identity_from(
            {
                "name": name,
                "publisher": publisher,
                "version": version,
            },
            "FAB7_EXTENSION_CREATE_INVALID",
        )
    except Fab7Error as exc:
        if exc.code == "FAB7_EXTENSION_CREATE_INVALID":
            raise
        raise Fab7Error("FAB7_EXTENSION_CREATE_INVALID", exc.message) from exc

    raw_target = target.expanduser()
    if raw_target.is_symlink() or not raw_target.is_dir():
        raise Fab7Error(
            "FAB7_EXTENSION_CREATE_INVALID",
            "Extension target must be an existing non-symlink directory",
        )
    target = raw_target.resolve()

    template_root = files("fab7").joinpath("templates", "extension")
    template_files = _template_files(template_root)
    source_files = sorted(
        [relative.removesuffix(".tmpl") for relative, _source in template_files]
        + ["uv.lock"]
    )
    values = {
        "display_name": " ".join(part.capitalize() for part in name.split("-")),
        "fab7_version": __version__,
        "name": name,
        "publisher": publisher,
        "version": version,
    }
    rendered: dict[Path, str] = {}
    for relative, source in template_files:
        output_relative = relative.removesuffix(".tmpl")
        destination = target.joinpath(*PurePosixPath(output_relative).parts)
        rendered[destination] = Template(source.read_text()).substitute(values)

    conflicts = sorted(
        relative
        for relative, path in {
            **{
                path.relative_to(target).as_posix(): path
                for path in rendered
            },
            "uv.lock": target / "uv.lock",
        }.items()
        if path.exists() or path.is_symlink()
    )
    if conflicts:
        raise Fab7Error(
            "FAB7_EXTENSION_CREATE_CONFLICT",
            "Refusing to overwrite existing extension files",
            {"paths": conflicts},
        )

    created: list[Path] = []
    lock_path = target / "uv.lock"
    try:
        for path, content in rendered.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(0o644)
            created.append(path)
        selected_home = home or fab7_home()
        toolchain = provision_toolchain(
            selected_home,
            uv_executable=uv_executable,
            install=False,
        )
        roots = toolchain_roots(selected_home)
        run_tool(
            [
                toolchain["uv"]["path"],
                "lock",
                "--project",
                str(target),
                "--python",
                toolchain["python"]["path"],
                "--managed-python",
                "--no-python-downloads",
                "--no-config",
            ],
            uv_environment(roots),
            "FAB7_EXTENSION_LOCK_FAILED",
            "Fab7 could not create the extension uv.lock",
        )
        lock = lock_path
        if lock.is_symlink() or not lock.is_file():
            raise Fab7Error(
                "FAB7_EXTENSION_LOCK_FAILED",
                "uv did not create the extension lock",
            )
        lock.chmod(0o644)
        created.append(lock)
    except Exception:
        if lock_path.is_file() and not lock_path.is_symlink():
            lock_path.unlink()
        for path in reversed(created):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        for directory in sorted(
            {path.parent for path in rendered if path.parent != target},
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    return {
        "ok": True,
        "status": "created",
        "template": TEMPLATE,
        "name": name,
        "target": str(target),
        "extension": {
            **identity,
            "repository": f"https://github.com/{publisher}/{name}",
        },
        "files": source_files,
        "test_command": [
            "uv",
            "run",
            "--isolated",
            "--locked",
            "--python",
            PYTHON_VERSION,
            "python",
            str(target / "tests/test_extension.py"),
        ],
        "build_command_template": [
            "fab7", "ext", "build", str(target), "--host", "HOST", "--json"
        ],
        "install_command_template": [
            "fab7", "ext", "install", "--local", str(target), "--host", "HOST", "--json"
        ],
        "next_action": f"Choose a target and run fab7 ext build {target} --host HOST --json",
    }


def _template_files(root: Traversable) -> list[tuple[str, Traversable]]:
    rows: list[tuple[str, Traversable]] = []

    def visit(current: Traversable, prefix: PurePosixPath) -> None:
        for child in sorted(current.iterdir(), key=lambda item: item.name):
            relative = prefix / child.name
            if child.is_dir():
                visit(child, relative)
            elif child.is_file() and child.name.endswith(".tmpl"):
                rows.append((relative.as_posix(), child))
            else:
                raise Fab7Error(
                    "FAB7_EXTENSION_CREATE_INVALID",
                    "Bundled extension template contains an unsupported entry",
                )

    if not root.is_dir():
        raise Fab7Error(
            "FAB7_EXTENSION_CREATE_INVALID",
            "Bundled extension template is missing",
        )
    visit(root, PurePosixPath())
    if not rows:
        raise Fab7Error(
            "FAB7_EXTENSION_CREATE_INVALID",
            "Bundled extension template is empty",
        )
    return rows
