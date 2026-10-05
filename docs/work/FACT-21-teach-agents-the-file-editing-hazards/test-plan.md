# FACT-21 — Test plan: Teach agents the file-editing hazards

Status: in-review · Risk: low · Jira: FACT-21

Test framework and conventions found: pytest, tests in `tests/` named `test_<area>.py`, `tmp_path` fixtures; run everything with `uv run python -m pytest -q` (the `pytest.exe` launcher is blocked on this machine). Skill lint tests are in `tests/test_lint.py`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_lint.py::test_repo_implement_skill_carries_the_editing_rules | the real `skills/factory-implement/SKILL.md` contains both rules and lints clean | body stays within the 150-line cap (lint) | n/a: covered by AC2 | verified |
| AC2 | unit | tests/test_lint.py::test_implement_skill_must_carry_editing_rules | a factory-implement skill with both rules passes | a skill named `factory-demo` without the rules is not subject to the rule | skill without the inline-script rule fails; skill without `git add -A` rule fails; each message names the rule | verified |
| AC3 | integration | `uv run factory sync --check .` (CI step) | exit 0 after sync | n/a: in sync or not | stale copy -> exit 1 (existing sync tests) | verified |
| AC4 | integration | `uv run factory lint` (CI step) | passes | n/a | n/a: existing generic-content lint tests cover forbidden content | verified |

## Regression risk

All other skills and `tests/test_lint.py` helpers (`skill_text`, `put_skill`) use the name `factory-demo`, which must stay exempt. `tests/test_install.py` syncs the real skills into temporary projects and must stay green with the longer skill.

## Untestable AC

None.

## Manual checks

None.

## Audit (after implementation)

Each mutation applied temporarily, tests and `factory lint` run, then restored.

| AC | Real test(s) | Broken on purpose | Result |
|----|--------------|-------------------|--------|
| AC1 | `tests/test_lint.py:196` `test_repo_implement_skill_carries_the_editing_rules` | `git add -A` replaced by other words in `skills/factory-implement/SKILL.md` | test fails; `factory lint` prints `missing required rule: explicit-staging rule` |
| AC2 | `tests/test_lint.py:178` `test_implement_skill_must_carry_editing_rules` | the check loop in `checks.py` disabled (`if False:`) | test fails (the missing-rule cases no longer fail) |
| AC2 | same | inline-script pattern changed to a string that never matches | `factory lint` fails on the real skill naming the file-editing rule |
| AC3 | `uv run factory sync --check .` | n/a: the stale-copy case is covered by the existing sync tests in `tests/test_install.py` | `factory sync .` updated 3 files; `--check` then reports in sync |
| AC4 | `uv run factory lint` | n/a | OK |
