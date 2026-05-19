# Spec 04: Anonymized Fixtures
**Goal:** Add fake fixture data and a golden-run example so prompt behavior can be reviewed without private genealogy content.
**Depends on:** 01, 02, 03

## Requirements
- Create a tiny fake vault with a living person, three deceased ancestors, a source conflict, and one open question.
- Add a golden-run transcript for `01-tree-expansion`.
- Add validation coverage that fixture files exist and no optional private denylist terms appear in tracked files.

## Files
- Create: `fixtures/minimal-vault/Family_Tree.md`
- Create: `fixtures/minimal-vault/Open_Questions.md`
- Create: `fixtures/minimal-vault/Research_Log.md`
- Create: `fixtures/minimal-vault/templates/person.md`
- Create: `fixtures/golden-runs/01-tree-expansion.md`
- Modify: `scripts/validate-repo`

## Boundary Map
- **Produces**: fake fixture vault, golden-run example, optional denylist validation.
- **Consumes**: privacy and naming rules from Spec 01.

## Acceptance Criteria
- [ ] Fixture data is explicitly fictional.
- [ ] Golden run demonstrates skipping living people.
- [ ] `scripts/validate-repo` passes.

## Test Plan
- Run `scripts/validate-repo`.
