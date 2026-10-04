# {{id}} — {{title}}

Status: draft · Risk: {{risk}} · Jira: {{jira}}
Created: {{date}} · Slug: {{slug}} · Spec: spec.md

<!--
GUIDANCE (delete every comment like this one before asking for approval).
The plan turns the APPROVED spec into an executable sequence for an agent that has not seen the
conversation. Name real files, modules and functions you have read; no hypothetical architecture.
The plan must not contradict spec.md. If the spec is wrong or incomplete, stop and amend the spec
first (and say so in notes.md) — do not paper over it here.
Unknowns: use the NEEDS CLARIFICATION marker (square brackets, see factory-spec); approval is blocked
while any remains.
-->

## Summary

<!-- 2-3 sentences: what will change and the shape of the solution. -->

**Size:** <!-- S (< ~half a day) | M (~1-2 days) | L (~3-5 days); if bigger than L, say how to split it -->

## Current state

<!-- What exists today, with paths: the modules, tables, endpoints, configs this change touches or
must stay compatible with. Include how the project runs lint/tests (the commands). -->

## Approach

<!-- The chosen design and why it is the smallest thing that satisfies the spec. -->

**Alternatives rejected**
- <!-- option — why not (1-3 lines each) -->

## Tasks

<!-- Ordered small to large; each task independently verifiable and committable. Map every task to the
acceptance criteria it serves; every AC from spec.md must appear in at least one task.
"Verify by" is a concrete command or observable result, not "looks right". -->

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | | | AC1 | |
| T2 | | | AC1, AC2 | |

## Data, API and migration impact

<!-- Schema changes, new/changed endpoints or CLI flags, config/env vars, backwards compatibility,
migration steps and their reversibility. Write "none" if none. -->

## Security and failure modes

<!-- Authn/authz, input validation, secrets, PII, dependency risk (see .factory/policies/security.md).
Then: what fails, how it shows up (logs/metrics/errors), and what the user sees. -->

## Rollout and rollback

<!-- Flags, staged release, order of deploys vs migrations, how to verify in each environment, and the
exact steps to undo (revert commit? down-migration? flag off?). Name the point of no return, if any. -->

## Risks and open points

<!-- What could invalidate this plan and the signal that would tell you. -->

-
