"""Tests for the findings loop: policy `findings.md` and skill `factory-findings` (FACT-34).

Three kinds of test:
* contract tests read the REAL skill, policy and routing text and pin what must not drift
  (exact `gh api` endpoints, the Jira label format, the dismissal reasons, the closure rule);
* a scripted walkthrough drives a few pure helper functions (below) that encode the skill's
  rules, with a fake `gh` and a fake Jira. The helper takes its endpoints, label template and
  dismissal mapping out of the real skill and policy text, and the fake `gh` rejects any other
  endpoint, so editing the text breaks the walkthrough;
* a sync test adopts a scratch project from the real factory root.
The helper models the rules; it is not a client for GitHub or Jira.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from swfactory import checks, common
from swfactory.commands import install as install_cmd

ROOT = common.FACTORY_ROOT
SKILL_PATH = ROOT / "skills" / "factory-findings" / "SKILL.md"
POLICY_PATH = ROOT / "policies" / "findings.md"


def read(path: Path) -> str:
    return common.normalise_newlines(path.read_text(encoding="utf-8"))


SKILL = read(SKILL_PATH)
POLICY = read(POLICY_PATH)

# --- what the skill and policy must say, verbatim ---------------------------------------

LIST_ENDPOINTS = {
    "code-scanning": "repos/{owner}/{repo}/code-scanning/alerts?state=open",
    "dependabot": "repos/{owner}/{repo}/dependabot/alerts?state=open",
    "secret-scanning": "repos/{owner}/{repo}/secret-scanning/alerts?state=open",
}
PR_QUERY = "code-scanning/alerts?ref=refs/pull/{n}/merge"
LABEL_TEMPLATE = "finding-<source>-<id>"
SOURCES = {"code-scanning": "codeql", "dependabot": "dependabot", "secret-scanning": "secret"}
REASONS = ("false positive", "won't fix", "used in tests")


# --- the helper: the skill's rules as small pure functions ------------------------------


def skill_list_endpoints(text: str = SKILL) -> dict[str, str]:
    """The list endpoints exactly as the skill's step 1 writes them in its `gh api` lines."""
    pat = re.compile(r'gh api --paginate "(repos/\{owner\}/\{repo\}/([a-z-]+)/alerts\?state=open)"')
    return {m.group(2): m.group(1) for m in pat.finditer(text)}


def label_template(text: str = SKILL) -> str:
    m = re.search(r"`(finding-<source>-<id>)`", text)
    assert m, "the skill must state the label as `finding-<source>-<id>`"
    return m.group(1)


def label(source: str, ident: int | str) -> str:
    return label_template().replace("<source>", source).replace("<id>", str(ident))


def policy_reason_mapping(text: str = POLICY) -> dict[str, dict[str, str]]:
    """reason -> {code-scanning, dependabot, secret-scanning} from the policy's table."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] in REASONS:
            apis = ("code-scanning", "dependabot", "secret-scanning")
            rows[cells[0]] = dict(zip(apis, cells[1:], strict=True))
    return rows


RANK = {"secret": -1, "critical": 0, "high": 1, "medium": 2, "low": 3}
FALLBACK_SEVERITY = {"error": "high", "warning": "medium", "note": "low"}
BATCH_LIMIT = 10
FIRST_SWEEP_RANKS = (RANK["critical"], RANK["high"])


@dataclass
class Finding:
    api: str  # code-scanning | dependabot | secret-scanning
    number: int
    severity: str
    summary: str
    url: str

    @property
    def source(self) -> str:
        return SOURCES[self.api]

    @property
    def rank(self) -> int:
        return RANK["secret"] if self.api == "secret-scanning" else RANK[self.severity]

    @property
    def label(self) -> str:
        return label(self.source, self.number)


def normalise(api: str, alert: dict) -> Finding:
    if api == "code-scanning":
        rule = alert["rule"]
        sev = rule.get("security_severity_level") or FALLBACK_SEVERITY[rule["severity"]]
        loc = alert["most_recent_instance"]["location"]
        summary = f"[{rule['id']}] {loc['path']}:{loc['start_line']}"
    elif api == "dependabot":
        sev = alert["security_advisory"]["severity"]
        summary = (
            f"[{alert['dependency']['package']['name']}] {alert['dependency']['manifest_path']}"
        )
    else:
        sev = "critical"
        summary = f"[secret] {alert['secret_type_display_name']}"  # never the value
    return Finding(api, alert["number"], sev, summary, alert["html_url"])


class FakeGh:
    """`gh api` stand-in: serves alert lists and single alerts, records every call, and fails on any
    endpoint the skill does not name."""

    def __init__(self, alerts: dict[str, list[dict]], allowed_lists: dict[str, str] | None = None):
        self.alerts = alerts
        self.allowed = allowed_lists if allowed_lists is not None else skill_list_endpoints()
        self.calls: list[str] = []
        self.patches: list[tuple[str, int, dict]] = []

    def get(self, endpoint: str):
        self.calls.append(endpoint)
        for api, listing in self.allowed.items():
            if endpoint == listing:
                return [a for a in self.alerts.get(api, []) if a["state"] == "open"]
        m = re.fullmatch(r"repos/\{owner\}/\{repo\}/([a-z-]+)/alerts/(\d+)", endpoint)
        if m and m.group(1) in self.alerts:
            for a in self.alerts[m.group(1)]:
                if a["number"] == int(m.group(2)):
                    return a
        raise AssertionError(f"gh api called with an endpoint the skill does not name: {endpoint}")

    def patch(self, api: str, number: int, **fields) -> None:
        self.patches.append((api, number, fields))
        for a in self.alerts[api]:
            if a["number"] == number:
                a.update(fields)


@dataclass
class Issue:
    key: str
    labels: list[str]
    summary: str
    status: str = "To Do"
    priority: str = ""
    comments: list[str] = field(default_factory=list)


class FakeJira:
    """Search by label (any status), create, comment, transition."""

    def __init__(self):
        self.issues: list[Issue] = []

    def search_label(self, lbl: str) -> list[Issue]:
        return [i for i in self.issues if lbl in i.labels]

    def create(self, labels: list[str], summary: str, url: str, priority: str) -> Issue:
        issue = Issue(f"FIND-{len(self.issues) + 1}", list(labels), summary, priority=priority)
        issue.comments.append(f"alert: {url}")
        self.issues.append(issue)
        return issue


@dataclass
class Report:
    created: list[Issue] = field(default_factory=list)
    already_tracked: int = 0
    reopened: list[Issue] = field(default_factory=list)
    unfiled: dict[str, int] = field(default_factory=dict)


def sweep(gh: FakeGh, jira: FakeJira) -> Report:
    """Steps 1 to 3 of the skill: pull, rank, batch limits, search Jira by label, create once."""
    findings = [
        normalise(api, a)
        for api, endpoint in skill_list_endpoints().items()
        for a in gh.get(endpoint)
    ]
    findings.sort(key=lambda f: (f.rank, f.number))
    first_sweep = not jira.search_label("finding")
    report = Report()
    for f in findings:
        existing = jira.search_label(f.label)
        if existing:
            issue = existing[0]
            if issue.status == "Done":  # alert is open again: reopen that issue, never a second one
                issue.status = "To Do"
                issue.comments.append(f"alert {f.url} is open again; reopened")
                report.reopened.append(issue)
            else:
                report.already_tracked += 1
            continue
        too_low = first_sweep and f.rank not in FIRST_SWEEP_RANKS and f.api != "secret-scanning"
        priority = "secret" if f.api == "secret-scanning" else f.severity
        if too_low or len(report.created) >= BATCH_LIMIT:
            report.unfiled[priority] = report.unfiled.get(priority, 0) + 1
            continue
        report.created.append(jira.create(["finding", f.label], f.summary, f.url, priority))
    return report


def requery(gh: FakeGh, source: str, number: int) -> dict:
    api = next(a for a, s in SOURCES.items() if s == source)
    return gh.get(f"repos/{{owner}}/{{repo}}/{api}/alerts/{number}")


def confirmed(source: str, alert: dict) -> bool:
    """The closure rule: the scanner says the finding is gone."""
    if source == "secret":
        return alert["state"] == "resolved" and alert.get("resolution") == "revoked"
    return alert["state"] == "fixed"


def close(gh: FakeGh, issue: Issue, source: str, number: int) -> bool:
    """Step 5: re-query, then Done only on the scanner's word, citing the state."""
    alert = requery(gh, source, number)
    if not confirmed(source, alert):
        issue.comments.append(f"not closed: alert state is {alert['state']}")
        return False
    issue.status = "Done"
    issue.comments.append(f"closed: alert {alert['html_url']} state {alert['state']}")
    return True


class DismissalRefused(Exception):
    pass


def dismiss(gh: FakeGh, issue: Issue, api: str, number: int, reason: str, approved_by: str | None):
    """Step 6: a proposal becomes an action only with an explicit approval and an allowed reason."""
    if not approved_by:
        raise DismissalRefused("no explicit approval from the human")
    if reason not in REASONS:
        raise DismissalRefused(f"reason {reason!r} is not one of {REASONS}")
    value = policy_reason_mapping()[reason][api]
    if api == "secret-scanning":
        fields = {"state": "resolved", "resolution": value}
    else:
        fields = {"state": "dismissed", "dismissed_reason": value}
    gh.patch(api, number, **fields)
    issue.comments.append(f"dismissed: {reason}, approved by {approved_by}")
    issue.status = "Done"


# --- fake alert data ---------------------------------------------------------------------


def cs(number, level="high", state="open", path="src/app.py", line=10):
    return {
        "number": number,
        "state": state,
        "html_url": f"https://example.test/cs/{number}",
        "rule": {"id": "py/sql-injection", "security_severity_level": level, "severity": "error"},
        "most_recent_instance": {"location": {"path": path, "start_line": line}},
    }


def dep(number, severity="high", state="open"):
    return {
        "number": number,
        "state": state,
        "html_url": f"https://example.test/dep/{number}",
        "security_advisory": {"severity": severity},
        "dependency": {"package": {"name": "libx"}, "manifest_path": "uv.lock"},
    }


def sec(number, state="open", resolution=None):
    return {
        "number": number,
        "state": state,
        "resolution": resolution,
        "html_url": f"https://example.test/sec/{number}",
        "secret_type_display_name": "Example API key",
        "secret": "NEVER-IN-JIRA",
    }


def three_alerts():
    return {
        "code-scanning": [cs(123)],
        "dependabot": [dep(7)],
        "secret-scanning": [sec(2)],
    }


# --- AC1: the files exist, lint, routing, closure rule, manifest -------------------------


def test_skill_and_policy_exist_and_lint_clean():
    assert SKILL_PATH.is_file() and POLICY_PATH.is_file()
    assert [f for f in checks.lint_skills(ROOT) if f.level == checks.FAIL] == []
    assert checks.failures(checks.lint_factory(ROOT)) == []
    meta, body = common.split_frontmatter(SKILL)
    assert meta["name"] == "factory-findings" and meta["description"].startswith("Use when")
    assert len(body.splitlines()) <= checks.MAX_BODY_LINES


def test_workflow_routes_findings_and_both_skills_state_the_closure_rule():
    workflow = read(ROOT / "skills" / "factory-workflow" / "SKILL.md")
    release = read(ROOT / "skills" / "factory-release" / "SKILL.md")
    assert "`factory-findings`" in workflow and "Scanner findings" in workflow
    assert "findings.md" in workflow
    for text in (workflow, release):
        assert "`finding`" in text
        assert "Done" in text and "`fixed`" in text
        assert "open alert never allows done" in text.lower()
    assert "findings.md" in read(ROOT / "policies" / "autonomy.md")
    assert "`findings`" in read(ROOT / "kit" / "AGENTS.block.md")


def test_manifest_covers_skill_and_policy():
    manifest = yaml.safe_load((ROOT / "kit" / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["skills"] == "all"
    assert any(d["src"] == "policies" and d["mode"] == "managed" for d in manifest["dirs"])
    assert checks.lint_manifest(ROOT) == []


# --- AC4: exact endpoints, label format, reasons, rules ----------------------------------


def test_skill_names_exact_endpoints_and_label_format():
    for api, endpoint in LIST_ENDPOINTS.items():
        assert f'gh api --paginate "{endpoint}"' in SKILL, api
    assert skill_list_endpoints() == LIST_ENDPOINTS
    assert PR_QUERY in SKILL
    assert "?ref=refs/pull/{n}/merge" in SKILL
    assert label_template() == LABEL_TEMPLATE
    assert "labels `finding` and `finding-<source>-<id>`" in SKILL
    for source in SOURCES.values():
        assert f"`{source}`" in SKILL
    for api in LIST_ENDPOINTS:
        assert f"{api}/alerts/<id>" in SKILL  # the re-query of a single alert
    assert label("codeql", 123) == "finding-codeql-123"


def test_endpoint_drift_is_detected():
    drifted = SKILL.replace("alerts?state=open", "alerts?state=all")
    assert skill_list_endpoints(drifted) != LIST_ENDPOINTS
    gh = FakeGh(three_alerts(), allowed_lists=skill_list_endpoints(drifted))
    with pytest.raises(AssertionError, match="does not name"):
        gh.get(LIST_ENDPOINTS["dependabot"])


def test_policy_names_closure_rule_reasons_and_enable_commands():
    for reason in REASONS:
        assert f"`{reason}`" in POLICY
    mapping = policy_reason_mapping()
    assert set(mapping) == set(REASONS)
    assert all(set(v) == set(LIST_ENDPOINTS) for v in mapping.values())
    assert "Never dismiss a finding to make a check go green" in POLICY
    assert "`state` = `fixed`" in POLICY and "`resolved` with resolution `revoked`" in POLICY
    flat = " ".join(POLICY.split())  # wrapped lines
    assert "at most 10 issues" in flat and "`critical` and `high`" in flat
    assert "factory harden" in POLICY
    for cmd in (
        "code-scanning/default-setup -f state=configured",
        "-X PUT repos/{owner}/{repo}/vulnerability-alerts",
        "-X PUT repos/{owner}/{repo}/automated-security-fixes",
        "security_and_analysis[secret_scanning][status]=enabled",
        "security_and_analysis[secret_scanning_push_protection][status]=enabled",
    ):
        assert cmd in POLICY, cmd


# --- AC2: the scripted walkthrough -------------------------------------------------------


def test_two_sweeps_create_one_issue_per_finding():
    gh, jira = FakeGh(three_alerts()), FakeJira()

    first = sweep(gh, jira)
    assert len(first.created) == 3 and len(jira.issues) == 3
    labels = sorted(i.labels[1] for i in jira.issues)
    assert labels == ["finding-codeql-123", "finding-dependabot-7", "finding-secret-2"]
    assert all(i.labels[0] == "finding" for i in jira.issues)
    assert all(re.fullmatch(r"finding-(codeql|dependabot|secret|sonar)-\w+", x) for x in labels)

    second = sweep(gh, jira)  # same alerts, nothing changed
    assert second.created == [] and second.already_tracked == 3
    assert len(jira.issues) == 3

    # only the endpoints the skill names were called, in both runs, and no secret value reached Jira
    assert set(gh.calls) == set(LIST_ENDPOINTS.values())
    assert not any("NEVER-IN-JIRA" in str(i) for i in jira.issues)


def test_open_alert_never_allows_done():
    alerts = three_alerts()
    gh, jira = FakeGh(alerts), FakeJira()
    sweep(gh, jira)
    by = {i.labels[1]: i for i in jira.issues}

    # open: refused, whatever else is true
    issue = by["finding-codeql-123"]
    issue.status = "In Review"  # the fix PR is merged and reviewed; the scanner has not agreed
    assert close(gh, issue, "codeql", 123) is False
    assert issue.status == "In Review" and "state is open" in issue.comments[-1]

    # a revoked-looking secret that is only dismissed as won't fix is not "revoked"
    alerts["secret-scanning"][0].update(state="resolved", resolution="wont_fix")
    assert close(gh, by["finding-secret-2"], "secret", 2) is False
    assert by["finding-secret-2"].status == "To Do"

    # fixed: Done, citing the state
    alerts["code-scanning"][0]["state"] = "fixed"
    assert close(gh, issue, "codeql", 123) is True
    assert issue.status == "Done" and "state fixed" in issue.comments[-1]
    alerts["secret-scanning"][0].update(resolution="revoked")
    assert close(gh, by["finding-secret-2"], "secret", 2) is True

    # a dismissed alert is not `fixed` either: closing needs the dismissal path
    alerts["dependabot"][0]["state"] = "dismissed"
    assert close(gh, by["finding-dependabot-7"], "dependabot", 7) is False


def test_dismissal_needs_explicit_approval_and_allowed_reason():
    alerts = three_alerts()
    gh, jira = FakeGh(alerts), FakeJira()
    sweep(gh, jira)
    issue = next(i for i in jira.issues if i.labels[1] == "finding-codeql-123")

    # proposed, not approved: nothing is applied
    with pytest.raises(DismissalRefused, match="approval"):
        dismiss(gh, issue, "code-scanning", 123, "false positive", approved_by=None)
    with pytest.raises(DismissalRefused, match="approval"):
        dismiss(gh, issue, "code-scanning", 123, "false positive", approved_by="")
    assert gh.patches == [] and alerts["code-scanning"][0]["state"] == "open"
    assert issue.status == "To Do"

    # approved but not an allowed reason (for example, to get a green check): refused
    for bad in ("make CI green", "", "fixed", "wontfix"):
        with pytest.raises(DismissalRefused, match="not one of"):
            dismiss(gh, issue, "code-scanning", 123, bad, approved_by="the owner")
    assert gh.patches == []

    # approved with an allowed reason: applied with the policy's value, recorded on the issue
    for reason in REASONS:
        probe = FakeGh({"code-scanning": [cs(5)]})
        dismiss(probe, Issue("X-1", [], "s"), "code-scanning", 5, reason, approved_by="the owner")
        assert probe.patches == [
            ("code-scanning", 5, {"state": "dismissed", "dismissed_reason": reason})
        ]
    dismiss(gh, issue, "code-scanning", 123, "used in tests", approved_by="the owner")
    assert alerts["code-scanning"][0]["state"] == "dismissed"
    assert "used in tests" in issue.comments[-1] and "the owner" in issue.comments[-1]
    assert issue.status == "Done"

    # the other scanners use their own field and value, taken from the policy table
    dismiss(gh, issue, "dependabot", 7, "false positive", approved_by="the owner")
    assert gh.patches[-1] == (
        "dependabot",
        7,
        {"state": "dismissed", "dismissed_reason": "inaccurate"},
    )
    dismiss(gh, issue, "secret-scanning", 2, "used in tests", approved_by="the owner")
    assert gh.patches[-1] == (
        "secret-scanning",
        2,
        {"state": "resolved", "resolution": "used_in_tests"},
    )


def big_backlog():
    return {
        "secret-scanning": [sec(1), sec(2)],
        "code-scanning": [cs(n, "critical") for n in (1, 2, 3, 4)]
        + [cs(n, "high") for n in (5, 6, 7)]
        + [cs(n, "medium") for n in (8, 9)],
        "dependabot": [dep(n, "critical") for n in (1, 2, 3)]
        + [dep(n, "high") for n in (4, 5)]
        + [dep(n, "low") for n in (6, 7)],
    }


def test_first_sweep_is_capped_and_highest_severity_first():
    gh, jira = FakeGh(big_backlog()), FakeJira()

    first = sweep(gh, jira)
    assert len(first.created) == BATCH_LIMIT == 10 and len(jira.issues) == 10
    # secrets first, then every critical (4 code scanning + 3 Dependabot), then the first high
    assert [i.priority for i in first.created] == ["secret"] * 2 + ["critical"] * 7 + ["high"]
    # medium and low are not filed on a first sweep; the rest of the highs wait for the human
    assert first.unfiled == {"high": 4, "medium": 2, "low": 2}

    # a later sweep is not a first sweep: it files the remainder, still at most 10 per run
    second = sweep(gh, jira)
    assert len(second.created) == 8 and second.already_tracked == 10
    assert sweep(gh, jira).created == []
    assert len(jira.issues) == 18  # exactly one issue per alert, ever


def test_exactly_the_limit_leaves_nothing_behind_and_does_not_flood():
    alerts = {"code-scanning": [cs(n, "critical") for n in range(1, 11)] + [cs(11, "low")]}
    report = sweep(FakeGh(alerts), FakeJira())
    assert len(report.created) == 10 and report.unfiled == {"low": 1}


def test_first_sweep_files_only_critical_and_high_even_below_the_cap():
    alerts = {
        "code-scanning": [cs(1, "critical"), cs(2, "high"), cs(3, "medium"), cs(4, "low")],
        "dependabot": [dep(5, "medium")],
    }
    gh, jira = FakeGh(alerts), FakeJira()
    first = sweep(gh, jira)
    assert [i.priority for i in first.created] == ["critical", "high"]
    assert first.unfiled == {"medium": 2, "low": 1}

    # once issues exist it is no longer a first sweep: the lower severities are filed next
    assert [i.priority for i in sweep(gh, jira).created] == ["medium", "medium", "low"]


def test_code_scanning_severity_falls_back_to_rule_severity():
    alert = cs(1, level=None)
    alert["rule"]["security_severity_level"] = None
    assert normalise("code-scanning", alert).severity == "high"  # rule.severity "error"
    alert["rule"]["severity"] = "note"
    assert normalise("code-scanning", alert).severity == "low"


def test_done_issue_with_reopened_alert_is_reopened_not_duplicated():
    alerts = three_alerts()
    gh, jira = FakeGh(alerts), FakeJira()
    sweep(gh, jira)
    issue = next(i for i in jira.issues if i.labels[1] == "finding-codeql-123")
    alerts["code-scanning"][0]["state"] = "fixed"
    assert close(gh, issue, "codeql", 123) and issue.status == "Done"

    alerts["code-scanning"][0]["state"] = "open"  # the same alert number appears open again
    report = sweep(gh, jira)
    assert report.reopened == [issue] and issue.status == "To Do"
    assert report.created == [] and len(jira.issues) == 3


# --- AC3: sync into a scratch adopted project --------------------------------------------


def run(*argv: str) -> int:
    parser = argparse.ArgumentParser(prog="factory")
    sub = parser.add_subparsers(dest="command", required=True)
    install_cmd.register(sub)
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


def snapshot(p: Path) -> dict[str, bytes]:
    return {
        f.relative_to(p).as_posix(): f.read_bytes()
        for f in p.rglob("*")
        if f.is_file() and ".git" not in f.relative_to(p).parts
    }


def scratch_project(tmp_path: Path) -> Path:
    proj = tmp_path / "scratch"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True)
    (proj / "pyproject.toml").write_text('[project]\nname = "scratch"\n', encoding="utf-8")
    return proj


def test_sync_copies_skill_and_policy_into_an_adopted_project(tmp_path):
    proj = scratch_project(tmp_path)
    assert run("adopt", str(proj)) == 0
    cfg_path = proj / ".factory" / "factory.yaml"
    targets = common.load_yaml(cfg_path)["skill_targets"]
    assert targets
    for t in targets:
        copy = proj / t / "factory-findings" / "SKILL.md"
        assert copy.is_file() and read(copy) == SKILL
    assert read(proj / ".factory" / "policies" / "findings.md") == POLICY

    # a project adopted before this release has neither: sync lays both down
    cfg = common.load_yaml(cfg_path)
    removed = [
        k for k in cfg["managed"] if "factory-findings" in k or k.endswith("policies/findings.md")
    ]
    assert len(removed) == len(targets) + 1
    for k in removed:
        (proj / k).unlink()
        del cfg["managed"][k]
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert run("sync", str(proj)) == 0
    for t in targets:
        assert read(proj / t / "factory-findings" / "SKILL.md") == SKILL
    assert read(proj / ".factory" / "policies" / "findings.md") == POLICY

    # idempotent: a second sync changes nothing
    before = snapshot(proj)
    assert run("sync", str(proj)) == 0
    assert snapshot(proj) == before
    assert run("sync", "--check", str(proj)) == 0
