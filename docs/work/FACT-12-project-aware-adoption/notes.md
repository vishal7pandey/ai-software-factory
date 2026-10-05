# Notes — FACT-12

## 2026-10-05: approvals (agent, under delegated authority)

Spec and plan approved by the agent under the owner's explicit delegation (2026-10-05); recorded as
`by: "Vishal Pandey (delegated to agent)"`, not as the owner's own act. The spec is the Confluence page
"FACT-12 Spec: Project-aware adoption" with its open question decided (assumption A1), two added
requirements (R5 default branch in the generated CI, R8) and acceptance criteria made testable.

## Proof on throwaway copies (T8)

Copies were made with `git archive HEAD` of the two adopted projects (tracked files only, so no `.env`,
no virtualenv), the adoption artifacts and the factory block were removed, and a fresh `git init -b master`
was made in a temp directory. `FACTORY_REGISTRY` pointed at a temp file. The real projects were only read.

* ade copy, `adopt --dry-run` and a real `adopt`: findings print
  `default branch: master` and ``push`/`pull_request` runs only on main, but the default branch is master``
  for the existing `.github/workflows/ci.yml`; the existing CI is not touched and no command runs;
  its AGENTS.md already had a `## Commands` section, so no TODO is added. `sync --check` afterwards: exit 0.
* chatpid copy (AGENTS.md without its commands section, CI removed): `--dry-run` reports
  `checks not run (--dry-run runs no project command)` and `would add a commands TODO section`;
  real `adopt` ran uv for real (about 3 minutes for the first `uv sync`) and reported
  `all 4 step(s) passed locally`; the generated CI has `branches: [master]` and
  `uv sync --all-extras --all-groups`.
* Same copy with one unused import added: result line
  ``removed failing step `uv run ruff check .` (Found 1 error.)``; the CI keeps `ruff format --check`
  and `pytest`, with a two-line comment where the step was. A second adopt prints `up to date`.
* Defect found by this proof and fixed: `uv run` inside the project warned about the factory's
  `VIRTUAL_ENV`; the project commands now run without it.
