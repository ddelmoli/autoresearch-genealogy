# Review Card: Session Close

Prompt: [22 Session Close](../prompts/22-session-close.md)

## Good Output

- The recorded outcome matches the metric: "hit" only when the lane's number actually moved against its session-start value.
- `session_close.py` output shows every step PASS or an honestly-explained SKIP; FAILs were fixed and the command re-run.
- `--rotation-done` appears only when the rotation slice was polled AND per-entry recorded.
- The close block fits the template: RETRACTIONS and NEGATIVES/DO-NOT-REDO present (may say "none"), OPEN/NEXT taken from the plan, load-bearing numbers marked `[finding]`.
- The session narrative lives in the `logs/` file; the Handoff block is an index into it.
- The final commit passes the pre-commit gates without `--no-verify`.

## Red Flags

- A hit recorded because the session "did a lot of work" while the lane metric stood still.
- The rotation clock reset on an unpolled slice (lies to the next session's DUE line).
- Derivable metrics hand-copied into the Handoff or baseline file unmarked.
- RETRACTIONS omitted rather than stated as "none" — a field filled only when convenient is not a record.
- Close-checklist SKIPs that are actually unfinished obligations (e.g. no Research_Log row).
- `--no-verify` anywhere, or a blocking gate "fixed" by rewording the narrative instead of fixing the finding or the check.
