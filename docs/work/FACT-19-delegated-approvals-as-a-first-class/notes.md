# Notes

- 2026-10-05: the run brief and Jira disagree on keys: the brief called this FACT-20 (and the status-after-merge ticket FACT-19);
  Jira has them the other way round. The ticket content is unambiguous, so this item uses the Jira key FACT-19.
- 2026-10-05: this item's own approvals are written by hand in the new form, because the CLI flag did not exist yet.
- 2026-10-05: first mutation run for the `is_delegated` suffix case did not apply (ruff had reflowed the line, so the
  sed matched nothing and the run looked green). Caught by comparing against the expected failure; redone and failing as it should.
