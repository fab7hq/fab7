from __future__ import annotations

import copy
import base64
import json
from pathlib import Path

import pytest

from fab7.cli import main
from fab7.errors import Fab7Error
from fab7.extensions import catalog_listing, extension_doctor, load_catalog, refresh_catalog


def _catalog(*extensions: dict[str, object]) -> dict[str, object]:
    return {
        "schema": 1,
        "registry": "fab7hq/ext-registry",
        "catalog_version": "0.1.0",
        "extensions": list(extensions),
    }


def _denim() -> dict[str, object]:
    return {
        "name": "denim",
        "publisher": "fab7hq",
        "repository": "https://github.com/fab7hq/denim",
        "version": "0.1.0",
        "fab7_min": "0.1.0",
        "fab7_max_exclusive": "0.2.0",
        "executable": "denim",
        "capabilities": ["project-workflow"],
        "hosts": ["claude", "codex"],
        "artifact": {
            "url": "https://github.com/fab7hq/denim/releases/download/v0.1.0/denim-0.1.0.tar.gz",
            "sha256": "sha256:" + "a" * 64,
        },
    }


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, indent=2) + "\n")
    return path


def test_empty_catalog_is_valid_json_compatible_yaml(tmp_path: Path) -> None:
    path = _write(tmp_path / "catalog.yaml", _catalog())

    catalog = load_catalog(path)
    listing = catalog_listing(path)

    assert catalog["extensions"] == []
    assert listing == {
        "ok": True,
        "catalog": str(path.resolve()),
        "catalog_version": "0.1.0",
        "registry": "fab7hq/ext-registry",
        "count": 0,
        "extensions": [],
    }


def test_catalog_accepts_one_closed_immutable_extension_entry(tmp_path: Path) -> None:
    path = _write(tmp_path / "catalog.yaml", _catalog(_denim()))

    listing = catalog_listing(path)

    assert listing["count"] == 1
    assert listing["extensions"][0]["name"] == "denim"


def test_ext_list_is_global_and_deterministic(tmp_path: Path, monkeypatch, capsys) -> None:
    path = _write(tmp_path / "catalog.yaml", _catalog(_denim()))
    monkeypatch.chdir(tmp_path)

    assert main(["ext", "list", "--catalog", str(path), "--json"]) == 0
    first = capsys.readouterr().out
    assert main(["ext", "list", "--catalog", str(path), "--json"]) == 0
    second = capsys.readouterr().out

    assert first == second
    assert json.loads(first)["extensions"][0]["version"] == "0.1.0"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"schema": 2}),
        lambda value: value.update({"registry": "other/registry"}),
        lambda value: value.update({"catalog_version": "1"}),
        lambda value: value.update({"unknown": True}),
        lambda value: value["extensions"][0].update({"source": "../denim"}),
        lambda value: value["extensions"][0]["artifact"].update({"unknown": True}),
        lambda value: value["extensions"][0].update({"publisher": "other"}),
        lambda value: value["extensions"][0].update({"executable": "other"}),
        lambda value: value["extensions"][0].update({"fab7_max_exclusive": "0.1.0"}),
        lambda value: value["extensions"][0].update({"capabilities": ["z", "a"]}),
        lambda value: value["extensions"][0].update({"hosts": ["codex", "claude"]}),
        lambda value: value["extensions"][0].update({"hosts": ["unknown"]}),
        lambda value: value["extensions"][0].update({"version": "01.0.0"}),
        lambda value: value["extensions"][0].update({"version": "1" * 5000 + ".0.0"}),
        lambda value: value["extensions"][0].update({"repository": "https://github.com/fab7hq/denim/"}),
        lambda value: value["extensions"][0].update({"repository": "https://[invalid"}),
        lambda value: value["extensions"][0].update(
            {"artifact": {"url": "https://github.com/fab7hq/denim/releases/latest/download/denim.tar.gz", "sha256": "sha256:" + "a" * 64}}
        ),
        lambda value: value["extensions"][0].update(
            {"artifact": {"url": "https://github.com/fab7hq/denim/releases/download/v0.1.0/path/denim.tar.gz", "sha256": "sha256:" + "a" * 64}}
        ),
        lambda value: value["extensions"][0].update(
            {"artifact": {"url": "https://[invalid", "sha256": "sha256:" + "a" * 64}}
        ),
        lambda value: value["extensions"][0]["artifact"].update({"sha256": "sha256:invalid"}),
    ],
)
def test_catalog_rejects_noncanonical_or_open_shapes(tmp_path: Path, mutate) -> None:
    value = _catalog(_denim())
    mutate(value)
    path = _write(tmp_path / "catalog.yaml", value)

    with pytest.raises(Fab7Error, match="FAB7_CATALOG_INVALID"):
        load_catalog(path)


def test_catalog_rejects_duplicate_keys_and_yaml_only_syntax(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        '{"schema":1,"schema":1,"registry":"fab7hq/ext-registry",'
        '"catalog_version":"0.1.0","extensions":[]}\n'
    )
    yaml_only = tmp_path / "yaml-only.yaml"
    yaml_only.write_text(
        "schema: 1\nregistry: fab7hq/ext-registry\ncatalog_version: 0.1.0\nextensions: []\n"
    )

    for path in (duplicate, yaml_only):
        with pytest.raises(Fab7Error, match="FAB7_CATALOG_INVALID"):
            load_catalog(path)


def test_catalog_rejects_duplicate_or_unsorted_extensions(tmp_path: Path) -> None:
    denim = _denim()
    canvas = copy.deepcopy(denim)
    canvas.update(
        {
            "name": "canvas",
            "repository": "https://github.com/fab7hq/canvas",
            "executable": "canvas",
            "artifact": {
                "url": "https://github.com/fab7hq/canvas/releases/download/v0.1.0/canvas-0.1.0.tar.gz",
                "sha256": "sha256:" + "b" * 64,
            },
        }
    )

    for value in (_catalog(denim, canvas), _catalog(denim, denim)):
        path = _write(tmp_path / f"catalog-{len(list(tmp_path.iterdir()))}.yaml", value)
        with pytest.raises(Fab7Error, match="FAB7_CATALOG_INVALID"):
            load_catalog(path)


def test_catalog_rejects_symlink_and_oversized_input(tmp_path: Path) -> None:
    target = _write(tmp_path / "target.yaml", _catalog())
    link = tmp_path / "catalog.yaml"
    link.symlink_to(target)
    oversized = tmp_path / "oversized.yaml"
    oversized.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(Fab7Error, match="FAB7_CATALOG_MISSING"):
        load_catalog(link)
    with pytest.raises(Fab7Error, match="FAB7_CATALOG_INVALID"):
        load_catalog(oversized)


def test_refresh_retains_immutable_source_and_preserves_last_known_good(tmp_path: Path) -> None:
    home = tmp_path / ".fab7"
    first = json.dumps(_catalog(), indent=2).encode() + b"\n"

    def response(content: bytes, sha: str) -> bytes:
        return json.dumps(
            {
                "type": "file",
                "encoding": "base64",
                "size": len(content),
                "sha": sha,
                "content": base64.encodebytes(content).decode(),
            }
        ).encode()

    result = refresh_catalog(
        home=home,
        fetcher=lambda _url, _limit: response(first, "a" * 40),
    )

    assert result["status"] == "refreshed"
    assert (home / "catalog.yaml").read_bytes() == first
    lock = json.loads((home / "catalog.lock.json").read_text())
    assert lock["blob_sha"] == "a" * 40

    changed_same_version = json.dumps({**_catalog(), "extensions": [_denim()]}).encode()
    with pytest.raises(Fab7Error, match="FAB7_CATALOG_ROLLBACK"):
        refresh_catalog(
            home=home,
            fetcher=lambda _url, _limit: response(changed_same_version, "b" * 40),
        )

    assert (home / "catalog.yaml").read_bytes() == first
    assert json.loads((home / "catalog.lock.json").read_text())["blob_sha"] == "a" * 40

    lock["content_sha256"] = "sha256:" + "0" * 64
    (home / "catalog.lock.json").write_text(json.dumps(lock) + "\n")
    diagnosis = extension_doctor(home=home)
    assert diagnosis["ok"] is False
    assert diagnosis["errors"][-1]["code"] == "FAB7_CATALOG_INVALID"
