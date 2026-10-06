# FACT-41 — Enable SonarCloud

Status: draft · Risk: low · Jira: FACT-41
Created: 2026-10-06 · Slug: enable-sonarcloud · Spec: spec.md

## Summary

Fill in the real organisation key (already in the working tree), adapt the generic test step of
this repo's `sonar.yml` to the factory's own command, ignore the generated coverage files, and pin the
agreement between the workflow and the properties file in one test. Then let the PR run the scan and
verify against the public SonarCloud API after merge.

**Size:** S (under half a day, most of it waiting on CI and SonarCloud).

## Current state

* `.github/workflows/sonar.yml` (laid by FACT-35, create-mode, ours to edit): guard, `setup-python`
  3.12, `setup-uv`, `uv sync --all-extras --all-groups`, test step with generic
  `uv run --with pytest-cov python -m pytest -q --cov --cov-report=xml:coverage.xml`, scan step with
  `SonarSource/sonarqube-scan-action@v8`.
* `.github/workflows/ci.yml`: matrix ubuntu and windows, `astral-sh/setup-uv`, `uv sync`, `ruff`,
  `uv run pytest -q`, `factory lint`, `factory sync --check`. No `setup-python`: uv picks the
  interpreter (`requires-python >= 3.12`).
* `sonar-project.properties`: organisation key set (uncommitted edit), `sonar.projectKey`,
  `sonar.python.version=3.12`, `sonar.python.coverage.reportPaths=coverage.xml`.
* `tests/test_sonar.py` holds the kit tests (FACT-35) and the helper `ROOT`. Commands: `uv run python
  -m pytest -q`, `uv run ruff check . && uv run ruff format --check .`, `uv run python -m
  swfactory.cli lint`, `uv run python -m swfactory.cli sync --check .`.
* Measured locally: the coverage command writes `coverage.xml` (466 tests pass).

## Approach

1. Test step: `uv run --with pytest-cov python -m pytest -q --cov=src/swfactory --cov-branch
   --cov-report=xml:coverage.xml`. Restricting `--cov` to the package keeps test files out of the
   coverage figure; `--with` avoids touching `pyproject.toml` and `uv.lock`.
2. `.gitignore`: `coverage.xml`, `.coverage`.
3. One test in `tests/test_sonar_self.py` reads this repo's own workflow and properties: no placeholder,
   expected project key, the coverage report named in the properties is the file written by the
   pytest step, and `setup-python` equals `sonar.python.version`.
4. Open the PR; read the `sonar` job log; fix the cause if SonarCloud refuses; merge when green.
5. Verify through the public SonarCloud API and the agent's SonarQube tools; run the findings loop.

**Alternatives rejected**
- Add `pytest-cov` to the dev dependency group: edits the lockfile and every contributor's env for a CI-only need.
- `-Dsonar.qualitygate.wait=true` now: a failing gate would block merges, a human decision.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing test that pins workflow/properties agreement | tests/test_sonar_self.py | AC1, AC2 | test fails before T2, passes after |
| T2 | Test step, gitignore | .github/workflows/sonar.yml, .gitignore | AC2 | local run of the exact command writes coverage.xml |
| T3 | PR: scan runs and passes | PR | AC2 | `gh pr checks --watch`, job log shows the scanner finishing |
| T4 | Verify after merge, record, MCP check | Jira, Confluence | AC3, AC5 | public API output |
| T5 | One issue through the findings loop (if any) | per the bug path | AC4 | API shows the issue closed |

## Data, API and migration impact

none.

## Security and failure modes

The token stays in the Actions secret; the workflow keeps read-only permissions. A refused scan fails
the `sonar` job and shows the reason in its log; nothing else is affected.

## Rollout and rollback

Merge to main triggers the push analysis. Rollback: revert the commit; the SonarCloud project can stay.

## Risks and open points

- Automatic Analysis enabled on the new project makes the CI scan fail: log shows it; owner action.
- Coverage paths may not map to files: the first scan's coverage figure tells.
