# Session Close (the standing research-session closer)

The prompt that ends every routine research session on a vault running the
mechanized session loop. It records the lane outcome into the lane bandit, runs
the ordered close checklist (`scripts/session_close.py`), and writes the Handoff
close block — so the next session starts from a ranked plan and an honest
record, not from memory. Pair of `21-session-start.md`.

Copy-paste prompt (fill the placeholders):

```text
Close this research session.

1. Decide the lane worked and the outcome. "hit" ONLY if the lane's metric
   moved (SILENT down / keystone written up / ?-edges adjudicated / rotation
   hits recorded); otherwise it is honestly a miss — the bandit needs the true
   signal.
2. Write the session log: logs/<today>-<slug>.md — the narrative lives THERE,
   not in the Handoff.
3. Run the close command (adjust flags to what actually happened):
   AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/session_close.py \
     --lane <LANE> --outcome <hit|miss> --note "<one line>" \
     --log logs/<today>-<slug> --summary "<one line>" --apply-archive
   Add --rotation-done ONLY if the profile-review slice was polled AND each
   entry recorded with --record this session.
4. Fix anything the checklist reports as FAIL; SKIP/DUE lines must be true,
   not ignored.
5. Write the close block in Handoff.md per the Operating_Protocol template
   (<=120 lines; RETRACTIONS and NEGATIVES/DO-NOT-REDO are required fields;
   OPEN/NEXT comes FROM the session plan; no hand-copied metrics — mark a
   load-bearing number [finding]). Update the suggested /rename line for the
   next session's plan.
6. Commit the vault. Pre-commit gates must pass — never use --no-verify.
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (same value used
  in `21-session-start.md`).

## Autoresearch Configuration

**Goal**: Close the session with nothing silently skipped: lane outcome
recorded, Research_Log row appended, Handoff close block written to template,
superseded close archived, all gates green at the final commit.

**Metric**: Close-checklist steps reporting FAIL (from `session_close.py`),
plus HANDOFF_LINT violations on the new close block.

**Direction**: Minimize (target 0 / 0).

**Verify**: `python3 scripts/session_close.py ...` output (every step PASS /
honest SKIP); `python3 scripts/handoff_lint.py --quiet`;
`python3 scripts/ascii_handoff.py`; the vault pre-commit hook on the final
commit.

**Guard**:
- The outcome is HONEST: a session that moved nothing records a miss. The
  exploration floors guarantee a miss never permanently starves a lane, so
  there is no incentive to flatter the record.
- `--rotation-done` only when the rotation slice was actually polled and each
  entry recorded — resetting the clock on unpolled work lies to the next
  session.
- The close block is an INDEX into the session log, not a story; RETRACTIONS
  and NEGATIVES/DO-NOT-REDO may say "none" but may not be omitted.
- No hand-copied derivable metrics in the Handoff or the baseline file; a
  load-bearing number is marked `[finding]`.
- Research_Log rows are appended via `scripts/log_session.py` (the close
  command does this) — never the Edit tool.
- Never `--no-verify`. If the pre-commit blocks, fix the finding (or the CHECK,
  if the parser is the suspect) — do not bypass.

**Iterations**: 1

**Protocol**:

1. Determine lane + outcome from what actually moved (compare the lane metric
   against the session-start value).
2. Write the session log with the narrative, negatives, and any retractions.
3. Run `session_close.py` with the truthful flags; re-run after fixing any
   FAIL.
4. Write the Handoff close block from the template; set OPEN/NEXT from the
   plan (re-run `session_plan.py` if the counts have moved enough to reorder
   it); update the suggested `/rename` line.
5. Final vault commit with all gates green. If the operator queue changed,
   say so in OPERATOR QUEUE DELTA.
