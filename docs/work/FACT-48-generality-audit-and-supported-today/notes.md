# Notes: FACT-48

2026-10-07 amendment to spec.md (R2, AC3, AC4, edge cases): while wiring `factory lint`, the first draft of AC4 used
`templates/go`. The real matrix already has a `go` row marked `not supported` (the audit lists the stacks that are not
supported), so a `templates/go` directory passed the check: a stack with a row was enough. That is the wrong way for the
matrix to rot, a template arriving while its row still says `not supported`. The check now also fails on that, and AC4
uses `templates/swift` (no row) and `templates/go` (stale row). Spec re-approved, delegated, same wording of authority.
