# Session Close (phase 4 of 4: file the sitting and set up the next one)

The prompt that ends every routine research session on a vault running the
mechanized session loop. Phase 3 decided what happened; this phase FILES it: the
ordered close checklist (`scripts/session_close.py`), the Handoff close block,
the next session's draw and starting command, and the final commit. Run after
`23-session-review`.

**Two defects fixed in the four-phase split (31 JUL 2026), both of which had
already corrupted state:**

1. **The old ordering destroyed the pending draw it had just created.** The
   prompt said to run `session_plan.py` for `OPEN / NEXT` *before* closing, and
   the close command's own first step (`session_plan.py --record`) sets
   `pending: null`. So the Handoff announced "a pending draw is waiting: EXPAND"
   while the state file held no pending draw at all, and the next session's plan
   drew a different lane. **The plan for the next session now runs AFTER the
   record, and `session_close.py --next-plan` does it in the right order for
   you.**
2. **"Is this lane already in the bandit?" is no longer a re-close test.** Under
   `22-research-iterations` every iteration records itself, so history rows from
   this sitting are expected. The close records NOTHING into the bandit by
   default, which removes the double-count trap rather than asking you to detect
   it. (The old test was undecidable anyway: history rows carry a date and a
   lane, and several sittings a day is normal.)

Copy-paste prompt (fill the placeholders):

```text
Close this research session. Every command runs with
AUTORESEARCH_VAULT="[VAULT_PATH]".

0. WHAT IS ALREADY RECORDED? ALWAYS PASS --session <SESSION NUMBER> (phase 1
   established it). The close command then TELLS you whether this is a first close
   or a re-close, from the `last_close` stamp, instead of asking you to remember —
   and it REFUSES --lane/--outcome and --log on a re-close rather than letting them
   double-count. Each iteration recorded its own outcome in phase 2, and phase 3
   reconciled them. So:
   - NORMALLY, RUN THE CLOSE WITHOUT --lane/--outcome. Passing them records ONE
     MORE observation on top of the per-iteration ones, and afterwards it is
     indistinguishable from a real session.
   - Pass --lane/--outcome ONLY if an iteration was worked and never recorded
     (phase 3 step 1 finds this), and then only for that one iteration.
   - IF THE COMMAND REPORTS A RE-CLOSE (the sitting was closed, then extended): the
     extra work went through 22-research-iterations and recorded itself, so
     --lane/--outcome and --log are refused, by design. One sitting is ONE bandit
     observation and ONE Research_Log row. Instead correct the now-stale row and any stale bandit
     note IN PLACE with a targeted replacement command (sed or python -c) rather
     than reading those files into context, and REWRITE the close block to cover
     the whole sitting, not just the part before the first close.

1. RUN THE CLOSE COMMAND, ONCE per sitting, with flags matching what actually
   happened:
     python3 scripts/session_close.py --session <SESSION NUMBER> \
       --log logs/<today>-<slug> --summary "<one line>"   # refused on a re-close
       [--lane <LANE> --outcome <hit|miss> --note "<one line>"]  # only if unrecorded
       [--rotation-done] [--apply-archive] --next-plan
   - --rotation-done ONLY if the profile-review slice was fully polled AND every
     entry recorded with --record. On a partial slice, omit it and name the
     unpolled entries; resetting the clock on unpolled work lies to the next
     session.
   - --next-plan runs scripts/session_plan.py AFTER the outcome is recorded, so
     the pending draw it registers is the NEXT session's and survives. ! Running
     the plan BEFORE the close command instead wipes that draw: --record clears
     `pending`. If you run the plan by hand, run it after, never before.

2. MAKE EVERY CHECKLIST LINE TRUE. Fix any FAIL and re-run. A SKIP or DUE is
   acceptable only if you can state why it is correct (e.g. "plan SKIP: all five
   iterations recorded themselves in phase 2") — write that reason into the close
   block or the commit message. Never leave one unexplained.

3. WRITE THE CLOSE BLOCK in Handoff.md per the Operating_Protocol template, from
   the material phase 3 assembled:
     GATES / WHAT MOVED / FINDINGS / RETRACTIONS / NEGATIVES-DO-NOT-REDO /
     NEW TRAPS / OPEN-NEXT / OPERATOR QUEUE DELTA
   - RETRACTIONS and NEGATIVES / DO-NOT-REDO are REQUIRED. They may say "none";
     they may not be omitted.
   - OPEN / NEXT carries, in priority order: the lane the --next-plan draw is
     pending on, what is left from this sitting (unworked iterations, unpolled
     rotation entries), and **how many FS write-backs THIS SITTING queued**, with
     a pointer to its log for the reasoning. ! Write the DELTA, not the total: the
     total is derivable (the banner's `writeback ->` line counts it off the
     entries every session) and prompt 17 changes it the moment it drains one, so
     a copied total is stale on arrival. The delta is a fact about this sitting
     and stays true.
   - Record the pending lane ABOVE the close block too, where it does not consume
     the block's line cap.
   - No hand-copied derivable metrics; mark a genuinely load-bearing number
     [finding].
   - ! The <=120-line cap is checked by scripts/handoff_lint.py. Run it and trim
     BEFORE committing rather than ping-ponging at 121.

4. SET UP THE NEXT SESSION, in the two places 21-session-start reads:
   - The "**Suggested rename for the next session:**" line near the top of
     Handoff.md, matching the pending lane and its top target. A stale one
     propagates straight into the next session's name.
   - The recommended STARTING COMMAND, in "Start here", naming the phase prompts
     and the dials you would set given what is left, e.g.:
       run 21-session-start, then 22-research-iterations with Iterations=5
     Raise or lower Iterations to fit what OPEN / NEXT actually holds, and say
     why in one clause. If the write-back queue is deep enough to be worth its
     own sitting, recommend 17-familysearch-tree-contribution (operator present)
     instead of research iterations.

5. CONFIRM THE GATES ARE STILL AT BASELINE. Phase 3 already compared them; this
   is the check that nothing the close itself wrote moved one. Read the
   pre-commit output rather than trusting its exit code.

6. COMMIT THE VAULT. Pre-commit must run; never --no-verify. The commit message
   carries what changed and why (the log carries the narrative), and it uses the
   session number established in phase 1. Finish with a clean working tree.
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (same value used in
  `21-session-start.md`).

## Autoresearch Configuration

**Goal**: File the sitting with nothing silently skipped and nothing recorded
twice: outcomes recorded exactly once (in phase 2, not again here), one
Research_Log row, a close block written to template and covering the whole
sitting, a pending draw that still exists when the next session opens, a starting
command and rename line for that session, and every gate at or below baseline at
the final commit.

**Metric**: Close-checklist steps reporting FAIL (from `session_close.py`), plus
HANDOFF_LINT violations on the new close block, plus duplicate one-per-sitting
artefacts (extra bandit observations, extra Research_Log rows), plus gate counts
above `.audit_baseline.txt`, plus a `pending` field that does not match what the
Handoff announces.

**Direction**: Minimize (target 0 on every term).

**Verify**: `python3 scripts/session_close.py ... --next-plan` output (every step
PASS, or a SKIP/DUE with its reason recorded); `python3 scripts/handoff_lint.py
--quiet`; `python3 scripts/ascii_handoff.py`; the vault's
`session_plan_snapshots.json` — one `history` observation per worked iteration and a
non-null `pending` matching the Handoff; exactly one Research_Log row for the
sitting; the vault pre-commit hook output READ, not merely exited.

**Guard**:
- **The close does not record the bandit by default.** Every iteration recorded
  itself; a close-time `--lane/--outcome` on top of that is a second observation
  for the same work.
- **Order matters: record, THEN plan.** `session_plan.py --record` clears
  `pending`, so a plan run before the close is wiped by it. `--next-plan` exists
  so this cannot be got wrong by hand.
- **A one-line `--note` or `--summary` goes stale the moment a sitting
  continues.** On a re-close, correct it in place rather than adding a second row
  or leaving a false one standing, and never read `Research_Log.md` into context
  to do it.
- `--rotation-done` only when the rotation slice was actually polled and each
  entry recorded; resetting the clock on unpolled work lies to the next session.
  Leaving an entry's `last_polled` unset is better than recording a miss for an
  entry nobody looked at, because a false miss also burns its cooldown.
- **An advisory gate can be FLAGGED inside a passing pre-commit.** "PASS" is not
  the baseline check; reading the numbers is the baseline check.
- The close block is an INDEX into the session log, not a story; RETRACTIONS and
  NEGATIVES / DO-NOT-REDO may say "none" but may not be omitted.
- No hand-copied derivable metrics in the Handoff or the baseline file; a
  load-bearing number is marked `[finding]`.
- **The write-back queue TOTAL is derived, like every other metric in this file;
  only the sitting's DELTA is written down.** The banner counts the total off the
  entries every session, and prompt 17 changes it the moment it drains one. This
  is the same rule that keeps SOURCE_GAP and SILENT out of the Handoff.
- **The Handoff must not announce state the JSON does not hold.** If the close
  block says a draw is pending, `session_plan_snapshots.json` says so too, or the
  next session opens on a lane nobody chose.
- Research_Log rows are appended via `scripts/log_session.py` (the close command
  does this) — never the Edit tool.
- Never `--no-verify`. If the pre-commit blocks, fix the finding (or the CHECK,
  if the parser is the suspect) — do not bypass.

**Iterations**: 1 — **this prompt is a PHASE, not a loop**, and raising it is
meaningless: a sitting is closed once. A sitting that continues after a close is
handled by the re-close path in step 0, not by closing twice.

**Protocol**:

1. Determine what phase 2 already recorded, and whether this is a first close or
   a re-close; that decides which flags are legal.
2. Run `session_close.py` once with the truthful flags, including `--next-plan`;
   re-run after fixing any FAIL.
3. Write (or on a re-close, rewrite) the Handoff close block from phase 3's
   material; set OPEN / NEXT from the pending draw, what is left, and the
   write-back queue; run `handoff_lint.py` and trim to the cap.
4. Update the suggested `/rename` line and the recommended starting command for
   the next session.
5. Confirm the gates are still at baseline, reading the output rather than the
   exit code.
6. Final vault commit under the session number, clean working tree. If the
   operator queue changed, say so in OPERATOR QUEUE DELTA.
