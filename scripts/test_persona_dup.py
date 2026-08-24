#!/usr/bin/env python3
"""Pin persona_dup_audit.py — the screen for one RECORD cited under two personas.

FamilySearch mints one persona per named party, so a marriage indexed for bride
and groom arrives as two ARKs of ONE record. The census counts one record per
Sources sub-bullet, so two sub-bullets = one phantom credit. Proven on a live
entry (24 AUG 2026; that vault's own log names it, this repo does not): FS's own
*Cite This Record* on the bride's persona page gives the GROOM's ark as the record
URL. Merging the two moved that entry from WELL_SOURCED/10 to WELL_SOURCED/9.

WHAT THIS FILE DEFENDS, and each assertion is here because getting it wrong was
either measured or nearly shipped:

  * ⚠⚠ THE TIER SPLIT. A repeat with an EVENT DATE is a duplicate candidate; a
    repeat with only a COLLECTION name is a NAMING defect and almost certainly
    several DIFFERENT records. The first cut of the script reported them together
    and its largest "duplicate" — twelve sub-bullets under one label — was
    entirely the second kind. Reporting that as an over-credit would have been a
    false claim about twelve real records. The collection's OWN year range must be
    stripped before testing for a date, or every collection name looks dated.
  * ⚠⚠ THE ORDERING. Negation is resolved over the WHOLE entry BEFORE the body is
    narrowed to the Sources bullet, because the `~` almost never lives inside that
    bullet — it is written where the rejection is explained. Narrowing first
    discards the negation and keeps the token; that exact inversion re-credited 27
    records across 10 entries in session #159.
  * ⚠⚠ THE CONTROLS AND THE DENOMINATOR. A throwaway version of this screen
    returned a clean 0 across the whole vault because it read a field the person
    records do not expose: every entry scored empty, and nothing errored. So the
    script runs two controls FIRST and REFUSES TO RUN if either misbehaves, and it
    always prints how many sub-bullets it actually examined. `test_refuses_when_
    blind` is the pin: a detector that cannot be seen failing reports zeros forever.

⚠ ALL FIXTURES BELOW ARE SYNTHETIC. This file is in the PUBLIC framework repo,
which carries zero real family names (CONTRIBUTING.md, "the framework/private
boundary"); the strings mirror the SHAPE of the measured entries, not the people.
"""
import io
import os
import sys
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona_dup_audit as PD

# One event, two personas, described by DATE + collection — the measured shape.
DATED_DUP = """
- **Sources**
  - 1911 Placeholt Marriage Records 1637-1947 — fs:1:1:AAAA-AAA
  - 1911 Placeholt Marriage Records 1637-1947 — fs:1:1:BBBB-BBB
"""

# Same descriptor, but it names only the COLLECTION — no event date survives once
# the collection's own range is stripped. Probably several DIFFERENT records.
UNNAMED_REPEAT = """
- **Sources**
  - Testland State Vital Records, 1638-1927 — fs:1:1:AAAA-AAA
  - Testland State Vital Records, 1638-1927 — fs:1:1:BBBB-BBB
  - Testland State Vital Records, 1638-1927 — fs:1:1:CCCC-CCC
"""

# Two genuinely different records: different descriptors, nothing to say.
DISTINCT = """
- **Sources**
  - 4 October 1889 Testland Births and Christenings 1639-1915 — fs:1:1:AAAA-AAA
  - 1 September 1919 Testland State Vital Records 1638-1927 — fs:1:1:BBBB-BBB
"""

# A repeat whose locators are ALL negated: off the metric, so nothing is credited
# twice and there is nothing to report.
ALL_NEGATED = """
- **Sources**
  - Find a Grave Index entry — NOT COUNTED, policy (e) — ~fs:1:1:AAAA-AAA
  - Find a Grave Index entry — NOT COUNTED, policy (e) — ~fs:1:1:BBBB-BBB
"""

# THE ORDERING PIN: the duplicate is real, but both spellings are negated in a
# write-back bullet OUTSIDE the Sources bullet — which is where a `~` normally
# lives. Narrowing before resolving negation would flag this.
NEGATED_ELSEWHERE = """
- **Sources**
  - 6 January 1859 Testland Deeds 1626-2001 — fs:1:1:AAAA-AAA
  - 6 January 1859 Testland Deeds 1626-2001 — fs:1:1:BBBB-BBB
- **FS write-back QUEUED 01 JAN 2026** (detach): both refuted — ~fs:1:1:AAAA-AAA, ~fs:1:1:BBBB-BBB
"""

# A descriptor legitimately containing an em-dash: the split must take the LAST
# one, or the descriptor is truncated and two different records collide.
EMDASH_IN_DESCRIPTOR = """
- **Sources**
  - 1847 birth atto — Placeholt register — fs:1:1:AAAA-AAA
  - 1852 death atto — Placeholt register — fs:1:1:BBBB-BBB
"""


def _kinds(body):
    groups, examined = PD.groups_for_body(body)
    return {desc: kind for desc, _locs, _n, kind in groups}, examined


def test_tiers():
    bad = []
    kinds, seen = _kinds(DATED_DUP)
    if not any(k == "DUP" for k in kinds.values()):
        bad.append("a DATED repeat must be tiered DUP")
    if seen != 2:
        bad.append(f"DATED_DUP: expected 2 sub-bullets examined, saw {seen}")

    kinds, _ = _kinds(UNNAMED_REPEAT)
    if not kinds:
        bad.append("a collection-only repeat must still be REPORTED")
    if any(k == "DUP" for k in kinds.values()):
        bad.append("a collection-only repeat must NOT be tiered DUP — the "
                   "collection's own year range is not an event date")
    if not any(k == "UNNAMED" for k in kinds.values()):
        bad.append("a collection-only repeat must be tiered UNNAMED")

    for name, body in (("DISTINCT", DISTINCT), ("ALL_NEGATED", ALL_NEGATED),
                       ("NEGATED_ELSEWHERE", NEGATED_ELSEWHERE),
                       ("EMDASH_IN_DESCRIPTOR", EMDASH_IN_DESCRIPTOR)):
        kinds, _ = _kinds(body)
        if kinds:
            bad.append(f"{name} must stay quiet, got {kinds!r}")

    # the denominator: a body with no credited sub-bullet examines nothing
    _, seen = _kinds(ALL_NEGATED)
    if seen != 0:
        bad.append(f"ALL_NEGATED must examine 0 credited sub-bullets, saw {seen}")
    return bad


def test_event_dated():
    """The date test, directly — collection ranges must not read as event dates."""
    bad = []
    for desc, want in (
            ("1911 placeholt marriage records 1637-1947", True),
            ("6 january 1859 testland state vital records 1638-1927", True),
            ("testland state vital records, 1638-1927", False),
            ("familysearch indexed record (testland vital, census or military)", False),
            ("social security numerical identification files (numident), 1936-2007", False),
            ("stato civile (archivio di stato), 1809-1944", False)):
        got = PD.is_event_dated(desc)
        if got != want:
            bad.append(f"is_event_dated({desc!r}) = {got}, want {want}")
    return bad


def test_refuses_when_blind():
    """If the detector stops detecting, the run must ABORT — not report zero."""
    bad = []
    if PD.self_check():
        bad.append("self_check failed on the shipped code")
    real = PD.groups_for_body
    try:
        PD.groups_for_body = lambda body: ([], 0)      # a detector that sees nothing
        if not PD.self_check():
            bad.append("self_check PASSED a blind detector — the controls are inert")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = PD.main_for_test()
        if rc != 2 or "REFUSING TO RUN" not in buf.getvalue():
            bad.append("a blind detector must make the run refuse with rc=2")
    finally:
        PD.groups_for_body = real
    return bad


def main():
    bad = test_tiers() + test_event_dated() + test_refuses_when_blind()
    if bad:
        print("PERSONA_DUP test FAILED:")
        for b in bad:
            print("   ", b)
        return 1
    print("PERSONA_DUP test ok (tier split dated vs collection-only, 4 negative "
          "controls incl. the body-wide-negation ordering pin, the em-dash split, "
          "the denominator, and a blind detector refuses to run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
