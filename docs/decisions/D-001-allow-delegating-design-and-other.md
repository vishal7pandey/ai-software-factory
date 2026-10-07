---
id: D-001
type: design
title: Allow delegating design and other decisions to an agent
status: proposed
jira: FACT-46
proposed_by: Claude (agent)
proposed_at: '2026-10-07'
options:
- text: Allow --delegated for design and other decisions only, with an explicit recorded owner instruction; never for charter or dismissal
  recommended: true
- text: Never allow delegation of any decision (remove the --delegated form from decide)
- text: Allow delegation for every type, like approve
decision: null
by: null
at: null
delegated: false
---
# Allow delegating design and other decisions to an agent

## Context

FACT-46 adds `factory decide`, the owner's answer to a decision record. The ticket asks that it behaves like
`factory approve`, including the `--delegated "Owner"` form, while the run brief says decisions and charters are never
delegated to an agent. The two cannot both hold literally, so the build chose the narrowest reading and the owner
should confirm or change it.

## Evidence

- `approve` allows a recorded owner delegation for spec and plan only, never for production (`policies/autonomy.md`).
- A `dismissal` is a security exception (`policies/findings.md`) and a `charter` is the owner's definition of done.
- A `design` or `other` decision can be low-stakes and time-critical (for example a naming choice during a delegated run).
- Built as proposed: `decide --delegated` writes `by: "<owner> (delegated to agent)"`, `delegated: true`; it is refused for
  `charter` and `dismissal`, and `verify` fails such a record written by hand.

## Options

1. Delegation for `design` and `other` only (recommended): keeps the escape hatch the ticket asked for, closes it for the
   two types that carry real authority, and stays visible (`delegated: true`) in the record and in review.
2. No delegation at all: simplest and strictest; a delegated run would stop and wait for the owner on every choice.
3. Delegation for every type, like `approve`: most flexible, but lets an agent accept its own dismissal or charter
   when told to, which the owner said must never happen.

## Recommendation

Option 1: it matches the ticket's `approve`-like form where the stakes are low and refuses it where they are not.
