# FACT-19 — Delegated approvals as a first-class form

Status: in-review · Risk: medium · Jira: FACT-19
Created: 2026-10-05 · Slug: delegated-approvals-as-a-first-class

## Problem

When an owner delegates spec or plan approval to an agent, `factory approve` records the local git user name,
so the ledger would claim the owner approved it. Agents therefore hand-write
`by: "<owner> (delegated to agent)"` into `item.yaml`. That works but is unchecked, inconsistent, and invisible in
`factory status`. The policies (`autonomy.md`, the AGENTS block, `factory-workflow`) also say "never approve"
without saying when delegation is valid, so the delegated run contradicted the written rules.

## Users and context

An owner who delegates gates to agents, and the agents working the factory's work items.
Modules: `src/swfactory/work.py` (`cmd_approve`, `collect_status`), `src/swfactory/commands/work.py`,
`src/swfactory/verify.py` (schema), `policies/autonomy.md`, `kit/AGENTS.block.md`,
`skills/factory-workflow/SKILL.md`, `docs/ARCHITECTURE.md` 3.2. The approval is still a ledger, not a lock.

## Goals and non-goals

**Goals**
- A CLI form that records a delegated approval consistently and unmistakably.
- `verify` accepts both the new form and the existing hand-written form; non-delegated approvals are unchanged.
- `factory status` shows when an item carries a delegated approval.
- Policy and skills say when delegation is valid and that production is never delegable.

**Non-goals**
- A config key in `factory.yaml` that pre-authorises delegation (the instruction stays a recorded owner instruction).
- Proving that the owner really delegated (a ledger cannot).
- Delegating production go-ahead (never allowed).

## Requirements

- R1. `factory approve <id> spec|plan --delegated "<who>"` records `by: "<who> (delegated to agent)"`, `at`, and `delegated: true`.
- R2. `--delegated` with an empty name is an error and writes nothing. Without `--delegated` behaviour is unchanged.
- R3. `verify` accepts `delegated: true` records and the older hand-written `by: "<who> (delegated to agent)"` form;
  it rejects a `delegated` value that is not a boolean and a `delegated: true` record whose `by` does not carry the suffix.
- R4. `factory status` marks an item that has a delegated approval (flag or suffix form).
- R5. `policies/autonomy.md` (and its kit copy) describe when delegation is valid: an explicit recorded owner
  instruction naming the gates, recorded with `--delegated`, never for production. The kit AGENTS block agrees.
- R6. The `factory-workflow` skill says an agent may approve only under such a delegation and only with `--delegated`.
- R7. ARCHITECTURE 3.2 and 3.7 document the form and the CLI flag.

## Acceptance criteria

- AC1. (R1, R2) Given an item at `draft` with a real spec, `approve <id> spec --delegated "Jane Doe" --yes` sets
  `approvals.spec` to `{by: "Jane Doe (delegated to agent)", at: <today>, delegated: true}` and status `spec-approved`.
  `--delegated ""` and `--delegated "   "` exit 1, change nothing. An approve without the flag still records the git user name and no `delegated` key.
- AC2. (R3) `verify` passes an item with a `delegated: true` record, and one with the hand-written suffix form and no flag;
  it fails `delegated: "yes"` and `delegated: true` with a `by` lacking the suffix; an ordinary record still passes.
- AC3. (R4) `factory status` shows `(delegated)` next to the status of an item whose approvals include either form,
  and nothing extra for an ordinary item.
- AC4. (R5, R6, R7) `policies/autonomy.md`, `kit/AGENTS.block.md`, `kit/work-README.md`, `skills/factory-workflow/SKILL.md` and
  ARCHITECTURE describe delegation as above; `factory lint` passes and `factory sync --check .` is clean after `factory sync .`.
- AC5. (R1) Re-approval with `--delegated` on an amended doc refreshes the ledger entry and keeps the status (same rule as an ordinary re-approval).
