#!/usr/bin/env python3
"""session_plan.py — ONE ranked session-start worklist, with the lane DRAWN, not argued.

WHY IT EXISTS (29 JUL 2026 framework review). The toolkit answers "what should this
session work?" with FIVE partial answers that rank overlapping populations in
incompatible orders: extension_frontier (parentless, gen ascending), keystone_report
(LOAD, now a tiebreaker), harvest_sources (the SOURCE_GAP worklist -- wired into
IMPROVE 31 JUL 2026, deferred 24; it was named here for months while no lane read
it), profile_review (bandit draw), and
buildout (edgeless nodes by cluster). Nothing joined them, so every session re-argued
the arbitration from prose — and the banner's information density (10 integrity gates
to 5 aggregate work counts) pointed the opposite way from the stated EXTENSION-first
priority. "Sessions trip over the priorities" was the operator's summary, and the
silent-leaf incident (leaf nodes without edges ignored until forced) was its symptom.

WHAT IT DOES. Builds one plan with four LANES, each fed by the existing tool's OWN
candidate-builder (imported, never re-derived — the "two readers, one entry" rule):

  EXPAND   extension_frontier SILENT rows: no parents edge, no declared reason.
           Ranked gen ascending (shallower = cheaper to verify, likelier to matter).
  IMPROVE  harvest_sources SOURCE_GAP rows with a usable FS PID: entries carrying
           ZERO cited records that a Recipe-S harvest can actually be run against.
           Ranked gen ascending, with keystone LOAD as a TIEBREAKER.
           ** REDEFINED 31 JUL 2026 (deferred 24). ** It was keystone_report's
           LOAD x THIN, which measures whether anyone WROTE THE ENTRY UP rather
           than whether it is SOURCED — a different question, and a disjoint
           population (of its last candidate, zero were SOURCE_GAP). The keystone
           report still exists and still finds real work; it is now a REPORT
           (`keystone_report.py --summary`), not this lane's definition.
  VERIFY   entries whose `parents:`/`spouse:` lists carry `?`-marked (not yet
           FS-confirmed) edges. Ranked gen ascending. ⚠ Read the entry before
           stripping a `?` — it survives legitimately as FS-GAP, SCHOLARLY HEDGE,
           or PRIVACY (see CLAUDE.method.md).
  ROTATE   the profile-review bandit's draw for this session (delegated to
           profile_review.py, which owns that state).

...and DRAWS one recommended lane with a small bandit over lanes (state in the
vault's session_plan_snapshots.json):

  1. BOOTSTRAP FLOOR: while any non-empty lane has been worked in fewer than
     MIN_SAMPLE SITTINGS, draw the least-sampled lane. No exploitation on tiny n.
  2. STALENESS FLOOR: any lane not drawn across the last STALE_AFTER SITTINGS is due.
     The anti-assumption device: no lane silently falls off the rotation.
  3. Otherwise EXPLOIT: highest Laplace-smoothed win rate (wins+1)/(iterations+2).

  ** THE FLOORS COUNT SITTINGS; THE REWARD COUNTS ITERATIONS. ** They were the same
  thing until `Iterations: N` arrived (30 JUL 2026) and one sitting began emitting N
  observations, at which point a ten-draw afternoon satisfied both floors by itself.
  A floor asks "is this lane still in the rotation", which is a question about
  SITTINGS; the win rate asks "does working it pay", which is a question about
  independent TRIALS. See sitting_of().

A "win" is an ITERATION MEETING ITS LANE TARGET, or the lane running dry before it.
** Short of target is a MISS. **

** ONE UNIT IS ONE PERSON DISPOSED OF, IN EVERY LANE ** (changed 01 AUG 2026,
operator-directed). A unit is a person you addressed and will not have to look at
again: a frontier row extended OR closed with a documented negative; a SOURCE_GAP
entry harvested OR closed as unharvestable; a `?` edge cleared, contradicted or
classified; a rotation entry polled and recorded whatever the outcome. Previously
EXPAND and IMPROVE credited only SUCCESSES while VERIFY and ROTATE credited
dispositions, and the arms tracked that split exactly -- the two success-only lanes
sat at EXPAND 0/3 and IMPROVE 0/2, the two disposition lanes at VERIFY 4/4 and
ROTATE 2/2. Since the target counts PEOPLE, a unit has to mean the same thing in
each lane or the lanes are not comparable and the bandit is choosing on the
definition rather than on the work.

! A NEGATIVE COUNTS ONLY IF IT REMOVES THE PERSON FROM THE CANDIDATE POOL --
otherwise the same entry is "disposed of" every session and the count is free.
For a 0-ARK entry FS will never index, that means a `pids` rule in the vault's
.autoresearch.json `structural_gap`. Prose alone is not a disposition. That is stricter than
the original "the metric moved at all", which produced sixteen consecutive hits: an arm
that never loses carries no signal, and the draw was being decided by the tie-break and
the staleness floor alone. Recorded per iteration by prompt 22-research-iterations via
`--record`; the close (24-session-close) normally records NOTHING, since recording again
would double-count one piece of work. The draw is a RECOMMENDATION: the operator can
override it, and the override is itself recordable (record the lane actually worked).

USAGE
  python3 scripts/session_plan.py                    # the session-start quality report
  python3 scripts/session_plan.py --limit 8          # more rows per lane
  python3 scripts/session_plan.py --json
  python3 scripts/session_plan.py --heartbeat        # cheap one-liner (SessionStart banner;
                                                     #   reads state only, builds nothing)
  python3 scripts/session_plan.py --record --lane EXPAND --outcome hit --note "..."
                                                     # at the END OF EACH ITERATION

Zero dependencies. Absent state file = fresh bandit (bootstrap floor governs).
Optional .maintenance.json `session_plan` block: {"per_lane": N, "min_sample": N,
"stale_after": N}; absent = defaults. Advisory: never blocks anything.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

SNAPSHOT_FILE = "session_plan_snapshots.json"
CONFIG_KEY = "session_plan"
LANES = ("EXPAND", "IMPROVE", "VERIFY", "ROTATE")

# What ONE unit of the lane target is, per lane. The target is a percent of the
# vault counted in PEOPLE (operator, 30 JUL 2026), so the units are deliberately
# comparable across lanes: 1.5% of the vault means the same amount of session
# whichever lane is drawn.
# ** A UNIT IS A DISPOSITION, NOT A SUCCESS ** (operator, 01 AUG 2026). Every lane
# credits the same thing: a person addressed and not needing to be looked at again.
# This module printed the SUCCESS-ONLY wording for EXPAND and IMPROVE for a day
# after `22-research-iterations` was changed, so the plan told every session one
# definition while the prompt stated another. Keep these strings in step with that
# prompt's unit table.
#
# ⚠ A disposition must also REMOVE the person from the pool — "prose alone is not a
# disposition" (see the prompt). A documented negative that no candidate builder can
# see leaves the row on the worklist and does not count.
LANE_UNITS = {
    "EXPAND": "one frontier row DISPOSED OF: it gains a sourced parent edge or the\n              parent it names is minted, OR it is closed with a documented negative",
    "IMPROVE": "one SOURCE_GAP entry DISPOSED OF: records found, read and cited in a\n              `- **Sources**` bullet (Recipe-S / prompt 19), OR closed as a\n              documented negative naming the real route",
    "VERIFY": "one `?` edge adjudicated: cleared, contradicted, or classified "
              "with its reason on the entry",
    "ROTATE": "one drawn entry polled AND recorded with --record",
}
# Defaults; override via .maintenance.json `session_plan` block.
PER_LANE = 5          # rows shown per lane (DISPLAY only -- not a work target)

# ** THE LANE TARGET: how many PEOPLE to work off the drawn lane in ONE ITERATION,
# as a PERCENT OF THE VAULT ** (operator, 30 JUL 2026: "lane targets should use the sample size
# metric -- i.e. X% of the vault"). Same form as the profile-review sample rate,
# so ONE number describes a session's workload whatever lane is drawn, and it
# scales with the vault instead of being a row count that silently ages.
#
# It DEFAULTS to the profile-review `sample_percent`, so a vault sets one rate and
# both loops follow it. It is separately settable because the two are not the same
# unit of effort: a profile poll is a page read or two, while an EXPAND row can be
# an afternoon. Diverge them when that starts to bite.
#
# Resolution order: --lane-pct > .maintenance.json session_plan.lane_target_percent
# > .maintenance.json profile_review.sample_percent > LANE_TARGET_PERCENT.
LANE_TARGET_PERCENT = 1.5
MIN_SAMPLE = 2        # bootstrap floor: no exploitation until every lane has this many
STALE_AFTER = 6       # staleness floor: a lane undrawn for this many draws is due

# ** CANDIDATE ROTATION (operator-directed, 01 AUG 2026, session #127). **
#
# THE DEFECT. Three of the four lanes ranked candidates with a DETERMINISTIC sort
# (gen ascending) and took the top N. So whichever rows sit at the shallow end are
# presented FIRST, EVERY SESSION, UNTIL THEY CLEAR -- and a row that is merely HARD
# never clears. Measured on the reference vault at #127: ONE entry's parent edge was
# walked and classified a permanent FS-GAP independently in THREE separate sittings,
# by three sessions that each reached the same answer unaided -- and it still ranked
# FIRST in the next draw. The `adjudicated` key (deferred
# 32) fixed the SETTLED half of this by removing judged rows from the pool; it did
# nothing for rows that are open, hard, and permanently at the head of the list.
#
# ROTATE never had the problem, because profile_review has carried a per-entry
# cooldown (`last_polled` + POLL_COOLDOWN_DAYS) since it was written -- and the one
# time that cooldown broke (30 JUL 2026: it PRINTED the FS PID but keyed the
# cooldown on the vault id, so recording the displayed key never entered cooldown)
# the symptom was exactly this, the same people redrawn every session. So: four
# lanes, four different PERMANENT-exclusion stores (`adjudicated` / frontier
# `declared` / `.autoresearch.json structural_gap` / none), and exactly ONE
# cooldown. This lifts the cooldown to all four.
#
# ** COOLDOWN, NOT RANDOMISATION, IS THE FIX -- and the distinction is the point. **
# The operator's instinct was to randomise the candidate list. Randomisation makes
# repetition UNPREDICTABLE, not RARE: a shuffle can hand you the same row twice
# running. A cooldown is a guarantee. Randomisation also throws away real priority
# -- gen ascending is not arbitrary, shallower means closer to the anchor. So the
# order is: cooldown first (guarantee), then a SEEDED STRATIFIED sample of what is
# left (variety), with the top of the priority order always represented.
#
# ** A COOLED ROW IS DEPRIORITISED, NEVER REMOVED. ** It goes to the BACK of its
# lane, so the lane size stays honest, a lane cannot be starved into looking empty,
# and a session that works past the target still reaches it. If EVERY row is
# cooling the original order is returned unchanged.
#
# ** OFFERS ARE STAMPED AT `--record`, NOT AT PLAN TIME. ** The plan is run several
# times per sitting (and by the SessionStart hook), so stamping on display would
# cool rows nobody looked at, and would do it again on every re-run. Instead the
# plan writes the ids it offered into `pending.offered`, and `record()` stamps them
# only when the recorded lane MATCHES the drawn one -- i.e. only when a session
# actually worked that lane. Override the lane and nothing is cooled, which is
# correct: nobody looked at those rows.
OFFER_COOLDOWN = 3    # sittings a row spends at the BACK after being offered and not disposed
HEAD_FRACTION = 3     # 1/N of the target is taken strictly by priority; the rest is sampled


# ---------------------------------------------------------------------------
# Lane candidate-builders. Each delegates to the owning tool's own logic.
# ---------------------------------------------------------------------------
def lane_expand(vault):
    import extension_frontier as ef
    rows = [r for r in ef.rows_with_bodies(vault) if not r["declared"]]
    rows.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0,
                             ef.TIER_ORDER.get(r["tier"], 3)))
    return [{"id": r["id"], "name": r["name"], "gen": r["gen"], "file": r["file"],
             "why": "no parents edge, no declared reason"
                    + (" (spouse-linked leaf)" if r["spouse"] else "")}
            for r in rows]


def harvestable_pid(pid):
    """A PID a Recipe-S harvest can actually be run against."""
    p = (pid or "").strip()
    return bool(p) and p.upper() not in ("TBD", "NONE", "-")


def lane_improve(vault):
    """SOURCE_GAP entries with a usable FS PID — the source-harvest worklist.

    ** REDEFINED 31 JUL 2026 (operator; deferred_decisions 24). ** This lane used
    to be `keystone_report` rows with `load >= 1 AND thin >= 3`, which measures
    NARRATIVE COMPLETENESS ("has anyone written this entry up"), not sourcing. The
    operator's question was the finding: IMPROVE is supposed to be about enhancing
    entries via source harvesting, so its population is the source census.

    What the measurement showed, and why the fix is not just swapping the metric:

      - **No lane fed the source census at all.** This module's own header comment
        listed `harvest_sources` as a candidate source, and `22-research-iterations`
        routes "a harvest target -> 19-fs-source-harvest" — but nothing produced
        harvest targets. Recipe-S ran on a calendar cadence, outside the bandit.
      - The two populations were **disjoint**: of the old filter's 1 candidate,
        ZERO were SOURCE_GAP.
      - **`load >= 1` was the binding constraint, not `thin`.** Keeping LOAD as a
        FILTER and swapping in SOURCE_GAP would have given a SEVEN-row lane, because
        an unsourced entry is typically an untouched leaf with no wired ancestry
        above it, so its LOAD is 0 by construction. (Inversely, LOW_COVERAGE has
        ~8x more load-bearing rows than SOURCE_GAP: 1-3 ARKs means somebody already
        worked the entry, which usually means its parents got wired too.)

    So LOAD is DEMOTED FROM FILTER TO TIEBREAKER: load-bearing entries sort to the
    top without excluding the rest of the backlog.

    The category comes from `harvest_sources.gather_records()`, not from an ARK
    count, and that distinction is load-bearing: BOOK_SOURCED and UNCITED entries
    ALSO have 0 ARKs. SOURCE_GAP is specifically the harvestable remainder, after
    the structurally-unsourceable rows are split out — and `gather_records` has
    already applied the privacy gate, so living/unknown people are re-categorised
    to LIVING_EXCLUDED and cannot appear here.
    """
    import harvest_sources as hs
    import keystone_report as kr
    rows = [r for r in hs.gather_records()
            if r.get("category") == "SOURCE_GAP" and harvestable_pid(r.get("pid"))]
    load = kr.load_by_id()          # no census: LOAD is pure graph reachability
    for r in rows:
        r["_load"] = load.get(r["id"], 0)
    # Shallow generations first (they anchor the most descendants and their records
    # are the densest), then LOAD as the tiebreaker, then name for a stable order.
    rows.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0, -r["_load"], r["name"] or ""))
    return [{"id": r["id"], "name": r["name"], "gen": r["gen"],
             "file": r.get("narr_file") or "?",
             "why": f"SOURCE_GAP: 0 records, FS {r['pid']} harvestable"
                    + (f"; {r['_load']} people lean on it" if r["_load"] else "")}
            for r in rows]


def lane_verify(vault, include_adjudicated=False):
    """`?`-marked edges that have NOT already been walked and judged.

    ** ADJUDICATED EDGES ARE SUBTRACTED (deferred 32, operator-directed 01 AUG 2026). **
    A `?` means two different things: "nobody has checked this" and "somebody
    checked this and the `?` is CORRECT" (FS-GAP, scholarly hedge, privacy). This
    builder keyed on the mark alone, so a settled edge looked identical to an
    untouched one and was re-offered every session. Measured on the reference
    vault: of 135 `?` edges only 35 were FS-checkable at all, and 5 of those had
    already been judged; two more carried hedges written in prose that no pattern
    matches, which is why the marker has to live in the DATA.

    That also made settled work UNCOUNTABLE. The lane floor is a count of PEOPLE
    (operator: at least 1.5% of the vault per draw, same in every lane), and
    `22-research-iterations` requires a disposition to REMOVE the person from the
    pool -- "prose alone is not a disposition". Classifying an edge and retaining
    its `?` left the row in the pool forever, so the work could never count toward
    the floor no matter how much of it was done. The `adjudicated` key is what
    makes it count.

    `--include-adjudicated` brings them back for an audit pass.
    """
    import re
    import gen_person_index as g
    edge_re = re.compile(r"(parents|spouse):\s*'\[([^\]]*)\]'")
    adj_re = re.compile(r"adjudicated:\s*'\[([^\]]*)\]'")
    id_re = re.compile(r"P-[0-9A-Za-z]{5,7}")
    living_re = re.compile(r"life_status:\s*(living|unknown)")
    rows = []
    for p in g.parse_narrative():
        meta = p.get("block") or ""
        if living_re.search(meta):
            continue  # privacy: a `?` here is unclearable by web research
        adj = set()
        if not include_adjudicated:
            m = adj_re.search(meta)
            if m:
                adj = set(id_re.findall(m.group(1)))
        marked, settled = [], 0
        for kind, ids in edge_re.findall(meta):
            # Count only `?` tokens whose TARGET id is not already adjudicated.
            open_n = 0
            for tok in (t.strip() for t in ids.split(",")):
                if not tok.endswith("?"):
                    continue
                tid = id_re.search(tok)
                if tid and tid.group(0) in adj:
                    settled += 1
                else:
                    open_n += 1
            if open_n:
                marked.append(f"{open_n} {kind}")
        if marked:
            why = "unconfirmed edges: " + ", ".join(marked) \
                  + " — read entry before stripping ? (FS-gap/hedge)"
            if settled:
                why += f" [{settled} already adjudicated, not offered]"
            rows.append({"id": p.get("id"), "name": p.get("name") or "?",
                         "gen": p.get("gen"), "file": p.get("file") or "?",
                         "why": why})
    rows.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0))
    return rows


def lane_rotate(vault, sample_percent=None):
    """The profile-review draw, delegated: that tool owns its own bandit state.
    Subprocess, not import — its draw path reads/derives its own census and the
    --json contract is the stable surface."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile_review.py")
    try:
        cmd = [sys.executable, script, "--json"]
        if sample_percent:                      # per-session rate override, forwarded
            cmd += ["--sample-percent", str(sample_percent)]
        r = subprocess.run(cmd,
                           capture_output=True, text=True, timeout=600,
                           env={**os.environ, "AUTORESEARCH_VAULT": vault})
        d = json.loads(r.stdout)
    except Exception as e:
        # ** DO NOT return [] SILENTLY. ** An empty list renders as "ROTATE 0
        # candidates", which reads as "nothing to poll" when it actually means
        # the subprocess failed or its --json contract broke. That exact
        # confusion happened on 30 JUL 2026 when a banner was written to stdout.
        print(f"session_plan: WARNING - the ROTATE lane could not be read from "
              f"profile_review.py ({type(e).__name__}: {e}). Reporting 0 "
              f"candidates, which is a TOOL FAILURE, not an empty worklist.",
              file=sys.stderr)
        return []
    return [{"id": e.get("id"), "name": e.get("name"), "gen": e.get("gen"),
             "file": e.get("region") or "", "why": f"rotation draw [{e.get('arm')}]: "
             f"{e.get('draw_reason')}; {e.get('_why') or ''}"}
            for e in d.get("draw", [])]


# ---------------------------------------------------------------------------
# The lane bandit
# ---------------------------------------------------------------------------
def load_state(vault):
    p = os.path.join(vault, SNAPSHOT_FILE)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"arms": {}, "history": [], "pending": None}


def save_state(vault, state):
    p = os.path.join(vault, SNAPSHOT_FILE)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
        f.write("\n")


def resolve_lane_target(vault, cfg, override=None):
    """(people, percent, source) -- how many PEOPLE to work off the drawn lane
    in ONE iteration (one draw -> work -> record cycle).

    A PERCENT of the person-record pool, mirroring profile_review's sample rate;
    see LANE_TARGET_PERCENT. Falls back to that loop's `sample_percent` so a vault
    that sets one rate gets both."""
    src = "default"
    pct = LANE_TARGET_PERCENT
    try:
        with open(os.path.join(vault, ".maintenance.json"), encoding="utf-8") as f:
            m = json.load(f)
        if (m.get("profile_review") or {}).get("sample_percent") is not None:
            pct, src = float(m["profile_review"]["sample_percent"]), "sample_percent"
        if cfg.get("lane_target_percent") is not None:
            pct, src = float(cfg["lane_target_percent"]), "config"
    except Exception:
        pass
    if override is not None:
        pct, src = float(override), "session-override"
    if pct <= 0:
        raise SystemExit("session_plan: lane target percent must be > 0")
    try:
        import gen_person_index as _g
        pool = sum(1 for _ in _g.parse_narrative())
    except Exception:
        pool = 0
    return (max(1, round(pool * pct / 100.0)) if pool else 0), pct, src


def target_and_dryness(lane_target, lane_size):
    """-> (target, is_dry). THE TARGET IS NEVER CAPPED TO THE LANE SIZE.

    Removed 31 JUL 2026 (operator: "I don't see any value in the cap"). main() used to
    print `min(lane_target, lane_size)`, which **relabelled an empty lane as a met goal**:
    a 1-row lane printed "LANE TARGET: 1", so any work at all scored a full-strength hit.
    That is the "an arm that never loses carries no signal" defect the 31 JUL arms reset
    was called to fix, arriving by a different route — and it had already fired, because
    IMPROVE has been drawn twice under the new hit rule and its target was capped BOTH
    times (5 of 21, then 1 of 21). The configured target has never actually been tested.

    The cap was also never load-bearing: **the hit rule already treats a lane that RUNS
    DRY as a hit**, so a short lane was never at risk of being punished. And it was
    internally inconsistent — `--json` has always emitted the UNCAPPED value, so the
    printed number and the machine-readable one disagreed.

    What the cap was really carrying is the DRYNESS SIGNAL, and that is worth keeping:
    `is_dry` says the lane cannot reach target, which is information about the LANE
    rather than a reduction of the goal.
    """
    return lane_target, (lane_size < lane_target)


def sitting_of(entry):
    """The SITTING an observation belongs to. `session` when stamped, else the date.

    ** WHY THIS EXISTS (31 JUL 2026). ** The floors below were written on 29 JUL when
    one sitting produced exactly one observation, so counting observations and counting
    sittings were the same thing. On 30 JUL `Iterations: N` was introduced and one
    sitting began emitting N observations -- in the PROMPTS only, so nothing here was
    revisited. The floors silently changed unit: with Iterations=10 the staleness
    window closes INSIDE a single sitting and the bootstrap floor is satisfied in an
    afternoon, i.e. the bandit behaves as though ten sessions had passed. Measured on
    the reference vault: 16 observations over 2 calendar days, 12 of them in one day.

    Legacy rows carry no `session`, so they fall back to `date`. That is imperfect
    (two sittings in one day is normal here and collapses to one) but it is the
    conservative direction: it under-counts sittings rather than over-counting them."""
    s = entry.get("session")
    return f"S{s}" if s not in (None, "") else f"D{entry.get('date')}"


def arm_of(state, lane):
    """{wins, iterations} for a lane, accepting the legacy `sessions` key.

    The field counts ITERATIONS (one per observation), which is the right unit for a
    REWARD estimate -- each iteration is an independent trial. It is the FLOORS that
    must count sittings; keeping the two units distinct is the whole point of the
    31 JUL fix, so the field was renamed away from `sessions` to stop it being read
    as a sitting count."""
    a = (state.get("arms") or {}).get(lane) or {}
    return {"wins": a.get("wins", 0),
            "iterations": a.get("iterations", a.get("sessions", 0))}


def since_epoch(state):
    """History the FLOORS are allowed to see: observations from the current rule epoch.

    ** A RESET HAS TO RESET BOTH HALVES (31 JUL 2026). ** Zeroing `arms` alone does
    not re-arm the floors, because they count sittings out of `history` -- so a vault
    that reset its tally after `hit` was redefined went straight to the exploit branch
    with every rate at the 0.50 prior, and the tie-break handed the same lane out six
    sittings running. That is worse than the tally it replaced. When `arms_reset.date`
    is present, observations recorded before it are kept in `history` as the record but
    no longer feed the floors, so the bootstrap floor re-samples each lane under the
    rule now in force.

    ** A RESET CAN ALSO BE PER-LANE (31 JUL 2026, deferred 24). ** When ONE lane's
    DEFINITION changes, its observations stop describing the population the lane now
    draws from, while every other lane's stay valid — so a global reset would throw
    away good data to fix one arm. `lane_epochs: {"IMPROVE": "2026-08-01"}` retires
    just that lane's history from the floors; it COMPOSES with the global
    `arms_reset.date` rather than replacing it, and an absent key means "no per-lane
    epoch", i.e. exactly the previous behaviour.
    """
    hist = state.get("history", [])
    epoch = (state.get("arms_reset") or {}).get("date")
    lane_epochs = state.get("lane_epochs") or {}
    out = []
    for h in hist:
        d = h.get("date") or ""
        if epoch and d < epoch:
            continue
        le = lane_epochs.get(h.get("lane"))
        if le and d < le:
            continue
        out.append(h)
    return out


def sittings_in_order(history):
    """Distinct sittings, oldest first, de-duplicated but order-preserving."""
    seen, out = set(), []
    for h in history:
        k = sitting_of(h)
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def cooling(state, lane, row_id, cooldown=OFFER_COOLDOWN):
    """(is_cooling, sittings_since_offered) for one row in one lane.

    Keyed on the VAULT id, never on an external PID — that is the exact bug that
    broke the ROTATE cooldown on 30 JUL 2026 (printed one key, cooled on another),
    and the whole point of `id` being the identity key. A stamp naming a sitting
    that has fallen out of the retained history reads as COLD rather than as an
    error: history is trimmed by epoch, and an unreadable stamp must not pin a row
    at the back for ever.
    """
    stamp = ((state.get("offered") or {}).get(lane) or {}).get(row_id)
    if not stamp:
        return False, None
    order = sittings_in_order(state.get("history") or [])
    if stamp not in order:
        return False, None
    since = len(order) - 1 - order.index(stamp)
    return since < cooldown, since


def stamp_offered(state, lane, ids, sitting_key):
    """Mark `ids` as offered in `lane` during `sitting_key`. Called from record()."""
    d = state.setdefault("offered", {}).setdefault(lane, {})
    for i in ids:
        if i:
            d[i] = sitting_key
    return state


def rotate_candidates(rows, state, lane, target, cooldown=OFFER_COOLDOWN,
                      head_fraction=HEAD_FRACTION, seed_extra=""):
    """Order one lane's candidates: priority head, seeded sample, then cooled rows.

    Returns (ordered_rows, n_cooling). Pure function of its inputs — pinned by
    scripts/test_session_plan.py. Length is always preserved: this REORDERS, it
    never filters, so `len(rows)` stays the honest lane size.

    The seed is derived from the lane and the number of recorded observations, so
    the list is STABLE across the several plan runs inside one iteration (history
    does not change until `--record`) and RESAMPLES for the next iteration (it
    does). That stability matters: a list that reshuffled on every invocation would
    make the printed plan unreproducible within a sitting.
    """
    if not rows:
        return list(rows), 0
    hot, cold = [], []
    for r in rows:
        is_cool, _ = cooling(state, lane, r.get("id"), cooldown)
        (cold if is_cool else hot).append(r)
    if not hot:
        # Everything is cooling. Deprioritising all of it would be meaningless, and
        # silently emptying the lane would be a lie, so hand back the plain order.
        return list(rows), len(cold)
    n = max(1, int(target or 1))
    head_k = max(1, n // max(1, head_fraction))
    head, pool = hot[:head_k], hot[head_k:]
    want = max(0, n - len(head))
    rng = random.Random(f"{lane}|{len(state.get('history') or [])}|{seed_extra}")
    sampled = rng.sample(pool, min(want, len(pool))) if want and pool else []
    picked = {id(r) for r in sampled}
    rest = [r for r in pool if id(r) not in picked]
    return head + sampled + rest + cold, len(cold)


def draw_lane(state, lane_sizes, min_sample=MIN_SAMPLE, stale_after=STALE_AFTER):
    """Pick the recommended lane. Pure function of (state, lane_sizes) — pinned by
    scripts/test_session_plan.py. Returns (lane, reason)."""
    live = [ln for ln in LANES if lane_sizes.get(ln, 0) > 0]
    if not live:
        return None, "all lanes empty"
    arms = {ln: arm_of(state, ln) for ln in live}
    hist = since_epoch(state)

    # Sittings each lane has been worked in -- NOT observations. A ten-draw sitting
    # is ONE sample of "is this lane worth a session", however many iterations it ran.
    lane_sittings = {}
    for h in hist:
        lane_sittings.setdefault(h.get("lane"), set()).add(sitting_of(h))

    # 1. Bootstrap floor: no exploitation while any live lane is under-sampled.
    n_sit = {ln: len(lane_sittings.get(ln, ())) for ln in live}
    under = [ln for ln in live if n_sit[ln] < min_sample]
    if under:
        pick = min(under, key=lambda ln: (n_sit[ln], LANES.index(ln)))
        return pick, (f"bootstrap floor: {pick} worked in {n_sit[pick]} sitting(s) "
                      f"(< {min_sample}); no exploitation on tiny n")

    # 2. Staleness floor: a lane undrawn across the last stale_after SITTINGS is due.
    recent_sittings = set(sittings_in_order(hist)[-stale_after:])
    stale = [ln for ln in live if not (lane_sittings.get(ln, set()) & recent_sittings)]
    if stale:
        pick = stale[0]
        return pick, f"staleness floor: {pick} not drawn in the last {stale_after} sittings"

    # 3. Exploit the Laplace-smoothed win rate.
    def rate(ln):
        a = arms[ln]
        return (a["wins"] + 1) / (a["iterations"] + 2)
    pick = max(live, key=lambda ln: (rate(ln), -LANES.index(ln)))
    return pick, (f"exploit: win rate {rate(pick):.2f} over "
                  f"{arms[pick]['iterations']} iterations in "
                  f"{len(lane_sittings.get(pick, ()))} sitting(s)")


def record(state, lane, outcome, note="", session=None, today=None):
    if lane not in LANES:
        raise SystemExit(f"unknown lane {lane!r}; one of {', '.join(LANES)}")
    if outcome not in ("hit", "miss"):
        raise SystemExit("outcome must be hit or miss")
    today = today or date.today().isoformat()
    cur = arm_of(state, lane)
    state.setdefault("arms", {})[lane] = {
        "wins": cur["wins"] + (1 if outcome == "hit" else 0),
        "iterations": cur["iterations"] + 1,
    }
    state.setdefault("history", []).append(
        {"date": today, "lane": lane, "outcome": outcome,
         **({"session": session} if session is not None else {}),
         **({"note": note} if note else {})})

    # ** CLEAR `pending` ONLY IF THIS RECORD CONSUMED IT. ** (31 JUL 2026.)
    # It used to clear unconditionally, which silently ate a draw registered AFTER
    # the work: a close ran the plan for OPEN / NEXT, then recorded, and the Handoff
    # went on announcing an EXPAND draw that the state file no longer held. Ordering
    # (`session_close.py --next-plan`) fixes the documented path; this fixes the
    # primitive, so a hand-run plan cannot be undone by a later record either.
    pend = state.get("pending")
    if pend and (pend.get("lane") == lane and (pend.get("date") or "") <= today):
        # ** STAMP THE COOLDOWN HERE, and only here. ** The rows in `pending.offered`
        # were presented for THIS lane and this sitting has now recorded an outcome
        # for it, so they have had their turn whether or not each one was disposed of.
        # Stamping at plan time instead would cool rows nobody looked at, and would
        # re-cool them on every re-run of the plan within the sitting. Note this runs
        # AFTER the history append above, so the current sitting is already in
        # sittings_in_order() and `cooling()` reads these rows as since=0.
        stamp_offered(state, lane, pend.get("offered") or [],
                      sitting_of({"session": session, "date": today}))
        state["pending"] = None
    return state


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def heartbeat(state):
    """Cheap: reads state only, builds no lanes (the SessionStart hook budget is
    the whole point — the full plan is the session's FIRST COMMAND, not hook work)."""
    pend = state.get("pending")
    hist = state.get("history", [])
    if pend:
        line = (f"PLAN: lane {pend.get('lane')} drawn {pend.get('date')} and NOT yet "
                f"recorded — it is the NEXT iteration's lane, and that iteration "
                f"records it (session_plan.py --record); run scripts/session_plan.py "
                f"for the full ranked plan")
    elif hist:
        h = hist[-1]
        line = (f"PLAN: last lane {h.get('lane')} ({h.get('outcome')}, {h.get('date')}); "
                f"start with 21-session-start, then run scripts/session_plan.py in "
                f"phase 2 for this session's ranked plan")
    else:
        line = ("PLAN: no lane history yet; start with 21-session-start, then run "
                "scripts/session_plan.py in phase 2 (it draws the lane and prints the "
                "worklist)")
    print(line)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--limit", type=int, help="rows per lane SHOWN (display only; default 5)")
    ap.add_argument("--lane-pct", type=float, dest="lane_pct", metavar="X",
                    help="Work X%% of the vault off the drawn lane per ITERATION "
                         "(the Lane target). Defaults to the profile-review "
                         "sample_percent so one rate drives both loops.")
    ap.add_argument("--sample-percent", "--pct", type=float, dest="sample_percent",
                    metavar="X",
                    help="Sample X%% of the pool in the ROTATE lane THIS SESSION only "
                         "(forwarded to profile_review.py). The standing rate is "
                         "`sample_percent` in .maintenance.json.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--include-adjudicated", action="store_true",
                    help="VERIFY: also offer `?` edges already walked and judged "
                         "(listed in the entry's `adjudicated:` meta key). Audit "
                         "pass only -- they are excluded from a normal draw.")
    ap.add_argument("--record", action="store_true",
                    help="record a lane outcome (with --lane/--outcome[/--note])")
    ap.add_argument("--lane")
    ap.add_argument("--outcome", choices=["hit", "miss"])
    ap.add_argument("--note", default="")
    ap.add_argument("--session", type=int, metavar="N",
                    help="the SITTING this observation belongs to (the session number "
                         "21-session-start established). The bandit floors count "
                         "sittings, not observations; without it, legacy rows fall back "
                         "to the date, which collapses two sittings in one day.")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    cfg = {}
    try:
        with open(os.path.join(vault, ".maintenance.json"), encoding="utf-8") as f:
            cfg = json.load(f).get(CONFIG_KEY, {}) or {}
    except Exception:
        pass
    per_lane = a.limit or int(cfg.get("per_lane", PER_LANE))
    min_sample = int(cfg.get("min_sample", MIN_SAMPLE))
    stale_after = int(cfg.get("stale_after", STALE_AFTER))
    cooldown_sittings = int(cfg.get("offer_cooldown", OFFER_COOLDOWN))

    state = load_state(vault)

    if a.heartbeat:
        heartbeat(state)
        return 0

    if a.record:
        if not (a.lane and a.outcome):
            raise SystemExit("--record needs --lane and --outcome")
        save_state(vault, record(state, a.lane.upper(), a.outcome, a.note, a.session))
        stamp = f" (sitting #{a.session})" if a.session is not None else ""
        print(f"PLAN: recorded lane {a.lane.upper()} -> {a.outcome}{stamp}")
        return 0

    # The full plan.
    lanes = {
        "EXPAND": lane_expand(vault),
        "IMPROVE": lane_improve(vault),
        "VERIFY": lane_verify(vault, include_adjudicated=a.include_adjudicated),
        "ROTATE": lane_rotate(vault, a.sample_percent),
    }
    if a.sample_percent:
        print(f"** ROTATE sample rate overridden for this session: {a.sample_percent:g}% "
              f"(standing rate is `sample_percent` in .maintenance.json). **")
    sizes = {ln: len(rows) for ln, rows in lanes.items()}
    # A lane count that mixes "not done" with "cannot be done" cannot be read, and the
    # bandit is fed these sizes: an IMPROVE draw whose candidates are unworkable by
    # construction is guaranteed to miss its target before it starts, which then teaches
    # the bandit that IMPROVE is a losing arm for a reason unrelated to the lane
    # (deferred_decisions 21). Report the floor rather than hiding it in the total.
    blocked = {ln: sum(1 for r in rows if r.get("blocked")) for ln, rows in lanes.items()}
    pick, reason = draw_lane(state, sizes, min_sample, stale_after)
    lane_target, lt_pct, lt_src = resolve_lane_target(vault, cfg, a.lane_pct)
    try:
        import gen_person_index as _g
        pool_n = sum(1 for _ in _g.parse_narrative())
    except Exception:
        pool_n = 0

    # Candidate rotation: cooldown + seeded stratified sample, in EVERY lane.
    # Runs after the target is resolved (it sizes the priority head) and after
    # `sizes` is taken (it reorders, never filters, so the counts are unchanged).
    cooled = {}
    for _ln in LANES:
        lanes[_ln], cooled[_ln] = rotate_candidates(
            lanes[_ln], state, _ln, lane_target, cooldown=cooldown_sittings)

    if pick:
        # The ids this draw actually OFFERS. record() stamps them only if the
        # recorded lane matches, so overriding the draw cools nothing.
        offered = [r.get("id") for r in lanes[pick][:max(lane_target or per_lane, per_lane)]
                   if r.get("id")]
        state["pending"] = {"date": date.today().isoformat(), "lane": pick,
                            "offered": offered}
        save_state(vault, state)

    if a.json:
        print(json.dumps({"date": date.today().isoformat(), "lane": pick,
                          "reason": reason, "sizes": sizes, "blocked": blocked,
                          "cooling": cooled, "offer_cooldown": cooldown_sittings,
                          "lane_target": lane_target, "lane_target_percent": lt_pct,
                          "lane_target_source": lt_src, "pool": pool_n,
                          "lanes": {ln: rows[:per_lane] for ln, rows in lanes.items()}},
                         indent=1, default=str))
        return 0

    counts = " / ".join(f"{ln} {sizes[ln]}"
                        + (f" ({blocked[ln]} blocked)" if blocked[ln] else "")
                        for ln in LANES)
    print("=== SESSION PLAN — one ranked worklist, one drawn lane ===")
    print(f"  {counts}")
    print(f"  RECOMMENDED LANE: {pick}  ({reason})")
    if lane_target:
        shown, is_dry = target_and_dryness(lane_target, sizes.get(pick, 0) if pick else lane_target)
        # "at least" is the operator's word (01 AUG 2026): the target is a FLOOR,
        # identical in every lane, and cost-per-person is not an input to it.
        print(f"  LANE TARGET: AT LEAST {shown} {'person' if shown == 1 else 'people'} "
              f"this ITERATION — {lt_pct:g}% of {pool_n:,} ({lt_src})")
        print("    Same floor in every lane, counted in PEOPLE. A lane being slow or")
        print("    thin is not a reason to work fewer; if the floor is not met, report")
        print("    what BLOCKED it.")
        if pick and is_dry:
            print(f"    ⚠ THE LANE HOLDS ONLY {sizes.get(pick, 0)} — it will RUN DRY before "
                  f"target, and a lane that runs dry is a HIT. Do not read {shown} as "
                  f"reachable here.")
        if pick and LANE_UNITS.get(pick):
            print(f"    one unit = {LANE_UNITS[pick]}")
    print("  The draw is a recommendation; if you work a different lane, record THAT one.")
    print("  At the END OF THIS ITERATION (not at close, which records nothing by default):")
    print("    python3 scripts/session_plan.py --record --lane <L> --outcome hit|miss")
    print("  hit = the lane target was met, or the lane ran dry; short of target is a MISS.")
    ordered = ([pick] if pick else []) + [ln for ln in LANES if ln != pick]
    for ln in ordered:
        rows = lanes[ln]
        mark = " <-- THIS SESSION" if ln == pick else ""
        floor = (f"  [{blocked[ln]} vitals-blocked: declare, do not research — "
                 f"workable {sizes[ln] - blocked[ln]}]" if blocked[ln] else "")
        cool = (f"  [{cooled[ln]} cooling: offered within the last "
                f"{cooldown_sittings} sittings, moved to the back]" if cooled.get(ln) else "")
        print(f"\n  [{ln}] {sizes[ln]} candidates{mark}{floor}{cool}")
        for r in rows[:per_lane]:
            gen = f"Gen {r['gen']:>2}" if r.get("gen") not in (None, "") else "Gen  ?"
            print(f"    {gen}  {str(r.get('name'))[:42]:44} {r.get('why')}")
        if sizes[ln] > per_lane:
            print(f"    ... and {sizes[ln] - per_lane} more (--limit N, or the owning "
                  f"tool for the full list)")
    print(f"\nPLAN: lane {pick}; {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
