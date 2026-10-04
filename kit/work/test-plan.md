# {{id}} — Test plan: {{title}}

Status: draft · Risk: {{risk}} · Jira: {{jira}}
<!-- factory:unfilled - delete this line when the document is really written; approval and verify refuse it -->

<!--
Filled by the factory-test skill. One row per acceptance criterion in spec.md (use the AC ids
exactly as written there). Do not merge rows and do not drop an AC.
- Level: unit | integration | e2e | manual (manual needs a reason in Notes below).
- Test: planned test name and path, in the project's own conventions. Later: the real one.
- Happy / Boundary / Negative: the concrete case each test covers (inputs and expected result),
  or "n/a: <reason>". A blank cell is not allowed.
- Status: planned -> written -> verified (verified = fails when the behaviour is broken).
If an AC cannot be tested as written, do not reinterpret it: put it under "Untestable AC" and
send it back to the spec. Leave a NEEDS CLARIFICATION marker (square brackets, see factory-spec)
in the file only while that question is open; implementation may not start while it is present.
-->

Test framework and conventions found: <!-- runner, test dir, naming, fixtures, command to run all tests -->

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_example.py::test_example | <!-- input -> result --> | <!-- edge value --> | <!-- invalid/abusive input --> | planned |

## Regression risk

<!-- Existing behaviour and tests near the touched code that this change could break; which existing
tests must stay green; any test that needs updating and why. -->

## Untestable AC

<!-- AC id, why it cannot be tested as written, proposed testable rewording for the human. "None" if none. -->

## Manual checks

<!-- Only for rows with Level = manual: exact steps and expected observation. "None" if none. -->

## Audit (after implementation)

<!-- Filled by factory-test in audit mode: per row, the real test file:line and how you confirmed it
fails when the behaviour is broken (mutation tried, or concrete reasoning). -->
