"""FACT-41: the factory repo's own SonarCloud set-up (not the kit templates, see test_sonar.py).

The scan can only work when this repository's workflow and its properties file agree."""

from __future__ import annotations

import re

import yaml

from swfactory import common

ROOT = common.FACTORY_ROOT
PROJECT_KEY = "vishal7pandey_ai-software-factory"


def properties() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (ROOT / "sonar-project.properties").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def steps() -> list[dict]:
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "sonar.yml").read_text(encoding="utf-8"))
    return wf["jobs"]["sonar"]["steps"]


def test_properties_have_the_real_organisation_and_project_key():
    props = properties()
    assert props["sonar.projectKey"] == PROJECT_KEY
    assert props["sonar.organization"] and "REPLACE_ME" not in props["sonar.organization"]
    # like the workflow guard: comment lines may mention the marker, value lines may not
    assert "REPLACE_ME" not in "\n".join(f"{k}={v}" for k, v in props.items())


def test_the_test_step_runs_the_own_suite_and_writes_the_coverage_file_the_properties_name():
    test_step = next(s for s in steps() if "pytest" in s.get("run", ""))
    command = test_step["run"]
    assert "python -m pytest" in command
    assert "--cov=src/swfactory" in command
    report = properties()["sonar.python.coverage.reportPaths"]
    assert f"--cov-report=xml:{report}" in command


def test_the_job_python_matches_the_sonar_python_version():
    setup = next(s for s in steps() if str(s.get("uses", "")).startswith("actions/setup-python"))
    assert str(setup["with"]["python-version"]) == properties()["sonar.python.version"]
    assert re.fullmatch(r"3\.\d+", properties()["sonar.python.version"])


def test_generated_coverage_files_are_ignored_by_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "coverage.xml" in ignored and ".coverage" in ignored


def test_the_own_workflow_pins_and_locks_like_the_template():
    """FACT-40: the repo's own sonar.yml follows the kit's rules (SHA-pinned third-party actions,
    `uv sync --locked`), so a re-scan has nothing left to report on those lines."""
    text = (ROOT / ".github" / "workflows" / "sonar.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses: ([\w.-]+/[\w.-]+)@(\S+)([^\n]*)", text)
    third = [(a, ref, rest) for a, ref, rest in uses if not a.startswith("actions/")]
    assert {a for a, _, _ in third} == {"astral-sh/setup-uv", "SonarSource/sonarqube-scan-action"}
    for action, ref, rest in third:
        assert re.fullmatch(r"[0-9a-f]{40}", ref), action
        assert re.fullmatch(r"\s+# v\d+(\.\d+){0,2}", rest), action
    sync = next(s["run"] for s in steps() if s.get("run", "").startswith("uv sync"))
    assert "--locked" in sync.split()
    kit = (ROOT / "kit" / "sonar" / "python.yml").read_text(encoding="utf-8")
    for action, ref, _ in third:  # the same commits as the kit template
        assert f"{action}@{ref}" in kit


def test_the_coverage_step_installs_nothing_outside_the_lockfile():
    """FACT-42 (Sonar githubactions:S8544): `uv run --with` resolves a fresh, unlocked version."""
    command = next(s for s in steps() if "pytest" in s.get("run", ""))["run"]
    assert "--with" not in command
    # `uv run` itself is what the rule flags: it must neither re-resolve nor build anything here
    assert "--locked" in command.split() and "--no-sync" in command.split()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "pytest-cov" in pyproject
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "pytest-cov"' in lock
