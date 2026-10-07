"""FACT-40: a new `sonar.yml` and `sonar-project.properties` are rendered from the project itself.

The default branch, the project's own test command and the python version of its CI are read when
`adopt` or `sync` CREATES the files (create-mode: an existing file is never touched). All runs
against the REAL kit templates; no network, no project command (conftest)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from swfactory import adopt_inspect, common, sonar
from swfactory.cli import main

ROOT = common.FACTORY_ROOT
WORKFLOW = ".github/workflows/sonar.yml"
CI = ".github/workflows/ci.yml"
PROPS = "sonar-project.properties"
LOCKED_PYTEST = "uv run --locked --no-sync python -m pytest"
XML = "--cov-report=xml:coverage.xml"

DESELECTS = [
    "src/tests/test_e2e.py::TestE2EInvoiceMocked::test_invoice_e2e_mocked",
    "src/tests/test_e2e.py::TestE2ESeedAndRun::test_seeded_definitions_exist",
    "src/tests/test_stabilization.py::TestMaxCyclesOverride::test_override_used_in_recursion_limit",
    "src/tests/test_agent_control.py::TestCompactEndpoint::test_compact_run_not_in_executor_returns_false",
]

ADE_CI = f"""\
name: CI
on:
  push:
    branches: [master]
  pull_request:
    branches: [master]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: Install uv
        uses: astral-sh/setup-uv@v10.2.0
      - name: Set up Python
        run: uv python install 3.11
      - name: Install dependencies
        run: uv sync --all-extras
      # a comment that mentions pytest and python-version: "3.9" must be ignored
      - name: Tests (pytest) with coverage gate
        run: >
          uv run pytest src/tests/ -v --tb=short -m "not integration"
          --cov=src --cov-report=term-missing --cov-fail-under=80
          --deselect {DESELECTS[0]}
          --deselect {DESELECTS[1]}
          --deselect {DESELECTS[2]}
          --deselect {DESELECTS[3]}
  frontend:
    runs-on: ubuntu-latest
    steps:
      - run: pnpm test
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def git(p: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=p,
        check=True,
        capture_output=True,
    )


def make_project(
    tmp_path: Path,
    stack: str = "python",
    *,
    branch: str = "main",
    origin_head: str | None = None,
    lock: bool = True,
    pyproject: str = '[project]\nname = "proj"\n',
) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    git(p, "init", "-b", branch)
    git(p, "remote", "add", "origin", "https://github.com/me/proj.git")
    if stack == "python":
        write(p / "pyproject.toml", pyproject)
        if lock:
            write(p / "uv.lock", "version = 1\n")
    else:
        write(p / "package.json", '{"name": "proj", "scripts": {}}\n')
    if origin_head:
        git(p, "commit", "--allow-empty", "-m", "init")
        git(p, "update-ref", f"refs/remotes/origin/{origin_head}", "HEAD")
        git(p, "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{origin_head}")
    return p


def workflow(p: Path) -> dict:
    return yaml.safe_load((p / WORKFLOW).read_text(encoding="utf-8"))


def push_branches(p: Path) -> list[str]:
    return workflow(p)[True]["push"]["branches"]


def steps(p: Path) -> list[dict]:
    return workflow(p)["jobs"]["sonar"]["steps"]


def coverage_step(p: Path) -> dict:
    return next(s for s in steps(p) if s.get("name", "").startswith("Tests with coverage"))


def prop(p: Path, key: str) -> str:
    for line in (p / PROPS).read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} not in {PROPS}")


def adopt(p: Path) -> int:
    return main(["adopt", str(p)])


def resync(p: Path) -> int:
    """The `sync` path: the project is adopted, the Sonar files are not there yet."""
    (p / WORKFLOW).unlink()
    (p / PROPS).unlink()
    return main(["sync", str(p)])


# --- AC1: the default branch, in both paths ------------------------------------------------------


@pytest.mark.parametrize("stack", ["python", "node"])
@pytest.mark.parametrize("path", ["adopt", "sync"])
def test_sync_and_adopt_point_a_new_workflow_at_master(tmp_path, stack, path):
    p = make_project(tmp_path, stack, branch="master", origin_head="master")
    assert adopt(p) == 0
    if path == "sync":
        assert resync(p) == 0
    assert push_branches(p) == ["master"]


@pytest.mark.parametrize("path", ["adopt", "sync"])
def test_main_stays_main(tmp_path, path):
    p = make_project(tmp_path, origin_head="main")
    assert adopt(p) == 0
    if path == "sync":
        assert resync(p) == 0
    assert push_branches(p) == ["main"]


def test_sync_on_a_feature_branch_still_finds_master(tmp_path):
    p = make_project(tmp_path, branch="master")
    git(p, "commit", "--allow-empty", "-m", "init")
    assert adopt(p) == 0
    git(p, "checkout", "-b", "feature/x")
    assert adopt_inspect.default_branch(p) == "master"
    assert resync(p) == 0
    assert push_branches(p) == ["master"]


def test_default_branch_prefers_origin_head_then_the_only_main_or_master(tmp_path):
    p = make_project(tmp_path, branch="trunk", origin_head="develop")
    assert adopt_inspect.default_branch(p) == "develop"
    q = tmp_path / "q"
    q.mkdir()
    git(q, "init", "-b", "main")
    git(q, "commit", "--allow-empty", "-m", "init")
    git(q, "branch", "master")
    git(q, "checkout", "-b", "feature/y")
    assert adopt_inspect.default_branch(q) == "feature/y"  # both exist: the current branch decides
    git(q, "branch", "-D", "master")
    assert adopt_inspect.default_branch(q) == "main"  # exactly one of them exists
    git(q, "checkout", "-q", "main")
    assert adopt_inspect.default_branch(q) == "main"


def test_an_existing_workflow_is_never_changed_by_sync(tmp_path):
    p = make_project(tmp_path, branch="master", origin_head="master")
    assert adopt(p) == 0
    mine = "name: my own sonar\non:\n  push:\n    branches: [main]\n"
    write(p / WORKFLOW, mine)
    assert main(["sync", str(p)]) == 0
    assert (p / WORKFLOW).read_text(encoding="utf-8") == mine


def test_an_odd_branch_name_keeps_main(tmp_path):
    text = (ROOT / "kit" / "sonar" / "python.yml").read_text(encoding="utf-8")
    assert "branches: [main]" in text
    for odd in ("we ird", "x]; y", "-lead", ""):
        assert adopt_inspect.point_at_branch(text, odd) == text
    assert "branches: [trunk]" in adopt_inspect.point_at_branch(text, "trunk")


# --- AC2: the project's own test command ---------------------------------------------------------


def ci_with(run: str, *, extra: str = "", top: str = "") -> str:
    body = "\n".join(f"          {ln}" for ln in run.splitlines())
    return (
        f"name: ci\non: push\n{top}jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      - uses: actions/checkout@v7\n      - name: tests\n{extra}        run: |\n{body}\n"
    )


def test_the_project_test_command_is_reused_from_an_ade_shaped_ci(tmp_path, capsys):
    p = make_project(tmp_path, branch="master", origin_head="master")
    write(p / CI, ADE_CI)
    assert adopt(p) == 0
    command = coverage_step(p)["run"]
    assert command.startswith(f"{LOCKED_PYTEST} src/tests/ -v --tb=short")
    assert '-m "not integration"' in command
    assert "--cov=src" in command and "--cov-fail-under=80" in command
    for d in DESELECTS:
        assert f"--deselect {d}" in command
    assert command.count(XML) == 1
    assert "--with" not in command and "--frozen" not in command
    assert "sonar.yml: test step taken from" in capsys.readouterr().out
    # nothing else of the template moved
    names = [s.get("name", s.get("uses", "")) for s in steps(p)]
    assert "SonarCloud scan" in names and "Check SonarCloud is set up" in names


def test_long_commands_wrap_without_separating_an_option_from_its_value(tmp_path):
    p = make_project(tmp_path, branch="master", origin_head="master")
    write(p / CI, ADE_CI)
    assert adopt(p) == 0
    text = (p / WORKFLOW).read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if "--deselect" in ln]
    assert len(lines) >= len(DESELECTS)
    for ln in lines:
        assert ln.strip().startswith("--deselect") or " --deselect " in ln
        assert not ln.rstrip().endswith("--deselect")
    command = coverage_step(p)["run"]  # folded back into one line
    assert "\n" not in command and "  " not in command
    folded = sonar._folded(command)
    assert " ".join(ln.strip() for ln in folded) == command
    assert all(len(ln) <= 100 or ln.strip().startswith("--deselect") for ln in folded)


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        ("uv run pytest -q", f"{LOCKED_PYTEST} -q --cov {XML}"),
        ("uv run python -m pytest tests -x", f"{LOCKED_PYTEST} tests -x --cov {XML}"),
        ("pytest -q", f"{LOCKED_PYTEST} -q --cov {XML}"),
        ("python -m pytest", f"{LOCKED_PYTEST} --cov {XML}"),
        (
            f"uv run --frozen --with pytest-cov pytest -q --cov=chatpid {XML}",
            f"{LOCKED_PYTEST} -q --cov=chatpid {XML}",
        ),
        ("uv run --extra dev --python 3.11 pytest", f"{LOCKED_PYTEST} --cov {XML}"),
        (
            "uv run pytest --cov=src --cov-report=term-missing",
            f"{LOCKED_PYTEST} --cov=src --cov-report=term-missing {XML}",
        ),
        (
            "uv run pytest tests/",
            f"{LOCKED_PYTEST} tests/ --cov {XML}",
        ),  # --cov must not eat a path
        (
            'uv run pytest -m "not slow and not db"',
            f'{LOCKED_PYTEST} -m "not slow and not db" --cov {XML}',
        ),
        ("uv run pytest --cov-report=xml", f"{LOCKED_PYTEST} --cov-report=xml --cov"),
    ],
)
def test_command_forms_are_rewritten_to_the_locked_runner(run, expected):
    command, note = sonar.test_command(ci_with(run), locked=True)
    assert command == expected, note


def test_coverage_options_are_added_once():
    command, _ = sonar.test_command(ci_with("uv run pytest --cov=a --cov=b"), locked=True)
    assert command.count("--cov=") == 2 and " --cov " not in command + " "
    assert command.count(XML) == 1
    command, _ = sonar.test_command(ci_with(f"uv run pytest --cov=a {XML}"), locked=True)
    assert command.count("--cov-report=xml") == 1


def test_a_continued_run_block_is_joined_and_only_the_pytest_line_is_taken():
    run = "uv run ruff check .\nuv run pytest -q \\\n  --deselect a::b\nuv run mypy ."
    command, _ = sonar.test_command(ci_with(run), locked=True)
    assert command == f"{LOCKED_PYTEST} -q --deselect a::b --cov {XML}"


def test_the_first_pytest_step_is_used_and_the_note_counts_them():
    ci = ci_with("uv run pytest unit").replace(
        "jobs:", "jobs:\n  u:\n    runs-on: x\n    steps:\n      - run: uv run pytest integration\n"
    )
    command, note = sonar.test_command(ci, locked=True)
    assert command is not None and "uv run --locked --no-sync python -m pytest" in command
    assert "2 pytest steps" in note


@pytest.mark.parametrize("locked", [True, False])
def test_without_a_lock_the_locked_flags_are_left_out(locked):
    command, _ = sonar.test_command(ci_with("uv run pytest -q"), locked=locked)
    assert command.startswith("uv run --locked --no-sync " if locked else "uv run --no-sync ")


def test_without_a_lock_adopt_writes_no_locked_flag_anywhere(tmp_path):
    p = make_project(tmp_path, lock=False)
    assert adopt(p) == 0
    text = (p / WORKFLOW).read_text(encoding="utf-8")
    assert "--locked" not in text
    assert (
        "uv sync --all-extras --all-groups" in text and "uv run --no-sync python -m pytest" in text
    )


def test_with_a_lock_adopt_keeps_the_locked_flags(tmp_path):
    p = make_project(tmp_path, lock=True)
    assert adopt(p) == 0
    text = (p / WORKFLOW).read_text(encoding="utf-8")
    assert "uv sync --locked --all-extras --all-groups" in text and LOCKED_PYTEST in text


# --- AC3: nothing is guessed ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ci", "reason"),
    [
        (None, "no ci.yml"),
        (
            "name: ci\non: push\njobs:\n  t:\n    runs-on: x\n    steps:\n      - run: make test\n",
            "no pytest step",
        ),
        (
            "name: ci\non: push\njobs:\n  t:\n    runs-on: x\n    steps:\n      - run: tox -e py\n",
            "no pytest step",
        ),
        (ci_with("uv run pytest && uv run ruff check ."), "shell operator"),
        (ci_with("uv run pytest | tee out.log"), "shell operator"),
        (ci_with("uv run pytest; echo done"), "shell operator"),
        (
            ci_with("uv run pytest", extra="        working-directory: backend\n"),
            "working-directory",
        ),
        (ci_with("uv run pytest", extra="        env:\n          DB: x\n"), "env"),
        (ci_with("uv run pytest", top="env:\n  DB: x\n"), "env"),
        (ci_with("uv run pytest ${{ github.event.head_commit.message }}"), "expression"),
        (ci_with("poetry run pytest -q"), "runner"),
        (ci_with("uv pip install pytest"), "runner"),
        (": : not yaml [", "does not parse"),
        ("- just\n- a list\n", "no pytest step"),
    ],
)
def test_unusable_ci_keeps_the_template_with_a_note(ci, reason):
    command, note = sonar.test_command(ci, locked=True)
    assert command is None
    assert reason in note


def test_job_level_env_and_defaults_are_refused_too():
    ci = ci_with("uv run pytest").replace(
        "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    env:\n      A: b\n"
    )
    assert sonar.test_command(ci, locked=True)[0] is None
    ci = ci_with("uv run pytest").replace(
        "    runs-on: ubuntu-latest\n",
        "    runs-on: ubuntu-latest\n    defaults:\n      run:\n        working-directory: x\n",
    )
    assert sonar.test_command(ci, locked=True)[0] is None


def test_the_template_step_is_kept_and_adopt_still_succeeds(tmp_path, capsys):
    p = make_project(tmp_path)
    write(
        p / CI,
        "name: ci\non: push\njobs:\n  t:\n    runs-on: x\n    steps:\n      - run: make test\n",
    )
    assert adopt(p) == 0
    command = coverage_step(p)["run"]
    assert command.startswith(f"{LOCKED_PYTEST} -q --cov") and command.endswith(XML)
    out = capsys.readouterr().out
    assert "sonar.yml: test step left as the template" in out


def test_an_expression_is_never_copied_into_the_workflow(tmp_path):
    p = make_project(tmp_path)
    write(p / CI, ci_with("uv run pytest ${{ github.head_ref }}"))
    assert adopt(p) == 0
    assert "github.head_ref" not in (p / WORKFLOW).read_text(encoding="utf-8")


# --- AC4: the python version follows CI -----------------------------------------------------------


@pytest.mark.parametrize(
    ("ci", "expected"),
    [
        (
            'steps:\n  - uses: actions/setup-python@v7\n    with:\n      python-version: "3.11"\n',
            ["3.11"],
        ),
        ("steps:\n  - run: uv python install 3.11\n", ["3.11"]),
        ("steps:\n  - run: uv run --python 3.13 pytest\n", ["3.13"]),
        ("    python-version: ['3.10', '3.12']\n", ["3.10", "3.12"]),
        ("    python-version: [3.10, 3.12, 3.10]\n", ["3.10", "3.12"]),
        ("    python-version: 3.10\n", ["3.10"]),
        ("# python-version: 3.9\n    python-version: 3.12 # was 3.9\n", ["3.12"]),
        ("    python-version:\n      - '3.9'\n      - \"3.12\"\n    other: 3.5\n", ["3.9", "3.12"]),
        ("python-version: ${{ matrix.python }}\n", []),
        ("python-version-file: .python-version\n", []),
        ("", []),
    ],
)
def test_python_version_follows_ci(ci, expected):
    assert sonar.ci_python_versions(ci) == expected


@pytest.mark.parametrize(
    ("pyproject", "expected"),
    [
        ('[project]\nrequires-python = ">=3.11"\n', ["3.11"]),
        ('[project]\nrequires-python = ">=3.10,<3.13"\n', ["3.10"]),
        ('[project]\nrequires-python = "<3.13,>=3.10"\n', ["3.10"]),
        ('[project]\nrequires-python = "~=3.12.1"\n', ["3.12"]),
        ('[project]\nrequires-python = "==3.11.*"\n', ["3.11"]),
        ('[project]\nname = "x"\n', ["3.12"]),
        ("not toml [", ["3.12"]),
    ],
)
def test_python_version_fallbacks(pyproject, expected):
    assert sonar.python_versions(None, pyproject) == expected
    assert sonar.python_versions("name: ci\n", pyproject) == expected


def test_ci_wins_over_requires_python():
    pyproject = '[project]\nrequires-python = ">=3.9"\n'
    assert sonar.python_versions("python-version: 3.11\n", pyproject) == ["3.11"]


def test_the_version_reaches_the_workflow_and_the_properties(tmp_path):
    p = make_project(tmp_path, branch="master", origin_head="master")
    write(p / CI, ADE_CI)
    assert adopt(p) == 0
    setup = next(s for s in steps(p) if s.get("uses", "").startswith("actions/setup-python"))
    assert setup["with"]["python-version"] == "3.11"
    assert prop(p, "sonar.python.version") == "3.11"
    assert "3.12" not in (p / PROPS).read_text(encoding="utf-8")


def test_a_matrix_gives_the_first_version_to_the_job_and_all_to_the_property(tmp_path):
    p = make_project(tmp_path)
    write(
        p / CI,
        ci_with("uv run pytest").replace(
            "jobs:",
            "jobs:\n  m:\n    strategy:\n      matrix:\n"
            "        python-version: ['3.10', '3.12']\n    runs-on: x\n"
            "    steps:\n      - run: echo\n",
        ),
    )
    assert adopt(p) == 0
    setup = next(s for s in steps(p) if s.get("uses", "").startswith("actions/setup-python"))
    assert setup["with"]["python-version"] == "3.10"
    assert prop(p, "sonar.python.version") == "3.10,3.12"


def test_the_fresh_adopt_default_is_the_template_ci_version(tmp_path):
    p = make_project(tmp_path)
    assert adopt(p) == 0
    assert prop(p, "sonar.python.version") == "3.12"  # the kit ci.yml is written in the same run


# --- AC5: pytest-cov note, idempotence -----------------------------------------------------------


COV_NOTE = "pytest-cov"


def notes(capsys) -> str:
    return "\n".join(ln for ln in capsys.readouterr().out.splitlines() if "sonar.yml:" in ln)


@pytest.mark.parametrize(
    "pyproject",
    [
        '[project]\nname = "p"\n[dependency-groups]\ndev = ["pytest-cov>=5"]\n',
        '[project.optional-dependencies]\ndev = ["pytest_cov"]\n',
    ],
)
def test_no_pytest_cov_note_when_it_is_a_dependency(tmp_path, capsys, pyproject):
    p = make_project(tmp_path, pyproject=pyproject)
    assert adopt(p) == 0
    assert COV_NOTE not in notes(capsys)


def test_pytest_cov_note_when_it_is_missing(tmp_path, capsys):
    p = make_project(tmp_path)
    assert adopt(p) == 0
    assert "uv add --dev pytest-cov" in notes(capsys)


def test_no_pytest_cov_note_for_node(tmp_path, capsys):
    p = make_project(tmp_path, "node")
    assert adopt(p) == 0
    assert COV_NOTE not in notes(capsys)


def test_the_note_is_only_printed_when_the_file_is_created(tmp_path, capsys):
    p = make_project(tmp_path)
    assert adopt(p) == 0
    capsys.readouterr()
    assert adopt(p) == 0
    out = capsys.readouterr().out
    assert "up to date" in out and "sonar.yml:" not in out


def test_adopt_twice_and_sync_after_adopt_change_nothing(tmp_path, capsys):
    p = make_project(tmp_path, branch="master", origin_head="master")
    write(p / CI, ADE_CI)
    assert adopt(p) == 0
    before = {r: (p / r).read_bytes() for r in (WORKFLOW, PROPS, CI)}
    capsys.readouterr()
    assert main(["sync", str(p)]) == 0
    assert "up to date" in capsys.readouterr().out
    assert adopt(p) == 0
    assert main(["sync", "--check", str(p)]) == 0
    assert before == {r: (p / r).read_bytes() for r in (WORKFLOW, PROPS, CI)}


def test_the_rendered_workflow_is_valid_yaml_with_the_guard_and_scan(tmp_path):
    p = make_project(tmp_path)
    write(p / CI, ADE_CI)
    assert adopt(p) == 0
    ids = [s.get("id") for s in steps(p)]
    assert "guard" in ids
    assert any("sonarqube-scan-action" in s.get("uses", "") for s in steps(p))
    assert "{{project_key}}" not in (p / WORKFLOW).read_text(encoding="utf-8")
    assert common.normalise_newlines((p / WORKFLOW).read_text(encoding="utf-8")).endswith("\n")
