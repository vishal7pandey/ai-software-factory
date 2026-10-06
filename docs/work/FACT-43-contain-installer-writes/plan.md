# FACT-43 — Contain installer writes

Status: draft · Risk: low · Jira: FACT-43 (also FACT-44, FACT-45)
Created: 2026-10-06 · Slug: contain-installer-writes · Spec: spec.md

## Summary

Resolve every installer destination with `os.path.realpath` and require it to lie strictly under the realpath of
its root, inline at each point of use, rejecting with "outside the project" before the first write. Covers the
three Sonar write sites (`_save_registry`, `new_project` twice) and the manifest/skill-target writes in `_install`.

**Size:** S.

## Current state

* `installer.py`: `_plan_item` builds `root / item.dest` for every manifest item (files, dirs, skills) and reads it;
  `_install` writes `root / a.dest`; `new_project` writes `target.joinpath(<template parts>)`; `_save_registry`
  dumps the registry then reads it back to prepend the header comment.
* `common.dump_yaml` writes yaml; `common.registry_path()` resolves `FACTORY_REGISTRY` or `~/.factory/registry.yaml`.
* Tests: `tests/test_install.py` has a fixture factory root (`factory`), `proj`, `run(...)`, `snapshot(...)`.
  Commands: `uv run python -m pytest -q`, `uv run python -m ruff check . && ... format --check .`, `uv run factory lint`,
  `uv run python -m swfactory.cli sync --check .`.

## Approach

Inline check, no helper (Sonar and CodeQL recognise the pattern at the point of use):
`base = os.path.realpath(root)`; `cand = os.path.realpath(os.path.join(base, dest))`; reject unless
`cand.startswith(base + os.sep)`. An absolute `dest` or a `..` makes `cand` leave `base`; a symlink that leaves the
project does too. `_plan_item` checks every item during planning (all items are planned before any write, so a bad
one aborts the whole run, also for `--dry-run`/`--check`); `_install` re-checks right before the write and writes
to the resolved path. `new_project` checks the project dir against its parent and every template path against the
project before `mkdir`/write. `_save_registry` checks the registry file against its own directory, and builds the
text in memory (`common.yaml_text`) so it is written once, with the header comment kept.

**Alternatives rejected**
- A shared `safe_join()` helper: scanners do not follow the sanitiser through a call as reliably as an inline check.
- Rejecting only `..` / absolute strings: misses symlink escapes.
- Dismissing the Sonar issues: forbidden without the owner's yes; the path property is real.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | failing regression tests (11 fail, 1 skipped without symlink rights) | tests/test_install.py | AC1, AC2, AC3 | `-k "outside or climbs or symlink"`: `DID NOT RAISE FactoryError` (done) |
| T2 | containment in `_plan_item` and `_install` | src/swfactory/installer.py | AC1, AC2 | the manifest, dir and skill-target tests pass |
| T3 | containment in `new_project` | src/swfactory/installer.py | AC3 | the `new` test passes |
| T4 | registry: containment, single write (`common.yaml_text`) | src/swfactory/installer.py, src/swfactory/common.py | AC3 | registry tests (existing header test + new symlink test) |
| T5 | document the rule | docs/ARCHITECTURE.md | AC4 | section 3.1 "Containment" |
| T6 | PR, scan, closure | PR, Sonar API | AC4 | `gh pr checks --watch`; Sonar issues closed after the push scan on main |

## Data, API and migration impact

None. New error text "destination '<x>' is outside the project <root>" (exit 1). No schema or CLI change.

## Security and failure modes

Removes path escape from manifest entries, `skill_targets`, template paths and a symlinked registry. Failure
shows as a one-line `factory:` error and exit 1 with nothing written. A project that symlinks a managed dir out
of the tree is refused (documented in the spec).

## Rollout and rollback

Merge; revert the commit to undo. No data migration.

## Risks and open points

Sonar may keep reporting the content-flow shape (file read to file write) even though the path side is now
checked. Signal: the Sonar API after the push scan on main. Response: dismissal proposal on the Jira issue, no
dismissal without the owner.
