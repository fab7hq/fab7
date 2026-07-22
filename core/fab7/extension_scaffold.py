"""Collision-safe source scaffolding for Fab7 extensions."""

from __future__ import annotations

import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from string import Template

from . import __version__
from .errors import Fab7Error
from .extension_package import parse_version, source_identity_from


TEMPLATE = "basic"


def create_extension_source(
    target: Path,
    *,
    name: str,
    publisher: str,
    version: str = "0.1.0",
    fab7_min: str = __version__,
) -> dict[str, object]:
    """Render the built-in source template without replacing existing files."""

    try:
        major, minor, _patch = parse_version(
            fab7_min,
            "FAB7_EXTENSION_CREATE_INVALID",
            "Fab7 minimum",
        )
        parse_version(version, "FAB7_EXTENSION_CREATE_INVALID", "Extension version")
        fab7_max_exclusive = f"{major}.{minor + 1}.0"
        identity = source_identity_from(
            {
                "name": name,
                "publisher": publisher,
                "repository": f"https://github.com/{publisher}/{name}",
                "version": version,
                "fab7_min": fab7_min,
                "fab7_max_exclusive": fab7_max_exclusive,
                "executable": name,
                "capabilities": ["sample"],
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
    source_files = sorted(relative.removesuffix(".tmpl") for relative, _source in template_files)
    values = {
        "display_name": " ".join(part.capitalize() for part in name.split("-")),
        "fab7_max_exclusive": fab7_max_exclusive,
        "fab7_min": fab7_min,
        "name": name,
        "publisher": publisher,
        "repository": identity["repository"],
        "source_files_json": json.dumps(source_files, indent=2).replace("\n", "\n    "),
        "version": version,
    }
    rendered: dict[Path, str] = {}
    for relative, source in template_files:
        output_relative = relative.removesuffix(".tmpl")
        destination = target.joinpath(*PurePosixPath(output_relative).parts)
        rendered[destination] = Template(source.read_text()).substitute(values)

    conflicts = sorted(
        path.relative_to(target).as_posix()
        for path in rendered
        if path.exists() or path.is_symlink()
    )
    if conflicts:
        raise Fab7Error(
            "FAB7_EXTENSION_CREATE_CONFLICT",
            "Refusing to overwrite existing extension files",
            {"paths": conflicts},
        )

    for path, content in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o644)

    return {
        "ok": True,
        "status": "created",
        "template": TEMPLATE,
        "name": name,
        "target": str(target),
        "extension": {
            field: identity[field]
            for field in (
                "name",
                "publisher",
                "repository",
                "version",
                "fab7_min",
                "fab7_max_exclusive",
            )
        },
        "files": source_files,
        "test_command": ["python3", str(target / "tests/test_extension.py")],
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
