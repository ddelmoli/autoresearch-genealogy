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
    """** DERIVED FROM CADENCE_FRACTION, NOT HARD-CODED. ** These asserted 13 and 26
    literally until 30 JUL 2026, when the operator raised the rate 1% -> 1.5% and
    every one of them failed for the right reason but the wrong cost. The rate is a
    dial; the CLAMP is the invariant, so that is what the test pins."""
    frac = PR.CADENCE_FRACTION
    pool = 1300
    ceil_1300 = max(1, round(pool * frac))
    print(f"\n-- cadence is clamped to ~{frac:.1%} of the pool, and the clamp is reported --")
    got, want, ceiling = PR.resolve_cadence({"per_session": 500}, pool)
    check((got, want, ceiling) == (ceil_1300, 500, ceil_1300),
          f"a configured 500 clamps to {ceil_1300} on a {pool:,} pool")
    got, _w, _c = PR.resolve_cadence({}, pool)
    check(got == ceil_1300, f"the default tracks the pool: {ceil_1300}")
    got, _w, _c = PR.resolve_cadence({"per_session": 13}, 200)
    check(got == max(1, round(200 * frac)), "a small pool clamps the cadence down, not up")


def test_cadence_tracks_pool_growth():
    """1% is a TARGET, not merely a ceiling (corrected 29 JUL 2026): with no
    per_session configured the cadence follows the LIVE pool, so it grows as the
    vault grows. The first version pinned 13 forever — a snapshot of 1% of 1,324
    that would have silently stopped scaling the day the vault passed 1,300."""
    print("\n-- cadence TRACKS pool growth when per_session is absent --")
    big = 2600
    ceil_big = max(1, round(big * PR.CADENCE_FRACTION))
    got, want, ceiling = PR.resolve_cadence({}, big)
    check((got, want, ceiling) == (ceil_big, ceil_big, ceil_big),
          f"a {big:,} pool draws {ceil_big} with no config — the target moved with the vault")
    got, _w, _c = PR.resolve_cadence({"per_session": None}, big)
    check(got == ceil_big, "an explicit null per_session also tracks the pool")
    got, _w, _c = PR.resolve_cadence({"per_session": 5}, big)
    check(got == 5, "an explicit number is honored as a below-rate override")
    check(ceil_big > max(1, round(big * 0.01)),
          "regression guard: the rate is genuinely above the historical 1%")


def test_no_exploitation_on_tiny_sample():
    """The protocol says 'do not tune the allocation on n<=3' — and until
    29 JUL 2026 that rule bound the human while the CODE exploited a 3-for-3
    arm into 46% of the next draw. Now an arm below MIN_EXPLOIT_SAMPLES
    completed polls is filled by exploration (least-sampled first), never by
    its rate."""
    print("\n-- no exploitation on a tiny sample (n < MIN_EXPLOIT_SAMPLES) --")
    arms = {a: {"polled": 0, "hits": 0} for a in ARMS}
    arms["SOURCE_GAP"] = {"polled": 3, "hits": 3}   # perfect record, tiny n
    st = {"arms": arms, "entries": {}, "history": []}
    r = PR.allocate(pool(), st, today=TODAY, cadence=13)
    drawn = {}
    for c in r["draw"]:
        drawn[c["arm"]] = drawn.get(c["arm"], 0) + 1
    check(drawn.get("SOURCE_GAP", 0) == 1,
          f"the 3-for-3 arm gets ONLY its floor slot ({drawn.get('SOURCE_GAP')}), "
          "not the exploitation slots")
    extras = [c["draw_reason"] for c in r["draw"] if c["draw_reason"] != "exploration floor"]
    check(all(reason.startswith("explore (n=") for reason in extras),
          "every non-floor slot says explore, none claims an exploit rate")

    # And the positive control: once every arm has a real sample, exploitation
    # resumes and the printed rate is the SELECTION score (assigned counted).
    st2 = {"arms": {a: {"polled": 20, "hits": 0} for a in ARMS}, "entries": {}, "history": []}
    st2["arms"]["SOURCE_GAP"] = {"polled": 20, "hits": 19}
    r2 = PR.allocate(pool(), st2, today=TODAY, cadence=13)
    hot = [c for c in r2["draw"]
           if c["arm"] == "SOURCE_GAP" and c["draw_reason"].startswith("exploit")]
    check(len(hot) >= 2, "a well-sampled hot arm wins exploitation slots again")
    rates = [c["draw_reason"] for c in hot]
    check(len(set(rates)) == len(rates),
          f"successive exploit slots print DIFFERENT (self-damped) rates {rates} — "
          "the draw no longer misreports its own reasoning")


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


def test_record_by_displayed_pid_enters_cooldown():
    """** THE DRAW PRINTS `pid`; THE COOLDOWN READS `id`. ** (regression, 30 JUL 2026)

    `render()` shows `c["pid"] or "=" + c["id"]`, so for anyone with an FS profile
    the identifier a reader copies out of the draw is the FS PID — while
    `allocate()` looks up `entries_state.get(c["id"])`. Recording by the displayed
    identifier therefore wrote a key nothing read, the entry never entered its
    180-day cooldown, and the same people were re-drawn session after session.

    It hid because the ARMS updated correctly either way, so polled counts and
    hit-rates advanced and every report looked healthy. On the reference vault 11
    of 26 records had landed on FS-PID keys; one 13-person slice put just 2
    entries into cooldown and the next draw re-issued eight already-done people.

    The negative control matters here: asserting only that recording works would
    have passed BEFORE the fix too, because `record()` happily created the
    FS-PID key. What has to be asserted is that the entry the ALLOCATOR sees is
    in cooldown afterwards — i.e. that the write and the read agree on the key.
    """
    print("\n-- recording by the identifier the draw actually prints --")
    pool = [cand(1, "SOURCE_GAP", pid="ABCD-123")]
    vault_id, shown = pool[0]["id"], pool[0]["pid"]
    check(shown != vault_id, "precondition: the draw shows a different key than it reads")

    st = PR.empty_state()
    PR.record(None, st, shown, "hit", arm="SOURCE_GAP", today=TODAY)
    # `record(None, ...)` cannot consult a vault, so it stores what it was given;
    # the allocator is the thing that must agree, so assert through the allocator.
    drawn = PR.allocate(pool, st, cadence=1, today=TODAY)["draw"]
    keyed_by_vault_id = "last_polled" in st["entries"].get(vault_id, {})
    if keyed_by_vault_id:
        check(not drawn or drawn[0]["_due"] is False,
              "an entry recorded by its displayed PID is in cooldown, not re-drawn")
    else:
        check(shown in st["entries"],
              "vault-less record() keeps the raw key (resolution needs the pool)")
        resolved = PR.resolve_person_key(None, shown, candidates=pool)
        check(resolved == vault_id,
              "resolve_person_key maps the displayed FS PID -> the vault id")
        st2 = PR.empty_state()
        PR.record(None, st2, resolved, "hit", arm="SOURCE_GAP", today=TODAY)
        d2 = PR.allocate(pool, st2, cadence=1, today=TODAY)["draw"]
        check(not d2 or d2[0]["_due"] is False,
              "and once resolved, the allocator sees the cooldown")

    # Negative control: the pre-fix behaviour must be visibly WRONG, or this
    # fixture proves nothing.
    st_bad = PR.empty_state()
    st_bad["entries"][shown] = {"last_polled": TODAY.isoformat(), "outcome": "hit"}
    bad = PR.allocate(pool, st_bad, cadence=1, today=TODAY)["draw"]
    check(bool(bad) and bad[0]["_due"] is True and bad[0]["_why"] == "never polled",
          "negative control: an FS-PID-only key still reads as 'never polled'")

    check(PR.resolve_person_key(None, "P-ABC123", candidates=pool) == "P-ABC123",
          "a vault id passes through untouched")
    check(PR.resolve_person_key(None, "abcd-123", candidates=pool) == vault_id,
          "PID matching is case-insensitive")


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
    test_cadence_tracks_pool_growth()
    test_no_exploitation_on_tiny_sample()
    test_record_updates_state()
    test_record_by_displayed_pid_enters_cooldown()
    test_research_privacy_gate()
    test_census_excludes_living()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
