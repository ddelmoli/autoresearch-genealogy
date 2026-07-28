#!/usr/bin/env python3
"""Regression fixtures for profile_review.py (and the research privacy gate).

Runnable with no test framework and no vault: `python3 scripts/test_profile_review.py`
(exit 0 = pass). The allocator fixtures are pure in-memory dicts; the census
fixture builds a throwaway 4-person vault in a temp dir.

** THE RULE MOST WORTH PINNING IS THE EXPLORATION FLOOR ** — at least one entry
from EVERY arm, every session, including BOOK_SOURCED. It is the anti-assumption
device: session #109 turned an n=5 null result into a permanent exclusion of 705
entries and had to retract it. The floor is also the part most likely to be
quietly optimised away once real hit-rates arrive, because it will look like waste.

So it is pinned in BOTH directions, with a NEGATIVE CONTROL. A fixture that cannot
be made to fail proves nothing: `test_floor_negative_control` re-runs the SAME
lopsided history with the floor DISABLED and asserts the draw collapses into a
single arm. That is what shows the fixture can actually see the floor working,
rather than passing because the data was never lopsided enough to challenge it.

Every name here is a placeholder. This repo is public.
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import privacy_gate as PG
import profile_review as PR

PASS = 0
FAIL = 0
TODAY = date(2026, 7, 28)


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
ARMS = ("SOURCE_GAP", "UNCITED", "LOW_COVERAGE", "WELL_SOURCED",
        "BOOK_SOURCED", "EXISTENCE_PROBE")


def cand(i, arm, ark_count=0, oq=None, pid="XXXX-XXX"):
    """One candidate. `pid` None models an entry with no FS profile to poll."""
    return {"id": f"P-{arm[:3]}{i:03d}", "pid": None if arm == "EXISTENCE_PROBE" else pid,
            "name": f"Placeholder {arm} {i}", "gen": 6, "region": "Testland",
            "category": arm if arm != "EXISTENCE_PROBE" else "SOURCE_GAP",
            "ark_count": ark_count, "confidence": "S", "arm": arm,
            "open_question": oq, "fs_state": "absent" if arm == "EXISTENCE_PROBE" else "pid",
            "has_wt": False, "has_anc": False}


def pool(per_arm=10):
    return [cand(i, arm, ark_count=i) for arm in ARMS for i in range(per_arm)]


def lopsided_state():
    """One arm measured hot, every other arm measured stone cold. This is the
    history a naive greedy allocator would answer by never touching five of the
    six arms again."""
    arms = {a: {"polled": 20, "hits": 0} for a in ARMS}
    arms["WELL_SOURCED"] = {"polled": 20, "hits": 19}
    return {"arms": arms, "entries": {}, "history": []}


# --------------------------------------------------------------------------- #
def test_exploration_floor():
    print("\n-- exploration floor (the anti-assumption device) --")
    r = PR.allocate(pool(), lopsided_state(), today=TODAY, cadence=13)

    drawn = {}
    for c in r["draw"]:
        drawn[c["arm"]] = drawn.get(c["arm"], 0) + 1

    check(len(r["draw"]) == 13, "the draw is exactly the cadence (13)")
    for arm in ARMS:
        check(drawn.get(arm, 0) >= 1,
              f"{arm} drew at least 1 despite a wildly lopsided hit-rate history")
    check(r["floor_unmet"] == [], "no arm reported as floor-unmet")
    check(drawn["WELL_SOURCED"] > 1,
          "and the hot arm still won the EXPLOITATION slots (the floor is not a cap)")
    check(drawn["WELL_SOURCED"] < 13,
          "but it did not take the whole draw")


def test_floor_negative_control():
    """** THE NEGATIVE CONTROL. ** Same fixture, floor switched OFF. If this
    collapses into one arm, the fixture is genuinely capable of detecting a
    missing floor — so `test_exploration_floor` passing means something. If this
    ALSO spread across arms, both tests would be vacuous."""
    print("\n-- negative control: the same fixture with the floor DISABLED --")
    # 20 per arm, not 10, and the reason is itself a finding: at 10 the hot arm
    # simply RAN OUT after 10 draws and the last 3 slots spilled into other arms,
    # so the control appeared to "spread" for a reason that had nothing to do with
    # the floor. A control that passes for the wrong reason is worse than none.
    r = PR.allocate(pool(20), lopsided_state(), today=TODAY, cadence=13, floor=0)
    arms_hit = {c["arm"] for c in r["draw"]}
    check(len(r["draw"]) == 13, "still draws a full slice")
    check(arms_hit == {"WELL_SOURCED"},
          "with floor=0 the lopsided history collapses the draw into ONE arm "
          f"(got {sorted(arms_hit)}) — so the floor test is not vacuous")


def test_cold_start_is_round_robin():
    print("\n-- cold start (every arm n=0: the first hit-rates are an artefact) --")
    r = PR.allocate(pool(), {"arms": {}, "entries": {}}, today=TODAY, cadence=13)
    counts = {}
    for c in r["draw"]:
        counts[c["arm"]] = counts.get(c["arm"], 0) + 1
    check(min(counts.values()) >= 2 and max(counts.values()) <= 3,
          f"with no history the draw is near-uniform across arms ({sorted(counts.values())})")


def test_cooldowns():
    print("\n-- cooldowns (a negative is a measurement with a date) --")
    p = [cand(0, "SOURCE_GAP"), cand(1, "SOURCE_GAP"), cand(2, "SOURCE_GAP")]
    st = {"arms": {}, "entries": {
        p[0]["id"]: {"last_polled": (TODAY - timedelta(days=10)).isoformat()},
        p[1]["id"]: {"last_polled": (TODAY - timedelta(days=200)).isoformat()},
    }}
    r = PR.allocate(p, st, today=TODAY, cadence=13)
    ids = [c["id"] for c in r["draw"]]
    check(p[0]["id"] not in ids, "an entry polled 10d ago is inside its 180d cooldown")
    check(p[1]["id"] in ids, "an entry polled 200d ago is due again")
    check(p[2]["id"] in ids, "a never-polled entry is due")

    due, _d, why = PR.probe_status({}, "fs", TODAY)
    check(due and "expired on sight" in why,
          "an UNDATED negative (`fs: none` with no probe date) is expired on sight")
    due, _d, _w = PR.probe_status(
        {"last_probed_fs": (TODAY - timedelta(days=100)).isoformat()}, "fs", TODAY)
    check(not due, "a probe 100d old is inside the 365d re-probe cooldown")
    due, _d, _w = PR.probe_status(
        {"last_probed_fs": (TODAY - timedelta(days=400)).isoformat()}, "fs", TODAY)
    check(due, "a probe 400d old has expired")


def test_floor_unmet_is_reported_not_padded():
    print("\n-- an arm entirely inside cooldown is REPORTED, never topped up --")
    p = [cand(0, "SOURCE_GAP"), cand(0, "BOOK_SOURCED")]
    st = {"arms": {}, "entries": {
        p[1]["id"]: {"last_polled": (TODAY - timedelta(days=5)).isoformat()}}}
    r = PR.allocate(p, st, today=TODAY, cadence=13)
    check(r["floor_unmet"] == ["BOOK_SOURCED"], "the starved arm is named")
    check(r["short"] and len(r["draw"]) == 1,
          "the draw is SHORT rather than padded from another arm")


def test_prior_is_a_tilt_within_an_arm():
    print("\n-- the prior tilts WITHIN an arm, it does not choose arms --")
    rich = cand(1, "LOW_COVERAGE", ark_count=3)
    poor = cand(2, "LOW_COVERAGE", ark_count=0)
    linked = cand(3, "LOW_COVERAGE", ark_count=3, oq="Q42")

    # The low-sourced boost ALONE, isolated: same arm, same everything, differing
    # only in record count.
    r1 = PR.allocate([rich, poor], {"arms": {}, "entries": {}}, today=TODAY, cadence=1)
    check([c["id"] for c in r1["draw"]] == [poor["id"]],
          "a 0-record entry outranks a 3-record one in the same arm")

    # Both signals together. The open-question boost (+2) is deliberately WORTH
    # MORE than the extra point a 0-record entry gets over a 3-record one, because
    # the operator named open-question links as the more interesting signal. So a
    # well-sourced entry attached to a live question outranks an unsourced entry
    # attached to nothing — that is the intended order, not an accident.
    r2 = PR.allocate([rich, poor, linked], {"arms": {}, "entries": {}},
                     today=TODAY, cadence=2)
    ids = [c["id"] for c in r2["draw"]]
    check(ids == [linked["id"], poor["id"]],
          "an open-question link ranks first, then the unsourced entry")
    check(rich["id"] not in ids, "the entry with neither signal is not drawn")
    check(PR.prior_score(linked) > PR.prior_score(poor) > PR.prior_score(rich),
          "and the scores say so: 3 > 2 > 1")


def test_arms_are_derived_not_hardcoded():
    print("\n-- arms are DERIVED from the data --")
    p = pool(2) + [dict(cand(0, "SOURCE_GAP"), arm="A_BRAND_NEW_ARM",
                        id="P-NEWARM")]
    r = PR.allocate(p, {"arms": {}, "entries": {}}, today=TODAY, cadence=13)
    check("A_BRAND_NEW_ARM" in r["arms"], "an arm absent from the display order is picked up")
    check(any(c["arm"] == "A_BRAND_NEW_ARM" for c in r["draw"]),
          "and it gets its exploration-floor slot like any other")


def test_determinism():
    print("\n-- determinism (a draw must be reviewable and re-runnable) --")
    a = PR.allocate(pool(), lopsided_state(), today=TODAY, cadence=13)
    b = PR.allocate(pool(), lopsided_state(), today=TODAY, cadence=13)
    check([c["id"] for c in a["draw"]] == [c["id"] for c in b["draw"]],
          "the same pool + state + date draws the same slice")


def test_cadence_clamp():
    print("\n-- cadence is clamped to ~1% of the pool, and the clamp is reported --")
    got, want, ceiling = PR.resolve_cadence({"per_session": 50}, 1300)
    check((got, want, ceiling) == (13, 50, 13), "a configured 50 clamps to 13 on a 1,300 pool")
    got, _w, _c = PR.resolve_cadence({}, 1300)
    check(got == 13, "the default is 13")
    got, _w, _c = PR.resolve_cadence({"per_session": 13}, 200)
    check(got == 2, "a small pool clamps the cadence down, not up")


def test_record_updates_state():
    print("\n-- recording an outcome --")
    st = PR.empty_state()
    PR.record(None, st, "P-AAA111", "hit", arm="SOURCE_GAP",
              note="a source we do not cite", probed=["fs", "wt"], today=TODAY)
    PR.record(None, st, "P-BBB222", "miss", arm="SOURCE_GAP", today=TODAY)
    check(st["arms"]["SOURCE_GAP"] == {"polled": 2, "hits": 1}, "per-arm polled/hits accrue")
    e = st["entries"]["P-AAA111"]
    check(e["last_polled"] == TODAY.isoformat(), "per-entry last_polled is stamped")
    check(e["last_probed_fs"] == TODAY.isoformat()
          and e["last_probed_wt"] == TODAY.isoformat()
          and "last_probed_anc" not in e,
          "only the platforms actually probed get a date")
    check(len(st["history"]) == 2, "history appends")


def test_research_privacy_gate():
    print("\n-- the research gate (deferred_decisions item 11) --")
    check(PG.may_research("deceased")[0], "deceased may be researched")
    check(not PG.may_research("living")[0], "living may NOT")
    check(not PG.may_research("unknown")[0], "unknown may NOT")
    check(not PG.may_research(None)[0], "an ABSENT life_status denies (fails closed)")
    check(not PG.may_research("Deceased?")[0], "an unrecognized value denies (fails closed)")
    check(PG.may_research("  DECEASED ")[0], "case and whitespace are normalized")


# --------------------------------------------------------------------------- #
# Census fixture: a throwaway 4-person vault, to pin the item-11 regression.
# --------------------------------------------------------------------------- #
FIXTURE_TREE = """---
type: lineage
created: 2026-07-28
tags: [test]
---

# Test lineage

### Generation 3: Placeholder line

**Alpha Placeholder** (b. 1900; d. 1970; FS PID AAAA-AAA)
- meta: {id: P-TST001, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 3, fs: AAAA-AAA}
- **Sources**
  - 1910 census, Testland - fs:1:1:YYYY-YYY
  - 1920 census, Testland - fs:1:1:ZZZZ-ZZZ

**Beta Placeholder** (b. 1975)
- meta: {id: P-TST002, profile_status: stub, life_status: living, generation: 2}

**Gamma Placeholder** (b. 1940)
- meta: {id: P-TST003, profile_status: stub, life_status: unknown, generation: 3}

**Delta Placeholder** (b. 1850; d. 1900)
- meta: {id: P-TST004, profile_status: stub, life_status: deceased, generation: 5}
"""


def test_census_excludes_living():
    """The deferred_decisions-11 regression: living/unknown people must not appear
    in ANY coverage category, and must not silently vanish from the census either.
    """
    print("\n-- census: living/unknown are re-categorized, not targets (item 11) --")
    tmp = tempfile.mkdtemp(prefix="pr_fixture_")
    try:
        with open(os.path.join(tmp, ".autoresearch.json"), "w", encoding="utf-8") as f:
            json.dump({"person_model": "narrative"}, f)
        with open(os.path.join(tmp, "Family_Tree_Test.md"), "w", encoding="utf-8") as f:
            f.write(FIXTURE_TREE)
        os.environ["AUTORESEARCH_VAULT"] = tmp
        for mod in ("harvest_sources", "gen_person_index", "shard_manifest"):
            sys.modules.pop(mod, None)
        import harvest_sources as H

        recs = {r["id"]: r for r in H.gather_records()}
        check(len(recs) == 4, "all four entries reach the census (nobody is dropped)")
        check(recs["P-TST002"]["category"] == "LIVING_EXCLUDED",
              "a living person is LIVING_EXCLUDED, not SOURCE_GAP")
        check(recs["P-TST003"]["category"] == "LIVING_EXCLUDED",
              "an unknown-status person is LIVING_EXCLUDED too")
        check(recs["P-TST004"]["category"] == "SOURCE_GAP",
              "a deceased 0-record person is still SOURCE_GAP (the gate is narrow)")
        check(recs["P-TST001"]["category"] == "LOW_COVERAGE"
              and recs["P-TST001"]["ark_count"] == 2,
              "a deceased person's records still count")

        cands = PR.build_candidates(tmp)
        ids = {c["id"] for c in cands}
        check("P-TST002" not in ids and "P-TST003" not in ids,
              "and the rotation never even sees them as candidates")
        check({"P-TST001", "P-TST004"} <= ids, "the deceased two are candidates")
        probe = [c for c in cands if c["arm"] == "EXISTENCE_PROBE"]
        check([c["id"] for c in probe] == ["P-TST004"],
              "the PID-less deceased entry lands in the EXISTENCE_PROBE arm")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        os.environ.pop("AUTORESEARCH_VAULT", None)
        for mod in ("harvest_sources", "gen_person_index", "shard_manifest"):
            sys.modules.pop(mod, None)


def main():
    test_exploration_floor()
    test_floor_negative_control()
    test_cold_start_is_round_robin()
    test_cooldowns()
    test_floor_unmet_is_reported_not_padded()
    test_prior_is_a_tilt_within_an_arm()
    test_arms_are_derived_not_hardcoded()
    test_determinism()
    test_cadence_clamp()
    test_record_updates_state()
    test_research_privacy_gate()
    test_census_excludes_living()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
