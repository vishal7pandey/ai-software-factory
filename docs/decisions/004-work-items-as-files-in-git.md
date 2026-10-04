# ADR-004 — Work item state and evidence are files in the repo

**Status:** accepted · 2026-10-04

**Context.** State could live in Jira, a database, or the repo. Jira is great for humans and portfolio views
but may be unavailable to the agent or the CI job, and is not committed with the code.

**Decision.** `docs/work/<id>-<slug>/item.yaml` + markdown artifacts are the source of truth for status,
approvals and evidence, committed with the change. Jira is optional and mirrors status via the agent's own
tools; the CLI does not call Jira in V1.

**Consequences.** + `verify` can gate in CI with no network; "why does this code exist?" is answerable
from the repo. − Two places to keep in sync when Jira is used; accepted until the Jira adapter trigger fires.
