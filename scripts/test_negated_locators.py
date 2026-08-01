#!/usr/bin/env python3
"""Regression tests for `~`-negated locators (deferred_decisions 28).

Runnable with no test framework: `python3 test_negated_locators.py` (exit 0 = pass).

The feature exists because recording WHY a source was excluded required naming it,
and naming it made the census COUNT it. A "NOT COUNTED — Find a Grave, policy (e)"
bullet citing `1:1:694C-W9N2` moved a person from SOURCE_GAP to LOW_COVERAGE with 2
records — credited with the two sources the bullet existed to exclude.

EVERY case here carries its positive control. A suppressor that suppresses everything
is indistinguishable from one that works, and this repo has shipped that mistake: the
whole point is that an UNMARKED locator on the same line, in the same entry, must still
count. Several cases below assert exactly that.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as H

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def main():
    print("negated locators — the forms that must be suppressed")
    for form, label in [
        ("~fs:1:1:AAAA-BBB", "host-prefixed"),
        ("~1:1:AAAA-BBB", "bare 1:1"),
        ("~ark:/61903/1:1:AAAA-BBB", "long ark form"),
        ("~fs:3:1:AAAA-BBBB-CCCC", "image 3:1 namespace"),
        ("~FamilySearch ARK AAAA-BBB", "legacy bare-PID-as-ARK form"),
        ("~antenati:ark:/12657/an_ua123", "antenati external"),
        ("~ metryki.genealodzy.pl/foo/bar", "metryki url, space after tilde"),
    ]:
        check(H.count_records(f"- NOT COUNTED — {form}") == 0, f"suppressed: {label}")

    print("negated locators — POSITIVE CONTROLS, the suppressor must not overreach")
    check(H.count_records("- 1910 US Census — fs:1:1:AAAA-BBB") == 1,
          "an ordinary citation still counts")
    check(H.count_records("- 1910 US Census — fs:1:1:AAAA-BBB\n"
                          "- NOT COUNTED — ~fs:1:1:CCCC-DDD") == 1,
          "one negated, one not: exactly the unmarked one counts")
    check(H.count_records("- mixed — fs:1:1:AAAA-BBB and ~fs:1:1:CCCC-DDD") == 1,
          "both on ONE line: only the negated token drops")
    check(H.count_records("- a — fs:1:1:AAAA-BBB\n- b — fs:1:1:CCCC-DDD") == 2,
          "two ordinary records still count as two")

    print("negated locators — the tilde must not eat unrelated prose")
    # `~` is used for approximate dates all over this vault; it must stay harmless.
    check(H.count_records("- b. ~1670, Beverly — fs:1:1:AAAA-BBB") == 1,
          "an approximate-date tilde does not suppress the line's real locator")
    check(H.count_records("- b. ~1670 and d. ~1732, no sources") == 0,
          "approximate dates alone are still zero records")

    print("negated locators — strip_negated_locators is textual and idempotent")
    s = "keep fs:1:1:AAAA-BBB drop ~fs:1:1:CCCC-DDD"
    once = H.strip_negated_locators(s)
    check("AAAA-BBB" in once and "CCCC-DDD" not in once, "keeps the live id, drops the negated one")
    check(H.strip_negated_locators(once) == once, "idempotent")
    check(H.strip_negated_locators("") == "", "empty input is safe")
    check(H.strip_negated_locators(None) == "", "None is safe")

    print("negated locators — per-host breakdown honours it too")
    check(H.per_host_locators("~fs:1:1:AAAA-BBB").get("familysearch", 0) == 0,
          "per_host_locators does not count a negated locator")
    check(H.per_host_locators("fs:1:1:AAAA-BBB").get("familysearch", 0) == 1,
          "per_host_locators still counts a live one")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
