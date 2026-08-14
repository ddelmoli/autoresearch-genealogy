#!/usr/bin/env python3
"""
archive_sections.py — config-driven section archiver for growth-prone vault files.

Generalizes the single-purpose archive_next_session.py into one engine that keeps
several growth-prone files small, each via its own retention policy declared in an
OPTIONAL local config (vault/.maintenance.json). If the config is absent the engine
is a silent no-op, so the script is safe to ship upstream as dormant tooling; the
project-specific thresholds/targets live in the gitignored config.

Every mutation is:
  * VERSIONED   — a full timestamped snapshot of each touched file is written to the
                  target's snapshot_dir BEFORE any edit (nothing is ever lost; git
                  history sits on top of that).
  * IDEMPOTENT  — re-running with nothing to archive is a no-op.
  * DRY-RUN by default — pass --apply to actually write.

Policies (config "policy" field):
  keep-n-recent   keep the newest N "## " sections + any pinned sections, archive the
                  rest. (The Handoff keep-n-recent behavior, ported verbatim.)
  drop-by-status  (Open_Questions) move full "### N." question blocks whose HEADING
                  status (text after the last em-dash) is a terminal status, into the
                  archive_file, and record ONE terse line per question in a single
                  "## Resolved & Closed — Index" section (adopted 01 JUL 2026, replacing
                  the old per-question inline struck-heading tombstones — 0 wikilinks
                  depended on the in-file anchors). Keeps OPEN / NEW / OPENED / PARTIALLY_*
                  / BRICK WALL etc. (allowlist, never denylist → never archives a live
                  question). Status is read from the HEADING ONLY (a resolved body is
                  full of the words RESOLVED/CLOSED/RULED-OUT — see Q19). Convert legacy
                  inline tombstones to the index with --migrate-tombstones.
  drop-older-rows (Research_Log) keep the newest N rows of a markdown table under a
                  named section, archive the older rows. Pinned headers stay.

Usage:
  python3 scripts/archive_sections.py [--target NAME | --all] [--apply]
  python3 scripts/archive_sections.py --list      # show targets + current sizes

Default (no --apply): dry-run. Default target selection: --all.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_config

ROOT = Path(__file__).resolve().parent.parent
_V = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
VAULT = Path(_V) if _V else None
CONFIG = (VAULT / ".maintenance.json") if VAULT else None


def est_tokens(text: str) -> int:
    """Rough token estimate: bytes / 4 (matches the premise-check measurements)."""
    return len(text.encode("utf-8")) // 4


def load_config() -> dict:
    if not CONFIG.exists():
        return {}
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def snapshot(path: Path, snapshot_dir: str, ts: str) -> Path:
    d = VAULT / snapshot_dir
    d.mkdir(parents=True, exist_ok=True)
    snap = d / f"{path.stem}_{ts}{path.suffix}"
    snap.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return snap


def obsidian_anchor(heading_text: str) -> str:
    """Slugify a heading the way the existing manual tombstones do (title-only,
    pre-status): lowercase, drop punctuation, spaces->hyphens."""
    s = heading_text.strip().strip("~").strip()
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s)      # drop . , : ( ) + / ' etc. (keep word chars, space, -)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s)
    return s


# --------------------------------------------------------------------------------------
# policy: keep-n-recent  (ported from archive_next_session.py)
# --------------------------------------------------------------------------------------
_POINTER_RE = re.compile(r"^> \*\*Archive:\*\*.*?(?:\n>.*)*\n\n", re.M)


def plan_keep_n_recent(text: str, cfg: dict):
    keep = cfg.get("keep", 5)
    pinned = cfg.get("pinned_patterns", [])
    pin_re = [re.compile(p, re.I) for p in pinned]
    lines = text.splitlines(keepends=True)

    sec_starts = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    if not sec_starts:
        return None, "no '## ' sections", []

    head = "".join(lines[: sec_starts[0]])
    head = _POINTER_RE.sub("", head)
    if not head.endswith("\n\n"):
        head = head.rstrip("\n") + "\n\n"

    sections = []
    for j, s in enumerate(sec_starts):
        e = sec_starts[j + 1] if j + 1 < len(sec_starts) else len(lines)
        sections.append({"header": lines[s].rstrip("\n"), "text": "".join(lines[s:e])})

    def is_pinned(h):
        return any(r.search(h) for r in pin_re)

    pinned_idx = [k for k, sec in enumerate(sections) if is_pinned(sec["header"])]
    session_idx = [k for k, sec in enumerate(sections) if not is_pinned(sec["header"])]
    keep_idx = set(pinned_idx) | set(session_idx[:keep])
    drop_idx = session_idx[keep:]

    dropped = [sections[k]["header"][:96] for k in drop_idx]
    if not drop_idx:
        return None, f"{len(session_idx)} session section(s) <= keep ({keep})", []

    ts_note = "{TS}"
    pointer = (
        f"> **Archive:** trimmed to the {keep} most recent session sections. "
        f"Full prior history is versioned in `vault/{cfg['snapshot_dir']}/` "
        f"(latest snapshot: `{Path(cfg['file']).stem}_{ts_note}{Path(cfg['file']).suffix}`).\n\n"
    )
    kept = [sec["text"] for k, sec in enumerate(sections) if k in keep_idx]
    new_text = head + pointer + "".join(kept)
    return new_text, None, dropped


# --------------------------------------------------------------------------------------
# policy: drop-by-status  (Open_Questions)
# --------------------------------------------------------------------------------------
EMDASH = "—"

# The ONE trailing `## ` section that is not question content -- the compact index this
# tool itself writes (INDEX_HEADING below, plus its "(full text in [[…]])" suffix). A
# question block stops here and at no other `## `; see _split_h3_blocks. Kept identical
# to gen_question_index.RESOLVED_INDEX so the reader and the writer cut in one place.
RESOLVED_INDEX = re.compile(r"^##\s+Resolved\s*&\s*Closed", re.I)


def _split_h3_blocks(lines):
    """Yield (start, end) for each '### ' block (ends at the next '### ', at the
    Resolved-index section, or EOF).

    ⛔ IT MUST NOT STOP AT *ANY* `## `, WHICH IS WHAT THIS FUNCTION DID UNTIL 14 AUG
    2026. Questions legitimately CONTAIN `## ` sub-headings -- the `## ✅ RESOLVED …`
    / `## ⏩ WORKED …` / `## 📏 RE-MEASURED …` blocks this vault writes into a question
    body -- so every archivable block truncated to its heading plus one blank line.
    THE ARCHIVER IS A WRITER, so the consequence was worse than a mis-measurement: it
    would have moved a 2-line stub to the Resolved file, DELETED the heading, and left
    the entire resolution write-up orphaned in the live file under no question at all.
    Measured on the two DUE targets: 10 of 10 archivable blocks truncated, 1,065 lines
    would have been orphaned (Q236 alone: moves 2, should move 202).

    This is the SAME defect `gen_question_index.py` was fixed for on 12 AUG 2026
    (fa6793a) -- the READER was corrected and the WRITER was not. When a structure has
    two parsers, fix both or neither; see the memory note "two readers, one entry".
    """
    idxs = [i for i, ln in enumerate(lines)
            if ln.startswith("### ") or RESOLVED_INDEX.match(ln)]
    for k, i in enumerate(idxs):
        if not lines[i].startswith("### "):
            continue
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        yield i, end


def _heading_status(heading: str):
    """Return the status phrase (text after the LAST em-dash) of a '### ' heading,
    or '' if the heading carries no em-dash status segment."""
    if EMDASH not in heading:
        return ""
    return heading.rsplit(EMDASH, 1)[1].strip()


def _is_tombstone(heading: str) -> bool:
    """A block is already-archived ONLY if its heading carries the migration pointer
    ('full entry in [[...]]'). A bare '### ~~strikethrough~~' is NOT sufficient:
    sessions routinely hand-strike a freshly-resolved heading (### ~~Title~~ — RESOLVED)
    expecting it to archive — but if a plain strikethrough counted as a tombstone the
    engine would skip it forever and the full body would never migrate (the 30 JUN 2026
    backlog: 12 fat resolved entries stuck inline, file 24k tokens over threshold while
    the engine reported 'nothing to archive'). Keying on the pointer instead lets a
    hand-struck-but-unlinked resolved heading migrate normally; plan_drop_by_status
    strips any residual '~~' from the title so the rewritten tombstone is well-formed."""
    return "full entry in [[" in heading


def _matches_terminal(status: str, allow) -> bool:
    """Whole-token, anchored at the start of the status phrase. 'PARTIALLY_RESOLVED'
    will not match (it starts with PARTIALLY); 'RESOLVED NEGATIVE' matches RESOLVED."""
    for kw in allow:
        if re.match(re.escape(kw) + r"\b", status):
            return True
    return False


# --------------------------------------------------------------------------------------
# HEADING LINT (added 11 AUG 2026) — the trap that hides a RESOLVED question from this tool.
#
# `_heading_status` reads the status as the text after the LAST em-dash. A heading whose
# last segment is a PROVENANCE clause ("— raised 05 AUG 2026 (session #144)") therefore
# reports that clause as its status, and no terminal keyword ever matches — so when the
# question is later resolved by inserting "— RESOLVED <date>" BEFORE the stable trailing
# provenance, the block silently stops being archivable.
#
# ** THIS IS NOT HYPOTHETICAL. ** Q188 and Q219 were both fully resolved on 09 AUG 2026 and
# both sat live because of exactly this, and a scan on 11 AUG found the shape in 28 of 144
# numbered questions (19%) — 2 blocked, 26 latent. It is the same class of failure as the
# 30 JUN 2026 backlog in `_is_tombstone`: the engine reporting "nothing to archive" while
# resolved blocks pile up inline and the file runs over threshold.
#
# ⛔ THE FIX BELONGS AT THE AUTHORING END, NOT HERE. Widening the detector to accept a
# terminal status in ANY em-dash segment was considered and REJECTED on measurement: it
# would archive Q134 and Q254, both LIVE, because their headings cite ANOTHER question's
# status ("split out of the RESOLVED Q195"). The last-em-dash rule is correct; what is
# needed is a warning when a heading is authored into the trap. Hence: advisory only.
_PROVENANCE_RE = re.compile(r"^\s*(raised|opened|split out of)\b", re.I)


def _block_key(heading: str) -> str:
    """Identity for matching a stored block to its pre-archive snapshot: the TITLE, not
    the Q number. ⚠ The number is NOT unique -- this vault has genuine duplicate Q96 and
    Q205 (upsert_index keys on the anchor for the same reason). Keying on the number
    matched each duplicate against the OTHER one's snapshot and reported both as
    truncated: 2 false positives of 11."""
    t = heading.rstrip("\n")[4:]
    if EMDASH in t:
        t = t.rsplit(EMDASH, 1)[0]
    return re.sub(r"[^a-z0-9]+", "", t.lower().replace("~~", ""))[:60]


def _snapshot_bodies(vault):
    """Largest pre-archive body seen for each block key, across every question snapshot.
    The snapshot is written BEFORE the archive edits, so it holds the full block."""
    out = {}
    for sp in sorted((vault / "Open_Questions_Archive").glob("*.md")):
        if "Resolved" in sp.name:
            continue
        lines = sp.read_text(encoding="utf-8").splitlines(keepends=True)
        for s, e in _split_h3_blocks(lines):
            k = _block_key(lines[s])
            if len(k) < 12:
                continue
            body = {l.strip() for l in lines[s + 1:e] if l.strip() and l.strip() != "---"}
            if k not in out or len(body) > len(out[k]):
                out[k] = body
    return out


def lint_archive(vault, slack=3):
    """Report archived questions whose stored write-up is MISSING or SHORTER than the
    pre-archive snapshot -- i.e. the migration moved a heading and left the resolution
    behind. Returns (empty_rows, truncated_rows).

    ⚠ WHY A STUB COUNT ALONE IS NOT ENOUGH, measured 14 AUG 2026: of the 8 questions
    whose write-ups were orphaned by the pre-fix archiver, only ONE stored a completely
    empty body and one a single line. The other six stored 10-23 plausible-looking lines
    -- the question and its opening statement -- and read as ordinary short resolutions.
    Q265 stored its *"⏭ WHAT WOULD SETTLE IT"* research plan under a `— RESOLVED`
    heading, which is worse than empty: it invites the work to be redone. Only comparing
    against the snapshot finds those, so this check does both.

    KNOWN BASELINE 1, and it is a layout artifact rather than a defect: in the JULY 2026
    single-file register Q73 was the last question before three genuine top-level
    sections (`## Confirmed Brick Walls`, `## Data Acquisition Priorities`, `## FamilySearch
    Duplicate / Conflation Log`), so its snapshot block absorbs them and they read as
    'missing'. ⛔ Do NOT enumerate those titles into the splitter to force a 0 -- that is
    the flattering-direction trap, and the whole point of fa6793a is that only the
    Resolved index is a non-content `## `. READ THE ROWS.
    """
    apath = vault / "Open_Questions_Resolved.md"
    if not apath.exists():
        return [], []
    snaps = _snapshot_bodies(vault)
    lines = apath.read_text(encoding="utf-8").splitlines(keepends=True)
    empty, truncated = [], []
    for s, e in _split_h3_blocks(lines):
        head = lines[s].rstrip("\n")
        body = [l.strip() for l in lines[s + 1:e] if l.strip() and l.strip() != "---"]
        if not body:
            empty.append(head)
            continue
        k = _block_key(lines[s])
        want = snaps.get(k)
        if want:
            missing = want - set(body)
            if len(missing) > slack:
                truncated.append((len(missing), head))
    truncated.sort(key=lambda x: -x[0])
    return empty, truncated


def lint_headings(text):
    """Return [(qlabel, last_segment)] for numbered questions whose terminal-status slot
    holds a provenance clause instead of a status. Advisory: these are not errors today,
    they are questions that CANNOT ARCHIVE once resolved."""
    out = []
    lines = text.splitlines(keepends=True)
    for start, _end in _split_h3_blocks(lines):
        heading = lines[start].rstrip("\n")
        m = re.match(r"###\s*(\d+)\.", heading)
        if not m or _is_tombstone(heading):
            continue
        last = _heading_status(heading)
        if _PROVENANCE_RE.match(last):
            out.append((m.group(1), last))
    return out


def _trailer_split(block_lines):
    """Split block into (heading_line, body_lines, trailer_lines) where trailer is the
    trailing run of blank / '---' lines."""
    heading = block_lines[0]
    rest = block_lines[1:]
    t = len(rest)
    while t > 0 and (rest[t - 1].strip() == "" or rest[t - 1].strip() == "---"):
        t -= 1
    return heading, rest[:t], rest[t:]


# --------------------------------------------------------------------------------------
# Compact Resolution Index (adopted 01 JUL 2026, replacing per-question inline tombstones)
# Instead of leaving a struck-through heading where each resolved question used to sit,
# the engine removes the block entirely and records ONE terse line in a single
# "## Resolved & Closed — Index" section. 0 wikilinks depend on the in-file anchors, so
# nothing breaks; the index preserves grep discoverability + the direct Resolved-file link
# in one consolidated, sorted place. Convert legacy inline tombstones with
# --migrate-tombstones.
# --------------------------------------------------------------------------------------
INDEX_HEADING = "## Resolved & Closed — Index"
_INDEX_ROW_RE = re.compile(r"^- \*\*Q(?P<q>[^*]+)\*\*.*?#(?P<anchor>[^\]]+)\]\]")
# terminal-status keywords, longest/most-specific first so the search below is unambiguous
_STATUS_KWS = ["FULLY RESOLVED", "RESOLVED NEGATIVE", "RULED OUT", "CONFIRMED FAIL",
               "RESOLVED", "CLOSED", "CONFIRMED", "DIGITALLY CLOSED"]


def _clean_short_title(title: str) -> str:
    """Short topic for the index: text before the first em-dash, minus the leading
    'NN. ' question number (re-shown as the bold Q label)."""
    short = title.split(EMDASH, 1)[0].strip()
    short = re.sub(r"^\d+[.)]\s*", "", short).strip()
    return short


def _qsort_key(qlabel: str):
    m = re.match(r"\d+", qlabel)
    return (0, int(m.group())) if m else (1, qlabel)


def _index_line(qlabel, short_title, status_kw, anchor, link) -> str:
    return f"- **Q{qlabel}** {short_title} ({status_kw}) {EMDASH} [[{link}#{anchor}]]\n"


def upsert_index(text: str, rows, link: str) -> str:
    """Insert/merge compact-index rows into the '## Resolved & Closed — Index' section
    (create at EOF if absent). rows = [(qlabel, short_title, status_kw, anchor)]. Keyed on
    the unique ANCHOR (not the Q number — the vault has a genuine duplicate Q96), so a
    re-archive of the same question updates in place while distinct same-number questions
    both survive; sorted by numeric Q. Idempotent."""
    if not rows:
        return text
    heading_line = f"{INDEX_HEADING} (full text in [[{link}]])\n"
    lines = text.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.startswith(INDEX_HEADING)), None)
    existing = {}   # anchor -> (qlabel, line)
    if start is not None:
        # ⚠ THE SECTION ENDS AT THE NEXT HEADING OF *ANY* LEVEL, NOT AT THE NEXT `## `.
        # Until 14 AUG 2026 this scanned for `## ` alone -- and a `### N.` question
        # heading does not start with `## `, so a question written BELOW the index ran
        # to EOF as "index content" and was DESTROYED when the section was rebuilt.
        # Measured live: a question raised the previous day (27 lines) was deleted
        # outright by an ordinary archive run of an unrelated question. The
        # index is appended at EOF when absent, so anything appended after it later
        # sits in the blast radius -- this is not an exotic layout.
        # Index rows are `- **Q…**` bullets and never start with '#', so any heading
        # is a safe terminator.
        end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("#")),
                   len(lines))
        for ln in lines[start:end]:
            m = _INDEX_ROW_RE.match(ln)
            if m:
                existing[m.group("anchor").strip()] = (m.group("q").strip(),
                                                       ln if ln.endswith("\n") else ln + "\n")
        body_before, body_after = lines[:start], lines[end:]
    else:
        body_before, body_after = lines, []
    for q, st, kw, anc in rows:
        existing[anc] = (q, _index_line(q, st, kw, anc, link))
    ordered = [v[1] for v in sorted(existing.values(), key=lambda v: _qsort_key(v[0]))]
    section = [heading_line, "\n"] + ordered + ["\n"]
    pre = "".join(body_before)
    if start is None and pre:                       # appending fresh at EOF -> ensure gap
        pre = pre.rstrip("\n") + "\n\n"
    return pre + "".join(section) + "".join(body_after)


def _extract_status(heading: str) -> str:
    """Best-effort terminal-status keyword from a tombstone heading (tolerant of a ';' or
    em-dash inside the status parenthetical)."""
    for kw in _STATUS_KWS:
        if re.search(r"\b" + re.escape(kw) + r"\b", heading):
            return kw
    return "RESOLVED"


def _tomb_parse(heading: str):
    """Parse a legacy inline tombstone heading -> (title, anchor) or (None, None).
    Tolerant of: strikethrough OR plain heading; a ';' / em-dash inside the status; and a
    link with NO #anchor (older Q14/36/38 point at the file only -> synthesize the anchor
    from the title, the same slug convention the anchored tombstones already use)."""
    ts = re.search(r"~~(.*?)~~", heading)          # strikethrough title if present
    if ts:
        title = ts.group(1).strip()
    else:                                          # hand-made tombstone w/o '~~' (e.g. Q99)
        title = heading[len("### "):]
        if EMDASH in title:
            title = title.split(EMDASH, 1)[0]
        title = title.strip()
    if not title:
        return None, None
    m = re.search(r"full entry in \[\[[^#\]]+#(?P<anchor>[^\]]+)\]\]", heading)
    anchor = m.group("anchor").strip() if m else obsidian_anchor(title)
    return title, (anchor or None)


def migrate_tombstones(text: str, link: str):
    """One-time back-fill: convert existing inline tombstones into compact-index rows,
    removing the struck headings. Returns (new_text, [labels], n_unmatched_tombstones)."""
    lines = text.splitlines(keepends=True)
    rows, edits, unmatched = [], [], 0
    for start, end in _split_h3_blocks(lines):
        heading = lines[start].rstrip("\n")
        if not _is_tombstone(heading):
            continue
        title, anchor = _tomb_parse(heading)
        if not title or not anchor:
            unmatched += 1
            continue
        rows.append((title.split(".", 1)[0].strip(), _clean_short_title(title),
                     _extract_status(heading), anchor))
        edits.append((start, end, ""))
    if not edits:
        return text, [], unmatched
    new_lines = list(lines)
    for start, end, repl in sorted(edits, key=lambda e: -e[0]):
        new_lines[start:end] = [repl]
    new_text = upsert_index("".join(new_lines), rows, link)
    return new_text, [f"Q{q}" for q, s, k, a in rows], unmatched


def plan_drop_by_status(text: str, cfg: dict, ts: str):
    allow = cfg.get("archive_statuses", [])
    link = cfg.get("tombstone_link", "Open_Questions_Resolved")
    lines = text.splitlines(keepends=True)

    moved = []          # list of (qlabel, status_kw, anchor, full_block_text)
    index_rows = []     # list of (qlabel, short_title, status_kw, anchor)
    edits = []

    for start, end in _split_h3_blocks(lines):
        heading = lines[start].rstrip("\n")
        if _is_tombstone(heading):
            continue
        status = _heading_status(heading)
        if not status or not _matches_terminal(status, allow):
            continue
        # archive this block
        block_lines = lines[start:end]
        hline, body, trailer = _trailer_split(block_lines)
        # title = heading text between "### " and the last em-dash
        title = hline.rstrip("\n")[len("### "):]
        if EMDASH in title:
            title = title.rsplit(EMDASH, 1)[0]
        # drop any residual strikethrough markers so a hand-struck heading
        # (### ~~Title~~ — RESOLVED) yields a clean tombstone, not ~~~~Title~~~~
        title = title.replace("~~", "").strip()
        status_kw = next((k for k in allow if re.match(re.escape(k) + r"\b", status)), status.split()[0])
        anchor = obsidian_anchor(title)
        qlabel = title.split(".", 1)[0].strip()

        # Remove the block entirely (no inline tombstone); the compact index carries the
        # pointer. Legacy inline tombstones are converted separately by --migrate-tombstones.
        edits.append((start, end, ""))
        moved.append((qlabel, status_kw, anchor, "".join(block_lines)))
        index_rows.append((qlabel, _clean_short_title(title), status_kw, anchor))

    if not edits:
        return None, None, []

    # apply edits back-to-front so indices stay valid
    new_lines = list(lines)
    for start, end, repl in sorted(edits, key=lambda e: -e[0]):
        new_lines[start:end] = [repl]
    new_live = upsert_index("".join(new_lines), index_rows, link)
    return new_live, moved, [f"Q{q} ({kw})" for q, kw, a, _ in moved]


# Compact Resolution Index rows for entries kept full-text in the live file carry a
# "Full text at Q## in [[Open_Questions]]" back-pointer. When such an entry is migrated,
# that pointer must be retargeted to the migrated block (else it loops to a tombstone).
def _backpointer_re(qlabel: str):
    return re.compile(r"Full text at Q" + re.escape(qlabel) + r" in \[\[Open_Questions\]\]")


def rewrite_index_backpointers(archive_text: str, blocks) -> tuple:
    """Retarget each migrated entry's Compact-Index back-pointer to its new in-file
    anchor. Returns (new_text, count_rewritten)."""
    count = 0
    for q, kw, anchor, _ in blocks:
        new = f"Full text at Q{q} in [[Open_Questions_Resolved#{anchor}]]"
        archive_text, n = _backpointer_re(q).subn(new, archive_text)
        count += n
    return archive_text, count


def count_index_backpointers(archive_text: str, blocks) -> int:
    return sum(len(_backpointer_re(q).findall(archive_text)) for q, kw, a, _ in blocks)


def insert_into_archive(archive_text: str, blocks, insert_before: str, ts: str) -> str:
    """Retarget back-pointers, then insert the moved blocks before insert_before (or EOF)."""
    archive_text, _ = rewrite_index_backpointers(archive_text, blocks)
    addition = ""
    for q, kw, anchor, block in blocks:
        b = block if block.endswith("\n") else block + "\n"
        if not b.rstrip().endswith("---"):
            b = b.rstrip("\n") + "\n\n---\n"
        addition += b + "\n"
    marker = f"<!-- archived from Open_Questions.md {ts} -->\n"
    addition = marker + addition

    if insert_before and insert_before in archive_text:
        i = archive_text.index(insert_before)
        return archive_text[:i] + addition + "\n" + archive_text[i:]
    return archive_text.rstrip("\n") + "\n\n" + addition


# --------------------------------------------------------------------------------------
# policy: drop-older-rows  (Research_Log Session Index)
# --------------------------------------------------------------------------------------
def plan_drop_older_rows(text: str, cfg: dict):
    section = cfg.get("table_section", "## Session Index")
    keep_rows = cfg.get("keep_rows", 40)
    lines = text.splitlines(keepends=True)
    try:
        sec_i = next(i for i, ln in enumerate(lines) if ln.rstrip("\n") == section)
    except StopIteration:
        return None, f"section '{section}' not found", []

    # table rows = contiguous lines starting with '|' after the section header,
    # excluding the header row and the |---| separator.
    row_idxs = [i for i in range(sec_i, len(lines)) if lines[i].lstrip().startswith("|")]
    data_rows = [i for i in row_idxs if not re.match(r"^\s*\|[\s:\-|]+\|\s*$", lines[i])]
    # first data row is the column header — keep it
    if len(data_rows) <= 1 + keep_rows:
        return None, f"{max(0, len(data_rows) - 1)} data row(s) <= keep ({keep_rows})", []

    header_row = data_rows[0]
    body_rows = data_rows[1:]
    drop = body_rows[:-keep_rows]  # rows are ascending (oldest first) → drop the oldest
    drop_set = set(drop)
    dropped = [lines[i].strip()[:80] for i in drop]
    new_lines = [ln for i, ln in enumerate(lines) if i not in drop_set]
    return "".join(new_lines), None, dropped


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------
def run_target(t: dict, apply: bool, ts: str):
    path = VAULT / t["file"]
    if not path.exists():
        print(f"  [{t['name']}] {t['file']} not found — skip")
        return
    text = path.read_text(encoding="utf-8")
    toks = est_tokens(text)
    thr = t.get("threshold_tokens", 0)
    over = toks >= thr
    print(f"\n=== {t['name']} ({t['file']}) — ~{toks:,} tokens "
          f"(threshold {thr:,}; {'OVER' if over else 'under'}) ===")

    policy = t["policy"]
    archive_blocks = None
    if policy == "keep-n-recent":
        new_text, why, dropped = plan_keep_n_recent(text, t)
    elif policy == "drop-by-status":
        new_text, archive_blocks, dropped = plan_drop_by_status(text, t, ts)
        why = None if new_text else "nothing to archive"
    elif policy == "drop-older-rows":
        new_text, why, dropped = plan_drop_older_rows(text, t)
    else:
        print(f"  unknown policy '{policy}' — skip")
        return

    if new_text is None:
        print(f"  nothing to do ({why}).")
        return

    new_toks = est_tokens(new_text.replace("{TS}", ts))
    print(f"  would archive {len(dropped)} item(s); live file ~{toks:,} -> ~{new_toks:,} tokens "
          f"(-{toks - new_toks:,})")
    if policy == "drop-by-status" and archive_blocks:
        apath = VAULT / t["archive_file"]
        if apath.exists():
            n_bp = count_index_backpointers(apath.read_text(encoding="utf-8"), archive_blocks)
            print(f"  would retarget {n_bp} Compact-Index back-pointer(s) to the migrated block(s)")
    for d in dropped[:60]:
        print(f"    - {d}")
    if len(dropped) > 60:
        print(f"    ... and {len(dropped) - 60} more")

    if not apply:
        print("  [dry-run] no files written. Re-run with --apply to commit the move.")
        return

    # APPLY
    snap = snapshot(path, t["snapshot_dir"], ts)
    print(f"  snapshot: {snap.relative_to(ROOT)}")
    final_live = new_text.replace("{TS}", ts)

    if policy == "drop-by-status" and archive_blocks:
        apath = VAULT / t["archive_file"]
        if apath.exists():
            snapshot(apath, t["snapshot_dir"], ts)
            atext = apath.read_text(encoding="utf-8")
        else:
            atext = f"# {apath.stem.replace('_', ' ')}\n\n"
        atext = insert_into_archive(atext, archive_blocks, t.get("archive_insert_before", ""), ts)
        apath.write_text(atext, encoding="utf-8")
        print(f"  appended {len(archive_blocks)} block(s) -> {apath.relative_to(ROOT)}")

    path.write_text(final_live, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", help="run a single target by name")
    ap.add_argument("--all", action="store_true", help="run all configured targets (default)")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry-run)")
    ap.add_argument("--list", action="store_true", help="list targets + current sizes and exit")
    ap.add_argument("--migrate-tombstones", action="store_true",
                    help="one-time: convert existing inline tombstones to the compact "
                         "'## Resolved & Closed — Index' (drop-by-status targets)")
    ap.add_argument("--lint-headings", action="store_true",
                    help="advisory: report question headings whose terminal-status slot holds a "
                         "provenance clause ('— raised <date>'), which silently blocks archiving "
                         "once the question is resolved")
    ap.add_argument("--lint-archive", action="store_true",
                    help="advisory: report archived questions whose stored write-up is EMPTY "
                         "or shorter than its pre-archive snapshot (a migration that moved the "
                         "heading and left the resolution behind)")
    args = ap.parse_args()

    if args.lint_archive:
        empty, truncated = lint_archive(VAULT)
        # aggregate FIRST, for the same banner reason as --lint-headings above
        print(f"ARCHIVE_LINT: EMPTY {len(empty)}  TRUNCATED {len(truncated)}  "
              f"[advisory; EMPTY baseline 0. TRUNCATED baseline is vault-specific -- a "
              f"question that preceded genuine top-level sections in an older file layout "
              f"reads as truncated. READ THE ROWS; see lint_archive docstring]")
        for h in empty:
            print(f"  EMPTY      (stored body has NO lines) {h[:105]}")
        for n, h in truncated:
            print(f"  TRUNCATED  ({n} snapshot lines absent from the store) {h[:105]}")
        return 0

    if args.lint_headings:
        cfg = load_config()
        rc = 0
        # ⚠⚠ THE TOTAL IS PRINTED FIRST, AND THAT IS LOAD-BEARING (12 AUG 2026, the
        # lineage shard split). The SessionStart banner reads this with `max_lines=1`,
        # so it takes whatever line comes FIRST. While the register was one file that
        # was the only line and the reading was honest. After the split there are seven
        # files, the ALPHABETICALLY-FIRST is `Open_Questions.md` -- the ROUTER, which
        # holds no `### N.` question blocks at all -- so a per-file line would have
        # reported a permanent, structural **0 from an empty file** and hidden a real
        # non-zero in any shard. A gate that cannot move is not a gate.
        # Emitting the aggregate first keeps the banner one line AND keeps it truthful;
        # the per-file breakdown still follows for a human reading the full output.
        per_file = []
        for t in cfg.get("targets", []):
            if t.get("policy") != "drop-by-status":
                continue
            path = VAULT / t["file"]
            if not path.exists():
                continue
            per_file.append((t["file"], lint_headings(path.read_text(encoding="utf-8"))))
        total = sum(len(h) for _, h in per_file)
        print(f"HEADING_LINT: {total}  [advisory]  across {len(per_file)} question file(s)"
              "  (terminal-status slot holds a provenance clause -> cannot archive when resolved)")
        for fname, hits in per_file:
            print(f"  HEADING_LINT ({fname}): {len(hits)}")
            for q, last in hits:
                print(f"    Q{q}: last em-dash segment = {last[:70]!r}")
            if hits:
                print("    FIX: move the clause into the title, e.g. "
                      "'### N. Title (raised <date>, session #N) — RESOLVED <date>'.")
        return rc

    cfg = load_config()
    targets = cfg.get("targets", [])
    if not targets:
        print("No vault/.maintenance.json targets configured — nothing to do (no-op).")
        return 0

    if args.migrate_tombstones:
        ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
        chosen = [t for t in targets if t["name"] == args.target] if args.target else targets
        print(f"archive_sections.py — MIGRATE-TOMBSTONES — {'APPLY' if args.apply else 'DRY-RUN'}")
        for t in chosen:
            if t.get("policy") != "drop-by-status":
                continue
            path = VAULT / t["file"]
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            link = t.get("tombstone_link", "Open_Questions_Resolved")
            new_text, labels, unmatched = migrate_tombstones(text, link)
            print(f"\n=== {t['name']} ({t['file']}) ===")
            print(f"  would convert {len(labels)} inline tombstone(s) -> compact index"
                  + (f"; {unmatched} tombstone(s) did NOT match the parser (left in place)" if unmatched else ""))
            print(f"  ~{est_tokens(text):,} -> ~{est_tokens(new_text):,} tokens")
            if labels:
                print("    " + ", ".join(labels[:80]) + (" ..." if len(labels) > 80 else ""))
            if args.apply and labels:
                snapshot(path, t["snapshot_dir"], ts)
                path.write_text(new_text, encoding="utf-8")
                print(f"  wrote {path.relative_to(ROOT)}")
        if not args.apply:
            print("\nDry-run. Add --apply to write.")
        return 0

    if args.list:
        for t in targets:
            p = VAULT / t["file"]
            toks = est_tokens(p.read_text(encoding="utf-8")) if p.exists() else 0
            thr = t.get("threshold_tokens", 0)
            flag = "OVER" if toks >= thr else "ok"
            print(f"  {t['name']:<16} {t['file']:<22} ~{toks:>7,} tok  (thr {thr:,}) [{flag}]  {t['policy']}")
        return 0

    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    chosen = [t for t in targets if t["name"] == args.target] if args.target else targets
    if args.target and not chosen:
        print(f"no target named '{args.target}'. Configured: {', '.join(t['name'] for t in targets)}")
        return 1

    print(f"archive_sections.py — {'APPLY' if args.apply else 'DRY-RUN'} — {len(chosen)} target(s)")
    for t in chosen:
        run_target(t, args.apply, ts)
    if not args.apply:
        print("\nDry-run complete. Add --apply (optionally --target NAME) to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
