# {{id}} — {{title}}

Status: draft · Risk: {{risk}} · Jira: {{jira}}
<!-- factory:unfilled - delete this line when the document is really written; approval and verify refuse it -->

<!--
Filled by the factory-diagnose skill. Reproduce first, then find the root cause, then write this.
Do not guess a fix: if the bug is not reproducible, say so under Repro and ask for data.
If something is unknown and a human must answer it, mark it with the NEEDS CLARIFICATION marker
(square brackets, see factory-spec) -- approval is blocked while that marker is present.
Replace every placeholder comment with real content; never leave placeholder text behind.
Security findings: keep exploit details out of public PR text; put them here only if the repo is private.
-->

## Repro

Environment / version / commit where it fails: <!-- e.g. main @ abc1234, Python 3.12, prod -->

1. <!-- exact step, with concrete inputs -->
2. <!-- ... -->

Automated repro (failing test or minimal script, with path and the command to run it):

- <!-- tests/test_x.py::test_name -- fails with: <one-line failure message> -->

Reproducibility: <!-- always | intermittent (rate, conditions) | not reproduced (what was tried) -->

## Expected

<!-- What should happen, citing the source of truth: earlier spec, docs, API contract, common sense. -->

## Actual

<!-- What happens instead: exact error text, wrong value, log lines (redact secrets and personal data). -->

## Root cause (with evidence)

<!--
Cause, not symptom. Cite file:line and the evidence that proves it: git blame / the commit that
introduced it, a log line, a bisect result, a debugger observation. State what you ruled out.
-->

- Where: <!-- path/to/file.py:123 -->
- Why it fails: <!-- the faulty assumption or logic, in one or two sentences -->
- Introduced by: <!-- commit/PR, or "always present" -->
- Evidence: <!-- bisect output, log excerpt, failing assertion -->

## Blast radius

<!--
- Other callers / code paths that reach the same code (list them).
- Other inputs that trigger the same defect.
- Data already corrupted or wrongly processed? Describe it and how to find/repair it (a separate item if large).
- Users or environments affected, and since when.
-->

## Regression criterion (AC1)

AC1: <!-- The failing test from Repro passes after the fix, and it fails on the current code. Name it. -->

<!-- Add AC2.. only for further behaviour the fix must preserve or newly guarantee (e.g. blast-radius cases). -->

## Fix constraints

<!-- Boundaries for the fix: minimal diff, no API change, must stay backward compatible, no migration,
performance budget, files that must not be touched. -->

## Risks

<!-- What could the fix break? Rollout/rollback notes. Reason for the Risk level in the header. -->
