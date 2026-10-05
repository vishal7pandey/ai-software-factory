# FACT-19 — Test plan: Delegated approvals as a first-class form

Status: in-review · Risk: medium · Jira: FACT-19

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, `project` fixture and `run(...)` helper in `tests/test_work.py`, verify tests in `tests/test_verify.py`; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine).

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_work.py::test_approve_delegated_records_flag_and_suffix, ::test_approve_delegated_empty_name_refused, ::test_approve_without_delegated_has_no_flag | `--delegated "Jane Doe" --yes` writes by/at/delegated and moves to spec-approved | name with surrounding spaces is trimmed | empty and blank name exit 1, item unchanged; plain approve has no `delegated` key | verified |
| AC2 | unit | tests/test_verify.py::test_delegated_approval_forms | flag form passes; hand-written suffix form passes; ordinary record passes | `delegated: false` on an ordinary `by` passes | `delegated: "yes"` fails; `delegated: true` without suffix fails | verified |
| AC3 | integration | tests/test_work.py::test_status_marks_delegated_approvals | item with flag form shows `(delegated)`; suffix-only form too | the hand-written suffix form with no flag is recognised after the flag form is replaced | ordinary item shows no marker | verified |
| AC4 | manual | `factory lint`, `factory sync --check .`, reading the text | n/a | n/a | n/a: lint cannot judge wording; see Manual checks | verified |
| AC5 | integration | tests/test_work.py::test_reapprove_delegated_refreshes_ledger | re-approve at implementing with `--delegated` refreshes `by`/`at`, status unchanged | n/a | n/a: refusal beyond in-review is covered by existing re-approval tests | verified |

## Regression risk

Existing approve tests (happy path, re-approval, wrong status, non-tty, interactive) must stay green; `status` table header and column order must not change (`tests/test_work.py` asserts the header). `tests/test_verify.py` approval-schema cases stay unchanged.

## Untestable AC

AC4 is wording; checked manually below. Mechanical parts (lint, sync) run in CI.

## Manual checks

AC4: read `policies/autonomy.md`, `kit/AGENTS.block.md`, `kit/work-README.md`, the `factory-workflow` skill and ARCHITECTURE 3.2/3.7; each says delegation needs an explicit recorded owner instruction naming the gates, is recorded with `--delegated`, and is never valid for production.

## Audit (after implementation)

Each mutation applied temporarily to `src/swfactory/`, the relevant tests run, then restored (`git diff` clean for those lines).

| AC | Real test(s) | Broken on purpose | Result |
|----|--------------|-------------------|--------|
| AC1 | `tests/test_work.py:292` `test_approve_delegated_records_flag_and_suffix`, `:321` `test_reapprove_delegated_refreshes_ledger` | `record["delegated"] = True` removed from `cmd_approve` | both fail |
| AC1 | `tests/test_work.py:307` `test_approve_delegated_empty_name_refused` (both params) | empty-name guard disabled | both params fail |
| AC1 | `tests/test_work.py:315` `test_approve_without_delegated_has_no_flag` | not mutated: asserts the unchanged ordinary path (would fail if the flag leaked into ordinary approvals) | passes on the real code |
| AC2 | `tests/test_verify.py:118` `test_delegated_approval_forms` | boolean check of `delegated` disabled; then suffix check disabled | fails each time |
| AC3 | `tests/test_work.py:334` `test_status_marks_delegated_approvals` | status marker removed; then `is_delegated` changed so the suffix form no longer counts (`or` -> `and`) | fails each time (the second also fails the verify test) |
| AC4 | manual | n/a | `factory lint` OK, `factory sync --check .` in sync after `factory sync .`; wording read in the five files |
| AC5 | `tests/test_work.py:321` | see AC1 | covered |
