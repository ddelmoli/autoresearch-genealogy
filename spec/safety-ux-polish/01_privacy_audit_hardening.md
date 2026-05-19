# Spec 01: Privacy Audit Hardening

**Goal:** Prevent privacy tools from creating secondary leaks and make local/private validation stricter.

**Depends on:** none

## Requirements

- Redact denylist terms in `scripts/privacy-audit-repo` reports.
- Write privacy audit reports outside the repo tree by default.
- Redact denylist terms in `scripts/validate-repo` error output.
- Add baseline public privacy checks that run in CI without a private denylist.
- Harden the private vault validator against exact dates for living or privacy-unknown person files.

## Files

- Modify: `scripts/privacy-audit-repo`
- Modify: `scripts/validate-repo`
- Modify: `CONTRIBUTING.md`
- Modify: `guides/privacy-mode.md`
- Modify private: `<private Genealogy vault>/_Audit/validate_genealogy_vault.rb`
- Modify private: `<private Genealogy vault>/_Audit/Validation_Guide.md`

## Acceptance Criteria

- [ ] Failed privacy audit reports do not include exact denylist terms.
- [ ] Default privacy audit reports are outside the repo tree.
- [ ] `scripts/validate-repo` still passes.
- [ ] Private vault validation catches exact private dates for living or privacy-unknown people.

## Test Plan

- Run `scripts/validate-repo`.
- Run `scripts/privacy-audit-repo`.
- Run a temporary failing denylist audit and inspect that the report redacts matched terms.
- Run `ruby "_Audit/validate_genealogy_vault.rb"` in the private vault.
