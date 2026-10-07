---
id: D-002
type: charter
title: Approve the factory project charter
status: proposed
jira: FACT-47
proposed_by: Claude (agent)
proposed_at: '2026-10-07'
options:
- text: Approve the charter in docs/PROJECT.md as written
  recommended: true
decision: null
by: null
at: null
delegated: false
subject: docs/PROJECT.md
---
# Approve the factory project charter

## Context

FACT-47 gives every project a written definition of done and a stop rule, so scope stops growing by default. The
factory is the first project to get one. This record asks the owner to approve (or send back) the proposed
`docs/PROJECT.md` of the factory repo: purpose, six done criteria for a "v1.0", non-goals, a parked list and the
maintenance-mode rule. Approving stamps the file's hash; any later edit needs a new charter decision.

## Evidence

- Done criteria, each with a reference the factory checks offline (`factory status` shows them): C1 the golden path
  exists as skills (`skills/factory-workflow/SKILL.md`), C2 findings loop (FACT-34, merged), C3 dependency loop (FACT-39,
  merged), C4 decision gate (FACT-46, merged), C5 project charter (FACT-47, merged with this change), C6 generality audit
  and supported-today matrix (FACT-48, not started: the only criterion not met).
- Non-goals come from ADR-001 and `docs/ROADMAP.md` ("if no project has needed it yet, it does not exist").
- Parked: the "Next" items of `docs/ROADMAP.md`, each with its trigger, none triggered yet.
- `factory doctor` shows `no approved charter` until this is decided; `factory status` shows the criteria once it is.

## Options

1. Approve the charter as written (recommended): the factory has an end (v1.0 when C1 to C6 are met) and a stop rule
   (maintenance mode: only security and dependency updates, anything else needs an amendment).
2. Send it back (`factory decide D-002 --reject --note "..."`): the agent revises `docs/PROJECT.md` and proposes again,
   for example with other criteria or another parked list.

## Recommendation

Approve as written: five of six criteria are already met, so v1.0 is one ticket (FACT-48) away, and the parked list keeps
the roadmap honest. If the owner wants a different bar for "done", reject with a note naming it.
