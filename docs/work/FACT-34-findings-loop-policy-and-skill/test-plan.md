# FACT-34 — Test plan: Findings loop policy and skill

Status: in-review · Risk: medium · Jira: FACT-34

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, `tmp_path` fixtures, an autouse isolation fixture in `tests/conftest.py`; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine). All new tests go in `tests/test_findings.py`. The walkthrough helper (`label`, `sweep`, `close`, `dismiss`, a fake `gh` and a fake Jira) is a few pure functions in that file; it takes its `gh api` endpoints, label template and dismissal mapping from the real `SKILL.md` and `findings.md`, so it is a model of the rules, not a client.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_findings.py::test_skill_and_policy_exist_and_lint_clean | both files exist, the whole repo lints without FAIL, frontmatter name and "Use when" are right | body within the 150-line cap | a skill with a bad shape would fail lint (existing lint tests) | verified |
| AC1 | unit | tests/test_findings.py::test_workflow_routes_findings_and_both_skills_state_the_closure_rule | `factory-workflow` names `factory-findings` and states the closure rule; `factory-release` states it; `autonomy.md` and the AGENTS block mention findings | n/a: text presence | removing the route row, or either closure sentence, fails the test | verified |
| AC1 | unit | tests/test_findings.py::test_manifest_covers_skill_and_policy | manifest has `skills: all` and a managed `policies` dir entry; manifest lint clean | n/a: two fixed entries | `skills: none` fails the test | verified |
| AC2 | unit | tests/test_findings.py::test_two_sweeps_create_one_issue_per_finding | one sweep over 3 fake alerts (one per source) creates 3 issues, each labelled `finding` and `finding-<source>-<id>` | second identical sweep creates 0 and the count stays 3 | any `gh` endpoint the skill does not name raises; no secret value reaches Jira | verified |
| AC2 | unit | tests/test_findings.py::test_open_alert_never_allows_done | alert re-queried as `fixed` -> Done, comment cites the state; secret `resolved` + `revoked` -> Done | `dismissed` alert is not `fixed` | alert `open` -> refused and issue unchanged; secret `resolved` as `wont_fix` -> refused | verified |
| AC2 | unit | tests/test_findings.py::test_dismissal_needs_explicit_approval_and_allowed_reason | approved dismissal with an allowed reason is applied with the policy's API value for each scanner and recorded on the issue | each of the three reasons accepted | no approval (None, "") -> refused, alert still open, no PATCH; approved with "make CI green", "", "fixed", "wontfix" -> refused | verified |
| AC2 | unit | tests/test_findings.py::test_first_sweep_is_capped_and_highest_severity_first | 18 alerts -> 10 issues: secrets, then criticals, then a high; the rest reported as counts; later runs file the other 8, then 0 | the 10th issue is exactly at the cap | an 11th eligible alert is not filed | verified |
| AC2 | unit | tests/test_findings.py::test_exactly_the_limit_leaves_nothing_behind_and_does_not_flood | 10 criticals -> 10 issues | exactly the limit | a low alert alongside is reported, not filed | verified |
| AC2 | unit | tests/test_findings.py::test_first_sweep_files_only_critical_and_high_even_below_the_cap | critical and high filed on a first sweep | the second sweep files the lower ones | medium and low are not filed on the first sweep | verified |
| AC2 | unit | tests/test_findings.py::test_code_scanning_severity_falls_back_to_rule_severity | `error` -> high | `note` -> low | n/a: two values | verified |
| AC2 | unit | tests/test_findings.py::test_done_issue_with_reopened_alert_is_reopened_not_duplicated | an alert that reappears open for a Done issue reopens that issue | n/a: single case | no second issue is created | verified |
| AC3 | integration | tests/test_findings.py::test_sync_copies_skill_and_policy_into_an_adopted_project | adopt a scratch project from the real factory root: the skill is in every target and the policy in `.factory/policies/`, identical to the sources | a second sync changes nothing; `sync --check` exits 0 | a project that has neither file (adopted before this release) gets both on `sync` | verified |
| AC3 | integration | tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit and `uv run python -m swfactory.cli sync --check .` | exit 0 after `sync .` | n/a: in sync or not | stale copy -> exit 1 (this test failed until `sync .` was run) | verified |
| AC4 | unit | tests/test_findings.py::test_skill_names_exact_endpoints_and_label_format | the skill contains the three `...alerts?state=open` commands, `?ref=refs/pull/{n}/merge`, the label template, the four sources and the single-alert re-query paths | the walkthrough parses its endpoints from the skill, so an edit breaks it too | endpoint, PR form or label text altered -> this test and the walkthrough fail | verified |
| AC4 | unit | tests/test_findings.py::test_endpoint_drift_is_detected | n/a: negative-only | a skill copy with `state=all` yields different endpoints | the fake `gh` raises for the original endpoint | verified |
| AC4 | unit | tests/test_findings.py::test_policy_names_closure_rule_reasons_and_enable_commands | the policy has the three reasons, the mapping table, the closure wording, "never dismiss", the batch limits and the five enable commands | table has exactly three reasons and three scanner columns | a changed batch limit, removed sentence or renamed reason fails the test | verified |
| AC5 | manual | n/a | n/a | n/a | n/a | untestable here (FACT-37) |

## Regression risk

`tests/test_lint.py::test_repo_implement_skill_carries_the_editing_rules` and `test_install.py` use the real skills or fixtures; the new skill is lint-clean and
the fixture factories are unaffected. `tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit` and CI's `factory sync --check` fail until the managed copies are refreshed, which `factory sync .` does (done in its own commit).

## Untestable AC

AC5 (the seeded-defect drill) is the end-to-end proof owned by FACT-37; it needs a live scanner and a throwaway PR. Not testable here as written.
Proposed: leave it as a dependency, as the ticket already says. Whether an agent obeys the skill text is not unit-testable either; the walkthrough pins the rules, the drill proves the behaviour.

## Manual checks

AC5: see FACT-37. None for this item.

## Audit (after implementation)

Each mutation applied temporarily (text or helper edit), `tests/test_findings.py` run, then restored with `git checkout`. Lines are in `tests/test_findings.py`. 15 tests; the full suite is 309 tests.

| AC | Real test(s) | Broken on purpose | Result |
|----|--------------|-------------------|--------|
| AC1 | `:317` workflow_routes... | `Scanner findings (open` renamed in `skills/factory-workflow/SKILL.md` | fails |
| AC1 | `:317` | closure sentence removed from `factory-release` / from `factory-workflow` (two runs) | fails both times |
| AC1 | `:330` manifest_covers... | `skills: all` -> `skills: none` in `kit/manifest.yaml` | fails (and the sync test fails too) |
| AC2 | `:387` two_sweeps..., `:494`, `:539` | `search_label` returns `[]` (no search before create) | three tests fail: duplicates are created |
| AC2 | `:406` open_alert_never_allows_done | `confirmed` returns True for any state | fails |
| AC2 | `:406` | secret closure ignores `resolution == revoked` | fails |
| AC2 | `:435` dismissal_needs... | approval check removed (`if False:`) | fails: `DID NOT RAISE DismissalRefused` |
| AC2 | `:435` | reason check removed | fails |
| AC2 | `:435` | policy table value `inaccurate` -> `bogus` in `policies/findings.md` | fails (the walkthrough reads the policy table) |
| AC2 | `:494` first_sweep_is_capped | `BATCH_LIMIT` 10 -> 100; severity order reversed (two runs) | fails both times |
| AC2 | `:517` first_sweep_files_only_critical_and_high | first-sweep filter forced off | first survived the suite (the cap test hid it), so this test was added; with it the mutation fails |
| AC2 | `:539` done_issue_with_reopened_alert | reopen branch removed (`if False:`) | fails |
| AC3 | `:580` sync_copies... | `dest: .factory/policies` -> `.factory/pol` in `kit/manifest.yaml` | fails |
| AC3 | `uv run python -m swfactory.cli sync --check .` | repo copies not synced | before `sync .`: `test_factory_repo_is_in_sync_with_its_kit` failed; after: exit 0 |
| AC4 | `:340` skill_names_exact_endpoints... | `dependabot/alerts?state=open` -> `state=all` in the skill | this test and four walkthrough tests fail |
| AC4 | `:340` | PR form `?ref=refs/pull/{n}/merge` -> `?pr={n}` | fails |
| AC4 | `:340` | label template `finding-<source>-<id>` -> `finding_<source>_<id>` | fails, with six walkthrough tests |
| AC4 | `:363` policy_names... | "Never dismiss a finding to make a check go green" reworded; `at most 10 issues` -> 100; reason table row renamed (three runs) | fails each time |
