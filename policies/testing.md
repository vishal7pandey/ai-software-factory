# Testing policy

## Acceptance criteria to tests

* Every acceptance criterion in `spec.md` maps to at least one test, listed in `test-plan.md`
  (one row per AC: test name or path, level, status).
* Write `test-plan.md` before implementing. An AC with no test is not done.
* When behaviour changes, update the test and the AC together; do not leave them disagreeing.

## Bugs: red, then green

1. Reproduce the bug with a failing regression test. Confirm it fails for the right reason.
2. Fix the code. Confirm the test passes.
3. Keep the test. It is the regression criterion in `spec.md`.

## Never make tests pass by weakening them

* Do not delete, skip, `xfail` or loosen a test to get green, and do not edit an assertion to match
  buggy output. If a test is wrong, say so, fix it in its own commit, and explain in the PR.
* Do not disable lint, type or CI checks. A flaky test gets fixed or reported, not retried until green.

## Determinism

* Unit tests: no real network, no `sleep`, no wall-clock or random dependence (inject or fix clocks and seeds).
* Use temp dirs and in-memory fakes; tests must not depend on order or on leftover state.
* Tests must pass on a clean checkout, on Windows and Linux where the project supports both.

## Coverage

Coverage is a signal, not a target. Do not write assertion-free tests to raise a number. Review
uncovered lines in changed code and cover the ones that carry behaviour.

## Pyramid

* Many fast unit tests for pure logic and edge cases.
* Fewer integration tests for module, database and API boundaries.
* A handful of end-to-end tests for critical user journeys.
* Mock only at system boundaries you do not own; prefer real collaborators inside your code.
* Run the narrow test first, then the full suite before opening a PR.
* After deploy, smoke tests cover the critical path (see `production.md`).
