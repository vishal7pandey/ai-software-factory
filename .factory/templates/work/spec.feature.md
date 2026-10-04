# {{id}} — {{title}}

Status: draft · Risk: {{risk}} · Jira: {{jira}}
<!-- factory:unfilled - delete this line when the document is really written; approval and verify refuse it -->
Created: {{date}} · Slug: {{slug}}

<!--
GUIDANCE (delete every comment like this one before asking for approval).
Write for a reader who has not seen the conversation: a reviewer, or an agent picking this up next week.
Describe WHAT and WHY, not HOW — design belongs in plan.md.
Unknowns: use the NEEDS CLARIFICATION marker (square brackets, exact syntax in factory-spec) inline where
the answer is missing. Approval is blocked while any marker remains, so resolve or convert each to a
stated assumption before handover.
-->

## Problem

<!-- Who hurts, when, and what it costs today. 2-5 sentences. No solution language. -->

## Users and context

<!-- Who uses this (role, not "the user"), in what situation, and where in the product it lives.
Name the existing modules/docs you read to ground this. -->

## Goals and non-goals

**Goals**
-

**Non-goals** <!-- things a reasonable reader might assume are included but are not -->
-

## Requirements

<!-- Numbered, one behaviour each, stated as what the system does ("The system rejects ..."),
using must/should consistently. Every requirement must be covered by at least one acceptance criterion. -->

- R1.
- R2.

## Acceptance criteria

<!-- Numbered AC1... Each one observable and testable by someone who did not write the code:
concrete inputs, concrete expected outputs/states (status codes, messages, rows, files).
Given/When/Then is allowed, not required. No "works well", "is fast", "user-friendly".
Reference the requirement(s) it proves, e.g. (R1). Include at least one failure-path criterion. -->

- AC1. (R1)
- AC2. (R2)

## Edge cases and failure modes

<!-- Empty input, duplicates, concurrency, partial failure, permissions, large volumes, timeouts,
third-party outage. State the expected behaviour, or why it is out of scope. -->

-

## Non-functional requirements

<!-- Only those that apply, each with a number or a policy reference: performance, security/privacy
(see .factory/policies/security.md), accessibility, observability, compatibility, data retention. -->

-

## Assumptions

<!-- Decisions you made without asking. Each one is a thing the human can overrule at approval. -->

-

## Risks and dependencies

<!-- What could make this wrong, costly or late: other teams, migrations, unclear ownership.
Justify the Risk level in the header (low = easily reversible, internal; high = money, auth, personal
data, irreversible migrations, many users). -->

-

## Open questions

<!-- Questions asked of the human, with your recommended answer. Remove the section once all are
answered; if any is still open, it must also appear as a NEEDS CLARIFICATION marker above. -->

-
