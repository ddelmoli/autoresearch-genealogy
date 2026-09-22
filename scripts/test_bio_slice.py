#!/usr/bin/env python3
"""Pin bio_slice.py — the per-sitting biography slice.

⚠ THE INVARIANTS THIS FILE EXISTS FOR:
  (a) the draw ranks DIRECT ancestors before collaterals and entries that CITE sources
      before uncited ones, and skips an entry whose core is complete and whose life is
      already written;
  (b) `written` is MEASURED: refused unless the entry gained a facet or NARRATIVE_GAIN
      lines since the draw; accepted once the life is written into the entry;
  (c) `nothing-to-add` needs a note naming what was read;
  (d) the close gate FAILS with no slice or an unrecorded one, WARNS when nothing was
      written, and PASSES when a biography was written;
  (e) a drawn entry cools off for `cooldown` sittings.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bio_slice as BS  # noqa: E402

TREE = """---
type: lineage
created: 2026-09-22
tags: [test]
---

# Test Lineage

### Generation 1

**Anchor Example** (b. 1950)
- meta: {id: P-AAAAAA, generation: 1, life_status: deceased, born: '1950', parents: '[P-BBBBBB?]'}
- Body bullet.

### Generation 2

**Direct Sourced Example** (b. unknown)
- meta: {id: P-BBBBBB, generation: 2, life_status: deceased}
- A short note.
- **Sources**
  - 1900 birth record — fs:1:1:XXXX-XXX

**Collateral Sourced Example** (b. unknown)
- meta: {id: P-CCCCCC, generation: 2, life_status: deceased}
- **Sources**
  - 1901 birth record — fs:1:1:YYYY-YYY

**Collateral Uncited Example** (b. unknown)
- meta: {id: P-DDDDDD, generation: 2, life_status: deceased}
- A short note.

**Finished Example** (b. 1900; d. 1980)
- meta: {id: P-EEEEEE, generation: 2, life_status: deceased, born: '1900', died: '1980', parents: '[P-FFFFFF?]', spouse: '[P-CCCCCC?]'}
- Born 1900 at Exampletown.
- Married in 1925.
- Worked as a farmer all his life.
- Died 1980 at Exampletown.
- **Sources**
  - 1900 birth record — fs:1:1:ZZZZ-ZZZ

**Parent Of Finished** (b. unknown)
- meta: {id: P-FFFFFF, generation: 3, life_status: deceased}
- Body bullet.
"""

WRITTEN = """**Direct Sourced Example** (b. unknown)
- meta: {id: P-BBBBBB, generation: 2, life_status: deceased}
- A short note.
- She was born at Exampletown, the eldest of four children.
- She married in 1922 and kept house on Example Street for forty years.
- She was buried in the Exampletown churchyard.
- **Sources**"""


def build(d, cfg=None):
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as fh:
        json.dump({"person_model": "narrative",
                   "anchor": {"kind": "individual", "people": [{"id": "P-AAAAAA"}]}}, fh)
    with open(os.path.join(d, ".maintenance.json"), "w", encoding="utf-8") as fh:
        json.dump({"bio_slice": cfg or {"per_session": 2, "cooldown": 2}}, fh)
    with open(os.path.join(d, "Family_Tree_Test.md"), "w", encoding="utf-8") as fh:
        fh.write(TREE)


def main():
    bad = []

    def check(name, cond):
        if not cond:
            bad.append(name)

    with tempfile.TemporaryDirectory() as d:
        build(d)
        # (a) ranking
        cands = [pid for pid, _r, _dir in BS.candidates(d, BS.load_config(d), BS.load_state(d))]
        check("direct ancestor ranks first", cands[0] == "P-BBBBBB")
        check("a cited collateral ranks above an uncited one",
              cands.index("P-CCCCCC") < cands.index("P-DDDDDD"))
        check("a finished entry is not drawn", "P-EEEEEE" not in cands)
        BS.draw(d, 1, register=True)
        offered = BS.load_state(d)["pending"]["offered"]
        check("slice size from config", len(offered) == 2 and offered[0] == "P-BBBBBB")

        # (d) gate before recording
        code, _ = BS.check(d, 2)
        check("FAIL when no slice for the sitting", code == 1)
        code, _ = BS.check(d, 1)
        check("FAIL while drawn entries are unrecorded", code == 1)

        # (b) measured `written`
        check("written refused with no gain", BS.record(d, 1, "P-BBBBBB", "written", "") == 1)
        # (c) nothing-to-add needs a note
        check("nothing-to-add needs a note",
              BS.record(d, 1, offered[1], "nothing-to-add", "") == 1)
        check("nothing-to-add accepted with a note",
              BS.record(d, 1, offered[1], "nothing-to-add", "read its one record") == 0)
        path = os.path.join(d, "Family_Tree_Test.md")
        s = open(path, encoding="utf-8").read()
        s = s.replace("**Direct Sourced Example** (b. unknown)\n"
                      "- meta: {id: P-BBBBBB, generation: 2, life_status: deceased}\n"
                      "- A short note.\n- **Sources**", WRITTEN)
        open(path, "w", encoding="utf-8").write(s)
        code, _ = BS.check(d, 1)
        check("gate still FAILS with one entry unrecorded", code == 1)
        check("written accepted once the life is written",
              BS.record(d, 1, "P-BBBBBB", "written", "wrote the life") == 0)
        row = [h for h in BS.load_state(d)["history"] if h["id"] == "P-BBBBBB"][-1]
        check("gain recorded from measurement",
              row["narrative_delta"] >= BS.NARRATIVE_GAIN and "burial" in row["facets_gained"])
        code, msg = BS.check(d, 1)
        check("PASS when a biography was written", code == 0 and "WRITTEN 1 of 2" in msg)
        check("double record refused", BS.record(d, 1, "P-BBBBBB", "written", "") == 1)
        check("heartbeat reports the slice", "wrote 1/2 drawn" in BS.heartbeat(d))

        # (e) cooldown
        check("drawn entry cools off", "P-BBBBBB" not in
              [p for p, _r, _x in BS.candidates(d, BS.load_config(d), BS.load_state(d))])

    with tempfile.TemporaryDirectory() as d:
        build(d)
        BS.draw(d, 1, register=True)
        for pid in BS.load_state(d)["pending"]["offered"]:
            BS.record(d, 1, pid, "blocked", "offline")
        code, msg = BS.check(d, 1)
        check("WARN when nothing was written", code == 2 and "nothing written" in msg)

    if bad:
        print("FAIL test_bio_slice: " + "; ".join(bad))
        return 1
    print("PASS test_bio_slice (17 checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
