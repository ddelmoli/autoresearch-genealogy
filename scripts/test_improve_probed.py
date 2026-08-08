#!/usr/bin/env python3
"""deferred 58: a dated `fs_probed` removes a row from IMPROVE's SOURCE_GAP pool.

Runnable with no test framework: `python3 scripts/test_improve_probed.py`.

THE DEFECT. `SOURCE_GAP` means "0 records", and nothing distinguished a row NOBODY
HAD LOOKED AT from one deliberately corrected TO zero. Measured on the forced IMPROVE
draw that raised this: of the top FOUR harvestable candidates, TWO were already
finished -- one corrected to 0 records six days earlier (its only attachment being a
DAUGHTER's death certificate, filed as limb (g) and negated) and one whose entry says
in terms "do not re-harvest this PID". **Every honest limb (g) correction was minting
a fresh false candidate**, so the lane got worse the better the vault got.

⚠⚠ THE TEST THAT MATTERS MOST HERE IS THE NEGATIVE ONE. `fs_probed` does a DIFFERENT
job in the ROTATE arms, where it deliberately retires NOTHING (Q157): there, a dated
point-in-time reading must not permanently silence a row, and only a declared `route`
retires. Unifying the two behaviours is the obvious "cleanup" and it would be wrong.
`test_profile_review.test_fs_probed_alone_does_not_retire` pins that side; this file
pins THIS side and asserts the two stay different.
"""
import json
import os
import shutil
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import session_plan as SP
import harvest_sources as HS
import gen_person_index as G
import profile_review as PR

PASS = 0
FAIL = 0

PID = "AAAA" + "-" + "111"
PID2 = "BBBB" + "-" + "222"


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def fixture(probed_line=""):
    """Two 0-record people. One may carry `fs_probed`; the other never does and is
    the positive control -- a suppressor that suppresses everything is
    indistinguishable from one that works."""
    return f"""### Generation 5

**Probed Person** (b. 1850; d. 1920; FS PID {PID})
- meta: {{id: P-AAA111, profile_status: partial, life_status: deceased, generation: 5, fs: {PID}{probed_line}}}
- Nothing of her own is cited.

**Unprobed Person** (b. 1855; d. 1925; FS PID {PID2})
- meta: {{id: P-BBB222, profile_status: partial, life_status: deceased, generation: 5, fs: {PID2}}}
- Nothing of his own is cited either.
"""


def gap_ids(text):
    d = tempfile.mkdtemp(prefix="improve-probed-")
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        json.dump({"person_model": "narrative"}, f)
    with open(os.path.join(d, "Family_Tree_Fixture.md"), "w", encoding="utf-8") as f:
        f.write(text)
    saved = (HS.VAULT, G.VAULT)
    try:
        HS.VAULT, G.VAULT = d, d
        gaps, _corrob, breadth = SP.lane_improve(d)
        return {r["id"] for r in gaps}, breadth.get("gap_probed_suppressed", 0)
    finally:
        HS.VAULT, G.VAULT = saved
        shutil.rmtree(d)


def main():
    print("baseline: BOTH 0-record rows are offered when neither is probed")
    ids, sup = gap_ids(fixture())
    check("P-AAA111" in ids, "unprobed row A is offered")
    check("P-BBB222" in ids, "unprobed row B is offered")
    check(sup == 0, f"nothing suppressed (got {sup})")

    print()
    print("a dated `fs_probed` removes THAT row and only that row")
    ids, sup = gap_ids(fixture(", fs_probed: 2026-08-08"))
    check("P-AAA111" not in ids, "the probed row is no longer offered")
    check("P-BBB222" in ids,
          "POSITIVE CONTROL: the unprobed row is STILL offered (not a blanket filter)")
    check(sup == 1, f"the suppression is REPORTED, not hidden (got {sup})")

    print()
    print("⚠ NEGATIVE CONTROL — `fs_probed` must NOT retire a ROTATE structural arm.")
    print("  Same key, different job. Q157: only a declared `route` retires there,")
    print("  because a dated reading must not silence a row for ever.")
    # ⚠ NOT a paraphrase of the other side -- this CALLS the canonical pin, so the
    # two behaviours cannot drift apart silently. An earlier draft of this block
    # asserted `... or True`, which is a test that cannot fail; that is the exact
    # defect this whole sitting kept finding, so it is called out rather than fixed
    # quietly.
    import test_profile_review as TPR
    fn = getattr(TPR, "test_fs_probed_alone_does_not_retire", None)
    check(callable(fn), "the canonical ROTATE pin exists and is callable")
    if callable(fn):
        before_fail = getattr(TPR, "FAIL", 0)
        try:
            fn()
            ok = getattr(TPR, "FAIL", 0) == before_fail
        except Exception as e:                      # noqa: BLE001
            ok = False
            print(f"       raised: {e}")
        check(ok, "fs_probed STILL retires nothing in the ROTATE arms (Q157 intact)")

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
