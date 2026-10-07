# FACT-40 — Test plan: Sonar kit template: default branch, project test command, locked deps, doctor check

Status: draft · Risk: medium · Jira: FACT-40

Test framework and conventions found: pytest, `tests/`, fixtures in `tests/conftest.py` (isolated HOME and registry, no `gh`, no project
commands); template and adopt tests run on the REAL kit (`tests/test_sonar.py`); doctor tests stub `harden.gh_api` and, new here, the
SonarCloud network function. New files: `tests/test_sonar_render.py` (adopt/sync rendering), `tests/test_sonar_server.py` (doctor
reader, stubs only). Run all: `uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_sonar_render.py::test_sync_and_adopt_point_a_new_workflow_at_master, test_default_branch_prefers_main_or_master_over_a_feature_branch | master fixture: both paths give `[master]`, python and node; main stays main | feature branch checked out, origin/HEAD unset, only master exists | existing sonar.yml byte-identical after sync; odd branch name keeps `main` | planned |
| AC2 | unit | tests/test_sonar_render.py::test_the_project_test_command_is_reused (ade-shaped), test_command_forms_are_rewritten_to_the_locked_runner, test_coverage_options_are_added_once | `-m "not integration"`, path and 9 `--deselect` kept; xml report added | folded `>` and `\` continuations; `--cov=pkg` kept; xml report already present | `--frozen --with pytest-cov` dropped | planned |
| AC3 | unit | tests/test_sonar_render.py::test_unusable_ci_keeps_the_template_with_a_note | no ci.yml, no pytest step: template kept, note | several pytest steps: first used, note counts | `&&`, `working-directory`, `env`, `${{ }}`, `tox`, `make test`, unparsable CI: template, note names the reason | planned |
| AC4 | unit | tests/test_sonar_render.py::test_python_version_follows_ci, test_python_version_fallbacks | 3.11 from `python-version`, from `uv python install` | list gives `3.10,3.12` for the property and 3.10 for the job; unquoted `3.10` | requires-python lower bound; nothing: 3.12; comment lines ignored | planned |
| AC5 | integration | tests/test_sonar_render.py::test_without_a_lock_the_locked_flags_are_left_out, test_pytest_cov_note_only_when_missing | with uv.lock: `--locked` kept | pytest-cov in dev group or in uv.lock: no note | missing: one note with `uv add --dev pytest-cov`; node: no note | planned |
| AC5 | integration | tests/test_sonar_render.py::test_adopt_twice_and_sync_after_adopt_change_nothing | adopt then sync: `up to date`, `sync --check` 0 | edited sonar.yml survives | n/a | planned |
| AC6 | contract | tests/test_sonar.py::test_third_party_actions_are_pinned_to_a_commit_sha, test_python_template_installs_only_from_the_lock; tests/test_sonar_self.py::test_the_own_workflow_pins_and_locks_like_the_template | every non-`actions/` `uses:` is 40-hex plus `# v` comment; `uv sync --locked`, `--locked --no-sync` | node template pinned too | `--with`, `@v8`, `@v10.2.0` rejected | planned |
| AC7 | contract | tests/test_sonar.py::test_the_doc_states_the_public_project_and_main_branch_facts | both facts and both commands present | commands read `$SONAR_TOKEN` | no `--with pytest-cov` | planned |
| AC8 | unit/integration | tests/test_sonar_server.py::test_ok_when_public_and_branches_match, test_mismatch_prints_the_repair_commands, test_delete_command_only_with_a_side_branch, test_not_found_and_private_warn, test_every_failure_is_unknown, test_no_call_for_placeholders_or_no_remote, test_no_token_in_output | public, main equals default: OK | main `master` vs `main`, side branch present or absent | 404, private, 500, status 0, bad JSON, no main branch, gh down: `unknown`; unsafe key not sent | planned |
| AC8 | unit | tests/test_sonar_server.py::test_the_network_guard_and_the_real_request_function | guard: `_request` is replaced in the suite | URL error maps to 0, HTTP error to its code | no real network | planned |
| AC10 | contract | tests/test_sonar.py::test_properties_templates_set_sonar_tests_and_nested_test_inclusions, tests/test_sonar_self.py::test_the_own_properties_set_sonar_tests, test_sonar.py::test_the_doc_names_sonar_tests | python and node templates and the repo's own file have `sonar.tests=.`; python inclusions have `**/tests/**` | adopted project's file has it | template without it rejected by the test | planned |
| AC11 | unit | tests/test_sonar_server.py::test_doctor_warns_when_sonar_tests_is_missing | set: OK `sonar: tests` | commented-out line still warns; placeholder properties also checked | no properties file: no finding | planned |
| AC9 | integration | tests/test_sonar.py::test_the_real_kit_lints_clean (existing), tests/test_install.py (existing), full suite | n/a: gates | n/a | n/a | planned |

## Regression risk

Existing Sonar tests assert the scan action is `@v8` (`test_scan_uses_the_pinned_action_and_the_secret`) and that the python template
contains `pytest-cov`: both change on purpose. `tests/test_sonar.py` doctor tests that fill the properties and expect no WARN now see the
`sonar: server` finding as `unknown` (the network guard answers status 0): they are updated to name it. `test_integration` adopt/doctor
idempotence stays clean because a fresh adopt has the placeholder and makes no call. `default_branch` is used by `adopt` findings: its
tests stay green.

## Untestable AC

None. The "SonarCloud re-scan shows the issue gone" half of AC6 can only be shown on the PR analysis; it is read through the public API
and recorded in the PR and on the ticket, not asserted by a test.

## Manual checks

- AC6: read the PR analysis anonymously (`api/issues/search?...&pullRequest=<n>`) for `.github/workflows/sonar.yml`; after merge read `main`.
- AC8: `factory doctor .` run read-only in the factory repo against the live public API; one run against a project with no remote.

## Audit (after implementation)

<!-- Filled after implementation: per row, the real test file:line and the mutation tried. -->
