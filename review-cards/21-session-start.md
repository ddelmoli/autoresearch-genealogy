# Review Card: Session Start

Prompt: [21 Session Start](../prompts/21-session-start.md)

Phase 1 of 4. Initializes the session and does no research.

## Good Output

- The vault is named with its resolution source, and an INFERRED vault is confirmed with the operator before anything is written.
- Current gate values are in hand (from the banner, or from `session_audit.sh` when the hook was skipped) and compared against `.audit_baseline.txt`, not against themselves.
- The session-start values of the four lane metrics are written down, so phase 3 has a "before".
- The session number is derived from the Handoff plus the Research_Log, and stated.
- Any announced pending draw is checked against `session_plan_snapshots.json` rather than believed from prose.
- Housekeeping DUE items, open deferred decisions and the FS write-back queue depth are surfaced ONCE, checked against `deferred_decisions.md` first, and either asked or queued per the away-policy.
- The reply ends with a rename command reconciled from the Handoff's stored suggestion, and hands off to `22-research-iterations`.

## Red Flags

- Research happens in this phase: a lane drawn, an entry edited, a search run.
- The banner is absent and the session proceeds anyway, or the baseline file is read as if it were current state.
- The session number is assumed to follow the last one the session personally saw (two sittings in one day is normal).
- A housekeeping item already parked in `deferred_decisions.md` is re-presented as new.
- The FS write-back queue goes unreported because it was unchanged — nothing else surfaces it, so an unreported queue is an invisible one.
- The operator is blocked on a checklist during an autonomous run instead of the item being queued.
- A rename composed from scratch while the Handoff already carried one.

## Verify Manually

- Compare the banner's vault name and source line against the vault you meant to work.
- Spot-check two gate numbers against `.audit_baseline.txt` yourself.
- `python3 scripts/session_plan.py --heartbeat` and the `pending` field of `session_plan_snapshots.json` — do they agree with what the session reported?
- Grep `Handoff.md` and `Research_Log.md` for the highest `#N`: is the stated session number one past it?

## Reject The Result When

- Any research or vault write happened in this phase.
- Gate state was never established, or a red HARD gate was noted and phase 2 started anyway.
- The vault was inferred by the hook and never confirmed, or 2+ candidates were resolved by guessing.
- Session-start metric values were not captured, leaving phase 3 with nothing to compare against.

## Next Prompt

`22-research-iterations` — with the Iterations and Lane target this prompt passed through.
