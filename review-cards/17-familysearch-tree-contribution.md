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

## The FS Write-Back Queue (added 31 JUL 2026)

- Queue items (`- **FS write-back QUEUED …**` bullets, written by `23-session-review`) are worked FIRST: they arrive pre-researched, and this prompt is the only one allowed to perform them.
- Every drained item's bullet is REWRITTEN to `- **FS write-back DONE <date>**` with what was actually written, or to `- **FS write-back DROPPED <date>**` with why it no longer applies (the canonical three states, `CLAUDE.method.md` rule 8). A performed action whose QUEUED bullet survives is re-presented at every session start; the ledger is the grep, so the rewrite IS the drain.
- An item that turns out not to apply is rewritten to say so, with the date and the reason. It is never deleted silently.
- The queuing session's evidence is re-checked against the live profile before acting, and a prior not-a-match decision is honoured. The bullet's `life_status` mark is a convenience, not the authority: `scripts/privacy_gate.py` is.
- Reject the run if the `FS write-back QUEUED` count fell without a matching rise in `FS WRITE-BACK DONE` (or a recorded not-applicable outcome).

## Next Prompt

Run [18 Edge Verification](../prompts/18-edge-verification.md).
