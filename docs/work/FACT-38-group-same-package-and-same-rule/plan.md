# FACT-38 — Group same-package and same-rule findings into one issue

Status: draft · Risk: medium · Jira: FACT-38
Created: 2026-10-05 · Slug: group-same-package-and-same-rule · Spec: spec.md

## Summary

Replace the "one issue per finding" rule with a grouping rule in `skills/factory-findings/SKILL.md` and `policies/findings.md`, align
`factory-workflow`, `factory-release` and the Treaty, and update `tests/test_findings.py`: the walkthrough helper (`Finding`,
`normalise`, `FakeJira`, `sweep`, `close`, `dismiss`, `Report`) models groups, and new tests pin that an open alert blocks a group's
Done, that two runs create one issue per group, that a new alert joins an open group, and that the cap counts issues. No `src/`
change. Managed copies are refreshed with `factory sync .`. **Size:** M.

## Current state

- `skills/factory-findings/SKILL.md` (58 lines): step 3 says "One issue per finding. Do not merge..."; step 5 re-queries "the single
  alert"; step 7 reports counts per source and severity; Output and Definition of done say one issue per finding.
- `policies/findings.md`: closure rule opens with "A finding is tracked as one Jira Bug"; batch limits say "at most 10 issues".
- `skills/factory-workflow/SKILL.md` line 31 (route row: "one Jira Bug each") and line 70 (closure rule); `skills/factory-release/SKILL.md`
  step 8 and the Never list. `kit/AGENTS.block.md` only lists the policies; no change needed. `docs/ARCHITECTURE.md` line 183 describes the skill.
- `tests/test_findings.py`: 15 tests; the helper creates one issue per alert; fixtures `cs()` and `dep()` use one fixed rule, path, package and
  manifest for every alert, so they must take distinct defaults or every alert would group.
- The repo adopts itself: `.claude/skills`, `.github/skills`, `.factory/policies` are managed copies; `factory sync .` refreshes them and
  `tests/test_integration.py::test_factory_repo_is_in_sync_with_its_kit` fails until it is run.
- Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m swfactory.cli lint`,
  `uv run python -m swfactory.cli sync --check .`.

## Approach

Keep the label format and the per-alert re-query; add a group lookup. In the skill's step 3 the order is: search Jira for the alert's own
label (any status; found means tracked or reopen, as today); if not found, look for an open group (label `finding`, not Done, summary exactly
equal to the group summary) and add label plus comment; otherwise create a new issue whose summary is the group summary. Step 5 re-queries every
`finding-` label of the issue and moves to Done only when all are `fixed` (or dismissed with recorded approval). Step 7 reports alerts and issues.
The policy holds the rules (grouping conditions, module definition, Done on all alerts, join, cap on issues); the skill holds the procedure.

The helper in the test file mirrors that: `Finding` gains `group` (the group summary, `None` for secrets) and `location`; `sweep(gh, jira, grouping=True)`
joins an open group or creates; `Report` gains alerts and issues counts; `close` re-queries every alert label of the issue; `dismiss` records
approval on the issue and sets Done only when every other alert is settled. Fixtures get distinct default rules, files and packages so the old
one-issue-per-alert tests stay unchanged, and new tests build groups on purpose.

**Alternatives rejected**
- A second label per group (`finding-group-...`): stable lookup, but the ticket decision says labels are `finding-<source>-<id>`, and
  paths and package names are awkward in labels. The summary is already human-readable and unique per group.
- Reopening a Done group for a new alert: makes "Done" untrue about the alerts the issue first carried; a new issue is cheaper and clearer.
- Grouping by top-level folder or language package: needs language knowledge; the directory needs none.
- Changing `checks.py` to pin the phrases: not needed; tests pin them.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Tests first: contract test for grouping text (skill, policy, workflow, release, old sentence gone); update helper (group key, join, counts, all-alerts close, dismissal-aware close); walkthrough tests for AC2 to AC5; see them fail against the old text | `tests/test_findings.py` | AC1 to AC5 | `uv run python -m pytest tests/test_findings.py -q` fails for the right reasons |
| T2 | Policy: grouping section, module definition, closure on all alerts, join and Done-group rule, cap counts issues | `policies/findings.md` | AC1, AC3 to AC5 | tests pass; `factory lint` |
| T3 | Skill: steps 3, 5, 7, description, Output, Definition of done, Never; body <= 150 lines | `skills/factory-findings/SKILL.md` | AC1 to AC5 | `factory lint`; tests |
| T4 | Align `factory-workflow` (route row, closure rule), `factory-release` (step 8, Never), Treaty line | `skills/factory-workflow/SKILL.md`, `skills/factory-release/SKILL.md`, `docs/ARCHITECTURE.md` | AC1 | tests |
| T5 | Refresh managed copies | `.claude/skills/`, `.github/skills/`, `.factory/policies/` via `factory sync .` | AC6 | `factory sync --check .` exits 0 |
| T6 | Full gate, mutation audit recorded in test-plan.md | repo | AC1 to AC6 | lint, ruff, full pytest, audit table |

## Data, API and migration impact

None for the factory. Adopted projects receive the changed skill and policy on their next `factory sync`; a project that edited them sees a conflict
reported, as for any managed file. No label or Jira schema change: groups are one issue with several existing-format labels. Existing per-alert issues
stay as they are.

## Security and failure modes

The closure rule gets stricter in effect, not weaker: every alert of a group is re-queried and any open alert blocks Done. The risk is a group
closed by mistake because one alert was not re-queried; the walkthrough pins one open alert among fixed ones, and a dismissed alert without
approval. Alert text stays data. A join comment must not contain a secret value (secrets are never grouped anyway).

## Rollout and rollback

Merge the PR, then adopted projects run `factory sync`. Rollback: revert the commit; projects keep whatever issues were filed, which stay valid
(a group issue is just an issue with several labels).

## Risks and open points

- A markdown rule is only as good as the agent reading it; the end-to-end drill (FACT-37) is the real proof.
- Summary search in Jira is fuzzy; the skill tells the agent to compare returned summaries exactly. A mismatch would create a second group,
  which is harmless duplication, not a wrong closure.
