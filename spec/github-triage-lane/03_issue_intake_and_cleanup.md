# Spec 03: Issue Intake And Cleanup
**Goal:** Make new GitHub issues easier to classify and apply the triage lane to the current public queue.
**Depends on:** Spec 01, Spec 02

## Requirements
- Add GitHub issue templates for genealogy help requests, usage questions, documentation improvements, and blank issue guardrails.
- Update contribution docs with maintainer triage guidance.
- Generate a UAT checklist for the triage lane.
- Use the report to label, comment, close, merge, or defer current public issues and PRs.

## Files
- Create: `.github/ISSUE_TEMPLATE/genealogy_request.yml`
- Create: `.github/ISSUE_TEMPLATE/usage_question.yml`
- Create: `.github/ISSUE_TEMPLATE/documentation_improvement.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Modify: `CONTRIBUTING.md`
- Create: `spec/github-triage-lane/uat.md`

## Boundary Map
- **Produces**: Structured issue intake, UAT checklist, cleaned public queue.
- **Consumes**: `scripts/github-triage` report from Spec 02.

## Acceptance Criteria
- [ ] Issue templates exist and collect enough information to triage without exposing living-person details.
- [ ] Contributing docs explain the safe PR gate.
- [ ] UAT covers static files, command checks, and human review.
- [ ] Current issues and PRs have an explicit maintainer outcome.

## Test Plan
- Run `scripts/validate-repo`.
- Run `scripts/github-triage report`.
- Verify issue template YAML is parseable by Ruby YAML safe load.
