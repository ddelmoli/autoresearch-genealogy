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
import pathlib
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
        lines = pathlib.Path(shard).read_text(encoding="utf-8").split("\n")

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
        lines2 = pathlib.Path(shard).read_text(encoding="utf-8").split("\n")
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
        lines3 = pathlib.Path(shard).read_text(encoding="utf-8").split("\n")
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
        lines4 = pathlib.Path(shard).read_text(encoding="utf-8").split("\n")
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

        # --resolve FOLDS an interim status into the title instead of stacking a
        # second status segment behind it — and must NOT fold a subtitle.
        # ⚠ The negative control is the point: 54 of 68 live headings in the
        # reference register carry a SUBTITLE in the status slot, and folding one
        # would mangle the heading.
        fold = os.path.join(d, "Open_Questions_Folding.md")
        with open(fold, "w", encoding="utf-8") as fh:
            fh.write(
                "# Folding\n\n"
                "### 70. A question with an interim status \u2014 PARTIALLY_RESOLVED 25 MAR 2026\n\nbody\n\n"
                "### 71. A question with an interim status and its own note \u2014 "
                "PARTIALLY RESOLVED 13 AUG 2026 ((a) settled; (b) open)\n\nbody\n\n"
                "### 72. A question \u2014 whose status slot is a SUBTITLE, not a status\n\nbody\n")
        for num, want_in_title, why in (
                ("70", "(PARTIALLY_RESOLVED 25 MAR 2026)", "underscore spelling folded"),
                ("71", "(PARTIALLY RESOLVED 13 AUG 2026 ((a) settled; (b) open))",
                 "spaced spelling folded VERBATIM, own parens and all")):
            QS.op_resolve(d, Namespace(resolve=num, status="RESOLVED NEGATIVE",
                                       note="closed", apply=True))
            with open(fold, encoding="utf-8") as fh:
                head = [l for l in fh if l.startswith(f"### {num}.")][0]
            h = QB.parse_heading(head)
            check(f"Q{num} {why}", want_in_title in h["title"])
            check(f"Q{num} exactly one status segment", h["status"].startswith("RESOLVED NEGATIVE"))
            check(f"Q{num} archivable", h["terminal"] and not QB.PROVENANCE_RE.match(h["status"]))
            check(f"Q{num} no stacked interim left in the slot",
                  "PARTIALLY" not in h["status"])
        QS.op_resolve(d, Namespace(resolve="72", status="RESOLVED", note=None, apply=True))
        with open(fold, encoding="utf-8") as fh:
            head72 = [l for l in fh if l.startswith("### 72.")][0]
        h72 = QB.parse_heading(head72)
        check("a SUBTITLE is never folded into parens",
              "(whose status slot is a SUBTITLE" not in h72["title"])
        check("a SUBTITLE stays a title segment",
              h72["title"].endswith("not a status") and h72["terminal"])

        # --replace corrects a token INSIDE one live block, and refuses the edits
        # that would break another consumer (16 SEP 2026).
        QS.op_replace(d, Namespace(replace="12a", old=["sub-question body"],
                                   with_text=["sub-question body, corrected"], apply=True))
        txt = pathlib.Path(shard).read_text(encoding="utf-8")
        check("replace lands inside the block", "sub-question body, corrected" in txt)
        for why, kw in (
                ("replace refuses a zero-match --old",
                 dict(replace="12a", old=["no such text"], with_text=["x"])),
                ("replace refuses a text outside the block",
                 dict(replace="12a", old=["preserved text"], with_text=["x"])),
                ("replace refuses a number change",
                 dict(replace="12a", old=["### 12a."], with_text=["### 12b."])),
                ("replace refuses a new question boundary",
                 dict(replace="12a", old=["sub-question body, corrected"],
                      with_text=["body\n\n### 55. A smuggled question"])),
                ("replace refuses removing the resolver",
                 dict(replace="10", old=["**\u23ed WHAT WOULD SETTLE IT:** read the register"],
                      with_text=["nothing"])),
                ("replace refuses an added em-dash in the heading",
                 dict(replace="10", old=["A plain open question"],
                      with_text=["A plain \u2014 open question"]))):
            try:
                QS.op_replace(d, Namespace(apply=True, **kw))
                check(why, False)
            except SystemExit:
                pass

        # --replace reaches a RESOLVED block still in a live shard (29 OCT 2026),
        # but never archived text in the Resolved store, and never its status
        QS.op_replace(d, Namespace(replace="14", old=["resolution text"],
                                   with_text=["resolution text, corrected"], apply=True))
        txt = pathlib.Path(shard).read_text(encoding="utf-8")
        check("replace corrects a resolved-unarchived block",
              "resolution text, corrected" in txt
              and "### 14. Done already — RESOLVED 04 AUG 2026 (worked)" in txt)
        for why, kw in (("replace refuses archived text in the Resolved store",
                         dict(replace="90", old=["archived body"], with_text=["x"])),
                        ("replace refuses un-resolving a resolved block",
                         dict(replace="14", old=[" — RESOLVED 04 AUG 2026 (worked)"],
                              with_text=[""]))):
            try:
                QS.op_replace(d, Namespace(apply=True, **kw))
                check(why, False)
            except SystemExit:
                pass
        check("archived text untouched", "archived body" in pathlib.Path(os.path.join(d, "Open_Questions_Resolved.md")).read_text(encoding="utf-8"))

        # --resolve refuses a DUPLICATED live number instead of writing through it
        with open(shard, "a", encoding="utf-8") as fh:
            fh.write("\n### 10. A duplicate of Q10 (raised twice by mistake)\n\ndup body\n")
        try:
            QS.op_resolve(d, Namespace(resolve="10", status="RESOLVED", note=None,
                                       apply=True))
            check("duplicate refused", False)
        except SystemExit:
            pass

    # --new does not double a provenance paren the title already carries
    # (27 OCT 2026), and still adds one when the title has none
    with tempfile.TemporaryDirectory() as d:
        build(d)
        shard = os.path.join(d, "Open_Questions_Testland.md")
        QS.op_new(d, Namespace(shard="testland",
                               title="A titled question (raised 05 OCT 2026, session #7)",
                               resolver="r", body_file=None, session="7", apply=True))
        QS.op_new(d, Namespace(shard="testland", title="A bare title",
                               resolver="r", body_file=None, session="7", apply=True))
        heads = [ln for ln in pathlib.Path(shard).read_text(encoding="utf-8").split("\n")
                 if ln.startswith("### 91.") or ln.startswith("### 92.")]
        check("provenance in title not doubled",
              len(heads) == 2 and heads[0].count("(raised ") == 1
              and heads[0].endswith("(raised 05 OCT 2026, session #7)"))
        check("bare title still gets provenance",
              heads[1].count("(raised ") == 1 and heads[1].endswith(", session #7)"))

        # a heading can be retitled through --replace (no separate retitle op)
        QS.op_replace(d, Namespace(replace="92", old=["A bare title"],
                                   with_text=["A better title"], apply=True))
        lines = pathlib.Path(shard).read_text(encoding="utf-8").split("\n")
        check("heading retitled via --replace",
              any(ln.startswith("### 92. A better title (raised ") for ln in lines))

    if bad:
        print("QUESTION_STORE test FAIL: " + ", ".join(bad))
        return 1
    print("QUESTION_STORE test ok (shared boundary, liveness, minting spans the "
          "Resolved store, writer refuses em-dash titles / re-resolve / duplicates, "
          "append stays inside its block)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
