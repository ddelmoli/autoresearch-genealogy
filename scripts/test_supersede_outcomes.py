#!/usr/bin/env python3
"""test_supersede_outcomes.py — pins `--supersede` on the two append-only outcome stores.

** WHY THIS EXISTS, AND IT IS A MEASURED FAILURE (20 SEP 2026, session #212). **
Both `question_drain.py` and `profile_review.py` record outcomes by APPENDING to a
history list, and neither had a way to CORRECT one. A sitting that recorded a question
`untouched` and then realised the row was actually access-BLOCKED appended a second row,
and the close gate reported **six outcomes for a five-question slice**. The same shape is
worse in `profile_review`, whose `arms` map is an incrementing counter: a re-record
inflates that arm's polled/hits, and the arm's hit-rate FEEDS THE DRAW.

** THE FIX KEEPS THE APPEND-ONLY DISCIPLINE. ** Nothing is deleted. The prior row is
marked `superseded: true` and the correcting row appended after it; every counter reads
through `live_rows()`. The original stays visible as an audit trail, which is the same
reason `log_session.py` and `question_store.py` forbid hand-edits.

What is pinned here:
  1. a plain re-record is REFUSED (this is what silently double-counted before);
  2. `--supersede` marks the prior row and the tally counts the question ONCE;
  3. the superseded row is still PRESENT (append-only, nothing destroyed);
  4. `--supersede` with nothing to correct is refused, not silently treated as new;
  5. profile_review rolls the arm counters BACK, so a corrected hit does not leave
     the arm's hit-rate inflated;
  6. ⚠ an ordinary poll of the SAME person on a LATER DAY is normal rotation and must
     still pass through — the guard is scoped to same-day corrections only. A guard
     that blocked cross-day polling would silently stop the rotation.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import question_drain as QD  # noqa: E402
import profile_review as PR  # noqa: E402

FAILS: list[str] = []


def check(cond, label):
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


# --------------------------------------------------------------- question_drain
def test_question_drain():
    print("question_drain.live_rows / --supersede")
    hist = [
        {"session": 212, "q": "146", "outcome": "untouched", "drawn": True},
        {"session": 212, "q": "294", "outcome": "advanced", "drawn": True},
    ]
    check(len(QD.live_rows(hist)) == 2, "no superseded rows -> all live")

    hist[0]["superseded"] = True
    hist.append({"session": 212, "q": "146", "outcome": "blocked", "drawn": True})
    live = QD.live_rows(hist)
    check(len(live) == 2, "a superseded row drops out of the live tally")
    check(len(hist) == 3, "the superseded row is KEPT in history, not deleted")
    outcomes = sorted(h["outcome"] for h in live)
    check(outcomes == ["advanced", "blocked"],
          "the CORRECTING outcome is the one that counts")
    q146 = [h for h in live if h["q"] == "146"]
    check(len(q146) == 1, "the corrected question is counted exactly ONCE")

    # the cooldown reader must not see the superseded row either
    since = QD._sessions_since(hist, "146", "untouched")
    check(since is None, "cooldown lookup ignores a superseded outcome")
    check(QD._sessions_since(hist, "146", "blocked") == 0,
          "cooldown lookup still sees the live outcome")


# --------------------------------------------------------------- profile_review
class _FakeVault:
    """resolve_person_key is the only vault touch record() makes; stub it out."""


def test_profile_review_arm_rollback():
    print("profile_review --supersede rolls the ARM counters back")
    today = date(2026, 9, 20)
    state = {"entries": {}, "arms": {}, "history": []}
    orig = PR.resolve_person_key
    PR.resolve_person_key = lambda vault, pid: pid
    try:
        PR.record(None, state, "P-AAAAAA", "hit", arm="EXISTENCE_PROBE", today=today)
        arm = state["arms"]["EXISTENCE_PROBE"]
        check((arm["polled"], arm["hits"]) == (1, 1), "first poll counts 1 polled / 1 hit")

        # a plain re-record is refused -- this is the bug being pinned
        try:
            PR.record(None, state, "P-AAAAAA", "miss", arm="EXISTENCE_PROBE", today=today)
            check(False, "a same-day re-record without --supersede is REFUSED")
        except SystemExit:
            check(True, "a same-day re-record without --supersede is REFUSED")
        arm = state["arms"]["EXISTENCE_PROBE"]
        check((arm["polled"], arm["hits"]) == (1, 1),
              "the refused re-record left the arm counters untouched")

        # the correction
        PR.record(None, state, "P-AAAAAA", "miss", arm="EXISTENCE_PROBE", today=today,
                  supersede=True)
        arm = state["arms"]["EXISTENCE_PROBE"]
        check((arm["polled"], arm["hits"]) == (1, 0),
              "a hit corrected to a miss leaves polled=1 and hits=0, NOT polled=2")
        check(len(state["history"]) == 2, "both rows kept in history")
        check(len(PR.live_rows(state["history"])) == 1, "only the correction is live")
        check(state["entries"]["P-AAAAAA"]["outcome"] == "miss",
              "the entry carries the corrected outcome")

        # --supersede with nothing to correct is refused
        try:
            PR.record(None, state, "P-BBBBBB", "hit", arm="EXISTENCE_PROBE", today=today,
                      supersede=True)
            check(False, "--supersede with no prior same-day row is REFUSED")
        except SystemExit:
            check(True, "--supersede with no prior same-day row is REFUSED")

        # ordinary rotation on a LATER day must still pass through
        later = today + timedelta(days=30)
        PR.record(None, state, "P-AAAAAA", "hit", arm="EXISTENCE_PROBE", today=later)
        arm = state["arms"]["EXISTENCE_PROBE"]
        check((arm["polled"], arm["hits"]) == (2, 1),
              "a LATER-day poll of the same person is normal rotation, not a correction")
    finally:
        PR.resolve_person_key = orig


if __name__ == "__main__":
    test_question_drain()
    test_profile_review_arm_rollback()
    print()
    if FAILS:
        print(f"FAILED {len(FAILS)}:")
        for f in FAILS:
            print("   -", f)
        sys.exit(1)
    print("all supersede checks passed")
