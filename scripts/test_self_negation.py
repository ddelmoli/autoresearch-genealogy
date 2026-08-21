#!/usr/bin/env python3
"""Regression tests for `self_negation_audit.findings` (Open_Questions Q305).

Runnable with no test framework: `python3 test_self_negation.py` (exit 0 = pass).

The check exists because `~` is scoped to the ENTRY, so a locator quoted with a `~` in
an audit note silently cancels the same token where the entry cites it properly. On the
reference vault that had one person reading SOURCE_GAP / 0 ARKs while citing a birth and
a marriage, and another whose own death-register entry -- the record naming his parents
-- had been filed into a list of his children's deaths.

EVERY case carries its positive control, per this repo's convention. A detector that
fires on everything is indistinguishable from one that works, and the first hand-rolled
version of this check returned a FALSE ZERO: its regex matched only `~fs:`-prefixed
tokens, so it could not see the `~1:1:` and `~ark:/61903/` spellings the counter treats
as the same locator. It reported 0 on a vault holding ten cancelled citations.

⚠ This suite also pins the asymmetry that the first draft of the suite ITSELF got wrong:
a bare `~PID` with no namespace does NOT cancel a host-prefixed citation. That assertion
was written from a real vault row whose cancelling token turned out to be host-prefixed
all along -- a generalisation from one example, which the test then refuted.

The two-tier split is pinned here as well, because it is the part most likely to be
"simplified" away: a sub-bullet may legitimately carry several locators for ONE record,
and negating one of them to stop that record being double-counted is CORRECT.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import self_negation_audit as S

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


def tiers(body):
    """Run findings() over ONE synthetic entry; return {token: tier}."""
    entries = {"F.md": [("P-AAA111", "Test Person", 1, body)]}
    orig = S.H.entry_blocks_with_ids
    S.H.entry_blocks_with_ids = lambda vault=None: entries
    try:
        out = S.findings(None)
    finally:
        S.H.entry_blocks_with_ids = orig
    return {tok: tier for _, _, _, rows in out for tok, tier in rows}


CITED = "- **Sources**\n  - her birth, 1691 — fs:1:1:AAAA-BBB\n"


def main():
    print("SELF_NEGATION — the defect it exists to catch")
    t = tiers(CITED + "- AUDITED: indexed twice — ~fs:1:1:AAAA-BBB\n")
    check(t.get("fs:1:1:AAAA-BBB") == "LOST",
          "a `~` elsewhere in the entry cancels the Sources citation")

    for neg, label in [("~1:1:AAAA-BBB", "bare namespace `1:1:`"),
                       ("~ark:/61903/1:1:AAAA-BBB", "long ark form")]:
        t = tiers(CITED + f"- note — {neg}\n")
        check(t.get("fs:1:1:AAAA-BBB") == "LOST",
              f"negation resolves across spellings: {label} cancels a host-prefixed citation")

    t = tiers("- **Sources**\n  - his death, 1853 — fs:1:1:CCCC-DDD\n"
              "- children's deaths, all postdating his own — ~fs:1:1:CCCC-DDD\n")
    check(t.get("fs:1:1:CCCC-DDD") == "LOST",
          "own record misfiled into an exclusion list is LOST")

    print("SELF_NEGATION — POSITIVE CONTROLS, the detector must not overreach")
    check(tiers(CITED) == {},
          "an ordinary citation with no negation anywhere is clean")
    check(tiers(CITED + "- NOT COUNTED — ~fs:1:1:ZZZZ-YYY\n") == {},
          "negating a DIFFERENT token does not implicate the cited one")
    # ⚠ PINNED ASYMMETRY, not an aspiration: a `~` binds to the token AS WRITTEN, so a
    # bare PID with no namespace cannot cancel a host-prefixed citation. The first draft
    # of this suite asserted the opposite -- generalising from a real vault row whose
    # cancelling token was host-prefixed all along -- and the assertion failed. Same
    # asymmetry `bare_ark_audit` exists for; if this ever starts passing, the counter
    # changed underneath and BOTH gates need re-reading.
    check(tiers(CITED + "- 1930 census note (household ARK ~AAAA-BBB)\n") == {},
          "a BARE `~PID` does NOT cancel a host-prefixed citation")
    check(tiers("- prose only — fs:1:1:AAAA-BBB\n"
                "- NOT COUNTED — ~fs:1:1:AAAA-BBB\n") == {},
          "no `- **Sources**` bullet: nothing is CLAIMED, so nothing is lost")
    check(tiers("- **Sources**\n  - a — fs:1:1:AAAA-BBB\n  - b — fs:1:1:CCCC-DDD\n") == {},
          "two ordinary citations stay clean")

    print("SELF_NEGATION — the DEDUP tier: one record, several locators")
    t = tiers("- **Sources**\n"
              "  - her christening — index + register image — fs:1:1:AAAA-BBB, fs:3:1:EEEE-FFFF\n"
              "- the image duplicates the indexed record — ~fs:3:1:EEEE-FFFF\n")
    check(t.get("fs:3:1:EEEE-FFFF") == "DEDUP",
          "a sibling on the SAME sub-bullet survives -> the record is still counted")
    check("fs:1:1:AAAA-BBB" not in t,
          "the surviving sibling is not itself reported")

    t = tiers("- **Sources**\n"
              "  - one record on two hosts — fs:1:1:AAAA-BBB, anc:6224:1234\n"
              "- write-back evidence — ~fs:1:1:AAAA-BBB\n")
    check(t.get("fs:1:1:AAAA-BBB") == "DEDUP",
          "cross-host duplicate of one record is DEDUP, not LOST")

    t = tiers("- **Sources**\n"
              "  - her christening — index + image — fs:1:1:AAAA-BBB, fs:3:1:EEEE-FFFF\n"
              "- both refused — ~fs:1:1:AAAA-BBB, ~fs:3:1:EEEE-FFFF\n")
    check(set(t.values()) == {"LOST"},
          "when NO sibling survives the sub-bullet, both tokens are LOST")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
