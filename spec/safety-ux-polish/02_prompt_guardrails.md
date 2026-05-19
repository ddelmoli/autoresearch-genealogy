# Spec 02: Prompt Guardrails

**Goal:** Reduce risky behavior in tree expansion, GEDCOM, and DNA workflows.

**Depends on:** 01

## Requirements

- Replace raw tree-growth optimization with source-backed relationship quality.
- Tighten GEDCOM privacy to protect living-person names, relationships, places, and notes, not only full birth dates.
- Tighten DNA prompt and templates for local-only, consent-aware genetic data handling.
- Remove guidance that casually recommends third-party raw DNA uploads.

## Files

- Modify: `prompts/01-tree-expansion.md`
- Modify: `prompts/04-gedcom-completeness.md`
- Modify: `prompts/12-dna-chromosome-analysis.md`
- Modify: `vault-template/Data_Inventory.md`
- Modify: `vault-template/Genetic_Profile.md`
- Modify: `workflows/phase-planning.md`
- Modify: review cards as needed

## Acceptance Criteria

- [ ] Tree expansion metric rewards source-backed leads, not raw person count.
- [ ] GEDCOM prompt protects living-person relationship structure.
- [ ] DNA prompt warns against public AI/raw DNA uploads and requires consent for match data.
- [ ] Validation passes.

## Test Plan

- Run `scripts/validate-repo`.
- Run `scripts/privacy-audit-repo`.
- Grep for removed high-risk DNA upload wording.

