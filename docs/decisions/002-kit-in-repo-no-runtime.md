# ADR-002 — Kit-in-repo: no runtime dependency after adoption

**Status:** accepted · 2026-10-04

**Context.** Real engineering often happens inside environments we don't control: customer GitHub, customer
Jira, customer policies, code and context that must not leave. A factory that has to be reachable at runtime
is unusable there.

**Decision.** `factory adopt` copies everything a project needs into the project (`AGENTS.md` block, skills,
policies, CI workflow, standalone `.factory/verify.py`). Skills must be executable with only git + file
access; the CLI is a convenience. `verify.py` is stdlib + PyYAML and runs without the factory installed.

**Consequences.** + Works offline/air-gapped and inside customer repos; survives the factory repo vanishing.
− Copies drift; we need hashes, `sync`, and conflict reporting (implemented as managed/create/block modes).
