# Roadmap

Rule: **if no project has needed it yet, it does not exist.** Each item below names the trigger that
would justify building it. Until the trigger fires, it stays here.

## V1 — golden path (this repo, now)

Idea → spec → plan → test plan → implement → PR → review → CI gate → release, for features and
bugs, on any repo that has adopted the kit. Skills + thin CLI + standalone `verify.py`.
**Exit criterion:** one real work item per adopted project has gone end to end with the factory
(spec and plan approved, PR merged, evidence committed) and we have written down what hurt.

## Next — in likely order

| Item | Trigger that justifies it |
|---|---|
| `factory-incident`, `factory-refactor`, `factory-security` skills | The router sends the same kind of work through the generic path 3+ times and the improvised steps keep being re-explained |
| Independent reviewer (separate agent/model reviews what another wrote) | A defect escapes that the implementing agent's own review missed — or any work item rated `risk: high` |
| `factory eval` — replay 10–20 historical tasks, compare with/without skills | We want to change a skill and need to know it didn't get worse; also the honest way to test "do skills actually help" |
| Jira REST adapter in the CLI | Agents without Atlassian MCP need to participate (CI-driven or non-Claude agents) |
| `factory-infra` repo: Cloudflare Pages/Workers, Supabase, Infisical, OpenTofu | First project that must deploy somewhere that isn't a laptop |
| Telemetry → Jira bug loop (alert → draft bug item) | A project in prod with real alerts |
| Cross-project memory ("build this like my other apps") | ≥3 adopted projects with patterns worth reusing; start with a `patterns/` folder of examples before anything vector-shaped |
| Stack templates: node/Next.js, Cloudflare Worker | Starting a new project of that kind |
| Dashboard | Never, until `factory status` across the registry feels inadequate |

## Explicitly rejected (for now)

Kubernetes, LangChain/LangGraph as foundation, a custom agent runtime, a workflow engine,
a proprietary state store, a vector DB. Reconsider only with an ADR that names the concrete failure
of the boring alternative.

## Open questions

* Do skills belong in `.claude/skills` **and** `.github/skills`, or does one target suffice for the
  agents actually used? (Currently both; copying is cheap, but verify against each agent's docs.)
* Where should the approval lock really live — CODEOWNERS on `docs/work/**`, or a required GitHub
  Environment review? Needs a private-repo plan check (environment protections are limited on Free).
* How much of `AGENTS.md` should the managed block own before it starts fighting project-specific text?
