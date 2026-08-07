#!/usr/bin/env python3
"""Pins the Q182 ruling (05 AUG 2026) and the Q157 `before_year` criterion.

Run: python3 scripts/test_reference_works.py

TWO rulings, both operator-made, both of which a later refactor could quietly undo:

  Q182 — encyclopedia / wiki / reference-website citations are a class rule 8 did
  not name, and they SPLIT: Wikipedia, Quora and BritRoyals are limb (d) (worth
  nothing, negate with `~`), while Britannica and the IGI are limb (c)
  (bibliographic, off-metric). The failure this prevents is concrete: a title
  classifier with no such class reported "27 records" for HENRY I, dead in 1135.

  Q157 — a `structural_gap` rule may state its real CRITERION (`before_year`)
  instead of enumerating FS PIDs. The guard that matters is that an entry with NO
  dated vitals must NOT pass, since "all vitals before 1866" is vacuously true of
  someone nobody has dated.

⚠ NEGATIVE CONTROLS ARE THE POINT OF THIS FILE. Every marker list here is a
substring test over a casefolded title, and the tempting short markers are exactly
the dangerous ones — `igi` alone matches `original`, `digital` and `digitized`,
which appear in a large share of real record-collection titles.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harvest_sources as H  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}  -> {got!r}"
          + ("" if ok else f"  (expected {want!r})"))
    if not ok:
        FAILED.append(label)


print("Q182 — limb (d): tertiary, user-editable, worth nothing")
for t in (
    "Wikipedia",
    "WIKIPEDIA, Part IV",
    "Quora answer: who was Henry I's mother?",
    "BritRoyals",
    "Brit Royals: Kings and Queens of England",
    "Directory of Royal Genealogical Data",
):
    check(f"limb d: {t[:52]}", H.reference_work_limb(t), "d")

print("\nQ182 — limb (c): edited, citable, bibliographic")
for t in (
    "Encyclopaedia Britannica",
    "Encyclopedia Britannica Online",
    "International Genealogical Index (IGI)",
    "The Jewish Encyclopedia",
):
    check(f"limb c: {t[:52]}", H.reference_work_limb(t), "c")

print("\nQ182 — NOT this class (real record collections must return None)")
for t in (
    "Italy, Sondrio, Civil Registration (State Archive), 1866-1936",
    "Massachusetts, Town and Vital Records, 1620-1988",
    "New York, Original Passenger Lists, 1820-1891",     # 'igi' inside 'Original'
    "England and Wales, Digitized Parish Registers",     # 'igi' inside 'Digitized'
    "Poland, Digital Images of Church Books",            # 'igi' inside 'Digital'
    "Find a Grave Index",                                # limb (e), a DIFFERENT class
    "The Great Migration Begins",                        # limb (c) BOOK, different test
    "",
    None,
):
    check(f"None: {str(t)[:52]}", H.reference_work_limb(t), None)

print("\nQ182 — is_reference_work is TRUE for both limbs, false otherwise")
check("wikipedia", H.is_reference_work("Wikipedia"), True)
check("britannica", H.is_reference_work("Encyclopaedia Britannica"), True)
check("a civil register", H.is_reference_work(
    "Italy, Sondrio, Civil Registration, 1866-1936"), False)

print("\nQ182 — the three classifiers are INDEPENDENT, not a ladder")
check("Find a Grave: memorial yes, reference no",
      (H.is_memorial_collection("Find a Grave Index"),
       H.is_reference_work("Find a Grave Index")), (True, False))
check("Wikipedia: reference yes, book no, memorial no",
      (H.is_reference_work("Wikipedia"),
       H.is_book_collection("Wikipedia"),
       H.is_memorial_collection("Wikipedia")), (True, False, False))

print("\nQ157 — vital_years takes EVERY year, so a span's LATEST year decides")
check("plain years", H.vital_years("1799", "1866"), (1799, 1866))
check("BET ... AND ...", H.vital_years("BET 1816 AND 1823", None), (1816, 1823))
# ⚠ CHANGED 06 AUG 2026: this line asserted (1800, 1866) and was PINNING A DEFECT.
# `BEF JAN 1866` is an EXCLUSIVE bound -- before 1 JAN 1866 -- so the latest year it
# can denote is 1865, and returning 1866 made `max(years) < before_year` reject a
# life that ended before the cutoff. See test_bef_exclusive_bound.py.
check("BEF JAN 1866 (exclusive bound)", H.vital_years("ABT 1800", "BEF JAN 1866"), (1800, 1865))
check("no dates at all", H.vital_years(None, None), ())

print("\nQ157 — before_year retires a pre-registration life, and NOT the others")
RULES = [{"label": "test", "region": "Somewhere", "before_year": 1866}]
_saved = H._STRUCTURAL_RULES
H._STRUCTURAL_RULES = RULES
try:
    def structural(years, region="Italian-Somewhere", pid="XXXX-XXX", gen=7):
        return H.is_structural(pid, gen, region, years)

    check("d. 1856 in region", structural((1785, 1856)), True)
    check("b. 1860, no death", structural((1860,)), True)
    check("d. 1866 exactly — registration HAS begun", structural((1804, 1866)), False)
    check("d. 1869 — a Stato Civile death exists", structural((1819, 1869)), False)
    check("b. 1876 d. 1937 — wholly modern", structural((1876, 1937)), False)
    # ⚠⚠ the guard this test exists for
    check("NO dated vitals — must NOT be vacuously structural", structural(()), False)
    # region scoping still applies
    check("pre-1866 but a DIFFERENT region",
          structural((1800, 1840), region="Elsewhere"), False)
    # a PID-less entry can still meet a date criterion, unlike an enumeration
    check("pre-1866, no FS PID at all",
          structural((1800, 1840), pid=None), True)
finally:
    H._STRUCTURAL_RULES = _saved

print("\nQ157 — the deep-generation test is untouched by any of this")
check("Gen >= threshold, no region, no years",
      H.is_structural(None, H.STRUCTURAL_GEN, None, ()), True)

print()
if FAILED:
    print(f"FAILED {len(FAILED)}: " + "; ".join(FAILED))
    sys.exit(1)
print("all checks passed")
