#!/usr/bin/env python3
"""deferred 56 option 2: `fs_absent: <date>` — a DATED "no FS profile exists".

Runnable with no test framework: `python3 scripts/test_fs_absent.py`.

THE DEFECT. `fs: none` means "searched FamilySearch, confirmed absent" and it cannot
carry a date. The EXISTENCE_PROBE arm treats an undated negative as expired on sight,
so all 13 such rows returned every cycle for ever. One entry had the diagnosis written
on it by a session that could not fix it, because the grammar had nowhere to put a date.

⚠⚠ THIS FILE EXISTS MOSTLY TO KEEP THREE NEAR-IDENTICAL KEYS APART. They are easy to
conflate and the vault has already paid for one overloaded marker (the `?` edge):

    route       WHERE the evidence is.       RETIRES, permanently, in 2 ROTATE arms.
    fs_probed   Sources READ, no records.    SUPPRESSES in IMPROVE (58). Retires
                                             nothing in ROTATE (Q157).
    fs_absent   NO PROFILE EXISTS.           Feeds the EXISTENCE_PROBE COOLDOWN (56).
                                             Does NOT suppress in IMPROVE.

Every one of those distinctions is asserted below, in both directions, because the
"obvious cleanup" is to make them behave alike and that would be wrong three times.
"""
import datetime
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import person_store as PS
import profile_review as PR

PASS = 0
FAIL = 0
TODAY = datetime.date(2026, 8, 8)


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def main():
    print("the reader: a well-formed ISO date, and nothing else")
    check(PS.fs_absent("- meta: {id: P-AAA111, fs: none, fs_absent: 2026-08-08}")
          == "2026-08-08", "reads a valid date")
    check(PS.fs_absent("- meta: {id: P-AAA111, fs: none}") is None,
          "absent key -> None")
    check(PS.fs_absent("- meta: {id: P-AAA111, fs: none, fs_absent: soon}") is None,
          "NEGATIVE CONTROL: a malformed date is REJECTED, not passed through")

    print()
    print("the cooldown: an UNDATED negative is still expired on sight")
    due, days, why = PR.probe_status({}, "fs", TODAY, record_date=None)
    check(due is True and days is None, f"no date anywhere -> due ({why[:44]})")

    print()
    print("a fresh `fs_absent` on the RECORD cools the row, with no state-file entry")
    due, days, why = PR.probe_status({}, "fs", TODAY, record_date="2026-08-01")
    check(due is False and days == 7, f"7 days ago -> not due (got days={days})")
    check("on the record" in why, f"and the reason names the SOURCE of the date: {why[:60]}")

    print()
    print("...but it EXPIRES. It is cooldown-shaped, not retirement-shaped, so a")
    print("profile created later is still found.")
    due, days, why = PR.probe_status({}, "fs", TODAY, record_date="2020-01-01")
    check(due is True, f"an ancient fs_absent is due again (days={days})")

    print()
    print("the MORE RECENT of record vs rotation-state wins, in BOTH directions")
    due, _d, why = PR.probe_status({"last_probed_fs": "2019-01-01"}, "fs", TODAY,
                                   record_date="2026-08-01")
    check(due is False and "on the record" in why,
          "record newer than state -> record wins, and is named")
    due, _d, why = PR.probe_status({"last_probed_fs": "2026-08-01"}, "fs", TODAY,
                                   record_date="2019-01-01")
    check(due is False and "rotation state" in why,
          "state newer than record -> state wins, and is named")

    print()
    print("⚠ KEEPING THE THREE KEYS APART — each assertion is a thing NOT to unify")
    check("fs_probed" not in str(PR.ROUTE_RETIRING_ARMS)
          and "fs_absent" not in str(PR.ROUTE_RETIRING_ARMS),
          "neither dated key retires an arm; only `route` does")
    # fs_absent must not be mistaken for fs_probed by the readers themselves
    line = "- meta: {id: P-AAA111, fs: none, fs_absent: 2026-08-08}"
    check(PS.fs_probed(line) is None,
          "NEGATIVE CONTROL: `fs_absent` does NOT read as `fs_probed`")
    line2 = "- meta: {id: P-AAA111, fs: XXXX-YYY, fs_probed: 2026-08-08}"
    check(PS.fs_absent(line2) is None,
          "NEGATIVE CONTROL: `fs_probed` does NOT read as `fs_absent`")
    both = "- meta: {id: P-AAA111, fs: none, fs_probed: 2026-08-07, fs_absent: 2026-08-08}"
    check(PS.fs_probed(both) == "2026-08-07" and PS.fs_absent(both) == "2026-08-08",
          "a row may carry BOTH, independently — they answer different questions")

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
