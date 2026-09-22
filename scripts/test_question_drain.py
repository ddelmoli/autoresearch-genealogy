#!/usr/bin/env python3
"""Pin question_drain.py — the per-sitting question slice.

⚠ THE INVARIANTS THIS FILE EXISTS FOR:
  (a) the draw EXCLUDES op-gated and BIG questions and RANKS a located-but-unread
      source above a merely free route, ties going to the oldest number;
  (b) a `blocked` outcome cools a question for `blocked_cooldown` SITTINGS (counted as
      distinct session numbers recorded after the block), then it returns;
  (c) a `blocked_routes` pattern removes questions whose body names a refusing site;
  (d) the close gate FAILS with no slice or an unrecorded one, PASSES when every drawn
      question is recorded, and WARNS when the sitting raised questions and closed none;
  (e) `resolved` is refused while the question is still LIVE (the register, not this
      script, is the record of a resolution);
  (d') an empty register owes nothing (the gate PASSES);
  (f) net flow is derived from the HEADINGS (raised clause, terminal status date),
      live shards and the Resolved store, deduplicated by title;
  (g) `--swap` replaces a drawn, UNWORKED question in the pending slice (next-ranked by
      default, or a named live one), needs a reason, refuses a recorded or undrawn
      question, counts the replacement as DRAWN, lets the close gate PASS, and cools the
      swapped-out question for `swap_cooldown` sittings;
  (h) the slice is judged by CLOSURES (operator ruling 22 SEP 2026): the gate WARNS when a
      slice closed nothing even if the sitting raised nothing, each prior `advanced` costs
      a question one rank point (capped), and the heartbeat reports the closure rate.
"""
import json
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import question_drain as QD

TODAY = date.today()
T = TODAY.strftime("%d %b %Y").upper().lstrip("0")

SHARD = f"""---
type: reference
---

# Open Questions — Testland

### 20. A small located source (raised 01 AUG 2026, session #1)

The record is located and never read; free on archive.org.

**⏭ WHAT WOULD SETTLE IT:** read the page

### 21. Needs the operator (raised 02 AUG 2026, session #1)

located and never read; an in-person visit is the only route.

### 22. A free route only (raised 03 AUG 2026, session #1)

archive.org holds the book.

### 23. A site that is refusing (raised 04 AUG 2026, session #2)

located and never read; free on Antenati.

### 24. Raised in the test sitting (raised {T}, session #9)

a new finding

### 25. Closed today — RESOLVED {T} (done)

text
"""

RESOLVED = """# Open Questions Resolved

### 19. Archived earlier (raised 01 AUG 2026, session #1) — RESOLVED 05 AUG 2026 (done)

archived body
"""


def build(d, cfg=None):
    with open(os.path.join(d, "Open_Questions_Testland.md"), "w", encoding="utf-8") as fh:
        fh.write(SHARD)
    with open(os.path.join(d, "Open_Questions_Resolved.md"), "w", encoding="utf-8") as fh:
        fh.write(RESOLVED)
    with open(os.path.join(d, ".maintenance.json"), "w", encoding="utf-8") as fh:
        json.dump({"question_drain": cfg or {"per_session": 3}}, fh)


def drawn(d, session):
    QD.draw(d, session, register=True)
    return QD.load_state(d)["pending"]["offered"]


def main():
    bad = []

    def check(name, cond):
        if not cond:
            bad.append(name)

    with tempfile.TemporaryDirectory() as d:
        build(d)
        # (a) ranking and exclusions
        offered = drawn(d, 9)
        check("op-gated excluded", "21" not in offered)
        check("unread+free ranks first, oldest wins ties", offered[:2] == ["20", "23"])
        check("slice size 3", len(offered) == 3)

        # (d) close gate
        code, _ = QD.check(d, 8)
        check("FAIL when no slice for the sitting", code == 1)
        code, _ = QD.check(d, 9)
        check("FAIL while drawn questions are unrecorded", code == 1)
        for q in offered:
            QD.record(d, 9, q, "advanced", "")
        code, msg = QD.check(d, 9)
        check("PASS when the sitting raised a question but a closure is dated today", code == 0)

        # (e) resolved refused while live
        check("resolved refused while live", QD.record(d, 9, "Q20", "resolved", "") == 1)

        # (f) net flow from the headings
        r, c = QD.net_flow(d, 14)
        check("net flow counts today's raise and today's closure", (r, c) == (1, 1))
        r, c = QD.net_flow(d, 3650)
        check("net flow spans the Resolved store", (r, c) == (6, 2))

    with tempfile.TemporaryDirectory() as d:
        build(d)
        # (d) WARN: raised this sitting, no closure today -> remove Q25's closure
        s = open(os.path.join(d, "Open_Questions_Testland.md"), encoding="utf-8").read()
        s = s.replace(f"— RESOLVED {T} (done)", "— RESOLVED 06 AUG 2026 (done)")
        open(os.path.join(d, "Open_Questions_Testland.md"), "w", encoding="utf-8").write(s)
        for q in drawn(d, 9):
            QD.record(d, 9, q, "untouched", "")
        code, _ = QD.check(d, 9)
        check("WARN when the sitting raised questions and closed none", code == 2)
        # (h) closures, not movement (operator ruling 22 SEP 2026): a slice that raised
        # nothing and closed nothing is no longer a clean PASS
        for q in drawn(d, 30):
            QD.record(d, 30, q, "advanced", "")
        code, msg = QD.check(d, 30)
        check("WARN when an all-advanced slice closed nothing, even with nothing raised",
              code == 2 and "closed nothing" in msg and "CLOSED 0 of" in msg)

    with tempfile.TemporaryDirectory() as d:
        build(d, {"per_session": 3})
        # (h') each prior `advanced` costs rank, capped, and the draw shows the count
        top = drawn(d, 40)[0]
        for s in (41, 42, 43, 44, 45):
            QD.record(d, s, top, "advanced", "")
        cands = QD.candidates(d, QD.load_config(d), QD.load_state(d))
        adv = {r["qlabel"]: (sc, r["advanced"]) for sc, r in cands}
        check("a repeatedly advanced question loses its first place",
              cands[0][1]["qlabel"] != top and adv[top][1] == 5)
        base = [sc for sc, r in QD.candidates(d, QD.load_config(d), QD.empty_state())
                if r["qlabel"] == top][0]
        check("the penalty is capped", adv[top][0] == base - QD.ADVANCED_PENALTY_CAP)
        check("heartbeat reports the slice closure rate",
              "slice closures, last 5 sittings: 0/5" in QD.heartbeat(d))

    with tempfile.TemporaryDirectory() as d:
        build(d, {"per_session": 3, "blocked_cooldown": 2})
        # (b) blocked cooldown, counted in sittings
        QD.record(d, 1, "20", "blocked", "restricted image")
        check("blocked question cools off", "20" not in drawn(d, 2))
        QD.record(d, 2, "22", "advanced", "")
        check("still cooling after one later sitting", "20" not in drawn(d, 3))
        QD.record(d, 3, "22", "advanced", "")
        check("returns after the cooldown", "20" in drawn(d, 4))

    with tempfile.TemporaryDirectory() as d:
        build(d, {"per_session": 3, "blocked_routes": ["Antenati"]})
        # (c) blocked route
        check("blocked route excluded", "23" not in drawn(d, 5))

    with tempfile.TemporaryDirectory() as d:
        build(d, {"per_session": 3, "swap_cooldown": 2})
        # (g) swap
        offered = drawn(d, 9)                                   # [20, 23, 22]
        check("swap needs a reason", QD.swap(d, 9, "Q23") == 1)
        check("swap refuses a question not in the slice", QD.swap(d, 9, "Q21", note="x") == 1)
        check("swap refuses a non-live replacement", QD.swap(d, 9, "Q23", "Q99", note="x") == 1)
        check("swap to next-ranked eligible", QD.swap(d, 9, "Q23", note="policy question") == 0)
        st = QD.load_state(d)
        check("replacement takes the slot", st["pending"]["offered"] == ["20", "24", "22"])
        check("swapped-out written to history",
              any(h["q"] == "23" and h["outcome"] == QD.SWAPPED for h in st["history"]))
        QD.record(d, 9, "Q20", "advanced", "")
        check("swap refuses a recorded question", QD.swap(d, 9, "Q20", note="x") == 1)
        QD.record(d, 9, "Q24", "advanced", "")
        check("replacement recorded as drawn",
              [h for h in QD.load_state(d)["history"] if h["q"] == "24"][-1]["drawn"] is True)
        code, _ = QD.check(d, 9)
        check("gate still FAILS while the rest is unrecorded", code == 1)
        QD.record(d, 9, "Q22", "untouched", "")
        code, msg = QD.check(d, 9)
        check("gate PASSES with a swap in the slice", code == 0 and "swapped 1" in msg)
        check("swapped question cools off", "23" not in drawn(d, 10))
        QD.record(d, 10, "22", "advanced", "")
        QD.record(d, 11, "22", "advanced", "")
        check("swapped question returns after the cooldown", "23" in drawn(d, 12))

    with tempfile.TemporaryDirectory() as d:
        build(d)
        drawn(d, 9)                                             # [20, 23, 22]
        check("swap --with a named question", QD.swap(d, 9, "Q22", "Q24", note="x") == 0
              and QD.load_state(d)["pending"]["offered"] == ["20", "23", "24"])

    with tempfile.TemporaryDirectory() as d:
        # (d) an empty register owes nothing: the close gate must not FAIL a vault
        # with no drawable questions (the session_close fixtures are such a vault)
        with open(os.path.join(d, ".maintenance.json"), "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        code, _ = QD.check(d, 1)
        check("empty register passes the close gate", code == 0)

    if bad:
        print("FAIL test_question_drain:", "; ".join(bad))
        return 1
    print("PASS test_question_drain (32 checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
