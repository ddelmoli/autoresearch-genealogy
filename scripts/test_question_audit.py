#!/usr/bin/env python3
"""Pin question_audit.py — the register's structural gate.

⚠ THE INVARIANTS: (a) a live block below the Resolved index is HARD (the
index-rebuild blast radius that destroyed a 27-line live question, 8477d95);
(b) a duplicated live Q number is HARD (question_store refuses to write through
one, so the gate must surface it); (c) a live number that is TERMINAL in the
Resolved store is HARD (the Q197 zombie class — resolved work re-offered as
live); (d) negative controls: a tombstone, an `(original)` wording and a
terminal block in the live shard are NOT zombies/dups — the archiver owns them.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import question_audit as QA

SHARD_A = """# Shard A

### 1. Open and fine (raised 01 AUG 2026)

body

**⏭ WHAT WOULD SETTLE IT:** a record read

### 2. Duplicated across shards (raised 01 AUG 2026)

body

### 3. The zombie: also terminal in Resolved (raised 05 AUG 2026)

body

### ~~4. Hand-struck tombstone~~ — Merged into Q1

### (original) 1. Preserved wording of Q1

preserved

### 5. Terminal but not yet archived — RESOLVED 14 AUG 2026 (fine, archiver owns it)

resolution

## Resolved & Closed — Index (full text in [[Open_Questions_Resolved]])

- **Q9** something — [[Open_Questions_Resolved#9-something]]

### 6. WRITTEN BELOW THE INDEX (raised 14 AUG 2026)

in the blast radius
"""

SHARD_B = """# Shard B

### 2. Duplicated across shards, the second copy (raised 02 AUG 2026)

body
"""

RESOLVED = """# Resolved

### 3. The zombie's terminal copy — RESOLVED 06 AUG 2026 (done)

archived write-up

### 7. An ordinary archived one — CLOSED 01 AUG 2026

archived
"""


def main():
    bad = []

    def check(name, cond):
        if not cond:
            bad.append(name)

    with tempfile.TemporaryDirectory() as d:
        for name, text in [("Open_Questions_A.md", SHARD_A),
                           ("Open_Questions_B.md", SHARD_B),
                           ("Open_Questions_Resolved.md", RESOLVED)]:
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write(text)

        f = QA.collect(d)
        check("below-index found",
              [q for _r, _l, q in f["Q_BELOW_INDEX"]] == ["6"])
        check("dup found", [lbl for lbl, _p in f["DUP_LIVE_Q"]] == ["2"])
        check("zombie found", [lbl for lbl, _p in f["ZOMBIE_Q"]] == ["3"])
        # negative controls
        live = {q for _r, _l, q in f["LIVE"]}
        check("tombstone not live", "4" not in live)
        check("terminal not live", "5" not in live)
        check("original not duplicated",
              all(lbl != "1" for lbl, _p in f["DUP_LIVE_Q"]))
        check("archived-only number is not a zombie",
              all(lbl != "7" for lbl, _p in f["ZOMBIE_Q"]))
        # resolverless: Q1 names one, Q2/Q3/Q6 do not
        no_res = {q for _r, _l, q in f["RESOLVERLESS"]}
        check("resolver detected", "1" not in no_res and "2" in no_res)

    if bad:
        print("QUESTION_AUDIT test FAIL: " + ", ".join(bad))
        return 1
    print("QUESTION_AUDIT test ok (below-index, dup, zombie all HARD-detected; "
          "tombstone/original/terminal are negative controls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
