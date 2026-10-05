"""Project inspection and CI adaptation behind `factory adopt` (FACT-12). Spawns no uv or npm."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from swfactory import adopt_inspect as ai
from swfactory import common

CI = """name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    steps:
      - uses: actions/checkout@v7
      - run: uv sync --all-extras --all-groups
      - run: uv run ruff check .
      - run: uv run pytest -q
"""


def w(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def git_init(path: Path, branch: str = "main") -> None:
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True)


class Recorder:
    """Fake command runner: records commands; `fail` maps a command to (code, output)."""

    def __init__(self, fail: dict[str, tuple[int, str]] | None = None):
        self.fail = fail or {}
        self.calls: list[str] = []

    def __call__(self, cmd: str, cwd: Path) -> tuple[int, str]:
        self.calls.append(cmd)
        return self.fail.get(cmd, (0, ""))


# --- AC1 ----------------------------------------------------------------------------------------


def test_python_template_installs_all_dependency_layouts(tmp_path):
    text = (common.kit_dir() / "ci" / "python.yml").read_text(encoding="utf-8")
    assert "uv sync --all-extras --all-groups" in text
    assert not re.search(r"run:\s*uv sync\s*$", text, re.MULTILINE)  # no bare `uv sync`

    # pytest only in an optional extra (the chatpid layout): the install step must cover extras
    w(
        tmp_path / "pyproject.toml",
        '[project]\nname = "x"\n[project.optional-dependencies]\ndev = ["pytest"]\n',
    )
    rec = Recorder()
    adapted, report = ai.adapt_ci(text, "main", tmp_path, check=True, runner=rec)
    assert rec.calls[0] == "uv sync --all-extras --all-groups"
    assert "uv run pytest -q" in rec.calls
    assert adapted == text and not report.dropped


# --- AC2 ----------------------------------------------------------------------------------------


def test_trigger_findings(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    w(
        wf / "ci.yml",
        "name: ci\non:\n  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\n",
    )
    found = ai.trigger_findings(tmp_path, "master")
    assert len(found) == 2
    assert all(".github/workflows/ci.yml" in f and "main" in f and "master" in f for f in found)
    assert any("`push`" in f for f in found) and any("`pull_request`" in f for f in found)

    # no filter, filter that lists the branch, filter with a matching glob: no finding
    w(wf / "ci.yml", "name: ci\non:\n  push:\n  pull_request:\n")
    assert ai.trigger_findings(tmp_path, "master") == []
    w(wf / "ci.yml", "name: ci\non:\n  push:\n    branches: [main, master]\n")
    assert ai.trigger_findings(tmp_path, "master") == []
    w(wf / "ci.yml", "name: ci\non:\n  push:\n    branches: ['release/**', 'mas*']\n")
    assert ai.trigger_findings(tmp_path, "master") == []
    # string and list forms of `on` carry no branch filter
    w(wf / "ci.yml", "name: ci\non: push\n")
    assert ai.trigger_findings(tmp_path, "master") == []
    w(wf / "ci.yml", "name: ci\non: [push, pull_request]\n")
    assert ai.trigger_findings(tmp_path, "master") == []

    # the factory's own workflow is ignored; an unparsable one is a finding, not a crash
    w(wf / "ci.yml", "name: ci\n")
    w(wf / "factory-verify.yml", "on:\n  push:\n    branches: [main]\n")
    w(wf / "broken.yml", "on: [unclosed\n")
    found = ai.trigger_findings(tmp_path, "master")
    assert len(found) == 1 and "broken.yml" in found[0] and "could not be parsed" in found[0]
    assert ai.trigger_findings(tmp_path, None) == [found[0]]  # unknown branch: parse issue only


def test_default_branch(tmp_path):
    assert ai.default_branch(tmp_path) is None  # not a git repo
    git_init(tmp_path, "master")
    assert ai.default_branch(tmp_path) == "master"  # current branch, no remote
    subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop"],
        cwd=tmp_path,
        check=True,
    )
    assert ai.default_branch(tmp_path) == "develop"  # origin/HEAD wins


# --- AC3 ----------------------------------------------------------------------------------------


def test_detects_commands_and_commands_section(tmp_path):
    w(
        tmp_path / "Makefile",
        "test:\n\tpytest\nlint:\n\truff\n.PHONY: test\nsecret-deploy:\n\tx\nX := 1\n",
    )
    w(tmp_path / "package.json", '{"scripts": {"test": "jest", "build": "tsc"}}')
    assert ai.detect_commands(tmp_path) == ["make test", "make lint", "npm test", "npm run build"]

    py = tmp_path / "py"
    w(
        py / "pyproject.toml",
        "[project]\nname='x'\n[tool.ruff]\nline-length=100\n[tool.pytest.ini_options]\n",
    )
    w(py / "uv.lock", "")
    assert ai.detect_commands(py) == [
        "uv sync --all-extras --all-groups",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run pytest -q",
    ]
    assert ai.detect_commands(tmp_path / "empty") == []

    for ok in ("# Notes\n\n## Testing\nrun it\n", "### Build and run\n", "## Commands\n"):
        assert ai.has_commands_section(ok), ok
    assert not ai.has_commands_section("# Project\n\nSome prose about tests.\n")
    assert not ai.has_commands_section("# Project\n\n```\n## Commands\n```\n")  # in a code fence
    in_block = f"# P\n\n{ai.BEGIN}\n## Commands\n{ai.END}\n"
    assert not ai.has_commands_section(in_block)  # inside the factory block does not count

    assert "* `make test`" in ai.todo_section(["make test"])
    assert "found no build, test or lint commands" in ai.todo_section([])
    assert ai.has_commands_section(
        ai.todo_section([])
    )  # our own section counts: adopt is idempotent


# --- AC4 / AC5 ----------------------------------------------------------------------------------


def test_adapt_ci_drops_failing_steps(tmp_path):
    rec = Recorder({"uv run ruff check .": (1, "lots\nFound 84 errors.\n")})
    adapted, report = ai.adapt_ci(CI, "main", tmp_path, check=True, runner=rec)
    assert rec.calls == [
        "uv sync --all-extras --all-groups",
        "uv run ruff check .",
        "uv run pytest -q",
    ]
    assert "run: uv run ruff check ." not in adapted
    assert "# factory adopt: removed `uv run ruff check .`" in adapted
    assert "Found 84 errors." in adapted
    assert (
        "run: uv run pytest -q" in adapted and "run: uv sync --all-extras --all-groups" in adapted
    )
    assert report.dropped == [("uv run ruff check .", "Found 84 errors.")]
    assert any("Found 84 errors." in ln and "ruff check" in ln for ln in report.lines())
    assert all(ln.isascii() for ln in report.lines())


def test_adapt_ci_install_failure_or_missing_tool_drops_nothing(tmp_path):
    rec = Recorder({"uv sync --all-extras --all-groups": (1, "resolution failed")})
    adapted, report = ai.adapt_ci(CI, "main", tmp_path, check=True, runner=rec)
    assert adapted == CI and not report.dropped
    assert rec.calls == ["uv sync --all-extras --all-groups"]  # nothing after the failed install
    assert "checks could not run" in report.lines()[0] and "resolution failed" in report.lines()[0]

    rec = Recorder({"uv sync --all-extras --all-groups": (127, "uv not found on PATH")})
    adapted, report = ai.adapt_ci(CI, "main", tmp_path, check=True, runner=rec)
    assert adapted == CI and "tool missing" in report.lines()[0]

    rec = Recorder({"uv run pytest -q": (124, "timed out after 600s")})  # a timeout is a failure
    adapted, report = ai.adapt_ci(CI, "main", tmp_path, check=True, runner=rec)
    assert report.dropped == [("uv run pytest -q", "timed out after 600s")]


def test_adapt_ci_check_off_never_runs_commands(tmp_path):
    rec = Recorder()
    adapted, report = ai.adapt_ci(CI, "master", tmp_path, check=False, runner=rec)
    assert rec.calls == [] and "branches: [master]" in adapted and report.lines() == []


def test_ci_push_trigger_uses_default_branch(tmp_path):
    adapted, _ = ai.adapt_ci(CI, "master", tmp_path, check=False)
    assert "branches: [master]" in adapted and "branches: [main]" not in adapted
    assert ai.adapt_ci(CI, "main", tmp_path, check=False)[0] == CI
    assert ai.adapt_ci(CI, None, tmp_path, check=False)[0] == CI  # unknown -> main
    adapted, report = ai.adapt_ci(CI, "bad]\nname: x", tmp_path, check=False)  # not YAML-safe
    assert adapted == CI and report.notes


def test_project_commands_do_not_inherit_the_factorys_virtualenv(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/factory/.venv")
    monkeypatch.setenv("KEEP_ME", "1")
    env = ai.project_env()
    assert "VIRTUAL_ENV" not in env and env["KEEP_ME"] == "1"


@pytest.mark.real_runner
def test_default_runner_runs_a_real_command(tmp_path):
    code, out = ai.run_shell("git --version", tmp_path)
    assert code == 0 and "git version" in out
    assert ai.run_shell("git definitely-not-a-subcommand", tmp_path)[0] != 0
    code, out = ai.run_shell("definitely-not-a-tool-xyz --flag", tmp_path)
    assert code == 127 and "not found" in out
