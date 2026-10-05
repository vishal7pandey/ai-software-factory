# FACT-33 — Test plan: factory harden: CodeQL, Dependabot, secret scanning

Status: in-review · Risk: medium · Jira: FACT-33

Test framework and conventions found: pytest, tests in `tests/test_*.py`, `from swfactory.cli import main`
with `capsys` for command output, autouse fixtures in `tests/conftest.py`; run everything with
`uv run python -m pytest -q`. New file `tests/test_harden.py`; the stub runner is a small `FakeGh` class
in that file that records every call, answers GETs from flags, and can fail a call by `(method, path
suffix) -> status` (the failed response body then carries the marker `LEAK-MARKER-xyz`). A new autouse
fixture in `tests/conftest.py` (`no_real_gh`) makes the one process-starting function inert.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_harden.py::test_apply_issues_exactly_the_expected_writes | all four off -> the 4 writes with exact method, path and JSON body, alerts before updates, summary line | n/a: single case | n/a: the skip rows below | verified |
| AC1 | unit | tests/test_harden.py::test_apply_skips_what_is_already_on, ::test_apply_with_everything_on_writes_nothing, ::test_push_protection_alone_off_still_writes_the_secret_scanning_call | two on -> only the other two written | all four on -> zero writes, exit 0; push protection alone off still triggers the secret-scanning call | n/a | verified |
| AC1 | unit | tests/test_harden.py::test_repo_slug_forms (x5), ::test_repo_slug_rejects_non_github_or_missing (x4) | https, `.git`, ssh scp-form, ssh url -> (me, proj) | trailing slash | non-github host, no remote, one path part, three path parts -> FactoryError | verified |
| AC1 | unit | tests/test_harden.py::test_state_all_on, ::test_state_each_protection_can_be_off_alone (x5), ::test_state_without_admin_secret_scanning_is_unknown_not_off, ::test_state_a_failing_read_is_unknown_with_its_status | enabled/disabled statuses map to ok/off for each of the four reads | secret scanning off vs push protection off alone; no `security_and_analysis` (non-admin) -> unknown | a 500 read -> unknown `HTTP 500` | verified |
| AC1 | unit | tests/test_harden.py::test_parse_response_status_and_body, ::test_parse_response_unusable_output_is_status_zero (x3), ::test_gh_api_builds_the_call_and_returns_the_status | `HTTP/2.0 200 OK` + CRLF headers + JSON -> (200, dict); argv and stdin of a PATCH with body | 204 empty body -> (204, None); GET passes no stdin | invalid JSON body -> None; empty / garbage output -> (0, None) | verified |
| AC2 | unit | tests/test_harden.py::test_dry_run_issues_no_write_and_lists_the_calls, ::test_dry_run_with_everything_on_has_nothing_to_do, ::test_dry_run_with_gh_unusable_prints_the_plan_with_unknown_states | all off + dry-run -> zero writes, the 4 calls printed, exit 0 | all on + dry-run -> 0 would be enabled | gh unusable + dry-run -> plan with unknown states, exit 0 | verified |
| AC2 | integration | tests/test_harden.py::test_adopt_prints_the_plan_and_the_apply_command_and_writes_nothing (x2), ::test_adopt_with_everything_on_says_there_is_nothing_to_enable, ::test_adopt_without_a_github_remote_prints_one_line_and_succeeds, ::test_adopt_with_gh_unusable_still_succeeds_and_names_the_command, ::test_adopt_note_quotes_a_path_with_spaces | real kit adopted into a temp git repo with a github remote: plan plus last line `apply with: factory harden <path>`, GETs only | `adopt --dry-run` prints the same; path with spaces is quoted; all on -> "nothing to enable" | no remote -> one line, exit 0; gh unusable -> still exit 0 | verified |
| AC2 | integration | tests/test_harden.py::test_command_applies_and_prints, ::test_command_dry_run_flag, ::test_command_defaults_to_the_current_directory, ::test_command_when_gh_is_unusable_is_a_user_error_and_dry_run_is_not | `main(["harden", path])` and `--dry-run` through argparse | no path -> current directory | gh unusable: apply exits 1 naming `gh auth status`, dry-run exits 0 | verified |
| AC3 | integration | tests/test_harden.py::test_doctor_all_on_prints_four_ok_lines, ::test_doctor_off_on_a_public_repo_fails, ::test_doctor_off_on_a_private_repo_only_warns | all on -> four `ok` lines, exit 0 | the same `off` state on a private repo -> WARN, exit 0 | alerts off on a public repo -> `FAIL ... off`, exit 1 | verified |
| AC3 | integration | tests/test_harden.py::test_doctor_unknown_when_gh_fails, ::test_doctor_unknown_on_http_401, ::test_state_when_gh_is_unusable_everything_is_unknown, ::test_state_gh_dying_midway_is_unknown_never_off | gh unusable -> four `unknown` WARN lines, exit 0 | HTTP 401 -> unknown naming the status; gh dies after the repo read -> unknown, not off | the 401 stub body (marker) is not printed | verified |
| AC3 | integration | tests/test_harden.py::test_doctor_without_a_github_remote_is_one_skipped_line (x2), ::test_doctor_does_not_ask_github_about_a_path_that_is_not_adopted, ::test_state_private_repo_without_the_feature_is_not_available | no remote / gitlab remote -> one OK `skipped` line | private repo + 403 -> `not available`; the same 403 on a public repo -> unknown | a path that is not an adopted project makes no gh call | verified |
| AC4 | unit | tests/test_harden.py::test_one_failure_does_not_stop_the_others_and_leaks_no_body, ::test_failure_of_the_first_write_still_attempts_the_rest, ::test_command_exit_code_is_one_when_a_protection_failed | CodeQL PATCH 403 -> the other three writes issued, `HTTP 403`, exit 1 | the first write failing (500) still lets the rest run | the response body marker is absent from stdout and stderr | verified |
| AC4 | unit | tests/test_harden.py::test_private_repo_403_is_not_available_and_not_a_failure, ::test_private_repo_404_and_422_behave_like_403 (x2), ::test_private_repo_500_is_still_a_failure, ::test_apply_refuses_when_the_repository_cannot_be_read, ::test_apply_with_a_401_names_the_status | private repo + CodeQL 403 -> `not available (HTTP 403)`, exit 0 | 404 and 422 behave the same | a 500 on a private repo is still `FAILED`, exit 1; unreadable repo -> FactoryError, no call made | verified |
| AC5 | manual | run `factory harden .` and `factory doctor .` on this repo | all four `ok`, no write call, doctor exit 0 | n/a | n/a | verified |
| AC6 | unit | tests/test_harden.py::test_the_suite_cannot_reach_the_real_gh | with the autouse guard, `gh_api(...)` returns (0, None) even with `subprocess.run` booby-trapped | n/a | n/a | verified |
| AC6 | manual | `factory lint`, `factory sync --check .`, ruff, full suite, ARCHITECTURE 3.7/3.8, README, `policies/security.md` | lint OK, in sync, docs list the command | n/a | n/a | verified |

## Regression risk

`adopt` output assertions in `tests/test_install.py`, `tests/test_integration.py` and
`tests/test_adopt_inspect.py` (exact "up to date" / "done:" lines; the new block is printed after them and
does not change the exit code: all stayed green). `tests/test_integration.py::
test_adopt_is_idempotent_and_doctor_is_clean` requires a clean doctor for a local-only project: that is why
a missing github.com remote is an `ok`-level `skipped` line (notes.md). `tests/test_doctor.py` command
tests (fixture project has no remote). `tests/test_lint.py` generic-host check (docs must not contain the
tracker hostname).

## Untestable AC

None. AC5 needs the live repo and is a manual check by nature; AC6's docs half is a reading check.

## Manual checks

AC5, run from the worktree on 2026-10-05 (real calls, nothing changed):

```
$ factory harden .
vishal7pandey/ai-software-factory (public)
ok      secret scanning + push protection   already on
ok      dependabot alerts                   already on
ok      dependabot security updates         already on
ok      codeql default setup                already on
harden: 0 enabled, 4 already on, 0 not available, 0 failed        (exit 0)
$ factory doctor .
OK    repo: secret scanning + push protection ok
OK    repo: dependabot alerts      ok
OK    repo: dependabot security updates ok
OK    repo: codeql default setup   ok
doctor: 0 failure(s), 0 warning(s)                                 (exit 0)
```

AC6 docs: ARCHITECTURE 3.7 table rows for `harden` / `doctor` / `adopt`, new section 3.8; README quick start;
`policies/security.md` "Repository protections"; `factory sync .` refreshed `.factory/policies/security.md`;
`factory lint` -> `lint: OK`; `factory sync --check .` -> in sync.

## Audit (after implementation)

Each mutation applied to the real source file (script confirmed the old text was present and the file
changed), `uv run python -m pytest -q --tb=no tests/test_harden.py` run, then the file restored from a
backup copy and confirmed byte-identical (`restored-identical=True`; `git status` clean afterwards).
Line numbers are the mutated line in the source file; tests are in `tests/test_harden.py`.

| Mutation | AC | Result |
|---|---|---|
| M1 `src/swfactory/harden.py:235` `if current.state == OK:` -> `if False:` (never skip what is on) | AC1 | 9 fail, e.g. `test_apply_skips_what_is_already_on` (:223), `test_apply_with_everything_on_writes_nothing` (:232), `test_adopt_with_everything_on_says_there_is_nothing_to_enable` (:409) |
| M2 `harden.py:205` `"query_suite": "default"` -> `"extended"` | AC1 | 5 fail, e.g. `test_apply_issues_exactly_the_expected_writes` (:214), `test_dry_run_issues_no_write_and_lists_the_calls` (:308) |
| M3 `harden.py:83` `KEYS` order swaps alerts and security updates | AC1 | 2 fail: `test_apply_issues_exactly_the_expected_writes` (:214), `test_one_failure_does_not_stop_the_others_and_leaks_no_body` (:246) |
| M4 `harden.py:153` alerts "on" is `status == 204` -> `== 200` | AC1 | 14 fail, e.g. `test_state_all_on` (:127), `test_state_each_protection_can_be_off_alone` (:141), `test_doctor_all_on_prints_four_ok_lines` (:453) |
| M5 `harden.py:325` slug no longer checks the host is github.com | AC1 | 2 fail: `test_repo_slug_rejects_non_github_or_missing` (:540, gitlab case), `test_doctor_without_a_github_remote_is_one_skipped_line` (:492) |
| M6 `harden.py:242` `if dry_run:` -> `if False:` (dry-run writes) | AC2 | 7 fail, e.g. `test_dry_run_issues_no_write_and_lists_the_calls` (:308), `test_command_dry_run_flag` (:350), both `test_adopt_prints_the_plan_...` cases (:395) |
| M7 `src/swfactory/installer.py:383` adopt's note loop -> `for line in []:` (nothing printed) | AC2 | 5 fail: both `test_adopt_prints_the_plan_...` cases (:395), `..._everything_on_...` (:409), `..._without_a_github_remote_...` (:417), `..._gh_unusable_...` (:424) |
| M8 `src/swfactory/checks.py:493` public `off` -> `level = WARN` (doctor never fails) | AC3 | 1 fails: `test_doctor_off_on_a_public_repo_fails` (:460) |
| M9 `harden.py:114` a read that did not happen (status 0) -> `OFF` instead of `UNKNOWN` | AC3 | first audit pass: **survived** (60 passed): no test covered gh dying after the repo read. Added `test_state_gh_dying_midway_is_unknown_never_off` (:156); rerun: 1 fails, that test |
| M10 `harden.py:254` after a failed write, `break` (stops the other protections) | AC4 | 1 fails: `test_failure_of_the_first_write_still_attempts_the_rest` (:262) |
| M11 `harden.py:246,254` failed-write detail also prints the response body (`HTTP 403 {body}`) | AC4 | 3 fail: `test_one_failure_does_not_stop_the_others_and_leaks_no_body` (:246), `test_failure_of_the_first_write_still_attempts_the_rest` (:262), `test_command_exit_code_is_one_when_a_protection_failed` (:366) |
| M12 `harden.py:251` private-repo 403/404/422 branch -> `elif False:` (always FAILED) | AC4 | 3 fail: `test_private_repo_403_is_not_available_and_not_a_failure` (:269), `test_private_repo_404_and_422_behave_like_403` (:279, x2) |
| M13 `tests/conftest.py:49` the `no_real_gh` guard body -> `pass` | AC6 | 1 fails: `test_the_suite_cannot_reach_the_real_gh` (:20); run alone so no real call is made |

Net: 13 mutations, 12 killed on the first pass, 1 (M9) survived and led to a new test, then killed. Full
suite after restoring: 355 passed (294 before this work item, 61 new). `ruff check .` and
`ruff format --check .`: clean. `factory lint`: OK. `factory sync --check .`: in sync.
`python .factory/verify.py`: OK.
