#!/usr/bin/env python3
"""Regression fixtures for handoff_lint.py.

Runnable with no test framework: `python3 scripts/test_handoff_lint.py`
(exit 0 = pass). Needs no vault — every fixture is inline text.

THE RULE UNDER TEST IS THE ONE MOST LIKELY TO MISFIRE. `BARE_METRIC` bans
hand-copying a banner-computed metric into Handoff prose, BUT it must not fire
when the number IS the finding — "SOURCE_GAP 218 -> 243 is minting, not
regression" is load-bearing, and a lint that deletes it makes the file worse.

This vault has been bitten repeatedly by a check whose first number was an
artefact (meta_presence's first run said 698 and about 11 were real), so the
fixtures below pin BOTH directions: every SHOULD_FLAG line must be caught, and
every SHOULD_PASS line must be left alone. Most of the SHOULD_PASS strings are
real lines lifted from the vault's own Handoff and audit baseline, because the
false positives that matter are the ones this project actually writes.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import handoff_lint as HL

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


def flags(line):
    """Does the bare-metric detector fire on this single line?"""
    return bool(HL.find_bare_metrics([line]))


# ---------------------------------------------------------------------------
# 1. BARE_METRIC must FIRE: a stale-able value copied out of the banner.
# ---------------------------------------------------------------------------
SHOULD_FLAG = [
    "**Canonical 1324, UNCHANGED.**",
    "The live banner reads `SOURCE_GAP 243, LOW_COVERAGE 208, WELL_SOURCED 485`.",
    "Frontier SILENT 298 / DECLARED 239 (44%), UNCHANGED.",
    "PARENT-GEN MISMATCH 14, chronology 2, meta_presence 3 - all known baselines.",
    "**SOURCE_GAP 218 still over its 200 ceiling and still needs re-basing.**",
    "canonical entries | **1,324** |",
    "META_PRESENCE is 3 and ORPHANED_META is 0.",
    "DATE_DRIFT: 0 and blocking.",
]

# ---------------------------------------------------------------------------
# 2. BARE_METRIC must NOT fire: the number IS the finding, or there is no value.
# ---------------------------------------------------------------------------
SHOULD_PASS = [
    # (a) TRANSITION — the movement is the whole claim
    "**THE +25 ON SOURCE_GAP IS MINTING: SOURCE_GAP 218 -> 243, and it is arithmetic.**",
    "canonical 1,277 -> 1,324 is +47",
    "Frontier SILENT 319 -> 309, DECLARED 212 -> 218 (41%).",
    "The census moved SOURCE_GAP 218 to 243 while LOW_COVERAGE did not move at all.",
    # (b) CONTRAST — a correction, where both values carry the point
    "**SOURCE_GAP is 243, not 218.** The 218 predates the last re-base.",
    "SILENT 309 vs 319 a week earlier.",
    # (c) the metric named with NO value — the normal, wanted way to write it
    "Do not hand-copy SOURCE_GAP, canonical or DECLARED into this file.",
    "GATES: at baseline (see the SessionStart banner).",
    "SOURCE_GAP entries are the canonical Recipe-S priority list.",
    # (d) numbers that are not metrics at all — the commonest false-positive shape
    "The GGG search silently caps at exactly 500 rows.",
    "Petition #45503 (1925) is the only John Example petition in the district.",
    "Interment #39613, Gate 615/S, Block 32, Row 006L, Grave 6.",
    "An n=5 null result was turned into a permanent exclusion of 705 entries.",
    "the query returned exactly 100 rows against `count=100`, i.e. TRUNCATED",
    # (e) explicit escape hatch for a load-bearing number the heuristics miss
    "WELL_SOURCED 485 is the number the operator asked me to quote here. [finding]",
]


def test_bare_metric():
    print("BARE_METRIC — must FIRE (a hand-copied banner value):")
    for ln in SHOULD_FLAG:
        check(flags(ln), ln[:88])
    print("\nBARE_METRIC — must NOT fire (the number IS the finding, or is not a metric):")
    for ln in SHOULD_PASS:
        check(not flags(ln), ln[:88])


# ---------------------------------------------------------------------------
# 3. Negative control. A fixture that cannot be made to fail proves nothing:
#    break the exemption logic and the SHOULD_PASS set must start failing.
# ---------------------------------------------------------------------------
def test_negative_control():
    print("\nnegative control (disable the exemptions; SHOULD_PASS must break):")
    saved = (HL._TRANSITION_AFTER, HL._CONTRAST_AFTER,
             HL._TRANSITION_BEFORE, HL._CONTRAST_BEFORE, HL.FINDING_MARK_RE)
    import re
    never = re.compile(r"(?!x)x")
    HL._TRANSITION_AFTER = HL._CONTRAST_AFTER = never
    HL._TRANSITION_BEFORE = HL._CONTRAST_BEFORE = HL.FINDING_MARK_RE = never
    try:
        broken = [ln for ln in SHOULD_PASS if flags(ln)]
        check(len(broken) >= 6,
              f"exemptions are load-bearing: {len(broken)} SHOULD_PASS lines flag without them")
    finally:
        (HL._TRANSITION_AFTER, HL._CONTRAST_AFTER,
         HL._TRANSITION_BEFORE, HL._CONTRAST_BEFORE, HL.FINDING_MARK_RE) = saved
    check(not any(flags(ln) for ln in SHOULD_PASS), "and restoring them makes them pass again")


# ---------------------------------------------------------------------------
# 4. Structure: required fields, the line cap, one live close, fenced code.
# ---------------------------------------------------------------------------
GOOD_CLOSE = """# Session Handoff

## SESSION #109 CLOSE (28 JUL 2026) -> full narrative in logs/slug.md

**GATES:** at baseline.
**WHAT MOVED:** 0 minted, 4 FS PIDs adopted.

### FINDINGS
- one sentence.

### RETRACTIONS
1. none.

### NEGATIVES / DO-NOT-REDO
- NYC deaths 1925-1932 are closed exhaustively.

### NEW TRAPS
- GGG caps at 500 rows.

### OPEN / NEXT
1. Order the petition.

### OPERATOR QUEUE DELTA
- ADDED: one order.

## Quick-resume commands

```bash
python3 scripts/harvest_sources.py   # SOURCE_GAP 243 / coverage
```
"""


def test_structure():
    print("\nstructure:")
    f = HL.lint_text(GOOD_CLOSE)
    check(f["missing_fields"] == [], "a conforming close block has every required field")
    check(f["missing_recommended"] == [], "and both recommended fields")
    check(not f["too_long"], "and is under the line cap")
    check(len(f["close_headings"]) == 1, "exactly one live close block")
    check(f["bare_metrics"] == [],
          "a metric inside a ``` fence is NOT flagged (command examples are not prose)")
    check(HL.total(f) == 0, "so the conforming fixture scores zero violations")

    missing = GOOD_CLOSE.replace("### RETRACTIONS\n1. none.\n\n", "")
    fm = HL.lint_text(missing)
    check("RETRACTIONS" in fm["missing_fields"],
          "dropping RETRACTIONS is caught — it is required even when it says 'none'")

    missing2 = GOOD_CLOSE.replace("### NEGATIVES / DO-NOT-REDO\n"
                                  "- NYC deaths 1925-1932 are closed exhaustively.\n\n", "")
    check("NEGATIVES / DO-NOT-REDO" in HL.lint_text(missing2)["missing_fields"],
          "dropping NEGATIVES / DO-NOT-REDO is caught")

    prose = GOOD_CLOSE.replace("### FINDINGS\n- one sentence.",
                               "### FINDINGS\n- The findings of this session were many.")
    check(HL.lint_text(prose)["missing_fields"] == [],
          "the word 'findings' mid-sentence neither satisfies nor breaks the field check")

    fat = GOOD_CLOSE.replace("### FINDINGS\n- one sentence.",
                             "### FINDINGS\n" + "- narrative line.\n" * 130)
    check(HL.lint_text(fat)["too_long"], "a 130-line narrative dump trips CLOSE_TOO_LONG")

    two = GOOD_CLOSE + "\n## STATE AT THE #108 CLOSE (28 JUL 2026) - SUPERSEDED\n\nold text.\n"
    f2 = HL.lint_text(two)
    check(len(f2["close_headings"]) == 2, "a superseded close left live is detected")
    check(HL.total(f2) >= 1, "and it counts as a violation")
    check(f2["close_len"] == HL.lint_text(GOOD_CLOSE)["close_len"],
          "the length measured is the FIRST (live) close, not the file")


def main():
    test_bare_metric()
    test_negative_control()
    test_structure()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
