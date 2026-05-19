# Spec 01: Safety And Contracts
**Goal:** Make prompt execution safer and less ambiguous.
**Depends on:** none

## Requirements
- Add living-person privacy guardrails to the first-run workflow and tree expansion prompt.
- Add per-prompt input sections so placeholders are explicit.
- Establish canonical vault file names so prompts do not create duplicate case variants.
- Clarify confidence terminology across evidence tiers and frontmatter values.

## Files
- Modify: `README.md`
- Modify: `workflows/getting-started.md`
- Modify: `prompts/*.md`
- Modify: `prompts/README.md`
- Modify: `CLAUDE.md`
- Create: `reference/vault-file-manifest.md`
- Modify: `reference/confidence-tiers.md`

## Boundary Map
- **Produces**: prompt input block format, canonical vault file table, privacy guardrails, confidence mapping.
- **Consumes**: existing prompt field format and vault-template filenames.

## Acceptance Criteria
- [ ] `01-tree-expansion` explicitly skips living people and redacts exact living-person dates.
- [ ] Every numbered prompt has an `Inputs To Replace` section.
- [ ] Prompt output paths use the canonical title-case vault filenames where templates already exist.
- [ ] Confidence docs distinguish evidence tier from file completeness.

## Test Plan
- Run `scripts/validate-repo` after Spec 02 exists.
- Manually inspect changed prompt paths for canonical names.
