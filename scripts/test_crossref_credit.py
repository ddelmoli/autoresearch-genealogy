#!/usr/bin/env python3
"""Regression tests for `credits_head_line_only` — deferred_decisions 59 (b)/(d)/(e3).

Runnable with no test framework: `python3 test_crossref_credit.py` (exit 0 = pass).

ONE principle, three head shapes: **a line that merely NAMES a person credits them
nothing when the records it carries document somebody else.** Spec 05 and rule 8 limbs
(g)/(h) had each already said this in other clothing; these three escaped only because
they carry no ENUMERATING head-word, which is all `is_kin_list_line` looks for.

⭐⭐ THE TREATMENT IS "KEEP THE HEAD LINE, DROP THE SUB-BULLETS" — deliberately NOT the
kin list's whole-region drop. A spouse / roster / header line names ONE person and may
carry that person's SHARED ACT (`... m. **17 JAN 1883 <Town>** atto 2 — <ARK>`), and a
marriage act, census household or joint manifest documents BOTH parties. That is a
standing invariant in `test_foreign_credit_magnitude`, and **it caught the first cut of
this rule**, which dropped whole regions and destroyed three people's shared acts along
with the borrowed piles. The split was then measured and is clean: every demolition case
carries 0 records on its head line and all of them below (16/16, 16/16, 20/20, 16/16,
24 of 25); every legitimate case is the reverse.

Measured after that refinement: **7 people change, 4 of them to 0 own records** —
SOURCE_GAP +4, LOW_COVERAGE +2, WELL_SOURCED −6. Two of the four read WELL_SOURCED off a
husband's marriage line while their own entries carry no `Sources` bullet at all, and one
of those entries says in terms that her parentage is UNRESEARCHED. That is the limb-(g)
failure exactly: the metric stops distinguishing DOCUMENTED from MENTIONED, so nobody is
ever prompted to research the people about whom least is known.

⚠⚠ THE FAIL DIRECTION IS THE OPPOSITE OF `is_kin_list_line`'s. A missed kin list leaves
a pre-existing over-credit; a FALSE POSITIVE here DESTROYS a real record. So the
controls below matter more than the positives, and the first of them is load-bearing:
the SANCTIONED inline-collateral bullet is how this vault deliberately DOES credit a
relative, and it must keep working. A suppressor that also kills the sanctioned form is
indistinguishable from one that works.
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
    print("(e3) SPOUSE CROSS-REFERENCE — names a spouse, documents the entry's person")
    for head in [
        "- Married Jane Placeholder (b. 4 JUL 1717, Anytown; d. 8 MAR 1800)",
        "- Wife: Jane Placeholder (b. ABT 1613, Somewhereton, England; FS: XXXX-XXX)",
        "- **Husband: John Placeholder** (b. ~1891, d. 1965; parents A + B; **FS: XXXX-XXX**)",
        "- Spouse: Jane Placeholder (no dates recorded)",
    ]:
        check(H.credits_head_line_only(head), head[:72])

    print("\n(b) NUMBERED ROSTER ITEM — a kin list wearing a number")
    for head in [
        "5. **Example Ancestor** (b. 1893; index 1893 #101; **FS XXXX-XXX**; emigrated 1909)",
        "6. **Another Ancestor** (b. 10 JUL 1917; d. 27 OCT 1995 Anytown; FS PID YYYY-YYY)",
        "1) **Third Ancestor** (FS ZZZZ-ZZZ; b. ~1861/2 Somewhereton)",
    ]:
        check(H.credits_head_line_only(head), head[:72])

    print("\n(d) THE ENTRY'S OWN HEADER — a line-start bold span IS an entry header")
    for head in [
        "**Example Person** (b. **21 MAR 1911, Anytown**; d. **1983**; FS PID XXXX-XXX)",
        "**Example Person — WWII KIA: SERVICE DOSSIER. NOT AN ENTRY.** His canonical record is",
        "**Another Person** (d. BEF 1898, Somewhereton; FS: no PID) — father of **A Third**",
    ]:
        check(H.credits_head_line_only(head), head[:72])

    print("\n⛔ LOAD-BEARING CONTROL — the SANCTIONED inline-collateral bullet must survive")
    for head in [
        "- **FS-attached sources for wife Jane Placeholder** (XXXX-XXX, inline collateral): "
        "fs:1:1:AAAA-111, fs:1:1:BBBB-222",
        "- **FS-attached sources for son John Placeholder** (YYYY-YYY, inline collateral; "
        "Recipe-S 21 JUN 2026): fs:1:1:CCCC-333",
    ]:
        check(not H.credits_head_line_only(head),
              "sanctioned: " + head[:58])

    print("\nCONTROLS — heads that must keep crediting")
    for head, label in [
        ("- **Sources** (Recipe-S harvest 21 JUN 2026, 46 FS sources; many co-attach): "
         "fs:1:1:AAAA-111",
         "(e1) the entry's OWN Sources bullet — deliberately NOT in scope"),
        ("- **Marriage record read 12 MAY 2026** — fs:1:1:AAAA-111",
         "'Marriage' is not 'married' — a record bullet, not a cross-ref"),
        ("- **Memorial** for the couple — ~fs:1:1:AAAA-111",
         "ordinary off-metric bullet"),
        ("3. **Suffolk Deeds vol 2** shows the conveyance — fs:3:1:AAAA-111",
         "numbered item with NO vitals parenthetical — an analysis item, not a roster"),
        ("- **FS identity RESOLVED 20 JUN 2026 (decisive family-unit match):** the earlier",
         "(e4) analysis prose — deliberately NOT in scope"),
        ("- Children (6): a, b, c", "kin list — is_kin_list_line owns this one"),
        ("- plain prose naming nobody", "no shape at all"),
        ("- m. 17 JAN 1883 Sometown, atto 2",
         "a bare 'm.' is NOT a relation word here — unmeasured, and the fail "
         "direction destroys records, so it was dropped rather than widened for"),
        ("", "empty head"),
    ]:
        check(not H.credits_head_line_only(head), label)

    print("\nCOMPOSITION — the sibling predicates are unchanged")
    check(H.is_kin_list_line("- Children (6): a, b, c"),
          "is_kin_list_line still fires on a kin list")
    check(H.struck_out_head("5. ~~Example Ancestor (FS XXXX-XXX)~~ — **REMOVED**"),
          "struck_out_head still fires on a struck subject")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
