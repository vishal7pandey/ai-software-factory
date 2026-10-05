# FACT-34 — Test plan: Findings loop policy and skill

Status: draft · Risk: medium · Jira: FACT-34

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, `tmp_path` fixtures, an autouse isolation fixture in `tests/conftest.py`; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine). All new tests go in `tests/test_findings.py`. The walkthrough helper (`label`, `sweep`, `close`, `dismiss`, a fake `gh` and a fake Jira) is a few pure functions in that file; it takes its `gh api` endpoints from the real `SKILL.md`, so it is a model of the rules, not a client.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_findings.py::test_skill_and_policy_exist_and_lint_clean | both files exist, `lint_skills` on the real repo has no FAIL, the skill body is within the lint cap | description starts "Use when" (lint) | a skill missing a section would fail lint (existing lint tests) | planned |
| AC1 | unit | tests/test_findings.py::test_workflow_routes_findings_and_both_skills_state_the_closure_rule | `factory-workflow` names `factory-findings` and the closure rule; `factory-release` states it | n/a: text presence | removing the name from the workflow text makes the assertion fail (mutation) | planned |
| AC1 | unit | tests/test_findings.py::test_manifest_covers_skill_and_policy | manifest has `skills: all` and a `policies` dir entry | n/a: two fixed entries | n/a: a missing entry would be a manifest lint failure (existing tests) | planned |
| AC2 | unit | tests/test_findings.py::test_two_sweeps_create_one_issue_per_finding | one sweep over 3 fake alerts (one per source) creates 3 issues, each with labels `finding` and `finding-<source>-<id>` | second identical sweep creates 0 and the issue count stays 3 | a fake `gh` call to any endpoint not in the skill text raises | planned |
| AC2 | unit | tests/test_findings.py::test_open_alert_never_allows_done | alert re-queried as `fixed` -> issue Done, comment cites `fixed` | state `dismissed` without approval record, and Sonar `OPEN`, are not `fixed` | alert `open` -> `close` refuses, issue stays not Done; secret `resolved` without `revoked` refuses | planned |
| AC2 | unit | tests/test_findings.py::test_dismissal_needs_explicit_approval_and_allowed_reason | proposed dismissal with approval and an allowed reason is applied and recorded | each of the three reasons accepted | no approval -> not applied; approval with reason "make CI green" -> refused; applied state of the alert unchanged | planned |
| AC2 | unit | tests/test_findings.py::test_first_sweep_is_capped_and_highest_severity_first | 14 alerts of mixed severity -> 10 issues, criticals first, the rest reported as a count | exactly 10 alerts -> 10 issues, none left | low and note severities are not filed on a first sweep | planned |
| AC2 | unit | tests/test_findings.py::test_done_issue_with_reopened_alert_is_reopened_not_duplicated | an alert that reappears open for a Done issue -> that issue is reopened | n/a: single case | no second issue is created | planned |
| AC3 | integration | tests/test_findings.py::test_sync_copies_skill_and_policy_into_an_adopted_project | adopt a scratch project from the real factory root: the skill is in both targets and the policy in `.factory/policies/`, byte-identical | a later `sync` changes nothing (idempotent) | a locally edited policy copy is reported as a conflict, not overwritten | planned |
| AC3 | integration | `uv run python -m swfactory.cli sync --check .` (gate step) | exit 0 after `sync .` | n/a: in sync or not | stale copy -> exit 1 (existing sync tests) | planned |
| AC4 | unit | tests/test_findings.py::test_skill_names_exact_endpoints_and_label_format | the skill contains the three `...alerts?state=open` endpoints, `?ref=refs/pull/{n}/merge` and `finding-<source>-<id>` | the walkthrough parses its endpoints out of the skill, so an edit breaks both | endpoint or label text altered in a copy of the skill -> the same assertions fail (mutation) | planned |
| AC4 | unit | tests/test_findings.py::test_policy_names_closure_rule_reasons_and_enable_commands | the policy has the three reasons exactly, the closure wording, "never dismiss", the batch limits and the enable commands | the reasons in the helper equal the ones in the policy | a reason missing from the policy fails the test | planned |
| AC5 | manual | n/a | n/a | n/a | n/a | planned |

## Regression risk

`tests/test_lint.py::test_repo_implement_skill_carries_the_editing_rules` and `test_install.py` use the real skills or fixtures; the new skill is lint-clean and
the fixture factories are unaffected. `factory sync --check .` in CI (the repo is an adopted project of itself) fails until the managed copies are refreshed, which T6 does.

## Untestable AC

AC5 (the seeded-defect drill) is the end-to-end proof owned by FACT-37; it needs a live scanner and a throwaway PR. Not testable here as written.
Proposed: leave it as a dependency, as the ticket already says. Whether an agent obeys the skill text is not unit-testable either; the walkthrough pins the rules, the drill proves the behaviour.

## Manual checks

AC5: see FACT-37. None for this item.

## Audit (after implementation)

<!-- Filled by factory-test in audit mode: per row, the real test file:line and how you confirmed it
fails when the behaviour is broken (mutation tried, or concrete reasoning). -->
