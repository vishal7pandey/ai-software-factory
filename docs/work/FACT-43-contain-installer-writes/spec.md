# FACT-43 — Contain installer writes

Status: draft · Risk: low · Jira: FACT-43 (also FACT-44, FACT-45)

One work item for three SonarCloud findings of the same rule in the same file, tracked one Jira Bug each
(`finding-sonar-<key>` labels): `pythonsecurity:S2083` (BLOCKER, "Path Traversal via unsanitized user input"):

| Jira | Sonar issue key | Line | Function |
|------|-----------------|------|----------|
| FACT-43 | AaESHawxBv0rcil6sMeR | `src/swfactory/installer.py:477` | `_save_registry` |
| FACT-44 | AaESHawxBv0rcil6sMeS | `src/swfactory/installer.py:642` | `new_project`, `dst.write_bytes(data)` |
| FACT-45 | AaESHawxBv0rcil6sMeQ | `src/swfactory/installer.py:646` | `new_project`, `dst.write_bytes(text.encode(...))` |

## Repro

Environment / version / commit where it fails: `main` @ d4126a6, SonarCloud project
`vishal7pandey_ai-software-factory`, analysis of `main`.

1. Read the three issues through `https://sonarcloud.io/api/issues/search?issues=<key>&componentKeys=vishal7pandey_ai-software-factory`
   (public project; the `flows` field is the taint path).
2. Flow of AaESHawxBv0rcil6sMeR: `Path.read_text` of the registry (`installer.py:470`, `:476`) is the
   "source", the string concatenation at `:477` carries it, and `p.write_text(...)` at `:477` is the sink.
3. Flows of ...MeS and ...MeQ: `src.read_bytes()` (`:638`) is the source; `decode`, the `{{name}}` /
   `{{package}}` replacements and `common.normalise_newlines` (`common.py:80-81`) carry it; the two
   `dst.write_bytes(...)` calls (`:642`, `:646`) are the sinks.
4. Separately, the real property behind the rule: `factory adopt`, `factory sync` and `factory new` write to
   `root / <manifest dest>`, `root / <skill target>/...` and `target.joinpath(<template path>)` with no check that
   the result stays inside the project. `factory sync` copies kit content into OTHER projects.

Automated repro (failing tests, written first; all fail with `DID NOT RAISE FactoryError` on the current code):

- `uv run python -m pytest -q tests/test_install.py -k "outside or climbs or symlink"` (11 failed, 1 skipped on `d4126a6`; two sibling-prefix cases were added afterwards).

Reproducibility: always (static analysis for the Sonar flows; deterministic for the tests).

## Expected

A destination that is not strictly inside the project root is rejected with a clear error before any file is
written: a `..` in a manifest `dest` or skill target, an absolute path, or a path that leaves the project through
a symlink. The registry file is written only where it resolves, inside its own directory.

## Actual

The installer joins the destination to the root and writes. A manifest entry `dest: ../x`, an absolute `dest`,
or a `skill_targets` entry in a project's `factory.yaml` of `../x` writes outside the project root. Sonar reports
the three write sites as path traversal.

## Root cause (with evidence)

- Where: `installer.py` `_plan_item` / `_install` (manifest and skill targets, line ~345 `target.write_bytes`),
  `new_project` (template paths, `:642`, `:646`) and `_save_registry` (`:477`).
- Why it fails: a destination was trusted because the kit manifest, the template tree and the registry are
  "owner controlled". They are not trusted inputs in general: a project's `factory.yaml › skill_targets` is
  owned by that (other) project, the kit tree is third-party content once the factory is installed from a
  checkout, and a symlink in a project or a registry file can redirect a write. No containment check existed.
- Introduced by: always present (the installer never checked containment).
- Evidence: the failing tests above; the Sonar flows in the table. Ruled out: the Sonar "source" (file reads) is
  not an HTTP request: for the content flows the finding is a taint false-positive shape (content read from a
  file is carried into a write). The path side is real and fixed here; whether Sonar closes the three issues
  after the fix is checked on the scanner (AC4), not assumed.

## Blast radius

- Callers reaching the writes: `adopt`, `sync` (`--force`), `sync --check`/`--dry-run` (read the destination
  during planning), `new` (which adopts), `project add|remove`, adopt's `_register_adopted`.
- Other inputs: manifest `files` and `dirs` `dest`, `skills: all` targets (`factory.yaml › skill_targets`),
  template relative paths, the registry file path (`FACTORY_REGISTRY`).
- Data: none written outside a root so far (the shipped manifest and templates are well-formed). A project that
  symlinks `.claude` or `.github` to another directory will now be refused (see Risks).
- Not changed: other writers in `src/swfactory` (work items, harden, sonar): no Sonar issue of this rule there.

## Regression criterion (AC1)

AC1: A manifest `files` or `dirs` destination that escapes the project (`../x`, `a/../../x`, an absolute path),
in `create` or `managed` mode, makes `adopt` fail with "outside the project" before any write; the project tree is
unchanged and nothing is created outside it. Tests: `test_a_manifest_file_dest_outside_the_project_is_rejected_before_any_write`
and `test_a_manifest_dir_dest_outside_the_project_is_rejected_before_any_write` (fail on the current code, pass after).

AC2: A `skill_targets` entry that escapes the project makes `sync` fail the same way with nothing written; a
destination reached through a symlink (a junction on Windows) that leaves the project is rejected too. Tests:
`test_a_skill_target_outside_the_project_is_rejected_by_sync`,
`test_a_dest_reached_through_a_symlink_that_leaves_the_project_is_rejected`.

AC3: `factory new` rejects a template path that climbs out of the new project, writing nothing outside it; and
`_save_registry` refuses a registry file that resolves outside its own directory and leaves the target untouched.
Tests: `test_new_rejects_a_template_path_that_climbs_out_of_the_new_project`,
`test_the_registry_is_not_written_through_a_symlink_that_leaves_its_directory` (needs symlink rights: skipped
on a Windows machine without them, runs on Linux CI).

AC4: Normal behaviour is unchanged (the full existing suite passes) and, after the fix is merged and the push
scan has run, the Sonar API reports each of AaESHawxBv0rcil6sMeR, ...MeS, ...MeQ as closed. If an issue stays
open although AC1-AC3 hold, it is a taint false positive: the Jira Bug stays In Progress with a dismissal
proposal for the owner; nothing is dismissed without the owner's yes.

## Fix constraints

Stdlib only; the check is inline (`os.path.realpath` on base and candidate, `startswith(base + os.sep)`) at each
point of use, the form Sonar and CodeQL recognise. No change to the manifest, the templates, or any message that
existing tests match. The registry rewrite becomes a single write (no read-back of the file just written).

## Risks

A project that symlinks a managed directory (for example `.claude/skills`) to a shared location outside the
project is now refused by `adopt`/`sync` with "outside the project"; accepted, since that is the escape this
guards against, and the error names the destination. Risk level low: the shipped kit passes unchanged (full
suite).

## Amendment 2026-10-07 (found on the PR scan)

The first fix (containment guard that raises, then `Path.write_bytes` / `write_text`) did not clear the issues:
the analysis of PR 19 still reported `pythonsecurity:S2083` at the three write sites (plus `python:S3776`, the
new code made `new_project` too complex). The Sonar flows show the "source" is the file read and the sink is the
`pathlib` write call, which a path guard does not sanitise. The shape that Sonar accepts is the guard with the
sink inside its true branch and the write made through `open(dst, ...)` / `os.makedirs(dst)`. Refinement inside the
same scope: writes in `_save_registry` and the template copy now use `open()` inside `if dst.startswith(root + os.sep):`
(else `raise`), and the template copy is split out of `new_project` (`_copy_template`, `_render_template`). Behaviour
and tests are unchanged. The PR analysis then reported no issue and CodeQL no alert.
