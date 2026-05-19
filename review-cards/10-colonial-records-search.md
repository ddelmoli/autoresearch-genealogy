# Review Card: Colonial Records Search

Prompt: [10 Colonial Records Search](../prompts/10-colonial-records-search.md)

## Good Output

- Claims are built from multiple record types, not one same-name hit.
- Land, probate, church, tax, militia, and court records are treated as a network.
- Date ranges and jurisdictions are explicit.
- Alternative identities are documented.
- Negative searches are logged.

## Red Flags

- A same-name colonial record is accepted without family or location support.
- Jurisdiction changes are ignored.
- The AI jumps across counties or colonies without migration evidence.
- A published genealogy is treated as primary proof.

## Verify Manually

- Check jurisdiction boundaries for the date.
- Compare associates, neighbors, witnesses, and heirs.
- Confirm whether the source is original or compiled.
- Use [Before You Add An Ancestor](../checklists/before-you-add-an-ancestor.md).

## Reject The Result When

- The identity match rests on name alone.
- The person cannot plausibly be in both places.
- A compiled source lacks citations for the claim.

## Next Prompt

Run [02 Cross-Reference Audit](../prompts/02-cross-reference-audit.md).

