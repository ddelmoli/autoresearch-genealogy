#!/usr/bin/env python3
"""Regression tests for `is_obituary_collection` / `obituary_postdates_death` (limb (f)).

Runnable with no test framework: `python3 test_obituary_collection.py` (exit 0 = pass).

WHY THESE EXIST. Limb (f) was the one source class rule 8 names that had NO detector,
while (c), (d) and (e) all had one. Measured across 335 people with a live FS PID and a
dated death: 116 obituary attachments postdate their own subject's death, on 39 people
(12%), median gap 40 years, max 73. The mechanism is that ONE family obituary names
several relatives, FamilySearch mints a persona per name, and each persona is attached
to that relative's profile -- confirmed by three married couples carrying IDENTICAL
obituary sets while having died ten and twenty years apart.

EVERY case carries a POSITIVE CONTROL. A screen that flags everything is
indistinguishable from one that works, and the whole value of limb (f) is that
obituaries DO count -- so the cases asserting that a person's OWN obituary is NOT
flagged are the ones that matter most.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as H

FAILED = []


def check(label, got, want):
    if got != want:
        FAILED.append(f"{label}\n     got:  {got!r}\n     want: {want!r}")
    else:
        print(f"  ok   {label}")


print("=== is_obituary_collection: the CLASS ===")
check("GenealogyBank Historical Newspaper Obituaries",
      H.is_obituary_collection('United States, GenealogyBank Historical Newspaper Obituaries, 1815-2013'), True)
check("GenealogyBank Obituaries, Births, and Marriages",
      H.is_obituary_collection('United States, GenealogyBank Obituaries, Births, and Marriages, 1980-2015'), True)
check("Obituary Records (singular stem)",
      H.is_obituary_collection('United States, Obituary Records, 2014-2023'), True)
check("death notice",
      H.is_obituary_collection('Anystate, Anycounty, Death Notices'), True)
check("case-insensitive",
      H.is_obituary_collection('OBITUARIES'), True)

print("\n=== POSITIVE CONTROLS: ordinary collections must NOT match ===")
for t in ['Massachusetts, State Vital Records, 1638-1927',
          'United States, Census, 1940',
          'England, Lincolnshire, Parish Registers, 1538-1990',
          'United States Social Security Death Index',
          'Find a Grave Index',
          'United States, World War II Army Enlistment Records, 1938-1946',
          "Italia, L'Aquila, Stato Civile (Archivio di Stato), 1809-1944"]:
    check(f"NOT an obituary collection: {t[:44]}", H.is_obituary_collection(t), False)

check("empty title", H.is_obituary_collection(''), False)
check("None title", H.is_obituary_collection(None), False)

# ⚠ The `igi` precedent: a bare marker was REFUSED there because it is a substring of
# `original` / `digital` / `digitized`. Assert that `obituar` has no such collision.
print("\n=== the `igi` precedent: no substring collision ===")
for t in ['Original digitized parish register', 'Digital Images, Original Records',
          'Obituaries of Digitized Originals']:
    want = 'obituar' in t.casefold()
    check(f"collision check: {t[:40]}", H.is_obituary_collection(t), want)

print("\n=== obituary_postdates_death: WHOSE death does it report ===")
OB = 'United States, GenealogyBank Historical Newspaper Obituaries, 1815-2013'

# THE DEFECT: an obituary decades after the person's own death is a relative's.
check("d.1995, obituary 2011 -> flagged", H.obituary_postdates_death(OB, 2011, 1995), True)
check("d.1890, obituary 1963 (73 yr) -> flagged", H.obituary_postdates_death(OB, 1963, 1890), True)

# POSITIVE CONTROLS: a person's OWN obituary must NEVER be flagged. Limb (f) counts it.
check("d.1995, obituary 1995 -> NOT flagged (his own)",
      H.obituary_postdates_death(OB, 1995, 1995), False)
check("year-boundary: d.1959, obituary 1960 -> NOT flagged (grace=1)",
      H.obituary_postdates_death(OB, 1960, 1959), False)
check("an obituary BEFORE the death is not flagged by this check",
      H.obituary_postdates_death(OB, 1990, 1995), False)

# POSITIVE CONTROL: the collection gate must still apply.
check("a CENSUS dated after death is NOT an obituary finding",
      H.obituary_postdates_death('United States, Census, 1940', 2011, 1995), False)

# THE GUARD: unknown is neither innocent nor guilty.
print("\n=== the guard: a missing year is UNKNOWN, never a verdict ===")
check("no event year -> False", H.obituary_postdates_death(OB, None, 1995), False)
check("no death year  -> False", H.obituary_postdates_death(OB, 2011, None), False)
check("both missing   -> False", H.obituary_postdates_death(OB, None, None), False)
check("non-numeric year -> False", H.obituary_postdates_death(OB, 'circa 2011', 1995), False)

# grace is a dial, and widening it must hide the boundary case and nothing else.
print("\n=== grace is explicit, not hidden ===")
check("grace=0 makes the year-boundary case flag",
      H.obituary_postdates_death(OB, 1960, 1959, grace=0), True)
check("grace=5 still flags a 40-year gap",
      H.obituary_postdates_death(OB, 2005, 1959, grace=5), True)

print("\n=== obituary_years_in_line: COLLECTION RANGES are not event years ===")
# ⚠ Without this the audit fires on every obituary ever cited, including a person's
# OWN: the collection title carries its own span.
check("collection span alone yields NO year",
      H.obituary_years_in_line('GenealogyBank Historical Newspaper Obituaries, 1815-2013'), ())
check("span stripped, real event year kept",
      H.obituary_years_in_line('obituary 22 AUG 1968 — Obituaries, 1815-2013'), (1968,))
check("en-dash span also stripped",
      H.obituary_years_in_line('Obituary Records, 2014–2023'), ())
check("a bare line with one year",
      H.obituary_years_in_line('obituary indexed 1958'), (1958,))
check("no years at all", H.obituary_years_in_line('obituary, undated'), ())

print("\n=== the two structural filters, each with its worked failure ===")
# 1. ONE locator per line. A legacy multi-locator bullet carries HARVEST METADATA,
#    and the harvest YEAR reads as an event year -- 7 of 17 first-draft findings.
legacy = ('  - **FS-attached sources** (Recipe-S harvest 29 MAY 2026, 6 record ARKs; '
          'incl. an obituary): 1:1:AAAA-111, 1:1:BBBB-222, 1:1:CCCC-333')
check("legacy multi-locator bullet has >1 ark, so it is NOT judged",
      len(H.extract_arks(legacy)) != 1, True)

# 2. Only sub-bullets INSIDE a Sources bullet. Ordinary prose may discuss an
#    obituary, carry a locator and a year -- 4 of 6 second-draft findings.
check("SOURCES_BULLET_RE matches a Sources bullet",
      bool(H.SOURCES_BULLET_RE.match('  - **Sources** (harvest 2026):')), True)
check("...and does NOT match a prose status line",
      bool(H.SOURCES_BULLET_RE.match('  - **Death-record status (checked 03 JUN 2026):** ...')), False)

print()
if FAILED:
    print(f"FAILED ({len(FAILED)}):")
    for f in FAILED:
        print("  x  " + f)
    sys.exit(1)
print("all checks passed")
