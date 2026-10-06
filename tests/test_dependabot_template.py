"""Tests for the kit's `dependabot.yml` generator (FACT-39, AC3 and the template part of AC6).

The generator reads the REAL kit files, so editing a fragment (schedule, grouping, limit) or the
manifest registration breaks these tests. Projects are tiny scratch directories; nothing here
reaches the network.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from swfactory import checks, common, dependabot, installer

ROOT = common.FACTORY_ROOT
KIT = ROOT / "kit" / "dependabot"


def touch(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def rendered(root: Path) -> dict:
    return yaml.safe_load(dependabot.render_for(root, (KIT / "dependabot.yml").read_text("utf-8")))


def ecosystems(doc: dict) -> list[tuple[str, str]]:
    return [(u["package-ecosystem"], u["directory"]) for u in doc["updates"]]


def adopt(project: Path) -> int:
    project.mkdir(parents=True, exist_ok=True)
    return installer.adopt(project, check=False)


# --- detection: only the ecosystems the project uses -----------------------------------------


def test_python_uv_project_gets_uv_and_github_actions(tmp_path):
    touch(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    touch(tmp_path, "uv.lock")
    assert ecosystems(rendered(tmp_path)) == [("uv", "/"), ("github-actions", "/")]


def test_python_without_uv_lock_gets_pip(tmp_path):
    touch(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    assert ecosystems(rendered(tmp_path)) == [("pip", "/"), ("github-actions", "/")]


def test_requirements_file_alone_gets_pip(tmp_path):
    touch(tmp_path, "requirements.txt", "flask\n")
    assert ecosystems(rendered(tmp_path)) == [("pip", "/"), ("github-actions", "/")]


def test_node_pnpm_project_gets_npm_and_github_actions(tmp_path):
    touch(tmp_path, "package.json", "{}")
    touch(tmp_path, "pnpm-lock.yaml")
    assert ecosystems(rendered(tmp_path)) == [("npm", "/"), ("github-actions", "/")]


def test_no_manifest_offers_only_github_actions(tmp_path):
    touch(tmp_path, "README.md", "hello")
    assert ecosystems(rendered(tmp_path)) == [("github-actions", "/")]


def test_directory_comes_from_where_the_manifest_lives(tmp_path):
    touch(tmp_path, "pyproject.toml")
    touch(tmp_path, "uv.lock")
    touch(tmp_path, "frontend/package.json", "{}")
    touch(tmp_path, "services/api/requirements.txt", "flask\n")
    assert ecosystems(rendered(tmp_path)) == [
        ("uv", "/"),
        ("pip", "/services/api"),
        ("npm", "/frontend"),
        ("github-actions", "/"),
    ]


def test_vendored_and_dependency_directories_are_not_scanned(tmp_path):
    touch(tmp_path, "node_modules/left-pad/package.json", "{}")
    touch(tmp_path, ".venv/lib/pkg/pyproject.toml")
    touch(tmp_path, "vendor/x/package.json", "{}")
    touch(tmp_path, "a/b/c/d/package.json", "{}")  # deeper than the search depth
    assert ecosystems(rendered(tmp_path)) == [("github-actions", "/")]


# --- what each entry says ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "files, ecosystem",
    [
        (("pyproject.toml", "uv.lock"), "uv"),
        (("pyproject.toml",), "pip"),
        (("package.json",), "npm"),
        ((), "github-actions"),
    ],
)
def test_every_entry_is_weekly_grouped_and_leaves_security_updates_alone(
    tmp_path, files, ecosystem
):
    for f in files:
        touch(tmp_path, f, "{}" if f.endswith(".json") else "")
    doc = rendered(tmp_path)
    entry = next(u for u in doc["updates"] if u["package-ecosystem"] == ecosystem)
    assert doc["version"] == 2
    assert entry["schedule"]["interval"] == "weekly"
    assert entry["groups"]["minor-and-patch"]["update-types"] == ["minor", "patch"]
    assert 1 <= entry["open-pull-requests-limit"] <= 10
    assert entry["open-pull-requests-limit"] != 0  # 0 would switch version updates off
    for u in doc["updates"]:  # a major is never grouped, and nothing narrows security updates
        assert "major" not in u["groups"]["minor-and-patch"]["update-types"]
        assert "applies-to" not in u["groups"]["minor-and-patch"]
        assert "ignore" not in u and "allow" not in u


def test_no_placeholder_tokens_survive_rendering(tmp_path):
    touch(tmp_path, "pyproject.toml")
    touch(tmp_path, "package.json", "{}")
    text = dependabot.render_for(tmp_path, (KIT / "dependabot.yml").read_text("utf-8"))
    assert "{{" not in text and "}}" not in text
    assert text.endswith("\n") and "\r" not in text


def test_header_without_the_token_is_an_error():
    with pytest.raises(dependabot.FactoryError):
        dependabot.render("version: 2\n", [], {})


# --- registered in the manifest, lint accepts it ---------------------------------------------


def test_manifest_registers_the_file_as_create_mode_and_names_the_fragments():
    manifest = yaml.safe_load((ROOT / "kit" / "manifest.yaml").read_text("utf-8"))
    entry = [e for e in manifest["files"] if e["dest"] == ".github/dependabot.yml"]
    assert len(entry) == 1 and entry[0]["mode"] == "create" and "stack" not in entry[0]
    assert set(manifest["dependabot_templates"]) == {"python", "npm", "github-actions"}
    assert checks.failures(checks.lint_manifest(ROOT)) == []


def test_lint_fails_when_a_fragment_is_missing(tmp_path):
    shutil.copytree(ROOT / "kit", tmp_path / "kit")
    (tmp_path / "kit" / "dependabot" / "npm.yml").unlink()
    fails = checks.failures(checks.lint_manifest(tmp_path))
    assert any("dependabot_templates.npm" in f.detail for f in fails)


def test_lint_fails_when_the_template_map_is_removed(tmp_path):
    shutil.copytree(ROOT / "kit", tmp_path / "kit")
    manifest = tmp_path / "kit" / "manifest.yaml"
    data = yaml.safe_load(manifest.read_text("utf-8"))
    del data["dependabot_templates"]
    manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
    fails = checks.failures(checks.lint_manifest(tmp_path))
    assert any("dependabot_templates" in f.detail for f in fails)


# --- adopt and sync: laid in once, only for the ecosystems in use, idempotent ----------------


def test_adopt_lays_in_only_the_used_ecosystems_and_sync_is_idempotent(tmp_path, capsys):
    project = tmp_path / "proj"
    touch(project, "pyproject.toml", "[project]\nname='proj'\n")
    touch(project, "uv.lock")
    touch(project, "web/package.json", "{}")
    assert adopt(project) == 0
    dest = project / ".github" / "dependabot.yml"
    first = dest.read_bytes()
    assert ecosystems(yaml.safe_load(first)) == [
        ("uv", "/"),
        ("npm", "/web"),
        ("github-actions", "/"),
    ]

    capsys.readouterr()
    assert installer.sync(project) == 0
    out = capsys.readouterr().out
    assert "dependabot.yml" not in out  # a no-op reports nothing about it
    assert dest.read_bytes() == first
    # not tracked as a managed file: it is the project's file from now on
    cfg = yaml.safe_load((project / ".factory" / "factory.yaml").read_text("utf-8"))
    assert ".github/dependabot.yml" not in cfg["managed"]


def test_sync_creates_the_file_in_an_already_adopted_project(tmp_path):
    project = tmp_path / "proj"
    touch(project, "package.json", "{}")
    assert adopt(project) == 0
    (project / ".github" / "dependabot.yml").unlink()
    assert installer.sync(project) == 0
    assert ecosystems(
        yaml.safe_load((project / ".github" / "dependabot.yml").read_text("utf-8"))
    ) == [
        ("npm", "/"),
        ("github-actions", "/"),
    ]


def test_an_existing_dependabot_yml_is_never_touched(tmp_path):
    project = tmp_path / "proj"
    touch(project, "pyproject.toml")
    own = "version: 2\nupdates: []  # the project's own\n"
    touch(project, ".github/dependabot.yml", own)
    assert adopt(project) == 0
    assert installer.sync(project) == 0
    assert (project / ".github" / "dependabot.yml").read_text("utf-8") == own


def test_dry_run_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    touch(project, "pyproject.toml")
    assert installer.adopt(project, dry_run=True, check=False) == 0
    assert not (project / ".github").exists()


def test_the_template_files_are_in_the_kit_and_generic():
    for name in ("dependabot.yml", "python.yml", "npm.yml", "github-actions.yml"):
        assert (KIT / name).is_file()
    assert "{{updates}}" in (KIT / "dependabot.yml").read_text("utf-8")
    assert checks.failures(checks.lint_generic(ROOT)) == []
