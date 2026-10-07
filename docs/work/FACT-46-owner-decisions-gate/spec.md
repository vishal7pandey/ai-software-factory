# FACT-46 — Owner decisions gate

Status: draft · Risk: medium · Jira: FACT-46
Created: 2026-10-07 · Slug: owner-decisions-gate

## Problem

Owner feedback of 2026-10-07: pending owner decisions (a finding dismissal, a design choice, a definition of
done) were asked in chat and tracked nowhere but in the agent's head. The factory has human gates for spec, plan,
merge and production, but nothing that shows "what is waiting for the owner", and no way to record the answer with
approver and date. A human above the loop needs one inbox, and a recorded answer an agent can cite.

## Users and context

* The owner (a human) who answers questions agents raise, across several projects.
* Agents running the factory skills (`factory-findings`, `factory-spec`, `factory-plan`, `factory-diagnose`) that hit
  a choice that belongs to the owner.
* Code read: `src/swfactory/work.py` (`cmd_approve`, `cmd_status`), `src/swfactory/verify.py` (standalone gate),
  `src/swfactory/checks.py` (doctor), `src/swfactory/installer.py` (manifest, registry), `skills/factory-findings`,
  `policies/findings.md`, `policies/autonomy.md`, `kit/manifest.yaml`, `docs/ARCHITECTURE.md` (Treaty).

## Goals and non-goals

**Goals**
- A decision is a file in the project's git repo, readable as markdown, answered with one command that records who
  and when, and visible in one place (`factory status`, `factory doctor`, `factory inbox`).
- A scanner-finding dismissal becomes such a record; the agent applies it only once it is accepted.
- The gate is a ledger like `approve`: an agent never answers for the owner.

**Non-goals**
- No tracker dependency (no Jira calls), no network, no notification channel. The `jira` field is a link, not a sync.
- Not a replacement for the spec and plan gates (`approve`) or for ADRs (`docs/decisions/00N-*.md` keep their form
  and are ignored by the new checks).
- The project charter (`docs/PROJECT.md`) is FACT-47; this item only lays the gate it will use (type `charter`).
- Records in other projects (the open ade and chatpid decisions of 2026-10-07) are written in those repos after
  they `factory sync`; this item changes the factory only.

## Requirements

- R1. A decision record is `docs/decisions/D-<n>-<slug>.md`: Markdown with YAML front matter (format below).
- R2. `factory decide <id> --accept [--option N] | --reject [--note TEXT] [--delegated WHO] [--yes]` answers a
  `proposed` record: stamps `status`, `decision`, `by` (git user name, or the delegated form), `at` (today), and
  leaves the body untouched. It refuses a record that is not `proposed`, one that fails validation, and one that is
  still a template (the unfilled-marker line, the clarification marker, `REPLACE_ME` or `{{` present).
- R3. `decide` never acts without an explicit command: it asks for confirmation on a terminal and refuses without
  `--yes` when stdin is not a terminal (an agent's shell); exactly one of `--accept`/`--reject` is required;
  `--delegated` is refused for `charter` and `dismissal` records (never delegated, even on request).
- R4. `factory decision new <title> --type dismissal|design|charter|other [--jira KEY] [--alert URL --reason R]
  [--by NAME]` scaffolds a valid `proposed` record from the kit template (next free `D-<n>`), never overwriting.
- R5. `factory status` and `factory doctor` list every `proposed` record as waiting for the owner, with age, type,
  title and the recommended option; when nothing waits, they print nothing for it.
- R6. `factory inbox` lists the waiting records of every project in the registry that has a local path, read-only,
  deterministically ordered (project name, then id).
- R7. `factory verify` (standalone) fails on an invalid record: accepted or rejected without `by`/`at`, accepted
  with a `decision` that is not one of the options, a proposed record that already carries an answer, a delegated
  record without the delegated wording, a delegated `charter`/`dismissal`, a `dismissal` without alert URL and an
  allowed reason, an accepted record whose `subject` has no `sha256`, a duplicate id.
- R8. The `factory-findings` skill and `policies/findings.md` route every dismissal through a `dismissal` record:
  the agent proposes, applies the dismissal only when the record is `accepted`, and cites the record id, `by` and
  `at` in Jira. `factory-spec`, `factory-plan`, `factory-diagnose` and `factory-workflow` say to open a decision
  record instead of asking in chat when a choice belongs to the owner; no skill instructs running `factory decide`
  (`factory lint` enforces it as it does for `approve`).
- R9. The kit lays `docs/decisions/TEMPLATE.md` in `create` mode (never overwritten, not tracked); `kit/manifest.yaml`
  names the template and `factory lint` checks it exists. The autonomy policy, the AGENTS block and the Treaty
  state that deciding is the owner's act and never an agent's own.

## Record format

```yaml
---
id: D-001                    # D-<n>, equals the file name prefix
type: design                 # dismissal | design | charter | other
title: One line the owner can answer
status: proposed             # proposed | accepted | rejected | superseded
jira: FACT-46                # ticket or null (a link only)
proposed_by: agent           # who raised it
proposed_at: 2026-10-07
alert: null                  # dismissal only: the alert URL
reason: null                 # dismissal only: false positive | won't fix | used in tests
options:                     # the choices; exactly one recommended while proposed
  - {text: "Do A", recommended: true}
  - {text: "Do B"}
decision: null               # the chosen option's text, set by `decide --accept`
by: null                     # set by `decide`
at: null
delegated: false
note: null                   # `decide --note`
subject: null                # optional: project file the decision covers (the charter: docs/PROJECT.md)
subject_sha256: null         # set on accept when subject is set (tamper evidence for FACT-47)
superseded_by: null          # D-<n> when status is superseded
---
Body: Context, Evidence, Options with consequences, Recommendation.
```

## Acceptance criteria

- AC1. (R2) `decide D-001 --accept --yes` on a valid proposed record sets `status: accepted`, `decision` to the
  recommended option, `by` to the git user name, `at` to today, keeps the body byte for byte; `--option 2` picks
  the second option; `--reject --note "no"` sets `status: rejected`, `note`, `by`, `at` and no `decision`. It
  refuses (exit 1, file unchanged) a record that is already `accepted`, `rejected` or `superseded`, a record with
  an invalid front matter, one still holding the unfilled line, `REPLACE_ME`, `{{` or a clarification marker, an
  `--option` out of range, and an unknown id.
- AC2. (R5) With one proposed and one accepted record, `status` prints a "waiting for the owner" block naming the
  proposed one with its age in days, type, title and recommended option and not the accepted one; with none
  waiting (or no `docs/decisions` folder) `status` prints no such block; `doctor` gives a WARN finding per waiting
  record and nothing when none waits; an invalid record is a WARN in `doctor`, never a crash.
- AC3. (R6) With a stubbed registry (a temp-dir registry file and two temp projects) `inbox` prints both projects'
  waiting records grouped by project in name order, notes a project without a path or whose path is missing as
  skipped, prints "nothing waiting" when none waits and "no registry yet" without a registry; it writes nothing.
- AC4. (R7) `verify` prints `FAIL D-001: ...` and exits 1 for each rule of R7 (one test per rule), ignores ADRs and
  the template, and is OK for valid proposed, accepted, rejected and superseded records.
- AC5. (R8) Contract tests read the real skill and policy and pin: the dismissal record flow (record type,
  `accepted` before the call, citation of id/by/at in Jira, no dismissal without an accepted record), the
  `docs/decisions` hand-off in spec, plan, diagnose and workflow, and that no skill tells an agent to run
  `factory decide`; a scripted walkthrough models the agent applying a dismissal only after the record is accepted.
- AC6. (R3) An agent-style run does not decide: `decide` without `--yes` on a non-terminal fails and leaves the file
  unchanged; with neither or both of `--accept`/`--reject` the parser exits 2; `--delegated "Owner"` on a
  `charter` or `dismissal` record fails; `--delegated` on a `design` record writes `by: "Owner (delegated to agent)"`
  and `delegated: true`; `status`, `doctor`, `inbox`, `feature start` and `next` leave every record byte-identical
  and the handoff prompt never contains `factory decide`; `lint` fails a skill line that instructs
  `factory decide`.
- AC7. (R4) `decision new` creates `docs/decisions/D-001-<slug>.md` that `verify` accepts, then `D-002`; a dismissal
  without `--alert`/`--reason` or with another reason fails; the new record is a draft (`decide` refuses it until
  the unfilled line is removed); an existing file is never overwritten.
- AC8. (R9) The manifest lists the template as `create`; `adopt` on a scratch project creates it, `sync` leaves an
  edited copy alone and `sync --check` ignores it; `lint` fails when the named template is missing; the Treaty
  documents section 3.11, the new commands and verify rule 6.

## Edge cases and failure modes

- A record with CRLF line endings (Windows) parses and round-trips with `\n`.
- Front matter missing or not valid YAML: `verify` FAILs it with the reason; `status`/`doctor` do not crash.
- File names that are not `D-<n>-<slug>.md` (ADRs `001-*.md`, `TEMPLATE.md`, `README.md`) are not records.
- Two files with the same id: `verify` FAIL; `decide <id>` refuses as ambiguous.
- A record file that is a symlink leaving `docs/decisions` is skipped (containment, FACT-43 pattern).
- `inbox`: a registered path that is missing, or has no `docs/decisions`, is skipped, never an error.
- Age is computed from `proposed_at` and an injected "today", so output is deterministic.

## Non-functional requirements

- Offline, no network; `verify.py` stays stdlib + PyYAML and imports nothing from `swfactory`.
- Output is ASCII only; titles and option text are cut to 60 printable ASCII characters in listings.
- Treaty rule: generic, no project names or hostnames in the kit, skills, policies or docs.

## Assumptions

- Decision ids are `D-<n>` per project (not Jira keys); `jira` links to the ticket. Changing this later is cheap.
- `decide` stamps the git user name like `approve` does; that is the "ledger, not a lock" model (Treaty 1.x): the lock
  is GitHub review (CODEOWNERS on `docs/decisions/` is documented), not this command.
- `--delegated` exists on `decide` because the ticket asks for the `approve`-like form, but it is limited to `design`
  and `other` records and needs an explicit recorded owner instruction; `charter` and `dismissal` are never delegated.
  This limit is an assumption the owner may overrule (it is also raised as a decision record in this PR).
- "verify rejects a dismissal commit": commits are not inspected; the record is the artefact `verify` checks.

## Risks and dependencies

- Adds a second front-matter parser inside the standalone `verify.py` (it cannot import `swfactory`). Mitigation:
  `swfactory` imports the parser and validator from `verify.py`, one implementation.
- The create-mode template lands in every adopted project on its next `sync`: low risk, one file.
- Risk is medium because it changes the verify gate (a malformed `D-*.md` now fails CI in adopted projects after
  they sync the new `verify.py`).

## Open questions

None open. The delegation limit above is stated as an assumption and raised as record D-001 for the owner.
