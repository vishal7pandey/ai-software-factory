# Notes — FACT-16

## 2026-10-05: approvals and amendments (agent, under delegated authority)

- Spec and plan approved by the agent under the owner's explicit delegation (2026-10-05); recorded as
  `by: "Vishal Pandey (delegated to agent)"`, not as the owner's own act.
- Spec amendment to AC5: the search may also hit `LICENSE` (MIT copyright holder line, added by FACT-13
  after this spec was written) and the lint rule's own `atlassian.net` literal and its tests. Neither is
  instance data.
- Spec amendment to R7: `factory lint` does not scan `docs/work/`: the factory's own evidence trail
  (specs, Jira and Confluence references) is project history, not shipped content.
- Migration done once by hand on the maintainer machine: the old committed registry and local paths
  were copied into `~/.factory/registry.yaml` before `registry/` was deleted.
