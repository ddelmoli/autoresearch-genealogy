#!/usr/bin/env python3
"""Regression tests for `source_symmetry_audit`.

Runnable with no test framework: `python3 test_source_symmetry.py` (exit 0 = pass).

EVERY case carries its NEGATIVE CONTROL. A detector that fires on everything is
indistinguishable from one that works, and the throwaway script these checks
replace shipped exactly that mistake: it used its own locator regex, over-matched
on backticked tokens, and reported a defect on an entry the census reads as zero.
So the controls below assert both halves each time: the defect IS seen, and the
clean shape beside it is NOT.

All names are placeholders.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import source_symmetry_audit as S  # noqa: E402

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")


# ---------------------------------------------------------------- lens D
print("DESCRIBED_NOT_NEGATED")

blocks = {
    "P-AAAAAA": ("Jane Placeholder", "Family_Tree_Example.md",
                 "- Her other attachment earns nothing: a compiled genealogy (anc:9999:12345)\n"),
    # NEGATIVE CONTROL: same sentence, locator correctly negated -> must NOT fire
    "P-BBBBBB": ("John Placeholder", "Family_Tree_Example.md",
                 "- His other attachment earns nothing: a compiled genealogy (~anc:9999:12345)\n"),
    # NEGATIVE CONTROL: a real citation with no non-evidence wording -> must NOT fire
    "P-CCCCCC": ("Mary Placeholder", "Family_Tree_Example.md",
                 "- 1850 census, Anytown — fs:1:1:XXXX-XXX\n"),
}
hits = {r[0] for r in S.described_not_negated(blocks)}
check("P-AAAAAA" in hits, "fires on an un-negated locator called 'earns nothing'")
check("P-BBBBBB" not in hits, "NEGATIVE CONTROL: silent when the locator IS negated")
check("P-CCCCCC" not in hits, "NEGATIVE CONTROL: silent on an ordinary citation")

# The exact shape that motivated the check: 'NOT counted here' with a live locator.
blocks2 = {"P-DDDDDD": ("Ann Placeholder", "Family_Tree_Example.md",
                        "- Her 1648 deposition (fs:3:1:AAAA-BBBB-CCCC) is NOT counted here — "
                        "it documents somebody else.\n")}
check(len(S.described_not_negated(blocks2)) == 1, "fires on 'is NOT counted here'")

# A negated locator inside the SAME line as a live one must leave the live one alone,
# i.e. the check reports the line, and `record_locators` reports only the live token.
blocks3 = {"P-EEEEEE": ("Eve Placeholder", "Family_Tree_Example.md",
                        "- bibliographic: ~anc:1:2 and the real one fs:1:1:YYYY-YYY\n")}
rows = S.described_not_negated(blocks3)
check(len(rows) == 1 and rows[0][3] == ["fs:1:1:YYYY-YYY"],
      "reports only the LIVE locator on a mixed line")


# ---------------------------------------------------------------- lens C
print("\nSPOUSE_ASYMMETRY")

blocks = {
    "P-H00000": ("Husband Placeholder", "Family_Tree_Example.md",
                 "- marriage to Wife Placeholder, 1720 — anc:2495:111\n"),
    "P-W00000": ("Wife Placeholder", "Family_Tree_Example.md",
                 "- She kept house at Anytown.\n"),
}
spouses = {"P-H00000": ["P-W00000"], "P-W00000": ["P-H00000"]}
rows = S.spouse_asymmetry(blocks, spouses)
check(len(rows) == 1 and rows[0][0] == "P-W00000",
      "fires on the spouse who LACKS the marriage locator")

# NEGATIVE CONTROL: both spouses cite it -> silent.
blocks_sym = dict(blocks)
blocks_sym["P-W00000"] = ("Wife Placeholder", "Family_Tree_Example.md",
                          "- marriage to Husband Placeholder, 1720 — anc:2495:111\n")
check(S.spouse_asymmetry(blocks_sym, spouses) == [],
      "NEGATIVE CONTROL: silent when BOTH spouses cite the marriage")

# NEGATIVE CONTROL: neither cites one -> silent (nothing to propagate).
blocks_none = {
    "P-H00000": ("Husband Placeholder", "Family_Tree_Example.md", "- No sources yet.\n"),
    "P-W00000": ("Wife Placeholder", "Family_Tree_Example.md", "- No sources yet.\n"),
}
check(S.spouse_asymmetry(blocks_none, spouses) == [],
      "NEGATIVE CONTROL: silent when NEITHER spouse cites a marriage")

# NEGATIVE CONTROL: a NON-marriage locator must not drive the check. A census on
# one spouse only is ordinary, not a defect.
blocks_census = {
    "P-H00000": ("Husband Placeholder", "Family_Tree_Example.md",
                 "- 1850 census, Anytown — fs:1:1:XXXX-XXX\n"),
    "P-W00000": ("Wife Placeholder", "Family_Tree_Example.md", "- No sources yet.\n"),
}
check(S.spouse_asymmetry(blocks_census, spouses) == [],
      "NEGATIVE CONTROL: a census-only asymmetry does NOT fire")

# A `~`-negated marriage locator is not a citation, so it cannot create asymmetry.
blocks_neg = {
    "P-H00000": ("Husband Placeholder", "Family_Tree_Example.md",
                 "- marriage record, rejected — ~anc:2495:111\n"),
    "P-W00000": ("Wife Placeholder", "Family_Tree_Example.md", "- No sources yet.\n"),
}
check(S.spouse_asymmetry(blocks_neg, spouses) == [],
      "NEGATIVE CONTROL: a negated marriage locator does not create asymmetry")

# The spouse edge may carry a trailing '?'; it must still resolve.
spouses_q = {"P-H00000": ["P-W00000?"], "P-W00000": ["P-H00000?"]}
check(len(S.spouse_asymmetry(blocks, spouses_q)) == 1,
      "an unverified '?' spouse edge still pairs")


print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
