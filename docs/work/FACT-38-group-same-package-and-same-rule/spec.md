# FACT-38 — Group same-package and same-rule findings into one issue

Status: draft · Risk: medium · Jira: FACT-38
Created: 2026-10-05 · Slug: group-same-package-and-same-rule

## Problem

The findings loop (`factory-findings`, `policies/findings.md`, FACT-34) says "one issue per finding. Do not merge several
alerts into one issue". The first real sweep showed the cost: one vulnerable package raised six Dependabot alerts per repo, all
fixed by a single upgrade, and that produced six near-identical Jira Bugs per repo. A code-scanning rule that fires forty times in
one helper module would take four full batches of ten, and the 10-issue cap fills with duplicates of one problem while other
high findings wait. The issue is the unit of work; one upgrade or one fix pattern is one unit. The owner decided on 2026-10-05
(comment on FACT-38) to group.

## Users and context

An engineer-agent running the findings loop in an adopted repo, and the human who reads the board and approves dismissals.
Grounded in: `skills/factory-findings/SKILL.md` (steps 3, 5, 7, Output, Definition of done), `policies/findings.md` (closure
rule, batch limits), `skills/factory-workflow/SKILL.md` and `skills/factory-release/SKILL.md` (route row and closure rule),
`tests/test_findings.py` (contract tests and the walkthrough with a fake `gh` and a fake Jira), `docs/ARCHITECTURE.md` (the
Treaty: the factory is generic, the shipped text names no project, host or ticket key).

## Goals and non-goals

**Goals**
- One Jira issue may carry several `finding-<source>-<id>` labels when the alerts are the same Dependabot package in the same
  manifest, or the same code-scanning rule in the same module.
- The safety property stays per alert: every alert keeps its own label and its own re-query, and the issue is Done only when
  all of its alerts re-query as `fixed`.
- A new alert that fits an existing open group joins it (label plus comment) instead of opening a new issue.
- The first-sweep cap counts issues, and the report gives alerts and issues.
- The tests pin the rule (walkthrough helper updated), and the skill, policy, routing text and docs say the same thing.

**Non-goals**
- No retroactive merging: existing per-alert issues are not merged, closed as duplicates or relabelled. Jira offers To Do,
  In Progress and Done only here, so "close as duplicate" would mean Done while an alert is open, which breaks the closure
  rule. Grouping applies to findings filed from now on (owner decision on the ticket; this replaces AC4 of the description).
- No grouping of secret-scanning alerts (each needs its own human-confirmed revocation) or SonarQube issues (not covered by
  the rule as decided); they stay one issue per alert.
- No new CLI command and no change to `src/swfactory`; the factory makes no network calls.
- No change to the dismissal gate, the allowed reasons or the label format.

## Requirements

- R1. The skill and the policy state that grouping is the default: one Jira issue may carry several `finding-<source>-<id>`
  labels when the alerts are (a) the same Dependabot package in the same manifest file, or (b) the same code-scanning rule in
  the same file or the same module. Per-alert issues remain available when the human asks. The earlier "one issue per finding,
  do not merge" statement is replaced everywhere it appears in shipped text.
- R2. "Same module" is defined precisely: the same directory, meaning the part of the path before the last `/` of the alert's
  file (the repo root counts as one directory), not including subdirectories. Same file is the same directory, so one rule
  covers both. The group is identified by the issue summary: Dependabot `[<package>] <manifest path>`, code scanning
  `[<rule id>] <directory>/` (`./` for the root).
- R3. Every alert keeps its own label and its own re-query. The issue goes to Done only when all alerts it carries re-query as
  `fixed`; an open alert anywhere in the group blocks Done, and a dismissed alert counts only with the human-approved
  dismissal on record.
- R4. A new alert (no label in Jira yet) that fits an existing open group (an issue not Done whose summary is the group
  summary) adds its label and a comment to that issue; it does not create an issue. A new alert that fits only a Done group
  is filed as a new issue. An alert that already has a label and is open again reopens the issue that carries it (the
  existing reopen rule, unchanged). The group's priority is the highest severity among its alerts.
- R5. The batch limits count issues, not alerts: at most 10 new issues per run (a first sweep still files only `critical` and
  `high`); alerts that join an issue do not use up the cap. The report gives alerts and issues.
- R6. The skill, the policy, `factory-workflow`, `factory-release` and the docs agree, and the repo's managed copies are in
  sync (`factory sync --check .` exits 0, `factory lint` passes).

## Acceptance criteria

- AC1. (R1, R2, R6) The skill and the policy contain the grouping rule: default for same-package and same-rule alerts, the two
  conditions, the definition of module as the directory, the summary format that identifies a group, and that per-alert issues
  remain available on request. The sentence "One issue per finding. Do not merge several alerts into one issue" is gone from
  `skills/`, `policies/`, `kit/` and `docs/` (outside `docs/work/`). `factory-workflow` route row and `factory-release` step
  say that a grouped issue closes only on every alert. A test reads the real text and fails when any of this is removed.
- AC2. (R1, R2) In the walkthrough (fake `gh`, fake Jira): three Dependabot alerts for the same package and manifest become one
  issue carrying three labels; two code-scanning alerts for the same rule in different files of the same directory become one
  issue; the same rule in a different directory, a different rule in the same directory, and the same package in a different
  manifest each get their own issue. Two runs over the same alerts create one issue per group and no more (no duplicates,
  every alert reported as tracked on the second run). With per-alert mode (the human asked) the same alerts give one issue per
  alert.
- AC3. (R3) A group with one alert still `open` is not Done, the comment names the open alert, and the other alerts' states are
  not enough; when the last alert re-queries as `fixed` the issue is Done and the comment cites every alert URL and state.
  Failure paths: one `fixed` and one `dismissed` alert without recorded approval is not Done; a dismissed-with-approval alert plus
  fixed alerts is Done.
- AC4. (R4) A new alert of an existing open group, in a later run, adds its label and a comment and creates no issue; a higher
  severity raises the group priority. A new alert whose only matching group is Done creates a new issue, and the Done group
  stays Done. An alert of a Done group that is open again reopens that same issue.
- AC5. (R5) With alerts forming more than 10 groups, a run creates exactly 10 issues, the rest of the groups are reported as
  unfiled, and alerts that join groups created in the same run do not count toward the cap; the report states alerts found,
  alerts filed and issues created, and the counts differ when grouping happened (for example 15 alerts filed in 10 issues).
- AC6. (R6) `uv run python -m swfactory.cli sync --check .` exits 0, `factory lint` passes, and the full suite passes.

## Edge cases and failure modes

- A group issue is already In Progress or In Review when a new alert joins: the comment says the alert is new for that issue, the
  fix in flight may not cover it, and Done waits on it (R3 covers closure). No new issue is opened.
- Code-scanning alerts whose most recent instance has no file path: not grouped; one issue per alert.
- An alert that already has a label is never re-grouped or moved to another issue.
- Two open issues share a group summary (for example one created at the human's request): the lookup uses the first; the human
  can split later. Per-alert issues carry a different summary (code: with `:<line>`; Dependabot: with `(alert <id>)`) so they are never
  join targets.
- Scanner not enabled or Jira tools missing: unchanged from FACT-34.
- Large groups (40 alerts): one issue with 40 labels; Jira accepts that. One fix pattern, one bug work item, one PR is allowed.
  The bug spec lists the alerts it covers.

## Non-functional requirements

- Generic: no project names, hosts or ticket keys in shipped text (Treaty; `factory lint`). The `next` package and the project
  keys from the ticket stay out of skills, policy and tests.
- Security: `policies/security.md` and the dismissal gate are unchanged; secret values never go to Jira; alert text is data.
- Skill body stays within 150 lines.

## Assumptions

- "Same module" is the same directory (non-recursive). A stricter or looser unit (package, top-level folder) can be chosen
  later by amending the policy; the directory is the one definition that needs no language knowledge.
- The issue summary is the lookup key for an open group, because labels carry alert ids, not group keys; Jira's summary
  search is fuzzy, so the agent compares the returned summaries exactly.
- A Done group is never reopened for a brand new alert; a new issue keeps "Done" a true statement about the alerts it carried.
- A group takes the highest severity of its alerts as its priority.

## Risks and dependencies

- Medium: the change alters how a loop touching security alert states tracks work. Mitigated by keeping the closure rule per
  alert and pinning it with a test that an open alert in a group blocks Done.
- Wording in a markdown skill cannot be proven obeyed by an agent; the walkthrough pins the rules as functions.
- Existing per-alert issues and groups coexist; a new alert may join an old Dependabot issue only if its summary equals the group summary.
- Depends on FACT-34 (merged). Touches the same skill text as other open findings items; edits are local.

## Open questions

None. The owner-delegated decision and the corrected rule are in the FACT-38 comment of 2026-10-05.
