# Review Card: FamilySearch Source Harvest

Prompt: [19 FS Source Harvest](../prompts/19-fs-source-harvest.md)

## Good Output

- Every recorded ARK was copied from the page, never reconstructed.
- Book and journal citations are noted in prose and counted separately, not as ARKs.
- Copied trees are excluded from the coverage count.
- A zero-record result says which surfaces were read before concluding it.
- Image-only collections are captured, not skipped for lacking an index entry.

## Red Flags

- A "0 ARKs" result from a run where Detail View was never confirmed on.
- Coverage counted from attached sources alone, with the hints surface unread.
- A rising ARK count that is really the same record cited on two sites.
- An ARK that will not reopen, or whose id looks assembled from a pattern.
- A citation added for a record nobody opened.

## Verify Manually

- Reopen three ARKs at random and confirm each names the person.
- Confirm one entry's count matches the records actually listed on the profile.
- Check that no book citation was promoted into the record count.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- Any ARK cannot be reopened.
- The coverage number rose without new records being read.
- A negative was recorded from a surface that could not have shown the answer.

## Next Prompt

Run [05 Source Citation Audit](../prompts/05-source-citation-audit.md).
