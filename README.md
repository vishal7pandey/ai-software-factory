# AI Software Factory

A personal software factory built on one rule:

> **The factory must not own what the platform already provides.**

GitHub is the system of record for code, Jira for work, Actions for CI, and Claude Code / Copilot
for the engineering. This repo owns only the **method** — skills, policies, templates — and a thin
CLI that lays the method into real projects and keeps work items honest.

Everything the factory gives a project is **committed into that project** (`AGENTS.md`, skills,
policies, CI, a standalone `verify.py`). No factory runtime is needed afterwards, so it works in
environments where only git and a coding agent are available.

## Quick start

```bash
uv sync
uv run factory doctor                        # are my tools ready?
uv run factory adopt ../my-project --dry-run # findings + what would be added (runs no project command)
uv run factory adopt ../my-project           # also runs the generated CI's commands locally; --no-check skips
cd ../my-project
uv run --project ../ai-software-factory factory feature start "Add Google login" --jira PF-12
```

Then drive the work item with your coding agent: `factory next PF-12` prints the right prompt for
the current state (spec → plan → test plan → implement → review → release).

## Where to read next

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — principles and the contracts (the "Treaty")
* [docs/ROADMAP.md](docs/ROADMAP.md) — what's next and what would justify building it
* [docs/decisions/](docs/decisions/) — why it is shaped this way
* [skills/](skills/) — the method itself
