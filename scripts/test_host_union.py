#!/usr/bin/env python3
"""
test_host_union.py — pins deferred_decisions 35 (operator, option 1).

RECORDS take the MAX over crediting blocks; HOSTS take the UNION. They answer
different questions:

  * "how many records" -- MAX, so the same record cited in two blocks does not
    double-count. That is what Spec 05 settled and it is unchanged.
  * "how many repositories" -- UNION, because a host cited only in the OTHER
    block is still a repository that documents this person.

Before the fix, `gather_records` took the winning block's `per_host` WHOLESALE,
so a person genuinely documented by two hosts could read `hosts 1,
SINGLE_SOURCED` with no error anywhere. The split across blocks is the SANCTIONED
inline-collateral convention, not a defect in the data.

THE NEGATIVE CONTROLS ARE THE POINT: the record COUNT must not move, and a
genuinely single-host person must not become multi-host. A change that inflated
breadth everywhere would "fix" the metric by breaking it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harvest_sources as H

PASS = FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def fold(matches):
    """Calls the REAL rule. A copy of it here would keep passing while the
    shipped one broke -- which is the whole reason this file exists."""
    _f, _n, records, _l, per_host, _s = H.fold_matches(matches)
    return records, per_host


def M(records, per_host, name="blk"):
    return (name, name, records, 100, per_host, False)


def main():
    print("=== deferred 35: records MAX, hosts UNION ===")

    # The worked case: own entry has 1 metryki record, the father's entry carries
    # 26 FamilySearch ones as inline collateral. He is documented by TWO hosts.
    own = M(1, {"metryki": 1}, "own")
    father = M(26, {"familysearch": 26}, "father")
    n, hosts = fold([own, father])
    check(n == 26, "record count takes the MAX (26), not the sum")
    check(set(hosts) == {"metryki", "familysearch"}, "hosts take the UNION of both blocks")
    check(len(hosts) == 2, "so `hosts` is 2 and the person is NOT single-sourced")

    # NEGATIVE CONTROL 1 — the count must not move.
    check(n != 27, "NEGATIVE CONTROL: records are not SUMMED across blocks")

    # NEGATIVE CONTROL 2 — a genuinely single-host person stays single-host.
    a = M(5, {"familysearch": 5}, "a")
    b = M(2, {"familysearch": 2}, "b")
    n2, h2 = fold([a, b])
    check(n2 == 5, "single-host: count still MAX")
    check(len(h2) == 1, "NEGATIVE CONTROL: two blocks on ONE host is still hosts=1")

    # NEGATIVE CONTROL 3 — one block behaves exactly as before.
    n3, h3 = fold([M(7, {"fs": 7}, "solo")])
    check(n3 == 7 and h3 == {"fs": 7}, "NEGATIVE CONTROL: a single block is untouched")

    # Per-host counts take the max per host, not the sum -- same anti-double-count
    # reason as the record total.
    n4, h4 = fold([M(3, {"fs": 3, "anc": 1}, "x"), M(2, {"fs": 2}, "y")])
    check(h4["fs"] == 3, "per-host count is the MAX for that host, not 3+2=5")
    check(set(h4) == {"fs", "anc"}, "and the union still picks up the other block's host")

    # An empty block must not erase a real host.
    n5, h5 = fold([M(4, {"fs": 4}, "real"), M(0, {}, "empty")])
    check(set(h5) == {"fs"}, "an empty per_host block does not wipe the union")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
