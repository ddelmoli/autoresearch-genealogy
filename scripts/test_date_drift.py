#!/usr/bin/env python3
"""test_date_drift.py — the Spec 06 header/meta sync gate.

Runnable with no test framework: `python3 test_date_drift.py` (exit 0 = pass).

DATE_DRIFT exists because this lane created TWO stores for one fact. Before it, a
person's dates lived only in the header parenthetical; now the `- meta:` field is
authoritative for machines and the header remains the human display. That is
exactly the drift integrity rule 7 polices, so it is gated rather than trusted.

The rule under test: compare YEARS, not strings. `3 SEP 1780` and
`b. 3 SEP 1780, Boston` agree. `ABT 1750` and `~1750` agree. Only both-present-and-
different is drift; one side absent is COVERAGE, which is a migration or display
gap, not a contradiction.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prose_audit as PA

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


def row(name, field_born=None, header_born=None, field_died=None, header_died=None):
    keys = tuple(k for k, v in (("born", field_born), ("died", field_died)) if v)
    return {"name": name, "file": "Family_Tree_Fixture.md", "meta_date_keys": keys,
            "field_born": field_born, "header_born": header_born or "",
            "field_died": field_died, "header_died": header_died or ""}


CASES = [
    # (row, should_be_reported, label)
    (row("Drifting Died", field_died="1675", header_died="d. 1671"), True,
     "header d.1671 vs field 1675 -> REPORTED"),
    (row("Exact With Place", field_born="3 SEP 1780", header_born="3 SEP 1780, Boston"), False,
     "'3 SEP 1780' vs 'b. 3 SEP 1780, Boston' -> not drift (same year, place ignored)"),
    (row("Approximate", field_born="ABT 1750", header_born="~1750"), False,
     "'ABT 1750' vs '~1750' -> not drift (years compared, not strings)"),
    (row("Range Vs Year", field_born="BET 1625 AND 1627", header_born="~1625-1627, Plymouth"), False,
     "'BET 1625 AND 1627' vs '~1625-1627, Plymouth' -> not drift"),
    (row("Medieval", field_born="ABT 1068", header_born="~1068"), False,
     "medieval years compare correctly (no 1500 floor anywhere in this path)"),
    (row("Dual Year", field_born="6 JAN 1744", header_born="6 JAN 1743/4, Somewhereton"), False,
     "an OS/NS dual header reads EITHER year, so the NS field is not drift"),
    (row("Field Only", field_born="1780"), False,
     "field present, header absent -> coverage, not drift"),
    (row("Header Only", header_born="b. 1780"), False,
     "header present, field absent -> coverage, not drift"),
    (row("Neither"), False, "neither present -> coverage, not drift"),
]

for r, want_reported, label in CASES:
    found = PA.date_drift([r])
    got = bool(found)
    check(got == want_reported, label + ("" if got == want_reported else f"  (got {found})"))

# Every finding is advisory (WARN) and names the metric, so the summary can count it.
found = PA.date_drift([CASES[0][0]])
check(found and found[0][2] == "WARN" and found[0][3] == "DATE_DRIFT",
      "a finding is WARN/DATE_DRIFT (advisory — exit 0 at first landing)")
check(found and "1675" in found[0][4] and "1671" in found[0][4],
      "the message reports BOTH years so the disagreement is actionable")

# Coverage is counted separately from drift, and the three cases are distinct.
PA.date_drift([row("A", field_born="1780"), row("B", header_born="b. 1780"), row("C")])
cov = PA.DATE_DRIFT_COVERAGE
check(cov["header_missing"] == 1, f"coverage: header_missing counted (got {cov['header_missing']})")
check(cov["field_missing"] == 1, f"coverage: field_missing counted (got {cov['field_missing']})")
# 3 rows x 2 slots = 6 checks; 1 field-only, 1 header-only, 4 with neither.
check(cov["both_missing"] == 4, f"coverage: both_missing counted (got {cov['both_missing']})")

# The field-vs-header question must be asked of the META BLOCK, not of the
# fallback: person_store's `born` falls back to the header, so a row whose meta
# carries no date key must count as field-missing even though field_born is set.
PA.date_drift([{"name": "Unmigrated", "file": "f.md", "meta_date_keys": (),
                "field_born": "1969, Somewhereton, MA", "header_born": "1969, Somewhereton, MA",
                "field_died": None, "header_died": ""}])
check(PA.DATE_DRIFT_COVERAGE["field_missing"] == 1,
      "an unmigrated entry counts as field-missing, not as a silent zero")

print(f"\n{PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
