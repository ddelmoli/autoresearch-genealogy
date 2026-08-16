#!/usr/bin/env python3
"""generation_audit.py — is every stored `generation` still the label the GRAPH implies?

WHY IT EXISTS (15 AUG 2026, session #172).

`generation` is a PATH LABEL: the distance from the anchor set, counted up through
`parents` edges. Nothing checked it against the actual edges. `build_edges
--validate` compares a parent to its child ONE EDGE AT A TIME, which catches a
local disagreement but is blind to a label that is wrong *consistently* — and
that is the failure that actually happened.

** THE INCIDENT. ** On 03 AUG 2026 a parent edge was DISPROVED and detached
(correctly: the printed town register gave that couple five children and not the
one claimed). The deletion was right. But **every generation label that had been
computed THROUGH that edge stayed behind**, and nothing connected the two events.
Two weeks later the residue surfaced as four PARENT-GEN mismatches in a different
surname, looking like four unrelated numbering slips. Re-deriving from the graph
found them in one pass — and found seven more rows nobody had reported.

⛔⛔ AND THE OBVIOUS IMPLEMENTATION IS WORSE THAN NOTHING. A naive shortest-path
BFS flags **the entire ancestry above every declared pedigree collapse** as
drifted. Measured on this vault the day it was written: naive walk **26 drifted
rows, every one of them CORRECT**; collapse-aware walk **0**. Applying the naive
result would have renumbered 19 correct medieval ancestors and silently undone 5
declarations — precisely the "never renumber to make the arithmetic agree" error
this vault has a standing rule against, wearing the costume of a tidy mechanical
fix.

⚠ The tell was **uniformity**: 19 identical `-1`s in one branch is one structural
cause, not 19 independent errors. A drift report whose rows all differ by the
same amount is describing your walk, not the vault.

HOW THE COLLAPSE-AWARE WALK WORKS

  A person named as the PARENT end of a `known_gen_collapse` declaration is
  PINNED to their stored generation. That is what the declaration asserts: two
  descent paths of different length reach this person, and the vault keeps the
  longer label deliberately. Ancestors above them are then computed from the
  pinned value, so the whole branch above a collapse comes out correct.

  Everyone else is `min(child) + 1` over their wired children — the ordinary
  shortest-path rule.

WHAT IT REPORTS

  GEN_DRIFT      stored `generation` != the collapse-aware computed value.
                 Baseline **0**. A non-zero is a REGRESSION, and the usual cause
                 is an edge that was added or removed without re-deriving the
                 labels downstream of it.

  UNREACHABLE    a person with a stored `generation` whom no chain of `parents`
                 edges connects to the anchor set. NOT a defect — collateral,
                 spouses of ancestors, and deliberately detached non-ancestors
                 all look like this. Reported only with --unreachable, because
                 the count is large and boring.

⚠ THIS TOOL NEVER WRITES. A drifted row is a CANDIDATE: read the entry, work out
whether the label or the edge is wrong, and if it is a genuine collapse DECLARE
it in `.autoresearch.json` rather than renumbering. ⚠ And when you do change a
`generation`, MOVE THE ENTRY to a matching `### Generation N` section in the same
commit — the meta and the heading are two records of one fact, and
`person_store.set_meta_key` only writes one of them. `gen_heading_audit.py`
caught that omission twice in the session that wrote this file.

Usage:
    python3 scripts/generation_audit.py [--vault PATH]
    python3 scripts/generation_audit.py --heartbeat
    python3 scripts/generation_audit.py --naive        # show the trap, for teaching
    python3 scripts/generation_audit.py --unreachable
"""

import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

META_RE = re.compile(r"- meta: \{id: (P-[0-9A-Z]{6})(.*)")
GEN_RE = re.compile(r"generation: (\d+)")
PARENTS_RE = re.compile(r"parents: '\[([^\]]*)\]'")
IDTOK_RE = re.compile(r"P-[0-9A-Z]{6}")
BOLD_LEAD_RE = re.compile(r"^\s*(?:[-*]\s*)?\*\*(.+?)\*\*")


def load(vault):
    """-> (people, parents, anchors, declared_parent_ids).

    ⚠ The display-name reader accepts BOTH entry forms — a bold name at line
    start AND the bullet form `- **Name** (...)`. A line-start-only reader
    silently attaches the PREVIOUS entry's name to every bullet-form entry,
    which is how two rows in this vault were briefly reported under the wrong
    person during the session that wrote this file.
    """
    people, parents = {}, collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        name = None
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                b = BOLD_LEAD_RE.match(line)
                if b and not line.lstrip().startswith(">"):
                    name = b.group(1)
                m = META_RE.match(line)
                if not m:
                    continue
                pid, rest = m.group(1), m.group(2)
                g = GEN_RE.search(rest)
                people[pid] = {
                    "id": pid, "name": name,
                    "gen": int(g.group(1)) if g else None,
                    "file": os.path.basename(path),
                }
                pm = PARENTS_RE.search(rest)
                if pm:
                    for tok in pm.group(1).split(","):
                        t = tok.strip().rstrip("?")
                        if IDTOK_RE.fullmatch(t):
                            parents[pid].append(t)
    cfg = {}
    cfgp = os.path.join(vault, ".autoresearch.json")
    if os.path.exists(cfgp):
        cfg = json.load(open(cfgp, encoding="utf-8"))
    raw = (cfg.get("anchor") or {}).get("people") or []
    anchors = [p["id"] if isinstance(p, dict) else p for p in raw]
    declared = {e["parent"] for e in cfg.get("known_gen_collapse", []) if e.get("parent")}
    return people, parents, anchors, declared


def compute(people, parents, anchors, declared, collapse_aware=True):
    """Generation by walk. Iterated to a fixpoint so that a later, shorter route
    correctly lowers a label already assigned — a single-pass BFS with in-place
    minimisation does not guarantee that."""
    dist = {a: 1 for a in anchors if a in people}
    # A declared collapse PARENT is pinned to the label the declaration asserts.
    pins = {}
    if collapse_aware:
        pins = {p: people[p]["gen"] for p in declared
                if p in people and people[p]["gen"] is not None}
    dist.update(pins)
    changed = True
    while changed:
        changed = False
        for child in list(dist):
            for par in parents.get(child, []):
                if par not in people:
                    continue
                if par in pins:
                    continue          # pinned: the declaration is authoritative
                cand = dist[child] + 1
                if par not in dist or cand < dist[par]:
                    dist[par] = cand
                    changed = True
    return dist


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--naive", action="store_true",
                    help="also run the NAIVE walk, to show what it would wrongly flag")
    ap.add_argument("--unreachable", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    vault = vault_config.resolve_vault(a.vault)
    people, parents, anchors, declared = load(vault)
    if not anchors:
        print("GEN_DRIFT: no anchor set in .autoresearch.json — cannot compute.")
        return 0

    dist = compute(people, parents, anchors, declared, collapse_aware=True)
    drift = [(p, people[p], dist[p]) for p in dist
             if people[p]["gen"] is not None and people[p]["gen"] != dist[p]]
    drift.sort(key=lambda r: -abs(r[1]["gen"] - r[2]))

    if a.heartbeat:
        extra = ""
        if a.naive:
            nd = compute(people, parents, anchors, declared, collapse_aware=False)
            n = sum(1 for p in nd if people[p]["gen"] is not None and people[p]["gen"] != nd[p])
            extra = f"; naive walk would flag {n} (ALL of them above declared collapses)"
        print(f"GEN_DRIFT: {len(drift)}  [stored vs collapse-aware computed; baseline 0]"
              f"  reachable {len(dist)}/{len(people)}{extra}")
        return 0

    print("=== GEN_DRIFT — stored `generation` vs the collapse-aware graph walk ===")
    print(f"  anchors: {', '.join(anchors)}   reachable: {len(dist)}/{len(people)}")
    print(f"  declared-collapse parents pinned: {len([p for p in declared if p in people])}\n")
    if not drift:
        print("  GEN_DRIFT: 0 — every reachable stored generation matches the graph.\n")
    for pid, rec, comp in drift[:a.limit]:
        print(f"  {pid}  {(rec['name'] or '')[:38]:38} stored {rec['gen']:>3} -> "
              f"computed {comp:>3} ({comp - rec['gen']:+d})  {rec['file'][:30]}")
    if len(drift) > a.limit:
        print(f"  ... and {len(drift) - a.limit} more (--limit N)")

    if a.naive:
        nd = compute(people, parents, anchors, declared, collapse_aware=False)
        nb = [p for p in nd if people[p]["gen"] is not None and people[p]["gen"] != nd[p]]
        print(f"\n  ⛔ NAIVE (shortest-path) walk would flag {len(nb)} rows.")
        print("     Those extra rows are the ancestry ABOVE declared collapses and are")
        print("     CORRECT. Renumbering them would silently undo the declarations.")

    if a.unreachable:
        un = [p for p in people if p not in dist and people[p]["gen"] is not None]
        print(f"\n  UNREACHABLE (has a generation, no parents-chain to an anchor): {len(un)}")
        print("     NOT a defect: collateral, spouses of ancestors, detached non-ancestors.")

    print(f"\nGEN_DRIFT: {len(drift)}  [baseline 0]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
