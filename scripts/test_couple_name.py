#!/usr/bin/env python3
"""Pin the COUPLE_NAME advisory in gen_person_index.py --integrity.

A vault entry may be written as a COUPLE -- one bold name, one `- meta:` block --
carrying a single `id`, `generation` and `died` for a HUSBAND AND A WIFE. That
passes every existing gate: DUP_ID checks ids are UNIQUE, MISSING_ID that they
are PRESENT, and neither asks whether a NAME denotes ONE PERSON.

Why it matters: children of such a couple CANNOT be wired. A
`parents: '[<couple-id>]'` edge records ONE parent where TWO are known, so the
row reads as half-wired when it is actually complete -- worse than silent,
because it looks answered.

⚠ THE NEGATIVE CONTROLS ARE THE POINT OF THIS FILE. On the corpus that prompted
the check, a naive scan over ~1,477 records returned 8 hits and SEVEN were FALSE
POSITIVES -- single people whose TITLE contained "and"/"&". A guard that fires on
those gets ignored within a session, so the connector set is deliberately narrow
and those seven shapes are pinned here.

⚠ ALL FIXTURES BELOW ARE SYNTHETIC. This file is in the PUBLIC framework repo,
which carries zero real family names (CONTRIBUTING.md, "the framework/private
boundary"); the strings mirror the SHAPE of the measured cases, not the people.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_person_index import _is_couple_name

# A name that denotes TWO PEOPLE — the defect this check exists to catch.
MUST_FLAG = [
    "Alonso Examplesson + Bertha",          # the shape that raised it: bare ` + `
    "Alonso and Bertha",                    # bare ` and `, no title, no bracket
    "Alonso Examplesson & Bertha Placeholt",
    "Cedric Testfield + Dorotea",
]

# Single people that must STAY QUIET. The first seven mirror the seven measured
# false positives: a peerage or territorial TITLE containing "and"/"&".
MUST_NOT_FLAG = [
    "Aldous Examplesson [Earl of Northpiece & Southpiece]",
    "Bertrand Placeholt [Baron I], King of the Testlands & Emperor",
    "Cedric of Testshire [Earl of Northpiece & Eastmarch]",
    "Dunstan Testfield [of Upper Sample and Lower Sample]",
    "Edmund de la Sample [of Sample Hall and Westfold]",
    "Fulk Testfield [of Westfold and Upper Sample]",
    "Gerald Testfield [of Upper Sample and Westfold]",
    # ordinary vault name SHAPES that must also stay quiet
    "Bertha, wife of Alonso Examplesson",
    "Sarah [maiden surname unconfirmed], wife of Cedric Testfield",
    "Hedwig [Hedy] de Sample",
    "Ingram [Ing], Lord of Sampleton, Westfold and Eastmarch",
    "Jorund [Jori], Graf [Testinger]",
]


def main():
    bad = []
    for n in MUST_FLAG:
        if not _is_couple_name(n):
            bad.append(f"MISSED (should flag): {n}")
    for n in MUST_NOT_FLAG:
        if _is_couple_name(n):
            bad.append(f"FALSE POSITIVE (should be clean): {n}")
    if bad:
        print("COUPLE_NAME test FAILED:")
        for b in bad:
            print("   ", b)
        return 1
    print(f"COUPLE_NAME test ok "
          f"({len(MUST_FLAG)} flag, {len(MUST_NOT_FLAG)} negative controls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
