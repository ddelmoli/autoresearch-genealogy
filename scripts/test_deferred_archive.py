#!/usr/bin/env python3
"""Pin the H2-item variant of drop-by-status (deferred_decisions.md).

⚠ THE INVARIANTS: (a) an item is a `## N.` heading and runs to the next `## `/
`# ` heading — every `### ` line, INCLUDING `### (original) …` and `### N.`
shapes, is content that travels with it (the one-level-up twin of the 8ace440
question fix); (b) only a LAST-em-dash terminal status archives — `MOVED` at the
start of a title does not; (c) non-numbered `## ` sections are never touched.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("AUTORESEARCH_VAULT", tempfile.gettempdir())
import archive_sections as A

DOC = (
    "# Deferred operator decisions\n"
    "\n"
    "preamble\n"
    "\n"
    "## 1. A done item — DONE 25 JUL 2026 (operator-directed)\n"
    "\n"
    "what happened\n"
    "\n"
    "### (original) 1. THE ORIGINAL WORDING (raised 24 JUL 2026)\n"
    "\n"
    "original text that must travel\n"
    "\n"
    "### 6. A NUMBERED sub-heading that is still item 1's content\n"
    "\n"
    "more of item 1\n"
    "\n"
    "## 2. MOVED 03 AUG 2026 to the question register — remnants prose\n"
    "\n"
    "status slot holds prose, so this must NOT archive\n"
    "\n"
    "## 3. A live item awaiting the operator\n"
    "\n"
    "open text\n"
    "\n"
    "## Parked options\n"
    "\n"
    "a non-numbered section, never a candidate\n"
)

CFG = {
    "name": "deferred-decisions", "file": "deferred_decisions.md",
    "policy": "drop-by-status", "item_heading": "## ",
    "archive_file": "deferred_decisions_Resolved.md",
    "snapshot_dir": "x", "tombstone_link": "deferred_decisions_Resolved",
    "archive_statuses": ["DONE", "RESOLVED", "SUPERSEDED"],
}


def main():
    bad = []

    def check(name, cond):
        if not cond:
            bad.append(name)

    new_text, moved, labels = A.plan_drop_by_status(DOC, CFG, "TS")
    check("exactly item 1 archived", labels == ["Q1 (DONE)"])
    block = moved[0][3]
    check("original wording travels", "original text that must travel" in block)
    check("numbered sub-heading travels", "more of item 1" in block)
    check("MOVED-in-title stays", "## 2. MOVED" in new_text)
    check("live item stays", "## 3. A live item" in new_text)
    check("non-numbered section stays", "## Parked options" in new_text)
    check("archived item gone from live", "what happened" not in new_text)

    if bad:
        print("DEFERRED_ARCHIVE test FAIL: " + ", ".join(bad))
        return 1
    print("DEFERRED_ARCHIVE test ok (H2 items; ### content travels; title-prose "
          "status and non-numbered sections never archive)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
