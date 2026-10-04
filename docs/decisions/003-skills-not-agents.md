# ADR-003 — One engineer-agent with skills, not a fleet of role agents

**Status:** accepted · 2026-10-04

**Context.** "Product agent, architect agent, QA agent…" is the common demo architecture. It multiplies
runtimes, contracts and failure modes before a single feature ships.

**Decision.** One capable agent; behaviour comes from skills (`factory-spec`, `factory-plan`, …) and a router
skill (`factory-workflow`). Independent reviewer roles come later, when a concrete escaped defect or a
`risk: high` item justifies them (ROADMAP).

**Consequences.** + Agent-neutral (Claude Code, Copilot, others read the same SKILL.md/AGENTS.md).
− Self-review bias until independent review exists; mitigated by `factory-review` forcing a different stance
and by human gates.
