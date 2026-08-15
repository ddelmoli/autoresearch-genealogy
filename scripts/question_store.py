#!/usr/bin/env python3
"""question_store.py — the STRUCTURED WRITER for the Open_Questions register.

Create, resolve, and append to question blocks WITHOUT hand-editing the shard
files. Same rule and same reason as `log_session.py` ("append via the script,
NEVER via the Edit tool") and `person_store.set_meta_key`: every write-discipline
incident in the register's history — orphaned write-ups, zombie duplicates,
malformed status slots, wrong-file appends — happened while a session spliced
text into a 20-175 KB markdown file by hand. This tool locates the block through
the shared grammar (`question_block.py`), so a write cannot land outside it.

Operations (all dry-run by default; --apply writes):

  --new --shard SLUG --title T --resolver R [--body-file F] [--session N]
        Mint the next free GLOBAL Q number (live shards + Resolved store), write
        a canonical block at the end of the shard's questions (before the
        Resolved index). Provenance goes in the title parens; the status slot is
        left empty — it belongs to --resolve.
  --resolve QLABEL --status KW [--note TEXT]
        Rewrite the heading of the live block to `… — KW DD MON YYYY (note)` and
        VERIFY the result is archivable (terminal per the shared rule, no
        provenance trap). Refuses if the block is already terminal, or if the
        number matches more than one live block (a duplicate must be repaired,
        not written through).
  --append QLABEL (--text TEXT | --body-file F) [--sub-heading H]
        Insert content at the END of the live block — the write physically
        cannot orphan itself under the wrong question.
  --where QLABEL       locate a question (any state) across every file
  --show QLABEL        print ONE question block, whole, using the shared boundary
  --next-number        print the next free global Q integer

The em-dash is MACHINE-OWNED in headings: a --new title containing one is
refused (the text after the last em-dash is the status slot; provenance and
subtitles go in parens or after a colon).
"""
import argparse
import datetime
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_config
import question_block as QB

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def today_str() -> str:
    d = datetime.date.today()
    return f"{d.day:02d} {MONTHS[d.month - 1]} {d.year}"


def parse_qlabel(s: str):
    m = re.fullmatch(r"(\d+)([a-z]?)", s.strip().lstrip("Qq"))
    if not m:
        raise SystemExit(f"not a Q label: {s!r} (expected e.g. 280 or 143a)")
    return int(m.group(1)), m.group(2)


def resolve_shard(vault: str, slug: str) -> str:
    """Map a slug (e.g. 'method', 'colonial-new-england', or a full filename)
    to exactly one live shard path."""
    files = QB.question_files(vault)
    by_base = {os.path.basename(p): p for p in files}
    if slug in by_base:
        return by_base[slug]
    want = re.sub(r"[^a-z0-9]+", "", slug.lower())
    hits = []
    for p in files:
        base = os.path.basename(p)
        stem = re.sub(r"[^a-z0-9]+", "", base[len("Open_Questions"):-len(".md")].lower())
        if stem == want or (want and want in stem):
            hits.append(p)
    if len(hits) == 1:
        return hits[0]
    names = ", ".join(os.path.basename(p) for p in (hits or files))
    raise SystemExit(f"shard {slug!r} is {'ambiguous' if hits else 'unknown'}: {names}")


def find_all(vault, num, suffix):
    """Every block (any state) for a number across live shards + the Resolved
    store: [(path, start, end, head)]."""
    out = []
    paths = QB.question_files(vault)
    rf = QB.resolved_file(vault)
    if os.path.exists(rf):
        paths = paths + [rf]
    for p in paths:
        for s, e, h, _lines in QB.iter_questions(p):
            if h["num"] == num and h["suffix"] == suffix:
                out.append((p, s, e, h))
    return out


def _write(path: str, lines, apply: bool, verb: str):
    if not apply:
        print(f"  [dry-run] would {verb} {os.path.basename(path)} — re-run with --apply")
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"  wrote {os.path.basename(path)}")


def op_new(vault, args):
    shard = resolve_shard(vault, args.shard)
    title = args.title.strip()
    if QB.EMDASH in title:
        raise SystemExit("title contains an em-dash — that slot is machine-owned "
                         "(status). Use a colon or parens; provenance is added "
                         "automatically.")
    if not args.resolver and not args.body_file:
        raise SystemExit("--resolver is required (a question without a named resolver "
                         "is a complaint, not a research task). Or supply --body-file "
                         "whose text names one.")
    num = QB.next_free_number(vault)
    prov = f"(raised {today_str()}" + (f", session #{args.session}" if args.session else "") + ")"
    heading = f"### {num}. {title} {prov}"

    body = []
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8").rstrip("\n").split("\n")
    if args.resolver:
        if body:
            body.append("")
        body.append(f"**⏭ WHAT WOULD SETTLE IT:** {args.resolver.strip()}")

    with open(shard, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    # insert after the LAST question block, before the Resolved index / EOF
    blocks = list(QB.split_blocks(lines))
    if blocks:
        at = blocks[-1][1]
    else:
        at = next((i for i, ln in enumerate(lines) if QB.RESOLVED_INDEX.match(ln)),
                  len(lines))
    new_block = [heading, ""] + body + [""]
    out = lines[:at] + new_block + lines[at:]
    print(f"Q{num} -> {os.path.basename(shard)}")
    print(f"  {heading}")
    _write(shard, out, args.apply, f"insert Q{num} into")
    if args.apply:
        print(f"  (regenerate the index: gen_question_index.py --write "
              f"<vault>/Open_Questions_Index.md)")
    return 0


def op_resolve(vault, args):
    num, suffix = parse_qlabel(args.resolve)
    status = args.status.strip().upper()
    if status not in QB.STATUS_KWS:
        raise SystemExit(f"status {status!r} is not terminal; one of: "
                         f"{', '.join(QB.STATUS_KWS)}")
    hits = QB.find_live_blocks(vault, num, suffix)
    if not hits:
        others = find_all(vault, num, suffix)
        where = "; ".join(f"{os.path.basename(p)}:{s+1} ({h['status'] or 'no status'})"
                          for p, s, e, h in others) or "nowhere"
        raise SystemExit(f"no LIVE block for Q{num}{suffix} — found: {where}")
    if len(hits) > 1:
        where = "; ".join(f"{os.path.basename(p)}:{s+1}" for p, s, e, h, _l in hits)
        raise SystemExit(f"Q{num}{suffix} is DUPLICATED across live shards ({where}) — "
                         f"repair the duplicate first; refusing to resolve through it.")
    path, s, _e, h, lines = hits[0]
    note = f" ({args.note.strip()})" if args.note else ""
    new_head = f"{lines[s].rstrip()} {QB.EMDASH} {status} {today_str()}{note}"
    check = QB.parse_heading(new_head)
    if not check or not check["terminal"] or QB.PROVENANCE_RE.match(check["status"]):
        raise SystemExit(f"internal: rewritten heading is not archivable: {new_head!r}")
    print(f"Q{num}{suffix} in {os.path.basename(path)}:{s+1}")
    print(f"  old: {lines[s][:110]}")
    print(f"  new: {new_head[:110]}")
    lines[s] = new_head
    _write(path, lines, args.apply, f"resolve Q{num}{suffix} in")
    if args.apply:
        print("  (archive it: archive_sections.py --apply, or leave for session close)")
    return 0


def op_append(vault, args):
    num, suffix = parse_qlabel(args.append)
    text = args.text
    if args.body_file:
        text = Path(args.body_file).read_text(encoding="utf-8")
    if not text or not text.strip():
        raise SystemExit("--append needs --text or --body-file")
    hits = QB.find_live_blocks(vault, num, suffix)
    if len(hits) != 1:
        where = "; ".join(f"{os.path.basename(p)}:{s+1}" for p, s, e, h, _l in hits)
        raise SystemExit(f"need exactly one LIVE Q{num}{suffix} block, found "
                         f"{len(hits)}{' (' + where + ')' if hits else ''}")
    path, s, e, h, lines = hits[0]
    addition = text.rstrip("\n").split("\n")
    if args.sub_heading:
        addition = [f"## {args.sub_heading.strip()}", ""] + addition
    # insert before the block's trailing blank/--- run so the write stays inside it
    t = e
    while t > s + 1 and lines[t - 1].strip() in ("", "---"):
        t -= 1
    out = lines[:t] + [""] + addition + lines[t:]
    print(f"append {len(addition)} line(s) to Q{num}{suffix} "
          f"({os.path.basename(path)}:{t+1})")
    _write(path, out, args.apply, f"append to Q{num}{suffix} in")
    return 0


def op_show(vault, args):
    """Print one question block WHOLE, cut by the shared boundary.

    ⚠ THIS EXISTS SO NOTHING ELSE HAS TO PARSE THE REGISTER. The old
    `08-open-question-resolution` prompt extracted a block with an inline
    `awk '/^### 114\\./,/^### 115\\./'` — which assumes questions are contiguous
    and live in one file, and both stopped being true at the 12 AUG lineage
    shard split (Q114's neighbour is in a different shard, so the range ran to
    EOF or matched nothing). A reader that re-implements the boundary is the
    same defect as a writer that does; there is ONE home."""
    num, suffix = parse_qlabel(args.show)
    rows = find_all(vault, num, suffix)
    if not rows:
        print(f"Q{num}{suffix}: not found in any question file")
        return 1
    live = [r for r in rows if QB.is_live(r[3])]
    chosen = live or rows
    for path, s, e, h in chosen:
        state = "LIVE" if QB.is_live(h) else (
            "terminal" if h["terminal"] else
            "tombstone" if h["tombstone"] or h["struck"] else "original")
        print(f"--- {os.path.basename(path)}:{s+1}-{e}  [{state}]")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        print("\n".join(lines[s:e]).rstrip())
    if live and len(rows) > len(live):
        print(f"\n(+{len(rows)-len(live)} non-live block(s) for this number not shown; "
              f"--where lists them)")
    return 0


def op_where(vault, args):
    num, suffix = parse_qlabel(args.where)
    rows = find_all(vault, num, suffix)
    if not rows:
        print(f"Q{num}{suffix}: not found in any question file")
        return 1
    for p, s, e, h in rows:
        state = ("LIVE" if QB.is_live(h) else
                 "terminal" if h["terminal"] else
                 "tombstone" if h["tombstone"] or h["struck"] else "original")
        print(f"Q{num}{suffix}  {os.path.basename(p)}:{s+1}  [{state}]  "
              f"{(h['status'] or h['title'])[:80]}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--new", action="store_true", help="create a question")
    ap.add_argument("--shard", help="target shard for --new (slug or filename)")
    ap.add_argument("--title", help="heading title for --new (no em-dash)")
    ap.add_argument("--resolver", help="what would settle it (required for --new)")
    ap.add_argument("--session", help="session number for the provenance paren")
    ap.add_argument("--resolve", metavar="QLABEL", help="mark terminal, e.g. 280 / 143a")
    ap.add_argument("--status", help="terminal keyword for --resolve")
    ap.add_argument("--note", help="parenthetical after the status date")
    ap.add_argument("--append", metavar="QLABEL", help="append content to a live block")
    ap.add_argument("--sub-heading", help="wrap the appended text under '## <H>'")
    ap.add_argument("--text", help="content for --append")
    ap.add_argument("--body-file", help="file holding content for --new/--append")
    ap.add_argument("--where", metavar="QLABEL", help="locate a question")
    ap.add_argument("--show", metavar="QLABEL",
                    help="print one question block whole (shared boundary; "
                         "prefers the LIVE block when a number has several)")
    ap.add_argument("--next-number", action="store_true")
    args = ap.parse_args()
    vault = vault_config.resolve_vault(args.vault)

    if args.next_number:
        print(QB.next_free_number(vault))
        return 0
    if args.new:
        if not (args.shard and args.title):
            raise SystemExit("--new needs --shard and --title")
        return op_new(vault, args)
    if args.resolve:
        if not args.status:
            raise SystemExit("--resolve needs --status")
        return op_resolve(vault, args)
    if args.append:
        return op_append(vault, args)
    if args.show:
        return op_show(vault, args)
    if args.where:
        return op_where(vault, args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
