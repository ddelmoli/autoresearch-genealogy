# Review Card: NARA AAD Military Service Sweep

Prompt: [16 AAD Military Sweep](../prompts/16-aad-military-sweep.md)

## Good Output

- Every US-resident person of military age during a covered conflict has a checked status.
- A no-match is recorded as a dated negative, not left blank.
- Each match cites the AAD series, National Archives Identifier, and record URL.
- The audit file distinguishes MATCH, NO_MATCH and NEEDS_AAD.
- Matches name the identifiers they were confirmed on, not just the surname.

## Red Flags

- A common surname is matched on name and state alone.
- A serial number is treated as proof without a birth year or town agreeing.
- The sweep reports a match for a man who was the wrong age at enlistment.
- An unchecked person is silently dropped from the audit file rather than marked.
- A conflict's date range is widened to make a candidate fit.

## Verify Manually

- Reopen two AAD record URLs and confirm they load the cited person.
- Check one match against the person's known residence and birth year.
- Confirm at least one NO_MATCH was genuinely searched, not assumed.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- Matches rest on a name alone with no corroborating identifier.
- Negatives carry no date, so they cannot be re-tested later.
- The audit file's totals do not reconcile with the vault's eligible population.

## Next Prompt

Run [19 FS Source Harvest](../prompts/19-fs-source-harvest.md).
