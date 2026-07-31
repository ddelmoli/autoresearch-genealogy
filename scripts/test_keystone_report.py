#!/usr/bin/env python3
"""Regression tests for keystone_report.thinness (deferred_decisions 21).

Runnable with no test framework: `python3 test_keystone_report.py` (exit 0 = pass).

The defect: `no-vitals` (+2) and `placeholder-header` (+1) can never be cleared for
a person whose authorities record no dates, so she sat at THIN 3 forever and
re-drew the IMPROVE lane no matter how thoroughly she had been researched. The lane
size feeds the session bandit, so a lane whose candidates are unworkable BY
CONSTRUCTION is guaranteed to miss its target before it starts -- teaching the
bandit that IMPROVE is a losing arm for a reason that has nothing to do with the
lane. A count mixing "not done" with "cannot be done" cannot be read.

The fix has two halves and BOTH are load-bearing, so both are pinned here:

  (1) a `VITALS UNRECOVERABLE` body declaration suppresses those two components,
      mirroring extension_frontier's SILENT/DECLARED split and `known_gen_collapse`
      -- the operator declares, the tool stops counting.
  (3) `blocked` marks a row held in the lane ONLY by those components, so the plan
      can report the floor rather than hiding it in the total.

EVERY case carries its negative control. The rejected option (2) -- "cap THIN when
the entry cites real apparatus" -- was rejected precisely because it would also
silence genuinely unworked entries that happen to name a source, so the controls
below assert that a declaration does NOT launder an entry with no write-up and no
source. A suppression that can be applied to anything is not a declaration, it is
a way to make the worklist shorter without doing any work.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import keystone_report as kr

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


# A body that is WORKED by every measure thinness can see: four bullets and a named
# authority. The only thing keeping such an entry in the lane is the absent vitals.
WORKED = """- meta: {id: P-JFB426, generation: 26}
- Daughter of the Tibetot line; parentage corroborated by Cawley.
- The Complete Peerage, read directly, gives her no dates.
- Married into the Malet line; see the marriage settlement.
- Nothing further is attested.
"""

# The control: nobody has written this person up and nothing is cited.
UNWORKED = """- meta: {id: P-XXXXXX, generation: 26}
"""

DECLARATION = ("- **VITALS UNRECOVERABLE 31 JUL 2026**: Cawley gives her no dates and "
               "the Complete Peerage, read directly, gives her none either.\n")

# The same marker with NO authority named. Kept separate because a declaration that
# names its authorities also (legitimately) clears `no-source-of-any-kind` -- the
# entry does now cite something. Isolating the marker from the citation is the only
# way to test what the DECLARATION suppresses versus what the CITATION suppresses.
DECLARATION_BARE = "- **VITALS UNRECOVERABLE 31 JUL 2026**: no dates found.\n"

NO_VITALS = {"born": "", "died": "", "header_paren": "unknown; unknown"}
HAS_VITALS = {"born": "1234", "died": "1310", "header_paren": "b. 1234; d. 1310"}


def main():
    print("=== keystone_report.thinness: the vitals floor (deferred 21) ===\n")

    # --- (3) the floor is DETECTED -------------------------------------------------
    thin, why, blocked = kr.thinness(NO_VITALS, WORKED, 0)
    check(thin == 3, f"worked entry, no vitals: THIN 3 (got {thin})")
    check(blocked is True, "worked entry, no vitals: flagged vitals-blocked")
    check(set(why) == {"no-vitals", "placeholder-header"},
          f"worked entry: thinness is ONLY the two settleable components (got {why})")

    # NEGATIVE CONTROL: an entry thin for reasons a declaration cannot settle is NOT
    # blocked. If this ever reports True, the flag has stopped meaning anything.
    thin, why, blocked = kr.thinness(NO_VITALS, UNWORKED, 0)
    check(blocked is False, "unworked entry: NOT flagged vitals-blocked")
    check(thin == 6, f"unworked entry: THIN 6, the real worklist (got {thin})")

    # NEGATIVE CONTROL: a person with dates was never in this population.
    _, why, blocked = kr.thinness(HAS_VITALS, WORKED, 0)
    check(blocked is False, "entry with vitals: NOT flagged vitals-blocked")
    check("no-vitals" not in why, "entry with vitals: no-vitals does not score")

    # --- (1) the DECLARATION suppresses --------------------------------------------
    thin, why, blocked = kr.thinness(NO_VITALS, WORKED + DECLARATION, 0)
    check(thin == 0, f"declared: THIN drops to 0, leaving the lane (got {thin})")
    check(blocked is False, "declared: no longer counted against the floor")
    check("[declared: vitals unrecoverable]" in why,
          f"declared: the reason is visible in WHY (got {why})")
    check("no-vitals" not in why and "placeholder-header" not in why,
          "declared: the settled components stop scoring")

    # THE CONTROL THAT MATTERS MOST: a declaration must NOT launder an entry that is
    # thin for other reasons. This is why rejected option (2) was rejected -- capping
    # THIN on the mere presence of apparatus would silence genuinely unworked entries.
    thin, why, blocked = kr.thinness(NO_VITALS, UNWORKED + DECLARATION_BARE, 0)
    check(thin == 4, f"declared BUT unworked: THIN 4, not 0 (got {thin})")
    check("no-writeup" in " ".join(why), "declared BUT unworked: no-writeup still scores")
    check("no-source-of-any-kind" in why,
          "declared BUT unworked: no-source-of-any-kind still scores")
    check(blocked is False, "declared BUT unworked: still not counted as the floor")

    # And the declaration only ever removes its OWN two components: naming Cawley in
    # the declaration clears `no-source-of-any-kind` because the entry now genuinely
    # cites an authority, but `no-writeup` survives either way.
    thin, why, _ = kr.thinness(NO_VITALS, UNWORKED + DECLARATION, 0)
    check(thin == 3, f"declared, authority named, no write-up: THIN 3 (got {thin})")
    check("no-writeup" in " ".join(why),
          "declared, authority named: no-writeup is NOT laundered by the citation")

    # A declaration on an entry that has nothing to suppress must be inert, not negative.
    thin, _, _ = kr.thinness(HAS_VITALS, WORKED + DECLARATION, 0)
    check(thin == 0, f"declared with nothing to settle: inert, THIN 0 (got {thin})")

    # --- the census veto still composes --------------------------------------------
    thin, why, _ = kr.thinness(NO_VITALS, UNWORKED, 4)
    check(thin == 1, f"WELL_SOURCED cap still applies after the change (got {thin})")
    thin, _, _ = kr.thinness(NO_VITALS, UNWORKED, 1)
    check(thin == 3, f"ARK cap still applies after the change (got {thin})")

    # --- the marker is a LITERAL, matched case-insensitively -----------------------
    _, _, blocked = kr.thinness(NO_VITALS, WORKED + DECLARATION.lower(), 0)
    check(blocked is False, "declaration matches case-insensitively")
    _, _, blocked = kr.thinness(NO_VITALS, WORKED + "- Her vitals are unrecoverable.\n", 0)
    check(blocked is True,
          "prose ABOUT unrecoverable vitals is not a declaration; the marker is literal")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
