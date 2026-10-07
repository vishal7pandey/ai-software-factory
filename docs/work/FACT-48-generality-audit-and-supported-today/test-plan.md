# FACT-48 — Test plan: Generality audit and supported-today matrix

Status: draft · Risk: low · Jira: FACT-48

Test framework and conventions found: pytest, `tests/test_*.py`, synthetic repository trees in `tmp_path`, the real
repository as `ROOT`; run all with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine).
Lint wiring is tested through `main(["lint"])` with `common.FACTORY_ROOT` monkeypatched, as `tests/test_lint.py` does.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | `tests/test_support.py::test_real_matrix_is_current`, `::test_real_matrix_has_the_rows_the_ticket_names`, `::test_real_matrix_is_honest_about_the_inert_github_tracker`, `::test_treaty_and_roadmap_link_the_matrix_and_the_page` | the real repo returns no problem; every named stack, tracker and dimension has a row; both docs link `SUPPORT.md` and name the page | the github tracker row says `not supported` and mentions that nothing reads it | n/a: negatives are AC2 and AC3 | written |
| AC2 | unit | `::test_stack_from_a_file_without_a_row_fails` (4 paths), `::test_stack_from_the_manifest_without_a_row_fails` (2 forms), `::test_stack_from_the_code_constant_needs_a_row` | `templates/go`, `kit/ci/go.yml`, `kit/sonar/go.*`, manifest `stack: rust` / `[rust, docs]`, a new `STACKS` entry each give a finding naming the stack and "no row" | the same tree before the stack appears is clean; the shared `generic` stem and a stray file under `templates/` need no row | the finding text names `docs/SUPPORT.md` | written |
| AC3 | unit | `::test_missing_file_fails`, `::test_file_without_a_table_fails`, `::test_unknown_status_fails`, `::test_empty_cell_fails` (2), `::test_row_with_too_few_or_too_many_cells_fails`, `::test_required_dimension_missing_fails`, `::test_row_claiming_support_for_a_stack_that_does_not_exist_fails`, `::test_dependabot_ecosystem_without_a_row_fails`, `::test_doc_without_a_link_fails` (2), `::test_missing_roadmap_fails`, `::test_unreadable_manifest_is_a_finding_not_a_crash` | each broken tree gives a finding naming the problem | status case-insensitive (`Supported` passes); a `not supported` row for an absent stack passes; header and separator lines are not rows | missing file, no table, bad status, empty cell, 4 or 6 cells, no `os` row, a `supported` and a `partial` claim with no template, missing ecosystem row, no link, broken YAML | written |
| AC4 | integration | `::test_lint_catches_a_new_stack_directory_without_a_row`, `::test_lint_checks_the_matrix_only_in_a_factory_repository` | `factory lint` on a copy of the factory files exits 0; adding `templates/go` exits 1 with `FAIL docs/SUPPORT.md:` naming `go` | a root without `docs/ARCHITECTURE.md` is not checked; with it and no matrix, lint fails | n/a: same cases | written |
| AC5 | manual | Confluence read-back | page "Factory generality: assumptions and roadmap" in space FACT has the ranked table and the seven topics; the FACT home page links it | n/a: a page | n/a: not testable offline | planned |
| AC6 | unit | `::test_the_proposed_extension_is_a_valid_unanswered_design_record`, `::test_no_decision_was_answered_by_this_item` | D-003 valid, design, proposed, answer fields null, three or more options, one recommended, "do nothing" among them | the recommended option is not the do-nothing one; D-001, D-002, D-003 all still proposed | n/a: a record the owner has not answered cannot be wrong that way; `validate_decision` is the failure source and is tested in `tests/test_decisions.py` | written |
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

<!-- Filled by factory-test in audit mode: per row, the real test file:line and how you confirmed it
fails when the behaviour is broken (mutation tried, or concrete reasoning). -->
