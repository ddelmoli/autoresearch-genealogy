# Session Close (the standing research-session closer)

The prompt that ends every routine research session on a vault running the
mechanized session loop. It records the lane outcome into the lane bandit, runs
the ordered close checklist (`scripts/session_close.py`), and writes the Handoff
close block — so the next session starts from a ranked plan and an honest
record, not from memory. Pair of `21-session-start.md`.

**Revised after a session that closed twice.** A long session is often closed,
then extended, then closed again; the earlier version of this prompt assumed a
single close and gave no guidance, so the second pass double-recorded the lane
into the bandit and left two stale one-line summaries behind. The earlier version
also required `OPEN / NEXT` to come from the session plan without noting that
re-running the plan REGISTERS a pending draw, which then makes the close
checklist report `plan DUE` about the *next* session. Both traps are handled
explicitly below, in steps 0 and 2.

Copy-paste prompt (fill the placeholders):

```text
Close this research session.

Every command below runs with AUTORESEARCH_VAULT="[VAULT_PATH]".

0. FIRST CLOSE, OR RE-CLOSE? Read the lane bandit state (the vault's
   session_plan_snapshots.json: `arms` and `history`). If this session's lane is
   ALREADY recorded there, this is a RE-CLOSE — the session was closed and then
   extended. For the rest of these steps:
     - DO NOT re-run session_close.py with --lane/--outcome. One session is ONE
       bandit observation; a second reads afterwards as two real sessions and
       corrupts the signal the bandit exists to carry.
     - DO NOT pass --log. One session is ONE Research_Log row.
     - INSTEAD correct the now-stale bandit `note` and the stale Research_Log
       row IN PLACE, by targeted string replacement. Never full-read
       Research_Log, never Edit it.
     - REWRITE the Handoff close block to cover the WHOLE session, not only the
       part that preceded the first close.

1. DECIDE THE LANE AND THE OUTCOME. Record the lane you actually WORKED, not
   the one that was drawn. "hit" ONLY if that lane's own metric moved: frontier
   SILENT down, a keystone written up, `?`-edges adjudicated, or rotation
   entries polled AND recorded. Otherwise it is a miss and you say so. If you
   worked more than one lane, record the dominant one and name the others in the
   close block.

2. DERIVE `OPEN / NEXT` NOW, BEFORE CLOSING: run scripts/session_plan.py.
   ! This REGISTERS a pending draw for the NEXT session, so the close checklist
   will report `plan DUE`. That DUE is correct, and it is about the next
   session, not this one. Record which lane is pending in the Handoff ABOVE the
   close block, where it does not consume the close block's line cap.

3. CONFIRM THE SESSION LOG IS COMPLETE: logs/<today>-<slug>.md. It should
   already exist and have been appended to as you worked — the narrative lives
   THERE, never in the Handoff. Name the slug for the LANE and session, not for
   the first thing you found; a session that wanders makes an early topical slug
   misleading. Every retraction, negative and record citation belongs in the log
   even when it is too long for the close block.

4. RUN THE CLOSE COMMAND, ONCE per session, with flags matching what actually
   happened:
     python3 scripts/session_close.py \
       [--lane <LANE> --outcome <hit|miss> --note "<one line>"]  # omit: re-close
       [--log logs/<today>-<slug> --summary "<one line>"]        # omit: re-close
       [--rotation-done] [--apply-archive]
   Add --rotation-done ONLY if the full profile-review slice was polled AND
   every entry recorded with --record this session. On a partial slice, omit it
   and say which entries were left unpolled.

5. MAKE EVERY CHECKLIST LINE TRUE. Fix any FAIL. A SKIP or DUE is acceptable
   only if you can state why it is correct; write that reason into the close
   block or the commit message. Never leave one unexplained.

6. WRITE THE CLOSE BLOCK in Handoff.md per the Operating_Protocol template.
   RETRACTIONS and NEGATIVES/DO-NOT-REDO are required (they may say "none", they
   may not be omitted). `OPEN / NEXT` comes from step 2. No hand-copied
   derivable metrics; mark a genuinely load-bearing number [finding].
   ! The <=120-line cap is checked by scripts/handoff_lint.py. Run it and trim
   BEFORE committing rather than ping-ponging at 121. Update the suggested
   /rename line to match the lane drawn in step 2.

7. VERIFY GATES AGAINST THE BASELINE, NOT AGAINST THE HOOK'S EXIT CODE. A
   "[pre-commit] PASS" can coexist with a FLAGGED advisory gate, so passing is
   not the test. Read the audit output and compare each number to the vault's
   .audit_baseline.txt. Anything above baseline that YOU introduced is a
   regression: fix it now. Anything above baseline you did not cause:
   investigate, or record why it is being left.

8. COMMIT THE VAULT. Pre-commit must run; never --no-verify. The commit message
   carries what changed and why, the log carries the narrative. Finish with a
   clean working tree.
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (same value used
  in `21-session-start.md`).

## Autoresearch Configuration

**Goal**: Close the session with nothing silently skipped and nothing recorded
twice: lane outcome recorded exactly once, Research_Log row present exactly
once, Handoff close block written to template and covering the whole session,
superseded close archived, every gate at or below baseline at the final commit.

**Metric**: Close-checklist steps reporting FAIL (from `session_close.py`), plus
HANDOFF_LINT violations on the new close block, plus duplicate one-per-session
artefacts (extra bandit observations, or extra Research_Log rows, for a single
session), plus gate counts above `.audit_baseline.txt`.

**Direction**: Minimize (target 0 on every term).

**Verify**: `python3 scripts/session_close.py ...` output (every step PASS, or a
SKIP/DUE with its reason recorded); `python3 scripts/handoff_lint.py --quiet`;
`python3 scripts/ascii_handoff.py`; exactly one `history` entry and one `arms`
increment per session in the vault's `session_plan_snapshots.json`; exactly one
Research_Log row per session; the vault pre-commit hook output READ, not merely
exited.

**Guard**:
- The outcome is HONEST: a session that moved nothing records a miss. The
  exploration floors guarantee a miss never permanently starves a lane, so
  there is no incentive to flatter the record.
- **One session is one observation.** Before recording a lane, check whether it
  is already in the bandit history. Re-recording an extended session inflates
  both `sessions` and `wins`, and afterwards is indistinguishable from two real
  sessions.
- **A one-line `--note` or `--summary` goes stale the moment a session
  continues.** On a re-close, correct it in place rather than adding a second
  row or leaving a false one standing.
- `--rotation-done` only when the rotation slice was actually polled and each
  entry recorded; resetting the clock on unpolled work lies to the next session.
  Leaving an entry's `last_polled` unset is better than recording a miss for an
  entry nobody looked at, because a false miss also burns its cooldown.
- **An advisory gate can be FLAGGED inside a passing pre-commit.** "PASS" is not
  the baseline check; reading the numbers is the baseline check.
- The close block is an INDEX into the session log, not a story; RETRACTIONS and
  NEGATIVES/DO-NOT-REDO may say "none" but may not be omitted.
- No hand-copied derivable metrics in the Handoff or the baseline file; a
  load-bearing number is marked `[finding]`.
- Research_Log rows are appended via `scripts/log_session.py` (the close command
  does this) — never the Edit tool.
- Never `--no-verify`. If the pre-commit blocks, fix the finding (or the CHECK,
  if the parser is the suspect) — do not bypass.

**Iterations**: 1

**Protocol**:

1. Read the bandit state and decide whether this is a first close or a re-close;
   that decision governs which flags are legal in step 5.
2. Determine lane + outcome from what actually moved (compare the lane metric
   against the session-start value), for the lane WORKED.
3. Run `session_plan.py` to source `OPEN / NEXT`, and note the pending draw it
   creates for the next session.
4. Confirm the session log carries the narrative, the negatives and any
   retractions.
5. Run `session_close.py` with the truthful flags; re-run after fixing any FAIL.
6. Write (or on a re-close, rewrite) the Handoff close block from the template;
   set OPEN/NEXT from step 3; run `handoff_lint.py` and trim to the cap; update
   the suggested `/rename` line.
7. Read the gate output against `.audit_baseline.txt` and fix any regression
   this session introduced.
8. Final vault commit with every gate at baseline. If the operator queue
   changed, say so in OPERATOR QUEUE DELTA.
