"""FACT-35: SonarCloud in the kit. Templates, adopt/sync, the workflow guard, doctor lines.

Template and adopt tests run against the REAL kit (like tests/test_integration.py); the guard step
is extracted from the real workflow YAML and executed with bash; doctor tests stub
`harden.gh_api`, so the suite never reaches the network (conftest `no_real_gh`)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from swfactory import __version__, checks, common, harden
from swfactory.cli import main

ROOT = common.FACTORY_ROOT
STACKS = ["python", "node"]
WORKFLOW = ".github/workflows/sonar.yml"
PROPS = "sonar-project.properties"
MARKER = "LEAK-MARKER-xyz"  # sits in every secret value / error body; must never be printed
NOTICE = "::notice"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def kit_workflow(stack: str) -> dict:
    return yaml.safe_load((ROOT / "kit" / "sonar" / f"{stack}.yml").read_text(encoding="utf-8"))


def steps(stack: str) -> list[dict]:
    return kit_workflow(stack)["jobs"]["sonar"]["steps"]


def make_project(
    tmp_path: Path,
    stack: str = "python",
    *,
    remote: str | None = "https://github.com/me/proj.git",
    branch: str = "main",
) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    common.git("init", "-b", branch, cwd=p)
    if remote:
        common.git("remote", "add", "origin", remote, cwd=p)
    if stack == "python":
        write(p / "pyproject.toml", '[project]\nname = "proj"\n')
    elif stack == "node":
        write(p / "package.json", '{"name": "proj", "scripts": {}}\n')
    return p


def adopt(p: Path, *flags: str) -> int:
    return main(["adopt", str(p), *flags])


# --- the kit: manifest and templates (AC1, AC2) ----------------------------------------------


def test_manifest_registers_both_files_as_create_mode_for_python_and_node():
    manifest = yaml.safe_load((ROOT / "kit" / "manifest.yaml").read_text(encoding="utf-8"))
    for dest in (WORKFLOW, PROPS):
        entries = [e for e in manifest["files"] if e["dest"] == dest]
        assert sorted(e["stack"] for e in entries) == sorted(STACKS), dest
        assert {e["mode"] for e in entries} == {"create"}, dest
        for e in entries:
            assert (ROOT / e["src"]).is_file()


@pytest.mark.parametrize("stack", STACKS)
def test_adopt_lays_both_files_with_project_key_and_placeholder(tmp_path, stack):
    p = make_project(tmp_path, stack)
    assert adopt(p) == 0
    props = (p / PROPS).read_text(encoding="utf-8")
    assert "sonar.projectKey=me_proj\n" in props
    assert f"sonar.organization={checks.SONAR_PLACEHOLDER}_SONAR_ORGANIZATION\n" in props
    assert checks.sonar_placeholders(props) == ["sonar.organization"]
    assert yaml.safe_load((p / WORKFLOW).read_text(encoding="utf-8"))["name"] == "sonar"


@pytest.mark.parametrize("stack", STACKS)
def test_properties_templates_set_sonar_tests_and_nested_test_inclusions(tmp_path, stack):
    """FACT-40 AC10: `sonar.tests=.` beside `sonar.sources=.` (tests live under the source tree), so
    the inclusions classify files and the scanner stops guessing test files from their names."""
    template = (ROOT / "kit" / "sonar" / f"{stack}.properties").read_text(encoding="utf-8")
    lines = [ln for ln in template.splitlines() if ln and not ln.startswith("#")]
    assert "sonar.sources=." in lines and "sonar.tests=." in lines
    inclusions = next(ln for ln in lines if ln.startswith("sonar.test.inclusions="))
    if stack == "python":
        assert "**/tests/**" in inclusions.split("=", 1)[1].split(",")
    p = make_project(tmp_path, stack)
    assert adopt(p) == 0
    assert "sonar.tests=.\n" in (p / PROPS).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("stack", "wanted", "other"),
    [
        ("python", "sonar.python.coverage.reportPaths=coverage.xml", "lcov.info"),
        ("node", "sonar.javascript.lcov.reportPaths=coverage/lcov.info", "coverage.xml"),
    ],
)
def test_python_properties_point_at_coverage_xml_and_node_at_lcov(tmp_path, stack, wanted, other):
    p = make_project(tmp_path, stack)
    assert adopt(p) == 0
    props = (p / PROPS).read_text(encoding="utf-8")
    assert wanted in props.splitlines()
    assert other not in props


@pytest.mark.parametrize("stack", STACKS)
def test_adopt_without_a_github_remote_marks_the_project_key_too(tmp_path, stack):
    p = make_project(tmp_path, stack, remote=None)
    assert adopt(p) == 0
    props = (p / PROPS).read_text(encoding="utf-8")
    assert f"sonar.projectKey={checks.SONAR_PLACEHOLDER}_OWNER_REPO\n" in props
    assert checks.sonar_placeholders(props) == ["sonar.organization", "sonar.projectKey"]


def test_a_non_github_remote_also_gets_the_marked_project_key(tmp_path):
    p = make_project(tmp_path, remote="https://gitlab.com/me/proj.git")
    assert adopt(p) == 0
    assert "sonar.projectKey=REPLACE_ME_OWNER_REPO" in (p / PROPS).read_text(encoding="utf-8")


@pytest.mark.parametrize("stack", STACKS)
def test_adopt_points_a_new_sonar_workflow_at_the_default_branch(tmp_path, stack):
    p = make_project(tmp_path, stack, branch="trunk")
    assert adopt(p) == 0
    on = yaml.safe_load((p / WORKFLOW).read_text(encoding="utf-8"))
    assert on[True]["push"]["branches"] == ["trunk"]


@pytest.mark.parametrize("stack", ["docs", "other"])
def test_docs_and_other_stacks_get_no_sonar_files(tmp_path, stack):
    p = make_project(tmp_path, "none")
    assert adopt(p, "--stack", stack) == 0
    assert not (p / WORKFLOW).exists() and not (p / PROPS).exists()


def test_the_rendering_token_never_leaks_into_a_project(tmp_path):
    p = make_project(tmp_path)
    assert adopt(p) == 0
    for rel in (WORKFLOW, PROPS):
        assert "{{project_key}}" not in (p / rel).read_text(encoding="utf-8")


def test_sync_after_adopt_is_up_to_date_and_never_overwrites_edits(tmp_path, capsys):
    p = make_project(tmp_path)
    assert adopt(p) == 0
    capsys.readouterr()
    assert main(["sync", str(p)]) == 0
    assert "up to date" in capsys.readouterr().out

    edited = {
        PROPS: "sonar.organization=my-org\nsonar.projectKey=me_proj\n# mine\n",
        WORKFLOW: "name: my own sonar\n",
    }
    for rel, text in edited.items():
        write(p / rel, text)
    assert main(["sync", str(p)]) == 0
    assert main(["sync", "--check", str(p)]) == 0
    for rel, text in edited.items():
        assert (p / rel).read_text(encoding="utf-8") == text
    managed = common.load_yaml(p / ".factory" / "factory.yaml")["managed"]
    assert not [k for k in managed if "sonar" in k]


def test_sync_check_ignores_missing_sonar_files(tmp_path):
    p = make_project(tmp_path)
    assert adopt(p) == 0
    (p / WORKFLOW).unlink()
    (p / PROPS).unlink()
    assert main(["sync", "--check", str(p)]) == 0


def test_the_real_kit_lints_clean():
    assert [f for f in checks.lint_factory(ROOT) if f.level == checks.FAIL] == []


# --- the workflow (AC3) ------------------------------------------------------------------------


@pytest.mark.parametrize("stack", STACKS)
def test_triggers_are_push_on_one_branch_and_pull_request(stack):
    on = kit_workflow(stack)[True]
    assert set(on) == {"push", "pull_request"}
    assert on["push"]["branches"] == ["main"]


@pytest.mark.parametrize("stack", STACKS)
def test_job_runs_only_for_same_repository_pull_requests(stack):
    cond = kit_workflow(stack)["jobs"]["sonar"]["if"]
    assert "github.event_name != 'pull_request'" in cond
    assert "github.event.pull_request.head.repo.full_name == github.repository" in cond
    assert " || " in cond


@pytest.mark.parametrize("stack", STACKS)
def test_checkout_has_full_history(stack):
    checkout = next(s for s in steps(stack) if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == 0


@pytest.mark.parametrize("stack", STACKS)
def test_scan_uses_the_pinned_action_and_the_secret(stack):
    scan = next(s for s in steps(stack) if "sonarqube-scan-action" in s.get("uses", ""))
    assert scan["uses"].startswith("SonarSource/sonarqube-scan-action@")
    assert scan["env"]["SONAR_TOKEN"] == "${{ secrets.SONAR_TOKEN }}"
    assert scan["env"]["SONAR_HOST_URL"] == "${{ vars.SONAR_HOST_URL || 'https://sonarcloud.io' }}"


@pytest.mark.parametrize("stack", STACKS)
def test_organisation_and_project_key_come_only_from_the_properties_file(stack):
    text = (ROOT / "kit" / "sonar" / f"{stack}.yml").read_text(encoding="utf-8")
    assert "sonar.organization" not in text and "sonar.projectKey" not in text
    assert "pull_request_target" not in text


@pytest.mark.parametrize("stack", STACKS)
def test_permissions_grant_no_write_scope(stack):
    perms = kit_workflow(stack)["permissions"]
    assert perms == {"contents": "read", "pull-requests": "read"}


@pytest.mark.parametrize("stack", STACKS)
def test_the_token_is_never_expanded_inside_a_script(stack):
    for s in steps(stack):
        assert "secrets." not in s.get("run", ""), s.get("name")


def run_lines(stack: str) -> str:
    return "\n".join(s["run"] for s in steps(stack) if "run" in s and s.get("id") != "guard")


SHA_USES = re.compile(r"^\s*(?:- )?uses: (?P<action>[\w.-]+/[\w.-]+)@(?P<ref>\S+)(?P<rest>.*)$")


@pytest.mark.parametrize("stack", STACKS)
def test_third_party_actions_are_pinned_to_a_commit_sha(stack):
    """FACT-40 (Sonar githubactions:S7637): every action outside `actions/` is a full commit SHA
    with its version in a trailing comment, so Dependabot can keep it current."""
    text = (ROOT / "kit" / "sonar" / f"{stack}.yml").read_text(encoding="utf-8")
    uses = [m for m in map(SHA_USES.match, text.splitlines()) if m]
    assert uses
    third_party = [m for m in uses if not m["action"].startswith("actions/")]
    assert {m["action"] for m in third_party} >= {"SonarSource/sonarqube-scan-action"}
    for m in third_party:
        assert re.fullmatch(r"[0-9a-f]{40}", m["ref"]), m.group(0)
        assert re.fullmatch(r"\s+# v\d+(\.\d+){0,2}", m["rest"]), m.group(0)


def test_python_template_installs_only_from_the_lock():
    """FACT-40 (Sonar githubactions:S8544): no `--with`, no unlocked `uv sync` or `uv run`."""
    runs = [s["run"] for s in steps("python") if "uv " in s.get("run", "")]
    assert runs
    assert not [r for r in runs if "--with" in r]
    sync = next(r for r in runs if r.startswith("uv sync"))
    assert "--locked" in sync.split()
    test = next(r for r in runs if "pytest" in r)
    assert test.startswith("uv run --locked --no-sync python -m pytest")


def test_python_template_produces_coverage_xml_before_the_scan():
    text = run_lines("python")
    assert "--cov-report=xml:coverage.xml" in text and "--with pytest-cov" not in text
    names = [s.get("uses", "") + s.get("run", "") for s in steps("python")]
    cov = next(i for i, t in enumerate(names) if "coverage.xml" in t)
    scan = next(i for i, t in enumerate(names) if "sonarqube-scan-action" in t)
    assert cov < scan


def test_node_template_produces_lcov_before_the_scan():
    assert "--coverage" in run_lines("node")
    names = [s.get("uses", "") + s.get("run", "") for s in steps("node")]
    cov = next(i for i, t in enumerate(names) if "--coverage" in t)
    scan = next(i for i, t in enumerate(names) if "sonarqube-scan-action" in t)
    assert cov < scan


@pytest.mark.parametrize("stack", STACKS)
def test_every_step_after_the_guard_waits_for_it(stack):
    seq = steps(stack)
    at = next(i for i, s in enumerate(seq) if s.get("id") == "guard")
    after = seq[at + 1 :]
    assert after, "nothing after the guard"
    for s in after:
        assert "steps.guard.outputs.enabled == 'true'" in s.get("if", ""), s
    # and nothing that costs minutes or touches the network runs before it, except checkout
    assert [s.get("uses", "").split("@")[0] for s in seq[:at]] == ["actions/checkout"]


def test_the_guard_and_scan_steps_are_identical_in_both_templates():
    def pick(stack):
        return [
            s for s in steps(stack) if s.get("id") == "guard" or "scan-action" in s.get("uses", "")
        ]

    assert pick("python") == pick("node")
    assert len(pick("python")) == 2


# --- the guard (AC4): extract the step's script from the YAML and run it -----------------------


def find_bash() -> str | None:
    if os.name == "nt":  # the System32 bash is WSL: it does not see our environment or paths
        git = shutil.which("git")
        if git:
            for up in (1, 2):
                try:
                    cand = Path(git).resolve().parents[up] / "bin" / "bash.exe"
                except IndexError:
                    continue
                if cand.is_file():
                    return str(cand)
        return None
    return shutil.which("bash")


BASH = find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no POSIX bash available to run the guard")

FILLED = "sonar.organization=my-org\nsonar.projectKey=me_proj\n"


def guard_script(stack: str) -> str:
    return next(s for s in steps(stack) if s.get("id") == "guard")["run"]


def run_guard(tmp_path: Path, stack: str, *, token: str | None, props: str | None):
    work = tmp_path / "work"
    work.mkdir()
    if props is not None:
        write(work / PROPS, props)
    out = tmp_path / "github_output"
    out.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "SONAR_TOKEN"}
    env["GITHUB_OUTPUT"] = out.as_posix()
    if token is not None:
        env["SONAR_TOKEN"] = token
    r = subprocess.run(
        [BASH, "--noprofile", "--norc", "-eo", "pipefail", "-c", guard_script(stack)],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )
    return r, out.read_text(encoding="utf-8")


@needs_bash
@pytest.mark.parametrize("stack", STACKS)
@pytest.mark.parametrize("token", [None, ""])
def test_guard_without_the_secret_exits_zero_with_a_notice(tmp_path, stack, token):
    r, output = run_guard(tmp_path, stack, token=token, props=FILLED)
    assert r.returncode == 0, r.stderr
    assert NOTICE in r.stdout and "SONAR_TOKEN" in r.stdout
    assert "enabled=false" in output and "enabled=true" not in output


@needs_bash
@pytest.mark.parametrize("stack", STACKS)
def test_guard_with_a_token_but_no_properties_file_skips(tmp_path, stack):
    r, output = run_guard(tmp_path, stack, token="t0ken-" + MARKER, props=None)
    assert r.returncode == 0, r.stderr
    assert NOTICE in r.stdout and PROPS in r.stdout
    assert "enabled=false" in output
    assert MARKER not in r.stdout + r.stderr + output


@needs_bash
@pytest.mark.parametrize("stack", STACKS)
def test_guard_with_a_token_and_a_placeholder_skips(tmp_path, stack):
    props = "sonar.organization=REPLACE_ME_SONAR_ORGANIZATION\nsonar.projectKey=me_proj\n"
    r, output = run_guard(tmp_path, stack, token="t0ken-" + MARKER, props=props)
    assert r.returncode == 0, r.stderr
    assert NOTICE in r.stdout and "organization" in r.stdout
    assert "enabled=false" in output
    assert MARKER not in r.stdout + r.stderr + output


@needs_bash
@pytest.mark.parametrize("stack", STACKS)
def test_guard_with_a_token_and_filled_properties_enables_the_scan_without_echoing_it(
    tmp_path, stack
):
    r, output = run_guard(tmp_path, stack, token="t0ken-" + MARKER, props=FILLED)
    assert r.returncode == 0, r.stderr
    assert output.strip() == "enabled=true"
    assert MARKER not in r.stdout + r.stderr + output


PROPS_CASES = [
    "# REPLACE_ME is the marker\n" + FILLED,  # a comment mentioning it is not a placeholder
    "   # indented comment REPLACE_ME\n" + FILLED,
    FILLED,
    "sonar.organization=REPLACE_ME_SONAR_ORGANIZATION\nsonar.projectKey=me_proj\n",
    "sonar.organization = my-org\nsonar.projectKey = REPLACE_ME_OWNER_REPO\n",
    "sonar.organization=REPLACE_ME_SONAR_ORGANIZATION\nsonar.projectKey=REPLACE_ME_OWNER_REPO\n",
]


@needs_bash
@pytest.mark.parametrize("props", PROPS_CASES)
def test_guard_and_doctor_agree_on_what_a_placeholder_is(tmp_path, props):
    _, output = run_guard(tmp_path, "python", token="x", props=props)
    assert ("enabled=true" in output) == (checks.sonar_placeholders(props) == [])


# --- placeholder detection ------------------------------------------------------------------------


def test_placeholder_detection_names_keys_and_ignores_comments():
    text = (
        "# REPLACE_ME in a comment\n"
        "  # also in an indented one REPLACE_ME\n"
        "sonar.organization=REPLACE_ME_SONAR_ORGANIZATION\n"
        "sonar.projectKey = me_proj\n"
        "sonar.sources=.\n"
    )
    assert checks.sonar_placeholders(text) == ["sonar.organization"]
    assert checks.sonar_placeholders("sonar.other : REPLACE_ME_X\n") == ["sonar.other"]
    assert checks.sonar_placeholders("sonar.projectKey = REPLACE_ME_OWNER_REPO") == [
        "sonar.projectKey"
    ]
    assert checks.sonar_placeholders(FILLED) == []
    assert checks.sonar_placeholders("") == []


# --- doctor (AC5, AC6) -------------------------------------------------------------------------

SECRETS = "repos/me/proj/actions/secrets"


class SecretGh:
    """Stands in for `harden.gh_api`: answers the secret list, records every call. The list carries
    MARKER in value fields (the real API never would): whatever happens, it must not be printed."""

    def __init__(self, names=("SONAR_TOKEN", "OTHER"), *, status=200, total=None):
        self.names, self.status, self.total = list(names), status, total
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if not path.startswith(SECRETS):
            return 404, None
        if self.status != 200:
            return self.status, {"message": MARKER}
        secrets = [
            {"name": n, "value": MARKER, "encrypted_value": MARKER, "created_at": "2026-01-01"}
            for n in self.names
        ]
        return 200, {"total_count": self.total or len(secrets), "secrets": secrets}


@pytest.fixture
def adopted(tmp_path):
    p = make_project(tmp_path, "none")
    common.dump_yaml(
        {"factory_version": __version__, "stack": "python", "skill_targets": [], "managed": {}},
        p / ".factory" / "factory.yaml",
    )
    return p


def configure(p: Path, props: str = FILLED) -> None:
    write(p / WORKFLOW, "name: sonar\n")
    write(p / PROPS, props)


PLACEHOLDER = "sonar.organization=REPLACE_ME_SONAR_ORGANIZATION\nsonar.projectKey=me_proj\n"


def sonar(p: Path, gh) -> dict[str, checks.Finding]:
    return {f.name: f for f in checks.check_sonar(p, gh)}


def test_secret_present_is_ok_and_calls_only_the_list(adopted):
    configure(adopted)
    gh = SecretGh()
    f = sonar(adopted, gh)
    assert f["sonar: SONAR_TOKEN"].level == checks.OK
    assert "present" in f["sonar: SONAR_TOKEN"].detail
    assert [c[:2] for c in gh.calls if SECRETS in c[1]] == [("GET", f"{SECRETS}?per_page=100")]
    assert f["sonar: properties"].level == checks.OK


def test_secret_absent_with_filled_properties_warns(adopted):
    configure(adopted)
    f = sonar(adopted, SecretGh(names=["OTHER"]))["sonar: SONAR_TOKEN"]
    assert (
        f.level == checks.WARN and "not set" in f.detail and "gh secret set SONAR_TOKEN" in f.detail
    )


def test_secret_absent_while_the_placeholder_remains_is_only_a_notice(adopted):
    configure(adopted, PLACEHOLDER)
    f = sonar(adopted, SecretGh(names=[]))
    assert (
        f["sonar: SONAR_TOKEN"].level == checks.OK and "not set" in f["sonar: SONAR_TOKEN"].detail
    )
    assert f["sonar: properties"].level == checks.OK
    assert "sonar.organization" in f["sonar: properties"].detail


def test_secret_present_but_placeholder_remains_warns_naming_the_key(adopted):
    configure(adopted, PLACEHOLDER)
    f = sonar(adopted, SecretGh())["sonar: properties"]
    assert f.level == checks.WARN
    assert "sonar.organization" in f.detail and "sonar.projectKey" not in f.detail


def test_placeholder_in_a_comment_does_not_count(adopted):
    configure(adopted, "# REPLACE_ME: set the organisation\n" + FILLED)
    assert sonar(adopted, SecretGh())["sonar: properties"].level == checks.OK


def test_missing_properties_file_warns(adopted):
    write(adopted / WORKFLOW, "name: sonar\n")
    f = sonar(adopted, SecretGh())["sonar: properties"]
    assert f.level == checks.WARN and PROPS in f.detail


def test_gh_unusable_is_unknown_never_not_set(adopted):
    configure(adopted)
    f = sonar(adopted, harden.gh_api)["sonar: SONAR_TOKEN"]  # the conftest guard makes gh inert
    assert f.level == checks.WARN and "unknown" in f.detail and "not set" not in f.detail


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_http_failures_are_unknown_with_the_status_only(adopted, status):
    configure(adopted)
    f = sonar(adopted, SecretGh(status=status))["sonar: SONAR_TOKEN"]
    assert f.level == checks.WARN and f"unknown (HTTP {status})" in f.detail
    assert MARKER not in f.detail and "not set" not in f.detail


def test_a_second_page_of_secrets_makes_absence_unknown(adopted):
    configure(adopted)
    names = [f"S{i}" for i in range(100)]
    f = sonar(adopted, SecretGh(names=names, total=150))["sonar: SONAR_TOKEN"]
    assert f.level == checks.WARN and "unknown" in f.detail and "100" in f.detail
    found = sonar(adopted, SecretGh(names=[*names[:99], "SONAR_TOKEN"], total=150))
    assert "present" in found["sonar: SONAR_TOKEN"].detail


@pytest.mark.parametrize("remote", [None, "https://gitlab.com/me/proj.git"])
def test_no_github_remote_skips_the_secret_check_without_a_call(tmp_path, remote):
    p = make_project(tmp_path, "none", remote=remote)
    configure(p)
    gh = SecretGh()
    f = sonar(p, gh)["sonar: SONAR_TOKEN"]
    assert f.level == checks.OK and "skipped" in f.detail
    assert gh.calls == []


def test_nothing_configured_is_one_notice_and_no_github_call(adopted):
    gh = SecretGh()
    findings = checks.check_sonar(adopted, gh)
    assert [(f.level, f.name) for f in findings] == [(checks.OK, "sonar")]
    assert "not configured" in findings[0].detail
    assert gh.calls == []


def doctor_out(capsys, p) -> tuple[int, str]:
    code = main(["doctor", str(p)])
    return code, capsys.readouterr().out


def test_doctor_prints_presence_but_never_a_value(adopted, monkeypatch, capsys):
    configure(adopted)
    monkeypatch.setattr(harden, "gh_api", SecretGh())
    code, out = doctor_out(capsys, adopted)
    assert code == 0
    (line,) = [ln for ln in out.splitlines() if "sonar: SONAR_TOKEN" in ln]
    assert line.startswith("OK") and "present" in line
    assert MARKER not in out and "encrypted" not in out


@pytest.mark.parametrize("status", [403, 500])
def test_doctor_does_not_print_an_error_body(adopted, monkeypatch, capsys, status):
    configure(adopted)
    monkeypatch.setattr(harden, "gh_api", SecretGh(status=status))
    code, out = doctor_out(capsys, adopted)
    assert code == 0 and f"HTTP {status}" in out and MARKER not in out


@pytest.mark.parametrize("props", [None, FILLED, PLACEHOLDER])
@pytest.mark.parametrize("names", [[], ["SONAR_TOKEN"]])
def test_doctor_never_exits_one_because_of_sonar(adopted, monkeypatch, capsys, props, names):
    # the protections come from the same stub (404 -> unknown -> WARN): nothing here may FAIL
    monkeypatch.setattr(harden, "gh_api", SecretGh(names=names))
    if props is None:
        write(adopted / WORKFLOW, "name: sonar\n")
    else:
        configure(adopted, props)
    code, out = doctor_out(capsys, adopted)
    assert code == 0 and "FAIL" not in out
    assert [ln for ln in out.splitlines() if "sonar:" in ln]


def test_doctor_on_a_project_without_sonar_files_prints_one_notice(adopted, monkeypatch, capsys):
    gh = SecretGh()
    monkeypatch.setattr(harden, "gh_api", gh)
    code, out = doctor_out(capsys, adopted)
    assert code == 0
    assert len([ln for ln in out.splitlines() if ln.startswith("OK    sonar ")]) == 1
    assert not [c for c in gh.calls if "actions/secrets" in c[1]]


def test_doctor_after_a_real_adopt_has_no_warning_for_a_local_only_project(tmp_path, capsys):
    p = make_project(tmp_path, "python", remote=None)
    assert adopt(p) == 0
    capsys.readouterr()
    code, out = doctor_out(capsys, p)
    warns = [ln for ln in out.splitlines() if ln.startswith("WARN")]
    assert code == 0 and "FAIL" not in out
    assert len(warns) == 1 and "no approved charter" in warns[0]  # the charter template (FACT-47)
    assert "sonar: properties" in out


# --- docs (AC7) --------------------------------------------------------------------------------


def test_the_how_to_covers_every_owner_step():
    text = (ROOT / "docs" / "sonarcloud.md").read_text(encoding="utf-8")
    for needle in (
        "organization",
        "Analyze new project",
        "Automatic Analysis",
        "My Account",
        "gh secret set SONAR_TOKEN",
        "<owner>_<repo>",
        "sonar-scanner",
        "SONAR_TOKEN",
        "REPLACE_ME_SONAR_ORGANIZATION",
        "factory doctor",
    ):
        assert needle in text, needle
    assert "sonar.qualitygate.wait=true" in text  # the opt-in for a failing gate


def doc_text() -> str:
    return " ".join((ROOT / "docs" / "sonarcloud.md").read_text(encoding="utf-8").split())


def test_the_doc_states_the_public_project_and_main_branch_facts():
    """FACT-40 AC7: two facts that cost real time, with the exact repair commands."""
    text = doc_text()
    assert "free plan" in text and "must be public" in text
    assert "succeeds" in text and "nothing can be read" in text
    assert "main branch" in text and "default branch" in text and "`master`" in text
    delete = 'curl -s -X POST -u "$SONAR_TOKEN:" "https://sonarcloud.io/api/project_branches/delete?project='
    rename = 'curl -s -X POST -u "$SONAR_TOKEN:" "https://sonarcloud.io/api/project_branches/rename?project='
    assert delete in text and rename in text
    assert text.index("project_branches/delete") < text.index("project_branches/rename")
    assert "sonar: server" in text  # doctor detects it


def test_the_doc_names_sonar_tests():
    text = doc_text()
    assert "sonar.tests=." in text and "sonar: tests" in text


def test_the_doc_local_scan_recipe_uses_only_locked_dependencies():
    text = doc_text()
    assert "--with pytest-cov" not in text
    assert (
        "uv run --locked --no-sync python -m pytest" in text and "uv add --dev pytest-cov" in text
    )


def test_security_policy_has_exactly_one_pointer_line():
    text = (ROOT / "policies" / "security.md").read_text(encoding="utf-8")
    assert len([ln for ln in text.splitlines() if "sonarcloud.md" in ln]) == 1


def test_treaty_and_readme_mention_the_new_files_and_doctor_lines():
    arch = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "sonar.yml" in arch and "sonar-project.properties" in arch and "SONAR_TOKEN" in arch
    assert "sonarcloud.md" in (ROOT / "README.md").read_text(encoding="utf-8")
