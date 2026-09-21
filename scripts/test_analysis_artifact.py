#!/usr/bin/env python3
"""Regression tests for the contributor-analysis artifact class (deferred 62).

Runnable with no test framework: `python3 test_analysis_artifact.py` (exit 0 = pass).

A tree host may serve, as an attached "source", something that is not a document at
all — the standing case is a summary of DNA matches, generated from the very tree it
hangs on, whose locator is an internal source id rather than an ARK. The operator
ruled it OFF-METRIC (20 SEP 2026) rather than an exclusion limb: DNA is real
relationship evidence that is simply not a record.

⚠⚠ WHY A POLICY SCREEN AND NOT A SHAPE TEST, re-measured 20 SEP 2026. The raised item
argued that the same id in the prescribed `host:locator` grammar would count. For
FamilySearch that has been FALSE since the evening of the day it was raised: Q200 made
`is_record_locator` require an `fs:` tail of `1:1:`/`3:1:`/`ark:/N/`. But that guard is
deliberately FS-ONLY — Q200 measured a general path-shaped-locator rule and refuted it,
because it destroyed 16 legitimate `tna:`, `agad:` and `anc:` locators — so on every
OTHER host the id still counts. The first block below pins both halves, because the
exposure is real and sits on the tree hosts, which is not where the item looked.

Every marker case carries a NEGATIVE control. A classifier that classifies everything
is indistinguishable from one that works, and here a false positive moves a REAL
record off the census — the expensive direction, so the markers under-catch on
purpose.
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
    print("no shape guard covers this class — the exposure is per-HOST")
    # An internal source id, of the shape a tree host mints for a non-document
    # attachment. Bare, it is invisible to the counter.
    check(H.count_records("- DNA Connections — S308") == 0,
          "a bare internal source id does not count")
    # FamilySearch is guarded, by Q200's record-shaped-tail rule — NOT by this ruling.
    check(H.count_records("- DNA Connections — fs:S308") == 0,
          "fs: is guarded by Q200 (tail must be 1:1:/3:1:/ark:/N/)")
    # ...and every other host is NOT, deliberately: Q200 refuted a general rule because
    # it destroyed 16 real tna:/agad:/anc: locators. THIS is the live exposure, and it
    # sits on the tree hosts where such artifacts actually accumulate.
    check(H.count_records("- DNA Connections — anc:S308") == 1,
          "anc: is UNGUARDED and counts (the live exposure)")
    check(H.count_records("- DNA Connections — wt:S308") == 1,
          "wt: is UNGUARDED and counts (the live exposure)")
    # Which is why the sanctioned way to record one is a negated locator + a screen.
    check(H.count_records("- **DNA evidence** (off-metric) — ~anc:S308") == 0,
          "`~`-negated, as the rule prescribes: off the census")

    print("classifier — titles that ARE contributor-built analysis artifacts")
    for title in ("DNA Connections for a Person",
                  "DNA Connections",
                  "DNA Matches",
                  "dna match list",
                  "My DNA Story",
                  "DNA Test Results Summary"):
        check(H.is_analysis_artifact(title), f"classified: {title!r}")

    print("classifier — NEGATIVE CONTROLS, the markers must not overreach")
    # A false positive here moves a real record OFF the census, so these matter more
    # than the positives. Note the last two: ordinary titles containing the letters
    # `dna` or the word in another role must not match.
    for title in ("Massachusetts, Town Clerk, Vital and Town Records",
                  "New York, Church Records",
                  "Find a Grave Index",
                  "Genetic and Genealogical Society Journal",
                  "Edna Township Births",          # `dna` as a substring of a NAME
                  "DNA: the Secret of Life"):      # a BOOK, limb (c), not this class
        check(not H.is_analysis_artifact(title), f"not classified: {title!r}")

    print("the classifier answers ONE question, not the whole rule-8 screen")
    # `False` means "not this class" and never "this is a record" — the same contract
    # `reference_work_limb` carries, and the residual-bucket error the vault has been
    # bitten by is exactly reading it the other way.
    check(not H.is_analysis_artifact("The Descendants of a Settler, 1620-1900"),
          "a book is not this class (screen it with is_book_collection)")
    check(H.is_book_collection("The Descendants of a Settler, 1620-1900"),
          "  ...and is_book_collection is the screen that catches it")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
