---
# The charter of the factory itself, a proposal for the owner. It is approved only through decision record D-002
# (`factory decide D-002 --accept`, run by the owner); until then `factory doctor` says "no approved charter".
purpose: "The factory is the engineering method (skills, policies, templates) plus a thin CLI that lays that method into real projects and keeps their work items honest. It owns the method, not the platform: Git, the tracker, CI and the coding agent stay somebody else's job."
mode: active
decision: D-002
done:
  - id: C1
    text: "The golden path from spec to release exists as skills and is enforced by verify"
    check: {file: skills/factory-workflow/SKILL.md}
  - id: C2
    text: "The findings loop turns scanner alerts into tracked and scanner-confirmed closed bugs"
    check: {work: FACT-34}
  - id: C3
    text: "The dependency loop lets an agent merge only Dependabot pull requests that meet every condition"
    check: {work: FACT-39}
  - id: C4
    text: "Owner decisions are recorded in the repository and listed in one inbox"
    check: {work: FACT-46}
  - id: C5
    text: "A project charter with measurable done criteria is approved through the decision gate"
    check: {work: FACT-47}
  - id: C6
    text: "The generality audit and the supported-today matrix are published and tested"
    check: {work: FACT-48}
non_goals:
  - "Owning a platform: an agent runtime, an orchestrator, a workflow engine or a dashboard (ADR-001)"
  - "Replacing Git, the tracker, CI or the coding agent"
  - "Storing state outside the project's own repository (no database, no daemon)"
  - "Supporting every stack before a real project needs it (docs/ROADMAP.md rule)"
parked:
  - {item: "Independent reviewer agent, until a defect escapes the implementer's own review", jira: null}
  - {item: "factory eval, replaying historical tasks with and without skills", jira: null}
  - {item: "Jira REST adapter in the CLI, until an agent without Atlassian tools must take part", jira: null}
  - {item: "factory-infra repository for deployment targets", jira: null}
  - {item: "Telemetry to bug loop", jira: null}
  - {item: "Cross-project memory and a dashboard", jira: null}
---
# The factory charter

The factory is finished as a v1.0 when the six criteria above are all met: the method (C1), the two loops that keep
a project's findings and dependencies honest (C2, C3), the gate that records what the owner decides (C4), the charter
that says when a project is done (C5), and an honest account of what the factory supports today (C6). The parked list
is what the owner has deliberately not asked for; each item stays parked until the trigger written in
`docs/ROADMAP.md` fires.

## Maintenance mode

When every done criterion is met the factory enters maintenance mode (`mode: maintenance`, approved through a new
charter decision). In maintenance mode only security and dependency updates are made, through the findings and
dependency loops (`factory-findings`, `factory-dependencies`). Any other change needs a charter amendment: a new
charter decision the owner accepts. `factory feature start` warns, but does not block, so the owner can proceed
deliberately.
