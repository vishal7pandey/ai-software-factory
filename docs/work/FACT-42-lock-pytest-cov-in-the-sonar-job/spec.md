# FACT-42 — Lock pytest-cov in the sonar job

Status: draft · Risk: low · Jira: FACT-42

## Repro

Environment / version / commit where it fails: `main` @ 13b25be (PR 15 of FACT-41), SonarCloud project
`vishal7pandey_ai-software-factory`, issue `AaESE3b0wkk0OfVcfULY`, rule `githubactions:S8544`.

1. Open the SonarCloud issues of the project, or read the analysis of PR 15.
2. The issue sits on `.github/workflows/sonar.yml` line 58, the test step
   `uv run --with pytest-cov python -m pytest ...`.

Automated repro (failing test, written first):

- `uv run python -m pytest -q tests/test_sonar_self.py::test_the_coverage_step_installs_nothing_outside_the_lockfile`
  fails on the current code with `assert '--with' not in 'uv run --with pytest-cov python -m pytest ...'`.

Reproducibility: always (static analysis of the workflow text).

## Expected

Everything the sonar job installs is resolved from `uv.lock`, like the CI job.

## Actual

`uv run --with pytest-cov` resolves the newest `pytest-cov` on every run, outside the lockfile and
without a hash check (SonarCloud: "Using dependencies without locking resolved versions is
security-sensitive").

## Root cause (with evidence)

- Where: `.github/workflows/sonar.yml:58`.
- Why it fails: the generic kit template (`kit/sonar/python.yml`) adds coverage with `--with
  pytest-cov` so that an adopted project needs no change to its own dependencies; FACT-41 kept that
  form for the factory repo, whose own `dev` group (`pyproject.toml`) has no `pytest-cov`.
- Introduced by: FACT-35 template, carried into this repo by FACT-41 (PR 15).
- Evidence: SonarCloud analysis of PR 15 (issue created 2026-10-06T16:35:40Z, line 58).

## Blast radius

- Other callers: `kit/sonar/python.yml` (same `--with pytest-cov` line, laid in adopted python
  projects) and `docs/sonarcloud.md` (local-scan recipe) carry the same pattern; they are a separate
  decision (a generic template cannot assume a locked `pytest-cov`) and out of scope here, noted for
  follow-up. `ci.yml` does not use `--with`.
- Data: none. Environments: the factory repo's sonar job only.

## Regression criterion (AC1)

AC1: `tests/test_sonar_self.py::test_the_coverage_step_installs_nothing_outside_the_lockfile` passes
after the fix and fails on the current code: the coverage step of this repo's `sonar.yml` contains no
`--with`, and `pytest-cov` is in `pyproject.toml` and locked in `uv.lock`.

AC2: The `sonar` job on the fix PR still scans (guard enabled, tests pass, `ANALYSIS SUCCESSFUL`) and
SonarCloud's analysis of that PR reports no `githubactions:S8544` issue for `sonar.yml`.

AC3: The SonarCloud issue `AaESE3b0wkk0OfVcfULY` is reported closed or resolved by the SonarCloud API
after an analysis of the fixed code; no issue is dismissed. If SonarCloud cannot report that (see
Risks), the Jira Bug stays open and says why.

## Fix constraints

Do not change `kit/sonar/python.yml`. Do not make the quality gate blocking. No other dependency
version may change in `uv.lock`.

## Risks

SonarCloud's main branch for this project is named `master` while the repository's default branch is
`main`, so analyses of `main` are stored as a short-lived branch and the API refuses to read them
("Organization is not allowed to access data from non main branches"). AC3 can then only be proven
once the owner renames the SonarCloud main branch to `main`.

## Amendment 2026-10-06 (found on the first PR scan, PR 16)

The first fix (pytest-cov into the dev group, no `--with`) did not clear the issue: SonarCloud's analysis of PR 16
still reports `githubactions:S8544` (and `S8541`) on `sonar.yml` line 58, at columns 13-19, which is the text
`uv run` itself, not `--with`. Corrected root cause: the rule flags a bare `uv run`, which re-resolves
the lock if needed and may build packages. Corrected fix: `uv run --locked --no-sync ...` (the preceding
`uv sync --all-extras --all-groups` step already built the environment; `--locked` fails when the lock is
stale; `--no-sync` builds nothing; `--no-build` is not usable because the project itself is an editable
build). The regression criterion AC1 also pins `--locked` and `--no-sync` now. This is a refinement inside
the same approved scope (same issue, same file, same line), recorded here instead of re-approving.
Lines 55 (`uv sync`) and `ci.yml:26` carry the same rule family on main and stay out of scope (the other
Sonar issues are not taken in this item).
