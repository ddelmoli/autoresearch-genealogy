#!/usr/bin/env python3
"""Pin deferred_decisions 47 and 48 (03 AUG 2026, session #138).

TWO defects, both found by reading COLLECTION TITLES rather than locator forms:

47. A registered host with a LEGACY pattern silently lost its host attribution when
    cited in the `host:id` form. `per_host_locators` skipped a prefixed token
    `if host in legacy_hosts`, on the assumption the legacy pattern had already
    tallied it — true only when that pattern ACTUALLY MATCHED THAT TOKEN. `agad`'s
    legacy pattern matches only the scan-filename form, so an archival-reference
    AGAD locator counted as a RECORD while being attributed to NO HOST.

    ⚠ Why that is worse than it sounds: the record count stays right, so SOURCE_GAP
    is unaffected and NOTHING LOOKS WRONG. What is lost is the host, and hosts are
    what SINGLE_SOURCED / MULTI_SOURCED are computed from.

    ⚠ And note `is_single_sourced` is `ark_count > 0 and hosts <= 1`, so 0 hosts and
    1 host BOTH read as single-sourced. The live symptom is therefore on
    MULTI_SOURCED: an entry with an archival AGAD locator PLUS a second host read as
    one host, not two. That is the regression this file exists to prevent.

48. Limb (e) (memorial indexes) has had a working detector since 02 AUG 2026; limb
    (d) (published books, journals, compiled indexes) had none — while BOTH hosts
    serve books with record-shaped locators, including FamilySearch serving
    digitised books as `3:1:` IMAGE ARKs, the very form rule 8 limb (a2) describes
    as a register image and counts unconditionally.

Run: python3 scripts/test_host_attribution.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harvest_sources as H  # noqa: E402

FAILURES = []


def check(label, got, want):
    if got != want:
        FAILURES.append(f"{label}\n     got  {got!r}\n     want {want!r}")
        print(f"  FAIL {label}")
    else:
        print(f"  ok   {label}")


# ── 47: host attribution ────────────────────────────────────────────────────────
print("deferred 47 — per_host_locators attributes every registered host")

# THE REGRESSION ITSELF. Before the fix this returned {}.
check("agad ARCHIVAL reference (the bug)",
      H.per_host_locators("  - birth act - agad:300/999/99-1999"),
      {"agad": 1})

# The form that always worked — must keep working (it is what the live vault uses).
check("agad scan-filename, prefixed",
      H.per_host_locators("  - x - agad:PL_1_300_999_0000.jpg"), {"agad": 1})
check("agad scan-filename, bare legacy token",
      H.per_host_locators("  - x - PL_1_300_999_0000.jpg"), {"agad": 1})

# ⚠ THE ANTI-DOUBLE-COUNT CONTROL. `fs:1:1:X` CONTAINS the legacy token `1:1:X`, so
# a naive fix that dropped the skip entirely would count it twice. The span-overlap
# test is what keeps these at 1.
check("fs prefixed (legacy pattern nested inside)",
      H.per_host_locators("  - x - fs:1:1:ABCD-123"), {"familysearch": 1})
check("fs bare legacy token",
      H.per_host_locators("  - x - 1:1:ABCD-123"), {"familysearch": 1})
check("fs image ARK",
      H.per_host_locators("  - x - fs:3:1:XXXX-XXXX-XXXX"), {"familysearch": 1})
check("same fs locator prefixed AND bare — one locator, not two",
      H.per_host_locators("  - x - fs:1:1:AAAA-111 and 1:1:AAAA-111"),
      {"familysearch": 1})

# Documented forms of the other legacy hosts embed their legacy pattern.
check("antenati documented form",
      H.per_host_locators("  - x - antenati:ark:/12657/an_ua123/abc99"),
      {"antenati": 1})
check("metryki documented form",
      H.per_host_locators("  - x - metryki:metryki.genealodzy.pl/m.php/1234"),
      {"metryki": 1})
check("szukajwarchiwach documented form",
      H.per_host_locators("  - x - szukajwarchiwach:szukajwarchiwach.gov.pl/jednostka/99"),
      {"szukajwarchiwach": 1})

# Hosts with NO legacy pattern were never affected; pin them so a future legacy
# pattern for one of them cannot silently re-arm the trap.
check("jri (no legacy pattern)",
      H.per_host_locators("  - x - jri:999/99/1999"), {"jri": 1})
check("geshergalicia (no legacy pattern)",
      H.per_host_locators("  - x - geshergalicia:someplace/1999"), {"geshergalicia": 1})
check("anc (no legacy pattern)",
      H.per_host_locators("  - x - anc:9999:9999999"), {"anc": 1})

check("two hosts on one record line",
      H.per_host_locators("  - x - fs:1:1:AAAA-111, anc:8888:8888888"),
      {"familysearch": 1, "anc": 1})

# NEGATIVE CONTROLS — the `~` suppression and the cite-a-locator-never-the-FORM rule
# must both survive the fix.
check("negated archival agad earns nothing",
      H.per_host_locators("  - x - ~agad:300/999/99-1999"), {})
check("negated fs earns nothing",
      H.per_host_locators("  - x - ~fs:1:1:ABCD-123"), {})
check("a locator CLASS named in prose is not a citation",
      H.per_host_locators("  - browse registers attach as fs:3:1: image ARKs"), {})

# ── 48: the book detector ───────────────────────────────────────────────────────
print("\ndeferred 48 — is_book_collection names the policy-(d) class")

BOOKS = [
    "Colonial Families of the USA, 1607-1775",
    "Mayflower Births and Deaths, Vol. 1 and 2",
    "Mayflower Increasings, 2nd Edition",
    "New England, The Great Migration and The Great Migration Begins",
    "Millennium File",
    "Torrey's, New England Marriages Prior to 1700",
    "Genealogical history of Deer Isle families",
    "The Royal Descents of 600 Immigrants",
    "U.S. and International Marriage Records, 1560-1900",
    "North America, Family Histories, 1500-2000",
    "The Complete Peerage Vol-vii",
    "U.S., Sons of the American Revolution Membership Applications",
    "American Genealogical-Biographical Index",
    "Copy of Family Group Records Collection, Archives Section, 1942-1969",
    # aggregated user trees sold as collections
    "Ancestry Family Trees",
    "Geneanet Community Trees Index",
    "Community Trees",
    "Matthew Plummer, MyHeritage Family Tree",
]
for t in BOOKS:
    check(f"BOOK: {t[:52]}", H.is_book_collection(t), True)

# ⚠ NEGATIVE CONTROLS ARE THE POINT. A brand list that catches transcribed REGISTERS
# is worse than no list — these are the collections that legitimately hold records,
# several of them the exact ones that yielded real records in session #138.
RECORDS = [
    "Massachusetts, Town and Vital Records, 1620-1988",
    "Massachusetts, Town Clerk, Vital and Town Records, 1626-2001",
    "England, Middlesex, Parish Registers, 1539-1988",
    "Suffolk, England, Extracted Church of England Parish Records",
    "Delaware, Church Records, 1660-1940",
    "Massachusetts, Births and Christenings, 1639-1915",
    "England Marriages, 1538-1973",
    "Italy, Sondrio, Sondrio, Civil Registration (Tribunale), 1866-1929",
    "New York, Passenger Arrival Lists",
    "United States, Census, 1940",
    "Massachusetts, State Vital Records, 1638-1927",
    "United States, Obituary Records, 2014-2023",   # limb (f): obituaries COUNT
    "Abington, Massachusetts, Vital Records to 1850",
]
for t in RECORDS:
    check(f"RECORD: {t[:52]}", H.is_book_collection(t), False)

# The two classifiers are INDEPENDENT: a memorial is not a book, and the JOWBR
# allowlist must not be collaterally caught by the book list either.
print("\nthe (d) and (e) classifiers stay independent")
check("Find a Grave is memorial, not book",
      (H.is_memorial_collection("Find a Grave Index"),
       H.is_book_collection("Find a Grave Index")), (True, False))
check("JOWBR is neither",
      (H.is_memorial_collection("JOWBR Burial Registry"),
       H.is_book_collection("JOWBR Burial Registry")), (False, False))

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
