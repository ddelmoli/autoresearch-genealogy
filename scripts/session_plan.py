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
  (VERIFY was COLLAPSED into IMPROVE 02 AUG 2026 -- deferred 39 + 40. It drew
           from mostly the same people, its edge population is exhausted, and its
           PID half was IMPROVE's own precondition wearing a lane's clothes.)
  -- was: entries whose `parents:`/`spouse:` lists carry `?`-marked (not yet
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
import re
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402
import person_store  # noqa: E402

SNAPSHOT_FILE = "session_plan_snapshots.json"
CONFIG_KEY = "session_plan"
LANES = ("EXPAND", "IMPROVE", "ROTATE")

# ** VERIFY WAS COLLAPSED INTO IMPROVE, 02 AUG 2026 (operator; deferred 39 + 40). **
#
# 40 measured that the two lanes already drew from mostly the same people: 694 in
# both, 72% of IMPROVE and 71% of VERIFY-PID. And the two jobs are ONE ACTION --
# `25-person-research-sweep` cannot harvest a person's FamilySearch sources without
# loading the profile, which IS the liveness check. The method file justified
# stale-PID work as protection for IMPROVE's own harvest, i.e. it described a
# PRECONDITION and then gave it equal billing as a lane.
#
# ** THE COLLAPSE IS ASYMMETRIC, AND THAT IS THE WHOLE DESIGN. ** IMPROVE stood at
# 0 wins / 9 and VERIFY at 11 / 13, latterly on PID checks alone. Merging naively
# would hand the expensive lane a cheap way to meet a floor it had NEVER met, so
# every honest miss would become a hit and the vault would stop being able to see
# that six-source sweeps are slow. Therefore:
#   - PID liveness is NOT a population and NOT a unit. It is step 0 of prompt 25,
#     annotated on whatever rows are drawn (`pid_stale`), and it scores NOTHING.
#   - `?` edges are NOT a population either (deferred 39: keying the lane on a
#     self-assigned mark meant VERIFY saw 76 of 2,393 edge tokens, 3.2%, and could
#     not see ANY of the 8 children carrying an unexplained PARENT-GEN MISMATCH).
#     They are one input to a DEFECT population that also carries the gate findings.
#   - The unit stays IMPROVE's: a person whose RECORD moved.
IMPROVE_DEFECT_SHARE = 0.25   # reserved for defect rows before sourcing rows get any

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
    "IMPROVE": "one entry DISPOSED OF: an unsourced entry's records found, read and\n"
               "              cited in a `- **Sources**` bullet, OR a SINGLE_SOURCED entry\n"
               "              corroborated from a SECOND host, OR either closed with a\n"
               "              documented negative naming the real route (prompt 25 sweeps\n"
               "              every resource; 19 is the FamilySearch leg only), OR the\n"
               "              person's problem characterised and filed as a numbered\n"
               "              Open_Questions entry naming a resolver (operator, 02 AUG\n"
               "              2026). ! A question does NOT shrink SOURCE_GAP, so count it\n"
               "              ONCE, name the Q number in --note, and never use it in place\n"
               "              of a closure you could actually have made,\n"
               "              OR a DEFECT row settled: a `?` edge adjudicated (cleared,\n"
               "              contradicted, or classified with its reason on the entry) or\n"
               "              a gate finding resolved / declared.\n"
               "              ! CONFIRMING AN FS PID IS LIVE SCORES NOTHING. It is step 0\n"
               "              of prompt 25 -- you load the profile to harvest it anyway --\n"
               "              and counting it would let the cheapest action in the system\n"
               "              satisfy a floor that sourcing has never met (deferred 40).",
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

# ** HISTORICAL (VERIFY collapsed into IMPROVE 02 AUG 2026); the SHARE mechanism it
# introduced is still in use, now protecting IMPROVE's defect + gap populations. **
# ** VERIFY CARRIED TWO POPULATIONS, AND THE SMALLER ONE WAS PROTECTED BY A SHARE **
# (operator-directed, 01 AUG 2026). VERIFY was `?`-marked edges only; it now also
# offers entries whose FS PID has not been confirmed live (see verify_stale_pids).
# Measured when that was added: ~1,131 PID rows against ~34 edge rows. Merged into
# one sampled pool the edge rows would be 3% of the lane -- half a row per draw --
# so the work the lane exists for would vanish behind mechanical checks. This
# reserves a fixed fraction of the lane target for edges before PIDs get any.
VERIFY_EDGE_SHARE = 0.5      # retained: referenced by tests pinning the share maths
# Same protection for IMPROVE, which now also carries two populations of very
# different size: SOURCE_GAP (0 records) against SINGLE_SOURCED (documented, but by
# one host only -- 734 people when this was added). Without a reserved share the
# corroboration backlog would bury the entries that have NO source at all.
IMPROVE_GAP_SHARE = 0.5


# ---------------------------------------------------------------------------
# Lane candidate-builders. Each delegates to the owning tool's own logic.
# ---------------------------------------------------------------------------
def lane_expand(vault):
    """EXPAND's candidates: leaf rows whose parentage is open.

    ** TWO TIERS, because the operator's definition of the lane has two (07 AUG
    2026: "review all leaf nodes ... especially those for which we only have 0 OR 1
    parents"). ** Until 07 AUG the builder drew only the 0-parent frontier, so a row
    naming ONE parent was drawable by nothing at all -- not by EXPAND, whose whole
    job is missing parents, and not by ROTATE or IMPROVE either. That is
    `deferred_decisions` 50, and it surfaced when Charlemagne's queen turned out to
    have been named in PROSE on two entries for seven weeks while her son's edge
    carried his father alone.

      tier 1  SILENT      -- no parents edge, no declared reason
      tier 2  HALF_WIRED  -- exactly one parent, no `no-second-parent` declaration

    ⚠ SILENT RANKS FIRST, and not because it is more important: a 0-parent row is
    unambiguously open, while a 1-parent row may be perfectly correct (an unnamed
    mistress, an unrecorded mother). Offering the unambiguous work first keeps the
    lane's early rows cheap to judge.

    ⛔ THE FRONTIER METRIC IS NOT TOUCHED. SILENT / DECLARED still mean exactly what
    they meant, so nothing in the banner moves. Option 1 of item 50 would have folded
    these into SILENT and shifted the gate by up to 75 in one commit; option 2 shipped
    the counter instead, and this makes the counted rows DRAWABLE without ever making
    a declaration on their behalf.

    ⚠ A HALF_WIRED row's `why` carries a DEPTH HINT, never a verdict -- deep rows
    usually need the named mother WIRED, shallow ones are genuinely mixed. Both
    dispositions are already EXPAND units: the vault grows by a person, or the row is
    closed with a documented reason.
    """
    import extension_frontier as ef
    import build_edges as be
    rows = [r for r in ef.rows_with_bodies(vault) if not r["declared"]]
    rows.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0,
                             ef.TIER_ORDER.get(r["tier"], 3)))
    out = [{"id": r["id"], "name": r["name"], "gen": r["gen"], "file": r["file"],
            "tier": "silent",
            "why": "no parents edge, no declared reason"
                   + (" (spouse-linked leaf)" if r["spouse"] else "")}
           for r in rows]

    seen = {r["id"] for r in out}
    hw = [h for h in be.half_wired_rows(vault)
          if not h["declared"] and h["id"] not in seen]
    hw.sort(key=lambda h: (h["gen"] is None, h["gen"] or 0, str(h["id"])))
    for h in hw:
        hint = ("second parent is usually NAMED in an authority this entry already "
                "cites -- wire it, do not declare"
                if h["deep"] else
                "mixed set: read the entry -- wire the second parent, or declare "
                "`no-second-parent` from a RECORD or named authority")
        out.append({"id": h["id"], "name": h["name"], "gen": h["gen"],
                    "file": h["file"], "tier": "half_wired",
                    "why": f"HALF-WIRED: one parent only, no declared reason -- {hint}"})
    return out


def harvestable_pid(pid):
    """A PID a Recipe-S harvest can actually be run against.

    Delegates to `person_store.live_external_id` so TBD/none AND a `~`-prefixed
    REJECTED profile (deferred 41) are screened in ONE place rather than by a
    literal tuple that has to be kept in step here.
    """
    return person_store.live_external_id(pid) is not None


# ** WHERE TO GO WHEN FAMILYSEARCH IS NOT THE ANSWER (01 AUG 2026, operator-directed).
# ** A worklist that only ever says "harvest the FS PID" trains every session to treat
# FamilySearch as the evidence base rather than the sync point, which is how this vault
# reached 660 of 691 source-citing entries on a single host. These are HINTS, not a
# closed list: the per-person sweep in `25-person-research-sweep` is the authority, and
# a region absent here just falls back to the generic line.
ROUTE_HINTS = (
    ("Italian", "Antenati (per-comune, coverage varies), the provincial state archive, "
                "the diocesan archive for pre-1866 parish registers"),
    ("Polish", "Geneteka, metryki.genealodzy.pl, szukajwarchiwach, AGAD"),
    ("Jewish", "JewishGen Unified Search, JRI-Poland, Gesher Galicia, JOWBR, Yad Vashem"),
    ("Colonial", "published town Vital Records, probate and land records, NEHGR"),
    ("Scottish", "ScotlandsPeople, FS Scotland Births & Baptisms (parent search), NRS"),
    ("British", "FreeREG, FreeBMD, GRO Online index, TNA Discovery, PRONI, the county "
                "record office"),
)
GENERIC_ROUTE = ("Ancestry, WikiTree + what it CITES, newspapers/obituaries, "
                 "HeritageQuest/Fold3, the regional archive")


def route_hint(region, vault=None):
    """A non-FamilySearch route for this person's region. Never returns FS.

    The VAULT's own hints are consulted first (vault_config.get_route_hints): they key
    on that vault's region labels, which are private family/place names and therefore
    belong in its .autoresearch.json, never in this file. The tuple above holds only
    generic ethnicity/region defaults."""
    r = region or ""
    hints = []
    if vault:
        try:
            hints = vault_config.get_route_hints(vault)
        except Exception:
            hints = []
    for needle, hint in list(hints) + list(ROUTE_HINTS):
        if needle.lower() in r.lower():
            return hint
    return GENERIC_ROUTE


def lane_improve(vault):
    """The source-improvement worklist: SOURCE_GAP + SINGLE_SOURCED entries.

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
    ** UN-GATED FROM FamilySearch 01 AUG 2026 (operator-directed, session #127). **
    This lane used to require `harvestable_pid()` — an FS PID — so a person with no
    FamilySearch profile could not enter the improvement lane AT ALL, however
    researchable they were at Antenati, Geneteka, GRO, PRONI or a diocesan archive.
    That is how a vault whose stated goal is "as complete a biographical entry as
    possible, from as many resources as possible" ended up with 660 of its 691
    source-citing entries citing FamilySearch and only 26 people citing two hosts.
    FamilySearch is the place this vault SYNCS with, not its evidence base.

    So the lane now carries TWO populations, composed with a share (see
    IMPROVE_GAP_SHARE):
      - SOURCE_GAP  — 0 records, with or without an FS PID. The `why` names the
                      route, which for a PID-less entry is a regional archive.
      - SINGLE_SOURCED — has records but from exactly ONE host. Not a coverage gap;
                      a CORROBORATION gap, and invisible to the category ladder
                      because a person with 30 FS ARKs and nothing else is
                      WELL_SOURCED. Measured at 734 people when this was added.

    ** RETURNS THE VAULT-WIDE BREADTH CENSUS AS A THIRD VALUE (deferred 34, option 2,
    operator-directed 02 AUG 2026). ** The lane printed its own CANDIDATE counts and
    nothing else, so the number the 01 AUG biography ruling is actually about —
    MULTI_SOURCED, the one that has to go UP — appeared nowhere at the moment a
    session chose what to do. It sat only in `harvest_sources --heartbeat`, which the
    lane does not call. Session #128 duly optimised the visible number: SOURCE_GAP
    238 -> 222 while SINGLE_SOURCED went 734 -> 750 and MULTI_SOURCED did not move at
    all, because sixteen people went from NO source to ONE host and that scores the
    same as a corroboration. Printing it is not scoring it — the floor is untouched.
    """
    import harvest_sources as hs
    import keystone_report as kr
    recs = hs.gather_records()
    gaps = [r for r in recs if r.get("category") == "SOURCE_GAP"]
    singles = [r for r in recs if hs.is_single_sourced(r)]
    # Same test `harvest_sources.heartbeat` uses, so the two can never disagree.
    breadth = {"single": len(singles),
               "multi": sum(1 for r in recs
                            if not hs.is_single_sourced(r) and (r.get("hosts") or 0) >= 2)}
    # ** deferred 58 (operator chose option 1, 08 AUG 2026): a SOURCE_GAP row whose
    # attached-source set has already been READ and found empty leaves the harvest
    # pool. **
    #
    # `SOURCE_GAP` means "0 records", and NOTHING distinguished a row nobody had
    # looked at from one deliberately corrected TO zero. Measured on the forced
    # IMPROVE draw that raised this: of the top FOUR harvestable candidates, TWO were
    # already finished -- one corrected to 0 records six days earlier (its single
    # attachment is a DAUGHTER's death certificate, filed as limb (g) and negated),
    # and one whose entry says in terms "do not re-harvest this PID". **Every honest
    # limb (g) correction was minting a fresh false candidate.**
    #
    # The key is `fs_probed`, reused rather than reinvented: it already means "the
    # attached-source set was read and holds NO records", which is exactly this state.
    #
    # ⚠⚠ THIS IS A DIFFERENT JOB FROM `fs_probed` IN THE ROTATE ARMS, AND THE TWO MUST
    # NOT BE UNIFIED. There (Q157) `fs_probed` deliberately retires NOTHING, because a
    # dated point-in-time reading must not permanently silence a row; only a declared
    # `route` retires, and `test_profile_review.test_fs_probed_alone_does_not_retire`
    # pins that. Here the question is not "is this row settled forever" but "should it
    # rank as a prime FS-harvest target today", and a dated empty read answers it.
    # Pinned in both directions by `scripts/test_improve_probed.py`.
    probed = {}
    for _p in person_store.iter_people(vault):
        if _p.id:
            _d = person_store.fs_probed(_p)
            if _d:
                probed[_p.id] = _d
    suppressed = [r for r in gaps if r["id"] in probed]
    gaps = [r for r in gaps if r["id"] not in probed]

    load = kr.load_by_id()          # no census: LOAD is pure graph reachability
    for r in gaps + singles:
        r["_load"] = load.get(r["id"], 0)
    key = lambda r: (r["gen"] is None, r["gen"] or 0, -r["_load"], r["name"] or "")
    gaps.sort(key=key)
    singles.sort(key=key)

    def row(r, kind):
        load_s = f"; {r['_load']} people lean on it" if r.get("_load") else ""
        if kind == "gap":
            route = (f"FS {r['pid']} harvestable" if harvestable_pid(r.get("pid"))
                     else f"NO FS PID — route: {route_hint(r.get('region'), vault)}")
            why = f"SOURCE_GAP: 0 records, {route}{load_s}"
        else:
            host = next(iter(r.get("per_host") or {}), "one host")
            why = (f"SINGLE_SOURCED: {r.get('ark_count')} record(s), all from "
                   f"`{host}` — corroborate at {route_hint(r.get('region'), vault)}{load_s}")
        return {"id": r["id"], "name": r["name"], "gen": r["gen"],
                "file": r.get("narr_file") or "?",
                "_cool_key": r["id"] if kind == "gap" else f"corrob:{r['id']}",
                "_kind": kind, "why": why}

    # The suppressed count rides on `breadth` so the printout can report it. Reporting
    # it is not decoration: `profile_review` learned the same lesson with its `rtrd`
    # column -- a pool that silently shrinks looks like a lane running dry, and nobody
    # can tell how many rows were SETTLED from how many were never there.
    breadth["gap_probed_suppressed"] = len(suppressed)
    return ([row(r, "gap") for r in gaps],
            [row(r, "corrob") for r in singles],
            breadth)


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
    # ⚠ NOT a local regex any more (deferred 50): `adjudicated_why` may now be a
    # single-quoted LIST, and the old `[a-z\-]+` pattern does not match a leading
    # quote -- it would have read a two-reason row as having NO reason and silently
    # switched off its fs-gap re-check. One reader, in person_store.
    why_of_line = person_store.adjudicated_why_values
    id_re = re.compile(r"P-[0-9A-Za-z]{5,7}")
    living_re = re.compile(r"life_status:\s*(living|unknown)")

    # ** WHICH ADJUDICATIONS COME BACK, AND WHY MOST DO NOT (deferred 38, measured). **
    # The item asked for a blanket expiry clock on `adjudicated`. Measured over 47 rows,
    # a clock helps SEVEN of them, and would re-offer 41 whose re-check a clock cannot
    # trigger:
    #   fs-gap 24 | contradicted 7 | hedge 6 | unstated 12
    # A HEDGE expires when the named resolver is READ, and a CONTRADICTION when the
    # sources are adjudicated -- both EVENTS, already tracked as Open_Questions. And of
    # the fs-gap rows, only 7 have a real PID at the far end; the other 28 end at
    # `fs: none`/`TBD`, where re-checking means a full existence probe with identifier
    # rejection (an FS tree search never returns zero). Re-offering those annually would
    # re-run the expensive work the adjudication exists to record -- the "same edge
    # walked in three sittings" failure deferred 32 was written to stop.
    # So ONLY `fs-gap` WITH A REAL FAR-END PID is re-offered: a contributor linking two
    # profiles that both exist is exactly the change a cheap re-read catches. They are
    # ranked LAST so they never crowd genuinely open work, and the existing offer
    # cooldown spaces them -- no new clock, no new date key.
    fs_of = {}
    for p in g.parse_narrative():
        if p.get("id"):
            fs_of[p["id"]] = str(g.parse_meta(p.get("block") or "").get("fs") or "")
    # deferred 41: a REJECTED profile (`fs: ~PID`) is NOT re-checkable. It is a
    # real PID, so a naive "not in (TBD, none)" test called it live and would
    # have re-offered an fs-gap row whose far end the vault has already declined.
    recheckable = lambda tid: person_store.live_external_id(fs_of.get(tid, "")) is not None

    rows, revisits = [], []
    for p in g.parse_narrative():
        meta = p.get("block") or ""
        if living_re.search(meta):
            continue  # privacy: a `?` here is unclearable by web research
        adj = set()
        _mline = next((l for l in meta.split("\n") if l.lstrip().startswith("- meta:")), "")
        whys = why_of_line(_mline)          # a LIST now — see person_store (deferred 50)
        if not include_adjudicated:
            m = adj_re.search(meta)
            if m:
                adj = set(id_re.findall(m.group(1)))
                if "fs-gap" in whys:
                    # Re-offer the cheaply re-checkable ones as their OWN row. The ids
                    # stay in `adj` deliberately: they are SETTLED, and letting them fall
                    # through as ordinary `?` rows would present adjudicated work as work
                    # nobody has looked at -- the exact misreporting `adjudicated` removed.
                    back = sorted(t for t in adj if recheckable(t))
                    if back:
                        revisits.append({
                            "id": p.get("id"), "name": p.get("name") or "?",
                            "gen": p.get("gen"), "file": p.get("file") or "?",
                            "_defect": "revisit",
                            "why": f"RE-CHECK an FS-GAP adjudication ({len(back)} edge(s)) — "
                                   f"both ends carry a live FS PID, so a contributor may have "
                                   f"linked them since. Cheap: reload the family panel. If still "
                                   f"unlinked, leave the `?` and the adjudication as they are."})
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
    # Re-checks go LAST: a settled edge worth a second look must never outrank an edge
    # nobody has looked at. A row already in `rows` (it has other open `?` edges) is not
    # duplicated.
    have = {r["id"] for r in rows}
    revisits.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0))
    return rows + [r for r in revisits if r["id"] not in have]


def verify_stale_pids(vault):
    """Entries whose FS PID has not been CONFIRMED LIVE inside the probe cooldown.

    ** WAS THE SECOND HALF OF VERIFY (01 AUG 2026); SINCE 02 AUG IT IS AN ANNOTATION,
    NOT A POPULATION (deferred 40) -- read through `pid_stale_ids()`, and note that
    confirming a PID SCORES NOTHING. The rationale below is why it still runs. **
    An `fs:` PID is an external pointer, and FamilySearch rots them: a profile merged
    away or deleted leaves a PID that still LOOKS like a person and reads, on a walk,
    as someone with no relatives. A stale PID does not just mislead VERIFY — IMPROVE
    harvests AGAINST these PIDs, so one silently poisons that lane too.

    ** THE STATE IS profile_review's, NOT A NEW STORE. ** It already keeps a per-entry
    `last_probed_fs` on the vault id, with a ~365d cooldown, and already treats an
    UNDATED negative as expired on sight. Reading it here (rather than inventing a
    second timestamp) is the "two readers, one entry" rule: profile_review owns that
    state and `--record --probed fs` is how a session writes it.

    Ranked never-probed first, then oldest probe, then generation.
    """
    import person_store as PS
    import profile_review as pr
    today = date.today()
    entries = (pr.load_state(vault) or {}).get("entries", {})
    rows = []
    for r in PS.iter_people(vault):
        if (r.life_status or "") in ("living", "unknown"):
            continue  # never web-searched at all
        pid = str((r.external_ids or {}).get("fs") or "")
        if not harvestable_pid(pid):
            continue
        due, days, why = pr.probe_status(entries.get(r.id, {}), "fs", today)
        if not due:
            continue
        rows.append({"id": r.id, "name": r.name, "gen": r.generation,
                     "file": r.source_file,
                     # namespaced so a PID offer and an edge offer on the SAME person
                     # do not cool each other -- they are different work
                     "_cool_key": f"pid:{r.id}",
                     "_days": -1 if days is None else days,
                     "why": f"FS PID liveness unconfirmed — {why}"})
    rows.sort(key=lambda r: (r["_days"] >= 0, -r["_days"],
                             r["gen"] is None, r["gen"] or 0))
    for r in rows:
        r.pop("_days", None)
    return rows


def lane_defects(vault, include_adjudicated=False):
    """People carrying a KNOWN, SPECIFIC defect in their record. (deferred 39)

    ** WHY THIS EXISTS. ** VERIFY keyed its edge half on the `?` mark, which is a
    mark the vault puts on ITSELF. Measured 02 AUG 2026: 76 of 2,393 edge tokens
    carry it -- 3.2% -- so 96.8% of edges were never re-examined by anything, and
    an edge cleared once was never looked at again. Worse, `build_edges --validate`
    was reporting 14 unexplained PARENT-GEN MISMATCHes across 8 children -- real
    structural inconsistencies on NAMED edges -- and **not one of those 8 was
    visible to the lane**, because none of their edges happened to carry a `?`.
    The lane whose job was verification could not see a single one of the vault's
    own flagged defects.

    ** SO THE POOL IS DEFINED BY EVIDENCE OF A PROBLEM, NOT BY A SELF-ASSIGNED MARK. **
    Two sources, ranked in that order:
      1. GATE findings -- a parent/child generation that does not add up. Machine
         found, specific, and previously drawn by nothing.
      2. `?` edges not yet `adjudicated` -- the old VERIFY edge population, kept
         because it is real work, but now ONE input rather than the definition.

    Declared pedigree collapse is excluded: `build_edges` already separates
    GEN_COLLAPSE (expected) from PARENT-GEN MISMATCH (unexplained), and re-offering
    a declared row would be the "never bulk-declare to reach 0" failure in reverse.
    """
    rows, seen = [], set()
    tracked = open_question_ids(vault)
    # 1. Gate findings first -- these are the ones nothing has ever drawn.
    try:
        import build_edges as be
        import gen_person_index as g
        info = {r["id"]: r for r in g.parse_narrative() if r.get("id")}
        for cid, _pid, cg, pg in be.gen_mismatches(vault):
            if cid in seen:
                continue
            seen.add(cid)
            r = info.get(cid, {})
            base = (f"GATE: parent gen {pg}, expected {cg + 1} — an UNEXPLAINED "
                    f"generation mismatch on a named edge (not declared collapse).")
            if cid in tracked:
                # deferred 44: already characterised as an Open_Question, so the only
                # honest disposition has been taken and re-noticing it counts for
                # nothing (prompt 22: a question counts ONCE). Demoted, never removed.
                rows.append({"id": cid, "name": r.get("name") or "?", "gen": cg,
                             "file": r.get("file") or "",
                             "_defect": "gate-tracked",
                             "why": base + " ⚠ ALREADY TRACKED in Open_Questions — "
                                    "re-noticing it disposes of nothing; it needs the "
                                    "resolver named there, not another sighting."})
            else:
                rows.append({"id": cid, "name": r.get("name") or "?", "gen": cg,
                             "file": r.get("file") or "",
                             "_defect": "gate",
                             "why": base + " Resolve it, or declare it in "
                                    "`known_gen_collapse` with a note."})
    except Exception as e:                         # never silently drop the population
        print(f"session_plan: WARNING - gate findings unavailable for the IMPROVE "
              f"defect pool ({type(e).__name__}: {e}). `?` edges still offered.",
              file=sys.stderr)
    # 2. Then the `?` edges, as ONE input rather than the whole lane.
    # ! PRESERVE an incoming `_defect`. lane_verify ranks its FS-GAP RE-CHECK rows LAST
    # on purpose ("a settled edge worth a second look must never outrank an edge nobody
    # has looked at") by tagging them `revisit` and appending them. Overwriting that tag
    # with "edge" here silently undid it: measured 03 AUG 2026, all 4 re-check rows came
    # back at rank 1 and, being Gen 6, sorted AHEAD of every genuinely open edge.
    for r in lane_verify(vault, include_adjudicated=include_adjudicated):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        rows.append({**r, "_defect": r.get("_defect") or "edge"})
    # 3. Then BANKED parent pairs -- located, declined, and drawn by NOTHING until now.
    for r in lane_banked(vault):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        rows.append(r)
    # 4. Then UNMARKED edges -- the 96.8% nothing has ever re-examined (39-residual).
    for r in lane_edge_audit(vault):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        rows.append(r)
    rows.sort(key=lambda r: (_DEFECT_RANK.get(r.get("_defect"), 9),
                             r["gen"] is None, r["gen"] or 0))
    return rows


# gate = machine-found evidence of a problem; edge = the vault's own `?` mark;
# banked = a parent pair LOCATED on another tree and deliberately not adopted;
# audit = NO signal at all, sampled because nothing else ever looks (39-residual).
# Lower ranks are offered first. The two DEMOTED kinds are work that has already been
# looked at: `gate-tracked` is a gate finding already characterised as an Open_Question
# (deferred 44), and `revisit` is a settled fs-gap adjudication worth a cheap second
# look (deferred 38). Both must sit behind anything nobody has examined -- otherwise the
# lane presents answered work as fresh work, which is what makes a worklist stop being
# trusted. Neither is REMOVED: the lane size stays honest.
#
# ** `banked` sits ABOVE `audit` and BELOW `edge` (operator-directed, 04 AUG 2026). **
# Above audit because it is the most SPECIFIC work in the pool -- the parents are named,
# dated and PID'd, so the task is "find one record", not "go and look". Below edge
# because a `?` edge is an edge the vault has ALREADY adopted and left unverified,
# which is a live claim in the tree, whereas a banked pair claims nothing yet.
_DEFECT_RANK = {"gate": 0, "edge": 1, "banked": 2, "audit": 3,
                "gate-tracked": 4, "revisit": 5}


def lane_banked(vault):
    """Frontier rows whose parents were LOCATED on another tree and NOT adopted.

    ** THE HOLE THIS FILLS (operator-directed, 04 AUG 2026). ** An EXPAND draw that
    finds a row's parents named on FamilySearch correctly declines to wire them --
    an FS couple is a tree ASSERTION, not a source. The row is then DECLARED, which
    means `extension_frontier` counts it as closed and **EXPAND never offers it
    again**. The work is real, located and cheap to finish, and nothing drew it.

    Measured at adoption: **11 rows (7 from session #138, 4 from #139)** holding
    ~22 parent PIDs, **none of those parents present in the vault**, growing 7 -> 11
    in two sittings. Same shape as the FS write-back queue: found work with no lane.

    ⚠ **A BANKED ROW IS NOT A DEFECT**, exactly as the `audit` tier is not. Nothing
    about it is wrong -- the declaration was the correct call. It sits in the defect
    POOL because that pool is "edge work the sourcing populations would swamp", and
    because its disposition is the defect unit (`--verified`): find a record naming
    the parents, then wire with a `?`, or record why the pair still cannot be
    adopted.

    ⚠ **AND IT IS SELECTED FROM THE DATA, NEVER FROM THE DECLARATION PROSE** -- see
    `person_store.banked_parents_host` for why (limb (g)'s ruling against
    text-as-failure-surface, and the `route_digest` blockquote double-count that
    made a first prose scan read 27 where the truth was 11).

    A row LEAVES this population by being wired: the `parents` edge is the exit
    test, so a wired row is not offered even if the key is left behind. That
    residue is reported separately as `BANKED_STALE` by `build_edges --validate`.
    """
    import person_store as ps
    rows = []
    for rec in ps.iter_people(vault):
        host = ps.banked_parents_host(rec)
        if not host:
            continue
        if getattr(rec, "parents", None):
            continue                      # wired since it was banked: done, not work
        rows.append({
            "id": rec.id,
            "name": rec.name or "?",
            "gen": rec.generation,
            "file": os.path.basename(str(getattr(rec, "source_file", "") or "")),
            "_defect": "banked",
            "why": (f"BANKED parents on `{host}` — located, PIDs in this entry's frontier "
                    f"declaration, deliberately NOT wired. ⚠ Do NOT wire as-is: an "
                    f"{host.upper()} couple is a tree assertion. ⏭ Find ONE record "
                    f"naming them, then mint + wire with `?`; a documented negative "
                    f"also disposes of the row."),
        })
    rows.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0, r["name"] or ""))
    return rows


def open_question_ids(vault):
    """Vault ids named anywhere in the LIVE `Open_Questions.md`. (deferred 44)

    ** WHY THE BUILDER READS THE REGISTER. ** The IMPROVE defect pool ranked a GATE
    finding first whether or not anyone had already answered it. Measured 03 AUG 2026
    (session #135): both of the vault's remaining PARENT-GEN mismatches were already
    fully characterised in Q126 -- inversion warning and all -- yet the lane offered one
    at rank 1. Prompt 22 is explicit that a question counts ONCE, for the sitting that
    did the work, so the row was unworkable for credit and would have ranked first every
    draw. `adjudicated` solved exactly this for `?` edges (deferred 32); the gate-finding
    half of the population never got the equivalent.

    ** THE REGISTER IS THE SOURCE OF TRUTH, so there is no second store to drift. **
    A `gate_tracked:` meta key was the alternative and was NOT taken (operator, 03 AUG
    2026): it would need its own staleness check, exactly as `ADJUDICATED_STALE` does,
    and a stale marker HIDES a real candidate. Reading the register cannot go stale.

    ⚠ Deliberately COARSE: any `P-` id anywhere in the file counts, including one named
    incidentally by a question about something else. That is an accepted false-positive
    cost because the consequence is a RANKING change, never a removal -- a wrongly
    demoted row is still offered, just later. Resolved questions live in
    `Open_Questions_Resolved.md` and are NOT read here: a resolved question should stop
    suppressing its row.
    """
    import os
    import re
    p = os.path.join(vault, "Open_Questions.md")
    try:
        with open(p, encoding="utf-8") as fh:
            return set(re.findall(r"P-[0-9A-Za-z]{5,7}", fh.read()))
    except OSError:
        return set()          # no register -> nothing is tracked; never a hard failure


def edge_audit_coverage(vault):
    """(total edge tokens, tokens carrying `?`, people with unmarked edges NOT offered).

    Exists so the plan can PRINT the uncovered remainder. deferred 39's whole
    complaint was that finishing the `?` work reads as "verification is done" while
    96.8% of edges have never been examined -- so the number that is NOT covered has
    to be on screen, not inferred.
    """
    import gen_person_index as g
    import harvest_sources as H
    try:
        cov = {r.get("id"): r for r in H.gather_records()}
    except Exception:
        cov = {}
    tot = q = 0
    offered, unmarked_people = set(), set()
    for r in g.parse_narrative():
        rid = r.get("id")
        if not rid:
            continue
        meta = g.parse_meta(r.get("block") or "")
        toks = [t for k in ("parents", "spouse")
                for t in re.findall(r"P-[0-9A-Za-z]+\??", str(meta.get(k) or ""))]
        tot += len(toks)
        q += sum(1 for t in toks if t.endswith("?"))
        if any(not t.endswith("?") for t in toks):
            unmarked_people.add(rid)
            tier = str(meta.get("evidence_tier") or "")
            cat = (cov.get(rid) or {}).get("category", "")
            if tier == "speculative" or cat in ("UNCITED", "SOURCE_GAP"):
                offered.add(rid)
    return tot, q, len(unmarked_people - offered)


def lane_edge_audit(vault):
    """People whose parent/spouse edges carry NO mark, RANKED BY RISK. (39-residual)

    ** THE GAP THIS CLOSES. ** Measured 02 AUG and unchanged 03 AUG: of 2,393 edge
    tokens only 76 (3.2%) carry a `?`; the other 2,317 across 1,171 people are
    re-examined by NOTHING. An edge is marked once, cleared once, and never looked
    at again -- and an edge that was never marked in the first place is invisible
    for ever. Deferred 39 routed the GATE findings in and left this half open.

    ** WHY THIS IS RISK-RANKED AND NOT A UNIFORM SAMPLE, WHICH IS THE WHOLE POINT. **
    Uniform sampling of 1,171 people inside IMPROVE's defect share is theatre: at
    1-3 rows a draw it needs 195-585 sittings for ONE pass. Matching
    profile_review's accepted cadence (~65 sittings per pass) would take ~18 rows a
    draw -- effectively the whole lane.

    So the population is CONCENTRATED on a real prior instead: an unmarked edge
    asserted on an entry that cites NO records at all, or is explicitly
    `speculative`, rests on nothing but the vault's own prior belief. Measured:
    **167 of 1,171 (14%)**, which a small share sweeps in ~17-28 sittings.

    ⚠ THE REMAINING ~1,004 ARE NOT OFFERED, AND THAT IS DECLARED RATHER THAN HIDDEN.
    They are unmarked edges on WELL_SOURCED / BOOK_SOURCED / LOW_COVERAGE entries.
    Sampling them uniformly would be a gesture, and pretending otherwise is what
    "nobody mistakes 3.2%-of-edges for `the vault is verified`" was warning about.
    `plan_summary` prints the number so the uncovered remainder stays visible.

    ⚠ AND THESE ARE NOT DEFECTS. A row here carries no evidence of a problem -- it
    is an AUDIT of an assertion nothing has tested. It ranks BEHIND every gate
    finding and every `?` edge, so known defects are never displaced by sampling.
    """
    try:
        import gen_person_index as g
        import harvest_sources as H
    except Exception as e:
        print(f"session_plan: WARNING - edge-audit population unavailable "
              f"({type(e).__name__}: {e}).", file=sys.stderr)
        return []
    cov = {}
    try:
        cov = {r.get("id"): r for r in H.gather_records()}
    except Exception:
        pass                      # risk ranking degrades to tier-only; never fatal
    out = []
    for r in g.parse_narrative():
        rid = r.get("id")
        if not rid:
            continue
        meta = g.parse_meta(r.get("block") or "")
        unmarked = [t for k in ("parents", "spouse")
                    for t in re.findall(r"P-[0-9A-Za-z]+\??", str(meta.get(k) or ""))
                    if not t.endswith("?")]
        if not unmarked:
            continue
        tier = str(meta.get("evidence_tier") or "")
        cat = (cov.get(rid) or {}).get("category", "")
        if tier != "speculative" and cat not in ("UNCITED", "SOURCE_GAP"):
            continue              # low-risk remainder: declared, not offered
        why = ("speculative tier" if tier == "speculative"
               else f"entry cites NO records ({cat})")
        out.append({
            "id": rid, "name": r.get("name") or "?", "gen": r.get("generation"),
            "file": r.get("file") or "", "_defect": "audit",
            "why": f"AUDIT ({len(unmarked)} unmarked edge(s)) — nothing has ever "
                   f"re-examined this edge, and {why}, so it rests on the vault's "
                   f"own prior belief. NOT a known defect: confirm it from the "
                   f"CHILD's page, and if it cannot be confirmed give it a `?`.",
        })
    return out


def pid_stale_ids(vault):
    """Vault ids whose FS PID has not been confirmed live inside the probe cooldown.

    ** NOT A POPULATION AND NOT A UNIT (deferred 40). ** This is an ANNOTATION on
    whatever rows a draw offers: you are about to open the profile to harvest it, so
    confirm it resolves first -- a merged-away PID reads as a person with no
    relatives and silently poisons the harvest. Scoring it would hand the lane the
    cheapest action in the system as a way to meet its floor.
    """
    return {r["id"] for r in verify_stale_pids(vault)}


def compose_share(primary, secondary, target, share):
    """Interleave two populations of a lane, reserving a share for the PRIMARY one.

    ** WHY A SHARE AND NOT A MERGE (measured 01 AUG 2026). ** On the reference vault
    the stale-PID population is ~1,131 rows against ~34 `?`-edge rows. Merged into one
    pool and sampled, the edge rows are 3% of the lane: a 21-row draw returns half an
    edge row, and the work VERIFY exists for silently disappears behind mechanical
    checks. The share fixes the edge quota FIRST, so adding the new population cannot
    swamp the old one. When the edges run out the quota simply goes unfilled and PIDs
    take the rest; when the PIDs run dry, edges do.

    Returns (composed_rows, primary_quota, secondary_quota).
    """
    n = max(1, int(target or 1))
    p_quota = min(len(primary), max(1, int(n * share)))
    s_quota = max(0, n - p_quota)
    return (primary[:p_quota] + secondary[:s_quota]
            + primary[p_quota:] + secondary[s_quota:]), p_quota, s_quota


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


def cool_key(row):
    """The cooldown key for a row. `_cool_key` namespaces a SUB-POPULATION of a lane.

    VERIFY offers two kinds of work on the same person (a `?` edge, and an unconfirmed
    FS PID). Cooling one must not cool the other — they are different work — so the
    stale-PID rows carry `pid:<id>` while edge rows use the bare vault id.
    """
    return row.get("_cool_key") or row.get("id")


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
        is_cool, _ = cooling(state, lane, cool_key(r), cooldown)
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


def record(state, lane, outcome, note="", session=None, today=None,
           sourced=None, corroborated=None, verified=None):
    """Record one iteration's outcome for `lane`.

    ** `sourced` / `corroborated` SPLIT THE IMPROVE UNIT (deferred 34, option 1,
    operator-directed 02 AUG 2026). ** IMPROVE's two dispositions — an unsourced
    entry cited for the first time, and a SINGLE_SOURCED entry corroborated from a
    SECOND host — scored identically while costing wildly differently, and only the
    second serves the stated biography goal. Recording the split does NOT change
    scoring: both still count one person toward the same floor, and the floor stays
    "the same in every lane, counted in PEOPLE" (operator, 01 AUG 2026; weighting
    was rejected on sight as reintroducing cost-per-person reasoning). What it buys
    is that an all-FS-harvest draw is visible AT REVIEW rather than a month later,
    which is how #128's went unnoticed.

    ** `verified` IS THE THIRD SLOT (deferred 40, 02 AUG 2026). ** When VERIFY was
    collapsed into IMPROVE the lane gained a DEFECT population -- `?` edges and gate
    findings -- whose dispositions are neither "sourced" nor "corroborated". Without
    a slot of its own, a draw that spent itself adjudicating edges would record as
    0/0 and read exactly like a draw that achieved nothing. ⚠ It does NOT cover
    confirming an FS PID is live: that is a precondition and scores nothing at all.

    All three are optional and IMPROVE-only; the numbers are advisory and deliberately
    NOT reconciled against the target, because a draw can dispose of a person by
    documented negative, which is none of them.
    """
    if lane not in LANES:
        raise SystemExit(f"unknown lane {lane!r}; one of {', '.join(LANES)}")
    if outcome not in ("hit", "miss"):
        raise SystemExit("outcome must be hit or miss")
    split = None
    if sourced is not None or corroborated is not None or verified is not None:
        if lane != "IMPROVE":
            raise SystemExit("--sourced/--corroborated/--verified split the IMPROVE "
                             f"unit and apply only to that lane, not {lane}")
        split = {"sourced": sourced or 0, "corroborated": corroborated or 0,
                 "verified": verified or 0}
    today = today or date.today().isoformat()
    cur = arm_of(state, lane)
    state.setdefault("arms", {})[lane] = {
        "wins": cur["wins"] + (1 if outcome == "hit" else 0),
        "iterations": cur["iterations"] + 1,
    }
    state.setdefault("history", []).append(
        {"date": today, "lane": lane, "outcome": outcome,
         **({"session": session} if session is not None else {}),
         **({"split": split} if split else {}),
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


def last_improve_split(state):
    """The most recent IMPROVE record that carried a SOURCED/CORROBORATED split.

    Returns None when no draw has been recorded with one yet — which is the state
    every vault starts in, and is why the caller must not assume a dict. Reads
    backwards so the newest wins; a record without a split is skipped rather than
    treated as zeroes, because "not reported" and "reported as none" are different
    facts and only the first should be silent.
    """
    for h in reversed(state.get("history", []) or []):
        if h.get("lane") == "IMPROVE" and h.get("split"):
            sp = h["split"]
            return {"date": h.get("date", "?"),
                    "sourced": sp.get("sourced", 0),
                    "corroborated": sp.get("corroborated", 0)}
    return None


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
                    help="IMPROVE defect pool: also offer `?` edges already walked and judged "
                         "(listed in the entry's `adjudicated:` meta key). Audit "
                         "pass only -- they are excluded from a normal draw.")
    ap.add_argument("--record", action="store_true",
                    help="record a lane outcome (with --lane/--outcome[/--note])")
    ap.add_argument("--lane")
    ap.add_argument("--outcome", choices=["hit", "miss"])
    ap.add_argument("--note", default="")
    # deferred 34 option 1: IMPROVE's two dispositions, reported apart. Advisory --
    # they do not change scoring, and they need not sum to the target (a person can
    # be disposed of by documented negative, which is neither).
    ap.add_argument("--sourced", type=int, metavar="N",
                    help="IMPROVE only: of this draw's disposals, how many were an "
                         "UNSOURCED entry cited for the first time (0 -> cited).")
    ap.add_argument("--verified", type=int, metavar="N",
                    help="With --record --lane IMPROVE: how many of this draw's "
                         "dispositions were DEFECT rows settled (a `?` edge "
                         "adjudicated, or a gate finding resolved/declared). "
                         "Confirming a PID is live is NOT one of these.")
    ap.add_argument("--corroborated", type=int, metavar="N",
                    help="IMPROVE only: of this draw's disposals, how many were a "
                         "SINGLE_SOURCED entry corroborated from a SECOND host "
                         "(1 host -> 2+). This is the one that moves MULTI_SOURCED.")
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
        save_state(vault, record(state, a.lane.upper(), a.outcome, a.note, a.session,
                                 sourced=a.sourced, corroborated=a.corroborated,
                                 verified=a.verified))
        stamp = f" (sitting #{a.session})" if a.session is not None else ""
        print(f"PLAN: recorded lane {a.lane.upper()} -> {a.outcome}{stamp}")
        if a.sourced is not None or a.corroborated is not None or a.verified is not None:
            print(f"  IMPROVE split: {a.sourced or 0} sourced (0 -> cited) / "
                  f"{a.corroborated or 0} corroborated (1 host -> 2+) / "
                  f"{a.verified or 0} defect rows settled")
            if not (a.corroborated or 0):
                print("  ⚠ ZERO corroborations: this draw lowered SOURCE_GAP without "
                      "moving MULTI_SOURCED.")
            if (a.verified or 0) and not ((a.sourced or 0) or (a.corroborated or 0)):
                print("  ⚠ ALL-DEFECT draw: no record moved. Legitimate, and visible "
                      "here on purpose (deferred 40).")
        return 0

    # The full plan.
    # IMPROVE's THREE populations are kept APART until the target is known, because
    # the shares that protect the smaller ones are fractions of that target.
    i_defects = lane_defects(vault, include_adjudicated=a.include_adjudicated)
    i_gaps, i_corrob, i_breadth = lane_improve(vault)
    stale_pids = pid_stale_ids(vault)      # an ANNOTATION, never a population
    lanes = {
        "EXPAND": lane_expand(vault),
        "IMPROVE": i_defects + i_gaps + i_corrob,
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
        if _ln == "IMPROVE":
            # THREE populations, each rotated on its OWN then composed by share.
            # Sampling a merged pool would let 761 corroboration rows swamp the 8
            # gate defects -- the same swamping the old VERIFY share existed to stop.
            _d, _dc = rotate_candidates(i_defects, state, _ln, lane_target,
                                        cooldown=cooldown_sittings, seed_extra="defect")
            _g, _gc = rotate_candidates(i_gaps, state, _ln, lane_target,
                                        cooldown=cooldown_sittings)
            _c, _cc = rotate_candidates(i_corrob, state, _ln, lane_target,
                                        cooldown=cooldown_sittings, seed_extra="corrob")
            # Defects reserve their share FIRST; sourcing rows split what is left.
            _src, _gq, _cq = compose_share(_g, _c, lane_target, IMPROVE_GAP_SHARE)
            lanes[_ln], i_dq, _srcq = compose_share(_d, _src, lane_target,
                                                    IMPROVE_DEFECT_SHARE)
            # ⚠ REPORT WHAT IS ACTUALLY TAKEN, NOT THE INNER SPLIT. The inner
            # compose sizes gaps/corrob against the FULL target; the outer one then
            # takes only `_srcq` of that ordering. Printing the inner quotas made
            # 5 + 10 + 11 = 26 for a target of 21 -- three numbers that cannot all
            # be true at once, in the one line telling the session how deep to go.
            i_gq = min(_gq, _srcq)
            i_cq = max(0, _srcq - i_gq)
            cooled[_ln] = _dc + _gc + _cc
        else:
            lanes[_ln], cooled[_ln] = rotate_candidates(
                lanes[_ln], state, _ln, lane_target, cooldown=cooldown_sittings)
    # PID staleness is an ANNOTATION on whatever was drawn, not a population and not
    # a unit (deferred 40). Mark the rows so the sweep knows to confirm the profile
    # resolves BEFORE harvesting it -- a merged-away PID reads as a person with no
    # relatives and silently poisons the harvest.
    for _ln in LANES:
        for _r in lanes[_ln]:
            if _r.get("id") in stale_pids:
                _r["why"] = (_r.get("why") or "") + \
                    "  [PID liveness unconfirmed — confirm it resolves as step 0; scores NOTHING]"

    if pick:
        # The ids this draw actually OFFERS. record() stamps them only if the
        # recorded lane matches, so overriding the draw cools nothing.
        offered = [cool_key(r) for r in lanes[pick][:max(lane_target or per_lane, per_lane)]
                   if cool_key(r)]
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
        if pick == "IMPROVE":
            _ngate = sum(1 for r in i_defects if r.get("_defect") == "gate")
            _nedge = sum(1 for r in i_defects if r.get("_defect") == "edge")
            _naud = sum(1 for r in i_defects if r.get("_defect") == "audit")
            _nbank = sum(1 for r in i_defects if r.get("_defect") == "banked")
            print(f"    IMPROVE holds THREE populations: {len(i_defects)} DEFECT "
                  f"({_ngate} gate finding(s) + {_nedge} `?` edges + {_nbank} BANKED "
                  f"parent pairs + {_naud} unmarked-edge AUDIT rows), "
                  f"{len(i_gaps)} with NO source,")
            print(f"    {len(i_corrob)} documented by ONE host only. This draw reserves "
                  f"{i_dq} for defects first, then {i_gq} unsourced + {i_cq} "
                  f"corroboration.")
            # 39-residual: the uncovered remainder is PRINTED, never implied away.
            # "Nobody should mistake 3.2%-of-edges for `the vault is verified`."
            try:
                _tot, _q, _lowrisk = edge_audit_coverage(vault)
                print(f"    ⚠ EDGE COVERAGE: {_q} of {_tot} edge tokens carry a `?`; the "
                      f"AUDIT tier offers the {_naud} highest-risk unmarked rows")
                print(f"      (no cited records, or speculative). {_lowrisk} people with "
                      f"unmarked edges are NOT offered — uniform sampling")
                print("      of them would need ~200-600 sittings for one pass. The vault "
                      "is NOT 'verified'; this is a risk-ranked audit.")
            except Exception:
                pass
            print("    FamilySearch is the SYNC point, not the evidence base — each")
            print("    sourcing row names a non-FS route to try.")
            print(f"    ⚠ {len(stale_pids)} drawn-or-not entries have an UNCONFIRMED FS "
                  f"PID. Confirming one is step 0 of prompt 25 and SCORES NOTHING")
            print("      — it is a precondition, not a disposition (deferred 40).")
            _sup = i_breadth.get("gap_probed_suppressed") or 0
            if _sup:
                print(f"    ⭐ {_sup} SOURCE_GAP row(s) are SUPPRESSED from this pool by a dated")
                print("      `fs_probed`: their sources were READ and hold no records, so a 0 there")
                print("      is a finished answer, not an unopened one (deferred 58). Reported, not")
                print("      hidden — a pool that shrinks silently reads as a lane running dry.")
            # deferred 34, option 2: the GOAL metric, at the moment of choosing.
            # SOURCE_GAP is the lane's worklist; MULTI_SOURCED is what the 01 AUG
            # biography ruling is about, and it is the one that must go UP.
            print(f"    ** GOAL METRIC (vault-wide, not this draw): SINGLE_SOURCED "
                  f"{i_breadth['single']} / MULTI_SOURCED {i_breadth['multi']}. **")
            print("    Clearing SOURCE_GAP with an FS-only harvest moves a person from")
            print("    NO source to ONE host: it lowers SOURCE_GAP and RAISES")
            print("    SINGLE_SOURCED. Only a SECOND host raises MULTI_SOURCED.")
            _sp = last_improve_split(state)
            if _sp:
                print(f"    Last recorded IMPROVE draw ({_sp['date']}): "
                      f"{_sp['sourced']} sourced / {_sp['corroborated']} corroborated.")
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
