#!/usr/bin/env python3
"""test_session_plan_supersede.py — pins `session_plan.py --record --supersede`.

** WHY THIS EXISTS (21 SEP 2026). ** `session_plan.py --record` appends one observation
to `history` and increments `arms[lane]`, and there was no way to CORRECT one. A ROTATE
observation recorded `miss` on the wrong unit had to be fixed by hand-editing the state
file. `question_drain.py` and `profile_review.py` had already solved this (9305b91): a
wrong row is never deleted, it is marked `superseded: true`, the correction is appended,
and every reader counts live rows only. This mirrors that design.

What is pinned:
  1. the prior row is KEPT and marked superseded; the correction is appended;
  2. the arm is rolled back (a miss corrected to a hit moves wins by one, iterations not at all);
  3. every reader excludes superseded rows: the floors (`since_epoch`), the heartbeat,
     `last_improve_split`;
  4. the correction inherits the original's date and sitting (epoch membership unchanged);
  5. an original outside the current epoch leaves the (reset) arm untouched;
  6. `pending` is NOT consumed by a correction;
  7. --supersede with nothing to correct, or without --session, is refused;
  8. ⚠ the NORMAL case still works: several plain records of one lane in one sitting are
     separate observations and are NOT refused (unlike the other two stores, whose key is
     unique per sitting).
"""
from __future__ import annotations

import copy
import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import session_plan as sp  # noqa: E402

FAILS: list[str] = []


def check(cond, label):
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


def refused(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


def base():
    return {"arms": {"EXPAND": {"wins": 1, "iterations": 4}}, "history": [], "pending": None}


def test_correction_and_rollback():
    print("supersede: row kept, correction appended, arm rolled back")
    st = base()
    sp.record(st, "EXPAND", "miss", "first", session=900, today="2026-01-10")
    arm_before = dict(sp.arm_of(st, "EXPAND"))
    sp.record(st, "EXPAND", "hit", "fixed", session=900, today="2026-01-11", supersede=True)
    h = st["history"]
    check(len(h) == 2, "the wrong row is kept (append-only), not deleted")
    check(h[0].get("superseded") is True and h[0]["outcome"] == "miss",
          "the original is marked superseded")
    check(h[1]["outcome"] == "hit" and h[1]["corrects"] == "miss",
          "the correction is appended and names what it corrects")
    check(h[1]["date"] == "2026-01-10" and h[1]["corrected_on"] == "2026-01-11",
          "the correction keeps the ORIGINAL date (same observation), dated corrected_on")
    a = sp.arm_of(st, "EXPAND")
    check(a["iterations"] == arm_before["iterations"], "iterations unchanged by a correction")
    check(a["wins"] == arm_before["wins"] + 1, "wins moved by exactly one (miss -> hit)")
    live = sp.live_rows(h)
    check(len(live) == 1 and live[0]["outcome"] == "hit", "live_rows sees the correction only")
    check(len(sp.since_epoch(st)) == 1, "the floors (since_epoch) count the observation ONCE")


def test_readers_exclude_superseded():
    print("supersede: heartbeat and last_improve_split read live rows")
    st = base()
    sp.record(st, "IMPROVE", "hit", "", session=901, today="2026-01-10",
              sourced=3, corroborated=1, verified=0)
    sp.record(st, "IMPROVE", "miss", "", session=901, today="2026-01-10", supersede=True)
    sp_ = sp.last_improve_split(st)
    check(sp_ is None, "a split carried only by a superseded row is not reported")
    buf = io.StringIO()
    with redirect_stdout(buf):
        sp.heartbeat(st)
    check("miss" in buf.getvalue() and "hit" not in buf.getvalue(),
          "heartbeat reports the live (corrected) outcome")


def test_outside_epoch_leaves_arm():
    print("supersede: an original outside the current epoch does not touch the reset arm")
    st = base()
    sp.record(st, "EXPAND", "hit", "", session=902, today="2026-01-10")
    sp.set_lane_epoch(st, "EXPAND", 902, "redefined", today="2026-01-12")
    zeroed = dict(sp.arm_of(st, "EXPAND"))
    sp.record(st, "EXPAND", "miss", "", session=902, today="2026-01-13", supersede=True)
    check(sp.arm_of(st, "EXPAND") == zeroed, "the zeroed arm is not driven negative or moved")
    check(sp.since_epoch(st) == [], "neither the original nor its correction enters the new epoch")


def test_pending_not_consumed():
    print("supersede: a correction never consumes the next draw")
    st = base()
    sp.record(st, "EXPAND", "miss", "", session=903, today="2026-01-10")
    st["pending"] = {"date": "2026-01-10", "lane": "EXPAND", "offered": ["P-TEST01"]}
    snapshot = copy.deepcopy(st["pending"])
    sp.record(st, "EXPAND", "hit", "", session=903, today="2026-01-10", supersede=True)
    check(st["pending"] == snapshot, "pending draw survives the correction")
    check(not (st.get("offered") or {}).get("EXPAND"), "no cooldown stamped by the correction")


def test_refusals():
    print("supersede: refusals")
    st = base()
    check(refused(lambda: sp.record(st, "EXPAND", "hit", "", session=904,
                                    today="2026-01-10", supersede=True)),
          "--supersede with nothing recorded for (lane, sitting) is refused")
    sp.record(st, "EXPAND", "miss", "", session=904, today="2026-01-10")
    check(refused(lambda: sp.record(st, "EXPAND", "hit", "", session=None,
                                    today="2026-01-10", supersede=True)),
          "--supersede without --session is refused")
    check(refused(lambda: sp.record(st, "IMPROVE", "hit", "", session=904,
                                    today="2026-01-10", supersede=True)),
          "a correction is matched on the LANE too (other lane, same sitting: refused)")


def test_normal_multi_iteration_case():
    print("NORMAL CASE: several plain records of one lane in one sitting")
    st = base()
    for o in ("miss", "hit", "miss"):
        sp.record(st, "EXPAND", o, "", session=905, today="2026-01-10")
    check(len(sp.live_rows(st["history"])) == 3, "three iterations = three live rows, none refused")
    check(sp.arm_of(st, "EXPAND") == {"wins": 2, "iterations": 7}, "each counted once")
    sp.record(st, "EXPAND", "hit", "", session=905, today="2026-01-10", supersede=True)
    live = sp.live_rows(st["history"])
    check([h["outcome"] for h in live] == ["miss", "hit", "hit"],
          "--supersede corrects only the MOST RECENT row of that lane and sitting")
    check(sp.arm_of(st, "EXPAND") == {"wins": 3, "iterations": 7}, "arm net of the correction")


if __name__ == "__main__":
    test_correction_and_rollback()
    test_readers_exclude_superseded()
    test_outside_epoch_leaves_arm()
    test_pending_not_consumed()
    test_refusals()
    test_normal_multi_iteration_case()
    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)}")
        sys.exit(1)
    print("OK")
