"""Work-item commands: start, status, approve, advance, next."""

from __future__ import annotations

import io
import subprocess

import pytest
import yaml

from swfactory import cli, common, work
from swfactory.common import FactoryError
from swfactory.verify import ITEM_KEYS, STATUSES, check_project, load_item

TEMPLATES = {
    "spec.feature.md": (
        "# {{id}} {{title}}\nslug={{slug}} date={{date}} risk={{risk}} jira={{jira}}\n"
    ),
    "spec.bug.md": "# BUG {{id}} {{title}}\njira={{jira}}\n",
    "plan.md": "# Plan {{id}}\n",
    "test-plan.md": "# Test plan {{id}}\n",
}


@pytest.fixture
def factory_root(tmp_path, monkeypatch):
    root = tmp_path / "factory"
    (root / "kit" / "work").mkdir(parents=True)
    for name, text in TEMPLATES.items():
        (root / "kit" / "work" / name).write_text(text, encoding="utf-8")
    manifest = {
        "work_templates": {
            "feature_spec": "kit/work/spec.feature.md",
            "bug_spec": "kit/work/spec.bug.md",
            "plan": "kit/work/plan.md",
            "test_plan": "kit/work/test-plan.md",
        }
    }
    (root / "kit" / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    monkeypatch.setattr(common, "FACTORY_ROOT", root)
    return root


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def make_project(tmp_path, autonomy="supervised", git=True):
    proj = tmp_path / "proj"
    (proj / ".factory").mkdir(parents=True)
    (proj / ".factory" / "factory.yaml").write_text(f"autonomy: {autonomy}\n", encoding="utf-8")
    if git:
        _git(proj, "init", "-q", "-b", "main")
        _git(proj, "config", "user.name", "Test Human")
        _git(proj, "config", "user.email", "t@example.com")
    return proj


@pytest.fixture
def project(tmp_path, factory_root, monkeypatch):
    proj = make_project(tmp_path)
    monkeypatch.chdir(proj)
    return proj


def run(*argv):
    """Like cli.main but lets FactoryError propagate so tests can assert on it."""
    args = cli.build_parser().parse_args(list(argv))
    return int(args.func(args) or 0)


def item_dir(project, ident):
    return work.find_item_dir(project, ident)


def set_status(project, ident, status, **extra):
    d = item_dir(project, ident)
    item = load_item(d / "item.yaml")
    item["status"] = status
    item.update(extra)
    work.write_item(d, item)
    return d


def fill_docs(d, **overrides):
    for name in ("spec.md", "plan.md", "test-plan.md"):
        (d / name).write_text(overrides.get(name, "real content\n"), encoding="utf-8")


APPROVAL = {"by": "Test Human", "at": "2026-10-04"}


# --- start -------------------------------------------------------------------------------------


def test_ids_increment_and_types_are_independent(project):
    assert run("feature", "start", "Add login", "--no-branch") == 0
    assert run("feature", "start", "Add logout", "--no-branch") == 0
    assert run("bug", "start", "Crash on save", "--no-branch") == 0
    names = sorted(p.name for p in (project / "docs" / "work").iterdir())
    assert names == ["B-001-crash-on-save", "F-001-add-login", "F-002-add-logout"]


def test_jira_key_is_used_as_id(project):
    assert run("feature", "start", "Add Google login", "--jira", "PF-12", "--no-branch") == 0
    d = project / "docs" / "work" / "PF-12-add-google-login"
    item = load_item(d / "item.yaml")
    assert item["id"] == "PF-12" and item["jira"] == "PF-12"
    assert "jira=PF-12" in (d / "spec.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("key", ["pf-12", "PF12", "12-PF", "P-1", "PF-"])
def test_invalid_jira_key(project, key):
    with pytest.raises(FactoryError, match="Jira key"):
        work.cmd_start("feature", "x", jira=key, risk="medium", no_branch=True, run=None)


def test_duplicate_id_refused(project):
    run("feature", "start", "One", "--jira", "PF-1", "--no-branch")
    with pytest.raises(FactoryError, match="already exists"):
        work.cmd_start("bug", "Other", jira="PF-1", risk="low", no_branch=True, run=None)


def test_scaffold_contents(project, capsys):
    assert run("feature", "start", "Add login", "--risk", "high", "--no-branch") == 0
    out = capsys.readouterr().out
    d = project / "docs" / "work" / "F-001-add-login"
    assert sorted(p.name for p in d.iterdir()) == [
        "item.yaml",
        "plan.md",
        "spec.md",
        "test-plan.md",
    ]
    raw = (d / "item.yaml").read_text(encoding="utf-8")
    assert raw.splitlines()[0] == "id: F-001"
    keys = [line.split(":")[0] for line in raw.splitlines() if not line.startswith(" ")]
    assert keys == list(ITEM_KEYS)
    item = yaml.safe_load(raw)
    assert item["status"] == "draft" and item["risk"] == "high" and item["jira"] is None
    assert item["created"] == common.today() and isinstance(item["created"], str)
    assert item["approvals"] == {} and item["pr"] is None
    spec = (d / "spec.md").read_text(encoding="utf-8")
    assert spec == f"# F-001 Add login\nslug=add-login date={common.today()} risk=high jira=none\n"
    assert "Use the factory-spec skill on work item docs/work/F-001-add-login/ (id F-001)" in out
    assert "Next human step: factory approve F-001 spec" in out
    assert "docs/work/F-001-add-login/spec.md" in out


def test_bug_uses_bug_template_and_diagnose(project, capsys):
    run("bug", "start", "Crash on save", "--no-branch")
    d = project / "docs" / "work" / "B-001-crash-on-save"
    assert (d / "spec.md").read_text(encoding="utf-8").startswith("# BUG B-001")
    assert load_item(d / "item.yaml")["type"] == "bug"
    assert "factory-diagnose" in capsys.readouterr().out


def test_branch_naming(project):
    run("feature", "start", "Add login")
    assert _git(project, "branch", "--show-current") == "feature/f-001-add-login"
    run("bug", "start", "Crash on save", "--jira", "PF-7")
    assert _git(project, "branch", "--show-current") == "fix/pf-7-crash-on-save"
    item = load_item(project / "docs" / "work" / "PF-7-crash-on-save" / "item.yaml")
    assert item["branch"] == "fix/pf-7-crash-on-save"


def test_no_branch_flag_and_non_git(project, tmp_path, monkeypatch):
    run("feature", "start", "Add login", "--no-branch")
    assert _git(project, "branch", "--show-current") == "main"
    plain = make_project(tmp_path / "other", git=False)
    monkeypatch.chdir(plain)
    assert run("feature", "start", "Add login") == 0  # no git: scaffold only
    assert (plain / "docs" / "work" / "F-001-add-login" / "item.yaml").is_file()


def test_dirty_tree_is_carried_not_staged(project):
    (project / "wip.txt").write_text("work in progress", encoding="utf-8")
    run("feature", "start", "Add login")
    assert _git(project, "branch", "--show-current") == "feature/f-001-add-login"
    assert (project / "wip.txt").read_text(encoding="utf-8") == "work in progress"
    assert _git(project, "diff", "--cached", "--name-only") == ""


def test_requires_adopted_project(tmp_path, factory_root, monkeypatch):
    bare = tmp_path / "bare"
    bare.mkdir()
    _git(bare, "init", "-q")
    monkeypatch.chdir(bare)
    with pytest.raises(FactoryError, match="factory adopt"):
        run("feature", "start", "x")


def test_missing_template_is_an_error(project, factory_root):
    (factory_root / "kit" / "work" / "plan.md").unlink()
    with pytest.raises(FactoryError, match="template 'plan'"):
        run("feature", "start", "x", "--no-branch")
    assert not (project / "docs" / "work").exists()


def test_run_launches_agent(project, monkeypatch):
    calls = []
    monkeypatch.setattr(work.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        work.subprocess,
        "run",
        lambda cmd, cwd: calls.append((cmd, cwd)) or subprocess.CompletedProcess(cmd, 0),
    )
    assert run("feature", "start", "Add login", "--no-branch", "--run", "claude") == 0
    cmd, _ = calls[-1]
    assert cmd[0] == "/bin/claude" and len(cmd) == 2 and cmd[1].startswith("Use the factory-spec")
    run("next", "F-001", "--run", "copilot")
    cmd, _ = calls[-1]
    assert cmd[:2] == ["/bin/copilot", "-i"] and "factory-spec" in cmd[2]


def test_run_missing_binary_shows_prompt(project, monkeypatch):
    monkeypatch.setattr(work.shutil, "which", lambda name: None)
    with pytest.raises(FactoryError, match="Use the factory-spec skill"):
        run("feature", "start", "Add login", "--no-branch", "--run", "claude")
    assert (project / "docs" / "work" / "F-001-add-login").is_dir()  # scaffold kept


# --- status ------------------------------------------------------------------------------------


def test_status_table(project, capsys):
    run("feature", "start", "Add login", "--no-branch")
    run("bug", "start", "Crash", "--no-branch")
    set_status(project, "B-001", "done")
    capsys.readouterr()
    assert run("status") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].split() == ["id", "type", "status", "branch", "next"]
    assert "F-001" in out and "draft" in out and "factory-spec" in out and "B-001" not in out
    run("status", "--all")
    out = capsys.readouterr().out
    assert "B-001" in out and "done" in out


def test_status_flags_invalid_items(project, capsys):
    run("feature", "start", "Good", "--no-branch")
    bad = project / "docs" / "work" / "F-002-bad"
    bad.mkdir()
    (bad / "item.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    worse = project / "docs" / "work" / "F-003-worse"
    worse.mkdir()
    (worse / "item.yaml").write_text("id: F-003\nstatus: bogus\n", encoding="utf-8")
    capsys.readouterr()
    assert run("status") == 0
    out = capsys.readouterr().out
    assert out.count("INVALID") == 2 and "F-001" in out


def test_status_empty(project, capsys):
    assert run("status") == 0
    assert "No open work items" in capsys.readouterr().out


def test_crlf_item_yaml_tolerated(project, capsys):
    run("feature", "start", "Add login", "--no-branch")
    d = item_dir(project, "F-001")
    text = (d / "item.yaml").read_text(encoding="utf-8").replace("\n", "\r\n")
    (d / "item.yaml").write_bytes(text.encode("utf-8"))
    capsys.readouterr()
    assert run("status") == 0
    assert "INVALID" not in capsys.readouterr().out
    assert load_item(d / "item.yaml")["id"] == "F-001"


# --- approve -----------------------------------------------------------------------------------


def start_with_spec(project, content="Real spec\n", **kw):
    run("feature", "start", "Add login", "--no-branch", *kw.get("args", []))
    d = item_dir(project, "F-001")
    (d / "spec.md").write_text(content, encoding="utf-8")
    return d


def test_approve_spec_happy_path(project, capsys):
    d = start_with_spec(project)
    assert run("approve", "F-001", "spec", "--yes") == 0
    item = load_item(d / "item.yaml")
    assert item["status"] == "spec-approved"
    assert item["approvals"]["spec"] == {"by": "Test Human", "at": common.today()}
    # dates stay quoted strings on disk
    assert f"at: '{common.today()}'" in (d / "item.yaml").read_text(encoding="utf-8")
    assert "spec approved" in capsys.readouterr().out


def test_approve_delegated_records_flag_and_suffix(project, capsys):
    d = start_with_spec(project)
    assert run("approve", "F-001", "spec", "--delegated", "  Jane Doe ", "--yes") == 0
    item = load_item(d / "item.yaml")
    assert item["status"] == "spec-approved"
    assert item["approvals"]["spec"] == {
        "by": "Jane Doe (delegated to agent)",
        "at": common.today(),
        "delegated": True,
    }
    assert "Jane Doe (delegated to agent)" in capsys.readouterr().out
    assert check_project(project, branch=None) == []  # verify accepts what the CLI wrote


@pytest.mark.parametrize("name", ["", "   "])
def test_approve_delegated_empty_name_refused(project, name):
    d = start_with_spec(project)
    before = (d / "item.yaml").read_bytes()
    with pytest.raises(FactoryError, match="--delegated needs the name"):
        run("approve", "F-001", "spec", "--delegated", name, "--yes")
    assert (d / "item.yaml").read_bytes() == before


def test_approve_without_delegated_has_no_flag(project):
    d = start_with_spec(project)
    run("approve", "F-001", "spec", "--yes")
    assert "delegated" not in load_item(d / "item.yaml")["approvals"]["spec"]


def test_reapprove_delegated_refreshes_ledger(project):
    d = start_with_spec(project)
    run("approve", "F-001", "spec", "--yes")
    (d / "plan.md").write_text("A plan\n", encoding="utf-8")
    run("approve", "F-001", "plan", "--yes")
    (d / "spec.md").write_text("Amended spec\n", encoding="utf-8")
    assert run("approve", "F-001", "spec", "--delegated", "Jane Doe", "--yes") == 0
    item = load_item(d / "item.yaml")
    assert item["status"] == "plan-approved"
    assert item["approvals"]["spec"]["by"] == "Jane Doe (delegated to agent)"
    assert item["approvals"]["spec"]["delegated"] is True


def test_status_marks_delegated_approvals(project, capsys):
    d = start_with_spec(project)
    run("approve", "F-001", "spec", "--yes")
    capsys.readouterr()
    run("status")
    assert "(delegated)" not in capsys.readouterr().out  # ordinary approval: no marker

    run("approve", "F-001", "spec", "--delegated", "Jane Doe", "--yes")
    capsys.readouterr()
    run("status")
    assert "spec-approved (delegated)" in capsys.readouterr().out

    item = load_item(d / "item.yaml")  # the older hand-written form is recognised too
    item["approvals"]["spec"] = {"by": "Jane Doe (delegated to agent)", "at": common.today()}
    work.write_item(d, item)
    capsys.readouterr()
    run("status")
    assert "(delegated)" in capsys.readouterr().out


def test_approve_plan_after_spec(project):
    d = start_with_spec(project)
    run("approve", "F-001", "spec", "--yes")
    (d / "plan.md").write_text("A plan\n", encoding="utf-8")
    assert run("approve", "F-001", "plan", "--yes") == 0
    item = load_item(d / "item.yaml")
    assert item["status"] == "plan-approved" and "plan" in item["approvals"]


@pytest.mark.parametrize("ident", ["f-001", "F-001-add-login", "f-001-ADD-login"])
def test_approve_id_is_case_insensitive_and_accepts_dir_name(project, ident):
    d = start_with_spec(project)
    assert run("approve", ident, "spec", "--yes") == 0
    assert load_item(d / "item.yaml")["status"] == "spec-approved"


def test_approve_blocked_by_wrong_status(project):
    start_with_spec(project)
    with pytest.raises(FactoryError, match="must be spec-approved"):
        run("approve", "F-001", "plan", "--yes")
    run("approve", "F-001", "spec", "--yes")
    # spec is approved now, so approving spec again is a re-approval, not an error (see below)
    assert run("approve", "F-001", "spec", "--yes") == 0


def test_reapprove_refreshes_ledger_without_moving_status(project, monkeypatch):
    d = start_with_spec(project)
    run("approve", "F-001", "spec", "--yes")
    (d / "plan.md").write_text("A plan\n", encoding="utf-8")
    run("approve", "F-001", "plan", "--yes")
    (d / "spec.md").write_text("Amended spec\n", encoding="utf-8")
    monkeypatch.setattr(common, "git_user_name", lambda *_a, **_k: "Second Human")
    assert run("approve", "F-001", "spec", "--yes") == 0
    item = load_item(d / "item.yaml")
    assert item["status"] == "plan-approved"  # never backwards
    assert item["approvals"]["spec"]["by"] == "Second Human"


def test_reapprove_refused_after_in_review_and_before_gate(project):
    d = start_with_spec(project)
    with pytest.raises(FactoryError, match="cannot approve plan"):
        run("approve", "F-001", "plan", "--yes")  # draft: plan gate not reachable
    item = load_item(d / "item.yaml")
    item["status"] = "merged"
    (d / "item.yaml").write_text(yaml.safe_dump(item, sort_keys=False), encoding="utf-8")
    with pytest.raises(FactoryError, match="cannot approve spec"):
        run("approve", "F-001", "spec", "--yes")


def test_approve_blocked_by_missing_empty_or_unclear_doc(project):
    d = start_with_spec(project, content="  \n")
    with pytest.raises(FactoryError, match="missing or empty"):
        run("approve", "F-001", "spec", "--yes")
    (d / "spec.md").unlink()
    with pytest.raises(FactoryError, match="missing or empty"):
        run("approve", "F-001", "spec", "--yes")
    (d / "spec.md").write_text("Q: [NEEDS CLARIFICATION: which IdP?]\n", encoding="utf-8")
    with pytest.raises(FactoryError, match="NEEDS CLARIFICATION"):
        run("approve", "F-001", "spec", "--yes")
    assert load_item(d / "item.yaml")["status"] == "draft"


def test_approve_plan_blocked_by_unclear_plan(project):
    d = start_with_spec(project)
    run("approve", "F-001", "spec", "--yes")
    (d / "plan.md").write_text("[NEEDS CLARIFICATION: x]\n", encoding="utf-8")
    with pytest.raises(FactoryError, match="NEEDS CLARIFICATION"):
        run("approve", "F-001", "plan", "--yes")


def test_approve_non_tty_without_yes_refused(project, monkeypatch):
    d = start_with_spec(project)
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))  # StringIO.isatty() is False
    with pytest.raises(FactoryError, match="--yes"):
        run("approve", "F-001", "spec")
    assert load_item(d / "item.yaml")["status"] == "draft"


class FakeTty(io.StringIO):
    def isatty(self):
        return True


def test_approve_interactive_confirmation(project, monkeypatch, capsys):
    d = start_with_spec(project)
    monkeypatch.setattr("sys.stdin", FakeTty("n\n"))
    assert run("approve", "F-001", "spec") == 1
    assert load_item(d / "item.yaml")["status"] == "draft"
    monkeypatch.setattr("sys.stdin", FakeTty("y\n"))
    assert run("approve", "F-001", "spec") == 0
    assert "Approve spec for F-001 'Add login'" in capsys.readouterr().out
    assert load_item(d / "item.yaml")["status"] == "spec-approved"


def test_unknown_item(project):
    with pytest.raises(FactoryError, match="no work item"):
        run("approve", "F-999", "spec", "--yes")


# --- advance -----------------------------------------------------------------------------------


def test_advance_ordering_errors(project):
    d = start_with_spec(project)
    with pytest.raises(FactoryError, match="skip"):
        run("advance", "F-001", "implementing")
    with pytest.raises(FactoryError, match="human gate"):
        run("advance", "F-001", "spec-approved")
    with pytest.raises(FactoryError, match="already draft"):
        run("advance", "F-001", "draft")
    set_status(project, "F-001", "plan-approved", approvals={"spec": APPROVAL, "plan": APPROVAL})
    with pytest.raises(FactoryError, match="forward"):
        run("advance", "F-001", "spec-approved")
    assert load_item(d / "item.yaml")["status"] == "plan-approved"


def test_advance_plan_approved_requires_approve_when_supervised(project):
    start_with_spec(project)
    set_status(project, "F-001", "spec-approved", approvals={"spec": APPROVAL})
    with pytest.raises(FactoryError, match="factory approve F-001 plan"):
        run("advance", "F-001", "plan-approved")


def test_advance_implementing_requires_test_plan(project, capsys):
    d = start_with_spec(project)
    set_status(project, "F-001", "plan-approved", approvals={"spec": APPROVAL, "plan": APPROVAL})
    (d / "test-plan.md").write_text("", encoding="utf-8")
    with pytest.raises(FactoryError, match="test-plan.md is missing or empty"):
        run("advance", "F-001", "implementing")
    (d / "test-plan.md").write_text("[NEEDS CLARIFICATION: how?]\n", encoding="utf-8")
    with pytest.raises(FactoryError, match="NEEDS CLARIFICATION"):
        run("advance", "F-001", "implementing")
    fill_docs(d)
    assert run("advance", "F-001", "implementing") == 0
    assert load_item(d / "item.yaml")["status"] == "implementing"
    assert "FAIL" not in capsys.readouterr().out


def test_advance_full_lifecycle_and_pr(project):
    d = start_with_spec(project)
    set_status(project, "F-001", "implementing", approvals={"spec": APPROVAL, "plan": APPROVAL})
    fill_docs(d)
    assert run("advance", "F-001", "in-review", "--pr", "https://example.com/pr/1") == 0
    assert load_item(d / "item.yaml")["pr"] == "https://example.com/pr/1"
    for status in ("merged", "released", "done"):
        assert run("advance", "F-001", status) == 0
    with pytest.raises(FactoryError, match="already done"):
        run("advance", "F-001", "done")


def test_advance_prints_verify_problems_but_succeeds(project, capsys):
    d = start_with_spec(project)
    set_status(project, "F-001", "plan-approved", approvals={"spec": APPROVAL, "plan": APPROVAL})
    (d / "test-plan.md").write_text("tests\n", encoding="utf-8")
    (d / "plan.md").write_text("", encoding="utf-8")
    capsys.readouterr()
    assert run("advance", "F-001", "implementing") == 0
    assert "FAIL F-001: status is implementing but plan.md is missing or empty" in (
        capsys.readouterr().out
    )


def test_waived_plan_under_trusted_low(tmp_path, factory_root, monkeypatch, capsys):
    proj = make_project(tmp_path, autonomy="trusted")
    monkeypatch.chdir(proj)
    run("feature", "start", "Small thing", "--risk", "low", "--no-branch")
    run("feature", "start", "Big thing", "--risk", "medium", "--no-branch")
    for ident in ("F-001", "F-002"):
        set_status(proj, ident, "spec-approved", approvals={"spec": APPROVAL})
    capsys.readouterr()
    assert run("advance", "F-001", "plan-approved") == 0  # waived: no approval entry needed
    assert "FAIL" not in capsys.readouterr().out
    assert load_item(item_dir(proj, "F-001") / "item.yaml")["approvals"] == {"spec": APPROVAL}
    with pytest.raises(FactoryError, match="human gate"):
        run("advance", "F-002", "plan-approved")  # medium risk: plan still required
    # `approve plan` keeps working on a waived item
    set_status(proj, "F-001", "spec-approved")
    (item_dir(proj, "F-001") / "plan.md").write_text("p\n", encoding="utf-8")
    assert run("approve", "F-001", "plan", "--yes") == 0


def test_waived_plan_next_step_line(tmp_path, factory_root, monkeypatch, capsys):
    proj = make_project(tmp_path, autonomy="trusted")
    monkeypatch.chdir(proj)
    run("feature", "start", "Small", "--risk", "low", "--no-branch")
    set_status(proj, "F-001", "spec-approved", approvals={"spec": APPROVAL})
    capsys.readouterr()
    run("next", "F-001")
    assert "factory advance F-001 plan-approved" in capsys.readouterr().out


def test_bad_autonomy_is_a_user_error(tmp_path, factory_root, monkeypatch):
    proj = make_project(tmp_path, autonomy="yolo")
    monkeypatch.chdir(proj)
    run("feature", "start", "x", "--no-branch")
    set_status(proj, "F-001", "spec-approved", approvals={"spec": APPROVAL})
    with pytest.raises(FactoryError, match="autonomy"):
        run("advance", "F-001", "plan-approved")


# --- next --------------------------------------------------------------------------------------

EXPECTED_NEXT = {
    "draft": ["factory-spec"],
    "spec-approved": ["factory-plan"],
    "plan-approved": ["factory-test", "factory-implement"],
    "implementing": ["factory-implement"],
    "in-review": ["factory-review"],
    "merged": ["factory-release"],
    "released": ["factory-release"],
}


@pytest.mark.parametrize("status", STATUSES)
def test_next_prompt_per_status(project, capsys, status):
    run("feature", "start", "Add login", "--no-branch")
    set_status(project, "F-001", status)
    capsys.readouterr()
    assert run("next", "F-001") == 0
    out = capsys.readouterr().out
    if status == "done":
        assert "Nothing to do" in out
        return
    assert "work item docs/work/F-001-add-login/ (id F-001)" in out
    assert "Read item.yaml, spec.md and plan.md first." in out
    assert "Do not run 'factory approve'" in out
    for skill in EXPECTED_NEXT[status]:
        assert f"factory-{skill.split('-', 1)[1]}" in out
    human = {
        "draft": "Next human step: factory approve F-001 spec",
        "spec-approved": "Next human step: factory approve F-001 plan",
        "in-review": "Next human step: merge the PR",
    }
    if status in human:
        assert human[status] in out
    else:
        assert "Next human step" not in out


def test_next_for_bug_draft_uses_diagnose(project, capsys):
    run("bug", "start", "Crash", "--no-branch")
    capsys.readouterr()
    run("next", "B-001")
    assert "factory-diagnose" in capsys.readouterr().out
