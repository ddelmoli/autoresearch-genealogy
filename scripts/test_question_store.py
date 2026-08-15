#!/usr/bin/env python3
"""Pin question_block.py (the ONE grammar home) and question_store.py (the writer).

⚠ THE INVARIANTS THIS FILE EXISTS FOR:
  (a) the boundary rule is SHARED — a `### 143a.` sub-question and a
      `### (original) N.` preserved wording are boundaries to EVERY consumer,
      while dated/emoji `### ` write-ups and `## ✅ …` sub-heads are content to
      every consumer (the 12-14 AUG 2026 truncation incidents were one parser
      fixed while another kept the bug);
  (b) LIVENESS excludes terminal, tombstone, hand-struck and `(original)` blocks
      — a hand-struck heading listed as live would resurrect the zombie class;
  (c) the WRITER cannot produce a non-archivable resolution, cannot write through
      a duplicate, and physically cannot append outside the target block.
"""
import os
import sys
import tempfile
from argparse import Namespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import question_block as QB
import question_store as QS

SHARD = """---
type: reference
---

# Open Questions — Testland

### 10. A plain open question (raised 01 AUG 2026, session #1)

body line

**⏭ WHAT WOULD SETTLE IT:** read the register

### 11. A question with sub-structure (raised 02 AUG 2026, session #2)

opening statement

## ✅ RESOLVED 03 AUG 2026 — a write-up sub-head that is CONTENT

### 📏 STEP 1 DONE — emoji content heading

### 28 JUL 2026 (session #3): a dated content heading

more of Q11's body

### 12a. A live split-out sub-question (raised 03 AUG 2026)

sub-question body

### ~~13. An old topic~~ — Merged into Q10

### (original) 11. The preserved earlier wording of Q11

preserved text

### 14. Done already — RESOLVED 04 AUG 2026 (worked)

resolution text

## Resolved & Closed — Index (full text in [[Open_Questions_Resolved]])

- **Q9** an archived one (RESOLVED) — [[Open_Questions_Resolved#9-an-archived-one]]
"""

RESOLVED = """# Open Questions Resolved

### 90. The highest number lives HERE — RESOLVED 01 AUG 2026 (done)

archived body
"""


def build(d):
    with open(os.path.join(d, "Open_Questions_Testland.md"), "w", encoding="utf-8") as fh:
        fh.write(SHARD)
    with open(os.path.join(d, "Open_Questions_Resolved.md"), "w", encoding="utf-8") as fh:
        fh.write(RESOLVED)


def main():
    bad = []

    def check(name, cond):
        if not cond:
            bad.append(name)

    with tempfile.TemporaryDirectory() as d:
        build(d)
        shard = os.path.join(d, "Open_Questions_Testland.md")
        lines = open(shard, encoding="utf-8").read().split("\n")

        # (a) boundaries: exactly the numbered headings, nothing else
        heads = [lines[s] for s, _e in QB.split_blocks(lines)]
        labels = [QB.parse_heading(h)["qlabel"] for h in heads]
        check("boundary set", labels == ["10", "11", "12a", "13", "11", "14"])
        q11 = next((s, e) for s, e in QB.split_blocks(lines)
                   if QB.parse_heading(lines[s])["qlabel"] == "11"
                   and not QB.parse_heading(lines[s])["original"])
        body = "\n".join(lines[q11[0]:q11[1]])
        check("content travels with block",
              "STEP 1 DONE" in body and "dated content heading" in body
              and "more of Q11's body" in body)

        # (b) liveness
        live = [h["qlabel"] for _s, _e, h, _l in QB.iter_questions(shard) if QB.is_live(h)]
        check("liveness", live == ["10", "11", "12a"])

        # next number spans live + Resolved (Resolved holds the max, 90)
        check("next number spans resolved", QB.next_free_number(d) == 91)

        # (c) writer: --new refuses an em-dash title
        try:
            QS.op_new(d, Namespace(shard="testland", title="Bad — title",
                                   resolver="r", body_file=None, session=None,
                                   apply=True))
            check("em-dash title refused", False)
        except SystemExit:
            pass

        # --new lands before the Resolved index, with the minted number
        QS.op_new(d, Namespace(shard="testland", title="A fresh question",
                               resolver="open the record", body_file=None,
                               session="9", apply=True))
        lines2 = open(shard, encoding="utf-8").read().split("\n")
        h91 = [QB.parse_heading(lines2[s]) for s, _e in QB.split_blocks(lines2)]
        check("new block minted 91", any(h["num"] == 91 for h in h91))
        i91 = next(i for i, ln in enumerate(lines2) if ln.startswith("### 91."))
        iidx = next(i for i, ln in enumerate(lines2) if QB.RESOLVED_INDEX.match(ln))
        check("new block before Resolved index", i91 < iidx)
        check("new block is live",
              QB.is_live(QB.parse_heading(lines2[i91])))

        # --append targets the LAST live block and stays inside it
        QS.op_append(d, Namespace(append="91", text="appended evidence line",
                                  body_file=None, sub_heading="WORKED 15 AUG 2026",
                                  apply=True))
        lines3 = open(shard, encoding="utf-8").read().split("\n")
        s91, e91 = next((s, e) for s, e in QB.split_blocks(lines3)
                        if QB.parse_heading(lines3[s])["num"] == 91)
        blk = "\n".join(lines3[s91:e91])
        check("append inside block", "appended evidence line" in blk
              and "## WORKED 15 AUG 2026" in blk)
        after = "\n".join(lines3[e91:])
        check("append did not leak past block", "appended evidence line" not in after)

        # --resolve writes an archivable heading and verifies it
        QS.op_resolve(d, Namespace(resolve="91", status="RESOLVED",
                                   note="one record read", apply=True))
        lines4 = open(shard, encoding="utf-8").read().split("\n")
        h = QB.parse_heading(next(ln for ln in lines4 if ln.startswith("### 91.")))
        check("resolved heading terminal", h["terminal"]
              and not QB.PROVENANCE_RE.match(h["status"]))

        # --resolve refuses an already-terminal block
        try:
            QS.op_resolve(d, Namespace(resolve="14", status="CLOSED", note=None,
                                       apply=True))
            check("re-resolve refused", False)
        except SystemExit:
            pass

        # --show prints the WHOLE block, cut by the shared boundary, and prefers
        # the LIVE copy. It exists so no consumer re-implements an awk range: Q11
        # carries `## ✅ …` and `### 📏 …` sub-headings that an awk to the next
        # `### ` would truncate away.
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            QS.op_show(d, Namespace(show="11"))
        shown = buf.getvalue()
        check("show carries H2 sub-heading", "RESOLVED 03 AUG 2026" in shown)
        check("show carries emoji sub-heading", "STEP 1 DONE" in shown)
        check("show carries dated content heading", "28 JUL 2026" in shown)
        check("show stops at the next question", "12a." not in shown)
        check("show prefers the LIVE copy over (original)",
              "preserved text" not in shown)

        # --resolve refuses a DUPLICATED live number instead of writing through it
        with open(shard, "a", encoding="utf-8") as fh:
            fh.write("\n### 10. A duplicate of Q10 (raised twice by mistake)\n\ndup body\n")
        try:
            QS.op_resolve(d, Namespace(resolve="10", status="RESOLVED", note=None,
                                       apply=True))
            check("duplicate refused", False)
        except SystemExit:
            pass

    if bad:
        print("QUESTION_STORE test FAIL: " + ", ".join(bad))
        return 1
    print("QUESTION_STORE test ok (shared boundary, liveness, minting spans the "
          "Resolved store, writer refuses em-dash titles / re-resolve / duplicates, "
          "append stays inside its block)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
