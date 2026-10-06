"""Read-only dependency summary for `factory status` and `factory doctor` (FACT-39).

For a project whose `origin` is on github.com: open alerts per source and severity, the open
Dependabot pull requests with their check state, the failed `Dependabot Updates` runs of the last
7 days, and a needs-attention flag. Every call goes through `harden.gh_api` (the one function that
starts `gh`), so tests replace it and the suite never reaches the network. Only GET calls and one
read-only GraphQL query are made.

A failure never crashes anything: a part that cannot be read prints `unknown (HTTP <status>)` or
`unknown (gh unavailable)`. Response bodies are parsed for counts and a few scalar fields (number,
state, severity, a sanitised title) and are never printed; no token or secret value is ever looked
at. Output is ASCII-only (Windows consoles).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from swfactory import harden
from swfactory.common import FactoryError

WINDOW_DAYS = 7
PAGE = 100  # alerts and runs per request
MAX_PAGES = 5  # a list longer than PAGE * MAX_PAGES is reported as "at least"
TITLE_MAX = 60
SEVERITIES = ("critical", "high", "medium", "low")
URGENT = frozenset({"critical", "high"})
UNPAGED = frozenset({"dependabot"})  # alert lists that cannot be read with `page=`
# Dependabot Updates runs are `event: dynamic` runs of this workflow path (observed on GitHub; the
# run `name` is "<ecosystem> in <dir> for <package> - Update #<n>", not the workflow name).
RUN_PATH_SUFFIX = "dependabot/dependabot-updates"
RUN_WORKFLOW_NAME = "Dependabot Updates"
BOT_LOGINS = frozenset({"dependabot", "dependabot[bot]", "app/dependabot"})
# error / warning / note, as code scanning reports a rule without a security severity level
_RULE_SEVERITY = {"error": "high", "warning": "medium", "note": "low"}
_PR_QUERY = (
    "query($o:String!,$r:String!){repository(owner:$o,name:$r){"
    "pullRequests(states:OPEN,first:100,orderBy:{field:CREATED_AT,direction:DESC}){"
    "pageInfo{hasNextPage} nodes{number title author{login} "
    "commits(last:1){nodes{commit{statusCheckRollup{state}}}}}}}}"
)
_CHECK_STATE = {
    "SUCCESS": "green",
    "FAILURE": "failing",
    "ERROR": "failing",
    "PENDING": "pending",
    "EXPECTED": "pending",
}


def _why(status: int) -> str:
    return "unknown (gh unavailable)" if status == 0 else f"unknown (HTTP {status})"


def _ascii(text: object, limit: int) -> str:
    """Printable ASCII only, one line, cut at `limit`: PR titles are third-party text."""
    s = re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7e]", "?", str(text))).strip()
    return s if len(s) <= limit else s[: limit - 3].rstrip() + "..."


@dataclass(frozen=True)
class AlertCount:
    source: str
    total: int | None  # None: could not be read
    by_severity: tuple[tuple[str, int], ...] = ()
    detail: str = ""  # why it is unknown
    capped: bool = False  # more alerts than the pages read

    @property
    def urgent(self) -> int:
        """Open alerts that make the project need attention: critical or high; every open secret."""
        if self.total is None:
            return 0
        if self.source == "secret-scanning":
            return self.total
        return sum(n for sev, n in self.by_severity if sev in URGENT)

    def text(self) -> str:
        if self.total is None:
            return self.detail
        lead = f"{'at least ' if self.capped else ''}{self.total} open"
        if not self.by_severity:
            return lead
        return lead + " (" + ", ".join(f"{sev} {n}" for sev, n in self.by_severity) + ")"


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    checks: str  # green | failing | pending | none


@dataclass(frozen=True)
class PullRequests:
    items: tuple[PullRequest, ...] | None  # None: could not be read
    detail: str = ""
    more: bool = False  # more open PRs than the first page


@dataclass(frozen=True)
class FailedRuns:
    count: int | None  # None: could not be read
    detail: str = ""
    capped: bool = False


@dataclass(frozen=True)
class Part:
    """One line of the summary, shared by `status` (text) and `doctor` (a Finding per part)."""

    name: str
    detail: str
    warn: bool


@dataclass(frozen=True)
class Summary:
    owner: str
    repo: str
    alerts: tuple[AlertCount, ...]
    prs: PullRequests
    runs: FailedRuns

    @property
    def urgent_alerts(self) -> int:
        return sum(a.urgent for a in self.alerts)

    @property
    def unreadable(self) -> bool:
        return (
            any(a.total is None for a in self.alerts)
            or self.prs.items is None
            or self.runs.count is None
        )

    @property
    def needs_attention(self) -> str:
        """`yes` when a critical or high alert (any secret) is open or a Dependabot Updates run
        failed; `unknown` when nothing known says yes but a part could not be read; else `no`."""
        if self.urgent_alerts or (self.runs.count or 0) > 0:
            return "yes"
        return "unknown" if self.unreadable else "no"

    def attention_text(self) -> str:
        state = self.needs_attention
        if state == "yes":
            why = []
            if self.urgent_alerts:
                why.append(f"{self.urgent_alerts} critical/high alert(s) open")
            if (self.runs.count or 0) > 0:
                why.append(f"{self.runs.count} failed Dependabot Updates run(s)")
            return f"yes ({'; '.join(why)})"
        if state == "unknown":
            return "unknown (a part above could not be read)"
        return "no"

    def parts(self) -> list[Part]:
        out = [
            Part(
                f"{a.source} alerts",
                a.text(),
                a.total is None or a.urgent > 0,
            )
            for a in self.alerts
        ]
        if self.prs.items is None:
            out.append(Part("dependabot PRs", self.prs.detail, True))
        else:
            n = len(self.prs.items)
            more = " (the first 100 open PRs were read)" if self.prs.more else ""
            out.append(Part("dependabot PRs", f"{n} open{more}", False))
        if self.runs.count is None:
            out.append(Part("dependabot updates", self.runs.detail, True))
        else:
            lead = "at least " if self.runs.capped else ""
            text = f"{lead}{self.runs.count} failed run(s) in the last {WINDOW_DAYS} days"
            out.append(Part("dependabot updates", text, self.runs.count > 0))
        out.append(Part("needs attention", self.attention_text(), self.needs_attention != "no"))
        return out

    def lines(self) -> list[str]:
        lines = [f"dependencies for {self.owner}/{self.repo} (read-only):"]
        for part in self.parts():
            if part.name.endswith("alerts"):
                lines.append(f"  alerts  {part.name.removesuffix(' alerts')}: {part.detail}")
            elif part.name == "dependabot PRs":
                lines.append(f"  {part.name}: {part.detail}")
                for pr in self.prs.items or ():
                    lines.append(f"    #{pr.number} checks {pr.checks}: {pr.title}")
            else:
                lines.append(f"  {part.name}: {part.detail}")
        return lines


# --- reading ---------------------------------------------------------------------------------


def _severity(source: str, alert: dict) -> str:
    if source == "dependabot":
        advisory = alert.get("security_advisory")
        sev = advisory.get("severity") if isinstance(advisory, dict) else None
    else:  # code scanning
        rule = alert.get("rule") if isinstance(alert.get("rule"), dict) else {}
        sev = rule.get("security_severity_level") or _RULE_SEVERITY.get(str(rule.get("severity")))
    sev = str(sev).lower() if sev else "unrated"
    return sev if sev in SEVERITIES else "unrated"


def _read_alerts(owner: str, repo: str, source: str, gh: harden.Gh) -> AlertCount:
    items: list[dict] = []
    capped = False
    # The Dependabot alerts endpoint rejects `page` (HTTP 400: it pages by cursor, which `gh_api`
    # does not follow), so one request is made and a full page is reported as "at least".
    pages = 1 if source in UNPAGED else MAX_PAGES
    for page in range(1, pages + 1):
        paging = "" if source in UNPAGED else f"&page={page}"
        path = f"repos/{owner}/{repo}/{source}/alerts?state=open&per_page={PAGE}{paging}"
        status, data = gh("GET", path, None)
        if status == 0 or status < 200 or status >= 300:
            return AlertCount(source, None, detail=_why(status))
        if not isinstance(data, list):
            return AlertCount(source, None, detail="unknown (unexpected answer)")
        items += [a for a in data if isinstance(a, dict)]
        if len(data) < PAGE:
            break
        capped = page == pages
    if source == "secret-scanning":  # no severity; every open secret needs attention
        return AlertCount(source, len(items), capped=capped)
    counts = {sev: 0 for sev in (*SEVERITIES, "unrated")}
    for alert in items:
        counts[_severity(source, alert)] += 1
    by = tuple((sev, n) for sev, n in counts.items() if n)
    return AlertCount(source, len(items), by, capped=capped)


def _check_state(node: dict) -> str:
    try:
        rollup = node["commits"]["nodes"][0]["commit"]["statusCheckRollup"]
    except (KeyError, IndexError, TypeError):
        return "none"
    state = rollup.get("state") if isinstance(rollup, dict) else None
    return _CHECK_STATE.get(str(state), "none")


def _read_prs(owner: str, repo: str, gh: harden.Gh) -> PullRequests:
    body = {"query": _PR_QUERY, "variables": {"o": owner, "r": repo}}
    status, data = gh("POST", "graphql", body)
    if status != 200:
        return PullRequests(None, _why(status))
    if not isinstance(data, dict) or data.get("errors"):
        return PullRequests(None, "unknown (GraphQL error)")
    try:
        conn = data["data"]["repository"]["pullRequests"]
        nodes = conn["nodes"]
        more = bool(conn["pageInfo"]["hasNextPage"])
    except (KeyError, TypeError):
        return PullRequests(None, "unknown (unexpected answer)")
    if not isinstance(nodes, list):
        return PullRequests(None, "unknown (unexpected answer)")
    prs = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("number"), int):
            continue
        author = node.get("author")
        login = str(author.get("login") if isinstance(author, dict) else "").lower()
        if login in BOT_LOGINS:
            title = _ascii(node.get("title", ""), TITLE_MAX)
            prs.append(PullRequest(node["number"], title, _check_state(node)))
    return PullRequests(tuple(sorted(prs, key=lambda p: p.number)), more=more)


def _parse_time(text: object) -> datetime | None:
    try:
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _is_dependabot_run(run: dict) -> bool:
    path = str(run.get("path") or "")
    return path.endswith(RUN_PATH_SUFFIX) or run.get("name") == RUN_WORKFLOW_NAME


def _read_runs(owner: str, repo: str, gh: harden.Gh, now: datetime) -> FailedRuns:
    cutoff = now - timedelta(days=WINDOW_DAYS)
    since = quote(f">={cutoff.strftime('%Y-%m-%d')}", safe="")
    count, capped = 0, False
    for page in range(1, MAX_PAGES + 1):
        path = (
            f"repos/{owner}/{repo}/actions/runs?status=failure&event=dynamic"
            f"&created={since}&per_page={PAGE}&page={page}"
        )
        status, data = gh("GET", path, None)
        if status == 0 or status < 200 or status >= 300:
            return FailedRuns(None, _why(status))
        runs = data.get("workflow_runs") if isinstance(data, dict) else None
        if not isinstance(runs, list):
            return FailedRuns(None, "unknown (unexpected answer)")
        for run in runs:
            if not isinstance(run, dict) or not _is_dependabot_run(run):
                continue
            if run.get("conclusion", "failure") != "failure":
                continue
            created = _parse_time(run.get("created_at"))
            if created is not None and created >= cutoff:
                count += 1
        if len(runs) < PAGE:
            break
        capped = page == MAX_PAGES
    return FailedRuns(count, capped=capped)


def summarize(
    owner: str, repo: str, gh: harden.Gh | None = None, now: datetime | None = None
) -> Summary:
    """Read the whole summary. Never raises; each part fails on its own."""
    gh = gh or harden.gh_api
    now = now or datetime.now(UTC)
    alerts = tuple(
        _read_alerts(owner, repo, source, gh)
        for source in ("dependabot", "code-scanning", "secret-scanning")
    )
    return Summary(
        owner, repo, alerts, _read_prs(owner, repo, gh), _read_runs(owner, repo, gh, now)
    )


def for_project(
    root: Path | str, gh: harden.Gh | None = None, now: datetime | None = None
) -> Summary | None:
    """The summary of the project's GitHub repository, or None when its `origin` is not on
    github.com (a local-only project has nothing to read and makes no call)."""
    try:
        owner, repo = harden.repo_slug(root)
    except FactoryError:
        return None
    return summarize(owner, repo, gh, now)
