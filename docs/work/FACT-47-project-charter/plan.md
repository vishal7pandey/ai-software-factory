# FACT-47 — Project charter

Status: draft · Risk: medium · Jira: FACT-47
Created: 2026-10-07 · Slug: project-charter · Spec: spec.md

## Summary

Add `docs/PROJECT.md` (kit template, create mode) and `swfactory/charter.py`: a pure parser and validator, an offline
criterion evaluator, and the approval-state logic that ties the file to a FACT-46 `charter` decision record by
`subject` and sha256. Wire it into `doctor`, `status` and `feature start`, extend `decide` and `decision new` for the
`charter` type, update the skill, policy and Treaty, and add the factory's own proposed charter.

**Size:** M.

## Current state

* FACT-46 (merged): `decisions.py` (`load_records`, `find_record`, `cmd_decide`, `cmd_new`, `placeholder_marker`),
  `verify.py` (`validate_decision`, `split_front_matter`, `DECISION_TYPES`, `ID_RE`, `JIRA_RE`, `STATUSES`,
  `load_item`), `checks.py` (`Finding`, `check_decisions`), `work.py` (`cmd_status`, `cmd_start`), the manifest
  `files` and `templates` sections, Treaty 3.11.
* The `charter` type exists but has no meaning beyond the generic record; no `subject` is required for it yet.
* Commands: `uv run python -m pytest -q`, `uv run ruff check . && uv run ruff format --check .`,
  `uv run python -m swfactory.cli lint | sync --check . | verify`.

## Approach

* **`charter.py` (new).** `parse_charter(text)` returns `(meta, body, problems)` and never raises;
  `validate_charter(meta, body)` is pure. `evaluate(criterion, root, jira_status)` returns `met` / `not met` /
  `unknown` for the four check kinds, reading only inside the project (inline `os.path.realpath` + `startswith`).
  `charter_state(root)` returns a `CharterState` (`absent`, `template`, `invalid`, `unapproved`, `changed`,
  `approved`, with detail, mode, decision id) using `decisions.load_records` and the record's `subject_sha256`.
  `status_lines(root, jira_status)` and `doctor_finding(root)` format the output.
* **Gate.** `verify._decision_type_fields` requires `subject: docs/PROJECT.md` for type `charter`. `decisions.cmd_decide`
  calls a pre-accept check for charters (lazy import of `charter`): the file must be a valid charter naming the record.
  `cmd_new` scaffolds `--type charter` with the subject and a single option; rejecting is how an owner sends it back.
* **Wiring.** `checks.check_charter` into both `doctor` branches; `work.cmd_status` prints the lines after the decisions
  block; `work.cmd_start` warns for features in maintenance mode.
* **Kit.** `kit/charter/PROJECT.md` (unfilled marker, placeholders, the maintenance definition), manifest `files` entry
  (`create`), `templates.charter`; `lint_manifest` already checks `templates`.
* **Text.** `factory-spec` step to check proposed work against the charter; one line in `factory-workflow`; autonomy
  policy; Treaty 3.1 layout, 3.7 rows, new 3.12; the factory's own `AGENTS.block` unchanged except one sentence.
* **Dogfood.** `docs/PROJECT.md` of the factory and `D-002` (type charter, proposed).

**Alternatives rejected**
- Approval stamped inside `PROJECT.md`: a second ledger beside the decision records, editable without a trace.
- Blocking `feature start` in maintenance mode: the owner said proceeding deliberately must stay possible.
- Free-text criteria checked by an LLM: not deterministic, not offline.
- A Jira reader in the CLI: the factory has no Jira client (ROADMAP); the lookup is injected, default unknown.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing tests first | tests/test_charter.py | AC1-AC7 | red before T2-T6 |
| T2 | Parser, validator, evaluator | src/swfactory/charter.py, verify.py (path helper) | AC2, AC3 | validator and evaluator tests |
| T3 | Approval state, gate in decide/new, verify subject rule | charter.py, decisions.py, verify.py | AC2, AC6 | state and decide tests |
| T4 | doctor, status, feature start | checks.py, commands/doctor.py, work.py | AC2, AC3, AC4 | command tests |
| T5 | Template, manifest, adopt/sync | kit/charter/PROJECT.md, kit/manifest.yaml | AC1 | adopt and sync tests |
| T6 | Skill, policy, Treaty 3.12 | skills/factory-spec, factory-workflow, policies/autonomy.md, docs/ARCHITECTURE.md | AC7 | contract tests, lint |
| T7 | Factory charter and proposed record; `factory sync .` | docs/PROJECT.md, docs/decisions/D-002-*.md, .factory, .claude, .github | AC5 | doctor, verify |
| T8 | Full suite, lint, ruff, PR, CI, merge | PR | all | `gh pr checks --watch` |

## Data, API and migration impact

New file `docs/PROJECT.md` (create mode) in adopted projects on `sync`; the validator now requires `subject` on a
`charter` record (none exists yet in any project). No change to `item.yaml` or `factory.yaml`. Reversible.

## Security and failure modes

Reads files inside the project only (realpath guard); no network; `jira` references go through an injected function.
A broken charter shows as a doctor WARN, never a crash or a failure. The approval stays a ledger like `approve`:
the lock is GitHub review of `docs/PROJECT.md` and `docs/decisions/`.

## Rollout and rollback

Merge; projects pick it up on `sync` (template file, `verify.py`, skills). Rollback: revert the PR.

## Risks and open points

- `doctor` gains a WARN for every project without a charter until the owner approves one (intended).
- A charter edit after approval needs a new record (strict by design); a typo fix costs one decision.
