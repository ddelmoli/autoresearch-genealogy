# Review Card: GEDCOM Completeness

Prompt: [04 GEDCOM Completeness](../prompts/04-gedcom-completeness.md)

## Good Output

- GEDCOM people match `Family_Tree.md`.
- Missing citations, dates, and relationships are listed.
- Living-person details are redacted or excluded before sharing.
- Export issues are separated from research questions.
- The output notes which fields require manual software review.

## Red Flags

- Exact living-person details remain in the export.
- The AI changes the tree only to satisfy GEDCOM formatting.
- Unsourced relationships are promoted to established facts.
- Source citations are flattened or lost.

## Verify Manually

- Open the GEDCOM in your tree software or a GEDCOM viewer.
- Check living-person privacy settings.
- Compare a sample of people against `Family_Tree.md`.
- Use [Share Safely](../checklists/share-safely.md).

## Reject The Result When

- The export exposes living people.
- Person identifiers are duplicated or merged incorrectly.
- The GEDCOM loses source references you need.

## Next Prompt

Run [05 Source Citation Audit](../prompts/05-source-citation-audit.md).

