# FACT-47 — Test plan: Project charter

Status: draft · Risk: medium · Jira: FACT-47

Test framework and conventions found: pytest, `tests/`, fixtures in `tests/conftest.py` (isolated HOME and registry, no
`gh`), command tests drive `cli.build_parser()`; new file `tests/test_charter.py` (builders for charters, records and work
items; `common.today` pinned; a Jira lookup is a stub function). Run all: `uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit/integration | tests/test_charter.py::test_the_template_is_create_mode_and_a_draft, test_adopt_creates_the_charter_and_sync_keeps_an_edited_copy, test_state_absent_and_template | manifest entry is `create`, `templates.charter` exists, template parses with the maintenance section; adopt creates the file; sync --check 0 | edited copy survives sync; not in `managed` | the template is never a charter (marker problem) and state is `template` | verified |
| AC1 | integration | tests/test_charter.py::test_decision_new_charter_scaffolds_the_record | record has `subject: docs/PROJECT.md`, one recommended option, validates, prints the `decision: D-001` hint | n/a: single case | n/a: dismissal flags covered in test_decisions | verified |
| AC2 | unit | tests/test_charter.py::test_a_good_charter_has_no_problems, test_validator_rejects (35 cases), test_validator_needs_the_maintenance_section_and_a_mapping, test_parse_never_raises_and_reports_why | active, maintenance, no decision, empty parked all valid | 3 and 7 criteria valid; 2 and 8 not; CRLF text parses | empty `done`, "works well", "user-friendly", "robust", two words, no/two/unknown check kind, bad ids, paths that escape, metric without/with two bounds or a bool bound, no purpose/non-goals, bad mode/decision, bad parked, no maintenance section, template | verified |
| AC2 | integration | tests/test_charter.py::test_state_unapproved_reasons, test_state_approved_and_changed, test_state_approved_with_crlf_file, test_state_invalid, test_doctor_warns_without_an_approved_charter_and_is_clean_with_one, test_doctor_command_shows_the_charter_line | approved charter: one OK `charter` finding, no WARN, doctor exit 0 | CRLF file hashes like LF | no file, template, invalid, no decision, missing/wrong-type/proposed/rejected/superseded/invalid record, edited after approval: each a WARN, never FAIL | verified |
| AC3 | unit | tests/test_charter.py::test_work_criterion, test_file_criterion, test_metric_criterion_bounds (7), test_metric_criterion_unknown_when_unreadable (6), test_metric_reads_json, test_jira_criterion_uses_the_injected_lookup, test_evaluate_never_reads_outside_the_project | merged/released/done work item met; file exists; metric within bound; Jira Done | bound equal to value (min 0.9 at 0.9); JSON file | draft/in-review item, missing item, missing file, below bound, unreadable metric file/key/non-number: `unknown`, no lookup: `unknown`, `../` paths | verified |
| AC3 | integration | tests/test_charter.py::test_status_shows_progress_and_not_yet_ready, test_status_flips_to_ready_when_all_met, test_an_unknown_criterion_keeps_it_from_flipping, test_status_in_maintenance_mode_prints_the_stop_rule, test_status_prints_one_line_for_an_unapproved_charter_and_nothing_without | `2 of 4 met` with per-criterion lines and references; `4 of 4` prints "ready for maintenance mode ... never run by an agent" | 3 of 4 with one `unknown` does not flip | metric below bound is `not met`; unapproved charter: one line; no charter: nothing | verified |
| AC4 | integration | tests/test_charter.py::test_feature_start_warns_in_maintenance_mode, test_no_warning_in_active_mode_or_for_a_bug, test_no_warning_without_a_charter, test_the_warning_survives_an_edit_after_approval | warning printed and the item is still created | charter edited after approval still warns | active mode, bug start, no charter, never-approved charter: silent | verified |
| AC5 | contract | tests/test_charter.py::test_the_factory_charter_is_valid_and_its_record_names_it, test_the_factory_charter_references_exist | real `docs/PROJECT.md` valid, `mode: active`, 5 to 7 criteria, parked and non-goals; its record `D-002` is a valid `charter` record with `subject: docs/PROJECT.md`; `verify` clean | the record is `proposed` (a test tolerates the owner's later `accepted`, which must then carry `by`) | n/a: pins validity, not the owner's answer | verified; proposed state checked by hand (see Audit) |
| AC6 | integration | tests/test_charter.py::test_decide_accept_stamps_the_hash_and_approves, test_decide_refuses_a_charter_that_is_not_ready (4), test_a_charter_record_without_a_subject_fails_verify, test_reject_needs_no_valid_charter_and_is_never_delegated, test_an_agent_shell_cannot_approve_a_charter | accept stamps the sha, state `approved`, later edit is `changed` | reject works with no valid charter | file missing, invalid, naming another record or none: refused, record unchanged; `--delegated` refused; no `--yes` on a non-terminal refused; record without subject fails verify | verified |
| AC7 | contract | tests/test_charter.py::test_spec_skill_checks_proposed_work_against_the_charter, test_workflow_policy_and_treaty_describe_the_charter | skill, workflow, policy and Treaty 3.12 carry the text; `lint` clean | wrapped lines normalised | n/a: text | verified |

## Regression risk

`tests/test_integration.py::test_adopt_is_idempotent_and_doctor_is_clean` and `tests/test_sonar.py::test_doctor_after_a_real_adopt_has_no_warning_for_a_local_only_project`
asserted a clean doctor after adopt; a fresh adopt now has exactly one WARN, the charter template (the intended pressure), and both tests now say
so. `tests/test_decisions.py::test_delegated_is_refused_for_never_delegated_types` gives its charter record the required
subject. Everything else unchanged: full suite 602 -> 729 (FACT-46) -> 816 passed.

## Untestable AC

None. AC5's "proposed, not accepted" is the owner's state to change, so the test pins validity and checks by hand that the record is proposed.

## Manual checks

- AC5: `uv run python -m swfactory.cli status` on this repo lists D-002 as waiting and `charter: no approved charter - decision D-002 is waiting for the owner`; `doctor` shows the WARN; `verify` is OK.

## Audit (after implementation)

2026-10-07. Tests were written first (`tests/test_charter.py`, red against the then-missing `charter` module), then the
module. Full suite: 816 passed, 2 skipped (the two symlink tests, no symlink rights on this Windows machine). Deliberate
breaks, each restored afterwards; tests run: `tests/test_charter.py tests/test_decisions.py tests/test_lint.py`.

| Mutation | Result |
|----------|--------|
| M1 `charter.py:131` vague-phrase check removed | killed: `test_validator_rejects[works well]` |
| M2 `charter.py:187` criteria count check removed | killed: `test_validator_rejects[no done list]` |
| M3 `charter.py:210` work item no longer needs `merged` | killed: `test_work_criterion` (draft) |
| M4 `charter.py:247` `min` compares the wrong way | killed: `test_metric_criterion_bounds[bound0-0.91-met]` |
| M5 `charter.py:307` record status not checked (a proposed record approves) | killed: `test_state_unapproved_reasons` |
| M6 `charter.py:314` hash comparison removed (no `changed`) | killed: `test_state_approved_and_changed` |
| M7 `charter.py:351` `decide` no longer needs the charter to name the record | killed: `test_decide_refuses_a_charter_that_is_not_ready[other-record]` |
| M8 `charter.py:382` "ready" printed with criteria unmet | killed: `test_status_shows_progress_and_not_yet_ready` |
| M9 `charter.py:394` warning only for `approved`, not `changed` | first run SURVIVED; test `test_the_warning_survives_an_edit_after_approval` added; re-run: killed |
| M10 `work.py:301` warning for bugs too | killed: `test_no_warning_in_active_mode_or_for_a_bug` |
| M11 `verify.py:487` charter subject rule removed | killed: `test_a_charter_record_without_a_subject_fails_verify` |

Manual: `docs/decisions/D-002-approve-the-factory-project-charter.md` is `status: proposed` (not accepted), as asked.
