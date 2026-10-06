# FACT-35 — Test plan: SonarCloud scan in the kit

Status: implementing · Risk: medium · Jira: FACT-35

Test framework and conventions found: pytest, tests in `tests/test_*.py`, `from swfactory.cli import main`
with `capsys`, autouse fixtures in `tests/conftest.py` (isolated home, inert `gh`); run everything with
`uv run python -m pytest -q`. One new file, `tests/test_sonar.py` (81 tests). Template and adopt tests use
the REAL kit and a temp git repo (`make_project`); the guard test extracts the `run:` script of the step
`id: guard` from the real workflow YAML and runs it with bash (Git Bash on Windows, system bash on Linux;
skipped with a reason when no POSIX bash exists); doctor tests stub `harden.gh_api` with `SecretGh`, a class
that records calls and puts the marker `LEAK-MARKER-xyz` into every secret `value` and error body.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_sonar.py::test_adopt_lays_both_files_with_project_key_and_placeholder (x2), ::test_python_properties_point_at_coverage_xml_and_node_at_lcov (x2) | python and node project with a github origin: both files exist, `sonar.projectKey=me_proj`, org is the marked placeholder, python has `coverage.xml`, node `coverage/lcov.info` and not the other | the placeholder detector returns exactly `sonar.organization` | n/a: see rows below | verified |
| AC1 | integration | tests/test_sonar.py::test_adopt_without_a_github_remote_marks_the_project_key_too (x2), ::test_a_non_github_remote_also_gets_the_marked_project_key, ::test_adopt_points_a_new_sonar_workflow_at_the_default_branch (x2), ::test_the_rendering_token_never_leaks_into_a_project | default branch `trunk` -> `branches: [trunk]` in sonar.yml | no remote / gitlab remote -> `REPLACE_ME_OWNER_REPO`, detector lists both keys | `{{project_key}}` never remains in any laid file | verified |
| AC1 | integration | tests/test_sonar.py::test_docs_and_other_stacks_get_no_sonar_files (x2) | n/a | stack `docs` / `other` -> neither file | n/a | verified |
| AC2 | unit | tests/test_sonar.py::test_manifest_registers_both_files_as_create_mode_for_python_and_node | both dests have one entry per stack, all `create`, sources exist | exactly the stacks python and node | n/a | verified |
| AC2 | integration | tests/test_sonar.py::test_sync_after_adopt_is_up_to_date_and_never_overwrites_edits, ::test_sync_check_ignores_missing_sonar_files, ::test_the_real_kit_lints_clean | `sync` right after `adopt` -> "up to date", exit 0 | `sync --check` exits 0 with the files deleted; managed ledger has no sonar path | project-edited files keep their bytes after `sync` | verified |
| AC3 | unit | tests/test_sonar.py::test_triggers_are_push_on_one_branch_and_pull_request (x2), ::test_job_runs_only_for_same_repository_pull_requests (x2), ::test_checkout_has_full_history (x2) | push on `[main]` + pull_request; `fetch-depth: 0` | job `if` has both the non-PR branch and the head-repo equality | n/a | verified |
| AC3 | unit | tests/test_sonar.py::test_scan_uses_the_pinned_action_and_the_secret (x2), ::test_organisation_and_project_key_come_only_from_the_properties_file (x2), ::test_permissions_grant_no_write_scope (x2), ::test_the_token_is_never_expanded_inside_a_script (x2), ::test_python_template_produces_coverage_xml_before_the_scan, ::test_node_template_produces_lcov_before_the_scan | `SonarSource/sonarqube-scan-action@v8`, token from `secrets.SONAR_TOKEN`, coverage step before the scan | permissions are exactly contents+pull-requests read | no `sonar.organization`/`sonar.projectKey`/`pull_request_target` text; no `secrets.` inside any `run:` | verified |
| AC4 | unit | tests/test_sonar.py::test_every_step_after_the_guard_waits_for_it (x2), ::test_the_guard_and_scan_steps_are_identical_in_both_templates | every step after the guard is conditioned on `enabled == 'true'`; only checkout runs before it | guard and scan steps equal in both stacks | n/a | verified |
| AC4 | integration | tests/test_sonar.py::test_guard_without_the_secret_exits_zero_with_a_notice (x4: 2 stacks x unset/empty) | token unset or empty -> exit 0, `::notice` naming SONAR_TOKEN, `enabled=false` | empty string vs unset | n/a | verified |
| AC4 | integration | tests/test_sonar.py::test_guard_with_a_token_but_no_properties_file_skips (x2), ::test_guard_with_a_token_and_a_placeholder_skips (x2), ::test_guard_with_a_token_and_filled_properties_enables_the_scan_without_echoing_it (x2), ::test_guard_and_doctor_agree_on_what_a_placeholder_is (x6) | token + filled file -> `enabled=true` only | comment-only `REPLACE_ME` (also indented) does not block; `key = value` spacing; guard and doctor agree on six property files | missing file / placeholder -> exit 0, `enabled=false`; the token marker never appears in stdout, stderr or the output file | verified |
| AC5 | unit | tests/test_sonar.py::test_secret_present_is_ok_and_calls_only_the_list, ::test_secret_absent_with_filled_properties_warns, ::test_secret_absent_while_the_placeholder_remains_is_only_a_notice | list with SONAR_TOKEN -> OK present, exactly one GET `.../actions/secrets?per_page=100` | absent + filled -> WARN naming `gh secret set SONAR_TOKEN`; absent + placeholder -> OK notice | n/a | verified |
| AC5 | unit | tests/test_sonar.py::test_gh_unusable_is_unknown_never_not_set, ::test_http_failures_are_unknown_with_the_status_only (x4), ::test_a_second_page_of_secrets_makes_absence_unknown | name on a full page of 100 with total 150 -> present | name not on the page and total 150 -> unknown naming 100 | gh unusable, 401/403/404/500 -> WARN `unknown (HTTP n)`, never "not set", no body | verified |
| AC5 | integration | tests/test_sonar.py::test_no_github_remote_skips_the_secret_check_without_a_call (x2), ::test_doctor_prints_presence_but_never_a_value, ::test_doctor_does_not_print_an_error_body (x2) | `main(["doctor", path])` prints the `present` line, exit 0 | no remote / gitlab remote -> OK `skipped`, zero calls | marker in secret `value`/`encrypted_value` fields and in 403/500 bodies is absent from output | verified |
| AC6 | unit | tests/test_sonar.py::test_placeholder_detection_names_keys_and_ignores_comments, ::test_secret_present_but_placeholder_remains_warns_naming_the_key, ::test_placeholder_in_a_comment_does_not_count, ::test_missing_properties_file_warns | filled -> OK `no placeholder left` | `:` separator; indented comment; empty text | secret present + placeholder -> WARN naming only `sonar.organization`; workflow without properties -> WARN | verified |
| AC6 | integration | tests/test_sonar.py::test_nothing_configured_is_one_notice_and_no_github_call, ::test_doctor_on_a_project_without_sonar_files_prints_one_notice, ::test_doctor_never_exits_one_because_of_sonar (x6), ::test_doctor_after_a_real_adopt_has_no_warning_for_a_local_only_project; existing tests/test_integration.py::test_adopt_is_idempotent_and_doctor_is_clean | no Sonar files -> one OK `not configured`, no gh call | 3 file states x secret present/absent -> exit 0, no FAIL | a freshly adopted local-only project keeps a doctor output without WARN or FAIL | verified |
| AC7 | unit | tests/test_sonar.py::test_the_how_to_covers_every_owner_step, ::test_security_policy_has_exactly_one_pointer_line, ::test_treaty_and_readme_mention_the_new_files_and_doctor_lines; `factory lint`; `factory sync --check .` | docs contain every owner step and the local scan | exactly one pointer line in the policy | n/a | verified |
| AC8 | manual | after the owner sets the organisation key and the secret: push, open the SonarCloud project, list it with the SonarQube tools | first analysis visible, project count 0 -> 1, recorded on FACT-35 | n/a | n/a | planned |
| AC9 | manual | one Sonar issue through `factory-findings` end to end | issue fixed and closed by a scan | n/a | n/a | planned |

## Regression risk

`tests/test_integration.py::test_adopt_is_idempotent_and_doctor_is_clean` (a local-only project must keep
a doctor output without WARN/FAIL: Sonar lines are OK notices or skipped without a remote; it stayed
green) and `::test_factory_repo_is_in_sync_with_its_kit` (the factory repo is python-stack, so it now
carries the two create-mode files, ignored by `sync --check`). `tests/test_install.py` and
`tests/test_adopt_inspect.py` use fixture manifests and are unaffected. `tests/test_harden.py` doctor tests
count only `repo:` lines: the added `sonar` line does not disturb them. `tests/test_doctor.py` has no
Sonar files, so `check_sonar` makes no gh call there.

## Untestable AC

AC8 and AC9 need the owner's SonarCloud organisation key and `SONAR_TOKEN` secret, and a live analysis;
they cannot be tested in this PR (by design of the ticket) and stay open on FACT-35.

## Manual checks

AC8, AC9: waiting on the owner. Exact steps are in `docs/sonarcloud.md`; after them: `factory doctor .`
shows both `sonar:` lines `OK`/`present`, a push shows the `sonarcloud` job running the scan, the project
appears in SonarCloud and in the SonarQube tools (`projects` count 1), and one issue is taken through
`factory-findings`.

Live read check of the doctor secret lookup (`GET repos/{o}/{r}/actions/secrets`): see the PR description
(the network was unreachable from the agent shell at times; the result of the last attempt is recorded
there).

## Audit (after implementation)

Each mutation was applied to the real file by a script (`mutate.py`, kept in the agent scratchpad: it checks
the old text occurs exactly once, writes the mutant, runs `tests/test_sonar.py` and `tests/test_integration.py`,
then restores the original bytes and asserts they are identical; `git status` shows only the intended changes
afterwards). Line numbers are the mutated line (source/kit files) and the test lines in `tests/test_sonar.py`
are as of this commit. The whole audit was run twice (the second pass listed every failing test, recorded
below); a first attempt at M18 skipped because its old text did not match (script indentation) and was fixed.

| Mutation | AC | Result: failing tests |
|---|---|---|
| M1 `src/swfactory/installer.py:266` project key `{owner}_{repo}` -> `{owner}/{repo}` | AC1 | killed (2): `test_adopt_lays_both_files_with_project_key_and_placeholder` (:78) |
| M2 `installer.py:265` no-remote key placeholder -> `"unknown"` | AC1 | killed (3): `test_adopt_without_a_github_remote_marks_the_project_key_too` (:104), `test_a_non_github_remote_also_gets_the_marked_project_key` (:112) |
| M3 `installer.py:296` rendering condition -> `False` (token never replaced) | AC1 | killed (6): the three above plus `test_the_rendering_token_never_leaks_into_a_project` (:133) |
| M4 `installer.py:303` default branch not applied to a new sonar.yml | AC1 | killed (2): `test_adopt_points_a_new_sonar_workflow_at_the_default_branch` (:119) |
| M5 `kit/manifest.yaml:17` python properties entry `create` -> `managed` | AC2 | killed (8): `test_manifest_registers_both_files_as_create_mode_for_python_and_node` (:67), `test_sync_after_adopt_is_up_to_date_and_never_overwrites_edits` (:140), `test_sync_check_ignores_missing_sonar_files` (:161), `tests/test_sonar.py` adopt tests, `tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit` |
| M6 `src/swfactory/checks.py:515` placeholder detector also counts comment lines | AC6 | killed (8): `test_placeholder_detection_names_keys_and_ignores_comments` (:380), `test_placeholder_in_a_comment_does_not_count` (:480), `test_guard_and_doctor_agree_on_what_a_placeholder_is` (:372), adopt tests (:78, :104) |
| M7 `checks.py:533` secret name test inverted (`not in`) | AC5 | killed (6): `test_secret_present_is_ok_and_calls_only_the_list` (:445), `test_secret_absent_with_filled_properties_warns` (:455), `test_secret_absent_while_the_placeholder_remains_is_only_a_notice` (:463), `test_secret_present_but_placeholder_remains_warns_naming_the_key` (:473), `test_a_second_page_of_secrets_makes_absence_unknown` (:505), `test_doctor_prints_presence_but_never_a_value` (:537) |
| M8 `checks.py:536` second-page check disabled (`if False`) | AC5 | killed (1): `test_a_second_page_of_secrets_makes_absence_unknown` (:505) |
| M9 `checks.py:531` HTTP failure detail also prints the response body | AC5 | killed (6): `test_http_failures_are_unknown_with_the_status_only` (:498), `test_doctor_does_not_print_an_error_body` (:548) |
| M10 `checks.py:573` absent secret is always an OK notice (never WARN) | AC5 | killed (1): `test_secret_absent_with_filled_properties_warns` (:455) |
| M11 `checks.py:564` placeholder with the secret present is OK instead of WARN | AC6 | killed (1): `test_secret_present_but_placeholder_remains_warns_naming_the_key` (:473) |
| M12 `checks.py:550` "not configured" needs only one of the two files (`or`) | AC6 | killed (3): `test_missing_properties_file_warns` (:485), `test_doctor_never_exits_one_because_of_sonar` (:557) |
| M13 `src/swfactory/commands/doctor.py:17` doctor no longer calls `check_sonar` | AC6 | killed (11): `test_doctor_prints_presence_but_never_a_value` (:537), `test_doctor_does_not_print_an_error_body` (:548), `test_doctor_never_exits_one_because_of_sonar` (:557), `test_doctor_on_a_project_without_sonar_files_prints_one_notice` (:569), `test_doctor_after_a_real_adopt_has_no_warning_for_a_local_only_project` (:578) |
| M14 `kit/sonar/python.yml:37` guard `-z` -> `-n` | AC4 | killed (9): `test_guard_without_the_secret_exits_zero_with_a_notice` (:321), `test_guard_with_a_token_but_no_properties_file_skips` (:330), `test_guard_with_a_token_and_a_placeholder_skips` (:340), `test_guard_with_a_token_and_filled_properties_enables_the_scan_without_echoing_it` (:351), `test_guard_and_doctor_agree_on_what_a_placeholder_is` (:372), `test_the_guard_and_scan_steps_are_identical_in_both_templates` (:257) |
| M15 `kit/sonar/python.yml:26` `fetch-depth: 0` -> `1` | AC3 | killed (1): `test_checkout_has_full_history` (:192) |
| M16 `kit/sonar/node.yml:22` same-repo condition removed from the job `if` | AC3 | killed (1): `test_job_runs_only_for_same_repository_pull_requests` (:184) |
| M17 `kit/sonar/node.yml:67` action pin `@v8` -> `@master` | AC3 | killed (2): `test_scan_uses_the_pinned_action_and_the_secret` (:198), `test_the_guard_and_scan_steps_are_identical_in_both_templates` (:257) |
| M18 `kit/sonar/python.yml:59` scan step loses its `if: ... enabled == 'true'` | AC4 | killed (2): `test_every_step_after_the_guard_waits_for_it` (:246), `test_the_guard_and_scan_steps_are_identical_in_both_templates` (:257) |
| M19 `kit/sonar/node.yml:43` guard grep no longer skips comment lines | AC4 | killed (1), but only by `test_the_guard_and_scan_steps_are_identical_in_both_templates` (:257): the executed guard tests run the python template's script; the node guard is covered by the equality test (noted as a limit: a drift that keeps both files equal is caught by the python executions) |
| M20 `kit/sonar/python.yml:46` guard also writes the token into its output | AC4 | killed (2): `test_guard_with_a_token_and_filled_properties_enables_the_scan_without_echoing_it` (:351), `test_the_guard_and_scan_steps_are_identical_in_both_templates` (:257) |
| M21 `kit/sonar/python.yml:15` `pull-requests: read` -> `write` | AC3 | killed (1): `test_permissions_grant_no_write_scope` (:213) |
| M22 `docs/sonarcloud.md:45` `gh secret set SONAR_TOKEN -R` removed | AC7 | killed (1): `test_the_how_to_covers_every_owner_step` (:590) |
| M23 `policies/security.md:26` pointer line no longer names `docs/sonarcloud.md` | AC7 | killed (2): `test_security_policy_has_exactly_one_pointer_line` (:608), `tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit` (the synced copy then differs from its source) |
| M24 `kit/sonar/python.yml:34` skip path `exit 0` -> `exit 1` | AC4 | killed (5): `test_guard_without_the_secret_exits_zero_with_a_notice` (:321), `test_guard_with_a_token_but_no_properties_file_skips` (:330), `test_guard_with_a_token_and_a_placeholder_skips` (:340), `test_the_guard_and_scan_steps_are_identical_in_both_templates` (:257) |

Net: 24 mutations, 24 killed, none survived, so the audit added no test. Observations: (a) the executed guard
tests are parametrized over both stacks only for the secret/file/placeholder cases (`test_guard_without_...`,
`..._no_properties_file_...`, `..._placeholder_skips`, `..._filled_properties_...`); the doctor-agreement test
uses the python script; the identical-steps test ties the node guard to it (M19). (b) AC8 and AC9 have no
automated test by design (owner-gated).

