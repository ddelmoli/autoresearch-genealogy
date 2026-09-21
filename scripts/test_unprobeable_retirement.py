#!/usr/bin/env python3
"""Pins deferred 71 option 4: an EXISTENCE_PROBE row with no live-FS-PID relative
is not offered by the profile-review draw.

Why it exists: an existence probe is answered through a RELATIVE's FamilySearch
profile. A row none of whose relatives carries a live PID cannot be answered, an
unanswered probe writes no dated key, and so the row was re-drawn every sitting
(measured on one vault: 53% of the arm's pool). The fix retires such rows from
ELIGIBILITY only; `pool` still counts them, and a row returns by itself once any
relative gains a PID.

Pinned in both directions, with negative controls: a probeable row is still drawn,
a row whose count was never computed (None) is still drawn, and the retirement
never touches another arm. Runnable with no framework: exit 0 = pass.

Every name here is a placeholder. This repo is public.
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import profile_review as PR

PASS = FAIL = 0
TODAY = date(2026, 9, 21)


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def cand(i, arm, rel):
    return {"id": f"P-{arm[:3]}{i:03d}", "pid": None if arm == PR.EXISTENCE_PROBE else "XXXX-XXX",
            "name": f"Placeholder {i}", "gen": 6, "region": "Testland",
            "category": "SOURCE_GAP", "ark_count": 0, "confidence": "S", "arm": arm,
            "open_question": None, "fs_state": "absent", "has_wt": False, "has_anc": False,
            "live_pid_relatives": rel}


def test_allocate():
    print("\n-- allocate(): unprobeable EXISTENCE_PROBE rows are retired from eligibility --")
    ep = PR.EXISTENCE_PROBE
    pool = ([cand(i, ep, 0) for i in range(5)] + [cand(10 + i, ep, 2) for i in range(3)]
            + [cand(20, ep, None)] + [cand(30 + i, "LOW_COVERAGE", 0) for i in range(4)])
    r = PR.allocate(pool, {"arms": {}, "entries": {}}, today=TODAY, cadence=40)
    a = r["per_arm"][ep]
    drawn = {c["id"] for c in r["draw"]}
    check(a["pool"] == 9, "pool still counts every EXISTENCE_PROBE row (9)")
    check(a["retired_unprobeable"] == 5 and r["retired_unprobeable_total"] == 5,
          "the five 0-relative rows are reported as retired")
    check(a["eligible"] == 4, "eligible = 3 probeable + 1 uncomputed")
    check(not any(f"P-EXI{i:03d}" in drawn for i in range(5)), "no 0-relative row is drawn")
    check(all(f"P-EXI{10 + i:03d}" in drawn for i in range(3)),
          "NEGATIVE CONTROL: a row with a live-PID relative is still drawn")
    check("P-EXI020" in drawn,
          "NEGATIVE CONTROL: a row whose count was never computed (None) is still drawn")
    low = r["per_arm"]["LOW_COVERAGE"]
    check(low["eligible"] == 4 and low.get("retired_unprobeable", 0) == 0,
          "NEGATIVE CONTROL: another arm with live_pid_relatives 0 is untouched")


FIXTURE = """# Family Tree: Testland

### Generation 5

**Parent Placeholder** (b. 1820; d. 1890)
- meta: {id: P-TSTP01, life_status: deceased, generation: 5, fs: AAAA-AAA}

**Lonely Placeholder** (b. 1822; d. 1880)
- meta: {id: P-TSTL01, life_status: deceased, generation: 5, fs: TBD}

### Generation 4

**Child Placeholder** (b. 1850; d. 1920)
- meta: {id: P-TSTC01, life_status: deceased, generation: 4, fs: TBD, parents: '[P-TSTP01?]'}

**Orphan Child Placeholder** (b. 1852; d. 1921)
- meta: {id: P-TSTC02, life_status: deceased, generation: 4, fs: TBD, parents: '[P-TSTL01?]'}

**Spouse Placeholder** (b. 1851; d. 1922)
- meta: {id: P-TSTS01, life_status: deceased, generation: 4, fs: none, spouse: '[P-TSTX01]'}

**Rejected Placeholder** (b. 1849; d. 1919)
- meta: {id: P-TSTX01, life_status: deceased, generation: 4, fs: ~BBBB-BBB, spouse: '[P-TSTS01]'}
"""


def test_build_candidates():
    print("\n-- build_candidates(): the relative count, read from both ends of an edge --")
    tmp = tempfile.mkdtemp(prefix="pr_unprobe_")
    mods = ("harvest_sources", "gen_person_index", "shard_manifest")
    try:
        with open(os.path.join(tmp, ".autoresearch.json"), "w", encoding="utf-8") as f:
            json.dump({"person_model": "narrative"}, f)
        with open(os.path.join(tmp, "Family_Tree_Test.md"), "w", encoding="utf-8") as f:
            f.write(FIXTURE)
        os.environ["AUTORESEARCH_VAULT"] = tmp
        for m in mods:
            sys.modules.pop(m, None)
        c = {x["id"]: x for x in PR.build_candidates(tmp)}
        check(c["P-TSTC01"]["live_pid_relatives"] == 1,
              "a child whose `?` parent has a live PID is probeable (the `?` is stripped)")
        check(c["P-TSTL01"]["live_pid_relatives"] == 0 and c["P-TSTC02"]["live_pid_relatives"] == 0,
              "a parent and child who only have each other, both PID-less, are unprobeable")
        check(c["P-TSTS01"]["live_pid_relatives"] == 0,
              "NEGATIVE CONTROL: a spouse whose partner's PID is a ~REJECTION is not probeable")
        check(c["P-TSTP01"]["arm"] != PR.EXISTENCE_PROBE,
              "the parent with a live PID is not in the EXISTENCE_PROBE arm at all")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        os.environ.pop("AUTORESEARCH_VAULT", None)
        for m in mods:
            sys.modules.pop(m, None)


if __name__ == "__main__":
    test_allocate()
    test_build_candidates()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
