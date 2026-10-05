# FACT-19 — Delegated approvals as a first-class form

Status: in-review · Risk: medium · Jira: FACT-19
Created: 2026-10-05 · Slug: delegated-approvals-as-a-first-class · Spec: spec.md

## Summary

Add `--delegated "<who>"` to `factory approve`, accept and validate the `delegated` flag in `verify.py`, mark
delegated items in `factory status`, and rewrite the policy, AGENTS block, work README, workflow skill and
ARCHITECTURE text so delegation is a described, bounded exception. Size: M.

## Current state

- `src/swfactory/work.py:334-371` `cmd_approve(ident, kind, yes)` writes `{by: git user, at}`; `collect_status` (line ~270) builds the table row.
- `src/swfactory/commands/work.py:36-41` defines the `approve` parser.
- `src/swfactory/verify.py:168-185` validates `approvals.<kind>` as `{by, at}`; the file is copied standalone into projects.
- Text: `policies/autonomy.md` NEVER list line 28; `kit/AGENTS.block.md:22-23`; `kit/work-README.md:25-31`; `skills/factory-workflow/SKILL.md` steps 6, 7 and Never; `docs/ARCHITECTURE.md` 3.2 and 3.7.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run factory lint`, `uv run factory sync --check .`.

## Approach

`verify.py` gains `DELEGATED_SUFFIX = " (delegated to agent)"` and `is_delegated(record)` (flag true, or `by` ends with
the suffix); `validate_item` checks the flag. `cmd_approve` takes `delegated: str | None`; when given it builds `by`
from it and adds `delegated: true`. `collect_status` appends `(delegated)` to the status cell. Text changes are small and
generic. After editing `policies/`, `kit/`, `skills/` and `verify.py`, run `factory sync .`.

**Alternatives rejected**
- A `delegated_by` mapping next to `approvals` in `item.yaml`: bigger schema change for no gain.
- A `factory.yaml` delegation key: invents policy config nobody asked for yet (scope check).

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | `verify.py`: suffix constant, `is_delegated`, schema check of `delegated` | `src/swfactory/verify.py` | AC2 | verify tests |
| T2 | `approve --delegated`; parser flag | `src/swfactory/work.py`, `src/swfactory/commands/work.py` | AC1, AC5 | work tests |
| T3 | `status` marker | `src/swfactory/work.py` | AC3 | status test |
| T4 | Policy, AGENTS block, work README, workflow skill, ARCHITECTURE | `policies/autonomy.md`, `kit/AGENTS.block.md`, `kit/work-README.md`, `skills/factory-workflow/SKILL.md`, `docs/ARCHITECTURE.md` | AC4 | lint; re-read |
| T5 | `factory sync .`; full gate | managed copies | AC4 | `sync --check`, pytest, ruff, lint |

## Data, API and migration impact

New optional boolean `delegated` inside `approvals.<kind>`; existing items unchanged; the old hand-written form stays valid.
Adopted projects get the new `verify.py` on their next `factory sync`; an old `verify.py` would reject the unknown key
`delegated` only if it validates unknown keys (it does not), so mixed versions keep working.

## Security and failure modes

The ledger remains unlocked by design (ARCHITECTURE honesty clause). The new text restricts delegation to explicit,
recorded owner instructions and excludes production. A mistyped `--delegated` name is visible in the ledger and in status.

## Rollout and rollback

Merge the PR. Rollback: revert the commit and `factory sync .`.

## Risks and open points

- Wording must not read as permission to self-approve: the policy requires an explicit recorded instruction naming the gates.
- Risk is medium because the change touches the approval gate's text and the verify schema.
