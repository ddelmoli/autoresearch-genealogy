#!/usr/bin/env python3
"""Regression tests for the `BEF` exclusive-bound fix in `vital_years` (session #149).

Runnable with no test framework: `python3 test_bef_exclusive_bound.py` (exit 0 = pass).

THE DEFECT. `is_structural` asks `max(vital_years(...)) < before_year`, meaning "this
person's whole life falls before the year their region's civil registration starts".
`vital_years` returned every 4-digit year verbatim, so a death recorded as
`BEF JAN 1866` yielded **1866** and `1866 < 1866` is False -- a death explicitly
BEFORE January 1866 failed a rule that means "everything before 1866". Off by exactly
one year, in the direction that keeps a structurally-unsourceable person on a worklist
whose route can never reach them.

On the reference vault THREE entries were excluded by this alone -- two written
`BEF JAN 1866` and one `BEF 1866` -- each independently verified to hold ZERO
attachments at the `tf/person/{PID}/entityref` endpoint, with a junk-PID control
returning 404 in the same pass. ⚠ BOTH SPELLINGS MATTER: a fix tested only against
`BEF JAN` would look complete while missing the year-only form, which is how the
third entry was nearly left behind -- it surfaced from the census diff, not from the
grep that found the first two.

EVERY case here carries a POSITIVE CONTROL. A decrement applied to everything would
pass a test that only checked the BEF cases, and would silently shift every ordinary
date by a year -- so the unqualified cases below assert that nothing else moved.
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


print("=== vital_years: BEF is an EXCLUSIVE bound ===")

# --- THE DEFECT ITSELF -------------------------------------------------------
check("BEF JAN 1866 -> 1865 (the reported case)",
      max(H.vital_years("ABT 1800", "BEF JAN 1866")), 1865)
check("BEF 1866 (year only) -> 1865",
      max(H.vital_years("1804", "BEF 1866")), 1865)
check("BEF on `born` is scoped to born, not to the whole record",
      sorted(H.vital_years("BEF 1800", "1850")), [1799, 1850])

# --- POSITIVE CONTROLS: nothing unqualified may move -------------------------
print("\n=== POSITIVE CONTROLS: unqualified dates are UNCHANGED ===")
check("a plain year is untouched",
      H.vital_years("1804", "1866"), (1804, 1866))
check("ABT is not a bound and is untouched",
      H.vital_years("ABT 1800", "ABT 1866"), (1800, 1866))
check("EST is not a bound and is untouched",
      H.vital_years("EST 1803", None), (1803,))
check("BET ... AND ... keeps BOTH years, undecremented",
      sorted(H.vital_years(None, "BET 1816 AND 1823")), [1816, 1823])
check("AFT is DELIBERATELY untouched (known under-statement, see docstring)",
      H.vital_years(None, "AFT 1872"), (1872,))
check("no dates at all -> empty, so a before_year rule cannot fire",
      H.vital_years(None, None), ())

# --- END TO END through is_structural ---------------------------------------
# ⚠ The rules are INJECTED, never read from a vault. A framework test that leans on
# a private vault's `.autoresearch.json` both leaks that vault's regions into a
# public repo and silently changes meaning when the operator edits their config.
print("\n=== is_structural end-to-end (SYNTHETIC rule, before_year 1866) ===")
RULES = [{"label": "test", "region": "Somewhere", "before_year": 1866}]
_saved = H._STRUCTURAL_RULES
H._STRUCTURAL_RULES = RULES
try:
    def structural(years, region="Somewhere", pid="XXXX-XXX", gen=7):
        return H.is_structural(pid, gen, region, years)

    y_bef = H.vital_years("ABT 1800", "BEF JAN 1866")
    check("BEF JAN 1866 IS structural (was False before the fix)",
          structural(y_bef), True)
    check("BEF 1866, year-only form, IS structural",
          structural(H.vital_years("1804", "BEF 1866")), True)

    # POSITIVE CONTROLS: the boundary must still EXCLUDE the registration era.
    check("a plain 1866 death is NOT structural (registration HAS begun)",
          structural(H.vital_years("1799", "1866")), False)
    check("an 1869 death is NOT structural",
          structural(H.vital_years("1819", "1869")), False)
    check("a 1876-1937 life is NOT structural",
          structural(H.vital_years("1876", "1937")), False)

    # THE LOAD-BEARING GUARD: an undated entry is unevidenced, which is a reason to
    # research them and NOT to declare them unresearchable (operator, Q157/Q144).
    check("NO dated vitals -> must NOT be vacuously structural",
          structural(()), False)

    # POSITIVE CONTROL: the fix must not leak across regions.
    check("a BEF-qualified date in an UNMATCHED region is NOT structural",
          structural(y_bef, region="Elsewhere"), False)
finally:
    H._STRUCTURAL_RULES = _saved

print()
if FAILED:
    print(f"FAILED ({len(FAILED)}):")
    for f in FAILED:
        print("  x  " + f)
    sys.exit(1)
print(f"all checks passed")
