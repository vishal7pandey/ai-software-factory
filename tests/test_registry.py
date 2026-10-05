"""The project registry lives outside the factory repo (Treaty 3.6, FACT-16).

These run the real CLI against the real kit, with the registry redirected into tmp_path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from swfactory import cli, common


@pytest.fixture
def proj(tmp_path) -> Path:
    p = tmp_path / "sample-app"
    p.mkdir()
    (p / "pyproject.toml").write_text('[project]\nname = "sample-app"\n', encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(p)], check=True)
    return p


def test_adopt_list_remove_with_env(tmp_path, monkeypatch, proj, capsys):
    reg = tmp_path / "r.yaml"
    monkeypatch.setenv("FACTORY_REGISTRY", str(reg))
    assert cli.main(["adopt", str(proj), "--tracker", "jira", "--jira-key", "PROJ"]) == 0
    data = common.load_yaml(reg)
    assert [p["name"] for p in data["projects"]] == ["sample-app"]
    assert data["paths"] == {"sample-app": str(proj.resolve())}

    capsys.readouterr()
    assert cli.main(["project", "list"]) == 0
    assert "sample-app" in capsys.readouterr().out

    assert cli.main(["adopt", str(proj)]) == 0  # re-adopt updates, never duplicates
    assert len(common.load_yaml(reg)["projects"]) == 1

    assert cli.main(["project", "remove", "sample-app"]) == 0
    data = common.load_yaml(reg)
    assert data["projects"] == [] and data["paths"] == {}


def test_remove_unknown_leaves_file_unchanged(tmp_path, monkeypatch, capsys):
    reg = tmp_path / "r.yaml"
    reg.write_text("projects: []\npaths: {}\n", encoding="utf-8")
    monkeypatch.setenv("FACTORY_REGISTRY", str(reg))
    before = reg.read_bytes()
    assert cli.main(["project", "remove", "nope"]) == 1
    assert "not registered" in capsys.readouterr().err
    assert reg.read_bytes() == before


def test_relative_env_resolves_against_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FACTORY_REGISTRY", "rel.yaml")
    assert common.registry_path() == (tmp_path / "rel.yaml").resolve()


def test_default_location_and_missing_file(tmp_path, monkeypatch, proj, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("FACTORY_REGISTRY", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    expected = home / ".factory" / "registry.yaml"
    assert common.registry_path() == expected

    assert cli.main(["project", "list"]) == 0  # no file: not an error
    assert "no registry yet" in capsys.readouterr().out
    assert not expected.exists()  # reading never creates it

    assert cli.main(["adopt", str(proj)]) == 0  # parent dir .factory/ is created on first write
    assert common.load_yaml(expected)["projects"][0]["name"] == "sample-app"


def test_unwritable_registry_is_an_error_after_the_kit_is_installed(
    tmp_path, monkeypatch, proj, capsys
):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, so nothing can be created below it\n", encoding="utf-8")
    bad = blocker / "sub" / "registry.yaml"
    monkeypatch.setenv("FACTORY_REGISTRY", str(bad))
    assert cli.main(["adopt", str(proj)]) == 1
    err = capsys.readouterr().err
    assert "cannot write the registry" in err and "registry.yaml" in err
    assert "Traceback" not in err
    assert (proj / ".factory" / "factory.yaml").is_file()  # the kit stayed installed


def test_repo_ships_a_neutral_example_registry():
    example = common.load_yaml(common.FACTORY_ROOT / "docs" / "registry.example.yaml")
    names = {p["name"] for p in example["projects"]}
    assert names and set(example["paths"]) <= names
