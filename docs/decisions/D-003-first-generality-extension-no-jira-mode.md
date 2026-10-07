---
id: D-003
type: design
title: 'Choose the first generality extension: a first-class no-Jira mode'
status: proposed
jira: FACT-48
proposed_by: Claude (agent)
proposed_at: '2026-10-07'
options:
- text: 'Make tracker none first-class: skills read tracker.kind and the findings loop works without Jira (GitHub Issues as a later step)'
  recommended: true
- text: Do nothing now; keep docs/SUPPORT.md honest and extend only when a project needs it
- text: Make tracker github real first (GitHub Issues as the tracker, issue numbers as work item ids)
- text: Add a third stack template, Go (CI, SonarCloud, Dependabot gomod, detection, factory new)
- text: Add a plain static-site stack template (build, link check, Pages)
decision: null
by: null
at: null
delegated: false
---
# Choose the first generality extension: a first-class no-Jira mode

## Context

FACT-48 audited what the factory assumes (`docs/SUPPORT.md`, `docs/ARCHITECTURE.md` 3.13, and the Confluence page
"Factory generality: assumptions and roadmap" in space FACT). The owner goal is a factory that can build any project.
The ticket asks for one extension to be proposed, chosen for the best value for its effort, for the owner to decide
here. Nothing below is built until you accept an option; every option also leaves the matrix check in place.

## Evidence

- Today a project needs a Jira project and a Confluence space before the first work item (docs/jira-workflow.md,
  "Create-by-hand checklist", steps 1 and 2). Seven of the ten skills (`factory-workflow`, `-spec`, `-plan`,
  `-diagnose`, `-release`, `-findings`, `-dependencies`) speak Jira and none reads `tracker.kind` from
  `.factory/factory.yaml`. The findings loop can only file Jira bugs.
- The CLI is already most of the way: `adopt` defaults to `tracker: none`, `feature start` without `--jira` gives
  `F-###` and `B-###` ids, `verify` accepts them, decisions and charter need no tracker (FACT-46, FACT-47). Shown by
  tests and the e2e-001 scratch project, by no real project (SUPPORT.md, tracker `none`: partial).
- `tracker: github` is accepted and recorded but nothing reads it (SUPPORT.md: not supported, inert).
- No stack outside python (and node, by tests only) has a template; a Go or static-site project is adopted as `other`
  with a placeholder CI. Each new stack unlocks one kind of project and needs CI, Sonar, Dependabot and detection.
- Effort and value scores, and the full ranked list, are on the Confluence page.

## Options

1. **First-class `tracker: none` (recommended).** Skills branch on `tracker.kind`: with `none`, no Jira comments or
   transitions, ids are `F-###`/`B-###`, the findings loop turns a scanner alert into a bug work item whose
   `notes.md` first line carries `finding-<source>-<id>` (the same dedupe key, searched with git), and
   `docs/jira-workflow.md` gets a sibling for the tracker-less path. Cost: about two days (seven skill edits, one
   findings path, tests that pin them, a scripted walkthrough with a fake `gh`, the scratch proof). Closes off nothing:
   GitHub Issues becomes a small second step on top.
2. **Do nothing now.** Zero cost, the matrix stays the honest account. Follows the roadmap rule "if no project has
   needed it yet, it does not exist". The cost lands on the next project without Jira, which would translate seven
   skills by hand on day one.
3. **GitHub Issues as the tracker.** Real `tracker: github`: an id scheme for issue numbers, `gh issue` calls in the
   skills and findings loop, a status mapping. More value than option 1 for a GitHub-only owner but about three to five
   days, and it needs option 1's branching first.
4. **Go template.** About two days for one stack: `kit/ci/go.yml`, `kit/sonar/go.*`, a `gomod` Dependabot fragment,
   `detect_stack`, `templates/go`. Real value only when a Go project exists; none does.
5. **Static-site template.** Smallest effort (about one day: build, link check, Pages), smallest value.

## Recommendation

Option 1. It has the best value for its effort: it applies to every stack and every future project, it removes the
heaviest hidden requirement (an Atlassian project and space per project), most of the machinery already exists in the
CLI, and it is the groundwork for GitHub Issues. Honest counterweight: the roadmap rule asks for a project that needs it,
and today the trigger is your stated goal (any project, including ones like those under `learning/`) rather than a
blocked project; if you do not want to build ahead of a need, choose option 2.

### Proposed spec if you accept option 1 (a new work item, approved through the normal gates)

- Scope: skills read `tracker.kind`; `none` skips every Jira step; the findings loop and `factory-release` have a
  tracker-less path; `docs/jira-workflow.md` is joined by a no-tracker page; `doctor` and `status` stay clean for a project
  with no tracker. Out of scope: GitHub Issues, any CLI network call, changing the Jira path.
- Acceptance criteria: (1) a scripted findings walkthrough with a fake `gh` files one bug work item per alert group
  without Jira and a rerun creates no duplicate; (2) a test pins that each of the seven skills names the `none` path and the
  Jira path unchanged; (3) a scratch GitHub project adopted with `--tracker none` runs one work item end to end
  (spec, plan, test plan, PR) with `verify` green and CI green; (4) `factory doctor` on it prints no WARN or FAIL.
- Proof: the scratch repository, its CI run and its doctor output, recorded on the work item. SUPPORT.md row
  `tracker none` moves to `supported` only when a real project uses it; until then it stays `partial`.
