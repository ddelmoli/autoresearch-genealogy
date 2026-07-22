#!/usr/bin/env python3
"""test_privacy_dates.py — regression tests for the narrative-model living-person
date gate (spec/structured-dates Spec 01), the Python twin of test_privacy_gate.rb.

Runnable with no test framework: `python3 test_privacy_dates.py` (exit 0 = pass).

WHY THIS EXISTS. Adopting GEDCOM 7 `DateValue` for born/died makes `3 SEP 1780` a
legal stored value. On the Ruby side that silently disarmed `exact_date?` (ISO
only). This side already matched the day-month-year form, so the test's job is to
PIN that behaviour down before Spec 03 starts writing dates in the new grammar —
an untested coincidence is not a guarantee — and to cover the `*_phrase` escape
hatch, which is new free-text surface arriving with Spec 03.

Three layers:
  1. the predicate (`has_exact_date`) over the Spec 01 case table;
  2. end to end through `check()` on a narrative fixture vault (today's path:
     vitals parsed from the header parenthetical);
  3. the `*_phrase` fields, screened via getattr so this holds both before and
     after Spec 03 adds them to PersonRecord.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config
import person_store as ps
import check_narrative_privacy as cnp

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


# (value, is_day_precise) — the Spec 01 acceptance table.
PREDICATE_CASES = [
    ("3 SEP 1780", True),            # GEDCOM 7 date
    ("JULIAN 30 JAN 1649", True),    # GEDCOM 7 with calendar escape
    ("1780-09-03", True),            # ISO (unchanged behaviour)
    ("3 September 1780", True),      # PHRASE free text
    ("Sep 3, 1780", True),           # US prose
    ("ABT 1780", False),             # approximate — permitted for the living
    ("EST 1780", False),
    ("BEF 1780", False),
    ("AFT 1780", False),
    ("BET 1779 AND 1781", False),    # year-only range — permitted
    ("1780", False),                 # bare year — permitted
    ("SEP 1780", False),             # month precision, no day — permitted
    ("", False),
    (None, False),
]

NARRATIVE = """---
type: family_tree
---

### Generation 1: Fixture

**Living Gedcom Day** (b. 3 SEP 1780)
- meta: {id: P-LIVE01, profile_status: partial, life_status: living, generation: 1}

**Living Julian Day** (b. JULIAN 30 JAN 1649)
- meta: {id: P-LIVE02, profile_status: partial, life_status: living, generation: 1}

**Living Approx Year** (b. ABT 1780)
- meta: {id: P-LIVE03, profile_status: partial, life_status: living, generation: 1}

**Living Bare Year** (b. 1780)
- meta: {id: P-LIVE04, profile_status: partial, life_status: living, generation: 1}

**Living Year Range** (b. 1779; d. BET 1779 AND 1781)
- meta: {id: P-LIVE05, profile_status: partial, life_status: living, generation: 1}

**Unknown Gedcom Day** (b. 3 SEP 1780)
- meta: {id: P-UNKN01, profile_status: stub, life_status: unknown, generation: 1}

**Deceased Gedcom Day** (b. 3 SEP 1780; d. 12 NOV 1901)
- meta: {id: P-DECD01, profile_status: complete, life_status: deceased, generation: 1}

**Living Meta Field Day** (b. about 1780)
- meta: {id: P-LIVE06, profile_status: partial, life_status: living, generation: 1, born: '3 SEP 1780'}

**Living Meta Phrase Day** (b. about 1780)
- meta: {id: P-LIVE07, profile_status: partial, life_status: living, generation: 1, born_phrase: '3 September 1780'}

**Living Meta Approx** (b. about 1780)
- meta: {id: P-LIVE08, profile_status: partial, life_status: living, generation: 1, born: 'ABT 1780'}
"""

# P-LIVE06/07 are the Spec 03 end-to-end proof: the day-precise value is in the
# META FIELD, not the header, which is the surface Spec 01 was hardened for.
BLOCKED = {"P-LIVE01", "P-LIVE02", "P-UNKN01", "P-LIVE06", "P-LIVE07"}
PERMITTED = {"P-LIVE03", "P-LIVE04", "P-LIVE05", "P-DECD01", "P-LIVE08"}


def make_vault(text=NARRATIVE, name="Family_Tree_Fixture.md"):
    d = tempfile.mkdtemp(prefix="privacy-dates-")
    with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(d, name), "w") as fh:
        fh.write(text)
    vault_config.load_config.cache_clear()
    return d


def main():
    # ---- 1. the predicate ------------------------------------------------- #
    for value, expected in PREDICATE_CASES:
        got = cnp.has_exact_date(value)
        check(got == expected,
              f"has_exact_date({value!r}) -> {expected}" + ("" if got == expected else f" (got {got})"))

    # ---- 2. end to end through check() ------------------------------------ #
    v = make_vault()
    try:
        violations = cnp.check(v)
        flagged = {pid for pid in BLOCKED | PERMITTED
                   if any(f" {pid} is " in m for m in violations)}
        for pid in sorted(BLOCKED):
            check(pid in flagged, f"{pid}: day-precise date for living/unknown BLOCKED")
        for pid in sorted(PERMITTED):
            check(pid not in flagged, f"{pid}: permitted (approximate, or deceased)")
        check(not any("no life_status" in m or "no generation" in m for m in violations),
              "fixture is structurally clean (no non-date findings)")
        # Messages must never echo the offending value.
        check(not any("1780" in m or "1649" in m for m in violations),
              "violation messages never echo the date value")
    finally:
        shutil.rmtree(v)

    # ---- 3. the Spec 03 *_phrase escape hatch ----------------------------- #
    # PersonRecord may not carry these fields yet; the gate must screen them the
    # moment it does, and must not crash while it does not.
    rec = ps.PersonRecord(id="P-PHRS01", name="Phrase Fixture", life_status="living")
    fields = {f for f in ("born_phrase", "died_phrase") if hasattr(rec, f)}
    check({"born_phrase", "died_phrase"} <= {a for a, _ in cnp._PRIVATE_DATE_ATTRS},
          "born_phrase/died_phrase are in the screened attribute set")
    if fields:
        for f in sorted(fields):
            setattr(rec, f, "3 September 1780")
            check(cnp.has_exact_date(getattr(rec, f)),
                  f"{f}: free-text exact date is day-precise")
            setattr(rec, f, None)
    else:
        check(True, "phrase fields not on PersonRecord yet (Spec 03) — screened defensively")

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
