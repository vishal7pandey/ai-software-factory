"""Tests for adopt / sync / new / project (installer.py + commands/install.py).

Everything runs against a FIXTURE factory root in tmp_path, never the real kit/skills.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from swfactory import common, installer
from swfactory.commands import install as install_cmd
from swfactory.common import FactoryError

MANIFEST = """version: 1
files:
  - {src: kit/AGENTS.block.md, dest: AGENTS.md, mode: block}
  - {src: kit/CLAUDE.md, dest: CLAUDE.md, mode: create}
  - {src: kit/ci/python.yml, dest: .github/workflows/ci.yml, mode: create, stack: python}
  - {src: kit/ci/generic.yml, dest: .github/workflows/ci.yml, mode: create, stack: [docs, other]}
  - {src: kit/workflows/fv.yml, dest: .github/workflows/factory-verify.yml, mode: managed}
  - {src: src/swfactory/verify.py, dest: .factory/verify.py, mode: managed}
dirs:
  - {src: policies, dest: .factory/policies, mode: managed}
skills: all
"""

REGISTRY = """\
# Committed registry header.
projects:
  - name: other
    repo: github.com/me/other
    stack: docs
    tracker: {kind: none}
    autonomy: supervised
    adopted: false
"""


def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def factory(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "factory"
    _w(root / "kit" / "manifest.yaml", MANIFEST)
    _w(root / "kit" / "AGENTS.block.md", "## Factory\nUse the skills.\n")
    _w(root / "kit" / "CLAUDE.md", "@AGENTS.md\n")
    _w(root / "kit" / "ci" / "python.yml", "name: ci-python\n")
    _w(root / "kit" / "ci" / "generic.yml", "name: ci-generic\n")
    _w(root / "kit" / "workflows" / "fv.yml", "name: factory-verify\n")
    _w(root / "src" / "swfactory" / "verify.py", "print('verify v1')\n")
    _w(root / "policies" / "git.md", "git policy v1\n")
    _w(root / "policies" / "security.md", "security policy\n")
    _w(root / "skills" / "factory-a" / "SKILL.md", "---\nname: factory-a\n---\nA v1\n")
    _w(root / "skills" / "factory-b" / "SKILL.md", "---\nname: factory-b\n---\nB v1\n")
    _w(root / "skills" / "factory-b" / "references" / "ref.md", "ref v1\n")
    _w(root / "registry" / "projects.yaml", REGISTRY)
    _w(root / "templates" / "python" / "pyproject.toml", 'name = "{{name}}"\npkg = "{{package}}"\n')
    _w(root / "templates" / "python" / "src" / "__package__" / "__init__.py", '"""{{name}}"""\n')
    _w(root / "templates" / "python" / "README.md", "# {{name}}\n")
    monkeypatch.setattr(common, "FACTORY_ROOT", root)
    return root


def git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)


@pytest.fixture
def proj(tmp_path) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    git_init(p)
    _w(p / "pyproject.toml", '[project]\nname = "proj"\n')
    return p


def run(*argv: str) -> int:
    parser = argparse.ArgumentParser(prog="factory")
    sub = parser.add_subparsers(dest="command", required=True)
    install_cmd.register(sub)
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


def config(p: Path) -> dict:
    return common.load_yaml(p / ".factory" / "factory.yaml")


def snapshot(p: Path) -> dict[str, bytes]:
    return {
        f.relative_to(p).as_posix(): f.read_bytes()
        for f in p.rglob("*")
        if f.is_file() and ".git" not in f.relative_to(p).parts
    }


# --- adopt -------------------------------------------------------------------------------------


def test_fresh_adopt_lays_down_kit(factory, proj, capsys):
    assert run("adopt", str(proj)) == 0
    out = capsys.readouterr().out
    assert "CREATE" in out and "AGENTS.md" in out
    agents = (proj / "AGENTS.md").read_text(encoding="utf-8")
    assert agents == "<!-- factory:begin -->\n## Factory\nUse the skills.\n<!-- factory:end -->\n"
    assert (proj / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert (proj / ".github/workflows/ci.yml").read_text(encoding="utf-8") == "name: ci-python\n"
    assert (proj / ".factory/verify.py").is_file()
    assert (proj / ".factory/policies/git.md").is_file()
    for target in (".claude/skills", ".github/skills"):
        assert (proj / target / "factory-a" / "SKILL.md").is_file()
        assert (proj / target / "factory-b" / "references" / "ref.md").is_file()

    cfg = config(proj)
    assert cfg["factory_version"] == "0.1.0"
    assert cfg["stack"] == "python"  # autodetected from pyproject.toml
    assert cfg["autonomy"] == "supervised"
    assert cfg["tracker"] == {"kind": "none"}
    assert cfg["skill_targets"] == [".claude/skills", ".github/skills"]
    managed = cfg["managed"]
    assert managed[".factory/verify.py"] == common.sha256_file(proj / ".factory/verify.py")
    assert ".claude/skills/factory-b/references/ref.md" in managed
    assert ".factory/policies/security.md" in managed
    assert "AGENTS.md#block" in managed
    assert "CLAUDE.md" not in managed  # create-mode is not tracked
    assert b"\r" not in (proj / ".factory/factory.yaml").read_bytes()


def test_adopt_is_idempotent(factory, proj, capsys):
    run("adopt", str(proj))
    before = snapshot(proj)
    capsys.readouterr()
    assert run("adopt", str(proj)) == 0
    assert "up to date" in capsys.readouterr().out
    assert snapshot(proj) == before


def test_dry_run_writes_nothing(factory, proj, capsys):
    reg_before = (factory / "registry" / "projects.yaml").read_bytes()
    before = snapshot(proj)
    assert run("adopt", str(proj), "--dry-run") == 0
    out = capsys.readouterr().out
    assert "CREATE" in out and ".factory/factory.yaml" in out
    assert snapshot(proj) == before
    assert (factory / "registry" / "projects.yaml").read_bytes() == reg_before
    assert not (factory / "registry" / "local.yaml").exists()


def test_dry_run_lists_skip_and_block(factory, proj, capsys):
    _w(proj / "CLAUDE.md", "mine\n")
    _w(proj / "AGENTS.md", "# Mine\n")
    run("adopt", str(proj), "--dry-run")
    out = capsys.readouterr().out
    assert "SKIP(exists)" in out and "CLAUDE.md" in out
    assert "BLOCK" in out and "AGENTS.md" in out


def test_existing_agents_md_gets_block_appended(factory, proj):
    _w(proj / "AGENTS.md", "# My project\n\nMy own rules.")
    run("adopt", str(proj))
    text = (proj / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("# My project\n\nMy own rules.\n\n<!-- factory:begin -->\n")
    assert text.endswith("<!-- factory:end -->\n")


def test_rerun_replaces_block_in_place(factory, proj):
    _w(proj / "AGENTS.md", "top\n")
    run("adopt", str(proj))
    agents = proj / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8") + "\nuser tail\n", encoding="utf-8", newline="\n"
    )
    _w(factory / "kit" / "AGENTS.block.md", "## Factory v2\n")
    assert run("sync", str(proj)) == 0
    text = agents.read_text(encoding="utf-8")
    assert (
        text == "top\n\n<!-- factory:begin -->\n## Factory v2\n<!-- factory:end -->\n\nuser tail\n"
    )
    assert text.count("factory:begin") == 1


def test_block_edited_by_user_conflicts(factory, proj, capsys):
    run("adopt", str(proj))
    agents = proj / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace("Use the skills.", "I changed this."),
        encoding="utf-8",
        newline="\n",
    )
    _w(factory / "kit" / "AGENTS.block.md", "## Factory v2\n")
    assert run("sync", str(proj)) == 1
    assert "CONFLICT" in capsys.readouterr().out
    assert "I changed this." in agents.read_text(encoding="utf-8")
    assert run("sync", str(proj), "--force") == 0
    assert "Factory v2" in agents.read_text(encoding="utf-8")


def test_crlf_agents_md_stays_crlf(factory, proj):
    (proj / "AGENTS.md").write_bytes(b"# Mine\r\nline\r\n")
    run("adopt", str(proj))
    raw = (proj / "AGENTS.md").read_bytes()
    assert raw.startswith(b"# Mine\r\nline\r\n\r\n<!-- factory:begin -->\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert run("adopt", str(proj)) == 0  # CRLF block is not seen as a user edit


@pytest.mark.parametrize(
    "broken",
    [
        "x\n<!-- factory:begin -->\nno end\n",
        "x\n<!-- factory:end -->\n",
        "<!-- factory:end -->\n<!-- factory:begin -->\n",
    ],
)
def test_broken_markers_error_and_write_nothing(factory, proj, broken):
    _w(proj / "AGENTS.md", broken)
    before = snapshot(proj)
    with pytest.raises(FactoryError, match="markers"):
        run("adopt", str(proj))
    assert snapshot(proj) == before


# --- sync --------------------------------------------------------------------------------------


def test_sync_updates_unmodified_managed_files(factory, proj):
    run("adopt", str(proj))
    _w(factory / "policies" / "git.md", "git policy v2\n")
    assert run("sync", str(proj)) == 0
    assert (proj / ".factory/policies/git.md").read_text(encoding="utf-8") == "git policy v2\n"
    assert config(proj)["managed"][".factory/policies/git.md"] == common.sha256_text(
        "git policy v2\n"
    )


def test_edited_managed_file_conflicts_and_force_overwrites(factory, proj, capsys):
    run("adopt", str(proj))
    edited = proj / ".factory/policies/git.md"
    _w(edited, "my local policy\n")
    recorded = config(proj)["managed"][".factory/policies/git.md"]
    _w(factory / "policies" / "git.md", "git policy v2\n")
    capsys.readouterr()

    assert run("sync", str(proj)) == 1
    out = capsys.readouterr().out
    assert "CONFLICT" in out and ".factory/policies/git.md" in out
    assert edited.read_text(encoding="utf-8") == "my local policy\n"
    assert config(proj)["managed"][".factory/policies/git.md"] == recorded  # still conflicting
    assert run("sync", str(proj)) == 1

    assert run("sync", str(proj), "--force") == 0
    assert edited.read_text(encoding="utf-8") == "git policy v2\n"
    assert run("sync", str(proj)) == 0


def test_conflict_does_not_block_other_files(factory, proj):
    run("adopt", str(proj))
    _w(proj / ".factory/policies/git.md", "mine\n")
    _w(factory / "policies" / "git.md", "git policy v2\n")
    _w(factory / "policies" / "security.md", "security v2\n")
    assert run("sync", str(proj)) == 1
    assert (proj / ".factory/policies/security.md").read_text(encoding="utf-8") == "security v2\n"


def test_deleted_managed_file_is_restored(factory, proj):
    run("adopt", str(proj))
    gone = proj / ".claude/skills/factory-a/SKILL.md"
    gone.unlink()
    assert run("sync", str(proj)) == 0
    assert gone.is_file()


def test_crlf_edit_with_same_content_is_not_a_conflict(factory, proj, capsys):
    run("adopt", str(proj))
    path = proj / ".factory/policies/git.md"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    capsys.readouterr()
    assert run("sync", str(proj)) == 0
    assert "CONFLICT" not in capsys.readouterr().out
    # and a later factory update still applies (the file is unmodified in substance)
    _w(factory / "policies" / "git.md", "git policy v2\n")
    assert run("sync", str(proj)) == 0
    assert path.read_text(encoding="utf-8") == "git policy v2\n"


def test_untracked_preexisting_managed_path_is_a_conflict(factory, proj):
    _w(proj / ".github/workflows/factory-verify.yml", "name: someone else's\n")
    assert run("adopt", str(proj)) == 1
    assert "someone else" in (proj / ".github/workflows/factory-verify.yml").read_text(
        encoding="utf-8"
    )
    assert ".github/workflows/factory-verify.yml" not in config(proj)["managed"]


def test_create_mode_never_overwrites(factory, proj):
    _w(proj / "CLAUDE.md", "my claude file\n")
    _w(proj / ".github/workflows/ci.yml", "name: mine\n")
    run("adopt", str(proj))
    _w(factory / "kit" / "CLAUDE.md", "changed upstream\n")
    run("sync", str(proj), "--force")
    assert (proj / "CLAUDE.md").read_text(encoding="utf-8") == "my claude file\n"
    assert (proj / ".github/workflows/ci.yml").read_text(encoding="utf-8") == "name: mine\n"


def test_sync_requires_adopted_project(factory, proj):
    with pytest.raises(FactoryError, match="not adopted"):
        run("sync", str(proj))
    with pytest.raises(FactoryError, match="not a directory"):
        run("sync", str(proj / "nope"))


def test_sync_dry_run_writes_nothing(factory, proj):
    run("adopt", str(proj))
    _w(factory / "policies" / "git.md", "git policy v2\n")
    before = snapshot(proj)
    run("sync", str(proj), "--dry-run")
    assert snapshot(proj) == before


# --- stack / config ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stack", "ci"),
    [("python", "ci-python"), ("other", "ci-generic"), ("docs", "ci-generic")],
)
def test_stack_filtering(factory, tmp_path, stack, ci):
    p = tmp_path / f"p-{stack}"
    p.mkdir()
    run("adopt", str(p), "--stack", stack)
    assert (p / ".github/workflows/ci.yml").read_text(encoding="utf-8") == f"name: {ci}\n"
    assert config(p)["stack"] == stack


def test_stack_autodetect(factory, tmp_path):
    node, plain = tmp_path / "n", tmp_path / "x"
    node.mkdir()
    plain.mkdir()
    _w(node / "package.json", "{}\n")
    run("adopt", str(node))
    run("adopt", str(plain))
    assert config(node)["stack"] == "node"
    assert config(plain)["stack"] == "other"  # never auto-detects docs


def test_tracker_and_autonomy_flags(factory, proj):
    run("adopt", str(proj), "--tracker", "jira", "--jira-key", "SCRUM", "--autonomy", "trusted")
    cfg = config(proj)
    assert cfg["tracker"] == {"kind": "jira", "key": "SCRUM"}
    assert cfg["autonomy"] == "trusted"


def test_existing_config_wins_unless_flag_passed(factory, proj):
    run("adopt", str(proj), "--tracker", "jira", "--jira-key", "SCRUM", "--autonomy", "trusted")
    run("adopt", str(proj))
    cfg = config(proj)
    assert cfg["tracker"] == {"kind": "jira", "key": "SCRUM"} and cfg["autonomy"] == "trusted"
    run("adopt", str(proj), "--autonomy", "supervised")
    cfg = config(proj)
    assert cfg["autonomy"] == "supervised" and cfg["tracker"]["key"] == "SCRUM"


@pytest.mark.parametrize(
    "flags",
    [
        ["--stack", "cobol"],
        ["--autonomy", "yolo"],
        ["--tracker", "linear"],
        ["--tracker", "jira"],  # key missing
        ["--jira-key", "X"],  # no jira tracker
        ["--tracker", "github", "--jira-key", "X"],
    ],
)
def test_bad_flag_values_are_factory_errors(factory, proj, flags):
    with pytest.raises(FactoryError):
        run("adopt", str(proj), *flags)
    assert not (proj / ".factory").exists()


def test_custom_skill_targets_are_honoured(factory, proj):
    run("adopt", str(proj))
    cfg = config(proj)
    cfg["skill_targets"] = [".agents/skills"]
    common.dump_yaml(cfg, proj / ".factory" / "factory.yaml")
    run("sync", str(proj))
    assert (proj / ".agents/skills/factory-a/SKILL.md").is_file()


def test_target_must_be_a_directory(factory, tmp_path):
    with pytest.raises(FactoryError, match="not a directory"):
        run("adopt", str(tmp_path / "missing"))


def test_non_git_dir_warns_but_adopts(factory, tmp_path, capsys):
    p = tmp_path / "plain"
    p.mkdir()
    assert run("adopt", str(p)) == 0
    assert "not a git repository" in capsys.readouterr().err
    assert (p / ".factory" / "factory.yaml").is_file()
    assert not (p / ".git").exists()


# --- registry ----------------------------------------------------------------------------------


def test_adopt_upserts_registry_and_local_paths(factory, proj):
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/me/proj.git"], cwd=proj, check=True
    )
    run("adopt", str(proj), "--tracker", "jira", "--jira-key", "SCRUM")
    reg_file = factory / "registry" / "projects.yaml"
    assert reg_file.read_text(encoding="utf-8").startswith("# Committed registry header.\n")
    entries = {p["name"]: p for p in common.load_yaml(reg_file)["projects"]}
    assert entries["other"]["adopted"] is False  # untouched
    e = entries["proj"]
    assert e == {
        "name": "proj",
        "repo": "github.com/me/proj",
        "stack": "python",
        "tracker": {"kind": "jira", "key": "SCRUM"},
        "autonomy": "supervised",
        "adopted": True,
    }
    local = common.load_yaml(factory / "registry" / "local.yaml")
    assert local["paths"]["proj"] == str(proj.resolve())

    run("adopt", str(proj))  # upsert, not duplicate
    assert [p["name"] for p in common.load_yaml(reg_file)["projects"]].count("proj") == 1


def test_adopt_keeps_existing_registry_fields(factory, tmp_path):
    p = tmp_path / "other"
    p.mkdir()
    git_init(p)
    reg_file = factory / "registry" / "projects.yaml"
    reg = common.load_yaml(reg_file)
    reg["projects"][0]["note"] = "keep me"
    common.dump_yaml(reg, reg_file)
    run("adopt", str(p))  # no remote: repo is kept
    e = common.load_yaml(reg_file)["projects"][0]
    assert e["note"] == "keep me" and e["repo"] == "github.com/me/other"
    assert e["adopted"] is True and e["stack"] == "other"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/me/proj.git", "github.com/me/proj"),
        ("https://user:tok@github.com/me/proj", "github.com/me/proj"),
        ("git@github.com:me/proj.git", "github.com/me/proj"),
        ("ssh://git@github.com/me/proj.git", "github.com/me/proj"),
    ],
)
def test_normalise_repo_url(url, expected):
    assert installer.normalise_repo_url(url) == expected


def test_project_add_list_remove(factory, tmp_path, capsys):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    run(
        "project", "add", "newproj", "--repo", "https://github.com/me/newproj.git",
        "--stack", "node", "--tracker", "jira", "--jira-key", "PF", "--path", str(checkout),
    )  # fmt: skip
    capsys.readouterr()
    run("project", "list")
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].split() == ["name", "stack", "tracker", "adopted", "path"]
    newproj = next(line for line in lines if line.startswith("newproj"))
    assert "node" in newproj and "jira:PF" in newproj and "no" in newproj.split()
    assert str(checkout.resolve()) in newproj
    other = next(line for line in lines if line.startswith("other"))
    assert other.rstrip().endswith("-")

    entries = common.load_yaml(factory / "registry" / "projects.yaml")["projects"]
    assert entries[-1]["repo"] == "github.com/me/newproj" and entries[-1]["adopted"] is False

    with pytest.raises(FactoryError, match="already registered"):
        run("project", "add", "newproj")
    run("project", "remove", "newproj")
    names = [
        p["name"] for p in common.load_yaml(factory / "registry" / "projects.yaml")["projects"]
    ]
    assert names == ["other"]
    assert "newproj" not in common.load_yaml(factory / "registry" / "local.yaml")["paths"]
    with pytest.raises(FactoryError, match="not registered"):
        run("project", "remove", "newproj")


# --- new ---------------------------------------------------------------------------------------


def test_new_substitutes_renames_inits_and_adopts(factory, tmp_path):
    out_dir = tmp_path / "work"
    assert run("new", "My-App", "--stack", "python", "--dir", str(out_dir)) == 0
    p = out_dir / "My-App"
    assert (p / "README.md").read_text(encoding="utf-8") == "# My-App\n"
    assert (p / "pyproject.toml").read_text(encoding="utf-8") == 'name = "My-App"\npkg = "my_app"\n'
    assert not (p / "src" / "__package__").exists()
    assert (p / "src" / "my_app" / "__init__.py").read_text(encoding="utf-8") == '"""My-App"""\n'
    assert (p / ".git").is_dir()
    branch = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"], cwd=p, capture_output=True, text=True
    ).stdout.strip()
    assert branch == "main"
    assert (p / ".factory" / "factory.yaml").is_file() and config(p)["stack"] == "python"
    assert (p / "AGENTS.md").is_file()
    log = subprocess.run(["git", "log"], cwd=p, capture_output=True, text=True)
    assert log.returncode != 0  # nothing committed
    names = [
        e["name"] for e in common.load_yaml(factory / "registry" / "projects.yaml")["projects"]
    ]
    assert "My-App" in names


@pytest.mark.parametrize("bad", ["1app", "___", "a/b", ".."])
def test_new_rejects_bad_names(factory, tmp_path, bad):
    with pytest.raises(FactoryError):
        run("new", bad, "--dir", str(tmp_path / "work"))
    assert not (tmp_path / "work").exists()


def test_new_refuses_non_empty_target(factory, tmp_path):
    target = tmp_path / "work" / "app"
    _w(target / "keep.txt", "x\n")
    with pytest.raises(FactoryError, match="not empty"):
        run("new", "app", "--dir", str(tmp_path / "work"))
    assert (target / "keep.txt").read_text(encoding="utf-8") == "x\n"
    assert not (target / ".git").exists()


def test_new_allows_existing_empty_target_and_unknown_stack_errors(factory, tmp_path):
    (tmp_path / "work" / "app").mkdir(parents=True)
    assert run("new", "app", "--dir", str(tmp_path / "work")) == 0
    with pytest.raises(FactoryError, match="no template"):
        run("new", "app2", "--stack", "cobol", "--dir", str(tmp_path / "work"))
