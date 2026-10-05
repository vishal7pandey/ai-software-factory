# FACT-34 — Findings loop policy and skill

Status: draft · Risk: medium · Jira: FACT-34
Created: 2026-10-05 · Slug: findings-loop-policy-and-skill · Spec: spec.md

## Summary

Add `policies/findings.md` and `skills/factory-findings/SKILL.md`, route to the skill from `factory-workflow`, state the closure rule in
`factory-workflow` and `factory-release`, and add `tests/test_findings.py` that pins the endpoints and label format found in the skill text,
walks the loop with a fake `gh` and a fake Jira, and proves `factory sync` copies both files. No CLI or `src/` change. Size: M.

## Current state

- `kit/manifest.yaml`: `skills: all` and `dirs: [{src: policies, ...managed}]`, so a new skill dir and a new policy file are laid into projects with no manifest edit.
- `src/swfactory/checks.py`: `lint_skills` enforces name, "Use when", 1024-char description, body <= 150 lines, the six sections in order, no `factory approve` instruction, links to `references/`, and that every `factory-*` name mentioned is a real skill. `REQUIRED_RULES` pins phrases for `factory-implement` only.
- `skills/factory-workflow/SKILL.md`: route tables (entry point, status), policies list in Inputs, Never list. `skills/factory-release/SKILL.md`: step 8 closes Jira.
- `policies/autonomy.md`: ASK FIRST list has no explicit dismissal line. `kit/AGENTS.block.md` line 11 lists the policies. `docs/ARCHITECTURE.md` 2 and 3.4 list the policies and the V1 skills.
- The repo adopts itself: `.claude/skills`, `.github/skills`, `.factory/policies` are managed copies, hashes in `.factory/factory.yaml`; `factory sync .` refreshes them.
- Tests: `tests/test_install.py` runs `adopt`/`sync` against a fixture factory root; `tests/test_lint.py` has `put_skill`/`reasons` helpers. Run all: `uv run python -m pytest -q`; also `uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m swfactory.cli lint`, `... sync --check .`.

## Approach

Rules that must not drift live in the policy; the skill is the procedure and repeats only the exact commands and label format. Pinning is by tests
(not by `checks.py`, to stay clear of FACT-33): one test reads the real `SKILL.md` and asserts the three endpoints, the PR form, the label format and the
policy's reasons; the walkthrough helper (a few pure functions in the test file) parses its endpoints out of the skill text and feeds them to a fake `gh`
that raises on any other call, so changing an endpoint in the skill breaks the walkthrough as well. The helper encodes the five rules as small functions
(`label`, `sweep`, `close`, `dismiss`) and the tests exercise them with the same fake data twice.
The real-repo sync test copies the real `skills/` and `policies/` into a scratch project via `installer` as `test_install.py` does (against the real factory root).

**Alternatives rejected**
- Add the endpoints and label to `REQUIRED_RULES` in `checks.py`: gives `factory lint` the check, but `checks.py` is likely touched by FACT-33 (doctor); a merge conflict for no gain, since the test suite runs in CI anyway.
- A Python module in `src/swfactory` implementing the loop: the factory CLI makes no network calls (Treaty 3.7) and the skill must run with git and `gh` only.
- One Jira issue per group of identical findings: breaks the one-label-per-alert idempotency; grouping is left to the human.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Policy: closure rule, dismissal gate, reasons and API mapping, batch limits, enable commands | `policies/findings.md` | AC1, AC4 | re-read; `factory lint` |
| T2 | Skill: steps 1 to 5, exact endpoints and label, Never list; <= 150 lines | `skills/factory-findings/SKILL.md` | AC1, AC4 | `factory lint` |
| T3 | Routing and closure rule; policy listed in the AGENTS block, autonomy, Treaty | `skills/factory-workflow/SKILL.md`, `skills/factory-release/SKILL.md`, `policies/autonomy.md`, `kit/AGENTS.block.md`, `AGENTS.md` (block), `docs/ARCHITECTURE.md` | AC1 | `factory lint`; test in T4 |
| T4 | Tests: repo contract (files exist, lint clean, routed, closure rule in both skills, manifest covers them) and drift pins (endpoints, label format, reasons) | `tests/test_findings.py` | AC1, AC4 | pytest |
| T5 | Tests: scripted walkthrough with fake gh and fake Jira (idempotent sweep, closure, dismissal gate, batch cap, reopened) | `tests/test_findings.py` | AC2 | pytest |
| T6 | Test: sync into a scratch adopted project; then `factory sync .` for the repo's own managed copies | `tests/test_findings.py`, `.claude/skills/`, `.github/skills/`, `.factory/` | AC3 | pytest; `factory sync --check .` |
| T7 | Full local gate, mutation audit recorded in test-plan.md | repo | AC1 to AC4 | lint, ruff, pytest, audit table |

## Data, API and migration impact

None for the factory. Adopted projects get two new managed files on their next `factory sync` (the `.factory/policies/findings.md` file and a
`factory-findings` directory per skill target); a project that edited nothing sees no conflict. The commands in the policy call the GitHub REST API
through `gh`; they are documentation, never run by the factory.

## Security and failure modes

The skill moves security alert states, so: dismissal needs a human yes in the conversation, the allowed reasons are a closed list, secret values are
never copied into Jira, and alert text is treated as data (it can contain attacker-controlled strings such as file names and rule messages). Failure
modes (scanner not enabled, Jira down, more alerts than the batch limit, issue already Done with the alert open again) are specified in the skill and exercised in the walkthrough where they are rules.

## Rollout and rollback

Merge the PR, then each adopted project runs `factory sync`. Rollback: revert the commit; projects that already synced keep the extra files until
the next sync removes nothing (sync never deletes), so a project may delete them by hand.

## Risks and open points

- Wording in a markdown skill cannot be proven to be obeyed by an agent; the drill (FACT-37) is the proof, and until then the tests only pin the text and the rules as functions.
- Dependabot and secret-scanning dismissal values differ from the code-scanning ones; if GitHub renames a value the policy table is stale. Signal: the drill or a real dismissal returns a 422.
- `kit/AGENTS.block.md` and `docs/ARCHITECTURE.md` may be edited by FACT-33 as well; the edits here are single lines to keep a merge trivial.
