"""Project charter (FACT-47): `docs/PROJECT.md`, its validator and evaluator, approval through a
`charter` decision record, and the doctor, status and `feature start` integration.

No network: a Jira lookup is a stub function; the registry and HOME are isolated by conftest.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
import yaml

from swfactory import charter, checks, cli, common, decisions, verify, work
from swfactory.common import FactoryError

ROOT = common.FACTORY_ROOT
TODAY = "2026-10-07"


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch):
    monkeypatch.setattr(common, "today", lambda: TODAY)


@pytest.fixture
def project(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / ".factory").mkdir(parents=True)
    (proj / ".factory" / "factory.yaml").write_text("autonomy: supervised\n", encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.name", "Test Owner"],
        ["config", "user.email", "t@example.com"],
    ):
        subprocess.run(["git", *args], cwd=proj, capture_output=True, check=True)
    monkeypatch.chdir(proj)
    return proj


def run(*argv):
    args = cli.build_parser().parse_args(list(argv))
    return int(args.func(args) or 0)


# --- builders ------------------------------------------------------------------------------

BODY = "# Charter\n\n## Maintenance mode\n\nOnly security and dependency updates are made.\n"


def criteria() -> list[dict]:
    return [
        {"id": "C1", "text": "The importer reads every sample file", "check": {"work": "FACT-12"}},
        {
            "id": "C2",
            "text": "The exporter writes the agreed format",
            "check": {"file": "docs/api.md"},
        },
        {
            "id": "C3",
            "text": "Recall on the reference set reaches the agreed bar",
            "check": {"metric": {"file": "docs/metrics.yaml", "key": "recall.value", "min": 0.9}},
        },
        {
            "id": "C4",
            "text": "The tracker ticket for the API is closed",
            "check": {"jira": "ADE-1"},
        },
    ]


def cmeta(**over) -> dict:
    base = {
        "purpose": "A small tool for recipes. It is not the next big platform.",
        "mode": "active",
        "decision": "D-002",
        "done": criteria(),
        "non_goals": ["A mobile app"],
        "parked": [
            {"item": "More exporters", "jira": None},
            {"item": "Dark mode", "jira": "ADE-9"},
        ],
    }
    base.update(over)
    return base


def charter_text(meta: dict | None = None, body: str = BODY) -> str:
    return "---\n" + yaml.safe_dump(meta or cmeta(), sort_keys=False) + "---\n" + body


def put_charter(project: Path, meta: dict | None = None, body: str = BODY, eol: str = "\n") -> Path:
    path = project / "docs" / "PROJECT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = charter_text(meta, body).replace("\n", eol)
    path.write_bytes(text.encode("utf-8"))
    return path


def put_record(project: Path, n: int = 2, **over) -> Path:
    m = {
        "id": f"D-{n:03d}",
        "type": "charter",
        "title": "Approve the project charter",
        "status": "proposed",
        "jira": "FACT-47",
        "proposed_by": "agent",
        "proposed_at": "2026-10-04",
        "options": [
            {"text": "Approve the charter in docs/PROJECT.md as written", "recommended": True}
        ],
        "decision": None,
        "by": None,
        "at": None,
        "delegated": False,
        "subject": "docs/PROJECT.md",
    }
    m.update(over)
    path = project / "docs" / "decisions" / f"D-{n:03d}-charter.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(m, sort_keys=False) + "---\n# Charter\n", encoding="utf-8"
    )
    return path


def approve(project: Path, meta: dict | None = None, eol: str = "\n") -> Path:
    """What the owner's `factory decide D-002 --accept` leaves behind."""
    doc = put_charter(project, meta, eol=eol)
    put_record(
        project,
        status="accepted",
        decision="Approve the charter in docs/PROJECT.md as written",
        by="The Owner",
        at="2026-10-05",
        subject_sha256=common.sha256_file(doc),
    )
    return doc


def put_item(project: Path, ident: str, status: str) -> None:
    folder = project / "docs" / "work" / f"{ident}-x"
    folder.mkdir(parents=True, exist_ok=True)
    item = {
        "id": ident,
        "type": "feature",
        "title": "x",
        "slug": "x",
        "status": status,
        "risk": "low",
        "jira": None,
        "branch": None,
        "created": "2026-10-01",
        "approvals": {},
        "pr": None,
    }
    (folder / "item.yaml").write_text(yaml.safe_dump(item), encoding="utf-8")


# --- the validator (AC2) -------------------------------------------------------------------


def test_a_good_charter_has_no_problems():
    assert charter.validate_charter(cmeta(), BODY) == []
    assert charter.validate_charter(cmeta(mode="maintenance"), BODY) == []
    assert charter.validate_charter(cmeta(decision=None, parked=[]), BODY) == []


def crit(i: int, text: str = "The importer reads every sample file", **check) -> dict:
    return {"id": f"C{i}", "text": text, "check": check or {"file": "docs/a.md"}}


def three(**over) -> list[dict]:
    return [crit(1), crit(2), crit(3)]


BAD = [
    ("no done list", cmeta(done=[]), "done must list 3 to 7 criteria"),
    ("done missing", {k: v for k, v in cmeta().items() if k != "done"}, "done must list 3 to 7"),
    ("two criteria", cmeta(done=three()[:2]), "done must list 3 to 7 criteria (found 2)"),
    ("eight criteria", cmeta(done=[crit(i) for i in range(1, 9)]), "(found 8)"),
    ("duplicate ids", cmeta(done=[crit(1), crit(1), crit(3)]), "duplicate criterion id 'C1'"),
    ("criterion not a mapping", cmeta(done=["x", crit(2), crit(3)]), "done[1] must be a mapping"),
    (
        "no id",
        cmeta(done=[{"text": "A real measurable thing", "check": {"file": "a"}}, crit(2), crit(3)]),
        "done[1] needs an id",
    ),
    (
        "no text",
        cmeta(done=[{"id": "C1", "check": {"file": "a"}}, crit(2), crit(3)]),
        "C1: text is missing",
    ),
    (
        "works well",
        cmeta(done=[crit(1, "The tool works well for everyone"), crit(2), crit(3)]),
        "C1: 'works well' is not measurable",
    ),
    (
        "user-friendly",
        cmeta(done=[crit(1, "A user-friendly editor ships"), crit(2), crit(3)]),
        "'user-friendly' is not measurable",
    ),
    (
        "robust",
        cmeta(done=[crit(1, "The parser is robust against input"), crit(2), crit(3)]),
        "'robust' is not measurable",
    ),
    (
        "too short",
        cmeta(done=[crit(1, "Done well"), crit(2), crit(3)]),
        "C1: text needs at least three words",
    ),
    (
        "no check",
        cmeta(
            done=[{"id": "C1", "text": "The importer reads every sample file"}, crit(2), crit(3)]
        ),
        "C1: check must be a mapping",
    ),
    (
        "two kinds",
        cmeta(done=[crit(1, work="F-1", file="a.md"), crit(2), crit(3)]),
        "C1: check needs exactly one of",
    ),
    (
        "unknown kind",
        cmeta(done=[crit(1, vibe="good"), crit(2), crit(3)]),
        "C1: check needs exactly one of",
    ),
    (
        "bad work id",
        cmeta(done=[crit(1, work="not an id"), crit(2), crit(3)]),
        "C1: work reference 'not an id'",
    ),
    (
        "bad jira key",
        cmeta(done=[crit(1, jira="adep"), crit(2), crit(3)]),
        "C1: jira reference 'adep'",
    ),
    (
        "absolute file",
        cmeta(done=[crit(1, file="/etc/passwd"), crit(2), crit(3)]),
        "C1: file must be a path inside the project",
    ),
    (
        "file climbs out",
        cmeta(done=[crit(1, file="../x"), crit(2), crit(3)]),
        "C1: file must be a path inside the project",
    ),
    (
        "metric without bound",
        cmeta(done=[crit(1, metric={"file": "m.yaml", "key": "a"}), crit(2), crit(3)]),
        "C1: metric needs exactly one of min, max, equals",
    ),
    (
        "metric two bounds",
        cmeta(
            done=[
                crit(1, metric={"file": "m.yaml", "key": "a", "min": 1, "max": 2}),
                crit(2),
                crit(3),
            ]
        ),
        "C1: metric needs exactly one of min, max, equals",
    ),
    (
        "metric bound not a number",
        cmeta(
            done=[crit(1, metric={"file": "m.yaml", "key": "a", "min": "high"}), crit(2), crit(3)]
        ),
        "C1: metric min must be a number",
    ),
    (
        "metric bound is a bool",
        cmeta(done=[crit(1, metric={"file": "m.yaml", "key": "a", "min": True}), crit(2), crit(3)]),
        "C1: metric min must be a number",
    ),
    (
        "metric without key",
        cmeta(done=[crit(1, metric={"file": "m.yaml", "min": 1}), crit(2), crit(3)]),
        "C1: metric needs a 'key'",
    ),
    (
        "metric file outside",
        cmeta(done=[crit(1, metric={"file": "../m.yaml", "key": "a", "min": 1}), crit(2), crit(3)]),
        "C1: metric file must be a path inside the project",
    ),
    ("no purpose", cmeta(purpose=""), "purpose is missing"),
    ("long purpose", cmeta(purpose="x" * 600), "purpose is longer than 400"),
    ("no non-goals", cmeta(non_goals=[]), "non_goals must list at least one"),
    ("non-goal not text", cmeta(non_goals=[3]), "non_goals[1] must be a non-empty string"),
    ("bad mode", cmeta(mode="sleeping"), "mode 'sleeping' is not one of active, maintenance"),
    ("bad decision id", cmeta(decision="2"), "decision must be a D-<number> or null"),
    ("parked not a list", cmeta(parked="later"), "parked must be a list"),
    ("parked entry bad", cmeta(parked=[{"jira": "ADE-1"}]), "parked[1] needs an 'item'"),
    (
        "parked jira bad",
        cmeta(parked=[{"item": "x", "jira": "nope"}]),
        "parked[1].jira 'nope' is not a Jira key",
    ),
]


@pytest.mark.parametrize(("case", "meta", "needle"), BAD, ids=[b[0] for b in BAD])
def test_validator_rejects(case, meta, needle):
    problems = charter.validate_charter(meta, BODY)
    assert any(needle in p for p in problems), problems


def test_validator_needs_the_maintenance_section_and_a_mapping():
    assert any("## Maintenance mode" in p for p in charter.validate_charter(cmeta(), "# Charter\n"))
    assert charter.validate_charter(["x"], BODY) == ["front matter must be a YAML mapping"]


def test_parse_never_raises_and_reports_why():
    meta, body, problems = charter.parse_charter(charter_text())
    assert problems == [] and meta["mode"] == "active" and "## Maintenance mode" in body
    assert charter.parse_charter("# nothing\n")[2][0].startswith("no YAML front matter")
    assert "not valid YAML" in charter.parse_charter("---\na: [\n---\n")[2][0]
    marked = charter_text(body=BODY + "<!-- factory:unfilled - x -->\n")
    assert any("still the template" in p for p in charter.parse_charter(marked)[2])
    crlf = charter_text().replace("\n", "\r\n")
    assert charter.parse_charter(crlf)[2] == []


# --- the evaluator (AC3) -------------------------------------------------------------------


def test_work_criterion(project):
    c = crit(1, work="FACT-12")
    assert charter.evaluate(c, project) == charter.NOT_MET  # no such item yet
    for status, want in (
        ("draft", charter.NOT_MET),
        ("in-review", charter.NOT_MET),
        ("merged", charter.MET),
        ("released", charter.MET),
        ("done", charter.MET),
    ):
        put_item(project, "FACT-12", status)
        assert charter.evaluate(c, project) == want, status


def test_file_criterion(project):
    c = crit(1, file="docs/api.md")
    assert charter.evaluate(c, project) == charter.NOT_MET
    (project / "docs").mkdir()
    (project / "docs" / "api.md").write_text("x", encoding="utf-8")
    assert charter.evaluate(c, project) == charter.MET


@pytest.mark.parametrize(
    ("bound", "value", "want"),
    [
        ({"min": 0.9}, 0.91, charter.MET),
        ({"min": 0.9}, 0.9, charter.MET),
        ({"min": 0.9}, 0.89, charter.NOT_MET),
        ({"max": 2}, 2, charter.MET),
        ({"max": 2}, 3, charter.NOT_MET),
        ({"equals": 19}, 19, charter.MET),
        ({"equals": 19}, 18, charter.NOT_MET),
    ],
)
def test_metric_criterion_bounds(project, bound, value, want):
    (project / "docs").mkdir()
    (project / "docs" / "metrics.yaml").write_text(
        yaml.safe_dump({"recall": {"value": value}}), encoding="utf-8"
    )
    c = crit(1, metric={"file": "docs/metrics.yaml", "key": "recall.value", **bound})
    assert charter.evaluate(c, project) == want


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not: [valid",
        "recall: {value: high}",
        "other: 1",
        "- a\n- b\n",
        "recall: {value: true}",
    ],
)
def test_metric_criterion_unknown_when_unreadable(project, content):
    (project / "docs").mkdir()
    if content is not None:
        (project / "docs" / "metrics.yaml").write_text(content, encoding="utf-8")
    c = crit(1, metric={"file": "docs/metrics.yaml", "key": "recall.value", "min": 1})
    assert charter.evaluate(c, project) == charter.UNKNOWN


def test_metric_reads_json(project):
    (project / "docs").mkdir()
    (project / "docs" / "m.json").write_text('{"score": 19}', encoding="utf-8")
    c = crit(1, metric={"file": "docs/m.json", "key": "score", "equals": 19})
    assert charter.evaluate(c, project) == charter.MET


def test_jira_criterion_uses_the_injected_lookup(project):
    c = crit(1, jira="ADE-1")
    assert charter.evaluate(c, project) == charter.UNKNOWN  # no lookup: offline
    assert charter.evaluate(c, project, lambda k: "Done") == charter.MET
    assert charter.evaluate(c, project, lambda k: "In Progress") == charter.NOT_MET
    assert charter.evaluate(c, project, lambda k: None) == charter.UNKNOWN


def test_evaluate_never_reads_outside_the_project(project, tmp_path):
    (tmp_path / "secret.yaml").write_text("a: 5\n", encoding="utf-8")
    c = crit(1, metric={"file": "../secret.yaml", "key": "a", "min": 1})
    assert charter.evaluate(c, project) == charter.UNKNOWN
    assert charter.evaluate(crit(1, file="../secret.yaml"), project) == charter.NOT_MET
    assert (
        charter.evaluate({"id": "C1", "text": "x y z", "check": "nonsense"}, project)
        == charter.UNKNOWN
    )


# --- approval state and doctor (AC2) -------------------------------------------------------


def state(project) -> str:
    return charter.charter_state(project).state


def test_state_absent_and_template(project):
    assert state(project) == "absent"
    (project / "docs").mkdir()
    shutil_copy = (ROOT / "kit" / "charter" / "PROJECT.md").read_text(encoding="utf-8")
    (project / "docs" / "PROJECT.md").write_text(shutil_copy, encoding="utf-8")
    assert state(project) == "template"


def test_state_invalid(project):
    put_charter(project, cmeta(done=[]))
    st = charter.charter_state(project)
    assert st.state == "invalid" and "done must list 3 to 7" in st.detail


def test_state_unapproved_reasons(project):
    put_charter(project, cmeta(decision=None))
    assert "no decision record" in charter.charter_state(project).detail
    put_charter(project)  # names D-002, which does not exist
    st = charter.charter_state(project)
    assert st.state == "unapproved" and "D-002 does not exist" in st.detail
    put_record(project, type="design", subject=None)
    assert "is not a charter decision" in charter.charter_state(project).detail
    put_record(project)  # proposed
    st = charter.charter_state(project)
    assert st.state == "unapproved" and "waiting for the owner" in st.detail
    put_record(project, status="rejected", by="The Owner", at="2026-10-05")
    assert "was rejected" in charter.charter_state(project).detail
    put_record(project, status="superseded", superseded_by="D-003")
    assert "is superseded" in charter.charter_state(project).detail
    (project / "docs" / "decisions" / "D-002-charter.md").write_text("broken\n", encoding="utf-8")
    assert "is invalid" in charter.charter_state(project).detail


def test_state_approved_and_changed(project):
    doc = approve(project)
    st = charter.charter_state(project)
    assert (st.state, st.mode, st.decision) == ("approved", "active", "D-002")
    doc.write_bytes(doc.read_bytes() + b"\nA late edit.\n")
    st = charter.charter_state(project)
    assert st.state == "changed" and "edited after D-002 was accepted" in st.detail


def test_state_approved_with_crlf_file(project):
    approve(project, eol="\r\n")
    assert state(project) == "approved"


def test_doctor_warns_without_an_approved_charter_and_is_clean_with_one(project):
    found = checks.check_charter(project)
    assert [(f.level, f.name) for f in found] == [(checks.WARN, "charter")]
    assert (
        "no approved charter" in found[0].detail and "docs/PROJECT.md is missing" in found[0].detail
    )
    put_charter(project, cmeta(done=[]))
    assert checks.check_charter(project)[0].level == checks.WARN
    approve(project)
    found = checks.check_charter(project)
    assert [(f.level, f.name) for f in found] == [(checks.OK, "charter")]
    assert "approved by D-002" in found[0].detail and "active" in found[0].detail
    assert not checks.failures(found)


def test_doctor_command_shows_the_charter_line(project, capsys):
    assert cli.main(["doctor", str(project)]) == 0
    assert "no approved charter" in capsys.readouterr().out
    approve(project)
    assert cli.main(["doctor", str(project)]) == 0
    out = capsys.readouterr().out
    assert "approved by D-002" in out and "no approved charter" not in out


# --- status (AC3) --------------------------------------------------------------------------


def lookup(key: str):
    return {"ADE-1": "Done"}.get(key)


def all_met(project: Path) -> None:
    put_item(project, "FACT-12", "merged")
    (project / "docs").mkdir(exist_ok=True)
    (project / "docs" / "api.md").write_text("x", encoding="utf-8")
    (project / "docs" / "metrics.yaml").write_text(
        yaml.safe_dump({"recall": {"value": 0.95}}), encoding="utf-8"
    )


def test_status_shows_progress_and_not_yet_ready(project, capsys):
    approve(project)
    put_item(project, "FACT-12", "merged")
    (project / "docs" / "metrics.yaml").write_text(
        yaml.safe_dump({"recall": {"value": 0.5}}), encoding="utf-8"
    )
    assert work.cmd_status(True, jira_status=lookup) == 0
    out = capsys.readouterr().out
    assert "charter: approved by D-002, active - done criteria: 2 of 4 met" in out
    lines = {ln.split()[0]: ln for ln in out.splitlines() if ln.startswith("  C")}
    assert "met  " in lines["C1"] and "(work FACT-12)" in lines["C1"]
    assert "not met" in lines["C2"] and "(file docs/api.md)" in lines["C2"]
    assert (
        "not met" in lines["C3"]
        and "(metric docs/metrics.yaml recall.value min 0.9)" in lines["C3"]
    )
    assert "met  " in lines["C4"] and "(jira ADE-1)" in lines["C4"]
    assert "ready for maintenance" not in out


def test_status_flips_to_ready_when_all_met(project, capsys):
    approve(project)
    all_met(project)
    work.cmd_status(True, jira_status=lookup)
    out = capsys.readouterr().out
    assert "done criteria: 4 of 4 met" in out
    assert "ready for maintenance mode: every done criterion is met" in out
    assert "charter decision" in out and "never run by an agent" in out


def test_an_unknown_criterion_keeps_it_from_flipping(project, capsys):
    approve(project)
    all_met(project)
    work.cmd_status(True)  # no Jira lookup: C4 is unknown
    out = capsys.readouterr().out
    assert "3 of 4 met" in out and "unknown" in out and "ready for maintenance" not in out


def test_status_in_maintenance_mode_prints_the_stop_rule(project, capsys):
    approve(project, cmeta(mode="maintenance"))
    work.cmd_status(True, jira_status=lookup)
    out = capsys.readouterr().out
    assert "maintenance mode" in out and "only security and dependency updates" in out
    assert "charter amendment" in out and "ready for maintenance" not in out


def test_status_prints_one_line_for_an_unapproved_charter_and_nothing_without(project, capsys):
    work.cmd_status(True)
    assert "charter" not in capsys.readouterr().out
    put_charter(project)
    work.cmd_status(True)
    out = capsys.readouterr().out
    assert "charter: no approved charter" in out and "C1" not in out


# --- feature start in maintenance mode (AC4) -----------------------------------------------


def test_feature_start_warns_in_maintenance_mode(project, capsys):
    approve(project, cmeta(mode="maintenance"))
    assert run("feature", "start", "Add a thing", "--jira", "FACT-9", "--no-branch") == 0
    out = capsys.readouterr().out
    assert "warning: this project is in maintenance mode (charter D-002)" in out
    assert "charter amendment" in out
    assert (project / "docs" / "work" / "FACT-9-add-a-thing" / "item.yaml").is_file()  # not a block


def test_no_warning_in_active_mode_or_for_a_bug(project, capsys):
    approve(project)
    run("feature", "start", "Add a thing", "--jira", "FACT-9", "--no-branch")
    assert "maintenance" not in capsys.readouterr().out
    approve(project, cmeta(mode="maintenance"))
    run("bug", "start", "Fix a thing", "--jira", "FACT-10", "--no-branch")
    assert "maintenance" not in capsys.readouterr().out


def test_no_warning_without_a_charter(project, capsys):
    run("feature", "start", "Add a thing", "--jira", "FACT-9", "--no-branch")
    assert "warning" not in capsys.readouterr().out


# --- the gate: decide on a charter record (AC6) ---------------------------------------------


def test_decide_accept_stamps_the_hash_and_approves(project):
    doc = put_charter(project)
    rec = put_record(project)
    assert run("decide", "D-002", "--accept", "--yes") == 0
    meta, _ = verify.load_decision(rec)
    assert meta["subject_sha256"] == common.sha256_file(doc) and meta["by"] == "Test Owner"
    assert state(project) == "approved"
    doc.write_text(doc.read_text(encoding="utf-8") + "edit\n", encoding="utf-8")
    assert state(project) == "changed"


@pytest.mark.parametrize(
    ("prep", "needle"),
    [
        ("missing", "docs/PROJECT.md does not exist"),
        ("invalid", "is not a valid charter"),
        ("other-record", "does not name D-002 in `decision`"),
        ("no-decision", "does not name D-002 in `decision`"),
    ],
)
def test_decide_refuses_a_charter_that_is_not_ready(project, prep, needle):
    if prep == "invalid":
        put_charter(project, cmeta(done=[]))
    elif prep == "other-record":
        put_charter(project, cmeta(decision="D-009"))
    elif prep == "no-decision":
        put_charter(project, cmeta(decision=None))
    rec = put_record(project)
    before = rec.read_bytes()
    with pytest.raises(FactoryError, match=needle):
        run("decide", "D-002", "--accept", "--yes")
    assert rec.read_bytes() == before


def test_a_charter_record_without_a_subject_fails_verify(project):
    put_record(project, subject=None)
    problems = verify.check_decisions(project)
    assert any("a charter decision needs subject: docs/PROJECT.md" in p for p in problems)
    put_record(project, subject="docs/OTHER.md")
    assert any("a charter decision needs subject" in p for p in verify.check_decisions(project))
    put_record(project)
    assert verify.check_decisions(project) == []


def test_reject_needs_no_valid_charter_and_is_never_delegated(project):
    rec = put_record(project)
    assert run("decide", "D-002", "--reject", "--note", "rework", "--yes") == 0
    assert verify.load_decision(rec)[0]["status"] == "rejected"
    put_charter(project)
    rec = put_record(project)
    with pytest.raises(FactoryError, match="never delegated to an agent"):
        run("decide", "D-002", "--accept", "--delegated", "The Owner", "--yes")
    assert verify.load_decision(rec)[0]["status"] == "proposed"


def test_an_agent_shell_cannot_approve_a_charter(project, monkeypatch):
    put_charter(project)
    rec = put_record(project)
    before = rec.read_bytes()
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    with pytest.raises(FactoryError, match="not a terminal"):
        run("decide", "D-002", "--accept")
    assert rec.read_bytes() == before and state(project) == "unapproved"


def test_decision_new_charter_scaffolds_the_record(project, capsys):
    assert run("decision", "new", "Approve the project charter", "--type", "charter") == 0
    rec = project / "docs" / "decisions" / "D-001-approve-the-project-charter.md"
    meta, _ = verify.load_decision(rec)
    assert meta["subject"] == "docs/PROJECT.md" and len(meta["options"]) == 1
    assert meta["options"][0]["recommended"] is True
    assert verify.validate_decision(meta, rec.name) == []
    assert (
        "decision: D-001" in capsys.readouterr().out
    )  # the hint to name the record in the charter


# --- the kit template (AC1) ----------------------------------------------------------------


def test_the_template_is_create_mode_and_a_draft():
    manifest = common.load_yaml(ROOT / "kit" / "manifest.yaml")
    entry = next(e for e in manifest["files"] if e["dest"] == "docs/PROJECT.md")
    assert entry["mode"] == "create" and entry.get("stack") is None
    assert (ROOT / manifest["templates"]["charter"]).is_file()
    text = (ROOT / entry["src"]).read_text(encoding="utf-8")
    meta, body = verify.split_front_matter(text)
    assert decisions.placeholder_marker(text) is not None
    assert "## Maintenance mode" in body and {"purpose", "mode", "done", "non_goals"} <= set(meta)
    # a template never passes as a charter, and never as an approved one
    assert any("still the template" in p for p in charter.parse_charter(text)[2])


def scratch(tmp_path: Path) -> Path:
    proj = tmp_path / "scratch"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True)
    (proj / "pyproject.toml").write_text('[project]\nname = "scratch"\n', encoding="utf-8")
    return proj


def test_adopt_creates_the_charter_and_sync_keeps_an_edited_copy(tmp_path):
    proj = scratch(tmp_path)
    assert cli.main(["adopt", str(proj)]) == 0
    doc = proj / "docs" / "PROJECT.md"
    assert doc.is_file() and state(proj) == "template"
    assert "docs/PROJECT.md" not in common.load_yaml(proj / ".factory" / "factory.yaml")["managed"]
    doc.write_text("my own charter\n", encoding="utf-8")
    assert cli.main(["sync", str(proj)]) == 0
    assert doc.read_text(encoding="utf-8") == "my own charter\n"
    assert cli.main(["sync", "--check", str(proj)]) == 0
    assert cli.main(["doctor", str(proj)]) in (0, 1)


# --- the factory's own charter (AC5) -------------------------------------------------------


def test_the_factory_charter_is_valid_and_its_record_names_it():
    doc = ROOT / "docs" / "PROJECT.md"
    meta, body, problems = charter.parse_charter(doc.read_text(encoding="utf-8"))
    assert problems == [], problems
    assert meta["mode"] == "active" and 5 <= len(meta["done"]) <= 7
    assert meta["parked"] and meta["non_goals"]
    rec = decisions.find_record(ROOT, meta["decision"])
    assert rec.type == "charter" and rec.meta["subject"] == "docs/PROJECT.md"
    assert rec.problems == () and verify.check_decisions(ROOT) == []
    # the proposal is the agent's; only the owner may have accepted it (by and at then present)
    assert rec.status in ("proposed", "accepted") and (rec.status == "proposed" or rec.meta["by"])
    st = charter.charter_state(ROOT)
    assert st.state in ("unapproved", "approved")
    assert st.state == "unapproved" or rec.status == "accepted"


def test_the_factory_charter_references_exist():
    meta, _, _ = charter.parse_charter((ROOT / "docs" / "PROJECT.md").read_text(encoding="utf-8"))
    for c in meta["done"]:
        kind, ref = next(iter(c["check"].items()))
        if kind == "file":
            assert (ROOT / ref).is_file(), ref
        if kind == "work":
            assert charter.evaluate(c, ROOT) in (charter.MET, charter.NOT_MET)  # a checkable ref


# --- text contracts (AC7) ------------------------------------------------------------------


def read(path: Path) -> str:
    return common.normalise_newlines(path.read_text(encoding="utf-8"))


def test_spec_skill_checks_proposed_work_against_the_charter():
    flat = " ".join(read(ROOT / "skills" / "factory-spec" / "SKILL.md").split())
    for needle in (
        "docs/PROJECT.md",
        "done criterion",
        "parked list",
        "charter amendment",
        "in scope",
        "maintenance mode",
    ):
        assert needle in flat, needle
    assert not checks.failures(checks.lint_skills(ROOT))


def test_workflow_policy_and_treaty_describe_the_charter():
    workflow = " ".join(read(ROOT / "skills" / "factory-workflow" / "SKILL.md").split())
    assert "docs/PROJECT.md" in workflow and "maintenance mode" in workflow
    autonomy = " ".join(read(ROOT / "policies" / "autonomy.md").split())
    assert "docs/PROJECT.md" in autonomy and "charter" in autonomy and "never delegated" in autonomy
    arch = read(ROOT / "docs" / "ARCHITECTURE.md")
    for needle in (
        "### 3.12 Project charter",
        "docs/PROJECT.md",
        "validate_charter",
        "maintenance mode",
        "subject_sha256",
        "ready for maintenance",
    ):
        assert needle in arch, needle


def test_the_warning_survives_an_edit_after_approval(project, capsys):
    doc = approve(project, cmeta(mode="maintenance"))
    doc.write_text(doc.read_text(encoding="utf-8") + "\nA late edit.\n", encoding="utf-8")
    assert state(project) == "changed"
    run("feature", "start", "Add a thing", "--jira", "FACT-9", "--no-branch")
    assert "maintenance mode (charter D-002)" in capsys.readouterr().out
    # but a charter that was never approved says nothing about maintenance
    (project / "docs" / "decisions" / "D-002-charter.md").unlink()
    run("feature", "start", "Another", "--jira", "FACT-10", "--no-branch")
    assert "maintenance" not in capsys.readouterr().out
