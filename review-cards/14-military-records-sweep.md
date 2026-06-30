# Review Card: Military Service Records Sweep (NARA AAD)

Prompt: [14 Military Service Records Sweep](../prompts/14-military-records-sweep.md)

## Good Output

- Each claimed match agrees on at least three of surname, given name, state, county, and year of birth (±2).
- Every cited field (serial number, unit, dates) is present in the AAD record, not inferred.
- Ambiguous and same-name candidates are listed for review, not silently resolved.
- Failed searches are logged with the databases and spelling variants tried.
- Not-in-AAD cases (pre-WWII births, WWI-only, Civil War) are marked with a reason and redirected.

## Red Flags

- A match is accepted on name alone, or on a single common name with no state/county/year support.
- A service number, unit, or date appears in the vault that is not in the cited record.
- A living or possibly living person was searched (the peacetime and recent-conflict buckets include them).
- WWI or Civil War service is "found" in AAD (it is not there).
- A 2-digit year of birth was misread (a 1900-1909 birth conflated with 2000-2009).

## Verify Manually

- Open the AAD record-detail page and confirm each cited field.
- Check the state and county of residence against the family's known location at that date.
- Decode any coded fields (term of enlistment, source of personnel) via the field's Detailed Field Information.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- Two or more records match equally well and one was picked anyway.
- The residence state or county does not fit the family's documented location.
- The only support is a name match with no corroborating field.
- The "record" is actually a medical, pension, WWI, or Civil War source that AAD does not hold.

## Next Prompt

Run [02 Cross-Reference Audit](../prompts/02-cross-reference-audit.md).
