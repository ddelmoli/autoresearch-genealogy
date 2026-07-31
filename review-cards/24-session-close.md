# Review Card: Session Close

Prompt: [24 Session Close](../prompts/24-session-close.md)

Phase 4 of 4. Files the sitting and sets up the next one.

## Good Output

- `session_close.py` ran ONCE, with `--next-plan`, and its output shows every step PASS or an honestly-explained SKIP/DUE.
- The `plan` step is SKIP with a stated reason ("all N iterations recorded themselves in phase 2"), not a second bandit observation for the same work.
- `--rotation-done` appears only when the slice was fully polled AND per-entry recorded.
- The next session's draw was registered AFTER the record step, and the `pending` field in `session_plan_snapshots.json` matches what the Handoff announces.
- The close block fits the template: RETRACTIONS and NEGATIVES / DO-NOT-REDO present (may say "none"), OPEN / NEXT carrying the pending lane, what is left, and the write-back queue count with its log pointer.
- The suggested `/rename` line and the recommended starting command for the next session are both updated.
- The narrative lives in the `logs/` file; the Handoff block indexes it. The final commit passes the pre-commit gates without `--no-verify`.

## Red Flags

- `--lane/--outcome` passed at close on top of per-iteration records — one sitting counted twice, and afterwards indistinguishable from two real sessions.
- `session_plan.py` run BEFORE the close command: the pending draw it registers is wiped by the record step, and the Handoff then announces a draw that does not exist.
- The rotation clock reset on an unpolled slice.
- A second Research_Log row for the same sitting, or a stale one-line summary left standing after the sitting continued.
- Derivable metrics hand-copied into the Handoff or baseline file unmarked, including the write-back queue depth (it is a grep, and prompt 17 changes it).
- RETRACTIONS omitted rather than stated as "none".
- `--no-verify` anywhere, or a blocking gate cleared by rewording the narrative instead of fixing the finding or the check.

## Verify Manually

- `python3 scripts/session_plan.py --heartbeat` — is a pending draw registered, and is it the lane the Handoff names?
- Count `history` observations for the sitting: one per worked iteration, none added by the close itself.
- Read the new close block against the Operating_Protocol template; run `python3 scripts/handoff_lint.py` and `python3 scripts/ascii_handoff.py`.
- Confirm the Research_Log gained exactly one Session Index row and the superseded close landed in the archive dir.
- Check that the "Suggested rename" line and the starting command reflect the pending lane, not the lane just finished.

## Reject The Result When

- The bandit gained an observation the work does not justify, or the sitting's outcomes were recorded twice.
- The Handoff announces a pending draw the state file does not hold.
- `--rotation-done` was passed without per-entry `--record` calls this sitting.
- The close block narrates the session instead of indexing the log, or omits a required field.
- Any commit used `--no-verify`, or a blocking gate was cleared by rewording narrative.

## Next Prompt

`21-session-start` at the next session, then `22-research-iterations` with the dials the close recommended. If the close surfaced operator decisions, resolve `deferred_decisions.md` items first.
