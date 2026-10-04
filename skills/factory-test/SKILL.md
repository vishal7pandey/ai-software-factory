---
name: factory-test
description: Use when a work item is at status plan-approved and needs test-plan.md before implementation starts (one row per acceptance criterion mapped to concrete tests), or when implementation is done and test-plan.md must be audited to prove each test really fails when its behaviour is broken. Do not use to write the implementation, to change acceptance criteria (send those back to factory-spec), or for work items without an approved spec.md.
---

# factory-test

## When to use

- **Plan mode:** status is `plan-approved`, `docs/work/<id>-<slug>/test-plan.md` is missing or still the template. This is the last step before `implementing`.
- **Audit mode:** code and tests exist (status `implementing`, about to go `in-review`, or reviewer asks). You verify the test plan against reality.
- Not for: writing production code (factory-implement), rewording ACs (factory-spec), reviewing the diff (factory-review).

## Inputs

- `docs/work/<id>-<slug>/spec.md` — the ACs. Use their ids verbatim (AC1, AC2, ...). For bugs, AC1 is the regression criterion.
- `docs/work/<id>-<slug>/plan.md` — files/components touched, risks.
- `docs/work/<id>-<slug>/item.yaml` — `risk` decides depth: low = one case per cell is fine; high = add abuse cases, concurrency, failure injection.
- Template: `.factory/templates/work/test-plan.md` (the CLI pre-renders it as `test-plan.md` in the work item).
- `.factory/policies/testing.md` — project test policy; it wins over your habits.

## Steps

### Plan mode

1. **Discover conventions first.** Find the test runner and config (`pyproject.toml`, `package.json`, `pytest.ini`, CI workflow), the test directory layout, naming style, fixtures/factories, how external services are faked. Run the existing suite once; note the command and the baseline result (any pre-existing failures). Record this in the "Test framework and conventions found" line.
2. **Read spec.md first, then plan.md.** List every AC. If `spec.md` is missing or empty, stop: this is a factory-spec problem.
3. **Gate each AC for testability.** An AC is testable if a stranger could write a pass/fail check from the text alone. It is not if it contains vague words (fast, intuitive, secure, "properly"), no observable outcome, or no concrete input. Do NOT reinterpret it. List it under "Untestable AC" with a proposed rewording, put the NEEDS CLARIFICATION marker (square brackets, see factory-spec) in test-plan.md, and ask the human to take it back to the spec. Spec changes after approval require a fresh human approval.
4. **One row per AC.** Fill the table: AC | Level | Test (name/path) | Happy | Boundary | Negative | Status=`planned`. Choose the lowest level that proves the AC:
   - unit: pure logic, branching, validation.
   - integration: crosses a boundary (DB, HTTP, filesystem, CLI).
   - e2e: only when the AC is about a user-visible flow that lower levels cannot prove.
   - manual: last resort; give exact steps under "Manual checks" and say why it cannot be automated.
5. **Fill all three cases per row, concretely** (real values, not "valid input"):
   - Happy: the typical input and exact expected result.
   - Boundary: empty, one, max, off-by-one, unicode, timezone/DST, null, duplicates, whichever apply. Write `n/a: <reason>` if truly none.
   - Negative/abuse: invalid input, missing permission, malformed payload, injection strings, dependency down. Security-relevant ACs must follow `.factory/policies/security.md`.
6. **Name tests in the project's conventions** (path + function name). Names should read as the AC: `test_login_rejects_expired_token`, not `test_1`.
7. **Regression risk.** Grep for callers and tests of the touched code (from plan.md). List existing tests that must stay green and any that will need changes, with why.
8. **Check preconditions for `implementing`:** test-plan.md is non-empty, every AC has a row, no blank cell, no NEEDS CLARIFICATION marker remains anywhere in the file (comments included). Then tell the human/agent that status may move to `implementing` (run `factory advance <id> implementing`, or edit `item.yaml` by hand: set `status: implementing`). You set nothing in `item.yaml` yourself unless told to do the hand-off.

### Audit mode

1. Re-open test-plan.md. For every row open the real test; replace planned names with real `path::name` and set Status=`written`.
2. **Mutation sanity check per row:** temporarily break the behaviour (flip a condition, return a constant, delete the guard), run only that test, confirm it fails for the right reason, then restore with `git checkout -- <file>` / `git stash` and re-run to confirm green. If you cannot safely mutate, write the concrete reason the test would fail (which assertion, on what value).
3. Reject tests that cannot fail: no assertion, assert on a mock you just configured, `assert True`, exceptions swallowed, tests skipped/xfail, assertions only on "no error".
4. Confirm happy/boundary/negative cases listed actually exist in code. Missing ones: add them (or hand back to the implementer) before verifying.
5. Run the full suite and the project linter. Set Status=`verified` only for rows that pass the mutation check. Write results in the "Audit" section.

## Output

- `docs/work/<id>-<slug>/test-plan.md`, complete, one row per AC, and (after audit) an Audit section with file:line per row.
- A short message: framework found, any untestable ACs sent back, gaps found in audit.

## Definition of done

- Plan mode: every AC has a row; no blank cells; levels justified; conventions recorded; test-plan.md non-empty and free of the NEEDS CLARIFICATION marker, so `implementing` is allowed.
- Audit mode: every row is `verified` with a real test location; each test was shown (or concretely argued) to fail when the behaviour breaks; full suite green; working tree clean of mutations.

## Never

- Never silently reinterpret or drop an AC, and never edit spec.md to make testing easier. Send it back to spec.
- Never mark a row `verified` without breaking the behaviour (or a concrete argument) and seeing the test fail.
- Never leave the NEEDS CLARIFICATION marker (the literal bracketed form) anywhere in test-plan.md, comments included, once the question is resolved.
- Never run `factory approve` or advance status past `implementing` yourself; humans gate approvals.
- Never commit a temporary mutation, skipped test, or weakened assertion.
