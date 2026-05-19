# Spec 03: Documentation Polish
**Goal:** Clean up drift and document the contribution workflow.
**Depends on:** 01, 02

## Requirements
- Fix README example count drift.
- Fix glossary typo.
- Add contribution instructions with validation command.
- Add archive guide verification metadata policy.

## Files
- Modify: `README.md`
- Modify: `reference/glossary.md`
- Create: `CONTRIBUTING.md`
- Modify: `archives/README.md`

## Boundary Map
- **Produces**: contributor checklist, archive metadata rule.
- **Consumes**: validator command from Spec 02.

## Acceptance Criteria
- [ ] README counts match actual repository contents.
- [ ] Contributor docs explain local validation before PRs.
- [ ] Archive docs require `last_verified` metadata.

## Test Plan
- Run `scripts/validate-repo`.
