# Spec 02: Durable Triage State
**Goal:** Add local tooling that keeps GitHub issue and PR state synchronized without giving an agent merge authority.
**Depends on:** Spec 01

## Requirements
- Add a script that fetches open issues and PRs through `gh`.
- Store fetched state in a local ignored database file.
- Classify items as repair-ready, needs human review, needs information, spam, duplicate, draft, or privacy-risk.
- Emit a markdown report with recommended action and validation status.
- Keep write operations out of the script unless a maintainer explicitly runs GitHub commands.

## Files
- Create: `scripts/github-triage`
- Modify: `.gitignore`
- Create: `reference/github-triage-lane.md`

## Boundary Map
- **Produces**: `scripts/github-triage`, local triage state, markdown report.
- **Consumes**: Green validator from Spec 01, GitHub CLI authentication.

## Acceptance Criteria
- [ ] `scripts/github-triage --help` prints usage.
- [ ] `scripts/github-triage sync --repo mattprusak/autoresearch-genealogy` writes local state.
- [ ] `scripts/github-triage report --repo mattprusak/autoresearch-genealogy` prints markdown.
- [ ] Generated state is ignored by Git.

## Test Plan
- Run help, sync, and report commands.
- Run `git status --ignored --short .github-triage` to confirm state is ignored.
- Run repository validation after adding the script and docs.
