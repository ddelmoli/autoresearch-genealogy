#!/usr/bin/env python3
"""Regression tests for Open_Questions Q200 — a ROUTE is not a RECORD.

Runnable with no test framework: `python3 test_route_not_a_record.py` (exit 0 = pass).

A family panel, a record-match hint list and a data-problem flag are all WHERE YOU
LOOKED, not WHAT YOU FOUND. But `fs:` + a non-space run IS the locator grammar, so each
counted as a record — and they turn up in the FS write-back grammar's `— evidence` slot,
which is precisely where a route gets mistaken for evidence.

Q200 caught FOUR family-panel URLs and negated them. **TWO MORE SURVIVED**, in a shape
the question did not anticipate: endpoint NAMES rather than URLs, so no URL screen saw
them —

    `— evidence fs:record-match hints on <PID>, read 31 JUL 2026`
    `— evidence fs:data-problem on <PID>, read 31 JUL 2026`

One of the two was a person's ONLY credited record, so he read LOW_COVERAGE on a route.

⚠⚠ THE RULE IS SCOPED TO FamilySearch, AND THE CONTROLS BELOW ARE WHY. A general
"reject a path-shaped locator" rule was measured and REFUTED: `tna:C142/87/65` (a
National Archives piece reference), `agad:300/872/31-1865` and `anc:6224/31430110` are
all legitimate and path-shaped, and a blanket rule would have destroyed 16 real
citations. **FamilySearch is the one host whose namespace mixes RECORDS with APPLICATION
ROUTES, so it is the one host that needs a shape.**

Measured before applying: of 7,621 `fs:` locators in the vault, 7,619 are `1:1:`/`3:1:`/
`ark:/` and exactly 2 are not — both routes. No legitimate citation is affected.
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
    print("FS RECORDS — the three real shapes must keep counting")
    for tok in ["fs:1:1:XXXX-YYY", "fs:3:1:3QS7-89WG-J9MJ-Y", "fs:ark:/61903/1:1:XXXX-YYY"]:
        check(H.is_record_locator(tok), tok)

    print("\nFS ROUTES — where you looked, not what you found")
    for tok, label in [
        ("fs:tree/person/family/XXXX-YYY", "the family panel (Q200's original four)"),
        ("fs:tree/person/XXXX-YYY", "a profile route"),
        ("fs:record-match", "the record-hints endpoint (Q200 residue)"),
        ("fs:data-problem", "the data-problem endpoint (Q200 residue)"),
        ("fs:search/record/results", "a search route"),
    ]:
        check(not H.is_record_locator(tok), f"{tok:<32} {label}")

    print("\n⚠ LOAD-BEARING CONTROLS — path-shaped locators on OTHER hosts are REAL")
    for tok, label in [
        ("tna:C142/87/65", "TNA piece reference (an inquisition post mortem)"),
        ("tna:C1/548/65", "TNA chancery reference"),
        ("tna:C1/1161/32-33", "TNA chancery, hyphenated range"),
        ("agad:300/872/31-1865", "AGAD fond/album/act"),
        ("anc:6224/31430110", "Ancestry collection/record, slash form"),
        ("anc:61843:1397440010", "Ancestry collection/record, colon form"),
        ("ia:vitalrecordsofsc02newe:p112", "archive.org id + page"),
        ("antenati:ark:/12657/an_ua37834763", "Antenati ark"),
        ("agad:PL_1_300_874_0117.jpg", "AGAD scan filename"),
        ("nycdoris:M-M-1912-0021642", "NYC DORIS certificate id"),
    ]:
        check(H.is_record_locator(tok), f"{tok:<34} {label}")

    print("\nEXISTING BEHAVIOUR — a locator FORM named in prose still counts for nothing")
    for tok in ["fs:1:1:", "fs:", "anc:"]:
        check(not H.is_record_locator(tok), f"{tok!r} is a class name, not a citation")

    print("\nEND TO END — the write-back `evidence` slot")
    check(H.count_records(
        "- **FS write-back QUEUED** (`XXXX-YYY`; merge) — evidence fs:record-match "
        "hints on XXXX-YYY, read 31 JUL 2026 — life_status: deceased") == 0,
        "a route in the evidence slot credits nothing")
    check(H.count_records(
        "- **FS write-back QUEUED** (`XXXX-YYY`; promote birth) — evidence "
        "fs:1:1:AAAA-111 — life_status: deceased") == 1,
        "POSITIVE CONTROL: a real record in the evidence slot still counts")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
