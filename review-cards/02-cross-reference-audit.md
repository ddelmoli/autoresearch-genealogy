# Review Card: Cross-Reference Audit

Prompt: [02 Cross-Reference Audit](../prompts/02-cross-reference-audit.md)

## Good Output

- Discrepancies are grouped by person and claim.
- Each fix explains which source won and why.
- Unresolved conflicts remain visible in `Open_Questions.md`.
- No fact is silently overwritten.
- Evidence tiers reflect source strength.

## Red Flags

- The AI chooses a date or place without citing a source.
- A lower-quality source overrides a primary record with no explanation.
- Conflicts disappear instead of being documented.
- Multiple people are merged because their names look similar.

## Verify Manually

- Compare the cited sources side by side.
- Check whether sources are independent.
- Confirm that the chosen source is closer to the event.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- The audit hides uncertainty.
- A correction contradicts a primary source without strong evidence.
- The AI cannot explain the identity match.

## Next Prompt

Run [05 Source Citation Audit](../prompts/05-source-citation-audit.md).

