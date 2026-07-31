# Review Card: Session Review

Prompt: [23 Session Review](../prompts/23-session-review.md)

Phase 3 of 4. Reconciles the sitting against the tools before phase 4 files it. No research, no FamilySearch writes.

## Good Output

- A per-iteration table rebuilt from `session_plan_snapshots.json`, whose observation count matches the iterations actually worked (one observation = one recorded lane outcome; a "row" elsewhere means a worklist candidate, i.e. a person).
- Every lane metric re-measured with the owning heartbeat and compared against the phase-1 values, with each recorded outcome confirmed or corrected in place.
- The audit suite re-run and compared line by line against `.audit_baseline.txt`; anything this sitting introduced is fixed before the close.
- Each queued FS write-back appears as a `- **FS write-back QUEUED <date>** …` bullet on the person's OWN entry, carrying action, evidence locator and `life_status`; living and unknown are absent for a public target. The session log's "## FS WRITE-BACK QUEUE" section carries the reasoning, and the reported count comes from `grep -ric "FS write-back QUEUED"`, not a hand tally.
- The session log confirmed complete: every negative, citation and retraction present.
- The close-block material assembled, including RETRACTIONS and NEGATIVES / DO-NOT-REDO even when they say "none".
- Partial work named item by item: unworked iterations, unpolled rotation entries.

## Red Flags

- The summary is written from the session's own memory of what happened rather than from the state file and the heartbeats.
- A recorded hit left standing after the heartbeat failed to confirm it.
- New research started because the review "noticed something" — it should have been queued.
- A write-back queue of bare PIDs with no evidence, or one that includes a living or unknown person for a public target.
- Queue items recorded ONLY in the session log (a write-once file cannot be marked done later), or in a new ledger file (a second store nothing audits).
- An FS hint queued as though it were a record, without the identifier check that would settle it.
- Derivable metrics copied into prose unmarked, or "mostly done" standing in for a list of what is left.
- Gates above baseline noted and carried into the close unexplained.

## Verify Manually

- Count the sitting's `history` observations yourself and compare against the iterations you watched happen.
- Re-run one heartbeat (`extension_frontier.py --heartbeat` or `keystone_report.py --summary`) and check it against the reported movement.
- Read the write-back queue: does each line let a future session act without re-deriving the evidence?
- `grep -ric "FS write-back QUEUED" <vault>/Family_Tree*.md` — does the total match what the review reported, and did it rise by the number of new items?
- Diff the audit output against `.audit_baseline.txt` for one gate the session claims is at baseline.

## Reject The Result When

- The iteration count and the bandit history disagree and the mismatch was not resolved.
- A recorded outcome contradicted by a re-measured metric was left standing.
- Any FamilySearch write was performed in this phase.
- The write-back queue omits items the session clearly surfaced, or includes living/unknown people for a public target.
- Required close-block fields have no material and the gap is not stated.

## Next Prompt

`24-session-close` — file the sitting and set up the next one.
