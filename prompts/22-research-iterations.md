# Research Iterations (phase 2 of 4: the lane draws)

The only LOOP in a research session. One iteration is a complete cycle:
**draw a lane, work it to the lane target, record the outcome**. The bandit in
`scripts/session_plan.py` updates between iterations, so draw 2 is informed by
outcome 1. Run after `21-session-start`; hand off to `23-session-review`.

**Split out of the old combined start prompt (31 JUL 2026)**, which tried to be
the initializer and the loop at once and had to exclude its own per-sitting
obligations from its own `Iterations` field in prose. Here, `Iterations` means
exactly one thing and nothing has to be excluded: everything in this prompt is
per-iteration except the one block that says otherwise.

**The lane target is a percent of the vault, counted in PEOPLE.** One number
describes a session's workload whatever lane is drawn, and it scales with the
vault instead of being a row count that silently ages. `session_plan.py` prints
the resolved figure; you never do the arithmetic:

```
LANE TARGET: 20 people this iteration — 1.5% of 1,352 (sample_percent)
```

What "20 people" means is the lane's own unit, and the units are deliberately
comparable:

| Lane | One unit of lane target |
|---|---|
| EXPAND | the vault GROWS by one person: a frontier row gains a sourced parent edge, or the parent it names is minted |
| IMPROVE | one SOURCE_GAP entry HARVESTED: its records found, read, and cited in a `- **Sources**` bullet (Recipe-S / prompt 19) |
| VERIFY | one `?`-marked edge adjudicated: cleared, contradicted, or classified with its reason on the entry |
| ROTATE | one drawn entry polled AND recorded with `--record` |

Copy-paste prompt (fill the placeholders):

```text
Run the research iterations for this session. Every command runs with
AUTORESEARCH_VAULT="[VAULT_PATH]". Repeat steps 1-5 [ITERATIONS] times.

PRECONDITION: 21-session-start has run, so you have current gate values, the
session number, and the Handoff read. If you do not, go back and do that first:
without the session-start values there is no "before", and phase 3 cannot report
movement honestly.

1. GET THE LANE.
   - ! First check the vault's session_plan_snapshots.json for a PENDING draw.
     If one is there, THAT is this iteration's lane. A re-run of the plan does
     not mint a fresh draw, and a pending lane is not an unrecorded outcome from
     the previous session.
   - Otherwise run: python3 scripts/session_plan.py [--lane-pct [LANE_PCT]]
   - SHOW ME the four lane counts, the drawn lane with its draw reason, the LANE
     TARGET line, and the top candidates BEFORE working. The draw is a
     recommendation: overriding it is allowed and must be stated up front,
     and the lane you actually work is the one you record in step 4.

2. WORK THE LANE TOP-DOWN to the lane target, in the plan's ranking order,
   dispatching to the owning prompt or workflow for the work type: VERIFY ->
   18-edge-verification; a harvest target -> 19-fs-source-harvest; EXPAND ->
   01-tree-expansion and the frontier declaration pattern; a stalled entry ->
   20-creative-vault-review. The plan ranks; those prompts do the work.

3. STANDING RULES, every iteration:
   - Check before searching, PER SOURCE: grep logs/ and Open_Questions.md for
     the name first, and do not re-run a spent route.
   - Log negatives. "Searched X, found nothing" is the deliverable that stops
     the next session repeating it.
   - A null is a statement about the SEARCH, not about the record. Name what was
     searched and what that search structurally cannot contain: one spelling,
     one field value, one repository. Calibrating a zero proves the index holds
     the population; it does NOT prove your filter values were right.
   - Wire only source-backed relationships, and mark every new edge `?`.
   - ! Read the entry before stripping a `?`. It survives legitimately as an
     FS-GAP, a SCHOLARLY HEDGE, or PRIVACY, and a mechanical pass deletes
     documented caveats.
   - Never web-search a person whose life_status is living or unknown.
   - CREATE and every other outward mutation (FS attach, merge, edit) is
     OPERATOR-GATED: do not perform it. QUEUE it, with its evidence, for the
     write-back queue that 23-session-review assembles.

4. RECORD THE ITERATION, before starting the next one:
     python3 scripts/session_plan.py --record --lane <LANE WORKED> \
       --outcome hit|miss --session <SESSION NUMBER> --note "<one line: what moved>"
   - ! --session is the number phase 1 established, and it is what makes N draws in
     one sitting count as ONE sitting for the bandit's floors. Without it the floors
     fall back to the date, so a ten-draw afternoon reads as ten sessions: the
     staleness window closes inside the sitting and the bootstrap floor is satisfied
     in an afternoon. That is a real defect this vault ran with from 30 to 31 JUL.
   - HIT = the lane target was met, or the lane ran dry before it. Anything
     short of target is a MISS with the reason stated. ! This is stricter than
     "the metric moved at all", deliberately: under the old wording sixteen
     consecutive iterations recorded a hit, and an arm that never loses carries
     no signal at all — the bandit was choosing on nothing but its own
     tie-break, and the staleness floor was doing all the real rotation.
   - Record the lane WORKED, never the lane drawn, when they differ.
   - Recording clears `pending`; the next iteration's plan run draws afresh.

5. COMMIT what the iteration produced, one logical unit per commit, gates green
   each time, and APPEND TO THE SESSION LOG as findings land:
   logs/<today>-<slug>.md, one file for the whole sitting. The narrative lives
   THERE, never in the Handoff. Name the slug for the sitting, not for the first
   thing you found — a session that draws four lanes makes an early topical slug
   misleading. Then go back to step 1 for the next iteration.

STOPPING EARLY IS ALLOWED AND MUST BE STATED. If the sitting ends before
[ITERATIONS] iterations (context, my time, a red gate, or the lane running dry),
say how many ran and why it stopped. Do not pad the count with a shallow draw:
the bandit records real cycles, and a fake one is worse than a short session.

ONCE PER SITTING, NOT PER ITERATION — do this once, whatever [ITERATIONS] is and
whichever lanes were drawn:
   - THE PROFILE-REVIEW SLICE. It is due EVERY session, independent of whether
     ROTATE was ever drawn; a skipped session is coverage permanently deferred,
     not deferred-and-caught-up. Draw it, poll it, and record each entry with
     --record. ! Draw only what you will actually poll: a slice drawn at 20 and
     polled at 5 leaves 15 entries looking considered when nobody looked, and
     the unpolled ones must be named at review.
   - NOT here: the Research_Log row and the Handoff close block. Those are one
     per sitting and belong to 24-session-close.

When the iterations are done (or the sitting stops), continue with
23-session-review.
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (same value used in
  `21-session-start.md`).
- **[ITERATIONS]** (optional, default 1) — how many lane draws to run in this
  sitting. Each is a full draw -> work -> record cycle, and the bandit updates
  between them.
- **[LANE_PCT]** (optional) — the Lane target as a percent of the vault
  (`--lane-pct X`). Omit to inherit the profile-review `sample_percent`. The two
  dials are independent: `Iterations` = how many lanes; `Lane target` = how deep
  in each.

## Autoresearch Configuration

**Goal**: Move a lane's own metric by the lane target, N times, with each
iteration recorded honestly, so that the next session's draw is informed by real
observations rather than by an arm that has never lost.

**Metric**: Per iteration, the drawn lane's metric against the session-start
value: EXPAND = people added to the vault off frontier rows; IMPROVE = SOURCE_GAP
entries harvested (0 records -> cited); VERIFY = `?`-marked edges adjudicated; ROTATE = entries polled and
recorded. Per sitting: iterations completed at or above the lane target, out of
`Iterations`.

**Direction**: Maximize iterations that meet their lane target; minimize the lane
backlogs (SILENT, SOURCE_GAP, `?` tokens) those iterations draw from.

**Verify**: `python3 scripts/session_plan.py` at each draw (counts, lane, target;
the draw reason names sittings, not observations, for the two floors);
the owning tool's heartbeat at the end of the iteration
(`extension_frontier.py --heartbeat`, `harvest_sources.py --heartbeat`,
`grep -rhoE "P-[0-9A-Z]{6}\?" [VAULT_PATH]/Family_Tree*.md | wc -l`,
`profile_review.py --heartbeat`); one `history` observation per worked iteration in
the vault's `session_plan_snapshots.json`.

**Guard**:
- **The outcome is HONEST, and short of target is a MISS.** The exploration
  floors guarantee a miss never permanently starves a lane, so there is no
  incentive to flatter the record. A lane that only ever wins teaches the bandit
  nothing.
- **One iteration, one record.** Never record a single piece of work twice, and
  never record a draw that was not worked.
- **A pending draw belongs to the iteration that consumes it.** It is not an
  unrecorded outcome from the previous session, and re-running the plan does not
  replace it.
- **EXPAND is expected to move SILENT the "wrong" way.** Every frontier row
  closed adds the parents it names, which are themselves parentless: net-positive
  SILENT is the shape of a working EXPAND iteration, not a failure. Count the
  people added, which is what the lane target asks for.
- **Read the entry before stripping a `?`** — FS-GAP, SCHOLARLY HEDGE and
  PRIVACY are all legitimate survivals, and only the remainder is actionable.
- **Outward mutations are queued, never performed.** FS attaches, merges, edits
  and creations are operator-gated; the evidence goes in the log and the queue
  goes to phase 3.
- **The profile-review slice is per SITTING and is due every session** whatever
  the lanes were. Partial is fine and must be named entry by entry; silent
  omission is not.
- All standing Operating_Protocol guards apply: check-before-searching per
  source; negatives logged; source-backed edges only, `?` on unverified;
  living/unknown people never web-searched; Research_Log appended via
  `scripts/log_session.py`, never the Edit tool.
- One logical unit per commit; the pre-commit gates pass every time; no
  `--no-verify`.
- **Do not close the session from this prompt.** No Research_Log row, no close
  block, no `session_close.py`. Phases 3 and 4 exist so that the summary is
  written once, over the whole sitting.

**Iterations**: 1 — **the number of LANE DRAWS**, and it is the dial to raise.

One iteration = one full cycle: **draw a lane -> work it -> record its outcome**.
`Iterations: N` runs that cycle N times, and the tooling supports it natively:
`session_plan.py --record --lane X --outcome Y` writes the arm and clears
`pending`, and the next `session_plan.py` draws again. N honest cycles are N
honest observations, and the bandit learns faster than at one draw per calendar
day.

**Lane target**: **a PERCENT OF THE VAULT, counted in people** — the same metric
as the profile-review sample rate. It **defaults to
`profile_review.sample_percent`**, so a vault sets one rate and both loops follow.
Override for one session with `--lane-pct X`, or pin it separately as
`session_plan.lane_target_percent` in `.maintenance.json`, which is worth doing
once the two diverge in cost: a profile poll is a page read or two, while an
EXPAND row can be an afternoon. It is capped at the lane's actual size (the plan
says so when it caps).

`Iterations` is how many lanes you draw; `Lane target` is how deep you go in each.

**Protocol**:

1. Take the pending draw if there is one; otherwise run `session_plan.py` and
   present the counts, the drawn lane, the lane target and the top candidates.
2. Work the lane top-down to the lane target, dispatching to the owning prompt
   for the work type.
3. Apply the standing rules throughout; queue outward mutations instead of
   performing them.
4. Record the iteration with `session_plan.py --record`, hit only at target.
5. Commit the iteration's work, then repeat from 1 until `Iterations` is reached
   or the sitting stops (and say which).
6. Once per sitting: run the profile-review slice, sized to what you will poll.
7. Hand off to `23-session-review`.
