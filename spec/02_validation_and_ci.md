# Spec 02: Validation And CI
**Goal:** Enforce repository conventions with one local command and CI.
**Depends on:** 01

## Requirements
- Add a dependency-free validator using Ruby standard library.
- Check prompt field coverage and input sections.
- Check vault-template YAML frontmatter and required keys.
- Check local markdown links.
- Check README counts against repository contents.
- Add GitHub Actions workflow that runs the validator.

## Files
- Create: `scripts/validate-repo`
- Create: `.github/workflows/validate.yml`
- Modify: `spec/progress.md`

## Boundary Map
- **Produces**: executable `scripts/validate-repo`, CI workflow.
- **Consumes**: prompt contracts and canonical naming from Spec 01.

## Acceptance Criteria
- [ ] `scripts/validate-repo` exits 0 on a clean repo.
- [ ] CI runs the same validator on pushes and pull requests.
- [ ] Validation failures print actionable file paths.

## Test Plan
- Run `scripts/validate-repo`.
