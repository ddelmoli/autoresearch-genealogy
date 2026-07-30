# Review Card: FamilySearch Tree Contribution

Prompt: [17 FamilySearch Tree Contribution](../prompts/17-familysearch-tree-contribution.md)

**This is the only prompt that WRITES to a shared public tree.** Review it more slowly than
the read-only ones: a bad edit here is visible to strangers and inherited by their trees.

## Good Output

- Every mutation was approved by you before it was made, and logged after.
- A search for an existing profile preceded every create.
- New people carry a source, not just a name and a date.
- The PID of each created or matched person is written back into the vault entry.
- Living and unknown-status people were skipped entirely.

## Red Flags

- A person was created when a duplicate already existed.
- The run "merged" duplicates on its own initiative.
- A prior not-a-match decision was overturned without saying why.
- Dates were entered precisely when the vault only holds an approximation.
- A batch approval is treated as blanket permission for later, different edits.
- Relationship edits were made from a parent's child list rather than the child's own page.

## Verify Manually

- Open two created profiles and confirm they are not duplicates.
- Re-read the change log on one edited profile and confirm the reason is stated.
- Confirm every new PID also appears in the vault entry it came from.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- Any mutation happened without your explicit approval.
- A create was made where a search would have found an existing person.
- A living person reached the shared tree.
- The log does not let you reconstruct, and undo, what was changed.

## Next Prompt

Run [18 Edge Verification](../prompts/18-edge-verification.md).
