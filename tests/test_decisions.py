"""Owner decisions as a first-class gate (FACT-46): records, `decide`, `decision new`, the waiting
block in `status` and `doctor`, `inbox`, the verify rule, and the text that routes agents to them.

Three kinds of test: pure validator tests; command tests in a scratch adopted project (no network,
`today` pinned); contract tests that read the real kit, skills, policies and Treaty.
"""

from __future__ import annotations

import io
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml

from swfactory import checks, cli, common, decisions, installer, verify, work
from swfactory.common import FactoryError

ROOT = common.FACTORY_ROOT
TODAY = "2026-10-07"


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch):
    monkeypatch.setattr(common, "today", lambda: TODAY)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def project(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / ".factory").mkdir(parents=True)
    (proj / ".factory" / "factory.yaml").write_text("autonomy: supervised\n", encoding="utf-8")
    _git(proj, "init", "-q", "-b", "main")
    _git(proj, "config", "user.name", "Test Owner")
    _git(proj, "config", "user.email", "t@example.com")
    monkeypatch.chdir(proj)
    return proj


def run(*argv):
    """Like cli.main but lets FactoryError propagate so tests can assert on it."""
    args = cli.build_parser().parse_args(list(argv))
    return int(args.func(args) or 0)


def meta(n: int = 1, **over) -> dict:
    base = {
        "id": f"D-{n:03d}",
        "type": "design",
        "title": "Pick a cache",
        "status": "proposed",
        "jira": "FACT-1",
        "proposed_by": "agent",
        "proposed_at": "2026-10-04",
        "options": [{"text": "Use redis", "recommended": True}, {"text": "Use memcached"}],
        "decision": None,
        "by": None,
        "at": None,
        "delegated": False,
    }
    base.update(over)
    return base


BODY = "# Pick a cache\n\n## Context\n\nWe need one.\n\n## Options\n\nRedis or memcached.\n"


def record_text(m: dict, body: str = BODY) -> str:
    return "---\n" + yaml.safe_dump(m, sort_keys=False) + "---\n" + body


def put(project: Path, n: int = 1, slug: str = "pick-a-cache", body: str = BODY, **over) -> Path:
    path = project / "docs" / "decisions" / f"D-{n:03d}-{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record_text(meta(n, **over), body), encoding="utf-8", newline="\n")
    return path


def accepted(n: int = 1, **over) -> dict:
    base = {"status": "accepted", "decision": "Use redis", "by": "Test Owner", "at": "2026-10-05"}
    return meta(n, **{**base, **over})


# --- the pure validator (AC4) --------------------------------------------------------------


@pytest.mark.parametrize(
    "m",
    [
        meta(),
        accepted(),
        meta(status="rejected", by="Test Owner", at="2026-10-05", note="no"),
        meta(status="superseded", superseded_by="D-002"),
        meta(jira=None),
        accepted(delegated=True, by="Vishal (delegated to agent)"),
        meta(
            type="dismissal",
            alert="https://github.com/o/r/security/code-scanning/52",
            reason="used in tests",
        ),
        accepted(subject="docs/PROJECT.md", subject_sha256="a" * 64),
    ],
)
def test_valid_records_have_no_problems(m):
    assert verify.validate_decision(m, f"{m['id']}-x.md") == []


BAD = [
    ("accepted without by", accepted(by=None), "'by' is missing"),
    ("accepted with blank by", accepted(by="  "), "'by' is missing"),
    ("accepted without at", accepted(at=None), "'at' is missing"),
    ("accepted with a bad date", accepted(at="5 Oct"), "'at' is missing or not YYYY-MM-DD"),
    ("accepted, decision not an option", accepted(decision="Use nothing"), "not the text of one"),
    ("rejected without by", meta(status="rejected", at="2026-10-05"), "'by' is missing"),
    ("proposed already answered", meta(decision="Use redis"), "status is proposed but 'decision'"),
    ("proposed with by", meta(by="Test Owner"), "status is proposed but 'by' is set"),
    (
        "rejected with a decision",
        meta(status="rejected", by="x", at="2026-10-05", decision="Use redis"),
        "status is rejected but 'decision'",
    ),
    ("no options", meta(options=[]), "options must be a non-empty list"),
    ("option without text", meta(options=[{"recommended": True}]), "options[1] must be a mapping"),
    (
        "two recommended",
        meta(options=[{"text": "a", "recommended": True}, {"text": "b", "recommended": True}]),
        "at most one",
    ),
    ("none recommended", meta(options=[{"text": "a"}, {"text": "b"}]), "needs one recommended"),
    (
        "recommended not boolean",
        meta(options=[{"text": "a", "recommended": "yes"}]),
        "must be true or false",
    ),
    (
        "duplicate option texts",
        meta(options=[{"text": "a", "recommended": True}, {"text": "a"}]),
        "must be distinct",
    ),
    ("id does not match the file", meta(id="D-009"), "does not match file name"),
    ("id not D-n", meta(id="X-1"), "is not D-<number>"),
    ("bad status", meta(status="maybe"), "status 'maybe' is not one of"),
    ("bad type", meta(type="wish"), "type 'wish' is not one of"),
    ("no title", meta(title=""), "missing required field 'title'"),
    ("no proposed_by", meta(proposed_by=None), "missing required field 'proposed_by'"),
    (
        "bad proposed_at",
        meta(proposed_at="yesterday"),
        "proposed_at 'yesterday' is not an ISO date",
    ),
    ("bad jira", meta(jira="fact 1"), "is not a Jira key or null"),
    ("delegated not boolean", accepted(delegated="yes"), "delegated must be true or false"),
    (
        "delegated without the wording",
        accepted(delegated=True),
        "does not end with ' (delegated to agent)'",
    ),
    (
        "delegated charter",
        accepted(type="charter", delegated=True, by="V (delegated to agent)"),
        "charter decision is never delegated",
    ),
    (
        "delegated by wording on a dismissal",
        accepted(
            type="dismissal", alert="https://x/1", reason="won't fix", by="V (delegated to agent)"
        ),
        "dismissal decision is never delegated",
    ),
    ("dismissal without alert", meta(type="dismissal", reason="won't fix"), "needs 'alert'"),
    (
        "dismissal with a bad reason",
        meta(type="dismissal", alert="https://x/1", reason="too hard"),
        "needs 'reason'",
    ),
    (
        "accepted subject without sha",
        accepted(subject="docs/PROJECT.md"),
        "'subject_sha256' is not a sha256",
    ),
    (
        "subject outside the project",
        meta(subject="../x.md"),
        "subject must be a path inside the project",
    ),
    ("absolute subject", meta(subject="/etc/passwd"), "subject must be a path inside the project"),
    (
        "superseded without pointer",
        meta(status="superseded"),
        "'superseded_by' is not a D-<number>",
    ),
]


@pytest.mark.parametrize(("case", "m", "needle"), BAD, ids=[b[0] for b in BAD])
def test_validator_rejects(case, m, needle):
    problems = verify.validate_decision(m, f"{meta()['id']}-x.md")
    assert any(needle in p for p in problems), problems


def test_validator_rejects_a_non_mapping():
    assert verify.validate_decision(["x"], "D-001-x.md") == ["front matter must be a YAML mapping"]


def test_front_matter_parser_errors_and_crlf():
    with pytest.raises(ValueError, match="no YAML front matter"):
        verify.split_front_matter("# just a heading\n")
    with pytest.raises(ValueError, match="not valid YAML"):
        verify.split_front_matter("---\nk: [unclosed\n---\nbody\n")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        verify.split_front_matter("---\n- a\n- b\n---\nbody\n")
    m, body = verify.split_front_matter("---\r\nid: D-001\r\nat: 2026-10-05\r\n---\r\nbody\r\n")
    assert m == {"id": "D-001", "at": "2026-10-05"} and body == "body\n"  # dates stay ISO strings


# --- verify rule 6 (AC4) -------------------------------------------------------------------


def test_verify_ok_for_valid_records_and_ignores_adrs_and_templates(project):
    put(project, 1)
    put(project, 2, slug="done", status="accepted", decision="Use redis", by="O", at="2026-10-05")
    folder = project / "docs" / "decisions"
    (folder / "001-an-adr.md").write_text("# ADR-001\n\n**Status:** accepted\n", encoding="utf-8")
    (folder / "TEMPLATE.md").write_text("no front matter, not a record\n", encoding="utf-8")
    (folder / "README.md").write_text("readme\n", encoding="utf-8")
    assert verify.check_decisions(project) == []
    assert verify.check_project(project) == []


def test_verify_fails_accepted_without_approver_and_date(project, capsys):
    put(project, 1, status="accepted", decision="Use redis")  # no by, no at
    assert verify.main(["--root", str(project)]) == 1
    out = capsys.readouterr().out
    assert "FAIL D-001: status is accepted but 'by' is missing" in out
    assert "FAIL D-001: status is accepted but 'at' is missing or not YYYY-MM-DD" in out
    assert "verify: 2 problem(s)" in out


def test_verify_reports_unparseable_and_duplicate_records(project):
    folder = project / "docs" / "decisions"
    folder.mkdir(parents=True)
    (folder / "D-001-broken.md").write_text("# no front matter\n", encoding="utf-8")
    put(project, 2, slug="a")
    (folder / "D-002-b.md").write_text(record_text(meta(2)), encoding="utf-8")
    problems = verify.check_decisions(project)
    assert any(p.startswith("D-001: D-001-broken.md: no YAML front matter") for p in problems)
    assert any(p.startswith("D-002: duplicate id in D-002-a.md and D-002-b.md") for p in problems)


def test_verify_reads_crlf_records(project):
    path = put(project, 1)
    path.write_bytes(path.read_text(encoding="utf-8").replace("\n", "\r\n").encode())
    assert verify.check_decisions(project) == []


# --- decide (AC1) --------------------------------------------------------------------------


def test_decide_accepts_the_recommended_option_and_keeps_the_body(project, capsys):
    path = put(project)
    before_meta, before_body = verify.load_decision(path)
    assert run("decide", "D-001", "--accept", "--yes") == 0
    m, body = verify.load_decision(path)
    assert (m["status"], m["decision"], m["by"], m["at"], m["delegated"]) == (
        "accepted",
        "Use redis",
        "Test Owner",
        TODAY,
        False,
    )
    assert body == before_body
    assert {k: v for k, v in m.items() if k not in ("status", "decision", "by", "at")} == {
        k: v for k, v in before_meta.items() if k not in ("status", "decision", "by", "at")
    }
    assert verify.validate_decision(m, path.name) == []
    assert "D-001: accepted by Test Owner" in capsys.readouterr().out
    assert "\r" not in path.read_text(encoding="utf-8")


def test_decide_option_picks_by_number(project):
    path = put(project)
    assert run("decide", "d-001", "--accept", "--option", "2", "--yes") == 0
    assert verify.load_decision(path)[0]["decision"] == "Use memcached"


def test_decide_reject_with_note(project):
    path = put(project)
    assert run("decide", "D-001", "--reject", "--note", "not now", "--yes") == 0
    m, _ = verify.load_decision(path)
    assert (m["status"], m["decision"], m["note"], m["by"], m["at"]) == (
        "rejected",
        None,
        "not now",
        "Test Owner",
        TODAY,
    )
    assert verify.validate_decision(m, path.name) == []


def test_decide_accepts_by_file_stem(project):
    put(project)
    assert run("decide", "D-001-pick-a-cache", "--accept", "--yes") == 0


@pytest.mark.parametrize("status", ["accepted", "rejected", "superseded"])
def test_decide_refuses_a_record_that_is_not_proposed(project, status):
    extra = {"superseded_by": "D-002"} if status == "superseded" else {}
    path = put(
        project,
        status=status,
        decision="Use redis" if status == "accepted" else None,
        by="Someone" if status != "superseded" else None,
        at="2026-10-05" if status != "superseded" else None,
        **extra,
    )
    before = path.read_bytes()
    with pytest.raises(FactoryError, match=f"already {status}"):
        run("decide", "D-001", "--accept", "--yes")
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "marker",
    [
        "<!-- factory:unfilled - delete this line -->",
        "[NEEDS CLARIFICATION: which cache?]",
        "REPLACE_ME: write the evidence",
        "the id is {{id}}",
    ],
)
def test_decide_refuses_templates_and_placeholders(project, marker):
    path = put(project, body=BODY + "\n" + marker + "\n")
    before = path.read_bytes()
    with pytest.raises(FactoryError, match="still contains"):
        run("decide", "D-001", "--accept", "--yes")
    assert path.read_bytes() == before


def test_decide_refuses_an_invalid_record(project):
    path = put(project, options=[])
    before = path.read_bytes()
    with pytest.raises(FactoryError, match="invalid record"):
        run("decide", "D-001", "--accept", "--yes")
    assert path.read_bytes() == before


@pytest.mark.parametrize("option", ["0", "3", "-1"])
def test_decide_refuses_an_option_out_of_range(project, option):
    path = put(project)
    before = path.read_bytes()
    with pytest.raises(FactoryError, match="--option must be 1 to 2"):
        run("decide", "D-001", "--accept", "--option", option, "--yes")
    assert path.read_bytes() == before


def test_decide_option_only_applies_to_accept(project):
    put(project)
    with pytest.raises(FactoryError, match="--option only applies to --accept"):
        run("decide", "D-001", "--reject", "--option", "1", "--yes")


def test_decide_unknown_and_ambiguous_ids(project):
    with pytest.raises(FactoryError, match="no decision record 'D-009'"):
        run("decide", "D-009", "--accept", "--yes")
    put(project, 1, slug="a")
    (project / "docs" / "decisions" / "D-001-b.md").write_text(
        record_text(meta(1)), encoding="utf-8"
    )
    with pytest.raises(FactoryError, match="ambiguous"):
        run("decide", "D-001", "--accept", "--yes")


def test_decide_stamps_the_subject_hash(project):
    (project / "docs").mkdir(exist_ok=True)
    (project / "docs" / "PROJECT.md").write_text(
        "charter\r\ntext\r\n", encoding="utf-8", newline=""
    )
    path = put(project, subject="docs/PROJECT.md")
    assert run("decide", "D-001", "--accept", "--yes") == 0
    m, _ = verify.load_decision(path)
    assert m["subject_sha256"] == common.sha256_text("charter\ntext\n")
    assert verify.validate_decision(m, path.name) == []


def test_decide_refuses_a_missing_subject(project):
    path = put(project, subject="docs/PROJECT.md")
    before = path.read_bytes()
    with pytest.raises(FactoryError, match="subject docs/PROJECT.md does not exist"):
        run("decide", "D-001", "--accept", "--yes")
    assert path.read_bytes() == before


# --- an agent does not decide on its own (AC6) ---------------------------------------------


class FakeTty(io.StringIO):
    def isatty(self):
        return True


def test_decide_without_yes_on_a_non_terminal_is_refused(project, monkeypatch):
    path = put(project)
    before = path.read_bytes()
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))  # what an agent's shell looks like
    with pytest.raises(FactoryError, match="not a terminal"):
        run("decide", "D-001", "--accept")
    assert path.read_bytes() == before


def test_decide_interactive_confirmation(project, monkeypatch, capsys):
    path = put(project)
    before = path.read_bytes()
    monkeypatch.setattr("sys.stdin", FakeTty("n\n"))
    assert run("decide", "D-001", "--accept") == 1
    assert "Not decided." in capsys.readouterr().out and path.read_bytes() == before
    monkeypatch.setattr("sys.stdin", FakeTty("y\n"))
    assert run("decide", "D-001", "--accept", "--option", "2") == 0
    assert verify.load_decision(path)[0]["decision"] == "Use memcached"


@pytest.mark.parametrize("argv", [["D-001"], ["D-001", "--accept", "--reject"]])
def test_decide_needs_exactly_one_of_accept_or_reject(project, argv, capsys):
    path = put(project)
    before = path.read_bytes()
    with pytest.raises(SystemExit) as exc:
        run("decide", *argv, "--yes")
    assert exc.value.code == 2 and path.read_bytes() == before


def test_decide_function_refuses_both_or_neither(project):
    put(project)
    with pytest.raises(FactoryError, match="exactly one of --accept or --reject"):
        decisions.cmd_decide("D-001", accept=False, reject=False, yes=True)
    with pytest.raises(FactoryError, match="exactly one of --accept or --reject"):
        decisions.cmd_decide("D-001", accept=True, reject=True, yes=True)


@pytest.mark.parametrize("dtype", ["charter", "dismissal"])
def test_delegated_is_refused_for_never_delegated_types(project, dtype):
    extra = {"alert": "https://x/1", "reason": "won't fix"} if dtype == "dismissal" else {}
    path = put(project, type=dtype, **extra)
    before = path.read_bytes()
    with pytest.raises(FactoryError, match="never delegated to an agent"):
        run("decide", "D-001", "--accept", "--delegated", "The Owner", "--yes")
    assert path.read_bytes() == before


def test_delegated_form_for_a_design_record(project):
    path = put(project)
    assert run("decide", "D-001", "--accept", "--delegated", "The Owner", "--yes") == 0
    m, _ = verify.load_decision(path)
    assert m["by"] == "The Owner (delegated to agent)" and m["delegated"] is True
    assert verify.validate_decision(m, path.name) == []


@pytest.mark.parametrize("name", ["", "   "])
def test_delegated_needs_a_name(project, name):
    put(project)
    with pytest.raises(FactoryError, match="--delegated needs the name"):
        run("decide", "D-001", "--accept", "--delegated", name, "--yes")


def snapshot_records(project: Path) -> dict[str, bytes]:
    folder = project / "docs" / "decisions"
    return {p.name: p.read_bytes() for p in sorted(folder.glob("*.md"))}


def test_read_only_commands_never_decide(project, tmp_path, monkeypatch, capsys):
    put(project, 1)
    put(project, 2, slug="other", type="other")
    (project / ".factory" / "templates" / "work").mkdir(parents=True)
    reg = tmp_path / "reg.yaml"
    reg.write_text(
        yaml.safe_dump({"projects": [{"name": "proj"}], "paths": {"proj": str(project)}})
    )
    monkeypatch.setenv("FACTORY_REGISTRY", str(reg))
    before = snapshot_records(project)
    run("status")
    run("inbox")
    cli.main(["doctor", str(project)])
    run("feature", "start", "Something", "--jira", "FACT-9", "--no-branch")
    run("next", "FACT-9")
    assert snapshot_records(project) == before
    assert "status: proposed" in next(iter(before.values())).decode()


@pytest.mark.parametrize("status", verify.STATUSES)
def test_handoff_prompts_never_tell_the_agent_to_decide(status):
    item = {"id": "F-001", "type": "feature", "status": status, "title": "t", "risk": "low"}
    prompt, human = work.build_prompt(item, Path("docs/work/F-001-t"), {"autonomy": "supervised"})
    assert "factory decide" not in prompt + (human or "")


# --- decision new (AC7) --------------------------------------------------------------------


def test_new_scaffolds_valid_draft_records_with_increasing_ids(project, capsys):
    assert run("decision", "new", "Pick a cache!", "--type", "design", "--jira", "FACT-1") == 0
    first = project / "docs" / "decisions" / "D-001-pick-a-cache.md"
    assert first.is_file() and "docs/decisions/D-001-pick-a-cache.md" in capsys.readouterr().out
    m, body = verify.load_decision(first)
    assert (m["id"], m["type"], m["status"], m["jira"], m["proposed_at"], m["proposed_by"]) == (
        "D-001",
        "design",
        "proposed",
        "FACT-1",
        TODAY,
        "agent",
    )
    assert body.startswith("# Pick a cache!") and "factory:unfilled" in body
    assert verify.validate_decision(m, first.name) == []
    assert verify.check_decisions(project) == []
    assert run("decision", "new", "Second", "--type", "other", "--by", "Claude") == 0
    second = project / "docs" / "decisions" / "D-002-second.md"
    assert verify.load_decision(second)[0]["proposed_by"] == "Claude"
    with pytest.raises(FactoryError, match="still contains 'factory:unfilled'"):
        run("decide", "D-001", "--accept", "--yes")  # a scaffold is a draft until it is written


def test_new_record_becomes_decidable_once_written(project):
    run("decision", "new", "Pick a cache", "--type", "design")
    path = project / "docs" / "decisions" / "D-001-pick-a-cache.md"
    m, body = verify.load_decision(path)
    m["options"] = [{"text": "Use redis", "recommended": True}, {"text": "Use memcached"}]
    clean = "\n".join(ln for ln in body.splitlines() if "factory:unfilled" not in ln)
    clean = "\n".join(ln for ln in clean.splitlines() if "REPLACE_ME" not in ln) + "\n"
    path.write_text(record_text(m, clean), encoding="utf-8", newline="\n")
    assert run("decide", "D-001", "--accept", "--yes") == 0


def test_new_dismissal_carries_alert_reason_and_options(project):
    url = "https://github.com/o/r/security/code-scanning/52"
    assert (
        run(
            "decision",
            "new",
            "Dismiss alert 52",
            "--type",
            "dismissal",
            "--jira",
            "CPID-41",
            "--alert",
            url,
            "--reason",
            "used in tests",
        )
        == 0
    )
    path = project / "docs" / "decisions" / "D-001-dismiss-alert-52.md"
    m, _ = verify.load_decision(path)
    assert (m["alert"], m["reason"]) == (url, "used in tests")
    assert m["options"][0] == {"text": "Dismiss the alert as 'used in tests'", "recommended": True}
    assert len(m["options"]) == 2 and verify.validate_decision(m, path.name) == []


@pytest.mark.parametrize(
    ("extra", "needle"),
    [
        ([], "a dismissal needs --alert"),
        (["--alert", "https://x/1"], "a dismissal needs --alert"),
        (["--alert", "https://x/1", "--reason", "too hard"], "--reason must be one of"),
        (["--alert", "not a url", "--reason", "won't fix"], "--alert must be an http"),
    ],
)
def test_new_dismissal_needs_alert_and_an_allowed_reason(project, extra, needle):
    with pytest.raises(FactoryError, match=needle):
        run("decision", "new", "Dismiss", "--type", "dismissal", *extra)
    assert not (project / "docs" / "decisions").exists()


def test_new_refuses_alert_flags_on_other_types_and_empty_titles(project):
    with pytest.raises(FactoryError, match="only apply to --type dismissal"):
        run("decision", "new", "X", "--type", "design", "--alert", "https://x/1")
    with pytest.raises(FactoryError, match="title must not be empty"):
        run("decision", "new", "  ", "--type", "design")
    with pytest.raises(FactoryError, match="invalid Jira key"):
        run("decision", "new", "X", "--type", "design", "--jira", "nope")


def test_a_broken_record_still_reserves_its_id(project):
    folder = project / "docs" / "decisions"
    folder.mkdir(parents=True)
    keep = folder / "D-004-broken.md"
    keep.write_text("not a record\n", encoding="utf-8")
    run("decision", "new", "Next", "--type", "other")
    assert (folder / "D-005-next.md").is_file() and keep.read_text(
        encoding="utf-8"
    ) == "not a record\n"


# --- status, doctor (AC2) ------------------------------------------------------------------


def test_status_lists_waiting_records(project, capsys):
    put(project, 1)
    put(project, 2, slug="done", status="accepted", decision="Use redis", by="O", at="2026-10-05")
    assert run("status") == 0
    out = capsys.readouterr().out
    assert "waiting for the owner (1 decision):" in out
    line = next(ln for ln in out.splitlines() if "D-001" in ln)
    assert line == "  D-001  design  3 days  Pick a cache  recommended: Use redis"
    assert "D-002" not in out
    assert "never run by an agent" in out


def test_status_is_silent_when_nothing_waits(project, capsys):
    assert run("status") == 0
    assert "waiting for the owner" not in capsys.readouterr().out
    put(project, 2, status="rejected", by="O", at="2026-10-05")
    assert run("status") == 0
    assert "waiting for the owner" not in capsys.readouterr().out


def test_age_text():
    assert [decisions.age_text(n) for n in (0, 1, 2)] == ["today", "1 day", "2 days"]
    recs = decisions.load_records(Path("/definitely/not/here"))
    assert recs == []


def test_listing_marks_drafts_and_cuts_long_text(project):
    long_title = "T" * 90
    put(project, 1, title=long_title, body=BODY + "\nREPLACE_ME\n")
    lines = decisions.inbox_lines(decisions.load_records(project), date.fromisoformat(TODAY))
    row = lines[1]
    assert "T" * 57 + "..." in row and "T" * 58 not in row and row.endswith("  [draft]")


def test_doctor_findings_per_waiting_record(project):
    put(project, 1)
    put(project, 2, slug="old", status="accepted", decision="Use redis", by="O", at="2026-10-05")
    findings = checks.check_decisions(project, date.fromisoformat(TODAY))
    assert [(f.level, f.name) for f in findings] == [(checks.WARN, "decision D-001")]
    assert "design, waiting 3 days: Pick a cache (recommended: Use redis)" in findings[0].detail
    assert "factory decide D-001" in findings[0].detail
    assert checks.failures(findings) == []


def test_doctor_is_silent_without_waiting_records_and_warns_on_invalid_ones(project):
    assert checks.check_decisions(project, date.fromisoformat(TODAY)) == []
    put(project, 1, status="accepted", decision="Use redis")  # no by/at: invalid
    (project / "docs" / "decisions" / "D-002-broken.md").write_text("nope\n", encoding="utf-8")
    findings = checks.check_decisions(project, date.fromisoformat(TODAY))
    assert [(f.level, f.name) for f in findings] == [
        (checks.WARN, "decision D-001"),
        (checks.WARN, "decision D-002"),
    ]
    assert all("invalid" in f.detail for f in findings)


def test_doctor_command_prints_the_waiting_record(project, capsys):
    put(project, 1)
    code = cli.main(["doctor", str(project)])
    out = capsys.readouterr().out
    assert code == 0  # a waiting decision is a warning, never a failure
    assert "decision D-001" in out and "waiting 3 days" in out


# --- inbox across projects (AC3) -----------------------------------------------------------


def registry(tmp_path, monkeypatch, projects: dict[str, Path | None]) -> Path:
    reg = tmp_path / "registry.yaml"
    data = {
        "projects": [{"name": n} for n in projects],
        "paths": {n: str(p) for n, p in projects.items() if p is not None},
    }
    reg.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setenv("FACTORY_REGISTRY", str(reg))
    return reg


def test_inbox_aggregates_registered_projects(tmp_path, monkeypatch, capsys):
    alpha, beta = tmp_path / "alpha", tmp_path / "beta"
    put(beta, 2, slug="two", title="Beta choice", proposed_at="2026-10-06", type="other")
    put(alpha, 1, slug="one", title="Alpha choice")
    put(alpha, 3, slug="three", title="Alpha later", proposed_at="2026-10-07")
    put(alpha, 4, slug="four", status="accepted", decision="Use redis", by="O", at="2026-10-05")
    registry(
        tmp_path,
        monkeypatch,
        {"beta": beta, "alpha": alpha, "gamma": None, "delta": tmp_path / "gone"},
    )
    snap = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    decisions.cmd_inbox()
    assert capsys.readouterr().out.splitlines() == [
        "inbox: 3 decisions waiting for the owner",
        "alpha:",
        "  D-001  design  3 days  Alpha choice  recommended: Use redis",
        "  D-003  design  today   Alpha later   recommended: Use redis",
        "beta:",
        "  D-002  other   1 day   Beta choice   recommended: Use redis",
        "for the owner: run `factory decide <id>` inside the project (never run by an agent)",
        "skipped: delta (path not found), gamma (no local path registered)",
    ]
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == snap  # read-only


def test_inbox_nothing_waiting_and_no_registry(tmp_path, monkeypatch, capsys):
    assert run("inbox") == 0
    assert capsys.readouterr().out.startswith("inbox: no registry yet")
    quiet = tmp_path / "quiet"
    quiet.mkdir()
    registry(tmp_path, monkeypatch, {"quiet": quiet})
    assert run("inbox") == 0
    assert capsys.readouterr().out.splitlines() == ["inbox: nothing waiting for the owner"]


def test_inbox_skips_unreadable_records_without_failing(tmp_path, monkeypatch, capsys):
    alpha = tmp_path / "alpha"
    put(alpha, 1)
    (alpha / "docs" / "decisions" / "D-002-bad.md").write_text(
        "no front matter\n", encoding="utf-8"
    )
    registry(tmp_path, monkeypatch, {"alpha": alpha})
    assert run("inbox") == 0
    out = capsys.readouterr().out
    assert "inbox: 1 decision waiting for the owner" in out
    assert "invalid: alpha D-002" in out


def test_registry_projects_helper(tmp_path, monkeypatch):
    assert installer.registry_projects() is None
    registry(tmp_path, monkeypatch, {"a": tmp_path, "b": None})
    assert installer.registry_projects() == {"a": str(tmp_path), "b": None}


# --- kit, template, lint (AC8) -------------------------------------------------------------


def scratch(tmp_path: Path) -> Path:
    proj = tmp_path / "scratch"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True)
    (proj / "pyproject.toml").write_text('[project]\nname = "scratch"\n', encoding="utf-8")
    return proj


def test_manifest_lays_the_template_create_mode():
    manifest = common.load_yaml(ROOT / "kit" / "manifest.yaml")
    entry = next(e for e in manifest["files"] if e["dest"] == "docs/decisions/TEMPLATE.md")
    assert entry["mode"] == "create" and (ROOT / entry["src"]).is_file()
    assert (ROOT / manifest["templates"]["decision"]).is_file()


def test_adopt_creates_the_template_and_sync_never_touches_it(tmp_path, capsys):
    proj = scratch(tmp_path)
    assert cli.main(["adopt", str(proj)]) == 0
    tpl = proj / "docs" / "decisions" / "TEMPLATE.md"
    assert tpl.is_file()
    assert (
        "docs/decisions/TEMPLATE.md"
        not in common.load_yaml(proj / ".factory" / "factory.yaml")["managed"]
    )
    tpl.write_text("my own template\n", encoding="utf-8")
    assert cli.main(["sync", str(proj)]) == 0
    assert tpl.read_text(encoding="utf-8") == "my own template\n"
    assert cli.main(["sync", "--check", str(proj)]) == 0
    assert verify.check_project(proj) == []  # the template is not a record


def test_template_is_a_draft_that_decide_refuses():
    text = (ROOT / "kit" / "decisions" / "TEMPLATE.md").read_text(encoding="utf-8")
    assert decisions.placeholder_marker(text) is not None


def test_lint_fails_when_the_named_template_is_missing(tmp_path):
    (tmp_path / "kit").mkdir()
    (tmp_path / "kit" / "manifest.yaml").write_text(
        yaml.safe_dump({"version": 1, "templates": {"decision": "kit/decisions/missing.md"}}),
        encoding="utf-8",
    )
    found = [f.detail for f in checks.lint_manifest(tmp_path)]
    assert "templates.decision: kit/decisions/missing.md does not exist" in found
    ok = checks.lint_manifest(ROOT)
    assert checks.failures(ok) == []


# --- text contracts (AC5, AC6, AC8) --------------------------------------------------------


def read(path: Path) -> str:
    return common.normalise_newlines(path.read_text(encoding="utf-8"))


def test_every_real_skill_passes_lint_including_the_decide_rule():
    assert checks.failures(checks.lint_skills(ROOT)) == []


@pytest.mark.parametrize(
    "skill", ["factory-spec", "factory-plan", "factory-diagnose", "factory-workflow"]
)
def test_skills_send_owner_choices_to_a_decision_record(skill):
    text = read(ROOT / "skills" / skill / "SKILL.md")
    assert "docs/decisions" in text and "decision record" in text
    assert "factory decision new" in text
    assert "chat" in text  # "instead of asking only in chat"


def test_autonomy_policy_and_agents_block_forbid_deciding():
    autonomy = read(ROOT / "policies" / "autonomy.md")
    block = read(ROOT / "kit" / "AGENTS.block.md")
    for text in (autonomy, block):
        assert "factory decide" in text and "never" in text.lower()
    assert (
        "charter" in autonomy and "dismissal" in autonomy and "never delegated" in autonomy.lower()
    )
    assert "decision record" in block and "docs/decisions" in block


def test_treaty_documents_the_gate():
    arch = read(ROOT / "docs" / "ARCHITECTURE.md")
    for needle in (
        "### 3.11 Owner decisions",
        "docs/decisions/D-<n>-<slug>.md",
        "factory decide",
        "factory decision new",
        "factory inbox",
        "docs/decisions/TEMPLATE.md",
        "validate_decision",
        "never run by an agent",
    ):
        assert needle in arch, needle


def test_a_record_symlinked_out_of_the_folder_is_skipped(project, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text(record_text(meta(1)), encoding="utf-8")
    folder = project / "docs" / "decisions"
    folder.mkdir(parents=True)
    try:
        (folder / "D-001-evil.md").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("no symlink rights on this machine")
    assert decisions.load_records(project) == []
    with pytest.raises(FactoryError, match="no decision record"):
        run("decide", "D-001", "--accept", "--yes")
