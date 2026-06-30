# Spec 01: Baseline And PR Gates
**Goal:** Make repository validation pass before any triage automation or external PR action.
**Depends on:** none

## Requirements
- `scripts/validate-repo` must pass on the current branch.
- `LC_ALL=C scripts/validate-repo` must pass.
- Public tracked files must not contain the private vault name, private absolute home path, or social security number pattern.
- The maintainer workflow must treat validation as a hard gate before merges.

## Files
- Modify: `scripts/validate-repo`
- Modify: `scripts/sync-vault-mirror.sh`
- Modify: `scripts/validate-genealogy-vault.rb`
- Create or modify: maintainer documentation in Spec 02 or Spec 03

## Boundary Map
- **Produces**: Green validation baseline, UTF-8 safe repository validator.
- **Consumes**: Existing privacy pattern checks in `scripts/validate-repo`.

## Acceptance Criteria
- [ ] `scripts/validate-repo` passes.
- [ ] `LC_ALL=C scripts/validate-repo` passes.
- [ ] `rg "private vault literal"` finds no tracked helper leak.

## Test Plan
- Run both validator commands.
- Run a targeted `rg` check for banned public privacy patterns in changed helper scripts.
