#!/usr/bin/env python3
"""Regression tests for deferred_decisions 64 — a printed TRANSCRIPTION is a RECORD.

Runnable with no test framework: `python3 test_printed_record_series.py` (exit 0 = pass).

Operator ruling 09 AUG 2026. `is_book_collection` missed two very different classes and
they must be treated in OPPOSITE directions:

  * DERIVATIVE WORKS — town and family histories, "Pioneers of …" volumes, compiled
    descendants genealogies, journals. Analysis ABOUT people. Now SCREENED (limb (c)).
  * PRINTED RECORD SERIES — town Vital Records (the NEHGS volumes), county Deeds,
    County Court records, Probate Records, Wills Abstracts. A published edition OF a
    register. These COUNT, and must never be added to the marker list.

⭐⭐ THE RULING TURNS ON A PARITY THE METRIC ALREADY CONTAINED. The FILM IMAGES of a town
register count; an FS INDEX entry for it is a VOLUNTEER's transcription and counts; the
NEHGS PRINTED VOLUME is an EDITOR's transcription of the same register and did not. The
identical record counted or not by which transcription you happened to read — an artifact
of ACCESS ROUTE, not evidence quality. **The line is transcription vs narrative, not
print vs film.**

⚠⚠ THE FAIL DIRECTION IS DESTRUCTIVE: a false positive REMOVES a real record from the
census. So the "must keep counting" block below is the load-bearing half, and the marker
list is deliberately narrow — a bare "history of" marker was considered and NOT taken.

⛔ AND SCREENING THIS CLASS WOULD HAVE BROKEN THE OTHER HALF OF THE CENSUS: of 23 entries
whose Sources bullet names a printed record series, only 8 cite apparatus that
`SCHOLARLY_CITATION_RE` recognises, so screening the other 15 would have moved them to
UNCITED — "nobody has cited anything" — about entries cited to the best evidence there is.
Any future move of this class must widen BOTH classifiers in the same commit; the last
case below pins that dependency.
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
    print("DERIVATIVE WORKS — narrative/analysis ABOUT people, screened under limb (c)")
    for t in [
        "History of the town of Hingham, Massachusetts",
        "History of the City of Boston",
        "The Pioneers of Massachusetts",
        "Genealogies of the families of Braintree",
        "The Descendants of John Alden",
        "Bay State Monthly",
    ]:
        check(H.is_book_collection(t), t)

    print("\n⚠ LOAD-BEARING — PRINTED RECORD SERIES MUST KEEP COUNTING")
    for t in [
        "Suffolk. Deeds 1661-1672",
        "Records of the Suffolk County Court 1671-1680",
        "Suffolk County Wills Abstracts",
        "Suffolk Grantor Deed Indexes",
        "Essex County, Massachusetts, Quarterly Court Records",
        "Plymouth County, Massachusetts, Probate Records 1686-1881",
        "Vital records of Weymouth, Massachusetts, to the year 1850",
        "Vital Records of Scituate, Massachusetts, to the year 1850",
        "Records of the Governor and Company of the Massachusetts Bay",
    ]:
        check(not H.is_book_collection(t), t)

    print("\n⚠ ORDINARY RECORD COLLECTIONS — untouched")
    for t in [
        "Massachusetts, Town Clerk, Vital and Town Records, 1626-2001",
        "England and Wales Census 1881",
        "New York, New York City Municipal Deaths, 1795-1949",
        # The reason a bare "monthly" marker was NOT used: Quaker Monthly Meeting
        # minutes are PRIMARY records, and would have been screened by it.
        "Massachusetts Monthly Meeting Records (Quaker)",
    ]:
        check(not H.is_book_collection(t), t)

    print("\nPRE-EXISTING MARKERS still fire (deferred 48 is not regressed)")
    for t in [
        "New England, The Great Migration and The Great Migration Begins, 1620-1635",
        "Torrey's New England Marriages Prior to 1700",
        "Colonial Families of the United States of America",
        "Millennium File",
        "Genealogical history of Deer Isle families",
    ]:
        check(H.is_book_collection(t), t)

    print("\nTHE CROSS-CLASSIFIER DEPENDENCY — pinned so a future change cannot forget it")
    # If a printed record series is ever screened as a book, these must ALSO become
    # recognised apparatus, or the rows land in UNCITED rather than BOOK_SOURCED.
    for t in ["Suffolk. Deeds 1661-1672",
              "Vital records of Weymouth, Massachusetts, to the year 1850"]:
        screened = H.is_book_collection(t)
        apparatus = H.has_scholarly_citation(t)
        check(not (screened and not apparatus),
              f"not screened-without-apparatus: {t[:52]}")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
