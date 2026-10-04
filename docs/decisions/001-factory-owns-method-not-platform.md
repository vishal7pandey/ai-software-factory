# ADR-001 — The factory owns method, not platform

**Status:** accepted · 2026-10-04

**Context.** The tempting build is an "AI software platform": orchestrator, agent runtime, dashboard,
workflow engine. Every piece duplicates something GitHub, Jira, Actions or the coding agents already do,
and ages as they improve.

**Decision.** The factory owns only (a) skills, (b) policies, (c) templates, (d) a thin CLI that installs
them and checks work items. Git/PRs → GitHub. Work tracking → Jira. CI → GitHub Actions. Engineering → the
user's coding agent.

**Consequences.** + Small surface; replaceable workers; nothing to operate. − Gates are only as strong as
GitHub's branch protection (see ARCHITECTURE honesty clause). − We cannot build features that need a
central runtime (cross-project dashboards) without revisiting this ADR.
