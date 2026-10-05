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
