#!/usr/bin/env python3
"""
tree_locator.py — derive a "which file is person X in?" locator from a sharded
family tree, with NO hand-maintained index required.

When `Family_Tree.md` outgrows a single file and is split into
`Family_Tree_<Region>_<Branch>.md` shards, locating a person becomes a real
problem. This tool answers it by reading the shards directly: it scans each
`Family_Tree*.md` for bold-name narrative entries (`**Name** ( ... )`) and
builds  name -> {file, generation, region}.

- Region is OPTIONAL and comes from the File/Region manifest in Family_Tree.md
  (see shard_manifest.py). Without a manifest, everything is one generic region.
- Generation is read from the nearest `### Generation N` heading above an entry,
  when the vault uses them; otherwise it is left blank.
- Degrades gracefully: on an un-sharded vault it just reports a single file.

Modes:
  (default)    print the locator (name -> file [gen] [region]); summary counts
  --by-file    group by shard file
  --by-region  group by manifest region
  --region X   filter to a region substring
  --csv        emit CSV: name,file,generation,region
  --check      integrity report (needs no index):
                 * people appearing in >1 shard file (ambiguous / possible dup)
                 * shard files on disk not declared in the manifest (no region)
                 * manifest entries with no matching file on disk
               --check exits 1 when any issue is found, else 0.

Generic: contains no project-specific names. Pairs with shard_manifest.py as the
"your vault outgrew one file" toolkit.
"""

import argparse
import glob
import os
import re
import sys
from collections import defaultdict

import shard_manifest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VAULT = os.path.join(os.path.dirname(SCRIPT_DIR), "vault")

# Bold-name narrative entry header — the convention this toolkit keys on:
#   "**Full Name** ( ... )"  or  "**Full Name ( ... )**"
# Require a proper-noun first token (Cap + lowercase) so all-caps labels
# ("SECOND MARRIAGE", "FS-attached") are not mistaken for people.
NAME_TOKEN_FIRST = r"[A-ZÀ-Ý][a-zà-ÿ][\w\.\-'À-ÿ]*"
NAME_TOKEN_REST = r"[\w\.\-'À-ÿ]+"
# Capture the parenthetical too (group 2) so we can confirm the entry is a person.
HDR_A = re.compile(
    rf"^[\-\*\s]*\*\*({NAME_TOKEN_FIRST}(?:\s+{NAME_TOKEN_REST}){{1,8}})\*\*\s*\(([^)]{{0,400}})",
    re.MULTILINE,
)
# ANCHORED to line start, like HDR_A (23 JUL 2026, spec/entry-boundary). Unanchored,
# this matched a bold-wrapped `Words (parenthetical)` span ANYWHERE in a line, so an
# archive or record-series name bolded mid-sentence ("**Archivio di Stato di Sondrio
# (1866-1900)**") was indexed as a person living in that file. `_is_person` cannot
# reject those: it permits lowercase toponymic particles so real names survive, and
# an institution name has the same shape. Position is the reliable discriminator —
# a real entry header always begins its line. Measured: 124 phantom index rows
# removed, all 31 genuine line-start B-dialect headers kept.
HDR_B = re.compile(
    rf"^[\-\*\s]*\*\*({NAME_TOKEN_FIRST}(?:\s+{NAME_TOKEN_REST}){{1,8}})\s*\(([^)]{{0,400}})",
    re.MULTILINE,
)
GEN_HDR = re.compile(r"^#{1,4}\s+Generation\s+(\d+)", re.MULTILINE | re.IGNORECASE)

# A real person entry's parenthetical carries a date signal (a year, or a
# b./d./m./bapt marker). Bolded section labels and society/order names do not.
DATE_SIGNAL = re.compile(r"\b\d{3,4}\b|\b[bdm]\.\s|\bborn\b|\bdied\b|\bbapt|\bc\.\s*\d", re.IGNORECASE)
# A 4-digit number inside the NAME itself means it isn't a person name
# ("Order of Three Crusades 1096-1192", "Researched 18 JUN 2026").
NAME_HAS_YEAR = re.compile(r"\d{4}")
# Lowercase tokens allowed inside a personal name (nobiliary particles /
# connectors). Any OTHER lowercase token means the bold string is a label
# ("Companion files", "In-law deep pedigrees"), not a person.
NAME_CONNECTORS = {
    "of", "de", "del", "della", "delle", "dei", "di", "da", "la", "le", "du",
    "van", "von", "der", "den", "the", "e", "y", "d'", "dell'",
}


def _looks_like_name(name):
    for tok in name.replace("-", " ").split():
        t = tok.strip(".'")
        if t and t[0].islower() and t.lower() not in NAME_CONNECTORS:
            return False
    return True


# RETIRED 23 JUL 2026 (spec/entry-boundary Spec 05): `looks_like_person_header`, its
# PATRONYMIC_PARTICLES set and the bracket-stripping helper lived here so that
# `harvest_sources` could decide whether a bold string was a person. That question is
# gone: the census detects entries by their `- meta:` block, not by name shape, so
# nothing has to judge whether "Archivio di Stato di Sondrio" looks like a name. The
# heuristic could never have answered it — an institution and a nobiliary name have
# identical shape — which is why the discriminator moved to structure instead.
# `_looks_like_name` below stays: it serves this module's own locator index.

def _is_person(name, paren):
    """Heuristic person filter: name has no embedded year, reads like a personal
    name (capitalized tokens + particles), and the parenthetical looks like a
    vitals descriptor (carries a date signal)."""
    return (not NAME_HAS_YEAR.search(name)
            and _looks_like_name(name)
            and bool(DATE_SIGNAL.search(paren)))


def find_people(text):
    """Yield (name, offset) for each bold-name PERSON entry (deduped by offset)."""
    hits = []
    for m in HDR_A.finditer(text):
        if _is_person(m.group(1), m.group(2)):
            hits.append((m.start(), m.group(1).strip()))
    for m in HDR_B.finditer(text):
        if _is_person(m.group(1), m.group(2)) and not any(abs(m.start() - o) < 10 for o, _ in hits):
            hits.append((m.start(), m.group(1).strip()))
    hits.sort()
    seen = set()
    for off, name in hits:
        if off in seen:
            continue
        seen.add(off)
        yield name, off


def _gen_at(gens, offset):
    """gens = sorted [(offset, gen)]; return gen of the last heading before offset."""
    g = None
    for o, n in gens:
        if o <= offset:
            g = n
        else:
            break
    return g


def build_index(vault):
    """Return (index, manifest, files_on_disk).

    index: name -> list of {file, gen, region} (one per shard the name appears in).
    """
    manifest = shard_manifest.load_shard_manifest(vault)
    index = defaultdict(list)
    files_on_disk = []
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        fn = os.path.basename(path)
        files_on_disk.append(fn)
        base = re.sub(r"\.md$", "", fn)
        region = shard_manifest.region_for(base, manifest)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        gens = [(m.start(), int(m.group(1))) for m in GEN_HDR.finditer(text)]
        for name, off in find_people(text):
            index[name].append({"file": fn, "gen": _gen_at(gens, off), "region": region})
    return index, manifest, files_on_disk


def _flat(index):
    """Yield (name, file, gen, region) for every (name, shard) pair, sorted."""
    rows = []
    for name, locs in index.items():
        for loc in locs:
            rows.append((name, loc["file"], loc["gen"], loc["region"]))
    rows.sort(key=lambda r: (r[3] or "", r[1], r[2] or 999, r[0]))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Derive a person->shard-file locator from a sharded family tree.")
    ap.add_argument("--vault", default=None, help="Path to the vault directory (default: $AUTORESEARCH_VAULT, else ../vault).")
    ap.add_argument("--by-file", action="store_true", help="Group output by shard file.")
    ap.add_argument("--by-region", action="store_true", help="Group output by manifest region.")
    ap.add_argument("--region", help="Filter to a region substring.")
    ap.add_argument("--csv", action="store_true", help="Emit CSV: name,file,generation,region.")
    ap.add_argument("--check", action="store_true", help="Integrity report; exit 1 if any issue.")
    args = ap.parse_args()
    # Vault precedence (standalone — no dependency on the local toolkit):
    # AUTORESEARCH_VAULT env var -> --vault arg -> the ../vault sibling default.
    _env = os.environ.get("AUTORESEARCH_VAULT")
    args.vault = os.path.expanduser(_env) if _env else (args.vault or DEFAULT_VAULT)

    index, manifest, files_on_disk = build_index(args.vault)

    if args.check:
        return run_check(index, manifest, files_on_disk)

    rows = _flat(index)
    if args.region:
        rows = [r for r in rows if r[3] and args.region.lower() in r[3].lower()]

    if args.csv:
        import csv
        w = csv.writer(sys.stdout)
        w.writerow(["name", "file", "generation", "region"])
        for name, fn, gen, region in rows:
            w.writerow([name, fn, gen if gen is not None else "", region])
        return 0

    if args.by_region or args.by_file:
        key_idx = 3 if args.by_region else 1
        groups = defaultdict(list)
        for r in rows:
            groups[r[key_idx]].append(r)
        for key in sorted(groups):
            print(f"\n== {key} ({len(groups[key])}) ==")
            for name, fn, gen, region in groups[key]:
                gtag = f"Gen {gen}" if gen is not None else "Gen ?"
                extra = fn if args.by_region else region
                print(f"  {gtag:<7} {name[:48]:<48} {extra}")
    else:
        for name, fn, gen, region in rows:
            gtag = f"Gen {gen}" if gen is not None else "Gen ?"
            print(f"  {gtag:<7} {name[:48]:<48} {fn}  [{region}]")

    distinct = len(index)
    print(f"\n{distinct} distinct people across {len(files_on_disk)} shard file(s); "
          f"{len(rows)} name-in-file entries shown.")
    return 0


def run_check(index, manifest, files_on_disk):
    issues = 0

    # 1. People appearing in more than one shard file (ambiguous / possible dup)
    multi = {n: locs for n, locs in index.items() if len({l["file"] for l in locs}) > 1}
    print(f"[1] People in >1 shard file: {len(multi)}")
    for n in sorted(multi)[:40]:
        print(f"    {n[:46]:<46} -> {', '.join(sorted({l['file'] for l in multi[n]}))}")
    if len(multi) > 40:
        print(f"    ... and {len(multi) - 40} more")
    issues += len(multi)

    # 2. Shard files on disk not declared in the manifest (so: no region)
    declared = set(manifest.keys())
    undeclared = [f for f in files_on_disk
                  if re.sub(r"\.md$", "", f) != "Family_Tree"
                  and not _declared(re.sub(r"\.md$", "", f), declared)]
    print(f"\n[2] Shard files on disk NOT in the manifest (ungrouped): {len(undeclared)}")
    for f in undeclared:
        print(f"    {f}")
    issues += len(undeclared)

    # 3. Manifest entries with no matching file on disk (stale manifest rows)
    on_disk_bases = {re.sub(r"\.md$", "", f) for f in files_on_disk}
    stale = [k for k in declared if k not in on_disk_bases]
    print(f"\n[3] Manifest entries with no file on disk (stale): {len(stale)}")
    for k in sorted(stale):
        print(f"    {k}  (region: {manifest[k]})")
    issues += len(stale)

    print(f"\n=== tree_locator --check: {issues} structural issue(s) "
          f"(dup-across-shards + manifest/disk mismatches) ===")
    return 1 if issues else 0


def _declared(base, declared):
    """True if `base` matches a manifest key by longest-prefix (mirrors region_for)."""
    return any(base == k or base.startswith(k + "_") for k in declared)


if __name__ == "__main__":
    sys.exit(main())
