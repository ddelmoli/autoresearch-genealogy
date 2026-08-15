#!/usr/bin/env python3
"""gen_question_index.py — a readable INDEX of the live open questions.

** WHY THIS EXISTS, AND IT IS A MEASURED FAILURE. ** The question register grew to
**~800 KB / ~206k tokens across ~148 live questions**, which is larger than a single
context. It cannot be read: the per-read cap forces ~14 sequential reads whose early
chunks are evicted before the later ones land, so a "full read" yields LESS of the
picture, not more. A session that wants to pick work therefore cannot see the work.

The register also carried a stale self-description — the vault's own context rule said
"~310 KB" when the file was 803 KB, i.e. **2.6x out of date**. A number nobody
regenerates is a number that lies.

** THE FIX IS A GENERATED VIEW, NOT A SECOND STORE. ** Same precedent as the retired
`Person_Index.md`: the question BODIES stay the source of truth and the index is
regenerated on demand, so it cannot drift. Do NOT hand-maintain the output.

** IT GLOBS FROM DAY ONE. ** `Open_Questions*.md` (minus `_Resolved` / `_Archive`) is
read, so the later shard split needs no change here — the index simply spans the shards
and reports which file each question lives in.

⚠ ** RESOLVED-DETECTION IS IMPORTED, NEVER REIMPLEMENTED. ** `_heading_status` +
`_matches_terminal` come from `archive_sections`, so the index and the archiver cannot
disagree about which questions are live. Reimplementing the "last em-dash" rule here is
exactly how the two would drift, and the trailing-provenance trap (28 of 144 headings,
11 AUG 2026) shows how subtle that rule is.

⚠ ** THE TAGS ARE A TRIAGE HINT, NOT A CLASSIFICATION. ** They are keyword-derived and
therefore carry the substring hazard this vault has documented before (`igi` inside
"original"; a lineage classifier that filed a Massachusetts question under ITALIAN
because `atto` sits inside ordinary place names). Use them to sort a worklist; never to
decide what a question IS, and never to assign a shard.

Usage:
    python3 scripts/gen_question_index.py                 # print the index
    python3 scripts/gen_question_index.py --write PATH    # write it
    python3 scripts/gen_question_index.py --tag UNREAD-SRC  # filter
    python3 scripts/gen_question_index.py --heartbeat     # one line for the banner
"""
import os
import re
import sys
import glob
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import vault_config
import question_block as QB

# ⚠ THE BLOCK GRAMMAR IS IMPORTED FROM question_block, NEVER REIMPLEMENTED — the
# boundary rule as well as the status rule (until 15 AUG 2026 only the STATUS was
# shared; the two boundary parsers diverged on `### 143a.` / `### (original) N.`,
# which made a live sub-question invisible and misattributed its content to the
# preceding question's row).
# provenance clause at the end of a title: "(raised 12 AUG 2026, session #162, ...)"
RAISED = re.compile(r"\s*\((?:raised|opened|migrated)\b[^)]*\)", re.I)

# Triage tags. Keyword-derived — see the docstring warning.
TAGS = [
    ("UNREAD-SRC", re.compile(
        r"attached and (?:never |un)read|located,? (?:attached )?and (?:never |un)read"
        r"|never read|not (?:yet )?read|unread|cited but not read", re.I)),
    ("free", re.compile(
        r"archive\.org|CELT|FreeREG|FreeBMD|PRONI|JewishGen|Gesher|Antenati|metryki"
        r"|curl|_djvu|no login|free at\b|free to", re.I)),
    ("op-gated", re.compile(
        r"operator[- ]gated|needs an operator|operator ruling needed|in[- ]person"
        r"|diocesan archive|not digitis|not digitiz|paywall|subscription|JSTOR"
        r"|OpenAthens", re.I)),
]

# The actionable line: the first item under a "what would settle it" heading.
SETTLE_HDR = re.compile(r"(what would settle it|what is left|what would name|⏭\s*\*\*)", re.I)

# A row of the ROUTER's shard table in Open_Questions.md:
#   | [[Open_Questions_Method]] | 17 | CROSS-CUTTING questions: … |
# The count is GENERATED (this tool); the `covers` prose is HAND-WRITTEN and must
# survive an update — only the number moves.
ROUTER_ROW = re.compile(r"^(\|\s*\[\[(Open_Questions_\w+)\]\]\s*\|\s*)(\d+)(\s*\|.*)$")


def _clean(s, n):
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[*`~]|\[\[|\]\]", "", s)   # keep `_`: PARTIALLY_RESOLVED is meaningful
    return s[:n].strip()


def question_files(vault):
    """Every LIVE question file — delegated to question_block (one home). `_Index`
    is excluded because the generated index matches its own glob (a generated view
    that reads itself is a drift source, not a view)."""
    return QB.question_files(vault)


def parse(vault):
    """[(num, title, file, kb, tags, resolver)] for every LIVE question, all files.
    Boundary + liveness come from question_block: suffixed sub-questions
    (`### 143a.`) get their OWN row; `(original)` preserved wordings, tombstones
    and hand-struck headings are skipped."""
    rows = []
    for path in question_files(vault):
        lines = open(path, encoding="utf-8").read().split("\n")
        for a, b in QB.split_blocks(lines):
            head = lines[a]
            h = QB.parse_heading(head)
            if h is None or not QB.is_live(h):
                continue                      # resolved/preserved: the archiver owns it
            body = "\n".join(lines[a:b])
            title = RAISED.sub("", h["rest"])
            tags = [name for name, rx in TAGS if rx.search(body)]
            kb = len(body) / 1024
            if kb >= 15:
                tags.append("BIG")
            rows.append({
                "num": h["num"],
                "suffix": h["suffix"],
                "qlabel": h["qlabel"],
                "title": _clean(title, 96),
                "file": os.path.basename(path),
                "kb": kb,
                "tags": tags,
                "resolver": _resolver(body),
            })
    rows.sort(key=lambda r: (r["num"], r["suffix"]))
    return rows


def _resolver(body):
    """The first actionable step this question names, if any.

    Tried in order: (1) the first list item under a 'what would settle it' heading,
    (2) the first `⏭` next-step marker anywhere, (3) the first `**⏭ ...**` bold lead.
    ⚠ A miss renders as an em-dash and means ONLY that no line matched these shapes --
    it is NOT a claim that the question names no resolver. Open the question."""
    lines = body.split("\n")
    for i, l in enumerate(lines):
        if SETTLE_HDR.search(l):
            for nxt in lines[i:i + 10]:
                m = re.match(r"\s*(?:\d+\.|[-*])\s+(.{12,})", nxt)
                if m:
                    return _clean(m.group(1), 116)
    for l in lines:
        if "\u23ed" in l:
            frag = l.split("\u23ed", 1)[1]
            if len(_clean(frag, 200)) >= 12:
                return _clean(frag, 116)
    return ""


def render(rows, vault):
    w = []
    files = {}
    for r in rows:
        files.setdefault(r["file"], []).append(r)
    total_kb = sum(r["kb"] for r in rows)
    w.append("# Open Questions — INDEX (generated)\n")
    w.append("> ⚠ **GENERATED by `scripts/gen_question_index.py` — do NOT hand-edit.**")
    w.append("> The question BODIES are the source of truth; this is a view over them.")
    w.append("> Regenerate with `python3 scripts/gen_question_index.py --write "
             "<vault>/Open_Questions_Index.md`.\n")
    w.append(f"**{len(rows)} live questions, {total_kb:.0f} KB across "
             f"{len(files)} file(s).**\n")
    w.append("Tags are a **triage hint only** and are keyword-derived — "
             "`UNREAD-SRC` a source already located/attached but unread; "
             "`free` a free route is named; `op-gated` needs the operator; "
             "`BIG` the block is >=15 KB and is a shard candidate.\n")
    from collections import Counter
    c = Counter(t for r in rows for t in r["tags"])
    w.append("| tag | questions |")
    w.append("|---|---|")
    for k, n in c.most_common():
        w.append(f"| `{k}` | {n} |")
    w.append("")
    for fn in sorted(files):
        w.append(f"\n## {fn} — {len(files[fn])} live, "
                 f"{sum(r['kb'] for r in files[fn]):.0f} KB\n")
        w.append("| Q | KB | tags | title | first named resolver |")
        w.append("|---|---|---|---|---|")
        for r in files[fn]:
            w.append(f"| **Q{r['qlabel']}** | {r['kb']:.1f} | "
                     f"{' '.join('`'+t+'`' for t in r['tags']) or '—'} | "
                     f"{r['title']} | {r['resolver'] or '—'} |")
    return "\n".join(w) + "\n"


def update_router(vault, rows, write=False):
    """Refresh the live-Q counts in the ROUTER's shard table (Open_Questions.md),
    keeping the hand-written `covers` prose intact. Returns (n_updated, warnings).
    The hand-kept counts were a THIRD live-question number (disk 145 / index 134 /
    router 141 on 15 AUG 2026), agreeing with neither computed one — a number
    nobody regenerates is a number that lies."""
    path = os.path.join(vault, "Open_Questions.md")
    if not os.path.exists(path):
        return 0, ["router Open_Questions.md not found"]
    counts = {}
    for r in rows:
        counts[r["file"][:-3]] = counts.get(r["file"][:-3], 0) + 1
    lines = open(path, encoding="utf-8").read().split("\n")
    seen, n_upd, warnings = set(), 0, []
    for i, ln in enumerate(lines):
        m = ROUTER_ROW.match(ln)
        if not m:
            continue
        shard = m.group(2)
        seen.add(shard)
        want = counts.get(shard, 0)
        if int(m.group(3)) != want:
            lines[i] = f"{m.group(1)}{want}{m.group(4)}"
            n_upd += 1
    for shard in sorted(set(counts) - seen):
        warnings.append(f"shard {shard} ({counts[shard]} live) has NO router-table row "
                        f"— add one (the covers prose is yours to write)")
    if n_upd and write:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    return n_upd, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault")
    ap.add_argument("--write", metavar="PATH")
    ap.add_argument("--tag", help="only questions carrying this tag")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--router", action="store_true",
                    help="refresh the shard-table counts in Open_Questions.md "
                         "(the covers prose is preserved)")
    args = ap.parse_args()
    vault = vault_config.resolve_vault(args.vault)
    rows = parse(vault)
    if args.router:
        n, warnings = update_router(vault, rows, write=True)
        print(f"ROUTER: {n} count(s) updated in Open_Questions.md"
              + (f"; {len(warnings)} warning(s)" if warnings else ""))
        for w in warnings:
            print(f"  ⚠ {w}")
        return 0
    if args.tag:
        rows = [r for r in rows if args.tag in r["tags"]]
    if args.heartbeat:
        kb = sum(r["kb"] for r in rows)
        from collections import Counter
        c = Counter(t for r in rows for t in r["tags"])
        print(f"QUESTIONS: {len(rows)} live, {kb:.0f} KB across "
              f"{len(question_files(vault))} file(s); "
              f"UNREAD-SRC {c.get('UNREAD-SRC',0)}, BIG {c.get('BIG',0)}, "
              f"op-gated {c.get('op-gated',0)}")
        return 0
    out = render(rows, vault)
    if args.write:
        with open(args.write, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"wrote {args.write} ({len(out)/1024:.0f} KB, {len(rows)} questions)")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
