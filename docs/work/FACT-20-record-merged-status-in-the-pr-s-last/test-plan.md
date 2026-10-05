# FACT-20 — Test plan: Record merged status in the PR's last commit

Status: in-review · Risk: low · Jira: FACT-20

Test framework and conventions found: pytest, `project` fixture, `run(...)` and `set_status(...)` helpers in `tests/test_work.py`; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine).

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_work.py::test_merged_is_complete_without_environments | no environments: `status` omits the merged item, `--all` lists it as complete (next: "complete (no environments to release to)") | an item at `done` is still omitted by default and listed by `--all` | an item at `in-review` is still listed by default | verified |
| AC2 | integration | tests/test_work.py::test_merged_routes_to_release_with_an_environment | `environments: {dev: x}`: merged item listed by default with `factory-release` | an environment key present but null does not count | n/a: covered by AC1 | verified |
| AC3 | integration | tests/test_work.py::test_next_prompt_per_status (updated), ::test_next_merged_without_environments | `next` on merged with no environments prints "Nothing to do"; in-review hint names the last-commit rule | released with no environments still routes to release (the rule is only for `merged`) | n/a: no invalid input | verified |
| AC4 | manual | reading; `factory lint`; `factory sync --check .` | n/a | n/a | n/a: wording | verified |
| AC5 | manual | `uv run factory status --all` on the branch | the five merged items show `merged` | the item under review (this one) shows `in-review` until the last commit | n/a | verified |
| AC6 | manual | `python .factory/verify.py` on a branch whose item is at `merged` with an open PR | verify OK | n/a | n/a | verified |

## Regression risk

`test_next_prompt_per_status` expects `merged -> factory-release` in a project without any `environments` key; it must configure one for `merged`/`released` rows. Other `status` tests (`test_status_table`) rely on `done` being hidden by default and must stay green.

## Untestable AC

None; AC4 to AC6 are checked by reading and by running the tools, recorded below.

## Manual checks

AC4: read the four documents. AC5: `uv run factory status --all`. AC6: `python .factory/verify.py --branch feature/fact-20-record-merged-status-in-the-pr-s-last` with this item at `merged` and the PR open.

## Audit (after implementation)

Each mutation applied temporarily to `src/swfactory/work.py` (each confirmed to have changed the file), the `-k "merged or next_prompt or status_table"` tests run, then restored (byte-identical).

| AC | Real test(s) | Broken on purpose | Result |
|----|--------------|-------------------|--------|
| AC1 | `tests/test_work.py:613` `test_merged_is_complete_without_environments` | `environments_configured` always True; then the default-listing filter `if closed and not show_all` disabled | fails each time |
| AC2 | `tests/test_work.py:630` `test_merged_routes_to_release_with_an_environment`, `:575` `test_next_prompt_per_status[merged]` | `environments_configured` always False | both fail |
| AC3 | `tests/test_work.py:601` `test_next_merged_without_environments`; `:575` `[in-review]` | the `merged` shortcut in `next_step` disabled; the in-review hint reworded to the old text | each fails |
| AC4 | manual | n/a | four documents carry the rule; `factory lint` OK; `factory sync --check .` in sync after `factory sync .` |
| AC5 | manual | n/a | `uv run factory status --all` lists FACT-12, 16, 18, 19, 21 as `merged` ("complete (no environments to release to)") |
| AC6 | manual | n/a | `python .factory/verify.py --branch <this branch>` OK with this item at `merged` and the PR open (recorded in the PR) |
