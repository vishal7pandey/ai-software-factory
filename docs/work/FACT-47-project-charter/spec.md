# FACT-47 — Project charter

Status: draft · Risk: medium · Jira: FACT-47
Created: 2026-10-07 · Slug: project-charter

## Problem

Owner question of 2026-10-07: "when do we end development on ade and chatpid? these are simple, smart recipes, not the
next Netflix." The factory has no answer: a project has no stated end, so scope grows. A project needs a written,
owner-approved definition of done and a stop rule, and the factory must keep the work honest against it.

## Users and context

* The owner, who approves what "done" means and when a project enters maintenance.
* Agents, who must check proposed work against the charter (`factory-spec`) and must not approve it themselves.
* Builds on FACT-46 (merged): the `charter` decision type, `factory decide`, the validator in `verify.py`, the
  `subject`/`subject_sha256` tamper evidence. Code read: `src/swfactory/decisions.py`, `verify.py`, `checks.py`
  (doctor), `work.py` (`cmd_status`, `cmd_start`), `kit/manifest.yaml`, `docs/ARCHITECTURE.md` 3.1 and 3.11.

## Goals and non-goals

**Goals**
- Every adopted project can carry `docs/PROJECT.md`: purpose, 3 to 7 measurable done criteria, non-goals, a parked
  list, and the maintenance-mode definition.
- The charter is approved only through the owner-decision gate (a `charter` record); until then the factory says so.
- `status` reports progress against the criteria from references it can check offline; when all are met it says the
  project is ready for maintenance mode and that the owner decides.
- In maintenance mode, starting a feature prints a warning (not a block).

**Non-goals**
- No Jira client: a `jira` reference is read only through an injected lookup (none by default: it shows `unknown`).
- No automatic switch to maintenance mode and no blocking of work: the owner may proceed deliberately.
- Writing the charters of other projects (ade, chatpid): they sync first; this item changes the factory only.

## Requirements

- R1. `docs/PROJECT.md` is Markdown with YAML front matter: `purpose`, `mode` (`active` | `maintenance`), `decision`
  (the `D-<n>` of the charter record that approves it, or null), `done` (list), `non_goals` (list), `parked` (list), and a
  body with a `## Maintenance mode` section.
- R2. Each `done` entry is `{id, text, check}`; `check` has exactly one of: `work: <work item id>` (met when that item
  is at `merged` or later), `file: <path>` (met when it exists), `metric: {file, key, min|max|equals}` (met when the
  value at the dotted `key` of that YAML or JSON file satisfies the bound), `jira: <KEY>` (met when the injected lookup
  says `Done`). Paths stay inside the project.
- R3. The pure validator `validate_charter` rejects: no or more than 7 or fewer than 3 criteria, duplicate ids, a
  criterion without a valid `check`, text with a vague phrase ("works well", "user-friendly", "robust", ...) or fewer
  than three words, empty purpose, no non-goals, a bad mode, a missing `## Maintenance mode` section, a malformed
  `parked` entry, an unfilled template.
- R4. Approval: a `charter` decision record must have `subject: docs/PROJECT.md` (the validator in `verify.py` requires
  it), `decide --accept` refuses unless `docs/PROJECT.md` is a valid charter that names that record in `decision`, and stamps
  the file's sha256. The charter is approved when `decision` names an accepted `charter` record whose hash equals the
  current file; an edit after approval is `changed` (a warning), and needs a new charter decision. An agent never runs
  `decide`; charter decisions are never delegated (FACT-46).
- R5. `factory doctor` gives one finding about the charter: WARN when there is no approved charter (missing, template,
  invalid, unapproved, pending, changed), OK when approved. Never a FAIL.
- R6. `factory status` prints, for an approved charter, progress per criterion (`met`, `not met`, `unknown`), the count,
  and, once all are met in `active` mode, that the project is ready for maintenance mode and that the owner decides with
  a `charter` record; in `maintenance` mode it prints the stop rule. A present but unapproved charter prints one line.
- R7. `factory feature start` in a project whose charter is in maintenance mode prints a warning that new features need
  a charter amendment and carries on. `bug start` does not warn.
- R8. The kit lays `docs/PROJECT.md` in `create` mode (a template: never overwritten, not tracked); `adopt` creates it,
  `sync` leaves an edited copy alone. `factory decision new --type charter` scaffolds the record (`subject`, one option).
- R9. The `factory-spec` skill checks proposed work against the charter (in scope, a done criterion, else parked or an
  amendment); `factory-workflow`, the autonomy policy and the Treaty (3.12) describe the charter.
- R10. Dogfood: the factory's own `docs/PROJECT.md` and its charter decision record, left `proposed`.

## Acceptance criteria

- AC1. (R8) The kit template renders (front matter parses, body has the required sections) and is `create` mode;
  `adopt` on a scratch project creates `docs/PROJECT.md`; an edited copy survives `sync`; `sync --check` ignores it;
  `decision new --type charter` writes a valid record with `subject: docs/PROJECT.md`.
- AC2. (R3, R5) `doctor` WARNs with no charter, with the template, with an invalid one, with one whose record is
  proposed, rejected, missing, or whose file changed after approval, and is clean (one OK line, no WARN) with an approved
  one; `validate_charter` returns a problem for each rule of R3 (one test per rule), including empty `done` and
  "works well".
- AC3. (R2, R6) With a stubbed Jira lookup, a work item, a file and a metric file, `status` prints each criterion as
  met, not met or unknown, the count, and flips to "ready for maintenance mode" when all are met; an unknown criterion
  keeps it from flipping; a metric below its bound is `not met`.
- AC4. (R7) In maintenance mode `feature start` prints the amendment warning and still creates the item; in active mode
  and for `bug start` it prints no warning.
- AC5. (R10) The factory repo carries `docs/PROJECT.md` (valid, `mode: active`, six criteria with checkable references,
  non-goals, a parked list, the maintenance definition) and a `charter` record in `proposed` state naming it; `doctor`
  shows the charter as waiting and `verify` is clean. The record is not accepted.
- AC6. (R4) `decide --accept` on a charter record refuses when `docs/PROJECT.md` is missing, invalid, or does not name
  the record; on success stamps `subject_sha256`; editing the file afterwards makes `doctor` say `changed`; a charter
  record without `subject` fails `verify`; `--delegated` is refused for it; the only agent-run path (no `--yes`, no
  terminal) refuses.
- AC7. (R9) Contract tests pin the `factory-spec` charter check and the charter text in the workflow skill, autonomy
  policy and Treaty; `lint` is clean.

## Edge cases and failure modes

- `docs/PROJECT.md` with CRLF line endings: parsed and hashed on the normalised text.
- A metric file that is missing, unreadable, lacks the key, or holds a non-number: `unknown`, never a crash.
- A `work:` reference to a work item that does not exist: `not met` (nothing has been built).
- `decision` names a record that does not exist or is not of type `charter`: unapproved, with the reason.
- A project with no `docs/PROJECT.md`: `doctor` warns, `status` prints nothing about it, `feature start` is silent.

## Non-functional requirements

- Offline, deterministic, ASCII output, no secret or network access; criterion text cut to 60 characters in listings.
- Treaty rule: generic; the kit template and docs carry no project names.

## Assumptions

- The charter's approval vehicle is the FACT-46 record plus the file hash, not a second ledger inside `PROJECT.md`.
- Switching to maintenance mode is an edit of `mode:` in `docs/PROJECT.md` together with a new `charter` record; its
  acceptance re-hashes the file. Between the edit and the acceptance the charter shows as unapproved (honest, and a
  warning only).
- Vague-phrase detection is a short fixed list plus a three-word minimum; the real measurability is the `check` reference.

## Risks and dependencies

- New create-mode file in every adopted project on its next `sync` and a new WARN in `doctor` until the owner approves a
  charter: intended pressure, but noisy for projects that never will; `doctor` never fails on it.
- Depends on FACT-46 (merged).

## Open questions

None. The done criteria of the factory itself are proposed in the dogfood record for the owner to change or accept.
