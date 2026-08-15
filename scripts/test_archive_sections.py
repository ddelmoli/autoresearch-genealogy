#!/usr/bin/env python3
"""Pin archive_sections.py's question-block BOUNDARY, in both directions.

⚠ THE INVARIANT THIS FILE EXISTS FOR: a `### N.` question block runs to the next
`### ` heading or to the Resolved-index section, and to NO other `## `. Questions
legitimately contain `## ✅ RESOLVED …` / `## ⏩ WORKED …` / `## 📏 RE-MEASURED …`
sub-headings -- that is how this vault writes a resolution -- so a splitter that
stops at any `## ` truncates every archivable block to its heading.

⛔ AND THE ARCHIVER IS A WRITER, which is why this is pinned separately from
test_question_index.py rather than trusted to it. A truncated block does not merely
mis-measure: the tool moves the 2-line stub to the Resolved file, DELETES the
heading, and leaves the whole resolution write-up orphaned in the live file under no
question at all. Measured on the two DUE targets 14 AUG 2026, before the fix: 10 of
10 archivable blocks truncated, 1,065 lines would have been orphaned.

The reader (gen_question_index.py) was fixed for this on 12 AUG 2026 (fa6793a); the
writer was not, and nothing noticed for two days because both tools "worked". When a
structure has two parsers, fix both or neither.

BOTH DIRECTIONS ARE REQUIRED. Case (b) alone passes on the pre-12-AUG code and case
(a) alone passes on the over-fix that fa6793a's message documents as WRONG.
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("AUTORESEARCH_VAULT", tempfile.gettempdir())
import archive_sections as A

# One question whose resolution is written the way this vault writes one: an H2
# sub-heading inside the body. Everything through the padding is Q1's content.
Q1_BODY_LINES = 34
DOC = (
    "### 1. A resolved question — RESOLVED 14 AUG 2026 (session #165)\n"
    "\n"
    "## ✅ RESOLVED 14 AUG 2026 (session #165) — the write-up lives HERE\n"
    "\n"
    + "resolution line\n" * 20
    + "\n"
    "## \U0001f4cf RE-MEASURED 14 AUG 2026 — a second sub-heading, still Q1's content\n"
    "\n"
    + "measurement line\n" * 9
    + "\n"
    "### 2. A live question (raised 14 AUG 2026, session #165)\n"
    "\n"
    "still open\n"
    "\n"
    "## Resolved & Closed — Index (full text in [[Open_Questions_Resolved]])\n"
    "\n"
    # 12 rows with DISTINCT anchors -- upsert_index keys on the anchor, so identical
    # rows would legitimately collapse to one and the survival check would be vacuous.
    + "".join(f"- **Q{900+i}** a previously migrated question "
              f"— [[Open_Questions_Resolved#{900+i}-a-previously-migrated-question]]\n"
              for i in range(12))
    + "\n"
    # ⚠ A QUESTION WRITTEN BELOW THE INDEX. The index is appended at EOF when absent,
    # so a question raised afterwards lands here -- an ordinary layout, not an exotic
    # one. upsert_index ended the section at the next `## `, and a `### ` heading does
    # not start with `## `, so this ran to EOF as "index content" and was DESTROYED on
    # rebuild. Live casualty 14 AUG 2026: Q270, 27 lines, deleted by an archive run of
    # an unrelated question in the same file.
    "### 3. A question raised AFTER the index existed (raised 14 AUG 2026)\n"
    "\n"
    "content below the index that must survive a rebuild\n"
)

CFG = {
    "name": "test", "file": "Open_Questions_Test.md",
    "archive_file": "Open_Questions_Resolved.md",
    "tombstone_link": "Open_Questions_Resolved",
    "archive_statuses": ["RESOLVED", "RULED OUT", "CLOSED"],
}


def main():
    bad = []
    lines = DOC.splitlines(keepends=True)
    blocks = {}
    for start, end in A._split_h3_blocks(lines):
        num = lines[start].split(".", 1)[0].replace("### ", "").strip()
        blocks[num] = (start, end)

    # (a) a question must KEEP its own `## ` sub-headings -- the truncation bug
    if "1" not in blocks:
        bad.append("Q1 not found at all")
    else:
        start, end = blocks["1"]
        n = end - start
        if n < Q1_BODY_LINES:
            bad.append(f"Q1 TRUNCATED at its own '## ' sub-heading: block is {n} lines, "
                       f"expected >= {Q1_BODY_LINES} -- sub-sections are question content")
        body = "".join(lines[start:end])
        for marker in ("resolution line", "measurement line"):
            if marker not in body:
                bad.append(f"Q1 block lost its {marker!r} content")

    # (b) ...but a question must NOT swallow the trailing Resolved index
    if "2" in blocks:
        start, end = blocks["2"]
        if "Resolved & Closed" in "".join(lines[start:end]):
            bad.append("the last question SWALLOWED the Resolved index "
                       f"({end - start} lines) -- it is not question content")

    # (c) end to end: the plan must move the whole write-up, not a stub, and must
    #     leave no orphaned resolution text behind in the live file.
    new_live, moved, dropped = A.plan_drop_by_status(DOC, CFG, "TS")
    if not moved or len(moved) != 1:
        bad.append(f"expected exactly 1 archivable block, got {moved and len(moved)}")
    else:
        block = moved[0][3]
        if "resolution line" not in block or "measurement line" not in block:
            bad.append("the MOVED block is a stub -- the resolution write-up was left behind")
        if new_live is not None and "resolution line" in new_live:
            bad.append("ORPHANED: resolution text stayed in the live file after its "
                       "heading was removed")
    # the live file must keep the open question and gain an index row
    if new_live is not None:
        if "### 2." not in new_live:
            bad.append("the live question was removed")
        if "Q1" not in new_live:
            bad.append("no compact-index row was written for the migrated question")

    # (d) a question written BELOW the index must survive the section rebuild, and the
    #     pre-existing index rows must survive with it.
    if new_live is not None:
        if "### 3." not in new_live:
            bad.append("DESTROYED: the question written below the Resolved index was "
                       "deleted when the section was rebuilt")
        if "content below the index that must survive" not in new_live:
            bad.append("DESTROYED: body text below the Resolved index was lost")
        kept = sum(1 for i in range(12) if f"**Q{900+i}**" in new_live)
        if kept != 12:
            bad.append(f"pre-existing index rows lost: {kept} of 12 survived")
        # and the survivor must still sit BELOW the index, not be hoisted above it.
        # ⚠ guarded: when the question has been destroyed this check cannot run, and a
        # traceback here would suppress the findings collected above (a failing control
        # reported NOTHING at all until this guard was added).
        if "### 3." in new_live and "Resolved & Closed" in new_live:
            if new_live.index("Resolved & Closed") > new_live.index("### 3."):
                bad.append("the below-index question was reordered above the index section")

    bad += check_h3_boundary()
    bad += check_lint_archive()

    if bad:
        print("ARCHIVE_SECTIONS test FAILED:")
        for b in bad:
            print("   ", b)
        return 1
    print("ARCHIVE_SECTIONS test ok (block keeps its own '## ' sub-headings; stops at "
          "the Resolved index; migration moves the full write-up and orphans nothing; "
          "lint_archive catches EMPTY + TRUNCATED and tolerates duplicate Q numbers)")
    return 0


# A pre-archive snapshot holding three questions in full, and a store that migrated them
# with varying damage. Q31 is the case a stub count MISSES: it stored plausible-looking
# lines and lost only its resolution.
# ⚠ EVERY LINE MUST BE DISTINCT. The comparison is set-based (line order and repetition
# carry no meaning across an edit), so a fixture built from repeated identical lines
# collapses to one element and the truncation it means to stage disappears.
def _lines(tag, n):
    return "".join(f"{tag} line {i}\n" for i in range(n))


SNAPSHOT = (
    "### 30. A question that lost EVERYTHING — RESOLVED 01 AUG 2026\n\nQ30 intro\n\n"
    "## ✅ RESOLVED — the write-up\n\n" + _lines("Q30 resolution", 8) + "\n"
    "### 31. A question that lost only its RESOLUTION — RESOLVED 01 AUG 2026\n\n"
    + _lines("Q31 opening statement", 9) + "\n"
    "## ✅ RESOLVED — the part that went missing\n\n" + _lines("Q31 verdict", 9) + "\n"
    "### 32. A question that migrated INTACT — RESOLVED 01 AUG 2026\n\nQ32 intro\n\n"
    "## ✅ RESOLVED — all present\n\n" + _lines("Q32 detail", 8) + "\n"
    # ⚠ a DUPLICATE question number with a different title: keying on the number would
    # match this against Q32's snapshot and report a phantom truncation.
    "### 32. A DIFFERENT question sharing the number — RESOLVED 01 AUG 2026\n\nQ32b intro\n\n"
    "## ✅ RESOLVED — distinct content\n\n" + _lines("Q32b detail", 8) + "\n"
)
STORE = (
    "### 30. A question that lost EVERYTHING — RESOLVED 01 AUG 2026\n\n---\n\n"
    "### 31. A question that lost only its RESOLUTION — RESOLVED 01 AUG 2026\n\n"
    + _lines("Q31 opening statement", 9) + "\n---\n\n"
    "### 32. A question that migrated INTACT — RESOLVED 01 AUG 2026\n\nQ32 intro\n\n"
    "## ✅ RESOLVED — all present\n\n" + _lines("Q32 detail", 8) + "\n---\n\n"
    "### 32. A DIFFERENT question sharing the number — RESOLVED 01 AUG 2026\n\nQ32b intro\n\n"
    "## ✅ RESOLVED — distinct content\n\n" + _lines("Q32b detail", 8) + "\n---\n"
)


# ⚠ BOTH DIRECTIONS ARE LOAD-BEARING AND EACH WAS OBSERVED FAILING ON 14 AUG 2026:
# treating any `### ` as a boundary ORPHANED 1,208 lines of question write-ups; treating
# every `### ` as content proposed BURYING a live sub-question (`### 143a.`) inside its
# archived parent. The discriminator is a number followed immediately by a period.
H3_DOC = (
    "### 50. A question whose resolution is written as `### ` sub-sections — RESOLVED 01 AUG 2026\n\n"
    "opening statement\n\n"
    "### 28 JUL 2026 (session #106): resolver (a) is CLOSED\n\n"
    "resolver a detail\n\n"
    "### ✅ WHAT IS NOW ESTABLISHED (do not re-derive)\n\n"
    "established detail\n\n"
    "### 50a. A split-out SUB-QUESTION that is still LIVE\n\n"
    "sub-question body\n\n"
    "### 51. The next question (raised 02 AUG 2026)\n\n"
    "next body\n"
)


def check_h3_boundary():
    bad = []
    lines = H3_DOC.splitlines(keepends=True)
    spans = {}
    for s, e in A._split_h3_blocks(lines):
        spans[lines[s].split(".", 1)[0].replace("### ", "").strip()] = (s, e)

    for want in ("50", "50a", "51"):
        if want not in spans:
            bad.append(f"Q{want} was not recognised as a question boundary")
    if "50" in spans:
        body = "".join(lines[slice(*spans["50"])])
        # (a) its own dated / emoji write-ups must travel WITH it
        for m in ("resolver a detail", "established detail"):
            if m not in body:
                bad.append(f"Q50 lost {m!r} -- a `### ` write-up is question CONTENT")
        # (b) ...but a numbered sub-question must NOT be swallowed
        if "sub-question body" in body:
            bad.append("Q50 SWALLOWED the live sub-question 50a -- archiving it would bury 50a")
        if "next body" in body:
            bad.append("Q50 ran past the next question")
    return bad


def check_lint_archive():
    import pathlib
    bad = []
    with tempfile.TemporaryDirectory() as d:
        v = pathlib.Path(d)
        (v / "Open_Questions_Archive").mkdir()
        (v / "Open_Questions_Archive" / "Open_Questions_2026-08-01-000000.md").write_text(
            SNAPSHOT, encoding="utf-8")
        (v / "Open_Questions_Resolved.md").write_text(STORE, encoding="utf-8")
        empty, truncated = A.lint_archive(v)

        if len(empty) != 1 or "30." not in empty[0]:
            bad.append(f"EMPTY should be exactly Q30, got {empty}")
        titles = " ".join(h for _, h in truncated)
        if len(truncated) != 1 or "31." not in titles:
            bad.append(f"TRUNCATED should be exactly Q31, got {[h for _, h in truncated]}")
        # ⭐ the case a stub count misses: Q31 stored 9 plausible lines and is NOT empty
        if any("31." in h for h in empty):
            bad.append("Q31 was reported EMPTY -- it stored 9 lines; only the snapshot "
                       "comparison can see that its resolution is missing")
        # the intact question, and its duplicate-numbered neighbour, must both stay clean
        if "32." in titles:
            bad.append("a Q32 was reported truncated -- duplicate question NUMBERS must be "
                       "matched by TITLE, or each duplicate is judged against the other")
    return bad


if __name__ == "__main__":
    sys.exit(main())
