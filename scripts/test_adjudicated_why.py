#!/usr/bin/env python3
"""Regression tests for `adjudicated_why` as a multi-valued key (deferred 50).

Runnable with no test framework: `python3 test_adjudicated_why.py` (exit 0 = pass).

WHY THE KEY GREW A LIST FORM. `no-second-parent` (operator-directed 04 AUG 2026)
had to share `adjudicated_why` with the four EDGE reasons that shipped with
deferred 38 — and on the reference vault **14 of the 109 half-wired rows already
carried one** (`fs-gap`, `hedge`, `contradicted`) with a real `adjudicated` list
beside it. A scalar cannot hold both, and overwriting an `fs-gap` would silently
switch off that row's re-check in `session_plan.lane_defects`.

⚠⚠ THE TRAP THIS FILE EXISTS TO PIN. The natural way to write two reasons is
`adjudicated_why: fs-gap, no-second-parent` — which is INVALID, because the meta
block is a YAML flow-mapping and a comma'd value must be single-quoted. And the
reader that consumed this key was `adjudicated_why:\\s*([a-z\\-]+)`, which does not
match a leading quote AT ALL: the row would parse as having NO reason, silently
disabling the fs-gap re-check while the entry advertised it. Same shape as the
`P-XXXXXX?!` suffix that `adjudicated` was designed to avoid.

Every case that accepts something is paired with one that must be rejected.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import person_store as PS

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


def meta(**kv):
    inner = ", ".join(f"{k}: {v}" for k, v in kv.items())
    return "- meta: {id: P-AAAAAA, generation: 9, " + inner + "}"


def main():
    print("the LEGACY bare scalar keeps working — 46 live rows use it")
    for val in ("fs-gap", "hedge", "contradicted", "privacy"):
        check(PS.adjudicated_why_values(meta(adjudicated_why=val)) == [val],
              f"bare `{val}` reads as [{val}]")

    print("\nthe NEW reason")
    check(PS.adjudicated_why_values(meta(adjudicated_why="no-second-parent"))
          == ["no-second-parent"], "bare `no-second-parent` reads")

    print("\nTHE COLLISION CASE — 14 real rows need two reasons at once")
    two = meta(adjudicated="'[P-BBBBBB]'", adjudicated_why="'[fs-gap, no-second-parent]'")
    vals = PS.adjudicated_why_values(two)
    check(vals == ["fs-gap", "no-second-parent"], "quoted list reads BOTH, in order")
    check("fs-gap" in vals, "...so the fs-gap RE-CHECK still fires for this row")
    check("no-second-parent" in vals, "...and the row counts as DECLARED half-wired")

    print("\nNEGATIVE CONTROL — the superseded regex would have silently lost it")
    import re
    old = re.compile(r"adjudicated_why:\s*([a-z\-]+)")
    m = old.search(two)
    check(m is None or m.group(1) not in ("fs-gap",),
          "the old `[a-z-]+` pattern does NOT recover fs-gap from the quoted form")
    check(PS.adjudicated_why_values(two)[0] == "fs-gap",
          "positive control — the new reader DOES recover it")

    print("\nunknown tokens are dropped, so a typo cannot invent a reason")
    check(PS.adjudicated_why_values(meta(adjudicated_why="fs_gap")) == [],
          "underscore typo `fs_gap` yields no reason (not a silent new value)")
    check(PS.adjudicated_why_values(meta(adjudicated_why="'[fs-gap, nonsense]'"))
          == ["fs-gap"], "a bad token is dropped, the good one survives")

    print("\nabsence and malformed input")
    check(PS.adjudicated_why_values(meta(fs="AAAA-111")) == [], "key absent -> []")
    check(PS.adjudicated_why_values("") == [], "empty string -> []")
    check(PS.adjudicated_why_values("not a meta line") == [], "non-meta line -> []")
    check(PS.adjudicated_why_values(None) == [], "None -> []")

    print("\nthe key stands ALONE — an absent parent has no far-end id to adjudicate")
    solo = meta(adjudicated_why="no-second-parent")
    check(PS.adjudicated_why_values(solo) == ["no-second-parent"],
          "`no-second-parent` with NO `adjudicated` list is valid")
    # and that must not look like an unexplained adjudication
    import gen_person_index as G
    check(not G.parse_meta(solo).get("adjudicated"),
          "...and carries no `adjudicated`, so ADJUDICATED_STALE cannot fire on it")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
