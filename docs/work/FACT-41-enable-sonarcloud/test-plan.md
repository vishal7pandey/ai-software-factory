# FACT-41 — Test plan: Enable SonarCloud

Status: draft · Risk: low · Jira: FACT-41

Test framework and conventions found: pytest, tests in `tests/test_*.py`, `common.FACTORY_ROOT` as the
repo root; run all with `uv run python -m pytest -q`. One new file, `tests/test_sonar_self.py` (4 tests),
reading this repo's own `.github/workflows/sonar.yml`, `sonar-project.properties` and `.gitignore`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_sonar_self.py::test_properties_have_the_real_organisation_and_project_key | org non-empty, key `vishal7pandey_ai-software-factory`, no `REPLACE_ME` in any value line | all value lines checked (comment lines may mention the marker, as the guard allows) | a placeholder organisation or another key fails it | verified |
| AC2 | unit | tests/test_sonar_self.py::test_the_test_step_runs_the_own_suite_and_writes_the_coverage_file_the_properties_name, ::test_the_job_python_matches_the_sonar_python_version, ::test_generated_coverage_files_are_ignored_by_git | pytest step has `python -m pytest`, `--cov=src/swfactory`, `--cov-report=xml:coverage.xml`; setup-python 3.12 equals `sonar.python.version` | report path read from the properties, not hard-coded | XML path or Python version changed in one file only fails | verified |
| AC2 | manual | PR checks: the `sonar` job on this PR | guard enabled, tests pass, scanner finishes, job green | n/a: only a live run proves the scanner accepts the project | n/a: SonarCloud refusal shows in the log and is recorded | planned |
| AC3 | manual | public SonarCloud API after merge: `components/search_projects`, `qualitygates/project_status`, `issues/search` | project count 1, gate status, issue count printed | n/a: single project | n/a: no token is used, so a private/absent project returns nothing | planned |
| AC4 | manual | `factory-findings` loop on one Sonar issue, or none exist | issue closed on SonarCloud after a new analysis, Jira Bug Done | n/a | an issue still OPEN keeps the Bug open | planned |
| AC5 | manual | `mcp__sonarqube__projects` in the agent session | result recorded (count, organisation visible or not) | n/a | not visible: recorded with the owner action | planned |

## Regression risk

`tests/test_sonar.py` and `tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit` read the
kit and the synced files; they do not read this repo's create-mode `sonar.yml`, so they are unaffected
and must stay green. The full suite (466 before this item) must pass.

## Untestable AC

None. AC2 (live scan), AC3, AC4 and AC5 are verified by manual checks against the live service (reason:
they are properties of SonarCloud, not of repository code), listed below.

## Manual checks

- AC2: `gh pr checks --watch` on the PR; read the `sonar` job log: guard prints enabled, the scanner
  reports the analysis URL and `EXECUTION SUCCESS`.
- AC3: after merge, from Python urllib without a token: `components/search_projects?organization=<key>`
  (count), `qualitygates/project_status?projectKey=<key>`, `issues/search?componentKeys=<key>&resolved=false`.
- AC4: only if issues exist: `skills/factory-findings/SKILL.md`; closure re-queried through the API.
- AC5: call `mcp__sonarqube__projects` and record the result.

## Audit (after implementation)

<!-- Filled by factory-test in audit mode: per row, the real test file:line and how you confirmed it
fails when the behaviour is broken (mutation tried, or concrete reasoning). -->

2026-10-06, `uv run python -m pytest -q tests/test_sonar_self.py` (4 tests). One deliberate break per
mutation, then restored (the final run is 4 passed, `git diff` shows only the intended change):

| Break | AC | Result |
|-------|----|--------|
| workflow report path `xml:coverage.xml` -> `xml:cov.xml` | AC2 | killed: `test_the_test_step_runs_the_own_suite_and_writes_the_coverage_file_the_properties_name` (tests/test_sonar_self.py:40) |
| workflow `python-version` 3.12 -> 3.13 | AC2 | killed: `test_the_job_python_matches_the_sonar_python_version` (:49) |
| `sonar.projectKey=REPLACE_ME_X` | AC1 | killed: `test_properties_have_the_real_organisation_and_project_key` (:32) |
| (the first run of the AC1 test failed on the explanatory comment in the properties file that names the marker; the test was corrected to look at value lines only, as the workflow guard does) | AC1 | n/a |

Checks run on the branch: full suite, `ruff check`, `ruff format --check`, `factory lint`, `factory sync
--check .` (results in the PR). AC2 live-scan, AC3, AC4, AC5 rows stay `planned` until verified on the PR
and after merge.
