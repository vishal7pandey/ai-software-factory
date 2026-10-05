"""The CI gate: rules 1-4 of docs/ARCHITECTURE.md section 3.3, plus standalone-ness."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from swfactory import verify
from swfactory.verify import (
    STATUSES,
    audit_is_placeholder,
    check_project,
    required_approvals,
    validate_item,
    warn_project,
)

VERIFY_SRC = Path(verify.__file__)
APPROVAL = {"by": "Someone", "at": "2026-10-04"}


def make_item(item_id="F-001", slug="add-login", **over):
    item = {
        "id": item_id,
        "type": "feature",
        "title": "Add login",
        "slug": slug,
        "status": "draft",
        "risk": "medium",
        "jira": None,
        "branch": f"feature/{item_id.lower()}-{slug}",
        "created": "2026-10-04",
        "approvals": {},
        "pr": None,
    }
    item.update(over)
    return item


def write_item(root, item, docs=True):
    d = root / "docs" / "work" / f"{item['id']}-{item['slug']}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "item.yaml").write_text(yaml.safe_dump(item, sort_keys=False), encoding="utf-8")
    if docs:
        for name in ("spec.md", "plan.md", "test-plan.md"):
            (d / name).write_text("content\n", encoding="utf-8")
    return d


def full_approvals():
    return {"spec": APPROVAL, "plan": APPROVAL}


def set_autonomy(root, value):
    (root / ".factory").mkdir(exist_ok=True)
    (root / ".factory" / "factory.yaml").write_text(f"autonomy: {value}\n", encoding="utf-8")


# --- required_approvals ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("config", "risk", "expected"),
    [
        ({}, "low", ["spec", "plan"]),
        ({"autonomy": "supervised"}, "low", ["spec", "plan"]),
        ({"autonomy": "trusted"}, "low", ["spec"]),
        ({"autonomy": "trusted"}, "medium", ["spec", "plan"]),
        ({"autonomy": "trusted"}, "high", ["spec", "plan"]),
    ],
)
def test_required_approvals(config, risk, expected):
    assert required_approvals({"risk": risk}, config) == expected


def test_required_approvals_bad_autonomy():
    with pytest.raises(ValueError, match="autonomy"):
        required_approvals({"risk": "low"}, {"autonomy": "yolo"})


def test_statuses_order():
    assert STATUSES[0] == "draft" and STATUSES[-1] == "done" and len(STATUSES) == 8


# --- rule 1: schema ----------------------------------------------------------------------------


def test_valid_item_has_no_problems():
    assert validate_item(make_item(), "F-001-add-login") == []
    jira = make_item("PF-12", jira="PF-12", approvals=full_approvals())
    assert validate_item(jira, "PF-12-add-login") == []


@pytest.mark.parametrize(
    ("over", "needle"),
    [
        ({"status": "bogus"}, "status"),
        ({"type": "epic"}, "type"),
        ({"risk": "extreme"}, "risk"),
        ({"id": "F-002"}, "directory"),
        ({"id": "nonsense"}, "id"),
        ({"title": ""}, "title"),
        ({"created": "yesterday"}, "created"),
        ({"jira": "lowercase-1"}, "jira"),
        ({"approvals": {"spec": {"by": "x"}}}, "approvals.spec"),
        ({"approvals": {"deploy": APPROVAL}}, "unknown key"),
        ({"approvals": "yes"}, "approvals"),
        ({"pr": 5}, "pr"),
    ],
)
def test_schema_failures(over, needle):
    problems = validate_item(make_item(**over), "F-001-add-login")
    assert any(needle in p for p in problems), problems


DELEGATED = {"by": "Jane Doe (delegated to agent)", "at": "2026-10-04"}


def test_delegated_approval_forms():
    def problems(spec):
        return validate_item(make_item(approvals={"spec": spec}), "F-001-add-login")

    assert problems({**DELEGATED, "delegated": True}) == []  # the --delegated form
    assert problems(DELEGATED) == []  # the older hand-written form, no flag
    assert problems(APPROVAL) == []  # ordinary approval unchanged
    assert problems({**APPROVAL, "delegated": False}) == []
    assert any("must be true or false" in p for p in problems({**DELEGATED, "delegated": "yes"}))
    assert any("does not end with" in p for p in problems({**APPROVAL, "delegated": True}))
    assert verify.is_delegated({**DELEGATED, "delegated": True}) and verify.is_delegated(DELEGATED)
    assert not verify.is_delegated(APPROVAL) and not verify.is_delegated("nope")


def test_missing_required_field():
    item = make_item()
    del item["slug"]
    assert any("'slug'" in p for p in validate_item(item, "F-001-add-login"))


def test_non_mapping_item():
    assert validate_item([1, 2], "x") == ["item.yaml must be a YAML mapping"]


def test_check_project_flags_unparseable_and_invalid(tmp_path):
    d = tmp_path / "docs" / "work" / "F-001-bad"
    d.mkdir(parents=True)
    (d / "item.yaml").write_text("id: [oops\n", encoding="utf-8")
    write_item(tmp_path, make_item("F-002", "worse", status="bogus"))
    problems = check_project(tmp_path)
    assert any(p.startswith("F-001-bad: item.yaml:") for p in problems)
    assert any(p.startswith("F-002-worse: ") and "status" in p for p in problems)


def test_crlf_and_unquoted_dates_tolerated(tmp_path):
    d = write_item(tmp_path, make_item(), docs=False)
    text = (
        "id: F-001\ntype: feature\ntitle: Add login\nslug: add-login\nstatus: spec-approved\n"
        "risk: medium\njira: null\nbranch: null\ncreated: 2026-10-04\n"
        "approvals:\n  spec: {by: Me, at: 2026-10-04}\npr: null\n"
    )
    (d / "item.yaml").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    item = verify.load_item(d / "item.yaml")
    assert item["created"] == "2026-10-04" and item["approvals"]["spec"]["at"] == "2026-10-04"
    assert check_project(tmp_path) == []


def test_no_work_dir_is_fine(tmp_path):
    assert check_project(tmp_path) == []


# --- rule 2: approvals and docs ----------------------------------------------------------------


@pytest.mark.parametrize("status", STATUSES[1:])
def test_missing_spec_approval_fails_from_spec_approved_up(tmp_path, status):
    write_item(tmp_path, make_item(status=status, approvals={"plan": APPROVAL}))
    assert any("approvals.spec is missing" in p for p in check_project(tmp_path))


@pytest.mark.parametrize("status", STATUSES[2:])
def test_missing_plan_approval_fails_from_plan_approved_up(tmp_path, status):
    write_item(tmp_path, make_item(status=status, approvals={"spec": APPROVAL}))
    problems = check_project(tmp_path)
    assert any("approvals.plan is missing" in p for p in problems)
    assert not any("approvals.spec" in p for p in problems)


def test_spec_approved_needs_only_spec(tmp_path):
    write_item(tmp_path, make_item(status="spec-approved", approvals={"spec": APPROVAL}))
    assert check_project(tmp_path) == []


@pytest.mark.parametrize("status", STATUSES[3:])
@pytest.mark.parametrize("doc", ["spec.md", "plan.md", "test-plan.md"])
def test_docs_required_from_implementing_up(tmp_path, status, doc):
    d = write_item(tmp_path, make_item(status=status, approvals=full_approvals()))
    assert check_project(tmp_path) == []
    (d / doc).write_text("  \n", encoding="utf-8")
    assert any(f"{doc} is missing or empty" in p for p in check_project(tmp_path))
    (d / doc).unlink()
    assert any(f"{doc} is missing or empty" in p for p in check_project(tmp_path))


@pytest.mark.parametrize("doc", ["spec.md", "plan.md", "test-plan.md"])
def test_open_clarification_blocks_from_implementing_up(tmp_path, doc):
    d = write_item(tmp_path, make_item(status="implementing", approvals=full_approvals()))
    (d / doc).write_text("Q: [NEEDS CLARIFICATION: which IdP?]\n", encoding="utf-8")
    assert any("NEEDS CLARIFICATION" in p and doc in p for p in check_project(tmp_path))


def test_docs_not_required_before_implementing(tmp_path):
    write_item(tmp_path, make_item(status="plan-approved", approvals=full_approvals()), docs=False)
    assert check_project(tmp_path) == []


def test_waived_plan_under_trusted_low(tmp_path):
    set_autonomy(tmp_path, "trusted")
    approvals = {"spec": APPROVAL}
    write_item(tmp_path, make_item(risk="low", status="implementing", approvals=approvals))
    write_item(
        tmp_path,
        make_item("F-002", "other", risk="medium", status="implementing", approvals=approvals),
    )
    assert check_project(tmp_path) == [
        "F-002: status is implementing but approvals.plan is missing"
    ]


def test_supervised_does_not_waive_low_risk(tmp_path):
    set_autonomy(tmp_path, "supervised")
    write_item(
        tmp_path, make_item(risk="low", status="plan-approved", approvals={"spec": APPROVAL})
    )
    assert any("approvals.plan is missing" in p for p in check_project(tmp_path))


def test_bad_autonomy_in_config_is_reported(tmp_path):
    set_autonomy(tmp_path, "yolo")
    write_item(tmp_path, make_item())
    problems = check_project(tmp_path)
    assert len(problems) == 1 and problems[0].startswith("factory.yaml:")


# --- rule 3: branch ----------------------------------------------------------------------------


@pytest.mark.parametrize("status", STATUSES[:3])
def test_feature_branch_on_unapproved_item_fails(tmp_path, status):
    write_item(tmp_path, make_item(status=status, approvals=full_approvals()))
    problems = check_project(tmp_path, "feature/f-001-add-login")
    assert any("must be implementing or later" in p for p in problems)


@pytest.mark.parametrize("status", STATUSES[3:])
def test_feature_branch_on_implementing_item_passes(tmp_path, status):
    write_item(tmp_path, make_item(status=status, approvals=full_approvals()))
    assert check_project(tmp_path, "feature/f-001-add-login") == []


def test_fix_branch_and_jira_id(tmp_path):
    bug = {"type": "bug", "jira": "PF-9"}
    write_item(tmp_path, make_item("PF-9", "crash", status="draft", **bug))
    assert any("PF-9" in p for p in check_project(tmp_path, "fix/pf-9-crash"))
    write_item(
        tmp_path,
        make_item("PF-9", "crash", status="implementing", approvals=full_approvals(), **bug),
    )
    assert check_project(tmp_path, "fix/pf-9-crash") == []


def test_branch_without_work_item_fails(tmp_path):
    problems = check_project(tmp_path, "feature/f-007-ghost")
    assert problems == ["F-007: branch 'feature/f-007-ghost' has no valid work item in docs/work/"]


def test_branch_id_is_not_a_prefix_match(tmp_path):
    write_item(tmp_path, make_item("F-001", status="implementing", approvals=full_approvals()))
    assert any("F-0010" in p for p in check_project(tmp_path, "feature/f-0010-x"))


@pytest.mark.parametrize(
    "branch", ["main", "chore/f-001-cleanup", "docs/f-001-x", "deps/bump", "feature/no-id", None]
)
def test_exempt_branches(tmp_path, branch):
    write_item(tmp_path, make_item(status="draft"))
    assert check_project(tmp_path, branch) == []


# --- warnings: empty test-plan Audit (FACT-5) ---------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "# Test plan\n\n## Audit (after implementation)\n\n<!-- Filled after. -->\n",
            True,
        ),
        ("# Test plan\n\n## Audit (after implementation)\n\n   \n\n", True),
        ("# Test plan\n\n## Audit (after implementation)\nRed first, 3 mutations caught.\n", False),
        ("# Test plan\n\nNo Audit heading here.\n", False),
        ("# Test plan\n\n## Audit (after implementation)\n<!-- old --> still has text\n", False),
    ],
)
def test_audit_is_placeholder(text, expected):
    assert audit_is_placeholder(text) is expected


def test_warn_project_only_for_in_review_or_later_with_a_placeholder_audit(tmp_path):
    placeholder = "## Audit (after implementation)\n\n<!-- Filled after implementation. -->\n"
    filled = "## Audit (after implementation)\nRed first; 2 mutations caught.\n"

    d = write_item(tmp_path, make_item("F-001", status="implementing", approvals=full_approvals()))
    (d / "test-plan.md").write_text(placeholder, encoding="utf-8")
    assert warn_project(tmp_path) == []  # implementing: too early to warn

    d = write_item(
        tmp_path,
        make_item("F-002", slug="b", status="in-review", approvals=full_approvals(), pr="x"),
    )
    (d / "test-plan.md").write_text(placeholder, encoding="utf-8")
    warnings = warn_project(tmp_path)
    assert len(warnings) == 1
    assert warnings[0].startswith("F-002:") and "Audit" in warnings[0]

    d = write_item(
        tmp_path, make_item("F-003", slug="c", status="merged", approvals=full_approvals(), pr="x")
    )
    (d / "test-plan.md").write_text(filled, encoding="utf-8")
    assert warn_project(tmp_path) == [
        "F-002: status is in-review but the Audit section of "
        "test-plan.md is still the template placeholder"
    ]  # F-003 has a real audit: no new warning

    write_item(tmp_path, make_item("F-004", slug="d", status="draft"), docs=False)
    # no test-plan.md at all, and too early anyway: must not raise, must not warn
    assert "F-004" not in "\n".join(warn_project(tmp_path))


def test_run_with_only_a_warning_does_not_fail(tmp_path, capsys):
    d = write_item(
        tmp_path, make_item(status="in-review", approvals=full_approvals(), pr="https://example/1")
    )
    (d / "test-plan.md").write_text(
        "## Audit (after implementation)\n\n<!-- Filled after implementation. -->\n",
        encoding="utf-8",
    )
    assert verify.main(["--root", str(tmp_path), "--branch", "main"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("WARN F-001:") and "Audit" in out[0]
    assert out[-1] == "verify: OK (1 warning(s))"


def test_run_with_a_problem_and_a_warning_shows_both_and_still_fails(tmp_path, capsys):
    d = write_item(tmp_path, make_item(status="in-review"))  # missing approvals -> a real problem
    (d / "test-plan.md").write_text(
        "## Audit (after implementation)\n\n<!-- Filled after implementation. -->\n",
        encoding="utf-8",
    )
    assert verify.main(["--root", str(tmp_path), "--branch", "main"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert any(line.startswith("WARN F-001:") for line in out)
    assert any(line.startswith("FAIL F-001:") for line in out)
    assert re.fullmatch(r"verify: \d+ problem\(s\)", out[-1])  # never the warning-count form


# --- rule 4 / CLI output -----------------------------------------------------------------------


def test_main_output_and_exit_codes(tmp_path, capsys):
    write_item(tmp_path, make_item(status="spec-approved"))
    assert verify.main(["--root", str(tmp_path), "--branch", "main"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "FAIL F-001: status is spec-approved but approvals.spec is missing",
        "verify: 1 problem(s)",
    ]
    write_item(tmp_path, make_item(status="spec-approved", approvals={"spec": APPROVAL}))
    assert verify.main(["--root", str(tmp_path), "--branch", "main"]) == 0
    assert capsys.readouterr().out.splitlines() == ["verify: OK"]


def test_docs_only_changed_files(tmp_path, capsys):
    write_item(tmp_path, make_item(status="draft"))
    branch = "feature/f-001-add-login"
    strict = check_project(tmp_path, branch)
    assert any("must be implementing or later" in p for p in strict)  # no list: unchanged

    docs = ["docs/work/F-001-add-login/spec.md", "./docs/work/F-001-add-login/item.yaml"]
    assert check_project(tmp_path, branch, docs) == []
    assert check_project(tmp_path, branch, []) == []  # nothing changed: nothing rides on the spec
    assert check_project(tmp_path, branch, [*docs, "src/app.py"]) == strict
    assert (
        check_project(tmp_path, branch, ["docs/work-notes/x.md"]) == strict
    )  # prefix, not substring
    windows = ["docs\\work\\F-001-add-login\\spec.md"]
    assert check_project(tmp_path, branch, windows) == []

    # a docs-only branch still needs its item
    assert any("no valid work item" in p for p in check_project(tmp_path, "feature/f-009-x", docs))

    # through the CLI: the file of changed paths
    lst = tmp_path / "changed.txt"

    def cli(listfile) -> int:
        argv = ["--root", str(tmp_path), "--branch", branch, "--changed-files-from", str(listfile)]
        return verify.main(argv)

    lst.write_text("\n".join(docs) + "\n", encoding="utf-8")
    assert cli(lst) == 0
    lst.write_text("src/app.py\n", encoding="utf-8")
    assert cli(lst) == 1
    assert "must be implementing or later" in capsys.readouterr().out
    lst.write_text("", encoding="utf-8")
    assert cli(lst) == 0
    # an unreadable list is not trusted: the strict rule applies
    assert cli(tmp_path / "nope.txt") == 1


def test_branch_defaults_to_current_git_branch(tmp_path, capsys):
    write_item(tmp_path, make_item(status="draft"))
    subprocess.run(["git", "init", "-q", "-b", "feature/f-001-add-login"], cwd=tmp_path, check=True)
    assert verify.main(["--root", str(tmp_path)]) == 1
    assert "must be implementing or later" in capsys.readouterr().out


def test_standalone_script_runs_without_swfactory(tmp_path):
    """The copy lives alone in a project: no swfactory importable, only stdlib + PyYAML."""
    proj = tmp_path / "proj"
    (proj / ".factory").mkdir(parents=True)
    copy = proj / ".factory" / "verify.py"
    shutil.copy(VERIFY_SRC, copy)
    lines = copy.read_text(encoding="utf-8").splitlines()
    imports = [ln for ln in lines if ln.startswith(("import ", "from "))]
    assert not any("swfactory" in ln for ln in imports)
    write_item(proj, make_item(status="spec-approved"))

    # -S drops site-packages (and with it the editable swfactory install); PyYAML is added back.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = str(Path(yaml.__file__).parent.parent)
    run = [sys.executable, "-S", str(copy), "--root", str(proj), "--branch", "main"]
    bad = subprocess.run(run, capture_output=True, text=True, env=env, cwd=tmp_path)
    assert bad.returncode == 1, bad.stderr
    assert "FAIL F-001" in bad.stdout and bad.stdout.strip().endswith("verify: 1 problem(s)")

    write_item(proj, make_item(status="spec-approved", approvals={"spec": APPROVAL}))
    ok = subprocess.run(run, capture_output=True, text=True, env=env, cwd=tmp_path)
    assert ok.returncode == 0 and ok.stdout.strip() == "verify: OK"

    probe = [sys.executable, "-S", "-c", "import swfactory"]
    lacks = subprocess.run(probe, capture_output=True, text=True, env=env, cwd=tmp_path)
    assert lacks.returncode != 0  # the environment really has no swfactory
