# FACT-33 notes

2026-10-05 amendment to spec.md (edge cases): `doctor` on a project with no github.com `origin` prints one
`ok`-level `skipped` line instead of `unknown`. Why: `tests/test_integration.py` requires a clean doctor
for a freshly adopted, local-only project, and a project with no GitHub repo has nothing to check; a WARN
there would be noise on every new project. AC3 is unchanged (it is about `gh` failures). Spec re-approved
under the same delegation.
