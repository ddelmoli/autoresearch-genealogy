# Review Card: Immigration Search

Prompt: [11 Immigration Search](../prompts/11-immigration-search.md)

## Good Output

- Candidate records match name variants, age, destination, relatives, and origin.
- Passenger, naturalization, census, and local records are compared.
- Original names and spellings are preserved.
- The output distinguishes arrival clues from confirmed identity.
- Failed searches are logged.

## Red Flags

- A passenger list match is accepted on name alone.
- The AI assumes a surname changed without evidence.
- Origin town, destination, or traveling companions conflict with known facts.
- Naturalization and arrival records are merged across two different people.

## Verify Manually

- Open the record image when possible.
- Compare traveling companions, sponsor, destination, and later residence.
- Check age tolerance and name variants.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- The candidate's destination or family context does not fit.
- There are multiple plausible same-name immigrants.
- The source is an index with no image and no corroboration.

## Next Prompt

Run [02 Cross-Reference Audit](../prompts/02-cross-reference-audit.md).

