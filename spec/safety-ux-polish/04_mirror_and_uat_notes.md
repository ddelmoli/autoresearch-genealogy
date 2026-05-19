# Spec 04: Mirror And UAT Notes

**Goal:** Keep the private version synchronized and record what was verified.

**Depends on:** 03

## Requirements

- Mirror tracked public toolkit changes into the private vault toolkit folder.
- Ensure `.git`, `.private/`, and privacy audit reports are not mirrored.
- Update progress and UAT notes.
- Run public and private validation gates.

## Files

- Modify: `spec/safety-ux-polish/progress.md`
- Modify: `spec/normie-usability/uat.md`
- Modify private mirror under `<private Genealogy vault>/_Toolkit/autoresearch-genealogy/`

## Acceptance Criteria

- [ ] Public repo is clean and pushed.
- [ ] Private mirror validates.
- [ ] Public validation and privacy audit pass.
- [ ] Private vault validation passes.

## Test Plan

- Run `scripts/validate-repo`.
- Run `scripts/privacy-audit-repo`.
- Run private mirrored toolkit `scripts/validate-repo`.
- Run private vault validator.
