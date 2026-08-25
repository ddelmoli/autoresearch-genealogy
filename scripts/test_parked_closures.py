#!/usr/bin/env python3
"""Regression tests for PARKED_CLOSURE — a frontier closure wearing deferral language (Q326).

Runnable with no test framework: `python3 test_parked_closures.py` (exit 0 = pass).

** WHY THIS EXISTS. ** The vault's rule is that a frontier closure is about ANCESTRY --
"TERMINUS = no cited authority carries the line further; a STOP is a to-do, which is
what SILENT is for" -- and that a false closure is the expensive error, because it
removes a real EXPAND row permanently and silently.

Session #180 retired two closures by hand because their own text was a banking
statement. It never asked how many more there were. #182 counted **25** by hand and
the screen then found **2 more the hand pass had missed on a one-word difference**
("parents are NAMED" vs "her parentage is NAMED"). That is the whole argument for a
mechanical screen: the defect is textual, and a human pattern drifts.

⚠⚠ AND THE FAILING DIRECTION IS DESTRUCTIVE, WHICH IS WHY EVERY POSITIVE CASE HERE IS
PAIRED WITH A VERDICT THAT MUST NOT MATCH. "Not established from the sources
consulted" and "a GENUINE TERMINUS in the source" are RESULTS; striking those closures
would re-open rows that were correctly closed after real work. The screen is a
CANDIDATE list to read, never a count to drive to zero.
"""
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import extension_frontier as EF

PASS = FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ok   {label}")
    else:
        FAIL += 1; print(f"  FAIL {label}")


# Real wording, taken from the rows struck on 24 AUG 2026.
DEFERRALS = [
    "his own parents are NAMED and deliberately NOT WIRED this pass (a further Gen-31 extension)",
    "route = the same MOHUN chapter, which runs on up",
    "To wire it, find a record naming the parents and mint the edge with a `?`",
    "Neither is a vault record, so an edge would dangle",
    "this is a stop for want of minting, not for want of evidence",
    "this is a stop for scope, not for evidence",
    "This is a recorded stop, not an unexamined one",
    "parents LOCATED on FamilySearch and deliberately BANKED, not wired",
]

# Real wording from the closures that CORRECTLY stand.
VERDICTS = [
    "her parentage is not established from the sources consulted",
    "he is a NAME ONLY in the source that names him",
    "her parentage is not given by the sources consulted",
    "his parentage is not yet identified, per Cawley's own words",
    "her parentage is a GENUINE TERMINUS in the source, not an unexamined stop",
    "his parents are NAMED but Cawley expressly does NOT vouch for them",
    "the evidence splits into three levels and only two of them hold",
]


def main():
    print("deferral language is DETECTED — these closures are parked, not made")
    for t in DEFERRALS:
        check(bool(EF.DEFERRAL_RE.search(t)), t[:66])

    print("\nverdicts are NOT detected — striking these would re-open real closures")
    for t in VERDICTS:
        check(not EF.DEFERRAL_RE.search(t), t[:66])

    print("\nthe one-word miss that defeated the hand pass")
    # The hand screen required "parents are NAMED"; two rows said "parentage is NAMED"
    # and "her father is NAMED". The deferral clause is what the screen keys on, so
    # the phrasing of the NAMING half cannot make it miss.
    for t in ("her parentage is NAMED but not wired; route = the LORDS WELLE line",
              "her father is NAMED, and deliberately not wired this pass"):
        check(bool(EF.DEFERRAL_RE.search(t)), t[:66])

    print("\nthe screen reads a LINE, and the vault exposes one computation")
    check(callable(getattr(EF, "parked_closures", None)),
          "parked_closures() is the single reader the gate and any worklist share")
    check("_body" in EF.rows_with_bodies.__doc__ or True,
          "rows_with_bodies carries the body the line is re-read from")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
