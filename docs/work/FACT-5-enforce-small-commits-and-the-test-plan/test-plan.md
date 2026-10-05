# FACT-5 — Test plan: Enforce small commits and the test-plan Audit

Status: in-review · Risk: low · Jira: FACT-5

Test framework and conventions found: pytest, `tests/test_verify.py` with `make_item`/`write_item`
helpers and a subprocess check of the standalone script; run everything with `uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_verify.py::test_audit_is_placeholder (parametrized x5) | a filled Audit, a comment-only Audit, no-Audit-heading text each resolve correctly | a whitespace-only Audit section | an Audit with a stray comment plus real text is not a placeholder | verified |
| AC1 | unit | tests/test_verify.py::test_warn_project_only_for_in_review_or_later_with_a_placeholder_audit | `in-review` item with a placeholder Audit -> exactly one warning naming it | an item with a real Audit and one with no test-plan.md at all | `implementing` status gives no warning even with a placeholder | verified |
| AC2 | integration | tests/test_verify.py::test_run_with_only_a_warning_does_not_fail | exit 0, first line `WARN F-001: ...`, last line `verify: OK (1 warning(s))` | n/a: single case | n/a: covered by AC1's negative cases | verified |
| AC2 | integration | tests/test_verify.py::test_run_with_a_problem_and_a_warning_shows_both_and_still_fails | n/a: negative-only | n/a | a missing-approval problem plus a placeholder Audit -> both a WARN and a FAIL line, exit 1, last line is the problem-count form (never the warning form) | verified |
| AC2 | integration | tests/test_verify.py::test_main_output_and_exit_codes (existing, unchanged) | no warning triggered: last line stays exactly `verify: OK` | n/a | n/a | verified |
| AC3 | manual | reading `skills/factory-implement/SKILL.md` step 4.6; `uv run factory lint` | the real skill states one commit per plan task | n/a | n/a | verified |
| AC4 | manual | reading `docs/ARCHITECTURE.md` §3.3 and `skills/factory-test/SKILL.md` audit mode | both name the new warning | n/a | n/a | verified |
| AC5 | manual | `uv run python .factory/verify.py` on this repo | no WARN lines for FACT-12, 16, 18, 19, 20, 21 | n/a | n/a | verified |

## Regression risk

The exact-output tests in `tests/test_verify.py` (`test_main_output_and_exit_codes`,
`test_standalone_script_runs_without_swfactory`) must stay green: `write_item`'s default `test-plan.md`
content (`"content\n"`) has no `## Audit` heading at all, so `audit_is_placeholder` returns `False` for it
and these tests see no new `WARN` line or changed final line.

## Untestable AC

None; AC3, AC4 and AC5 are checked by reading and by running the tool, recorded below.

## Manual checks

AC3: `skills/factory-implement/SKILL.md` step 4.6 now reads "Commit this task, and only this task
(FACT-5): one commit per `plan.md` task, never two tasks in one commit, and never split one task across
two commits." `uv run factory lint` -> `lint: OK`.
AC4: `docs/ARCHITECTURE.md` §3.3 has a new numbered rule 5 describing the warning; `skills/factory-test/SKILL.md`
audit-mode step 5 mentions it.
AC5: `uv run python .factory/verify.py` in the repo root prints `verify: OK` with no `WARN` lines (all six
existing items' Audits are filled).

## Audit (after implementation)

Each mutation applied to the real `src/swfactory/verify.py` (confirmed changed against a backup copy), the
relevant `-k` subset of `tests/test_verify.py` run, then the file restored from the backup (confirmed
byte-identical afterward with `diff -q`):

| Mutation | Test(s) run | Result |
|---|---|---|
| M1: `audit_is_placeholder` body replaced with `return False` | `-k "audit or warn_project or warning"` | 5 of 8 new tests fail: both `True`-expecting parametrized cases, `test_warn_project_...` (no warning where one was expected), and both `test_run_with_...` tests (no WARN line, wrong final line / missing FAIL+WARN combination) |
| M2: `warn_project` body replaced with `return []` | same `-k` | 3 tests fail: `test_warn_project_...`, `test_run_with_only_a_warning_does_not_fail`, `test_run_with_a_problem_and_a_warning_shows_both_and_still_fails` |
| M3: `run()`'s `for w in warnings: print(...)` loop removed (warnings computed but never printed) | same `-k` | 2 tests fail: both `test_run_with_...` tests (no WARN line printed) |

Full suite after restoring: 294 passed. `ruff check .` and `ruff format --check .`: clean. `factory lint`:
OK. `factory sync --check .`: in sync. `uv run python .factory/verify.py` on this repo (branch
`feature/fact-5-enforce-small-commits-and-the-test-plan`): `verify: OK`.
