# FACT-46 — Owner decisions gate

Status: draft · Risk: medium · Jira: FACT-46
Created: 2026-10-07 · Slug: owner-decisions-gate · Spec: spec.md

## Summary

Add decision records (`docs/decisions/D-<n>-<slug>.md`, Markdown plus YAML front matter) with one pure validator in
the standalone `verify.py`, a new `swfactory/decisions.py` (load, list, `decide`, `decision new`, inbox), three
commands (`decide`, `decision new`, `inbox`), a waiting block in `status` and WARN findings in `doctor`, a kit
template, and the skill, policy, AGENTS-block and Treaty text that make dismissals and owner choices go through the
record.

**Size:** M.

## Current state

* `src/swfactory/verify.py`: standalone gate; `check_project` runs rules 1-3, `warn_project` the warnings; it
  already has `_norm_dates`, `DELEGATED_SUFFIX`, `is_delegated`, `UNFILLED`, `CLARIFY`, `open_marker`, `JIRA_RE`.
* `src/swfactory/work.py`: `cmd_approve` (refuses templates via `_doc_ok`, stamps `common.git_user_name`, `--yes`,
  non-terminal refusal, delegated form), `cmd_status` (table, then the dependency summary from `deps.for_project`).
* `src/swfactory/checks.py`: `Finding`, `check_dependencies`; `commands/doctor.py` builds the list in two branches.
* `src/swfactory/installer.py`: `_load_registry()` (private), `_install` / `_plan_item` create-mode handling,
  `kit/manifest.yaml` (`files`, `dirs`, `work_templates`); `checks.lint_manifest` validates the manifest;
  `checks._APPROVE` makes lint fail a skill line that instructs `factory approve`.
* Tests: `tests/test_work.py` (fixtures `factory_root`, `project`, `run`), `tests/test_verify.py`,
  `tests/test_findings.py` (contract style), `tests/test_registry.py`, `tests/test_doctor.py`, `tests/test_lint.py`.
  Commands: `uv run python -m pytest -q`, `uv run ruff check . && uv run ruff format --check .`,
  `uv run python -m swfactory.cli lint`, `uv run python -m swfactory.cli sync --check .`,
  `uv run python -m swfactory.cli verify`.

## Approach

* **One validator, in `verify.py`.** `split_front_matter`, `validate_decision(meta, filename)` (pure, returns a list of
  problems) and `check_decisions(root)` live in the standalone file because CI runs it in adopted projects with no
  `swfactory`; `swfactory/decisions.py` imports them, so there is one implementation. `check_project` adds
  `check_decisions` (Treaty rule 6). Only files named `D-<n>-*.md` are records; ADRs and the template are ignored.
* **`decisions.py`** holds `Record` (path, meta, body, raw text, problems), `load_records(root)` (sorted by number,
  symlinks that leave the folder skipped with an inline `os.path.realpath` + `startswith` guard), age and listing
  helpers (`inbox_lines`), `cmd_decide`, `cmd_new` and `cmd_inbox`. `today` is injectable so output is deterministic.
* **`decide`** mirrors `cmd_approve`: find, check decidable (valid, `proposed`, no placeholder), pick the option
  (recommended by default, `--option N` 1-based), confirm on a tty or demand `--yes`, stamp, rewrite the front matter
  in the canonical key order with `common.yaml_text`, keep the body. `subject` (optional file) gets its sha256 stamped
  on accept. `--delegated` is refused for the never-delegated types (`verify.NEVER_DELEGATED`).
* **Wiring.** `commands/decide.py` registers `decide`, `decision new`, `inbox`; `cli.COMMAND_MODULES` gains it.
  `work.cmd_status` prints the block after the table; `checks.check_decisions` feeds `doctor` in both branches.
  `installer.registry_paths()` is the public read of the registry's `paths` for `inbox`.
* **Kit.** `kit/decisions/TEMPLATE.md` (`create` to `docs/decisions/TEMPLATE.md`); a manifest `templates.decision`
  key the CLI reads for the body; `lint_manifest` checks it. No managed-mode change, so existing projects only gain
  one create-mode file on `sync`.
* **Text.** `skills/factory-findings` step 6 and the Dismissal gate in `policies/findings.md` become the record flow;
  one or two lines each in spec, plan, diagnose and workflow; `autonomy.md`, `kit/AGENTS.block.md`, the Treaty
  (3.1 layout, 3.7 table, new 3.11) and `checks._APPROVE` (also `factory decide`).
* **Dogfood.** One real record in this repo: `D-001`, the delegation limit of `decide`, left `proposed` for the owner.

**Alternatives rejected**
- Decision ids as Jira keys: couples the gate to a tracker the factory does not require.
- A separate validator module imported by `verify.py`: breaks the standalone copy that CI runs in projects.
- Storing decisions in `item.yaml`: they are not work items and outlive them.
- A decisions database or tracker comments: not in git, not offline, not diffable.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing tests first: validator, verify rules, decide, new, listings, inbox | tests/test_decisions.py, tests/test_verify.py | AC1-AC4, AC6, AC7 | run before T2: ImportError / failures |
| T2 | `split_front_matter`, `validate_decision`, `check_decisions`, hook in `check_project` | src/swfactory/verify.py | AC4 | `-k decision` in test_verify |
| T3 | `decisions.py`: records, listing, `decide`, `decision new` | src/swfactory/decisions.py | AC1, AC6, AC7 | test_decisions |
| T4 | CLI wiring; `registry_paths`; `inbox` | src/swfactory/commands/decide.py, cli.py, installer.py | AC3, AC6 | test_decisions inbox tests |
| T5 | `status` block and `doctor` findings | src/swfactory/work.py, checks.py, commands/doctor.py | AC2 | test_decisions, test_doctor |
| T6 | Template, manifest key, lint check | kit/decisions/TEMPLATE.md, kit/manifest.yaml, checks.py | AC7, AC8 | test_decisions, test_lint, test_install |
| T7 | Skills, policies, AGENTS block, lint `_APPROVE` extension | skills/*, policies/*, kit/AGENTS.block.md, checks.py | AC5, AC6 | test_decisions contract tests, test_lint |
| T8 | Treaty 3.11 and tables | docs/ARCHITECTURE.md | AC8 | test pins the section |
| T9 | `factory sync .`; dogfood record D-001; full suite, lint, verify, ruff | .factory/, .claude/, .github/, docs/decisions/ | all | all checks green |
| T10 | PR, CI (all jobs), Jira, changelog, merge | PR | all | `gh pr checks --watch` |

## Data, API and migration impact

New files only (records, a create-mode template). New commands: `decide`, `decision new`, `inbox`. `verify.py`
gains rule 6: a project that already has files named `D-<n>-*.md` in `docs/decisions` would be checked (none known).
No schema change to `item.yaml` or `factory.yaml`. Reversible: remove the commands and the rule.

## Security and failure modes

No network, no secrets. `decide` writes one file chosen by id lookup among the folder's own files; `decision new`
writes `docs/decisions/D-<n>-<slug>.md` with the slug from `common.slugify` and a realpath containment check.
Failure shows as `error: ...` and exit 1 with the file unchanged. The ledger-not-lock honesty clause applies: the
lock is GitHub review; the docs say an agent never runs `decide` and CODEOWNERS can cover `docs/decisions/`.

## Rollout and rollback

Merge, then each project picks it up on `factory sync` (new `verify.py`, skills, policies, one create-mode file).
Rollback: revert the PR; records already written stay valid markdown.

## Risks and open points

- Sonar S3776 (cognitive complexity) on the validator: split into helpers (done in the design).
- Windows: records are written with `\n`; tests use `tmp_path` and no symlink rights are assumed (the symlink test skips).
- The owner may overrule the delegation limit: D-001 captures it.
