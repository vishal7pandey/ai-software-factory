# FACT-48 — Generality audit and supported-today matrix

Status: draft · Risk: low · Jira: FACT-48
Created: 2026-10-07 · Slug: generality-audit-and-supported-today · Spec: spec.md

## Summary

Write the audit as `docs/SUPPORT.md` (a checked matrix), add one pure module `src/swfactory/support.py` that compares
the matrix with what the repository contains, wire it into `factory lint`, link it from the Treaty and the roadmap,
publish the ranked roadmap as a Confluence page, and propose one extension as decision record D-003 (never decided).
No behaviour of adopt, sync, verify or the skills changes.

**Size:** M (about one day: most of it is reading evidence and writing honest rows)

## Current state

* Stacks in code: `installer.STACKS` and `checks.STACKS` = python, node, docs, other (two copies of one tuple).
  Kit templates: `kit/ci/{python,node,generic}.yml`, `kit/sonar/{python,node}.{yml,properties}`,
  `kit/dependabot/{python,npm,github-actions}.yml`; `templates/python/` is the only `factory new` template.
  `installer.detect_stack` returns python (pyproject.toml), node (package.json), else other; never docs.
* Trackers: `installer.TRACKERS = (jira, github, none)`; nothing reads `kind: github`. Item ids are Jira keys
  (`JIRA_RE` in `verify.py`, `work.py`, `decisions.py`, `charter.py`) or `F-###`/`B-###` without `--jira`.
* GitHub only: `harden.repo_slug` rejects any host but github.com; `gh_api` runs `gh api`; `doctor`, `status` and
  `adopt` skip GitHub reads for a project without a github.com origin.
* `checks.TOOLS` makes `uv` required in `doctor` for every stack.
* Lint: `checks.lint_factory(root) = lint_skills + lint_manifest + lint_generic`; the lint tests build temporary roots
  with no `docs/`. `factory lint` calls it on `common.FACTORY_ROOT`. Run tests with `uv run python -m pytest -q`.
* The projects: ade and chatpid are `stack: python`, tracker jira, with a pnpm `frontend/`; both adopted the kit,
  synced it (ade PR 22, chatpid PR 23), enabled SonarCloud (ade 23, chatpid 24), applied the dependency loop (ade 25,
  chatpid 27) and the decision gate and charter (ade 45, chatpid 35).

## Approach

`support.py` is a pure function over a directory (no network, no `swfactory` imports except `Finding` from `checks` and
`STACKS`): parse the pipe tables of `docs/SUPPORT.md` into rows, enumerate the stacks the repository has, compare.
`checks.lint_factory` calls it when `docs/ARCHITECTURE.md` exists, so the existing synthetic-root lint tests are
untouched and a real factory repo cannot lose its matrix. The matrix is written from the evidence I read, row by row,
and says "tests only" or "nothing" where that is the truth. The decision record is scaffolded with
`factory decision new` and left `proposed`.

**Alternatives rejected**
- Matrix inside `ARCHITECTURE.md`: the Treaty is the stable contract; the matrix changes with every stack. Linked instead.
- A test only, no lint hook: CI would still run it, but `factory lint` is the command a contributor runs first.
- Generating the matrix from code: the interesting columns (proven by, gaps) are judgement, not derivable.
- Enumerating stacks only from `STACKS`: a template directory added without touching `STACKS` would slip through.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Write the failing tests: real matrix passes, synthetic trees for each failure, lint wiring, decision record, charter unchanged | `tests/test_support.py` | AC1-AC4, AC6, AC7 | `uv run python -m pytest tests/test_support.py -q` fails (module and files missing) |
| T2 | `check_support` and the table parser | `src/swfactory/support.py` | AC2, AC3 | synthetic-tree tests pass |
| T3 | Wire into `lint_factory` for a root with `docs/ARCHITECTURE.md` | `src/swfactory/checks.py` | AC4 | lint wiring tests pass; existing lint tests still pass |
| T4 | Write the matrix from the audit | `docs/SUPPORT.md` | AC1 | `check_support(ROOT) == []`; each row re-read against its evidence |
| T5 | Treaty section 3.13 and repo anatomy line, roadmap link and stale row, README pointer | `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `README.md` | AC1 | link test passes; `factory lint` OK |
| T6 | Proposed decision record D-003 | `docs/decisions/D-003-*.md` | AC6 | `verify` accepts it; record test passes |
| T7 | Mutation audit, then fill the test plan Audit section | `docs/work/FACT-48-*/test-plan.md` | AC2-AC4 | each mutation fails a named test |
| T8 | Confluence page, link from the FACT home, change-log row, Jira comments | Confluence, Jira | AC5 | pages read back |
| T9 | Full gate, PR, CI (including CodeQL result and sonarcloud), merge | - | AC7 | `gh pr checks --watch` all green |

## Data, API and migration impact

None for adopted projects: `support.py` is not in the kit manifest and `docs/SUPPORT.md` is not laid into projects.
`factory lint` in the factory repo gains one check. No CLI flag, schema or config change.

## Security and failure modes

Offline, reads files inside the repo root only (the root is `common.FACTORY_ROOT`), writes nothing. A malformed matrix
produces findings, never an exception (every parse step is guarded); an unreadable file is a finding. No secrets are
read; no `.env` is opened. Confluence and Jira text written here contains no token or hostname.

## Rollout and rollback

Merge to main; CI runs lint. Rollback: revert the PR. Point of no return: none. The Confluence page and the decision
record are additive.

## Risks and open points

* Another agent may add a kit stack file (FACT-40, sonar). The check would then require a row: expected, and the
  later merger adds it. Signal: lint failure naming the stack.
* The matrix could overstate. Mitigation: each row cites a project and PR or "tests only"; reviewer re-reads the
  evidence column against `ade`/`chatpid` files.
