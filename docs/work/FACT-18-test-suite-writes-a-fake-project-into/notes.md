# Notes

- 2026-10-05: the ticket's symptom (every `pytest` run adds `sample-app` to the real registry) does not reproduce
  on current `main`: all existing tests redirect by hand. The registry entry in the developer's home dates from an
  earlier state (its temp path is from pytest run 36; the suite is now past run 119). The defect fixed here is the
  missing harness-level guarantee, proven with a mutation. The stale `paths.sample-app` entry is left alone on
  the owner's instruction.
- 2026-10-05: guard is path-based rather than a hash compare inside the suite, so a second process legitimately
  changing the real registry mid-run cannot fail the suite.
- Learning: a feature that writes outside the repo needs an isolation guard in the test skill (candidate for
  `factory-test`; not done here, scope).
