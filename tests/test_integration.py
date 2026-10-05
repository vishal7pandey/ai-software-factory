"""Cross-module checks against the REAL kit and skills.

Unit tests use fixture factory roots; these catch what only shows when the real pieces meet
(installer ledger vs doctor, templates vs approve/verify, verify.py running standalone).
"""

import subprocess
import sys

import pytest

from swfactory import cli, common


def sh(*args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_REGISTRY", str(tmp_path / "reg" / "registry.yaml"))
    p = tmp_path / "app"
    p.mkdir()
    (p / "pyproject.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
    sh("git", "init", "-q", "-b", "main", cwd=p)
    sh("git", "config", "user.name", "Test Human", cwd=p)
    sh("git", "config", "user.email", "t@example.com", cwd=p)
    monkeypatch.chdir(p)
    return p


def item_dir(p):
    return next((p / "docs" / "work").glob("F-001-*"))


def write_real(path):
    """Replace a scaffolded doc with 'written' content (no sentinel line)."""
    lines = [
        ln for ln in path.read_text(encoding="utf-8").splitlines() if "factory:unfilled" not in ln
    ]
    path.write_text("\n".join(lines) + "\nReal content.\n", encoding="utf-8")


def test_adopt_is_idempotent_and_doctor_is_clean(app, capsys):
    assert cli.main(["adopt", str(app)]) == 0
    capsys.readouterr()
    assert cli.main(["adopt", str(app)]) == 0
    assert "up to date" in capsys.readouterr().out
    assert cli.main(["doctor", str(app)]) == 0
    out = capsys.readouterr().out
    assert "FAIL" not in out and "WARN" not in out


def test_every_installed_skill_and_policy_exists(app):
    cli.main(["adopt", str(app)])
    for target in (".claude/skills", ".github/skills"):
        names = sorted(d.name for d in (app / target).iterdir())
        assert names == sorted(d.name for d in common.skills_dir().iterdir())
    assert (app / ".factory" / "templates" / "work" / "test-plan.md").is_file()
    assert (app / ".factory" / "verify.py").is_file()


def test_golden_path_gates_reject_scaffolds_and_pass_real_docs(app, capsys):
    cli.main(["adopt", str(app)])
    assert cli.main(["feature", "start", "Add thing", "--no-branch"]) == 0
    d = item_dir(app)

    # A scaffolded template must NOT be approvable (substance, not surface).
    assert cli.main(["approve", "F-001", "spec", "--yes"]) == 1
    assert "scaffolded template" in capsys.readouterr().err
    write_real(d / "spec.md")
    assert cli.main(["approve", "F-001", "spec", "--yes"]) == 0

    assert cli.main(["approve", "F-001", "plan", "--yes"]) == 1
    write_real(d / "plan.md")
    assert cli.main(["approve", "F-001", "plan", "--yes"]) == 0

    # The CLI refuses to move to implementing with an untouched test plan...
    assert cli.main(["advance", "F-001", "implementing"]) == 1
    # ...and verify catches the same thing when status was edited by hand (skills allow that).
    item = d / "item.yaml"
    item.write_text(
        item.read_text(encoding="utf-8").replace("status: plan-approved", "status: implementing"),
        encoding="utf-8",
    )
    verify = [sys.executable, str(app / ".factory" / "verify.py"), "--root", str(app)]
    r = sh(*verify, cwd=app)
    assert r.returncode == 1 and "factory:unfilled" in r.stdout
    write_real(d / "test-plan.md")
    r = sh(*verify, cwd=app)
    assert r.returncode == 0, r.stdout
    assert "verify: OK" in r.stdout


def test_slugify_cuts_on_word_boundary():
    slug = common.slugify("Add a greet command that prints a greeting for a given name")
    assert slug == "add-a-greet-command-that-prints-a"
    assert len(slug) <= 40
    assert common.slugify("x" * 60) == "x" * 40  # no hyphen to cut on: hard cut
    assert common.slugify("!!!") == "item"
