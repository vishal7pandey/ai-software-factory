# FACT-12 — Project-aware adoption

Status: in-review · Risk: medium · Jira: FACT-12
Created: 2026-10-05 · Slug: project-aware-adoption

Source: the Confluence page "FACT-12 Spec: Project-aware adoption" (space FACT) and the ticket. This
file is the repo copy that gets approved.

## Problem

`factory adopt` writes the same generic files into every project without looking at it, and that
failed in practice on the first two adoptions: the generated CI could not find pytest because the
project keeps it in an optional extra; an existing CI never ran on pull requests because it filtered
on `main` while the default branch is `master`; a new `AGENTS.md` pointed agents to "the rest of this
file" for commands when there was none; and a starter CI would have been red on day one because the
project's own lint failed. The factory itself also showed two gaps: managed copies inside its own repo
can drift from their source with no signal, and a feature branch that only holds a draft spec fails the
`verify` rule that demands implementation status.

## Users and context

The maintainer and agents running `factory adopt` / `factory sync` against a real repository, and CI
running `verify`. Code: `src/swfactory/installer.py` (adopt, sync, planning), `src/swfactory/verify.py`
(standalone, copied into projects), kit templates in `kit/ci/` and `kit/workflows/`.

## Goals and non-goals

**Goals:** adopt looks at the project (default branch, existing CI, AGENTS.md, its own check commands)
and reports or adapts; sync can fail CI on drift; verify stops punishing docs-only branches.

**Non-goals:** a project-introspection framework or plugin system; guessing commands silently; changing
files that already exist (CI, AGENTS.md text outside the factory block); reading build tools beyond
Makefile targets, `package.json` scripts and pyproject tool tables for the TODO list.

## Requirements

- R1. The Python CI template installs every dependency layout: `uv sync --all-extras --all-groups`.
- R2. `adopt` prints a findings list before applying: default branch, existing workflow triggers that
  do not cover it, whether `AGENTS.md` has a commands section. After applying it prints what it did
  (TODO section inserted, CI steps dropped, checks skipped and why).
- R3. When `AGENTS.md` has no commands section, adopt inserts a short `Commands (TODO: confirm)` section
  directly above the factory block, listing commands detected from Makefile targets, `package.json`
  scripts and pyproject tool tables. It never invents a command; with nothing detected it says so.
  A project that already has a commands section is left alone.
- R4. When adopt writes a new `ci.yml`, it first runs that CI's `run:` steps locally in the project
  (opt out with `--no-check`; never in `--dry-run`). A failing step is left out of the generated CI,
  replaced by a comment, and reported with the step and the last output line. If the dependency-install
  step itself fails, or a needed tool is missing, nothing is dropped and the report says the checks
  could not run.
- R5. The generated CI triggers `push` on the project's default branch (not a hard-coded `main`).
- R6. `factory sync --check` writes nothing and exits 1 when any managed or block file is missing or
  differs from the factory source, 0 otherwise. The factory's own CI runs it.
- R7. `verify --changed-files-from FILE` (one path per line) lets a feature/fix branch whose changed
  files are all under `docs/work/` pass at any status; the item must still exist. Without the option
  nothing changes. The kit's `factory-verify` workflow passes the PR's changed files.
- R8. No new dependency; Windows and Linux behave the same.

## Acceptance criteria

- AC1. The Python CI template contains `uv sync --all-extras --all-groups` and no bare `uv sync`. A
  fixture with pytest only in an optional extra, adopted with a fake command runner, yields a CI whose
  install step is that command. (R1)
- AC2. Adopting a fixture whose default branch is `master` and whose existing workflow filters on `main`
  prints a finding naming the file, `master` and `main`. A workflow with no branch filter, or one that
  lists `master`, produces no finding. (R2)
- AC3. Adopting a fixture with no commands section inserts the TODO section above the factory block,
  listing the Makefile targets and `package.json` scripts it finds; with none found it says so; a fixture
  that already has a commands heading is not modified; running adopt twice changes nothing. (R3)
- AC4. Adopting a fixture whose lint step fails (fake runner) writes a CI without that step, with a
  comment, and prints the step and the failing output; steps that pass stay. A failing install step drops
  nothing and prints that checks could not run; `--no-check` and `--dry-run` run no command. (R4)
- AC5. Adopting a fixture whose default branch is `master` writes a CI whose push trigger is
  `branches: [master]`; with `main` it is unchanged. (R5)
- AC6. `factory sync --check` returns 0 and writes nothing on an up-to-date project, and returns 1 listing
  the file when a managed file's source changed or the file is deleted; the factory repo passes it and its
  CI runs it. (R6)
- AC7. A docs-only changed-files list on a `feature/...` branch at status `draft` passes `verify`; a list
  that includes a `src/` path still fails; an empty list passes; a missing item still fails; with no option
  the behaviour is unchanged. (R7)
- AC8. All tests pass on Windows and Linux (CI); `factory lint` passes. (R8)

## Edge cases and failure modes

- No git repo, or no remote: the default branch is the current branch if any, else "unknown", which skips
  the trigger finding and uses `main` in the generated CI.
- Workflow file that does not parse as YAML: reported as a finding, not a crash.
- A required tool (`uv`, `npm`) is not on PATH: the checks are skipped with a message; nothing is dropped.
- Each check step has a timeout (10 minutes); a timeout counts as failure of that step.
- CI already exists: it is never changed; the checks run only when a new `ci.yml` is generated.
- `sync --check` on a project that is not adopted: error, exit 1, as `sync` does.

## Non-functional requirements

Running project commands executes project code (tests, build). It only runs the exact `run:` lines about
to be written into CI, on the machine of whoever runs adopt, and `--no-check` turns it off. The commands
come from kit templates, never from project files (see `.factory/policies/security.md`).

## Assumptions

- A1. The cost of running the project's checks during adopt is acceptable with the opt-out (the draft
  spec asked this question; decided here, overrule at approval).
- A2. The "commands section" test is a heading containing command, build, test, run, develop or scripts.
  It can be wrong; the TODO is a prompt for a human, not a verdict.
- A3. `uv sync` run during the check may create a `.venv` in the project; that is what the CI does too.

## Risks and dependencies

- Medium risk: adopt now executes commands and inserts text into `AGENTS.md` outside the block. Both are
  bounded by the rules above and covered by tests with an injected runner.
- Changing `verify.py` and the kit workflow changes what adopted projects receive; they pick it up with
  `factory sync`. The factory repo syncs itself in the same PR.

## Open questions

None.
