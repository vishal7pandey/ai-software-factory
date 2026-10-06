# FACT-42 — Test plan: Lock pytest-cov in the sonar job

Status: draft · Risk: low · Jira: FACT-42

Test framework and conventions found: pytest, `tests/test_*.py`, `common.FACTORY_ROOT`; run all with
`uv run python -m pytest -q`. The regression test lives in `tests/test_sonar_self.py` (FACT-41).

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_sonar_self.py::test_the_coverage_step_installs_nothing_outside_the_lockfile | no `--with` in the step; `pytest-cov` in pyproject and uv.lock | both pyproject and the lock are checked | a `--with` in the step, or a pyproject entry without a lock entry, fails | verified |
| AC2 | manual | PR checks and the SonarQube tools on the PR analysis | `sonar` job scans, no S8544 on sonar.yml | n/a | n/a: a refusal shows in the job log | planned |
| AC3 | manual | SonarCloud API after merge | issue closed/resolved | n/a | an issue still OPEN keeps the Bug open | planned |

## Regression risk

`tests/test_sonar_self.py` (FACT-41) pins `python -m pytest`, `--cov=src/swfactory` and the report path:
the step keeps all three. The full suite must stay green; CI `uv sync` gains `pytest-cov`.

## Untestable AC

None; AC2 and AC3 are properties of the live service (manual checks below).

## Manual checks

- AC2: `gh pr checks --watch`; the sonar job log; the SonarQube issues tool with `pull_request=<n>`.
- AC3: after merge, SonarQube tools: issue `AaESE3b0wkk0OfVcfULY` status; main-branch issues.

## Audit (after implementation)

<!-- Filled by factory-test in audit mode. -->

2026-10-06: the regression test failed on the unfixed code (`assert '--with' not in 'uv run --with
pytest-cov python -m pytest ...'`, tests/test_sonar_self.py:63) and passes after the fix (471 passed in
the full suite; ruff check and format, `factory lint`, `factory sync --check .` all OK). Deliberate break
after the fix: the step put back to `uv run --with pytest-cov python -m pytest` makes the same test fail
(1 failed); restored (`git diff` shows only the intended change; 5 passed). AC2 and AC3 stay `planned`
until verified on the PR and after merge (see the Jira comments on FACT-42).
