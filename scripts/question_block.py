#!/usr/bin/env python3
"""question_block.py — THE one home for the Open_Questions block grammar.

Every tool that reads or writes the question register imports its boundary,
heading and status logic from HERE: `archive_sections.py` (the archiver),
`gen_question_index.py` (the index), `question_store.py` (the writer) and
`question_audit.py` (the gate). Same rule as `person_store` for person records:
one grammar, one home, so two tools cannot disagree about where a block ends.

⚠ WHY THIS FILE EXISTS. Until 15 AUG 2026 the boundary logic lived TWICE — once
in the archiver, once in the index — and the two disagreed: the index could not
see `### 143a.` (a live split-out sub-question) or `### (original) 238.` (a
preserved earlier wording), so a live question was invisible to the worklist and
its content was reported under its numeric neighbour's row. Three separate
truncation/orphaning incidents (fa6793a, 8477d95, 8ace440) were each one parser
being fixed while the other kept the bug. The full case history stays on those
commits and in the archiver's docstrings; the RULES live here:

  BOUNDARY  a `### ` heading whose text is a NUMBER (optional single trailing
            letter) IMMEDIATELY FOLLOWED BY A PERIOD — optionally struck
            (`~~31.`) or prefixed `(original) `. Also the `## Resolved & Closed`
            index section.
  CONTENT   every other `### ` or `## ` line — dated write-ups
            (`### 28 JUL 2026 …`), emoji-led steps (`### 📏 STEP 1 DONE`),
            resolution sub-heads (`## ✅ RESOLVED …`) all travel WITH their
            question.
  STATUS    the text after the LAST em-dash of the heading; terminal only if it
            STARTS with a terminal keyword (whole-token). Provenance belongs in
            the title parens, never after the status.
"""
import glob
import os
import re

EMDASH = "—"

# The ONE trailing `## ` section that is not question content — the archiver's
# compact index. A question block stops here and at no other `## `.
RESOLVED_INDEX = re.compile(r"^##\s+Resolved\s*&\s*Closed", re.I)

# A `### ` line that really STARTS A QUESTION — a boundary. See module docstring
# for the boundary/content rule and the two measured failure directions.
QUESTION_HEAD = re.compile(r"^###\s+(?:~~)?(?:\(original\)\s*)?\d+[a-z]?\.")

# Structured parse of a boundary heading.
HEAD_PARSE = re.compile(
    r"^###\s+(?P<struck>~~)?(?P<original>\(original\)\s*)?"
    r"(?P<num>\d+)(?P<suffix>[a-z]?)\.\s*(?P<rest>.*)$")

# Terminal-status keywords, longest/most-specific first so matching is unambiguous.
STATUS_KWS = ["FULLY RESOLVED", "RESOLVED NEGATIVE", "RULED OUT", "CONFIRMED FAIL",
              "RESOLVED", "CLOSED", "CONFIRMED", "DIGITALLY CLOSED"]

# A status slot holding a provenance clause — the authoring trap that silently
# blocks archiving (28 of 144 headings, 11 AUG 2026). Advisory-linted.
PROVENANCE_RE = re.compile(r"^\s*(raised|opened|split out of)\b", re.I)


def heading_status(heading: str) -> str:
    """The status phrase (text after the LAST em-dash), or '' if none."""
    if EMDASH not in heading:
        return ""
    return heading.rsplit(EMDASH, 1)[1].strip()


def is_tombstone(heading: str) -> bool:
    """Already-archived ONLY if the heading carries the migration pointer.
    A bare `~~strikethrough~~` is NOT sufficient — see archive_sections._is_tombstone's
    docstring for the 30 JUN 2026 backlog that rule prevents."""
    return "full entry in [[" in heading


def matches_terminal(status: str, allow=None) -> bool:
    """Whole-token, anchored at the start of the status phrase. 'PARTIALLY_RESOLVED'
    will not match; 'RESOLVED NEGATIVE' matches RESOLVED."""
    for kw in (allow if allow is not None else STATUS_KWS):
        if re.match(re.escape(kw) + r"\b", status):
            return True
    return False


def split_blocks(lines):
    """Yield (start, end) for each question block. A block runs from its boundary
    heading to the next boundary heading, the Resolved-index section, or EOF —
    and stops NOWHERE else (no bare `## `, no non-numbered `### `)."""
    idxs = [i for i, ln in enumerate(lines)
            if QUESTION_HEAD.match(ln) or RESOLVED_INDEX.match(ln)]
    for k, i in enumerate(idxs):
        if not lines[i].startswith("### "):
            continue
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        yield i, end


def parse_heading(line: str):
    """Structured view of a boundary heading, or None if the line is not one.
    Returns dict(num:int, suffix:str, struck:bool, original:bool, title:str,
    status:str, terminal:bool, tombstone:bool). `title` is the heading text
    before the last em-dash (status slot excluded); `qlabel` renders `143a`."""
    m = HEAD_PARSE.match(line.rstrip("\n"))
    if not m:
        return None
    rest = m.group("rest")
    status = heading_status(line)
    title = rest.rsplit(EMDASH, 1)[0].strip() if EMDASH in rest else rest.strip()
    return {
        "num": int(m.group("num")),
        "suffix": m.group("suffix") or "",
        "qlabel": m.group("num") + (m.group("suffix") or ""),
        "struck": bool(m.group("struck")),
        "original": bool(m.group("original")),
        "title": title,
        "rest": rest,
        "status": status,
        "terminal": bool(status and matches_terminal(status)),
        "tombstone": is_tombstone(line),
    }


def is_live(head: dict) -> bool:
    """A block is LIVE iff it is none of: terminal-status, migration tombstone,
    hand-struck (`### ~~31. …~~` — a hand-marked tombstone even without the
    migration pointer), or a preserved `(original)` earlier wording."""
    return not (head["terminal"] or head["tombstone"]
                or head["struck"] or head["original"])


def question_files(vault):
    """Every LIVE question file: Open_Questions*.md minus the resolved/archive
    stores and minus the generated index (which matches its own glob)."""
    out = []
    for p in sorted(glob.glob(os.path.join(str(vault), "Open_Questions*.md"))):
        base = os.path.basename(p)
        if "_Resolved" in base or "_Archive" in base or "_Index" in base:
            continue
        out.append(p)
    return out


def resolved_file(vault):
    return os.path.join(str(vault), "Open_Questions_Resolved.md")


def block_key(heading: str) -> str:
    """Identity for matching a block across copies: the TITLE, not the Q number
    (the vault has genuine duplicate Q96 / Q205)."""
    t = heading.rstrip("\n")[4:]
    if EMDASH in t:
        t = t.rsplit(EMDASH, 1)[0]
    return re.sub(r"[^a-z0-9]+", "", t.lower().replace("~~", ""))[:60]


def iter_questions(path):
    """Yield (start, end, head_dict, lines) for every question block in one file."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    for s, e in split_blocks(lines):
        h = parse_heading(lines[s])
        if h is None:
            continue
        yield s, e, h, lines


def next_free_number(vault) -> int:
    """The next free global Q integer: one above the highest number used in any
    live shard OR the Resolved store (numbers are never reused — the convention
    at the head of Open_Questions.md)."""
    highest = 0
    paths = question_files(vault)
    rf = resolved_file(vault)
    if os.path.exists(rf):
        paths = paths + [rf]
    for p in paths:
        for _s, _e, h, _lines in iter_questions(p):
            highest = max(highest, h["num"])
    return highest + 1


def find_live_blocks(vault, num, suffix=""):
    """Every LIVE (non-terminal, non-tombstone, non-original) block for a Q number
    across all shards: [(path, start, end, head, lines)]. More than one hit is a
    duplicate the caller should refuse to act on."""
    hits = []
    for p in question_files(vault):
        for s, e, h, lines in iter_questions(p):
            if h["num"] == num and h["suffix"] == suffix and is_live(h):
                hits.append((p, s, e, h, lines))
    return hits
