"""FACT-40 AC8: `factory doctor` reads the SonarCloud project through the public API (no token).

Everything is stubbed: the GitHub side through `harden.gh_api`'s signature, the SonarCloud side
through the `fetch` argument (`sonar.http_get`'s signature). conftest makes the real network
function inert."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from swfactory import __version__, checks, common, sonar
from swfactory.cli import main

REAL_REQUEST = sonar._request  # captured at import, before conftest's autouse fixture replaces it

KEY = "me_proj"
MARKER = "LEAK-MARKER-xyz"
BASE = "https://sonarcloud.io/api"
SHOW = f"{BASE}/components/show?component={KEY}"
BRANCHES = f"{BASE}/project_branches/list?project={KEY}"
FILLED = f"sonar.organization=my-org\nsonar.projectKey={KEY}\n"
PLACEHOLDER = "sonar.organization=REPLACE_ME_SONAR_ORGANIZATION\nsonar.projectKey=me_proj\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_project(tmp_path: Path, props: str = FILLED, *, remote: str | None = None) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    common.git("init", "-b", "main", cwd=p)
    if remote is not False:
        common.git("remote", "add", "origin", remote or "https://github.com/me/proj.git", cwd=p)
    common.dump_yaml(
        {"factory_version": __version__, "stack": "python", "skill_targets": [], "managed": {}},
        p / ".factory" / "factory.yaml",
    )
    write(p / ".github" / "workflows" / "sonar.yml", "name: sonar\n")
    write(p / "sonar-project.properties", props)
    return p


class Gh:
    """GitHub: the secret list and the repository (its default branch)."""

    def __init__(self, default="main", repo_status=200):
        self.default, self.repo_status = default, repo_status
        self.calls: list[str] = []

    def __call__(self, method, path, body=None):
        self.calls.append(path)
        if path == "repos/me/proj":
            if self.repo_status != 200:
                return self.repo_status, {"message": MARKER}
            # private: the protections read as "not available", so `doctor` has nothing to FAIL on
            return 200, {"default_branch": self.default, "private": True, "token": MARKER}
        if path.startswith("repos/me/proj/actions/secrets"):
            return 200, {"total_count": 1, "secrets": [{"name": "SONAR_TOKEN"}]}
        return 404, None


class Server:
    """SonarCloud's public API as `sonar.http_get` sees it."""

    def __init__(self, *, show=None, branches=None):
        public = {"component": {"key": KEY, "visibility": "public", "secret": MARKER}}
        self.routes = {
            SHOW: (200, public) if show is None else show,
            BRANCHES: (200, {"branches": [{"name": "main", "isMain": True}]})
            if branches is None
            else branches,
        }
        self.calls: list[str] = []

    def __call__(self, url):
        self.calls.append(url)
        return self.routes.get(url, (404, None))


def server_finding(p: Path, gh=None, fetch=None) -> checks.Finding:
    found = checks.check_sonar(p, gh or Gh(), fetch or Server())
    (f,) = [f for f in found if f.name == "sonar: server"]
    return f


def test_ok_when_public_and_the_main_branch_matches(tmp_path):
    f = server_finding(make_project(tmp_path))
    assert f.level == checks.OK
    assert "public" in f.detail and "'main'" in f.detail and "matches" in f.detail


def test_the_reader_asks_exactly_two_anonymous_get_urls(tmp_path):
    srv = Server()
    server_finding(make_project(tmp_path), fetch=srv)
    assert srv.calls == [SHOW, BRANCHES]


def test_mismatch_prints_the_repair_commands(tmp_path):
    branches = (200, {"branches": [{"name": "master", "isMain": True}]})
    f = server_finding(make_project(tmp_path), fetch=Server(branches=branches))
    assert f.level == checks.WARN
    assert "'master'" in f.detail and "'main'" in f.detail
    url = f"{BASE}/project_branches/rename?project={KEY}&name=main"
    rename = f'curl -s -X POST -u "$SONAR_TOKEN:" "{url}"'
    assert rename in f.detail
    assert "project_branches/delete" not in f.detail  # no side branch named main: nothing to delete
    assert "docs/sonarcloud.md" in f.detail


def test_the_delete_command_comes_first_and_only_with_a_side_branch(tmp_path):
    branches = (
        200,
        {"branches": [{"name": "master", "isMain": True}, {"name": "main", "isMain": False}]},
    )
    f = server_finding(make_project(tmp_path), fetch=Server(branches=branches))
    assert f.level == checks.WARN
    delete = f'"{BASE}/project_branches/delete?project={KEY}&branch=main"'
    assert delete in f.detail
    assert f.detail.index("project_branches/delete") < f.detail.index("project_branches/rename")


def test_a_different_default_branch_is_used_in_the_commands(tmp_path):
    f = server_finding(make_project(tmp_path), gh=Gh(default="trunk"))
    assert f.level == checks.WARN
    assert "name=trunk" in f.detail and "'trunk'" in f.detail


@pytest.mark.parametrize(
    "show",
    [(404, {"errors": [{"msg": MARKER}]}), (200, {"component": {"visibility": "private"}})],
)
def test_not_found_and_private_warn_that_the_project_must_be_public(tmp_path, show):
    srv = Server(show=show)
    f = server_finding(make_project(tmp_path), fetch=srv)
    assert f.level == checks.WARN
    assert "public" in f.detail and "free plan" in f.detail
    assert MARKER not in f.detail
    assert BRANCHES not in srv.calls  # nothing readable: no second call


@pytest.mark.parametrize(
    ("show", "branches"),
    [
        ((500, None), None),
        ((0, None), None),
        ((200, "not json at all"), None),
        ((200, {"component": {}}), None),  # no visibility at all
        (None, (500, None)),
        (None, (0, None)),
        (None, (200, {"branches": []})),
        (None, (200, {"branches": [{"name": "main", "isMain": False}]})),  # nothing is main
        (None, (200, {"branches": "x"})),
        (None, (200, ["not", "a", "dict"])),
        (None, (200, {"branches": [{"isMain": True}]})),  # main without a name
    ],
)
def test_every_failure_is_unknown(tmp_path, show, branches):
    f = server_finding(make_project(tmp_path), fetch=Server(show=show, branches=branches))
    assert f.level == checks.WARN and f.detail.startswith("unknown"), f.detail
    assert MARKER not in f.detail


@pytest.mark.parametrize("status", [0, 403, 404, 500])
def test_unreadable_github_default_branch_is_unknown_without_a_sonar_call(tmp_path, status):
    srv = Server()
    f = server_finding(make_project(tmp_path), gh=Gh(repo_status=status), fetch=srv)
    assert f.level == checks.WARN and f.detail.startswith("unknown")
    assert MARKER not in f.detail
    assert srv.calls == []


def test_a_malformed_default_branch_is_unknown(tmp_path):
    class Odd(Gh):
        def __call__(self, method, path, body=None):
            return (
                (200, {"default_branch": None})
                if path == "repos/me/proj"
                else super().__call__(method, path, body)
            )

    f = server_finding(make_project(tmp_path), gh=Odd())
    assert f.level == checks.WARN and f.detail.startswith("unknown")


@pytest.mark.parametrize("key", ["a b", "x;rm -rf", "a/b", "k&evil=1", ""])
def test_an_unsafe_project_key_is_never_sent(tmp_path, key):
    srv = Server()
    f = server_finding(
        make_project(tmp_path, f"sonar.organization=o\nsonar.projectKey={key}\n"), fetch=srv
    )
    assert f.level == checks.WARN and f.detail.startswith("unknown")
    assert srv.calls == []


def test_a_missing_project_key_line_is_unknown(tmp_path):
    srv = Server()
    f = server_finding(make_project(tmp_path, "sonar.organization=o\n"), fetch=srv)
    assert f.detail.startswith("unknown") and srv.calls == []


def test_no_call_while_the_placeholder_remains(tmp_path):
    srv = Server()
    found = checks.check_sonar(make_project(tmp_path, PLACEHOLDER), Gh(), srv)
    assert srv.calls == []
    (f,) = [f for f in found if f.name == "sonar: server"]
    assert f.level == checks.OK and "skipped" in f.detail


@pytest.mark.parametrize("remote", [None, "https://gitlab.com/me/proj.git"])
def test_no_call_without_a_github_remote(tmp_path, remote):
    srv = Server()
    gh = Gh()
    p = make_project(tmp_path, remote=remote if remote else False)
    f = server_finding(p, gh=gh, fetch=srv)
    assert f.level == checks.OK and "skipped" in f.detail
    assert srv.calls == [] and gh.calls == []


def test_a_project_with_no_sonar_files_gets_no_server_finding(tmp_path):
    p = make_project(tmp_path)
    (p / "sonar-project.properties").unlink()
    (p / ".github" / "workflows" / "sonar.yml").unlink()
    srv = Server()
    found = checks.check_sonar(p, Gh(), srv)
    assert [f.name for f in found] == ["sonar"] and srv.calls == []


def test_doctor_prints_the_server_line_and_never_a_secret_or_an_exit_one(
    tmp_path, monkeypatch, capsys
):
    p = make_project(tmp_path)
    monkeypatch.setattr("swfactory.harden.gh_api", Gh())
    monkeypatch.setattr(
        sonar,
        "http_get",
        Server(branches=(200, {"branches": [{"name": "master", "isMain": True}]})),
    )
    code = main(["doctor", str(p)])
    out = capsys.readouterr().out
    assert code == 0 and "FAIL" not in out
    (line,) = [ln for ln in out.splitlines() if "sonar: server" in ln]
    assert line.startswith("WARN") and "project_branches/rename" in line
    assert MARKER not in out


# --- the one function that touches the network ---------------------------------------------------


def test_the_suite_cannot_reach_the_network():
    assert sonar._request is not REAL_REQUEST
    assert sonar._request(SHOW) == (0, "")
    assert sonar.http_get(SHOW) == (0, None)


class Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_real_request_function_maps_outcomes(monkeypatch):
    seen = {}

    def ok(req, timeout=None):
        seen["url"], seen["timeout"] = req.full_url, timeout
        seen["headers"] = dict(req.header_items())
        seen["method"] = req.get_method()
        return Response(json.dumps({"a": 1}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", ok)
    assert REAL_REQUEST(SHOW) == (200, '{"a": 1}')
    assert seen["url"] == SHOW and seen["method"] == "GET" and 0 < seen["timeout"] <= 30
    assert "Authorization" not in seen["headers"]

    def http_error(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", http_error)
    assert REAL_REQUEST(SHOW) == (404, "")

    for exc in (urllib.error.URLError("dns"), TimeoutError("slow"), OSError("reset")):

        def boom(req, timeout=None, exc=exc):
            raise exc

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        assert REAL_REQUEST(SHOW) == (0, "")


def test_the_real_request_function_refuses_anything_but_the_sonarcloud_api(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("network call"))
    for url in (
        "http://sonarcloud.io/api/x",
        "https://evil.example/api/x",
        "file:///etc/passwd",
        "https://sonarcloud.io.evil.example/api",
    ):
        assert REAL_REQUEST(url) == (0, "")


def test_http_get_parses_json_and_survives_garbage(monkeypatch):
    for text, expected in (('{"a": 1}', {"a": 1}), ("", None), ("<html>", None), ("[1]", [1])):
        monkeypatch.setattr(sonar, "_request", lambda url, text=text: (200, text))
        assert sonar.http_get(SHOW) == (200, expected)
    monkeypatch.setattr(sonar, "_request", lambda url: (404, '{"errors": []}'))
    assert sonar.http_get(SHOW) == (404, {"errors": []})
