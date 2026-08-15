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
| EXPAND | one frontier row DISPOSED OF: the vault grows by a person (the row gains a sourced parent edge, or the parent it names is minted), **or** the row is closed with a documented negative naming what was searched and why the route is closed |
| IMPROVE | one entry DISPOSED OF: an unsourced entry's records found, read and cited in a `- **Sources**` bullet (prompt 25's sweep), **or** a `SINGLE_SOURCED` entry corroborated from a SECOND host, **or** either closed with a documented negative naming the real route, **or** the person's problem characterised and filed as a numbered `Open_Questions` entry naming a resolver (operator, 02 AUG 2026 — see the note below on how that squares with "prose alone is not a disposition"). ⚠ "FS holds nothing" is NOT a disposition on its own — it closes one repository, and the entry only leaves the pool when the other routes are named too, **or** a **DEFECT row settled**: a `?` edge adjudicated (cleared, contradicted, or classified with its reason on the entry), a **gate finding** resolved / declared, or a **BANKED parent pair disposed of** — a row whose parents were located on another tree and deliberately not wired (`banked_parents`), settled either by finding a record that names them (then mint + wire with `?`) or by a documented negative on the entry. ⚠ **Do NOT wire a banked pair as-is** — an FS couple is a tree assertion, and adopting it is the borrowed certainty the lane exists to remove. ⛔ **Confirming an FS PID is live is NOT a unit** — it is step 0 of prompt 25 and scores nothing (deferred 40) |
| ROTATE | one drawn entry polled AND recorded with `--record`. ⭐ **If the row is flagged `AUDIT (N ARKs)`, re-group its locators by EVENT before trusting the count** (deferred 42): limbs (g)+(h) — children's and siblings' records — are most of a typical FS Sources tab, and measured inflation ran **4x-23x**. The backlog is NOT swept as a campaign; a DRAWN row is audited because the poll opens the Sources tab anyway, and the event descriptors are free only while it is open |

**A UNIT IS A DISPOSITION, NOT A SUCCESS** (changed 01 AUG 2026, operator-directed). Every lane
now credits the same thing: **a person you addressed and will not have to look at again.** Before
this change EXPAND and IMPROVE counted only successes while VERIFY (now retired) and ROTATE counted dispositions,
and the bandit's own record tracked that split exactly — **the two success-only lanes stood at
EXPAND 0/3 and IMPROVE 0/2, the two disposition lanes at VERIFY 4/4 and ROTATE 2/2.** An IMPROVE
iteration that harvested three entries and closed two more as documented negatives scored 3, while
the same five people worked in VERIFY would have scored 5. The lane target is a count of PEOPLE, so
what counts as one has to mean the same thing in each lane.

⛔ **VERIFY WAS COLLAPSED INTO IMPROVE ON 02 AUG 2026 (operator; deferred 39 + 40). THERE ARE
THREE LANES: EXPAND, IMPROVE, ROTATE.** The paragraph below describes the retired design and is
kept because the SHARE mechanism it introduced is still what protects IMPROVE's small populations.

**Why it went.** The two lanes already drew from mostly the same people — **694 in both, 72% of
IMPROVE and 71% of VERIFY-PID** — and the two jobs are ONE ACTION: `25-person-research-sweep`
cannot harvest a person's FamilySearch sources without loading the profile, which *is* the liveness
check. Stale-PID work was justified in this very file as protection for IMPROVE's own harvest, i.e.
it was a **precondition** that had been given equal billing as a lane.

⚠ **THE COLLAPSE IS ASYMMETRIC, AND THAT IS THE WHOLE DESIGN.** IMPROVE stood at **0 wins / 9**
and VERIFY at **11 / 13**, latterly on PID checks alone. A naive merge would hand the expensive
lane a cheap way to meet a floor it had never met, turning every honest miss into a hit and hiding
the fact that six-source sweeps are slow. So:
- **Confirming an FS PID is live SCORES NOTHING.** It is **step 0 of prompt 25** — you are opening
  the profile to harvest it anyway — and the plan annotates drawn rows that need it.
- **`?` edges are no longer a population.** Keying a lane on a self-assigned mark meant it saw
  **76 of 2,393 edge tokens (3.2%)** and could not see **any** of the 8 children carrying an
  unexplained PARENT-GEN MISMATCH. They are now ONE INPUT to a **DEFECT** population that also
  carries the gate findings, and that population gets a reserved share of every IMPROVE draw.
- **The unit stays IMPROVE's**: a person whose RECORD moved.

*(retired design, for the record)* Alongside
`?`-marked edges it offers entries whose FS PID has not been confirmed live within the probe
cooldown — an external id rots, and a profile merged away or deleted reads on a walk as a person
with no relatives, which also silently poisons an IMPROVE harvest run against that PID. The two
populations differ hugely in size (on the reference vault ~34 edges against ~1,131 PIDs), so the
plan reserves a fixed share of the lane target for edges **before** PIDs get any; it prints the
split. Do not "simplify" that into one pool — sampling a merged pool returns roughly half an edge
row per draw and the edge work disappears.

⚠ **A NEGATIVE ONLY COUNTS IF IT REMOVES THE PERSON FROM THE POOL.** Otherwise the same entry is
"disposed of" every session, the candidate list never shrinks, and the count becomes free. A
documented negative must (a) say what was searched and what that search structurally cannot contain,
and (b) land somewhere the candidate builder reads — for a 0-ARK entry FS will never index, that is
a `pids` rule in the vault's `.autoresearch.json` `structural_gap`, which moves it out of the
actionable SOURCE_GAP count. **Prose alone is not a disposition.** If you cannot close it in the
data, it stays on the worklist and does not count.

⭐ **RAISING AN OPEN QUESTION IS A DISPOSITION ONLY FOR A ROW THIS SITTING CANNOT ADVANCE**
(operator, 02 AUG 2026; scope sharpened 15 AUG 2026 with the operator's clarification of intent).
The 02 AUG ruling exists to keep sessions WORKING — prior sessions constantly stopped, thinking
they had "done enough", and the register is the mechanism that parks a blocker and keeps the
sitting moving. It was never meant to make filing a cheap way to score, and by 15 AUG the register
showed what that reading produces: ~140 live questions, nearly all raised within the month, the
audit lanes minting defect questions faster than research absorbed them. So the rule now has an
edge: **a filed question counts as the disposition ONLY when the row is genuinely BLOCKED this
sitting** — the resolver is op-gated, in-person, paywalled, or depends on work that cannot happen
now. **If the question you just filed names a FREE resolver, the filing is not the end of the
row: working that resolver is the same sitting's natural next step, and the disposition is
whatever the work then earns** (`--sourced` / `--corroborated` / `--verified`, or the blocked
filing if the free route dead-ends). **Correction work still counts on the same footing** —
proving a vault value wrong, retracting a bad declaration — that was never the churn.

⚠ **AND IT SITS IN TENSION WITH THE RULE DIRECTLY ABOVE — read both.** A question does NOT shrink
`SOURCE_GAP`; the row stays in the candidate pool. So the two rules are reconciled by SCOPE, not by
one overriding the other:
- **Count the question ONCE, for the sitting that did the work.** A later session that re-notices
  the same problem has not disposed of anything.
- **Say which kind each disposition was** when recording: `--sourced` / `--corroborated` for cited
  records, and name the question numbers in the `--note` for question-dispositions. A draw that was
  ALL questions and no records is legitimate and must be visible as such.
- **A finding of an already-registered SHAPE joins the existing batch question, never a new
  number.** Check `Open_Questions_Index.md` before minting; `question_store.py --append N` puts
  the row under the right heading mechanically. Proliferating near-duplicate questions is how the
  register became unreadable.
- **It is not a substitute for closing what can be closed.** If the person can be sourced, source
  them; if the negative can land in `structural_gap`, land it.

⭐⭐ **WHEN THE LANE RUNS DRY, DRAIN THE REGISTER — do not stop, and do not conclude "done
enough" (standing rule, operator-directed 15 AUG 2026).** The register IS the fallback work
queue: `Open_Questions_Index.md` marks which live questions name a `free` resolver and which
carry an unread located source (`UNREAD-SRC`). When the drawn lane's target is met or its pool
is exhausted and iterations remain, take the next `free`-tagged question (oldest first), work
its named resolver, and record the outcome against the lane you are in with the question number
in the `--note`. Ten consecutive sittings ran off-lane on question work before this rule existed
because it was the most productive thing available; the rule makes that path legitimate and
RECORDED instead of invisible to the bandit.

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
   dispatching to the owning prompt for the work type. The plan RANKS; those
   prompts do the work, and each is applied to ONE PERSON at a time:

     IMPROVE          -> 25-person-research-sweep   (the default unit of work)
     EXPAND           -> 01-tree-expansion + the frontier declaration pattern;
                         use 25 when the parent is not findable on FS either
     IMPROVE, defect  -> 18-edge-verification for a `?` edge; for a GATE finding,
                         resolve the generation or declare it in known_gen_collapse
     any drawn row     -> if it is marked "PID liveness unconfirmed", confirm the
       with a stale PID   profile resolves BEFORE harvesting (step 0, scores NOTHING)
     ROTATE           -> the profile-review poll; escalate a HIT to 25
     a stalled entry  -> 20-creative-vault-review

   ! 19-fs-source-harvest IS NO LONGER THE DEFAULT for a sourcing target. It is
   the FamilySearch LEG of 25, and reaching for it alone is how the vault ended
   up with 660 of its 691 source-citing entries on one host. Run 25 and let FS
   be step 2a of a sweep, not the whole sweep.

3. STANDING RULES, every iteration:
   - Check before searching, PER SOURCE: grep logs/ and Open_Questions.md for
     the name first, and do not re-run a spent route.
   - Log negatives. "Searched X, found nothing" is the deliverable that stops
     the next session repeating it.
   - ! ANYTHING NEEDING FURTHER RESEARCH GETS AN Open_Questions ENTRY, not just a
     narrative bullet. An entry states CURRENT STATE; Open_Questions is the
     register of what is UNRESOLVED, and a discrepancy recorded only on an entry
     is invisible to everything that picks work. Owed when resolving it needs
     work not yet done (a source located but unread, a contradiction, a choice
     between candidates); NOT owed for something you settled, or for a closed
     negative with no route left — that is a declaration. Batch thin ones into
     one question, cross-link both ways, and name what would settle it. Full
     rule in CLAUDE.method.md.
   - ! WRITE QUESTIONS THROUGH scripts/question_store.py, NEVER the Edit tool —
     `--new` mints the number and requires the resolver, `--append` lands a
     write-up inside the right block, `--resolve` writes an archivable heading.
     Same rule and same reason as log_session.py for the Research_Log: every
     orphaned write-up and zombie question came from hand-splicing a shard.
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
say how many ran and why it stopped.

! A MISS IS A RESULT, NOT WASTED EFFORT, AND IS NEVER A REASON TO STOP EARLY
(operator, 07 AUG 2026). The only thing forbidden here is recording a cycle
that was NOT WORKED. An iteration you genuinely drew, genuinely worked, and
that fell short of its lane target is a REAL observation: it is the single
most informative thing you can hand the bandit, because an arm that only ever
wins carries no signal at all. Record it as a miss, say what blocked it, and
carry on to the next iteration.

  - "This draw would probably miss" is NOT a reason to skip it. Run it.
  - "The remaining lane is expensive / thin / slow" is NOT a reason to stop.
    That judgement was already made when the floor was set.
  - Negative results are results. A documented negative, a route closed, a
    row proven unworkable and declared — all of these advance the record and
    all of them belong in an iteration that gets recorded.

! THIS PARAGRAPH USED TO SAY "do not pad the count with a shallow draw: the
bandit records real cycles, and a fake one is worse than a short session", and
that wording caused the failure it was meant to prevent. Session #150 ran two
of three requested iterations and cited this line to justify not starting the
third — reasoning that the honest options were a big draw it might not finish
or a small one that would miss, and that the small one was "theatre". It is
not theatre; it is data. SHALLOW meant FABRICATED, never SMALL-YIELD, and the
distinction is now spelled out because one session already read it the other
way.

ONCE PER SITTING, NOT PER ITERATION — do this once, whatever [ITERATIONS] is and
whichever lanes were drawn:
   - THE PROFILE-REVIEW SLICE. It is due EVERY session, independent of whether
     ROTATE was ever drawn; a skipped session is coverage permanently deferred,
     not deferred-and-caught-up. Draw it, poll it, and record each entry with
     --record.
     ! SINCE 08 AUG 2026 ROTATE IS NO LONGER A BANDIT LANE (deferred 51 option 3):
     the bandit chooses between EXPAND and IMPROVE only. The slice is UNAFFECTED --
     it runs every sitting on its own cadence, which is precisely why taking ROTATE
     out of the draw cost no coverage.
     ! ALSO RECORD ONE LANE OBSERVATION FOR THE SLICE:
       session_plan.py --record --lane ROTATE --outcome hit|miss --session <N>
     Its observations no longer feed any choice, and they are kept anyway
     (operator, 08 AUG 2026): a lane that RUNS but is not COUNTED is the shape that
     let the FS write-back queue go quiet. ! Draw only what you will actually poll: a slice drawn at 20 and
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
entries harvested (0 records -> cited) + defect rows settled; ROTATE = entries polled and
recorded. Per sitting: iterations completed at or above the lane target, out of
`Iterations`.

**Direction**: Maximize iterations that meet their lane target; minimize the lane
backlogs (SILENT, SOURCE_GAP, `?` tokens) those iterations draw from.

**Verify**: `python3 scripts/session_plan.py` at each draw (counts, lane, target;
the draw reason names sittings, not observations, for the two floors);
the owning tool's heartbeat at the end of the iteration
(`extension_frontier.py --heartbeat`, `harvest_sources.py --heartbeat`,
`grep -rhE "P-[0-9A-Z]{6}\?" [VAULT_PATH]/Family_Tree*.md | grep -v "^>" | grep -oE "P-[0-9A-Z]{6}\?" | wc -l`,
`profile_review.py --heartbeat`); one `history` observation per worked iteration in
the vault's `session_plan_snapshots.json`.

**Guard**:
- **The outcome is HONEST, and short of target is a MISS.** The exploration
  floors guarantee a miss never permanently starves a lane, so there is no
  incentive to flatter the record. A lane that only ever wins teaches the bandit
  nothing.
- ⭐ **A MISS COSTS NOTHING AND IS NEVER A REASON TO SKIP AN ITERATION**
  (operator, 07 AUG 2026: *"negative results are still results; I don't consider
  'misses' to be wasted effort"*). Expecting to miss is not grounds for not
  drawing; a lane being expensive or thin is not grounds for stopping. **Prefer
  a worked miss to an unrun iteration** — the miss is an observation and the
  unrun iteration is nothing.
- **One iteration, one record.** Never record a single piece of work twice, and
  never record a draw that was not worked.
  - ⚠ **This is the ONLY thing the "no shallow draw" rule forbids: a cycle
    RECORDED WITHOUT BEING WORKED.** It has never meant "a cycle with a small
    yield". Session #150 read it the second way and left a requested third
    iteration unrun; the prose in the loop section now says so explicitly.
- **A pending draw belongs to the iteration that consumes it.** It is not an
  unrecorded outcome from the previous session, and re-running the plan does not
  replace it.
- **EXPAND is expected to move SILENT the "wrong" way, AND SO IS IMPROVE'S BANKED
  TIER.** Every frontier row closed adds the parents it names, which are themselves
  parentless: net-positive SILENT is the shape of a working extension iteration, not
  a failure. Count the people added, which is what the lane target asks for.
  - ⚠ **THE GUARD IS PER-EFFECT, NOT PER-LANE.** It named EXPAND alone until 04 AUG
    2026, when `banked_parents` made the same work drawable from **IMPROVE** — so a
    lane whose own metric is SOURCE_GAP now routinely pushes SILENT up, and nothing
    said that was expected. Given the standing rule that a non-zero gate is a
    REGRESSION rather than a backlog, that reads as damage and would be
    "investigated" by a future session at real cost.
  - ⭐ **WIRING A BANKED PAIR MOVES THREE COUNTS THE WRONG WAY AT ONCE, and all three
    are honest.** Measured on the 11-row backlog at adoption, each naming exactly 2
    parents, none already in the vault:

    | count | direction | why |
    |---|---|---|
    | DECLARED | **-11** | a wired row is no longer parentless, so it leaves the frontier population entirely |
    | SILENT | **+22** | its two parents arrive, themselves parentless |
    | SOURCE_GAP | **up to +22** | a record naming the parents documents the CHILD — limb (g) `Named-in`, off the census — so each parent arrives at 0 own records |
    | `?` edge tokens | **+22** | every new edge is wired unverified, as it must be |

    ⭐ The minted parents land in the exact shape of the canonical limb-(g) case:
    present only because a child's record names them, and correctly `SOURCE_GAP`.
  - ⛔ **DO NOT pre-declare the minted parents to keep SILENT flat.** That is
    "never bulk-declare to reach 0" in its purest form — a declaration inherits the
    correctness of its REASON, and there is no reason yet.
  - ⚠ **AND THIS IS A CROSS-LANE EFFECT THE BANDIT DOES NOT MODEL.** An IMPROVE draw
    scoring a legitimate hit inflates EXPAND's backlog. The lanes are a small
    economy, not independent arms; record the outcome on what the lane DISPOSED OF,
    and let the frontier count move.
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
   for the work type — `25-person-research-sweep` for IMPROVE and for any row
   needing sources, since it is the per-PERSON unit this loop repeats.
3. Apply the standing rules throughout; queue outward mutations instead of
   performing them.
4. Record the iteration with `session_plan.py --record`, hit only at target.
5. Commit the iteration's work, then repeat from 1 until `Iterations` is reached
   or the sitting stops (and say which).
6. Once per sitting: run the profile-review slice, sized to what you will poll.
7. Hand off to `23-session-review`.
