# Notes

- 2026-10-05: the run brief and Jira disagree on keys; this item uses the Jira key FACT-20 (status after merge).
- 2026-10-05: flaw in the recommended option (a), handled in the plan: it can only reach `merged`, never `done`.
  The owner's AC wording ("status --all shows merged work as done") is therefore met as "shows merged work as
  complete" for projects without environments; with environments `merged` still routes to `factory-release`.
- 2026-10-05: this item dogfoods the rule: the last commit on its branch sets `status: merged`.
- Open point for the owner: setting `merged` one step before the merge is a convention, not enforced. A post-merge
  check (option b or c) can replace it later if it proves unreliable.
