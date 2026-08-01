#!/usr/bin/env python3
"""
move_tail_entries.py — carve a contiguous TAIL of a shard (an anchor line through
EOF) out into a companion file, conserving every person record.

The counterpart to `split_shard.py` for a file whose oversized mass is an
**appendix** rather than a generation run.

  split_shard.py --gen-min/--gen-max   moves whole `### Generation N` blocks.
  split_shard.py --surnames            moves entries whose header matches a
                                       surname -- but it matches across the
                                       WHOLE file, so on a shard that also holds
                                       direct-line entries of that surname it
                                       takes those too.
  THIS TOOL                            moves exactly `anchor` .. EOF. The
                                       boundary is STATED, not inferred.

Use it when the section to move is the tail of the file: a
`## Collateral stub entries` appendix, or a gen-sorted run inside one.

**Choosing between the two is a SEMANTIC decision and it is yours.** The test
that has held up (session #121): ask whether the file's `##` sections have
*overlapping* generation ranges. If they do, a generation cut slices every
branch at once and you want a section/appendix cut instead.

Safety contract, matching split_shard.py:

  * DRY-RUN by default; `--apply` writes.
  * Snapshots every file it touches into `Shard_Split_Archive/` first.
  * **Refuses an anchor that is not an entry boundary** -- see below.
  * **Conservation is checked on the ID SET, not the count**: the source's
    original ids must equal (new source + dest), with none lost, gained or
    duplicated. Refuses to write on any mismatch.
  * Leaves a pointer stub at the cut and a "split from" header in the dest.
  * Adds a File Index row to Family_Tree.md via `split_shard.update_manifest`.

**Why an id-set check is not sufficient on its own, and what the anchor rule is
for.** A tail move splits at a line, so it cannot lose an id by construction --
which makes a conservation check that passes here nearly uninformative. The
failure this tool can actually cause is a cut *inside* an entry: the bold-name
header stays in the source while its `- meta:` block travels to the dest. The id
set is conserved, every count balances, and the result is one entry with no
record and one record with no name. So the anchor must be a legal entry boundary
-- a bold-name header at line start, or a `#`-level heading -- per the vault's
entry-boundary spec ("a bold name at line start is an entry header; anywhere
else on the line it is prose"). Both checks are enforced, and both have negative
controls in `test_move_tail_entries.py`.

Usage:
  python3 scripts/move_tail_entries.py \
      --source Family_Tree_Example.md \
      --dest Family_Tree_Example_Collateral.md \
      --anchor '## Collateral stub entries' \
      --title 'Family Tree - Example collateral entries' \
      --tags 'family-tree, example, collateral' \
      --intro '> **Split from [[Family_Tree_Example]] on 2026-01-01.** ...' \
      --stub '> **Collateral entries moved to [[Family_Tree_Example_Collateral]]**.' \
      --region 'Example' --content 'Example collateral entries, split 2026-01-01' \
      [--apply]
"""
import argparse
import datetime
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import split_shard
import vault_config

ID_RE = re.compile(r"\bid:\s*(P-[0-9A-Za-z]+)")
META_RE = re.compile(r"^\s*-\s*meta:\s*\{", re.MULTILINE)


def ids(text):
    """The id multiset of a chunk of narrative."""
    return Counter(ID_RE.findall(text))


def is_boundary(line):
    """True if `line` may legally begin a moved tail.

    An entry starts at a bold name at LINE START, or at a Markdown heading. A cut
    anywhere else lands inside an entry and separates a header from its record.
    """
    return line.startswith("**") or line.startswith("#")


def find_cut(lines, anchor):
    """Index of the single line starting with `anchor`.

    Raises ValueError unless exactly one line matches AND that line is a legal
    entry boundary. Ambiguity is an error rather than a first-match, because the
    caller is naming a cut point and two candidates mean they do not know which.
    """
    hits = [i for i, ln in enumerate(lines) if ln.startswith(anchor)]
    if len(hits) == 0:
        raise ValueError(f"anchor matched no line: {anchor!r}")
    if len(hits) > 1:
        raise ValueError(
            f"anchor matched {len(hits)} lines (need exactly 1): {anchor!r} "
            f"at lines {[i + 1 for i in hits]}")
    if not is_boundary(lines[hits[0]]):
        raise ValueError(
            f"anchor is not an entry boundary (line {hits[0] + 1}): "
            f"{lines[hits[0]].strip()[:60]!r}. A tail must start at a bold-name "
            f"header at line start or at a heading; cutting inside an entry "
            f"separates its bold name from its `- meta:` block.")
    return hits[0]


def conservation(original, kept, moved):
    """(ok, lost, gained, duplicated) for the id set across a split."""
    before, after = ids(original), ids(kept) + ids(moved)
    lost = sorted((before - after).elements())
    gained = sorted((after - before).elements())
    dupes = sorted(i for i, n in after.items() if n > 1)
    return (not lost and not gained and not dupes), lost, gained, dupes


def build_dest_text(source_name, title, tags, intro, moved, day):
    return (
        "---\ntype: reference\n"
        f"created: {day}\nupdated: {day}\n"
        f"tags: [{tags}]\n"
        f"prior update: split from {source_name} {day}\n"
        "---\n\n"
        f"# {title}\n\n{intro}\n\n---\n\n" + moved.lstrip("\n")
    )


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Move an anchor..EOF tail of a shard into a companion file.")
    ap.add_argument("--source", required=True, help="source shard filename (in the vault)")
    ap.add_argument("--dest", required=True, help="new companion filename (in the vault)")
    ap.add_argument("--anchor", required=True,
                    help="exact start-of-line text of the FIRST line to move; "
                         "must match exactly one line, and be a heading or a "
                         "bold-name header at line start")
    ap.add_argument("--title", required=True, help="the dest's H1")
    ap.add_argument("--tags", required=True, help="dest frontmatter tags, comma-separated")
    ap.add_argument("--intro", required=True, help="the dest header's scope note")
    ap.add_argument("--stub", required=True, help="pointer left at the cut point in the source")
    ap.add_argument("--region", required=True, help="File Index Region column value")
    ap.add_argument("--content", required=True, help="File Index Content column value")
    ap.add_argument("--vault", help="vault path (else AUTORESEARCH_VAULT)")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args(argv)

    vault = Path(vault_config.resolve_vault(args.vault))
    src, dest = vault / args.source, vault / args.dest
    if not src.exists():
        print(f"REFUSING: {args.source} not found in {vault}")
        return 2
    if dest.exists():
        print(f"REFUSING: {args.dest} already exists -- this tool only creates a "
              f"NEW companion, it never appends to one")
        return 2

    text = src.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    try:
        cut = find_cut(lines, args.anchor)
    except ValueError as e:
        print(f"REFUSING: {e}")
        return 2

    kept, moved = "".join(lines[:cut]), "".join(lines[cut:])
    ok, lost, gained, dupes = conservation(text, kept, moved)

    print(f"move_tail_entries — {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  source: {args.source}  -> cut at line {cut + 1}: "
          f"{lines[cut].strip()[:70]}")
    print(f"  dest:   {args.dest}")
    print(f"  meta blocks: source had {len(META_RE.findall(text))} -> "
          f"source {len(META_RE.findall(kept))} + dest {len(META_RE.findall(moved))}")
    print(f"  meta ids:    source had {sum(ids(text).values())} -> "
          f"source {sum(ids(kept).values())} + dest {sum(ids(moved).values())}")
    print(f"  id set conserved (none lost/gained/duplicated): {ok}")
    if not ok:
        print(f"    LOST {lost}  GAINED {gained}  DUPLICATED {dupes}")
        print("REFUSING to write: id set not conserved")
        return 2

    if not args.apply:
        print("\n  [dry-run] nothing written. Re-run with --apply to perform the move.")
        return 0

    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    day = ts[:10]
    master = vault / "Family_Tree.md"
    snapdir = vault / "Shard_Split_Archive"
    snapdir.mkdir(parents=True, exist_ok=True)
    for p in (src, master):
        if p.exists():
            (snapdir / f"{p.stem}_{ts}{p.suffix}").write_text(
                p.read_text(encoding="utf-8"), encoding="utf-8")

    dest.write_text(
        build_dest_text(args.source, args.title, args.tags, args.intro, moved, day),
        encoding="utf-8")
    src.write_text(kept.rstrip("\n") + "\n\n" + args.stub + "\n", encoding="utf-8")

    man_ok = False
    if master.exists():
        mnew, man_ok = split_shard.update_manifest(
            master.read_text(encoding="utf-8"), dest.stem,
            args.region, args.content, args.source)
        if man_ok:
            master.write_text(mnew, encoding="utf-8")

    print(f"\n  wrote {args.dest}, updated {args.source}, manifest row: "
          f"{'added' if man_ok else 'NOT ADDED — add the File Index row by hand'}")
    print("  REVIEW the source's File Index row (its content changed), then commit;")
    print("  the vault pre-commit hook runs the full integrity gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
