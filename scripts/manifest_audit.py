#!/usr/bin/env python3
"""manifest_audit.py — does a generation heading still hold the people it names?

WHY IT EXISTS (Q340, raised 26 AUG 2026). The File Index table in `Family_Tree.md`
is the vault's map of which shard holds what, and NOTHING checked a row against its
own file. Two rows were found by hand, in one lineage, in one sitting, describing
families that had either left or never arrived.

⭐ THE MECHANISM, AND WHY THIS CHECK IS AIMED WHERE IT IS. A File Index row is
written from the file's SECTION HEADINGS, and **a split updates the row it creates,
never the row it empties**. Each split correctly appended its own "Gen 15-16 split
to X" note while the front half of the sentence went on naming families that had
gone. Four splits later the row was mostly false and every individual edit had been
correct. So the EMPTY HEADING is the upstream cause: it is what the stale row was
written from, and catching it catches the row before it is ever written.

WHAT COUNTS
  MANIFEST_EMPTY_HEADING   a `### Generation N` heading whose section holds no
                           person entry AND no wikilink pointer. Advisory.

⭐ THE POINTER IS THE DISCRIMINATOR, AND IT IS STRUCTURAL. An emptied heading kept
deliberately as a signpost carries a pointer naming where the people went; a
`[[wikilink]]` in the section body IS that pointer, and testing for one separates
the two populations exactly. ⛔ Do NOT test for the word "moved" instead: the
vault writes the pointer at least four ways ("— MOVED" in the heading, "**Moved
<date>** to [[X]]", "EMPTY SINCE AN EARLIER SPLIT, kept as a pointer", "split to
[[X]]"), and a word match scored 17 pointered sections three different ways while
the wikilink test scored all 17 the same way. The wikilink tests what the
remediation actually requires — a destination a reader can follow — rather than the
sentence someone happened to write around it.

⚠ A FINDING IS NOT AUTOMATICALLY A DELETION, and the two kinds need OPPOSITE fixes:
  - **emptied by a split** -> add a pointer naming where the people went;
  - **a reservation for work never done** -> must NOT get a pointer, because
    "moved to X" would be false; either delete the heading or say what it reserves.
The discriminator between THOSE two is whether a person entry of that surname
exists anywhere in the vault, which is a judgement call this check does not make.
Read the rows.

⛔ WHAT IT CANNOT DO, SAID PLAINLY. It checks headings, not prose. The most
misleading clause found in the incident that raised Q340 was a row's claim to be
"the vault's single home" for a whole class of ancestry, which was false and is
unreachable by this check or any of Q340's other two. A green reading is NOT
"the File Index is true".

SCOPE. Section extent follows the markdown nesting rule: a heading's section runs
to the next heading at the SAME OR SHALLOWER level, so a Generation heading whose
entries live under `####` subheadings is correctly seen as populated.

USAGE
  python3 scripts/manifest_audit.py               # full report
  python3 scripts/manifest_audit.py --pointered    # also list the resolved sections
  python3 scripts/manifest_audit.py --heartbeat    # one line for the banner
"""
from __future__ import annotations

import argparse
import glob as _glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import person_store  # noqa: E402
import vault_config  # noqa: E402

# Heading grammar: kept compatible with person_store's own `_GEN_HDR`, which is
# what decides a person's generation fallback. One grammar, one meaning.
GEN_HEADING_RE = re.compile(r"^(#{1,6})\s+Generation\s+(\d+)", re.I)
ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")


def scan(vault):
    """Yield one dict per Generation heading that holds no person entry.

    Entry positions come from `person_store.iter_entry_blocks` — the sanctioned
    reader. ⛔ Never re-derive them from a bold-name pattern here: a sanctioned
    body bullet (`- **Sources**`, `- **Prior work**`) is indistinguishable from an
    entry header under a naive rule, and a hand-rolled chunker does not fail
    quietly, it MISFILES.
    """
    entry_lines = defaultdict(list)
    for _rec, path, hline, _block in person_store.iter_entry_blocks(vault):
        entry_lines[path].append(hline)

    rows = []
    for path in sorted(_glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        headings = [(i, len(m.group(1)))
                    for i, ln in enumerate(lines)
                    for m in [ANY_HEADING_RE.match(ln)] if m]
        here = entry_lines.get(path, [])
        for idx, (i, level) in enumerate(headings):
            if not GEN_HEADING_RE.match(lines[i]):
                continue
            # Section runs to the next heading at the same or a shallower level.
            end = len(lines)
            for j, other_level in headings[idx + 1:]:
                if other_level <= level:
                    end = j
                    break
            if any(i < e < end for e in here):
                continue
            body = "\n".join(lines[i + 1:end])
            rows.append({
                "file": os.path.basename(path),
                "line": i + 1,
                "heading": lines[i].strip(),
                "pointered": bool(WIKILINK_RE.search(body)),
            })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--pointered", action="store_true",
                    help="also list the sections that ARE pointered — the resolved "
                         "population, shown so a reader can check the discrimination "
                         "rather than take the count on trust")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    rows = scan(vault)
    findings = [r for r in rows if not r["pointered"]]
    pointered = [r for r in rows if r["pointered"]]

    if a.heartbeat:
        nfiles = len({r["file"] for r in findings})
        extra = (f" across {nfiles} file(s); {len(pointered)} more are empty but "
                 f"POINTERED (resolved)" if findings else "")
        print(f"MANIFEST_EMPTY_HEADING: {len(findings)}  [advisory]{extra}")
        return 0

    print("=== MANIFEST_EMPTY_HEADING — a generation heading with no entries "
          "and no pointer (advisory) ===")
    print("  A finding is NOT automatically a deletion: an emptied-by-a-split")
    print("  heading wants a pointer; a reservation for work never done must NOT")
    print("  get one. Read the row before fixing it.\n")
    for r in findings:
        print(f"  {r['file']}:{r['line']}")
        print(f"      {r['heading'][:96]}")
    if a.pointered:
        print(f"\n  --- empty but POINTERED ({len(pointered)}), not findings ---")
        for r in pointered:
            print(f"  {r['file']}:{r['line']}  {r['heading'][:80]}")
    print(f"\nMANIFEST_EMPTY_HEADING: {len(findings)}  [advisory]"
          f"   (+{len(pointered)} empty but pointered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
