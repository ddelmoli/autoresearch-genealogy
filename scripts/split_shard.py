#!/usr/bin/env python3
"""
split_shard.py — mechanically carve a contiguous generation range out of an
oversized Family_Tree shard into a new shard, and update the File Index manifest.

Plan 3 of the vault-housekeeping work. Splitting a shard is a SEMANTIC decision
(which generations/branches belong together) — the operator picks the boundary;
this tool does the mechanical, error-prone part SAFELY:

  * moves whole `### Generation N` blocks (N in [--gen-min, --gen-max]) to a new
    shard, carrying each person entry's `- meta:` block intact (ids never change);
  * leaves a cross-reference stub where they were, and a "split from" note + a
    cross-ref back in the new shard's header;
  * adds a row to the File Index manifest table in Family_Tree.md for the new shard;
  * snapshots every file it will touch (source, Family_Tree.md) before writing;
  * verifies meta-block conservation (total `- meta:` count + distinct ids across
    source+dest must equal the source's original) and refuses to apply on mismatch;
  * DRY-RUN by default — pass --apply to write.

Only `### Generation N` blocks in range move. Other `## ` sections (Research path,
Status, Collateral stubs, etc.) and out-of-range generations stay in the source;
move those by hand if needed. The pre-commit hook still runs the full integrity
gate afterward.

Entry-level modes (for a shard whose entries sit under ONE section, e.g. a
gen-sorted `## Collateral stub entries` appendix with no `### Generation N`
headings, where the block mode above finds nothing to carve):

  * `--surnames A,B`  moves each person entry whose HEADER whole-word-matches;
  * `--by-meta-gen` with `--gen-min/--gen-max` moves each person entry whose
    `- meta:` `generation` lies in range (the meta field is the machine truth;
    an entry with no generation stays in the source).

  ⚠ Entry mode rebuilds each section from its entries. A prose line AFTER an
  entry is part of that entry's block and travels with it; a section INTRO
  (prose between a heading and its first entry) stays with the source's copy of
  the heading. Intros used to be DROPPED SILENTLY (the id-conservation check
  counts ids, not prose); any line the rebuild still cannot place now ABORTS
  the split and is listed. Blank lines and `---` rules are normalised away.

Usage:
  python3 scripts/split_shard.py --source Family_Tree_Maternal.md \
      --gen-min 5 --gen-max 6 --dest Family_Tree_Maternal_Deep.md \
      --region Maternal --content "Maternal deep immigrant-origin generations (Gen 5-6)" [--apply]
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_config

ROOT = Path(__file__).resolve().parent.parent
_V = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
VAULT = Path(_V) if _V else None
MASTER = (VAULT / "Family_Tree.md") if VAULT else None

GEN_HDR = re.compile(r"^###\s+Generation\s+(\d+)\b", re.IGNORECASE)
META_RE = re.compile(r"^\s*-\s*meta:\s*\{", re.MULTILINE)
ID_RE = re.compile(r"\bid:\s*(P-[0-9A-Za-z]+)")


def snapshot(path: Path, ts: str) -> Path:
    d = VAULT / "Shard_Split_Archive"
    d.mkdir(parents=True, exist_ok=True)
    snap = d / f"{path.stem}_{ts}{path.suffix}"
    snap.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return snap


def meta_ids(text: str):
    return ID_RE.findall(text)


def carve(text: str, gen_min: int, gen_max: int):
    """Return (new_source_text, moved_text, moved_gens). Moves whole '### Generation N'
    blocks with gen_min<=N<=gen_max; a block runs to the next '### '/'## '/EOF."""
    lines = text.splitlines(keepends=True)
    # boundaries = every heading line (## or ###)
    bounds = [i for i, ln in enumerate(lines)
              if ln.startswith("### ") or ln.startswith("## ")]
    bounds.append(len(lines))

    moved_chunks, moved_gens = [], []
    drop = set()
    stub_at = {}  # first dropped line index of each moved block -> stub text
    for k in range(len(bounds) - 1):
        i = bounds[k]
        m = GEN_HDR.match(lines[i])
        if not m:
            continue
        g = int(m.group(1))
        if gen_min <= g <= gen_max:
            j = bounds[k + 1]
            moved_chunks.append("".join(lines[i:j]))
            moved_gens.append(g)
            for x in range(i, j):
                drop.add(x)
            stub_at[i] = None  # mark the heading line; stub injected once below

    if not moved_chunks:
        return None, None, []

    # Build new source: drop moved lines; at the first moved block's position,
    # insert ONE consolidated cross-ref stub.
    first_moved = min(stub_at)
    return lines, drop, first_moved, moved_chunks, moved_gens


ENTRY_HDR = re.compile(r"^\*\*")           # a person-entry header starts with ** (body bullets start with "- ")
HEADING = re.compile(r"^#{2,3}\s")
GEN_H = re.compile(r"^###\s+Generation\b", re.IGNORECASE)
COLLAT_H = re.compile(r"^##\s+Collateral", re.IGNORECASE)


def _blockify(lines):
    """Tokenize a shard into blocks: ('head'|'heading'|'entry'|'prose', text, has_meta)."""
    blocks = []
    # head = frontmatter + intro, up to the first heading or entry header
    i = 0
    while i < len(lines) and not (HEADING.match(lines[i]) or ENTRY_HDR.match(lines[i])):
        i += 1
    if i:
        blocks.append(("head", "".join(lines[:i]), False))
    while i < len(lines):
        ln = lines[i]
        if HEADING.match(ln):
            blocks.append(("heading", ln, False))
            i += 1
        elif ENTRY_HDR.match(ln):
            j = i + 1
            while j < len(lines) and not (HEADING.match(lines[j]) or ENTRY_HDR.match(lines[j])):
                j += 1
            txt = "".join(lines[i:j])
            blocks.append(("entry", txt, bool(META_RE.search(txt))))
            i = j
        else:
            blocks.append(("prose", ln, False))
            i += 1
    return blocks


META_GEN_RE = re.compile(r"^\s*-\s*meta:\s*\{[^\n]*?\bgeneration:\s*(\d+)", re.MULTILINE)


def surname_matcher(surnames):
    """Route an entry whose HEADER whole-word-matches one of `surnames`."""
    sur_re = re.compile(r"\b(" + "|".join(re.escape(s) for s in surnames) + r")\b")
    return lambda entry_txt: bool(sur_re.search(_hdr_name(entry_txt)))


def meta_gen_matcher(gen_min, gen_max):
    """Route an entry whose FIRST `- meta:` line carries generation in range."""
    def match(entry_txt):
        m = META_GEN_RE.search(entry_txt)
        return bool(m) and gen_min <= int(m.group(1)) <= gen_max
    return match


def _hdr_name(entry_txt):
    m = re.match(r"^\*\*(.+?)\*\*", entry_txt)
    return (m.group(1) if m else entry_txt[:40]).strip()


def cluster_split(text, match, source_name, dest_name, ts):
    """Entry-level split: route each PERSON entry (a '**'-header block containing a
    '- meta:') to the dest if `match(entry_text)` is true, else keep it in source.
    (`match` may also be a list of surnames, the original calling form.) Generation / Collateral headings are emitted lazily to each
    stream (so emptied headings vanish and dest headings are reconstructed). Prose
    '##' sections (Research path / Status) stay in source. Returns
    (new_src, dest_body, moved, kept, dropped) -- `dropped` lists the non-blank,
    non-rule prose lines the rebuild could not place; callers must refuse to
    write when it is non-empty."""
    if not callable(match):
        match = surname_matcher(match)
    blocks = _blockify(text.splitlines(keepends=True))

    src_out, dst_out = [], []
    moved, kept, dropped = [], [], []
    pending = {"src": None, "dst": None}   # a heading awaiting its first entry per stream
    mode = "gen"                            # 'gen' | 'collateral' | 'prose'
    cur_heading = None

    hdr_name = _hdr_name

    for kind, txt, has_meta in blocks:
        if kind == "head":
            src_out.append(txt)
        elif kind == "heading":
            if GEN_H.match(txt):
                mode, cur_heading = "gen", txt
                pending["src"] = pending["dst"] = txt
            elif COLLAT_H.match(txt):
                mode, cur_heading = "collateral", txt
                pending["src"] = pending["dst"] = txt
            else:  # other '##' prose section (Research path, Status)
                mode, cur_heading = "prose", txt
                src_out.append(txt)
        elif kind == "entry":
            if mode == "prose" or not has_meta:
                # a non-person bold paragraph (e.g. **FamilySearch status:**) or an
                # entry inside a prose section → keep with source.
                src_out.append(txt)
                continue
            to_dst = bool(match(txt))
            stream, out = ("dst", dst_out) if to_dst else ("src", src_out)
            if pending[stream] is not None and mode in ("gen", "collateral"):
                out.append("\n" + pending[stream])
                pending[stream] = None
            out.append("\n" + txt if not txt.startswith("\n") else txt)
            (moved if to_dst else kept).append(hdr_name(txt))
        else:  # prose line
            if mode == "prose":
                src_out.append(txt)
            elif txt.strip() and txt.strip() != "---":
                if pending["src"] is not None and pending["src"] == cur_heading:
                    # a section INTRO (prose before the section's first entry): it
                    # describes the section, so it stays with the source's copy of
                    # the heading, which is emitted now rather than lazily.
                    src_out.append("\n" + pending["src"])
                    pending["src"] = None
                    src_out.append("\n" + txt)
                elif not moved and not kept:
                    src_out.append(txt)
                else:
                    dropped.append(txt.rstrip("\n"))
            # blanks and '---' rules between entries are normalised away
    return "".join(src_out), "".join(dst_out), moved, kept, dropped


def gen_range_label(gens):
    lo, hi = min(gens), max(gens)
    return f"Gen {lo}" if lo == hi else f"Gen {lo}-{hi}"


def build_dest(source_name, dest_name, moved_chunks, gens, ts):
    title = dest_name.replace("Family_Tree_", "").replace(".md", "").replace("_", " ")
    label = gen_range_label(gens)
    fm = (f"---\n"
          f"type: reference\n"
          f"created: {ts[:10]}\n"
          f"updated: {ts[:10]}\n"
          f"tags: [genealogy, family-tree]\n"
          f"prior update: split from {source_name} {ts[:10]}\n"
          f"---\n\n"
          f"# Family Tree: {title} ({label})\n\n"
          f"> Split from [[{Path(source_name).stem}]] on {ts[:10]} "
          f"({label} carved out to keep the source shard readable). "
          f"Recent generations + line context remain in [[{Path(source_name).stem}]].\n\n"
          f"---\n\n")
    return fm + "\n".join(c.rstrip("\n") + "\n" for c in moved_chunks)


def update_manifest(master_text, dest_name, region, content, source_name):
    """Insert a File Index row for dest after the source row (or at table end)."""
    lines = master_text.splitlines(keepends=True)
    # find the | File | Region | Content | header
    hdr = None
    for i, ln in enumerate(lines):
        cells = [c.strip().lower() for c in ln.strip().strip("|").split("|")]
        if "file" in cells and "region" in cells:
            hdr = i
            break
    if hdr is None:
        return master_text, False
    dest_stem = Path(dest_name).stem
    src_stem = Path(source_name).stem
    row = f"| [[{dest_stem}]] | {region} | {content} |\n"
    # find last contiguous table row; and the source row (to insert right after it)
    last = hdr
    src_row = None
    i = hdr + 1
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        if f"[[{src_stem}]]" in lines[i]:
            src_row = i
        last = i
        i += 1
    at = (src_row + 1) if src_row is not None else (last + 1)
    lines.insert(at, row)
    return "".join(lines), True


def _run_cluster(args, src, dest, text):
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    if args.by_meta_gen:
        match = meta_gen_matcher(args.gen_min, args.gen_max)
        what = f"Gen {args.gen_min}-{args.gen_max}" if args.gen_min != args.gen_max else f"Gen {args.gen_min}"
    else:
        surnames = [s.strip() for s in args.surnames.split(",") if s.strip()]
        match = surname_matcher(surnames)
        what = "surnames " + ", ".join(surnames)
    new_src, dest_body, moved, kept, dropped = cluster_split(text, match, args.source, args.dest, ts)
    if not moved:
        print(f"No person entries match ({what}) in {args.source}.")
        return 0

    title = args.dest.replace("Family_Tree_", "").replace(".md", "").replace("_", " ")
    fm = (f"---\ntype: reference\ncreated: {ts[:10]}\nupdated: {ts[:10]}\n"
          f"tags: [genealogy, family-tree]\n"
          f"prior update: split from {args.source} {ts[:10]}\n---\n\n"
          f"# Family Tree: {title}\n\n"
          f"> Split from [[{Path(args.source).stem}]] on {ts[:10]} "
          + (f"(the {what} entries carved out to keep the source shard readable). "
             f"The other generations remain in [[{Path(args.source).stem}]].\n"
             if args.by_meta_gen else
             f"(this branch carved out by lineage to keep the source shard readable). "
             f"The joining person + the other branch remain in [[{Path(args.source).stem}]].\n"))
    dest_text = fm + dest_body
    # cross-ref note into the source, right after its frontmatter+intro head
    note = f"\n> **{len(moved)} entries ({what}) moved to [[{dest.stem}]]** (split {ts[:10]}).\n"
    m = re.search(r"\n---\n", new_src)
    new_src = (new_src[:m.end()] + note + new_src[m.end():]) if m else note + new_src

    orig_ids = meta_ids(text)
    new_ids = meta_ids(new_src) + meta_ids(dest_text)
    ok = sorted(orig_ids) == sorted(new_ids) and len(set(new_ids)) == len(new_ids)

    print(f"split_shard (cluster) — {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  source {args.source}: {len(orig_ids)} person meta ids")
    print(f"  -> MOVE {len(moved)} entr(y/ies) to {args.dest}: {', '.join(moved)}")
    print(f"  -> KEEP {len(kept)} in source: {', '.join(kept)}")
    print(f"  meta ids: {len(orig_ids)} -> source {len(meta_ids(new_src))} + dest "
          f"{len(meta_ids(dest_text))}; conserved + unique: {ok}")
    master_text = MASTER.read_text(encoding="utf-8") if MASTER.exists() else ""
    new_master, man_ok = update_manifest(master_text, args.dest, args.region, args.content, args.source)
    print(f"  manifest: {'will add File Index row for ' + dest.stem if man_ok else 'NO File/Region table — add by hand'}")

    if dropped:
        print(f"  ABORT: {len(dropped)} prose line(s) sit between entries and have no entry to "
              "travel with; move or attach them by hand first. Nothing written:")
        for d in dropped:
            print(f"    | {d[:150]}")
        return 2
    if not ok:
        print("  ABORT: meta-block conservation FAILED (ids lost/duplicated). Nothing written.")
        return 2
    if not args.apply:
        print("\n  [dry-run] nothing written. Review the MOVE/KEEP assignment above, then --apply.")
        return 0
    snapshot(src, ts)
    if MASTER.exists():
        snapshot(MASTER, ts)
    dest.write_text(dest_text, encoding="utf-8")
    src.write_text(new_src, encoding="utf-8")
    if man_ok:
        MASTER.write_text(new_master, encoding="utf-8")
    print(f"\n  wrote {args.dest}, updated {args.source}"
          + (", added manifest row" if man_ok else "") + ".")
    print("  REVIEW the source's File Index row (content now that a branch moved), then commit.")
    return 0


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="source shard filename (in vault/)")
    ap.add_argument("--gen-min", type=int, help="generation-range mode: low bound")
    ap.add_argument("--gen-max", type=int, help="generation-range mode: high bound")
    ap.add_argument("--surnames", help="entry-level mode: comma-separated surnames; "
                                       "move person entries whose header whole-word-matches one")
    ap.add_argument("--by-meta-gen", action="store_true",
                    help="entry-level mode: with --gen-min/--gen-max, move person entries "
                         "whose meta generation is in range (for a shard with no "
                         "'### Generation N' blocks)")
    ap.add_argument("--dest", required=True, help="new shard filename (in vault/)")
    ap.add_argument("--region", required=True, help="File Index Region column value")
    ap.add_argument("--content", required=True, help="File Index Content column value")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args()

    src = VAULT / args.source
    dest = VAULT / args.dest
    if not src.exists():
        print(f"ERROR: {src} not found")
        return 1
    if dest.exists():
        print(f"ERROR: dest {dest} already exists — choose a new name")
        return 1

    text = src.read_text(encoding="utf-8")
    if args.by_meta_gen:
        if args.surnames or args.gen_min is None or args.gen_max is None:
            print("ERROR: --by-meta-gen needs --gen-min and --gen-max, and not --surnames.")
            return 2
        return _run_cluster(args, src, dest, text)
    if args.surnames:
        return _run_cluster(args, src, dest, text)
    if args.gen_min is None or args.gen_max is None:
        print("ERROR: provide --surnames (entry-level) OR --gen-min/--gen-max (generation-range).")
        return 2
    res = carve(text, args.gen_min, args.gen_max)
    if res[0] is None:
        print(f"No '### Generation N' blocks with {args.gen_min}<=N<={args.gen_max} in {args.source}.")
        return 0
    lines, drop, first_moved, moved_chunks, moved_gens = res

    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    stub = (f"> **{gen_range_label(moved_gens)} moved to [[{dest.stem}]]** "
            f"(split {ts[:10]}; see that shard for these generations).\n\n")
    new_src = []
    for idx, ln in enumerate(lines):
        if idx == first_moved:
            new_src.append(stub)
        if idx not in drop:
            new_src.append(ln)
    new_src_text = "".join(new_src)
    dest_text = build_dest(args.source, args.dest, moved_chunks, moved_gens, ts)

    # meta conservation check
    orig_ids = meta_ids(text)
    new_ids = meta_ids(new_src_text) + meta_ids(dest_text)
    moved_meta = sum(len(META_RE.findall(c)) for c in moved_chunks)
    ok = sorted(orig_ids) == sorted(new_ids) and len(set(new_ids)) == len(new_ids)

    print(f"split_shard — {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  source: {args.source}  ->  carve {gen_range_label(moved_gens)} "
          f"({len(moved_chunks)} generation block(s), {moved_meta} person meta block(s))")
    print(f"  dest:   {args.dest}  (region '{args.region}')")
    print(f"  meta ids: source had {len(orig_ids)} -> source {len(meta_ids(new_src_text))} "
          f"+ dest {len(meta_ids(dest_text))}; conserved + unique: {ok}")
    master_text = MASTER.read_text(encoding="utf-8") if MASTER.exists() else ""
    new_master, man_ok = update_manifest(master_text, args.dest, args.region, args.content, args.source)
    print(f"  manifest: {'will add File Index row for ' + dest.stem if man_ok else 'NO File/Region table found — add the row by hand'}")

    if not ok:
        print("  ABORT: meta-block conservation check FAILED (ids lost/duplicated). "
              "Nothing written. Inspect the generation boundaries.")
        return 2
    if not args.apply:
        print("\n  [dry-run] nothing written. Re-run with --apply to perform the split.")
        print("  After applying: review the source row's gen-range/content in the File Index,")
        print("  then commit (the pre-commit hook runs the full integrity gate).")
        return 0

    snapshot(src, ts)
    if MASTER.exists():
        snapshot(MASTER, ts)
    dest.write_text(dest_text, encoding="utf-8")
    src.write_text(new_src_text, encoding="utf-8")
    if man_ok:
        MASTER.write_text(new_master, encoding="utf-8")
    print(f"\n  wrote {args.dest}, updated {args.source}"
          + (", added manifest row" if man_ok else "") + ".")
    print("  REVIEW the source's File Index row (gen-range/content) by hand, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
