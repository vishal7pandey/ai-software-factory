"""Tests for `factory harden` (swfactory.harden, commands/harden.py) and the doctor/adopt hooks.

No test reaches GitHub: every `gh` call goes through `harden.gh_api`, replaced here by `FakeGh`, and
the autouse guard in conftest.py makes the one real process-starting function inert.
"""

from __future__ import annotations

import subprocess

import pytest

from swfactory import common, harden
from swfactory.common import FactoryError

# --- the runner ---------------------------------------------------------------------------------


def test_the_suite_cannot_reach_the_real_gh(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", boom)
    assert harden.gh_api("GET", "repos/o/r") == (0, None)


def test_parse_response_status_and_body():
    text = (
        'HTTP/2.0 200 OK\r\nContent-Type: application/json\r\nX-A: b\r\n\r\n{"state": "configured"}'
    )
    assert harden.parse_response(text) == (200, {"state": "configured"})
    assert harden.parse_response("HTTP/2.0 204 No Content\nDate: x\n\n") == (204, None)
    assert harden.parse_response("HTTP/2.0 404 Not Found\n\n{not json") == (404, None)


@pytest.mark.parametrize("text", ["", "gh: command not found", "garbage\n\n{}"])
def test_parse_response_unusable_output_is_status_zero(text):
    assert harden.parse_response(text) == (0, None)


def test_gh_api_builds_the_call_and_returns_the_status(monkeypatch):
    seen = {}

    def fake(argv, stdin):
        seen["argv"], seen["stdin"] = argv, stdin
        return 0, "HTTP/2.0 202 Accepted\n\n{}"

    monkeypatch.setattr(harden, "_run_gh", fake)
    body = {"state": "configured", "query_suite": "default"}
    assert harden.gh_api("PATCH", "repos/o/r/code-scanning/default-setup", body) == (202, {})
    assert seen["argv"][:5] == ["api", "-i", "-X", "PATCH", "repos/o/r/code-scanning/default-setup"]
    assert seen["argv"][5:] == ["--input", "-"]
    assert seen["stdin"] == '{"state": "configured", "query_suite": "default"}'
    harden.gh_api("GET", "repos/o/r")
    assert seen["argv"] == ["api", "-i", "-X", "GET", "repos/o/r"] and seen["stdin"] is None


# --- a stub GitHub --------------------------------------------------------------------------------

BASE = "repos/me/proj"
MARKER = "LEAK-MARKER-xyz"  # sits in every failed response body; must never be printed


class FakeGh:
    """Stands in for `harden.gh_api`: answers GETs from the flags, records every call, and can be
    told to fail a call by (method, path suffix) -> status (the body then carries MARKER)."""

    def __init__(
        self,
        *,
        private=False,
        secret=True,
        push=True,
        alerts=True,
        updates=True,
        codeql=True,
        fail=None,
        admin=True,
    ):
        self.private, self.secret, self.push = private, secret, push
        self.alerts, self.updates, self.codeql = alerts, updates, codeql
        self.fail = dict(fail or {})
        self.admin = admin
        self.calls: list[tuple[str, str, dict | None]] = []

    @property
    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        for (m, suffix), status in self.fail.items():
            if m == method and path.endswith(suffix):
                return status, {"message": MARKER}
        if method != "GET":
            if path.endswith("default-setup"):
                return 202, {}
            return (200, {}) if method == "PATCH" else (204, None)
        if path == BASE:
            meta = {"private": self.private}
            if self.admin:
                meta["security_and_analysis"] = {
                    "secret_scanning": {"status": "enabled" if self.secret else "disabled"},
                    "secret_scanning_push_protection": {
                        "status": "enabled" if self.push else "disabled"
                    },
                }
            return 200, meta
        if path == f"{BASE}/vulnerability-alerts":
            return (204, None) if self.alerts else (404, {"message": "Not Found"})
        if path == f"{BASE}/automated-security-fixes":
            return 200, {"enabled": self.updates, "paused": False}
        if path == f"{BASE}/code-scanning/default-setup":
            return 200, {"state": "configured" if self.codeql else "not-configured"}
        return 404, None


def states(gh):
    st = harden.read_state("me", "proj", gh)
    return {p.key: p.state for p in st.protections}


ALL_OK = {k: harden.OK for k in harden.KEYS}


def test_state_all_on():
    assert states(FakeGh()) == ALL_OK


@pytest.mark.parametrize(
    ("flags", "off"),
    [
        ({"secret": False}, harden.SECRET),
        ({"push": False}, harden.SECRET),
        ({"alerts": False}, harden.ALERTS),
        ({"updates": False}, harden.UPDATES),
        ({"codeql": False}, harden.CODEQL),
    ],
)
def test_state_each_protection_can_be_off_alone(flags, off):
    assert states(FakeGh(**flags)) == {**ALL_OK, off: harden.OFF}


def test_state_without_admin_secret_scanning_is_unknown_not_off():
    assert states(FakeGh(admin=False))[harden.SECRET] == harden.UNKNOWN


def test_state_when_gh_is_unusable_everything_is_unknown():
    st = harden.read_state("me", "proj", lambda m, p, b=None: (0, None))
    assert st.private is None
    assert {p.state for p in st.protections} == {harden.UNKNOWN}
    assert "gh unavailable" in st.protections[0].detail


def test_state_a_failing_read_is_unknown_with_its_status():
    gh = FakeGh(fail={("GET", "/automated-security-fixes"): 500})
    st = harden.read_state("me", "proj", gh)
    assert st.get(harden.UPDATES).state == harden.UNKNOWN
    assert st.get(harden.UPDATES).detail == "HTTP 500"
    assert st.get(harden.ALERTS).state == harden.OK


def test_state_private_repo_without_the_feature_is_not_available():
    gh = FakeGh(private=True, fail={("GET", "/code-scanning/default-setup"): 403})
    st = harden.read_state("me", "proj", gh)
    assert st.private is True
    assert st.get(harden.CODEQL).state == harden.UNAVAILABLE
    assert st.get(harden.CODEQL).detail == "HTTP 403"
    # the same status on a public repo is not "not available"
    gh = FakeGh(fail={("GET", "/code-scanning/default-setup"): 403})
    assert harden.read_state("me", "proj", gh).get(harden.CODEQL).state == harden.UNKNOWN


# --- apply ----------------------------------------------------------------------------------------

SECRET_WRITE = (
    "PATCH",
    BASE,
    {
        "security_and_analysis": {
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "enabled"},
        }
    },
)
ALERTS_WRITE = ("PUT", f"{BASE}/vulnerability-alerts", None)
UPDATES_WRITE = ("PUT", f"{BASE}/automated-security-fixes", None)
CODEQL_WRITE = (
    "PATCH",
    f"{BASE}/code-scanning/default-setup",
    {"state": "configured", "query_suite": "default"},
)


@pytest.fixture
def proj(tmp_path):
    return git_repo(tmp_path / "proj", "https://github.com/me/proj.git")


def test_apply_issues_exactly_the_expected_writes(proj):
    gh = FakeGh(secret=False, alerts=False, updates=False, codeql=False)
    lines, code = harden.run(proj, gh=gh)
    assert gh.writes == [SECRET_WRITE, ALERTS_WRITE, UPDATES_WRITE, CODEQL_WRITE]
    assert code == 0
    assert [ln.split()[0] for ln in lines[1:5]] == ["enabled"] * 4
    assert lines[-1] == "harden: 4 enabled, 0 already on, 0 not available, 0 failed"


def test_apply_skips_what_is_already_on(proj):
    gh = FakeGh(alerts=False, codeql=False)
    lines, code = harden.run(proj, gh=gh)
    assert gh.writes == [ALERTS_WRITE, CODEQL_WRITE]
    assert code == 0
    assert lines[1].startswith("ok") and "already on" in lines[1]
    assert lines[-1].startswith("harden: 2 enabled, 2 already on")


def test_apply_with_everything_on_writes_nothing(proj):
    gh = FakeGh()
    lines, code = harden.run(proj, gh=gh)
    assert gh.writes == [] and code == 0
    assert sum("already on" in ln for ln in lines[1:5]) == 4
    assert lines[-1] == "harden: 0 enabled, 4 already on, 0 not available, 0 failed"


def test_push_protection_alone_off_still_writes_the_secret_scanning_call(proj):
    gh = FakeGh(push=False)
    harden.run(proj, gh=gh)
    assert gh.writes == [SECRET_WRITE]


def test_one_failure_does_not_stop_the_others_and_leaks_no_body(proj, capsys):
    gh = FakeGh(
        secret=False,
        alerts=False,
        updates=False,
        codeql=False,
        fail={("PATCH", "/code-scanning/default-setup"): 403},
    )
    lines, code = harden.run(proj, gh=gh)
    assert gh.writes == [SECRET_WRITE, ALERTS_WRITE, UPDATES_WRITE, CODEQL_WRITE]
    assert code == 1
    assert lines[4].startswith("FAILED") and lines[4].endswith("HTTP 403")
    assert [ln.split()[0] for ln in lines[1:4]] == ["enabled"] * 3
    assert MARKER not in "\n".join(lines)


def test_failure_of_the_first_write_still_attempts_the_rest(proj):
    gh = FakeGh(secret=False, alerts=False, fail={("PATCH", BASE): 500})
    lines, code = harden.run(proj, gh=gh)
    assert gh.writes == [SECRET_WRITE, ALERTS_WRITE]
    assert code == 1 and lines[1].endswith("HTTP 500")


def test_private_repo_403_is_not_available_and_not_a_failure(proj):
    gh = FakeGh(private=True, codeql=False, fail={("PATCH", "/code-scanning/default-setup"): 403})
    lines, code = harden.run(proj, gh=gh)
    assert code == 0
    assert "not available" in lines[4] and "HTTP 403" in lines[4]
    assert lines[-1].startswith("harden: 0 enabled, 3 already on, 1 not available, 0 failed")
    assert MARKER not in "\n".join(lines)


@pytest.mark.parametrize("status", [404, 422])
def test_private_repo_404_and_422_behave_like_403(proj, status):
    gh = FakeGh(
        private=True, codeql=False, fail={("PATCH", "/code-scanning/default-setup"): status}
    )
    lines, code = harden.run(proj, gh=gh)
    assert code == 0 and f"HTTP {status}" in lines[4] and "not available" in lines[4]


def test_private_repo_500_is_still_a_failure(proj):
    gh = FakeGh(private=True, codeql=False, fail={("PATCH", "/code-scanning/default-setup"): 500})
    lines, code = harden.run(proj, gh=gh)
    assert code == 1 and lines[4].startswith("FAILED") and "HTTP 500" in lines[4]


def test_apply_refuses_when_the_repository_cannot_be_read(proj):
    gh = FakeGh()
    with pytest.raises(FactoryError, match="gh auth status"):
        harden.run(proj, gh=lambda m, p, b=None: (0, None))
    assert gh.calls == []


def test_apply_with_a_401_names_the_status(proj):
    with pytest.raises(FactoryError, match="HTTP 401"):
        harden.run(proj, gh=lambda m, p, b=None: (401, {"message": MARKER}))


# --- dry run --------------------------------------------------------------------------------------


def test_dry_run_issues_no_write_and_lists_the_calls(proj):
    gh = FakeGh(secret=False, alerts=False, updates=False, codeql=False)
    lines, code = harden.run(proj, dry_run=True, gh=gh)
    assert gh.writes == [] and code == 0
    text = "\n".join(lines)
    assert f"PUT {BASE}/vulnerability-alerts" in text
    assert f"PUT {BASE}/automated-security-fixes" in text
    assert '"query_suite": "default"' in text and '"state": "configured"' in text
    assert "secret_scanning_push_protection" in text
    assert (
        lines[-1].startswith("harden (dry-run): 4 would be enabled")
        and "nothing was changed" in lines[-1]
    )


def test_dry_run_with_everything_on_has_nothing_to_do(proj):
    gh = FakeGh()
    lines, code = harden.run(proj, dry_run=True, gh=gh)
    assert gh.writes == [] and code == 0
    assert lines[-1].startswith("harden (dry-run): 0 would be enabled, 4 already on")


def test_dry_run_with_gh_unusable_prints_the_plan_with_unknown_states(proj):
    lines, code = harden.run(proj, dry_run=True, gh=lambda m, p, b=None: (0, None))
    assert code == 0
    assert lines[0] == "me/proj (visibility unknown)"
    assert sum("state unknown" in ln for ln in lines) == 4


# --- owner/repo from the git remote ---------------------------------------------------------------


def git_repo(path, remote=None):
    path.mkdir(parents=True, exist_ok=True)
    common.git("init", "-b", "main", cwd=path)
    if remote:
        common.git("remote", "add", "origin", remote, cwd=path)
    return path


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/me/proj.git",
        "https://github.com/me/proj",
        "https://github.com/me/proj/",
        "git@github.com:me/proj.git",
        "ssh://git@github.com/me/proj.git",
    ],
)
def test_repo_slug_forms(tmp_path, url):
    assert harden.repo_slug(git_repo(tmp_path / "p", url)) == ("me", "proj")


@pytest.mark.parametrize(
    "url",
    [None, "https://gitlab.com/me/proj.git", "https://github.com/me", "https://github.com/a/b/c"],
)
def test_repo_slug_rejects_non_github_or_missing(tmp_path, url):
    with pytest.raises(FactoryError):
        harden.repo_slug(git_repo(tmp_path / "p", url))
