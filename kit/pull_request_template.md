## Work item

ID: <!-- e.g. F-001 or PF-12 -->
Spec: `docs/work/<id>-<slug>/spec.md` · Plan: `plan.md` · Test plan: `test-plan.md`

## Summary

<!-- What changed and why, in 2-3 lines. -->

## Acceptance criteria → tests

| AC | Test(s) | Passing |
|----|---------|---------|
| AC1 |  |  |

## Risk and verification

Risk: low / medium / high — <!-- why -->
How verified: <!-- commands run, manual checks, environment -->
Rollback: <!-- how to undo; required for medium/high -->

## Human gates

- [ ] Spec approved (`approvals.spec` in `item.yaml`)
- [ ] Plan approved (`approvals.plan`, unless waived by autonomy rules)
- [ ] Reviewed against the spec by a human
- [ ] Production release needs a separate human go-ahead

## Security

- [ ] No secrets, tokens or PII in code, logs, fixtures or this PR
- [ ] Inputs validated at boundaries; authn/authz checked where relevant
- [ ] New dependencies reviewed and pinned (or none added)
- [ ] CI/infra changes called out (or none)
