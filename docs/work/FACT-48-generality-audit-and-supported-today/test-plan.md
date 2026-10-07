# FACT-48 — Test plan: Generality audit and supported-today matrix

Status: draft · Risk: low · Jira: FACT-48

Test framework and conventions found: pytest, `tests/test_*.py`, synthetic repository trees in `tmp_path`, the real
repository as `ROOT`; run all with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine).
Lint wiring is tested through `main(["lint"])` with `common.FACTORY_ROOT` monkeypatched, as `tests/test_lint.py` does.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | `tests/test_support.py::test_real_matrix_is_current`, `::test_real_matrix_has_the_rows_the_ticket_names`, `::test_real_matrix_is_honest_about_the_inert_github_tracker`, `::test_treaty_and_roadmap_link_the_matrix_and_the_page` | the real repo returns no problem; every named stack, tracker and dimension has a row; both docs link `SUPPORT.md` and name the page | the github tracker row says `not supported` and mentions that nothing reads it | n/a: negatives are AC2 and AC3 | verified |
| AC2 | unit | `::test_stack_from_a_file_without_a_row_fails` (4 paths), `::test_stack_from_the_manifest_without_a_row_fails` (2 forms), `::test_stack_from_the_code_constant_needs_a_row`, `::test_not_supported_row_goes_stale_when_the_stack_arrives` (3 paths) | `templates/go`, `kit/ci/go.yml`, `kit/sonar/go.*`, manifest `stack: rust` / `[rust, docs]`, a new `STACKS` entry each give a finding naming the stack and "no row"; a stack whose row says `not supported` that now exists gives a "not supported ... exists" finding | the same tree before the stack appears is clean; the shared `generic` stem and a stray file under `templates/` need no row | the finding text names `docs/SUPPORT.md` | verified |
| AC3 | unit | `::test_missing_file_fails`, `::test_file_without_a_table_fails`, `::test_unknown_status_fails`, `::test_empty_cell_fails` (2), `::test_row_with_too_few_or_too_many_cells_fails`, `::test_required_dimension_missing_fails`, `::test_row_claiming_support_for_a_stack_that_does_not_exist_fails`, `::test_dependabot_ecosystem_without_a_row_fails`, `::test_doc_without_a_link_fails` (2), `::test_missing_roadmap_fails`, `::test_unreadable_manifest_is_a_finding_not_a_crash` | each broken tree gives a finding naming the problem | status case-insensitive (`Supported` passes); a `not supported` row for an absent stack passes; header and separator lines are not rows | missing file, no table, bad status, empty cell, 4 or 6 cells, no `os` row, a `supported` and a `partial` claim with no template, missing ecosystem row, no link, broken YAML | verified |
| AC4 | integration | `::test_lint_catches_a_new_stack_directory_without_a_row`, `::test_lint_checks_the_matrix_only_in_a_factory_repository` | `factory lint` on a copy of the factory files exits 0; adding `templates/swift` (no row) exits 1 with `FAIL docs/SUPPORT.md:` naming `swift`; adding `templates/go` (row says `not supported`) exits 1 naming `go` | a root without `docs/ARCHITECTURE.md` is not checked; with it and no matrix, lint fails | n/a: same cases | verified |
| AC5 | manual | Confluence read-back | page "Factory generality: assumptions and roadmap" in space FACT has the ranked table and the seven topics; the FACT home page links it | n/a: a page | n/a: not testable offline | planned |
| AC6 | unit | `::test_the_proposed_extension_is_a_valid_unanswered_design_record`, `::test_no_decision_was_answered_by_this_item` | D-003 valid, design, proposed, answer fields null, three or more options, one recommended, "do nothing" among them | the recommended option is not the do-nothing one; D-001, D-002, D-003 all still proposed | n/a: a record the owner has not answered cannot be wrong that way; `validate_decision` is the failure source and is tested in `tests/test_decisions.py` | verified |
| AC7 | integration | full suite, ruff, `factory lint`, `factory sync --check .`, `factory verify`; manual `git diff origin/main -- docs/PROJECT.md` | all pass, charter diff empty | n/a | n/a | planned |

## Regression risk

* `checks.lint_factory` gains a check; `tests/test_lint.py` and others call it on synthetic roots with no `docs/`, so the
  check is skipped there. `test_command_exit_codes_and_output` and `test_registry_directory_fails_lint` must stay green.
* `tests/test_sonar_self.py`, `test_dependencies.py`, `test_findings.py` call `lint_factory(ROOT)` and demand no FAIL: the
  real matrix must be complete and correct, or they fail too.
* Adding `docs/SUPPORT.md` to `docs/` is covered by `lint_generic` (no Atlassian hostname in the file).
* A concurrent change by another agent that adds a kit stack file would make `test_real_matrix_is_current` fail until its
  row is added: intended.

## Untestable AC

AC5: Confluence cannot be read by an offline test. Proposed wording kept: verified by reading the pages back after
publishing (manual check below).

## Manual checks

* AC5: after publishing, read the new page and the FACT home page back with the Atlassian tools; the page contains the
  ranked table with seven topics; the home page has a link to it.
* AC7: `git diff origin/main --stat -- docs/PROJECT.md` prints nothing.

## Audit (after implementation)

Run 2026-10-07 with a script (`mutate.ps1`, kept outside the repo): for each mutation it reads the file, requires the
pattern to be present and the mutated text to differ, writes it, runs `tests/test_support.py` and `tests/test_lint.py`
(`uv run python -m pytest`), restores the original in a `finally`, and prints the failing tests. A control mutation whose
replacement equals the pattern printed `NOT-APPLIED (no change)`, so a mutation that does not take effect cannot pass as
killed. `git status` was clean afterwards. 32 mutations, 32 killed, 0 survivors.

| # | Mutation (file:line) | Killed by (test file `tests/test_support.py` unless noted) |
|---|----------------------|------------------------------------------------------------|
| 1 | support.py:171 stack without a row not reported | :160 `test_stack_from_a_file_without_a_row_fails` (all 4 paths) and 4 more |
| 2 | support.py:24 `SHARED_STEMS` empty (generic counted) | :103 `test_real_matrix_is_current`, :147, :160 (14 tests) |
| 3 | support.py:108 `templates/` ignored | :160 `[templates/go/main.go]`, :188 `[templates/go/main.go]`, :326 lint test |
| 4 | support.py:25 `kit/sonar` not scanned | :160 `[kit/sonar/go.properties]`, `[kit/sonar/go.yml]`, :188 `[kit/sonar/go.yml]` |
| 5 | support.py:25 `kit/ci` not scanned | :160 `[kit/ci/go.yml]`, :188 `[kit/ci/go.yml]` |
| 6 | support.py:126 manifest `stack:` values ignored | :169 both forms |
| 7 | support.py:125 `STACKS` constant ignored | :181 `test_stack_from_the_code_constant_needs_a_row` |
| 8 | support.py:179 claim without a stack not reported | :215 `test_row_claiming_support_for_a_stack_that_does_not_exist_fails` |
| 9 | support.py:179 only `supported` claims reported (`partial` dropped) | :215 (the `partial` iteration) |
| 10 | support.py:174 stale `not supported` row not reported | :188 (3 paths), :326 lint test |
| 11 | support.py:139 bad status not reported | :235 `test_unknown_status_fails` |
| 12 | support.py:147 empty "proven by" not reported | :251 `test_empty_cell_fails[proven by]` |
| 13 | support.py:147 empty "known gaps" not reported | :251 `test_empty_cell_fails[known gaps]` |
| 14 | support.py:162 missing required dimension not reported | :273 `test_required_dimension_missing_fails` |
| 15 | support.py:194 ecosystem without a row not reported | :280 `test_dependabot_ecosystem_without_a_row_fails` |
| 16 | support.py:189 `dependabot_templates` not read | :280 |
| 17 | support.py:209 missing link not reported | :287 `test_doc_without_a_link_fails` (both docs) |
| 18 | support.py:205 missing doc not reported | :293 `test_missing_roadmap_fails` |
| 19 | support.py:23 roadmap not required to link | :287 `[ROADMAP.md]`, :293 |
| 20 | support.py:228 wrong cell count not reported | :263 `test_row_with_too_few_or_too_many_cells_fails` |
| 21 | support.py:64 status read case sensitive | :241 `test_status_words_are_exact` |
| 22 | support.py:52 separator line read as a row | :103, :147 and 13 more |
| 23 | support.py:52 header line read as a row | :103, :147 and 13 more |
| 24 | support.py:63 backticks kept in the value | :103, :107, :129 and 14 more |
| 25 | support.py:225 file without a table not reported | :229 `test_file_without_a_table_fails` |
| 26 | support.py:80 list-valued manifest `stack` ignored | :169 `[stack1]` (the list form) |
| 27 | checks.py:330 `lint_factory` does not call the matrix check | :326 `test_lint_catches_a_new_stack_directory_without_a_row`, :346 |
| 28 | checks.py:323 matrix checked in every root | :346, `tests/test_lint.py::test_command_exit_codes_and_output`, `::test_registry_directory_fails_lint` |
| 29 | support.py:109 a file under `templates/` counted as a stack | :202 `test_stack_directories_are_the_only_templates_counted` |
| 30 | support.py:92 unreadable manifest not reported | :299 `test_unreadable_manifest_is_a_finding_not_a_crash` |
| 31 | D-003 front matter line 5 `status: accepted` | :360, :377 |
| 32 | D-003 front matter line 12 no "do nothing" option | :360 |

Rows not covered by a test and not mutated: `check_support` on a `SUPPORT.md` that is not valid UTF-8 (the `except
(OSError, UnicodeDecodeError)` branch) and a manifest that is not a mapping; both return a finding and are
fail-safe by construction. AC5 (Confluence) and the charter diff in AC7 are manual, below.
