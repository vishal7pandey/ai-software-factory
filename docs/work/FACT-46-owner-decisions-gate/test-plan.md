# FACT-46 — Test plan: Owner decisions gate

Status: draft · Risk: medium · Jira: FACT-46

Test framework and conventions found: pytest, `tests/`, fixtures in `tests/conftest.py` (isolated HOME and
registry, no `gh`, no project commands); command tests drive `cli.build_parser()`; contract tests read the real kit.
Run all: `uv run python -m pytest -q`. New file: `tests/test_decisions.py`; additions in `tests/test_lint.py` and
`tests/test_findings.py`. `common.today` is pinned to 2026-10-07 in the decisions tests.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_decisions.py::test_decide_accepts_the_recommended_option_and_keeps_the_body, test_decide_option_picks_by_number, test_decide_reject_with_note, test_decide_accepts_by_file_stem, test_decide_stamps_the_subject_hash | accept stamps status, decision, by (git user), at, body identical; `--option 2`; `--reject --note`; id by stem; subject hash of CRLF file | `--option` 1-based pick; mixed-case id | n/a: see next rows | verified |
| AC1 | integration | tests/test_decisions.py::test_decide_refuses_a_record_that_is_not_proposed, test_decide_refuses_templates_and_placeholders, test_decide_refuses_an_invalid_record, test_decide_refuses_an_option_out_of_range, test_decide_option_only_applies_to_accept, test_decide_unknown_and_ambiguous_ids, test_decide_refuses_a_missing_subject | n/a: happy rows above | options 0, 3, -1 | accepted/rejected/superseded; unfilled line, clarification marker, REPLACE_ME, `{{`; invalid front matter; unknown and duplicate id; missing subject; file bytes unchanged | verified |
| AC2 | integration | tests/test_decisions.py::test_status_lists_waiting_records, test_status_is_silent_when_nothing_waits, test_age_text, test_listing_marks_drafts_and_cuts_long_text | block with id, type, `3 days`, title, recommended; accepted one absent | 0, 1, N days; 90-char title cut to 60; draft marker | none waiting, no folder, rejected only: nothing printed | verified |
| AC2 | integration | tests/test_decisions.py::test_doctor_findings_per_waiting_record, test_doctor_is_silent_without_waiting_records_and_warns_on_invalid_ones, test_doctor_command_prints_the_waiting_record | one WARN per waiting record, exit 0 | accepted record not listed | invalid record and unreadable file: WARN, no crash; none waiting: no finding | verified |
| AC3 | integration | tests/test_decisions.py::test_inbox_aggregates_registered_projects, test_inbox_nothing_waiting_and_no_registry, test_inbox_skips_unreadable_records_without_failing, test_registry_projects_helper | two projects grouped, name order, exact output, files unchanged | project without path, missing path | no registry, nothing waiting, invalid record reported not fatal | verified |
| AC4 | unit | tests/test_decisions.py::test_valid_records_have_no_problems, test_validator_rejects (34 cases), test_validator_rejects_a_non_mapping, test_front_matter_parser_errors_and_crlf | proposed, accepted, rejected, superseded, delegated design, dismissal, subject records valid | CRLF front matter; dates as ISO strings | each R7 rule: accepted without by/at, bad date, decision not an option, proposed answered, no/duplicate/two recommended, id mismatch, bad enums, delegated wording, delegated charter/dismissal, dismissal fields, subject sha and path | verified |
| AC4 | integration | tests/test_decisions.py::test_verify_ok_for_valid_records_and_ignores_adrs_and_templates, test_verify_fails_accepted_without_approver_and_date, test_verify_reports_unparseable_and_duplicate_records, test_verify_reads_crlf_records | `verify` OK with ADR, TEMPLATE.md, README | CRLF record | `FAIL D-001: ... 'by' is missing`, exit 1; broken and duplicate ids | verified |
| AC5 | contract | tests/test_findings.py::test_skill_routes_dismissals_through_a_decision_record, test_policy_gates_dismissals_on_an_accepted_record | skill and policy name the record flow, the accepted-only call, the Jira citation | wrapped lines normalised | old "propose for the human to approve" and "says yes in words" wording absent | verified |
| AC5 | scripted walkthrough | tests/test_findings.py::test_dismissal_is_applied_only_from_an_accepted_record, test_a_dismissal_record_cannot_be_delegated_to_an_agent | accepted record: alert dismissed, issue Done, comment cites id/by/at | api mapping unchanged | proposed, rejected, unsigned accepted, other option, delegated: no PATCH | verified |
| AC6 | integration | tests/test_decisions.py::test_decide_without_yes_on_a_non_terminal_is_refused, test_decide_interactive_confirmation, test_decide_needs_exactly_one_of_accept_or_reject, test_decide_function_refuses_both_or_neither | tty `y` decides | tty `n` leaves file | non-terminal without `--yes`; neither or both flags (exit 2) | verified |
| AC6 | integration | tests/test_decisions.py::test_delegated_is_refused_for_never_delegated_types, test_delegated_form_for_a_design_record, test_delegated_needs_a_name | design record gets `(delegated to agent)` and `delegated: true` | blank name | charter and dismissal refused, file unchanged | verified |
| AC6 | integration | tests/test_decisions.py::test_read_only_commands_never_decide, test_handoff_prompts_never_tell_the_agent_to_decide; tests/test_lint.py::test_decide_instruction_fails, test_decide_prohibition_passes; tests/test_decisions.py::test_every_real_skill_passes_lint_including_the_decide_rule | prohibition lines pass | every status's prompt | status, inbox, doctor, feature start, next leave records byte-identical; a skill line instructing `factory decide` fails lint | verified |
| AC7 | integration | tests/test_decisions.py::test_new_scaffolds_valid_draft_records_with_increasing_ids, test_new_record_becomes_decidable_once_written, test_new_dismissal_carries_alert_reason_and_options, test_a_broken_record_still_reserves_its_id | D-001 then D-002 valid for verify; draft until written; dismissal options | a broken D-004 reserves its id | decide refuses the scaffold | verified |
| AC7 | integration | tests/test_decisions.py::test_new_dismissal_needs_alert_and_an_allowed_reason, test_new_refuses_alert_flags_on_other_types_and_empty_titles | n/a: above | n/a: n/a | missing alert/reason, bad reason, bad URL, alert on design, empty title, bad Jira key; nothing created | verified |
| AC8 | integration | tests/test_decisions.py::test_manifest_lays_the_template_create_mode, test_adopt_creates_the_template_and_sync_never_touches_it, test_template_is_a_draft_that_decide_refuses, test_lint_fails_when_the_named_template_is_missing | adopt creates the file, sync --check 0, verify clean | edited copy kept by sync | missing template named in the manifest fails lint | verified |
| AC8 | contract | tests/test_decisions.py::test_skills_send_owner_choices_to_a_decision_record (4 skills), test_autonomy_policy_and_agents_block_forbid_deciding, test_treaty_documents_the_gate | skills, policy, AGENTS block, Treaty carry the text | n/a: text | n/a: text | verified |
| AC8 | integration | tests/test_decisions.py::test_a_record_symlinked_out_of_the_folder_is_skipped | n/a: containment | symlink in the folder | skipped on this Windows machine (no symlink rights); runs on Linux CI | verified (CI) |

## Regression risk

`tests/test_work.py` (status output unchanged without records), `tests/test_doctor.py`, `tests/test_install.py`
(a new create-mode file appears in adopt output; counts are asserted on specific files, all green), `tests/test_lint.py`
(the approve rule now also covers decide: same message shape), `tests/test_findings.py` (existing walkthrough keeps
the `dismiss` helper; the new text did not break its pins), `tests/test_verify.py` (rule 6 only fires for `D-<n>-*.md`).
Full suite before: 602 passed, 1 skipped; after: see Audit.

## Untestable AC

None. The cross-project dogfood of the ticket (records in other projects) is out of scope of this item (spec Non-goals).

## Manual checks

None.

## Audit (after implementation)

2026-10-07. Tests were drafted first (`tests/test_decisions.py`, run red against the then-missing commands and text), but
`verify.py`'s validator was written before them, so it is covered by the mutations below rather than by a red run.
Full suite after the change and after the Sonar-driven refactor (PR scan: S3776 complexity, S3516, S5713, S3358 fixed): 729 passed, 2 skipped (the registry and the new record symlink tests, no symlink rights on this Windows machine). Mutation line numbers are from the final code; the run was repeated after the refactor, same results.
Deliberate breaks, each restored afterwards (`git diff` shows only the intended change); tests run:
`tests/test_decisions.py tests/test_findings.py tests/test_lint.py`.

| Mutation | Result |
|----------|--------|
| M1 `verify.py:443` accepted no longer requires by/at (`status in ("rejected",)`) | killed: `test_validator_rejects[accepted without by]` |
| M2 `verify.py:469` delegated charter/dismissal check disabled (`if False and ...`) | killed: `test_validator_rejects[delegated charter]` |
| M3 `verify.py:499` subject sha check always passes | killed: `test_validator_rejects[accepted subject without sha]` |
| M4 `decisions.py:277` non-terminal check removed (agent shell path) | killed: `test_decide_without_yes_on_a_non_terminal_is_refused` |
| M5 `decisions.py:244` status check removed (decide an accepted record) | killed: `test_decide_refuses_a_record_that_is_not_proposed[accepted]` |
| M6 `decisions.py:246` placeholder check removed | killed: `test_decide_refuses_templates_and_placeholders[the unfilled-marker line]` |
| M7 `decisions.py:300` delegation refusal for charter/dismissal removed | killed: `test_delegated_is_refused_for_never_delegated_types[charter]` |
| M8 `decisions.py:287` accept/reject exclusivity removed | killed: `test_decide_function_refuses_both_or_neither` |
| M9 `decisions.py:166` status lists every record, not only waiting ones | killed: `test_status_lists_waiting_records` |
| M10 `checks.py:60` lint rule back to `factory approve` only | killed: `test_decide_instruction_fails[Run ...]` |
| M11 skill/policy text: `No accepted record, no call.` reworded | killed: `test_skill_routes_dismissals_through_a_decision_record` |
| M12 `decisions.py:108` symlink containment removed | survives locally: the test needs symlink rights (skipped on this machine); runs on Linux CI |
