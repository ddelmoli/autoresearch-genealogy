#!/usr/bin/env python3
"""
chronology_audit.py — check each person's dates against their PARENTS' dates.

`prose_audit`'s DATE_IMPOSSIBLE already catches a person born after they died.
That is a check WITHIN one record. Nothing checked a record against the records
it is wired to, so the vault could assert a parentage that the dates on both ends
forbid — a child born years after both parents were dead — and every gate stayed
green.

Written 27 JUL 2026 after a same-name conflation in which a whole 49-person branch
hung off a link to a man whose own life could not accommodate it. That case had no
death date and so would NOT have been caught here; this check mechanizes the part
of the failure mode that IS mechanizable, and does not claim the class. On its
first run against a live vault it found one real contradiction: a child recorded
`b. ABT 1513` whose BOTH parents were recorded `d. ABT 1510`, with neither death
backed by a record.

CHECKS
  PARENT_DEAD_BEFORE_BIRTH  child born after the parent's LATEST possible death.
                            One year of slack for a posthumous child.
  PARENT_TOO_YOUNG          the parent cannot reach MIN_AGE under any reading.
  PARENT_TOO_OLD            the parent exceeds MAX_AGE under every reading.

⚠ INTERVALS, NOT POINTS — THIS IS THE WHOLE DESIGN.
A GEDCOM DateValue is frequently a RANGE (`BET 877 AND 920`) or a one-sided bound
(`BEF 1292`, `AFT 960`). Collapsing one to a single year and comparing produces
confident nonsense: the first draft of this script reported five findings, and
FOUR were artefacts of resolving `BEF`/`BET` to a point — including one against a
value written the same morning. A finding here means the contradiction survives
the MOST FAVOURABLE reading of both ranges:

  too young  <=>  child_latest  - parent_earliest < MIN_AGE
  too old    <=>  child_earliest - parent_latest  > MAX_AGE
  dead       <=>  child_earliest - parent_latest_death > 1

Get that backwards — test whether SOME reading fails rather than whether EVERY
reading fails — and the check flags honest uncertainty as error. It is an easy
mistake: the first version made it.

An open-ended bound simply yields no finding on that side, which is correct: `BEF
1292` has no lower bound, so no maximum age can be computed from it.

Edges carrying a trailing `?` are still checked but marked, since `?` declares the
edge unverified rather than wrong — a contradiction on one is a reason to drop the
edge, not to trust it.

Advisory (exit 0): a strained-but-possible edge is reported separately and is
usually a real uncertainty rather than a defect.

Usage:
    AUTORESEARCH_VAULT=/path/to/vault python3 scripts/chronology_audit.py
    ... --advisory      # also list the strained-but-possible edges
"""
import argparse
import collections
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import gdate
import person_store as PS
import vault_config

MIN_AGE = 12          # below this no reading is credible
MAX_AGE = 65          # above this, for either parent, no reading is credible
POSTHUMOUS_SLACK = 1  # years after a father's death a child may still be born


def _range(value):
    """(lo, hi) inclusive year bounds for a DateValue; None on either side = open."""
    if not value:
        return None
    try:
        lo, hi = gdate.year_range(value)
    except Exception:
        return None
    if lo is None and hi is None:
        return None
    return (abs(lo) if lo is not None else None,
            abs(hi) if hi is not None else None)


def _parents(rec):
    raw = getattr(rec, "parents", None) or []
    if isinstance(raw, str):
        raw = [x.strip() for x in re.sub(r"[\[\]]", "", raw).split(",") if x.strip()]
    out = []
    for x in raw:
        x = str(x).strip()
        if x:
            out.append((x.rstrip("?"), x.endswith("?")))
    return out


def audit(vault):
    people = {}
    for rec, path, _h, _b in PS.iter_entry_blocks(vault):
        if rec.id:
            people[rec.id] = (rec, os.path.basename(path))
    hard, soft = [], []
    for cid, (child, _f) in people.items():
        cb = _range(child.born)
        if not cb:
            continue
        c_lo, c_hi = cb
        for pid, tentative in _parents(child):
            if pid not in people:
                continue
            parent, pfile = people[pid]
            pb, pd = _range(parent.born), _range(parent.died)
            where = (parent.name, child.name, pfile, tentative)
            if pb:
                p_lo, p_hi = pb
                if p_lo is not None and c_hi is not None and c_hi - p_lo < MIN_AGE:
                    hard.append(("PARENT_TOO_YOUNG", where,
                                 f"max possible age {c_hi - p_lo} "
                                 f"(parent b. {parent.born}, child b. {child.born})"))
                elif p_hi is not None and c_lo is not None and c_lo - p_hi > MAX_AGE:
                    hard.append(("PARENT_TOO_OLD", where,
                                 f"min possible age {c_lo - p_hi} "
                                 f"(parent b. {parent.born}, child b. {child.born})"))
                else:
                    if p_hi is not None and c_lo is not None and c_lo - p_hi < MIN_AGE + 2:
                        soft.append(("young_at_edge", where,
                                     f"as low as {c_lo - p_hi} "
                                     f"(parent b. {parent.born}, child b. {child.born})"))
                    if p_lo is not None and c_hi is not None and c_hi - p_lo > MAX_AGE - 5:
                        soft.append(("old_at_edge", where,
                                     f"as high as {c_hi - p_lo} "
                                     f"(parent b. {parent.born}, child b. {child.born})"))
            if pd and pd[1] is not None and c_lo is not None \
                    and c_lo - pd[1] > POSTHUMOUS_SLACK:
                hard.append(("PARENT_DEAD_BEFORE_BIRTH", where,
                             f"child b. {child.born} is at least {c_lo - pd[1]}y after the "
                             f"parent's latest possible death ({parent.died})"))
    return hard, soft


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--advisory", action="store_true",
                    help="also list strained-but-possible edges")
    args = ap.parse_args()
    vault = vault_config.resolve_vault(args.vault)

    hard, soft = audit(vault)
    print("=== cross-edge chronology (a person vs their PARENTS) ===")
    print("    A finding means the contradiction survives the MOST FAVOURABLE")
    print("    reading of both date ranges. Open-ended bounds yield no finding.")
    print()
    for kind, where, msg in sorted(hard):
        pname, cname, pfile, tent = where
        mark = "?" if tent else " "
        print(f"[{kind}]{mark} {pname[:38]} -> {cname[:32]}")
        print(f"    {msg}")
        print(f"    {pfile}")
    counts = collections.Counter(k for k, _, _ in hard)
    print()
    print(f"CHRONOLOGY: {len(hard)} contradiction(s)"
          + (f"  {dict(counts)}" if counts else ""))
    if args.advisory:
        print(f"\n--- advisory: strained but possible ({len(soft)}) ---")
        for kind, where, msg in sorted(soft):
            pname, cname, _pf, tent = where
            print(f"[{kind}]{'?' if tent else ' '} {pname[:34]} -> {cname[:30]}  {msg}")
    else:
        print(f"  ({len(soft)} strained-but-possible edges; --advisory to list them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
