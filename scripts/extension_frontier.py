#!/usr/bin/env python3
"""extension_frontier.py — who is the tree NOT extended above, and is that on purpose?

WHY IT EXISTS. Line-extension work in this vault has always been organised by
CHAIN: pick a named line (Capetian, Rurikid, Carolingian, Dunkeld/Alpin, Leinster),
walk it up until it hits a documented terminus, stop. That is a good way to extend a
line and a bad way to notice a line you never started. A person added as a
completeness leaf — most often a WIFE added by a "wives pass" — is never the head of
a chain, so no later pass ever treats them as a frontier.

The concrete failure this was written for (22 JUL 2026): **Hedwig of Saxony** sat at
Gen 37 as the mother of Hugh Capet with NO parents edge, and the omission survived
several extension passes. Her parentage was neither unknown nor contested — Cawley
gives it, FamilySearch carries it, and the operator found it in one click on
Wikipedia. The vault simply had no report that asked "who has no parents?".

WHAT IT REPORTS. Every person with NO `parents` edge, split by whether the entry
says WHY:

  DECLARED   the prose gives a reason — terminus, unknown parentage, legendary,
             ceiling, explicitly speculative. Not work; a recorded decision.
  SILENT     no parents edge and no stated reason. THIS IS THE WORKLIST. Each one
             is either a real extension opportunity or a missing terminus note, and
             you cannot tell which without looking — which is the point.

A SILENT row is not an accusation that the parents are known. It says the vault has
not recorded either the parents or a reason there are none. Both outcomes are
progress: extend the line, or write the terminus down so it stops appearing here.

Rows are ranked by generation ascending (shallower = closer to the subject = cheaper
to verify and more likely to matter), then by evidence tier.

USAGE
  python3 scripts/extension_frontier.py                  # SILENT rows, all gens
  python3 scripts/extension_frontier.py --gen-min 29     # deep medieval only
  python3 scripts/extension_frontier.py --all            # DECLARED rows too
  python3 scripts/extension_frontier.py --csv
  python3 scripts/extension_frontier.py --summary        # counts only (banner use)

Advisory. Never blocks a commit: a silent frontier is a research to-do, not a defect.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_person_index as g  # noqa: E402
import vault_config  # noqa: E402

PARENTS_RE = re.compile(r"parents:\s*'\[")
SPOUSE_RE = re.compile(r"spouse:\s*'\[")
TIER_RE = re.compile(r"evidence_tier:\s*(\w+)")
LIVING_RE = re.compile(r"life_status:\s*(living|unknown)")

# A reason to have no parents. Deliberately broad: this gate is trying NOT to nag
# about decisions already recorded, so a false "DECLARED" is cheaper than a false
# "SILENT" that trains the reader to ignore the report.
DECLARED_RE = re.compile(
    r"terminus|reliability ceiling"
    # "not given"/"not stated"/"not recorded" are how Cawley-derived entries phrase a
    # dead end, and omitting them produced a FALSE SILENT on Pavia, whose entry already
    # said "Parentage not given by Cawley". A missed DECLARED is the expensive error
    # here: it sends someone researching a question the vault already closed.
    r"|parentage[^.;]{0,40}(?:unknown|not known|not given|not stated|not recorded|unproven|doubtful|not securely)"
    r"|parents? (?:are )?(?:unknown|not known|not recorded)|no parents recorded|brick wall"
    r"|legendary|fabricat|unknown per Cawley|origin.{0,24}(?:unknown|doubt)"
    r"|NOT WORKED|not yet worked|deliberate stop|do NOT (?:adopt|extend)",
    re.I,
)


def rows_with_bodies(vault):
    """Person records joined to their FULL narrative block (not just the meta line).

    parse_narrative()'s `block` is the meta line; the reason a person has no parents
    is written in the surrounding prose, so the body has to be read from the file.
    """
    import pathlib
    vault = pathlib.Path(vault)
    bodies = {}
    for path in sorted(vault.glob("Family_Tree*.md")):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        idx = [i for i, l in enumerate(lines) if l.startswith("**")]
        for a, b in zip(idx, idx[1:] + [len(lines)]):
            chunk = "".join(lines[a:b])
            m = re.search(r"- meta: \{id: (P-[0-9A-Z]{6})", chunk)
            if m:
                bodies[m.group(1)] = chunk
    out = []
    for p in g.parse_narrative():
        pid = p.get("id")
        body = bodies.get(pid, p.get("block") or "")
        meta = p.get("block") or ""
        if PARENTS_RE.search(meta):
            continue
        if LIVING_RE.search(meta):
            continue  # living/unknown are privacy-excluded from research anyway
        tier = TIER_RE.search(meta)
        out.append({
            "id": pid,
            "name": p.get("name") or "?",
            "gen": p.get("gen"),
            "file": p.get("file") or "?",
            "tier": tier.group(1) if tier else "",
            "spouse": bool(SPOUSE_RE.search(meta)),
            "declared": bool(DECLARED_RE.search(body)),
        })
    return out


TIER_ORDER = {"strong_signal": 0, "moderate_signal": 1, "speculative": 2, "": 3}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--gen-min", type=int)
    ap.add_argument("--gen-max", type=int)
    ap.add_argument("--all", action="store_true", help="include DECLARED rows")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    rows = rows_with_bodies(vault)
    if a.gen_min is not None:
        rows = [r for r in rows if r["gen"] is not None and r["gen"] >= a.gen_min]
    if a.gen_max is not None:
        rows = [r for r in rows if r["gen"] is not None and r["gen"] <= a.gen_max]

    silent = [r for r in rows if not r["declared"]]
    declared = [r for r in rows if r["declared"]]

    if a.summary:
        print(f"EXTENSION FRONTIER: SILENT {len(silent)} (no parents, no stated reason); "
              f"DECLARED {len(declared)}; total parentless {len(rows)}")
        return 0

    show = rows if a.all else silent
    show.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0, TIER_ORDER.get(r["tier"], 3)))

    if a.csv:
        print("id,name,gen,tier,spouse_linked,status,file")
        for r in show:
            nm = '"%s"' % r["name"].replace('"', "'")
            print(f"{r['id']},{nm},{r['gen']},{r['tier']},{int(r['spouse'])},"
                  f"{'DECLARED' if r['declared'] else 'SILENT'},{r['file']}")
        return 0

    print("=" * 78)
    print("EXTENSION FRONTIER — people with no `parents` edge (advisory)")
    print("=" * 78)
    print("  SILENT = no parents recorded AND no reason given. Either extend the line,")
    print("  or write the terminus into the entry so it stops appearing here.")
    print("  `sp` marks an entry that has a spouse edge — the completeness-leaf class")
    print("  that chain-by-chain passes cannot see (this is how Hedwig was missed).\n")
    for r in show:
        gen = f"Gen {r['gen']:>2}" if r["gen"] is not None else "Gen  ?"
        tag = "sp" if r["spouse"] else "  "
        st = "DECLARED" if r["declared"] else "SILENT  "
        print(f"  {st} {gen} {tag} {r['name'][:46]:48} {r['tier'][:8]:9} [{r['file']}]")
    print(f"\n  SILENT {len(silent)}   DECLARED {len(declared)}   total parentless {len(rows)}")
    print("  Advisory only — a silent frontier is a research to-do, not a defect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
