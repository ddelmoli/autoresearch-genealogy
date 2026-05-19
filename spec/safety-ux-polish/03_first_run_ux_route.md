# Spec 03: First-Run UX Route

**Goal:** Make the beginner path consistent and navigable.

**Depends on:** 02

## Requirements

- Remove expansion-first contradictions from README, prompts README, and getting-started workflow.
- Add a download-first path for users who do not use Git.
- Convert primary first-run raw paths into markdown links.
- Add validation that blocks reintroducing expansion-first beginner guidance.

## Files

- Create: `guides/download-and-start.md`
- Modify: `README.md`
- Modify: `START_HERE.md`
- Modify: `prompts/README.md`
- Modify: `workflows/getting-started.md`
- Modify: `guides/no-obsidian-setup.md`
- Modify: `scripts/validate-repo`

## Acceptance Criteria

- [ ] Beginner docs route to privacy, source inventory, and verification before expansion.
- [ ] Git is optional in the first-run path.
- [ ] Primary route references are clickable links.
- [ ] Validator fails on known expansion-first phrases.

## Test Plan

- Run `scripts/validate-repo`.
- Run `scripts/privacy-audit-repo`.
- Manually review UAT scenarios 1, 4, and 7.

