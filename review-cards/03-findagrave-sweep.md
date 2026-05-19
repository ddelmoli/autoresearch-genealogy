# Review Card: Find A Grave Sweep

Prompt: [03 Find a Grave Sweep](../prompts/03-findagrave-sweep.md)

## Good Output

- Memorial candidates match name, date, place, and relatives.
- Cemetery location fits the known residence or death place.
- The output separates memorial text from verified facts.
- Photos, inscriptions, and linked relatives are treated as clues unless independently verified.
- Non-matches and ambiguous matches are logged.

## Red Flags

- Same-name memorials are accepted without family context.
- A wrong-cemetery match is accepted because dates are close.
- Linked relatives are copied into the tree without records.
- An inscription is treated as a civil record.

## Verify Manually

- Open the memorial page and inspect photos or transcription quality.
- Check cemetery geography.
- Compare linked relatives against known family members.
- Look for an independent death, burial, obituary, or probate source.

## Reject The Result When

- The cemetery or death place conflicts with known facts.
- The memorial has no family links and the name is common.
- The result relies only on another user's unsourced note.

## Next Prompt

Run [02 Cross-Reference Audit](../prompts/02-cross-reference-audit.md).

