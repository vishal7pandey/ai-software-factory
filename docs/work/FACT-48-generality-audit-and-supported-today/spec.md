# FACT-48 — Generality audit and supported-today matrix

Status: draft · Risk: low · Jira: FACT-48
Created: 2026-10-07 · Slug: generality-audit-and-supported-today

## Problem

The owner's goal is a factory that can build any project. The method (spec, plan, test plan, review, release,
findings, dependencies, decisions) is generic, but the machinery is narrower, and nothing in the repository says
by how much. A reader of the README or the Treaty can believe that Go, GitLab, Linear or macOS work. Exactly three
projects have used the factory (itself, ade, chatpid), all one owner, all GitHub and Jira, python with a pnpm
frontend, developed on Windows. Without an honest, checked account, the next project finds the gaps by hitting them.

## Users and context

* **The owner**, deciding what to extend next and what to believe about the factory today.
* **An agent** starting a project that does not fit the three proven shapes: it must be able to read what is
  supported and what is not before it adopts the kit.
* Read for this audit: `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/PROJECT.md` (charter criterion C6 names this
  ticket), `kit/manifest.yaml`, `kit/ci`, `kit/sonar`, `kit/dependabot`, `templates/`, `src/swfactory` (installer,
  adopt_inspect, harden, deps, checks, work, verify), the tests, and what `ade` and `chatpid` actually contain
  (their `factory.yaml`, workflows, `docs/work` and merged PRs).

## Goals and non-goals

**Goals**
- One place (`docs/SUPPORT.md`, linked from the Treaty and the roadmap) that says, per dimension and value,
  supported, partial or not supported, what proves it, and the known gaps.
- A check that fails when that place falls behind the repository (a stack with no row, a claim with nothing behind it).
- A ranked, evidence-based roadmap (Confluence page "Factory generality: assumptions and roadmap") with the smallest
  next step per gap and how each would be proven.
- One extension proposed to the owner as a decision record, not decided.

**Non-goals**
- Building any extension (no new stack template, tracker, scanner or hosting support in this item).
- Editing the charter's approval state, or accepting any decision record (the owner decides).
- Changing CI, branch protection or repository settings.
- Counting a capability as supported on the strength of intent: only what a project, a CI run or a test shows.

## Requirements

- R1. `docs/SUPPORT.md` holds one table with the columns dimension, value, status, proven by, known gaps. Status is
  exactly `supported`, `partial` or `not supported`. Dimensions: stack, tracker, hosting, ci, scanner, dependabot
  ecosystem, os, agent, shape, owners. Every row names what proves it (a project and PR, a CI run, or "tests only" /
  "nothing") and its known gaps.
- R2. A pure function `check_support(root)` reads the repository and reports a finding for each of: the matrix
  file missing or without a table; a row with an unknown status, a missing cell or fewer than five cells; a required
  dimension (stack, tracker, hosting, ci, scanner, os) with no row; a stack that exists in the repository but has no
  `stack` row; a `stack` row claiming `supported` or `partial` for a stack that does not exist; a `stack` row marked `not supported`
  for a stack that now exists (the row went stale); a Dependabot
  ecosystem template without a `dependabot ecosystem` row; the Treaty or the roadmap not linking `SUPPORT.md`.
  A stack "exists" when it is a name in `STACKS`, a `stack:` value in `kit/manifest.yaml`, a directory under
  `templates/`, or a file stem under `kit/ci/` or `kit/sonar/` (the stem `generic` is the shared placeholder of `docs`
  and `other` and needs no row of its own).
- R3. `factory lint` runs `check_support` in a factory repository (one that has `docs/ARCHITECTURE.md`), so CI blocks
  a merge that makes the matrix stale.
- R4. The Treaty gets a short section that links `docs/SUPPORT.md` and says what the matrix is and how it is checked;
  `docs/ROADMAP.md` links it and its stale line "Stack templates: node/Next.js" is corrected.
- R5. The Confluence page "Factory generality: assumptions and roadmap" in space FACT lists each assumption, what
  breaks, the smallest work that lifts it, ranked by value over effort, with how each step would be proven (a scratch
  project adopted, CI green, doctor clean). It covers at least: more stack templates (Go, Java, Rust, .NET, static
  site, infrastructure as code), a no-Jira and GitHub-Issues-only mode, non-GitHub hosting, more scanners (container,
  infrastructure as code, licence, SBOM), Linux and macOS evidence, research and learning projects, multi-owner use.
  It is linked from the FACT space home page, and the Treaty and roadmap name it by title (no hostnames in the repo).
- R6. One extension is proposed as `docs/decisions/D-003-*.md`: type `design`, status `proposed`, options that include
  doing nothing, exactly one recommended, with the reason and a proposed spec (scope, acceptance criteria, how it
  would be proven). It is never accepted by the agent.

## Acceptance criteria

- AC1. (R1, R4) `docs/SUPPORT.md` exists with rows for every stack the repository has (`python`, `node`, `docs`,
  `other`) and for the not-supported stacks go, java, rust, dotnet, static site, infrastructure as code, mobile,
  notebooks; the trackers jira, none, github, other; the hostings github.com, local only, other; CI, scanner,
  Dependabot ecosystem, OS, agent, shape and owners rows. `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` both link it.
  A test reads the real file and asserts `check_support(ROOT) == []`.
- AC2. (R2) A test that copies a minimal valid tree into a temporary directory and adds a directory `templates/go`
  (and, separately, `kit/ci/go.yml`, a `stack: rust` value in the manifest) gets a finding that names the stack and
  says it has no row in `docs/SUPPORT.md`; the unmodified tree gets none. Failure path.
- AC3. (R2) Tests show each of these gives a finding naming the problem: a missing `SUPPORT.md`; a row with status
  `works`; a row with an empty "proven by" cell; a required dimension (`os`) with no row; a `stack` row `go` marked
  `supported` with no such stack; a `dependabot_templates` key with no `dependabot ecosystem` row; `ARCHITECTURE.md`
  without a link. Failure paths.
- AC4. (R3) `factory lint` run against a temporary copy of the repository's factory files (kit, skills, policies,
  templates, docs, `verify.py`) exits 1 and prints a line naming the stack when a `templates/swift` directory (no
  row) is added, and again when a `templates/go` directory is added (its row says `not supported`: stale), and
  exits 0 without either. A repo root without `docs/ARCHITECTURE.md`
  (the existing lint tests' temporary roots) is not checked and still passes.
- AC5. (R5) The Confluence page exists in space FACT with title "Factory generality: assumptions and roadmap", contains
  a ranked table (rank, gap, value, effort, smallest next step, proof) covering the seven topics of R5, and is linked
  from the FACT space home page; verified by reading both pages back after publishing. (Manual: no repository test
  can read Confluence.)
- AC6. (R6) `docs/decisions/D-003-*.md` validates with `validate_decision` (the same function `verify` runs), has
  `status: proposed`, `type: design`, `decision: null`, at least three options one of which is "do nothing", exactly
  one `recommended: true`, and `by`/`at` null; a test asserts this and that no record in the repository was answered
  by this item (D-001, D-002 and D-003 are all still `proposed`).
- AC7. (R1-R6) `factory lint`, `factory sync --check .`, `factory verify`, ruff check and format, and the full
  suite pass on Windows and Linux; the charter file `docs/PROJECT.md` is byte-identical to `main`.

## Edge cases and failure modes

- A new stack directory arrives together with its matrix row in the same PR: passes. Arrives without: lint and the
  test fail with the stack name. Arrives for a stack whose row says `not supported`: fails until the row is updated.
- The matrix claims `supported` for a stack whose template was removed: fails (a claim with nothing behind it).
- `kit/ci/generic.yml` is a shared placeholder, not a stack: no row of its own is demanded; it serves `docs` and `other`.
- A table cell containing a pipe breaks the row: the check reports the row by its number of cells.
- A synthetic repository root without `docs/ARCHITECTURE.md` (other tests build such roots) is not a factory repository:
  `lint` skips the matrix check there, `check_support` itself called directly on it reports the missing file.
- The matrix cannot prove more than its source: a `supported` row with "nothing" in "proven by" is allowed to exist
  (the check demands the cell be written, not that the claim be true); review of this PR is where that is judged.

## Non-functional requirements

- No network, no new dependency (stdlib + PyYAML). The new module is offline and deterministic.
- Windows and Linux: files read as UTF-8, paths through `pathlib`, no shell.
- `docs/` must not contain an Atlassian site hostname (`factory lint` rule): the Confluence page is named by title.
- The matrix states only what the evidence supports (spec principle for this item); where evidence is only a unit
  test the row says "tests only".

## Assumptions

- The matrix lives in a dedicated `docs/SUPPORT.md` rather than inside the Treaty: it will change at every new stack
  and tracker, and the Treaty is meant to be stable. The Treaty links it.
- The check is wired into `factory lint` (which CI already runs on every PR) as well as tested directly.
- `node` is `partial`, not `supported`: no project has `stack: node`; the template (`npm ci`, npm cache) is proven by
  tests only, and the pnpm frontends of ade and chatpid are covered by Dependabot, not by the kit CI.
- The Jira ticket text says "Node (pnpm)"; the template is npm. The matrix records what the file says.
- `tracker: github` is a value the CLI accepts and the Treaty lists, but no code or skill reads it: the matrix says
  `not supported` (accepted, inert).
- Delegated approval of this spec and plan is recorded under the owner's name as instructed for this run.

## Risks and dependencies

- Risk is low: documentation, one pure function, one lint hook, one proposed (inert) record. Reversible by revert.
- Another agent works on the Sonar kit template and `docs/sonarcloud.md` (FACT-40); this item touches neither. If that
  work adds a `kit/sonar/<stem>` for a new stack, the matrix check will ask for the row, which is the intent.
- The honesty of the matrix depends on this audit's reading of three projects; a mistake is a docs fix, not a break.

## Open questions

- None blocking. Recommended answer for the owner to confirm later: which extension to build first (D-003).
