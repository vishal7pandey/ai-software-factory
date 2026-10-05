# FACT-33 — Test plan: factory harden: CodeQL, Dependabot, secret scanning

Status: spec-approved · Risk: medium · Jira: FACT-33

Test framework and conventions found: pytest, tests in `tests/test_*.py`, `from swfactory.cli import main`
with `capsys` for command output, autouse fixtures in `tests/conftest.py`; run everything with
`uv run python -m pytest -q`. New file `tests/test_harden.py`; the stub runner is a small `FakeGh` class
in that file that records every call and answers from a dict of `(method, path) -> (status, body)`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_harden.py::test_apply_issues_exactly_the_expected_writes | all four off -> the 4 writes with the exact method, path and JSON body, in order alerts before updates | n/a: single case | n/a: covered by the skip rows | planned |
| AC1 | unit | tests/test_harden.py::test_apply_skips_what_is_already_on | one protection on -> its write absent, the other three present | all four on -> zero writes, exit 0, "already on" x4 | n/a | planned |
| AC1 | unit | tests/test_harden.py::test_repo_slug_forms | https, `.git` suffix, ssh `git@github.com:o/r.git` -> (o, r) | trailing slash | non-github host, no remote, malformed -> FactoryError | planned |
| AC1 | unit | tests/test_harden.py::test_state_mapping (parametrized) | enabled/disabled statuses -> ok/off for each of the four reads | `security_and_analysis` absent -> unknown; 204 vs 404 for alerts; `automated-security-fixes` enabled false | read fails with 500 -> unknown with HTTP 500 | planned |
| AC1 | unit | tests/test_harden.py::test_gh_api_parses_status_and_body | `HTTP/2.0 200 OK` + headers + JSON body -> (200, dict) | 204 with empty body -> (204, None); CRLF headers | gh missing / timeout / garbage output -> (0, None) | planned |
| AC2 | unit | tests/test_harden.py::test_dry_run_issues_no_write | all off, `--dry-run` -> only GETs recorded, output lists the 4 would-do calls, exit 0 | all on + dry-run -> nothing to do | gh unusable + dry-run -> plan with unknown states, exit 0 | planned |
| AC2 | integration | tests/test_harden.py::test_adopt_prints_plan_and_apply_command_without_writing | adopt of a temp git repo with a github remote and a stub runner -> output has the plan and `factory harden <path>`, zero writes | `adopt --dry-run` prints it too | no remote -> one line, adopt exit unchanged; gh unusable -> adopt still exit 0 | planned |
| AC3 | unit | tests/test_harden.py::test_doctor_off_on_public_repo_fails | alerts disabled on a public repo -> finding says `off`, level FAIL, doctor exit 1 | the same state on a private repo -> WARN, exit 0 | n/a | planned |
| AC3 | unit | tests/test_harden.py::test_doctor_unknown_when_gh_fails | status 0 (and 401) -> four `unknown` lines, exit 0 | no remote or a non-github remote -> one `skipped` OK line, exit 0 | n/a | planned |
| AC3 | integration | tests/test_harden.py::test_doctor_command_prints_four_states | `main(["doctor", path])` with all on -> four `ok` lines | mixed states print `ok`, `off`, `unknown` | off public -> exit 1 | planned |
| AC4 | unit | tests/test_harden.py::test_one_failure_does_not_stop_the_others | CodeQL PATCH 403 -> other three writes issued, output `HTTP 403`, exit 1 | failure on the first write (secret scanning) -> remaining three still issued | the stub body carries `LEAK-MARKER-xyz`: it is absent from stdout and stderr | planned |
| AC4 | unit | tests/test_harden.py::test_private_repo_failure_is_not_available | private repo, CodeQL 403 -> `not available (HTTP 403)`, exit 0 | 404 and 422 behave the same | a 500 on a private repo is still `failed (HTTP 500)`, exit 1 | planned |
| AC5 | manual | run `factory harden` and `factory doctor .` on this repo | all four `ok`, no write call, doctor exit 0 | n/a | n/a | planned |
| AC6 | unit | tests/test_harden.py::test_the_suite_cannot_reach_the_real_gh | with no stub, `gh_api(...)` returns (0, None) and no subprocess runs | n/a | n/a | planned |
| AC6 | manual | `factory lint`, `factory sync --check .`, ARCHITECTURE 3.7, README, `policies/security.md` | lint OK, in sync, docs list the command | n/a | n/a | planned |

## Regression risk

`adopt` output assertions in `tests/test_install.py`, `tests/test_integration.py` and
`tests/test_adopt_inspect.py` (exact "up to date" / "done:" lines; the new block is printed after them and
must not change the exit code). `tests/test_doctor.py::test_command_with_path_reports_project_only`
(the fixture has no remote, so doctor adds one `unknown` WARN line and still exits 0 / the failure path
is unchanged). `tests/test_lint.py` generic-host check (docs must not contain the tracker hostname).

## Untestable AC

None. AC5 needs the live repo and is a manual check by nature; AC6's docs half is a reading check.

## Manual checks

AC5: from the worktree, `uv run python -m swfactory.cli harden .` (not dry-run) and
`uv run python -m swfactory.cli doctor .`; expect four `ok` lines each, and `harden` reporting no change.
AC6 docs: read ARCHITECTURE 3.7 and README for the command; `uv run factory sync --check .` says in sync.

## Audit (after implementation)

<!-- Filled by factory-test in audit mode: per row, the real test file:line and how you confirmed it
fails when the behaviour is broken (mutation tried, or concrete reasoning). -->
