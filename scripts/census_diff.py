#!/usr/bin/env python3
"""Report EVERY census row a change moves -- the check nothing else performs.

The source-coverage census is the vault's only measure of how well documented each
person is, and it is *non-monotonic*: negating a locator can move a count either way,
because `~` is resolved over a whole entry and because records, not tokens, are counted.
So the direction of travel cannot be reasoned about -- it has to be measured, per row,
before and after.

⭐⭐ WHY THIS EXISTS. Every source-crediting defect this vault has found was invisible to
every gate and visible only to a per-row census diff, run by hand:

  * an entry reading SOURCE_GAP / 0 ARKs while citing a birth AND a marriage, because an
    audit bullet quoted its own locators negated;
  * two Gen-13 people reading WELL_SOURCED on 26 and 12 ARKs whose entries recorded that
    their births, parents and marriage were all unknown -- every locator was a child's
    baptism (rule 8 limb (g));
  * a bulk edit that matched five entries where two were intended and deleted the only
    citations on two people, while the commit message said "nothing is lost".

In each case integrity, prose_audit, entry_boundary, bare_ark and entry_attribution all
stayed green. **The row diff caught all three.** Automating it is the difference between
a discipline that depends on remembering and one that does not.

⛔ IT ANSWERS "WHAT MOVED", NEVER "WAS THAT RIGHT". A row moving is not a defect: an
EXPAND iteration that mints parents legitimately pushes SOURCE_GAP up, and removing a
phantom credit legitimately pushes a count down. The tool's whole contribution is that a
human or a commit message has to ACCOUNT for each moved row. Silence is what it removes,
not judgement.

HOW IT WORKS. The comparison runs `harvest_sources.py --csv` twice as a SUBPROCESS -- once
against the working tree and once against a materialised copy of the vault at a git ref --
rather than importing the census builder twice. That is deliberate: `harvest_sources`
resolves its vault into a module-level global at import time, so an in-process second run
would grade the wrong tree, silently. A subprocess with `AUTORESEARCH_VAULT` set is the
same path the operator uses, which is the only one worth trusting.

    python3 scripts/census_diff.py                    # working tree vs HEAD
    python3 scripts/census_diff.py --since HEAD~3     # vs an older ref
    python3 scripts/census_diff.py --quiet            # print only when rows moved
"""
import argparse
import csv
import io
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import vault_config

HARVEST = os.path.join(SCRIPT_DIR, "harvest_sources.py")


def _census(vault_path):
    """pid/id -> row dict, by running the census exactly as the operator would."""
    env = dict(os.environ, AUTORESEARCH_VAULT=str(vault_path))
    r = subprocess.run([sys.executable, HARVEST, "--csv"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"census failed for {vault_path}:\n{r.stderr[-2000:]}")
    rows = {}
    for row in csv.DictReader(io.StringIO(r.stdout)):
        # Key on the vault id, which is the only stable identity; an FS PID is an
        # external attribute and a name is a display string.
        key = row.get("id") or f"?{row.get('pid','')}|{row.get('name','')}"
        rows[key] = row
    return rows


def _materialise(vault, ref, dest):
    """Extract the vault at `ref` into `dest` via `git archive`.

    The whole tracked tree, not a pathspec: the census reads `.autoresearch.json` for
    hosts and structural-gap rules, and a copy missing them would grade a different
    policy and call the difference a change.
    """
    p1 = subprocess.Popen(["git", "-C", str(vault), "archive", ref],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = subprocess.Popen(["tar", "-x", "-C", str(dest)], stdin=p1.stdout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p1.stdout.close()
    p2.communicate()
    err = p1.stderr.read().decode(errors="replace")
    if p2.returncode != 0 or not os.listdir(dest):
        raise RuntimeError(f"could not materialise {ref}: {err.strip() or 'empty tree'}")


def diff(vault, ref="HEAD"):
    """(moved, added, removed, totals_before, totals_after)."""
    after = _census(vault)
    with tempfile.TemporaryDirectory() as tmp:
        _materialise(vault, ref, tmp)
        before = _census(tmp)

    moved = []
    for key, a in after.items():
        b = before.get(key)
        if b is None:
            continue
        if b["category"] != a["category"] or b["ark_count"] != a["ark_count"]:
            moved.append((a.get("name", "?"), b["category"], b["ark_count"],
                          a["category"], a["ark_count"], key))
    added = [(a.get("name", "?"), a["category"], a["ark_count"], k)
             for k, a in after.items() if k not in before]
    removed = [(b.get("name", "?"), b["category"], b["ark_count"], k)
               for k, b in before.items() if k not in after]

    def totals(rows):
        t = {}
        for r in rows.values():
            t[r["category"]] = t.get(r["category"], 0) + 1
        return t

    return moved, added, removed, totals(before), totals(after)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", help="vault path (default: resolved as usual)")
    ap.add_argument("--since", default="HEAD", help="git ref to compare against (default HEAD)")
    ap.add_argument("--quiet", action="store_true",
                    help="print nothing when no row moved (for hook use)")
    a = ap.parse_args()

    vault = vault_config.resolve_vault(a.vault)
    try:
        moved, added, removed, tb, ta = diff(vault, a.since)
    except RuntimeError as e:
        # A missing ref or a non-repo vault must not block a commit: this is advisory.
        print(f"CENSUS_DIFF: skipped — {e}")
        return 0

    if a.quiet and not (moved or added or removed):
        return 0

    print(f"=== CENSUS DIFF — working tree vs {a.since} ===")
    for name, bc, bn, ac, an, key in sorted(moved):
        print(f"  {name[:38]:40} {bc}/{bn:<3} ->  {ac}/{an}   {key}")
    for name, c, n, key in sorted(added):
        print(f"  {name[:38]:40} NEW  ->  {c}/{n}   {key}")
    for name, c, n, key in sorted(removed):
        print(f"  {name[:38]:40} {c}/{n} ->  GONE   {key}")

    changed_cats = sorted(set(tb) | set(ta))
    deltas = [f"{c} {tb.get(c,0)}->{ta.get(c,0)}" for c in changed_cats
              if tb.get(c, 0) != ta.get(c, 0)]
    print()
    print(f"CENSUS_DIFF: {len(moved)} row(s) moved, {len(added)} added, "
          f"{len(removed)} removed  [advisory]")
    if deltas:
        print("  categories: " + "; ".join(deltas))
    if moved or added or removed:
        print("  ⚠ ACCOUNT FOR EVERY ROW ABOVE. A move is not a defect — minting parents")
        print("    raises SOURCE_GAP, and removing a phantom credit lowers a count — but a")
        print("    row you cannot explain is the one worth opening.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
