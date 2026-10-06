# FACT-38 — Test plan: Group same-package and same-rule findings into one issue

Status: in-review · Risk: medium · Jira: FACT-38

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, `tmp_path` fixtures, autouse isolation in `tests/conftest.py`; run everything with `uv run python -m pytest -q` (`pytest.exe` is blocked on this machine). All new tests go in `tests/test_findings.py`, next to the FACT-34 walkthrough. The helper (`normalise`, `sweep`, `close`, `dismiss`, `FakeGh`, `FakeJira`) is extended to model groups; it still takes its endpoints, label template and reason mapping from the real skill and policy text. Fixtures `cs()` and `dep()` get distinct default rules, files and packages so the existing one-issue-per-alert tests do not change meaning; new tests build groups on purpose with explicit `rule=`, `path=`, `package=`, `manifest=`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_findings.py::test_grouping_rule_is_stated_in_skill_and_policy | skill and policy contain: grouping is the default, same Dependabot package in the same manifest, same code-scanning rule in the same file or module, module = directory (non-recursive), the group summary formats, per-alert issues on request | the group summary formats in the skill equal the ones the helper builds | removing any of these phrases from the skill or the policy fails the test | verified |
| AC1 | unit | tests/test_findings.py::test_old_one_issue_per_finding_rule_is_gone_everywhere | none of `skills/`, `policies/`, `kit/`, `docs/` (outside `docs/work/`) contains "Do not merge several alerts into one issue" or "one Jira Bug each" | n/a: text scan | reintroducing either sentence fails the test | verified |
| AC1 | unit | tests/test_findings.py::test_workflow_routes_findings_and_both_skills_state_the_closure_rule | `factory-workflow` and `factory-release` still route and state the closure rule, now with "every alert" the issue carries | n/a: text presence | removing "every alert" or the open-alert sentence from either file fails | verified |
| AC2 | unit | tests/test_findings.py::test_same_package_and_manifest_dependabot_alerts_share_one_issue | 3 alerts of one package in one manifest give 1 issue with 3 `finding-dependabot-<id>` labels and 1 `finding` label | a different manifest for the same package, and a different package in the same manifest, each give their own issue | an alert is never given two issues; no label lost | verified |
| AC2 | unit | tests/test_findings.py::test_same_rule_in_the_same_directory_shares_one_issue | 2 alerts of one rule in two files of one directory give 1 issue; the summary is `[<rule>] <dir>/` | same file twice; repo-root files group under `./`; a subdirectory is a different module | same rule in another directory, other rule in the same directory, and an alert with no path are separate issues | verified |
| AC2 | unit | tests/test_findings.py::test_secret_alerts_are_never_grouped | two secret alerts give two issues | n/a: two alerts | secrets never share an issue | verified |
| AC2 | unit | tests/test_findings.py::test_two_sweeps_create_one_issue_per_group | run 1 creates one issue per group; run 2 over the same alerts creates 0 and reports every alert already tracked | issue count is stable across a third run | search by label removed (mutation) would create duplicates | verified |
| AC2 | unit | tests/test_findings.py::test_per_alert_mode_when_the_human_asks | `grouping=False` gives one issue per alert for alerts that would otherwise group, with per-alert summaries (`:<line>` / `(alert <id>)`) | a later grouped run does not join those issues (summaries differ) | n/a: opt-in only | verified |
| AC3 | unit | tests/test_findings.py::test_group_with_an_open_alert_is_not_done | all alerts `fixed` -> Done, comment cites every alert URL and state | the last alert flips to `fixed` and only then the issue closes | 2 of 3 `fixed`, 1 `open` -> not Done, status unchanged, comment names the open alert | verified |
| AC3 | unit | tests/test_findings.py::test_group_with_dismissed_alert_needs_the_recorded_approval | one `fixed` plus one dismissed with recorded approval -> Done | dismissing the last open alert is what closes the issue, not the first | one `fixed` plus one `dismissed` with no approval on the issue -> not Done; approved dismissal of one alert leaves the issue open while another is `open` | verified |
| AC4 | unit | tests/test_findings.py::test_new_alert_joins_an_existing_open_group | a later run with one new alert of an open group adds its label and a comment with its URL, creates no issue | a higher severity raises the issue priority; a lower one does not lower it | the alert is not attached to an issue of a different group (other package, other directory) | verified |
| AC4 | unit | tests/test_findings.py::test_new_alert_for_a_done_group_gets_a_new_issue | a new alert whose only matching group is Done creates a new issue; the Done group stays Done and keeps its labels | the next new alert of that group joins the new open issue, not the Done one | the Done issue is not reopened and not given the new label | verified |
| AC4 | unit | tests/test_findings.py::test_reopened_alert_of_a_done_group_reopens_that_issue | an alert already labelled on a Done group, open again, reopens that same issue with a comment | n/a: single case | no second issue is created | verified |
| AC5 | unit | tests/test_findings.py::test_the_cap_counts_issues_not_alerts | 12 groups of 2 alerts: a run creates 10 issues carrying 20 alerts; the 2 remaining groups are unfiled | alerts joining an issue created in the same run do not use up the cap; exactly 10 groups with 11 alerts each also creates 10 | an 11th group is not filed on the same run | verified |
| AC5 | unit | tests/test_findings.py::test_alerts_joining_a_group_do_not_use_up_the_cap | a 30-alert group plus 9 single alerts file 39 alerts in 10 issues, nothing unfiled | exactly 10 issues | joining alerts never count toward the cap | verified |
| AC5 | unit | tests/test_findings.py::test_report_gives_alerts_and_issues | the report shows alerts found, alerts filed, issues created, joined, tracked and unfiled; 15 alerts in 10 issues reads 15 and 10 | a run with no grouping has equal counts | alerts not filed (cap, severity) are counted as alerts, not issues | verified |
| AC6 | integration | tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit and `uv run python -m swfactory.cli sync --check .` | exit 0 after `sync .` | n/a: in sync or not | stale managed copy -> exit 1 | verified |
| AC6 | integration | tests/test_findings.py::test_sync_copies_skill_and_policy_into_an_adopted_project, `factory lint`, full suite | the changed skill and policy reach a scratch adopted project byte-identical; lint clean | skill body within 150 lines | n/a: existing tests | verified |

## Regression risk

The existing walkthrough tests (`test_two_sweeps_create_one_issue_per_finding`, `test_open_alert_never_allows_done`, `test_dismissal_needs_explicit_approval_and_allowed_reason`,
the cap and first-sweep tests, `test_done_issue_with_reopened_alert_is_reopened_not_duplicated`) run on the changed helper; they must stay green with
only fixture defaults changed (distinct rules, files and packages per alert), which proves single alerts still get one issue each.
`test_workflow_routes_findings_and_both_skills_state_the_closure_rule` is tightened. `test_integration.py::test_factory_repo_is_in_sync_with_its_kit` fails until `factory sync .` is run.

## Untestable AC

None. (Whether an agent obeys the text is the FACT-37 drill; the rules are pinned as functions and as text.)

## Manual checks

None.

## Audit (after implementation)

Each mutation applied temporarily (text or helper edit) with `tests/test_findings.py` run, then restored with `git checkout`. Lines are in `tests/test_findings.py` at the audited commit; the file has 30 tests (15 before this item) and the full suite is 385 tests. The helper functions are the model of the rules, so breaking the helper is how a rule is "broken"; text mutations break the real skill, policy and routing files.

| AC | Real test(s) | Broken on purpose | Result |
|----|--------------|-------------------|--------|
| AC1 | `:483` grouping_rule_is_stated... | skill: "Per-alert issues remain available when the human asks" reworded | fails |
| AC1 | `:483` | policy: "the same directory: the part" -> "the same package: the part" (module definition) | fails |
| AC1 | `:483` | skill: the "never grouped" sentence for secrets and Sonar replaced; policy: "The cap counts issues, not alerts" -> "counts alerts"; skill: "only when all" removed; skill: Done-group sentence replaced (four runs) | fails each time |
| AC1 | `:407` workflow_routes... | `factory-workflow` / `factory-release`: "every alert the issue carries" -> "the alert" (two runs) | fails both times |
| AC1 | `:510` old_one_issue_per_finding_rule_is_gone | "One issue per finding." added to `kit/AGENTS.block.md` | fails (the first full run also caught a real leftover in the workflow route row) |
| AC2 | `:709` same_package_and_manifest..., `:733` same_rule_in_the_same_directory... | `directory()` returns the full path (no module grouping) | fails (4 tests) |
| AC2 | `:709`, `:733` | Dependabot group key drops the manifest; code-scanning key uses the directory only in brackets (two runs) | fails (5 and 2 tests) |
| AC2 | `:765` secret_alerts_are_never_grouped | secrets given a group key | fails (with the cap test) |
| AC2 | `:779` two_sweeps_create_one_issue_per_group, `:536` | `search_label` returns nothing (no search before create) | 8 tests fail: duplicates created |
| AC2 | `:779` and 10 others | open-group lookup returns nothing (no join) | 11 tests fail |
| AC2 | `:791` per_alert_mode_when_the_human_asks | per-alert Dependabot summary equal to the group summary (no `(alert <id>)`) | fails: a later run joins a per-alert issue |
| AC3 | `:808` group_with_an_open_alert_is_not_done | `if blocking:` -> `if False:` in `close` | fails (3 tests, also the older open-alert test) |
| AC3 | `:808`, `:829` | `check_alerts` re-queries only the first alert of an issue | fails (2 tests) |
| AC3 | `:829` group_with_dismissed_alert... | `confirmed` accepts `dismissed` | fails (2 tests) |
| AC3 | `:829`, `:584` | recorded approvals ignored (`if lbl in issue.dismissed` -> `if False`) | fails (2 tests) |
| AC3 | `:829` | `dismiss` sets Done even when another alert is open | fails |
| AC4 | `:859` new_alert_joins_an_existing_open_group | join no longer appends the label | 9 tests fail |
| AC4 | `:859` | priority is never raised on join | fails |
| AC4 | `:890` new_alert_for_a_done_group... | open-group lookup includes Done issues | fails |
| AC4 | `:911` reopened_alert_of_a_done_group..., `:688` | reopen branch removed (`if False`) | fails (2 tests) |
| AC5 | `:926` the_cap_counts_issues_not_alerts, `:947` | cap compares alerts filed instead of issues created | fails (2 tests) |
| AC5 | `:957` report_gives_alerts_and_issues | joined alerts not counted as filed | fails (5 tests) |
| AC5 | `:957`, `:666` | first-sweep severity filter forced off | fails (2 tests) |
| AC5 | `:483` | report sentence "in alerts and in issues": removing it from step 7 alone survives, because the Definition of done line carries the same phrase and is still present; both lines are pinned together, not separately | survives (accepted: the helper tests pin the counts) |
| AC6 | `tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit`, `factory sync --check .` | skill edited without `factory sync .` | fails; after sync, exit 0 |
