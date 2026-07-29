#!/usr/bin/env python3
"""gen_heading_audit.py — do the `### Generation N` headings agree with the meta fields?

WHY IT EXISTS (29 JUL 2026 framework review). The generation number lives in TWO
places: the `### Generation N` section heading (what the human reads) and the
`generation:` meta field (what every tool reads). Integrity Rule 5 asks the author
to confirm they agree; nothing enforced it, and 83 entries had drifted on the
reference vault — including whole sections where every entry disagreed with its own
heading (a `### Generation 13` section whose entries all carry `generation: 14`).
This is the same defect class DATE_DRIFT was built for: two machine-readable copies
of one fact, disagreeing silently. The human reads one number, the machine reads
another, and derived prose ("her 11th great-grandfather") inherits whichever copy
the writer happened to look at.

THE SANCTIONED EXCEPTION. Files deliberately keep a spouse with their partner's
section rather than splitting couples (the sharding rubric says so). So a mismatch
is ALLOWED when the entry has a `spouse:` edge to a person whose `generation`
matches the heading — that is "kept inline with partner", recorded in the data. A
textual `kept inline`/`kept with` marker in the entry body is honored the same way
for spouses whose partner edge is not yet wired.

WHAT COUNTS
  GEN_HEADING_DRIFT   entry under `### Generation N:` whose meta `generation` is
                      not N, with no sanctioned reason. Advisory; baseline should
                      be driven to 0, then promoted to the pre-commit hook.

Headings stop applying at the next `##`/`###` heading of any kind; entries in
sections without a `### Generation N` heading (collateral stubs, theme sections)
are out of scope — their generation truth is the meta field alone.

USAGE
  python3 scripts/gen_heading_audit.py               # full report
  python3 scripts/gen_heading_audit.py --by-section  # grouped: section -> entry gens
  python3 scripts/gen_heading_audit.py --heartbeat   # one line for the banner
"""
from __future__ import annotations

import argparse
import glob as _glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

HEADING_RE = re.compile(r"^(#{2,6})\s+(.*)$")
GEN_HEADING_RE = re.compile(r"^Generation\s+(\d+)\b[:\s]?", re.I)
META_RE = re.compile(r"^\s*-\s*meta:\s*\{(.*)\}\s*$")
GEN_FIELD_RE = re.compile(r"\bgeneration:\s*(\d+)")
ID_FIELD_RE = re.compile(r"\bid:\s*([A-Za-z0-9?-]+)")
SPOUSE_RE = re.compile(r"spouse:\s*'\[([^\]]*)\]'")
PID_TOKEN_RE = re.compile(r"(P-[0-9A-Za-z]{4,10})")
KEPT_RE = re.compile(r"kept (?:inline|with)", re.I)


def scan(vault):
    """Yield dicts: one per meta-bearing entry under a Generation heading."""
    # First pass: id -> generation, vault-wide (for the spouse allowlist).
    gen_of = {}
    files = sorted(_glob.glob(os.path.join(vault, "Family_Tree*.md")))
    for path in files:
        for ln in open(path, encoding="utf-8"):
            m = META_RE.match(ln)
            if m:
                gid = ID_FIELD_RE.search(m.group(1))
                g = GEN_FIELD_RE.search(m.group(1))
                if gid and g:
                    gen_of[gid.group(1)] = int(g.group(1))

    rows = []
    for path in files:
        heading_gen = None
        heading_text = ""
        entry_block = []  # lines since the current entry's meta, for the KEPT marker
        for ln in open(path, encoding="utf-8"):
            hm = HEADING_RE.match(ln)
            if hm:
                gm = GEN_HEADING_RE.match(hm.group(2).strip())
                heading_gen = int(gm.group(1)) if gm else None
                heading_text = hm.group(2).strip()
                continue
            mm = META_RE.match(ln)
            if mm and heading_gen is not None:
                meta = mm.group(1)
                g = GEN_FIELD_RE.search(meta)
                gid = ID_FIELD_RE.search(meta)
                spouses = PID_TOKEN_RE.findall(
                    SPOUSE_RE.search(meta).group(1)) if SPOUSE_RE.search(meta) else []
                rows.append({
                    "file": os.path.basename(path),
                    "section": heading_text,
                    "heading_gen": heading_gen,
                    "id": gid.group(1) if gid else "?",
                    "gen": int(g.group(1)) if g else None,
                    "spouse_gens": sorted({gen_of[s] for s in spouses if s in gen_of}),
                })
    return rows, gen_of


def body_has_kept_marker(vault, file, entry_id):
    """Cheap targeted check, only run for candidate mismatches.

    Anchors on the entry's OWN `- meta:` line (`id: <entry_id>`), not the first
    file occurrence of the id — the first occurrence is often a RELATIVE's
    `parents:`/`spouse:` edge listing this id, and searching that neighborhood
    missed a real marker sitting on the entry itself (an immigrant-generation
    father whose id first appears in his son's parents edge ~35 lines earlier;
    found on the very first burn-down, corrected 29 JUL 2026).
    """
    path = os.path.join(vault, file)
    text = open(path, encoding="utf-8").read()
    i = text.find(f"id: {entry_id}")
    if i < 0:
        return False
    # the entry's neighborhood: its header just above to ~15 lines of body below
    seg = text[max(0, i - 400): i + 1500]
    return bool(KEPT_RE.search(seg))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--by-section", action="store_true",
                    help="group by section with the entry-gen tally — the fastest "
                         "way to see whether the HEADING or the FIELDS drifted")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    rows, _gen_of = scan(vault)

    drift = []
    for r in rows:
        if r["gen"] is None or r["gen"] == r["heading_gen"]:
            continue
        # Sanctioned: spouse kept with partner whose gen matches the heading.
        if r["heading_gen"] in r["spouse_gens"]:
            continue
        if body_has_kept_marker(vault, r["file"], r["id"]):
            continue
        drift.append(r)

    if a.heartbeat:
        nfiles = len({d['file'] for d in drift})
        print(f"GEN_HEADING_DRIFT: {len(drift)}  [advisory]"
              + (f" across {nfiles} file(s) — heading says one generation, "
                 f"meta says another" if drift else ""))
        return 0

    if a.by_section:
        by = defaultdict(list)
        for d in drift:
            by[(d["file"], d["section"], d["heading_gen"])].append(d["gen"])
        print("=== GEN_HEADING_DRIFT by section (advisory) ===")
        print("  A section whose flagged entries ALL share one other generation is")
        print("  usually a wrong HEADING; a mixed tally needs per-entry judgment.\n")
        for (f, sec, hg), gens in sorted(by.items()):
            tally = defaultdict(int)
            for g in gens:
                tally[g] += 1
            t = ", ".join(f"gen {g} x{n}" for g, n in sorted(tally.items()))
            print(f"  {f} :: {sec[:60]}")
            print(f"      heading Gen {hg} vs entries: {t}")
        print(f"\nGEN_HEADING_DRIFT: {len(drift)}  [advisory]")
        return 0

    print("=== GEN_HEADING_DRIFT — heading vs meta `generation` (advisory) ===")
    for d in drift:
        print(f"  {d['file']} :: {d['section'][:48]:50} heading {d['heading_gen']:>2} "
              f"vs meta {d['gen']:>2}  [{d['id']}]")
    print(f"\nGEN_HEADING_DRIFT: {len(drift)}  [advisory]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
