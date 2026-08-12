#!/usr/bin/env python3
"""Pin gen_question_index.py's live/resolved filter and title handling.

⚠ THE INVARIANT THIS FILE EXISTS FOR: the index and `archive_sections` must agree
about which questions are LIVE. They agree by CONSTRUCTION -- the index imports
`_heading_status` / `_matches_terminal` rather than reimplementing the last-em-dash
rule -- and these cases pin that the wiring stays correct.

The trailing-provenance trap (28 of 144 headings, 11 AUG 2026) is included as a
control: a heading whose status slot holds a provenance clause is NOT archivable, so
the index must keep showing it as LIVE. An index that hid it would conceal exactly
the backlog the heading lint exists to surface.
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_question_index as G

LIVE = [
    "### 1. A plain open question",
    "### 2. Something (raised 12 AUG 2026, session #162, EXPAND lane)",
    # PARTIALLY_RESOLVED is NOT terminal -- the question is still open
    "### 3. Half done — PARTIALLY_RESOLVED 30 JUN 2026 (two limbs left)",
    # the trailing-provenance trap: status slot holds provenance, so NOT archivable
    "### 4. Title — RESOLVED 09 AUG 2026 — raised 05 AUG 2026 (session #144)",
    # a title that merely CITES another question's status must stay live
    "### 5. Split out of the RESOLVED Q195",
]
RESOLVED = [
    "### 6. Done — RESOLVED 12 AUG 2026 (he died 25 JAN 1660/61)",
    "### 7. Done — RULED OUT 01 JUL 2026",
    "### 8. Done — FULLY RESOLVED 30 JUN 2026 (pirate detach)",
    "### 9. Done — CONFIRMED FAIL 22 MAR 2026",
]


def main():
    bad = []
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "Open_Questions.md"), "w", encoding="utf-8") as fh:
            for h in LIVE + RESOLVED:
                fh.write(h + "\n\nbody text for " + h[:9] + "\n\n")
        # a resolved store that must be IGNORED by the glob
        with open(os.path.join(d, "Open_Questions_Resolved.md"), "w", encoding="utf-8") as fh:
            fh.write("### 99. Should never appear\n\nbody\n")
        rows = G.parse(d)
        nums = {r["num"] for r in rows}
        for h in LIVE:
            n = int(h.split(".")[0].replace("### ", ""))
            if n not in nums:
                bad.append(f"LIVE question {n} missing from the index: {h}")
        for h in RESOLVED:
            n = int(h.split(".")[0].replace("### ", ""))
            if n in nums:
                bad.append(f"RESOLVED question {n} wrongly shown as live: {h}")
        if 99 in nums:
            bad.append("Open_Questions_Resolved.md was globbed -- it must be excluded")
        by = {r["num"]: r for r in rows}
        # the provenance clause is stripped from the displayed title...
        if 2 in by and "raised" in by[2]["title"].lower():
            bad.append(f"provenance not stripped from title: {by[2]['title']!r}")
        # ...but PARTIALLY_RESOLVED keeps its underscore
        if 3 in by and "PARTIALLY_RESOLVED" not in by[3]["title"]:
            bad.append(f"underscore eaten in title: {by[3]['title']!r}")
    if bad:
        print("QUESTION_INDEX test FAILED:")
        for b in bad:
            print("   ", b)
        return 1
    print(f"QUESTION_INDEX test ok ({len(LIVE)} live, {len(RESOLVED)} resolved, "
          f"resolved-store exclusion, title handling)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
