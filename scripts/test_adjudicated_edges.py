#!/usr/bin/env python3
"""Regression tests for the `adjudicated` meta key (deferred_decisions 32).

Runnable with no test framework: `python3 scripts/test_adjudicated_edges.py`
(exit 0 = pass).

WHAT THIS FIXES. A `?` on an edge id means two different things:
  (a) "nobody has checked this yet", and
  (b) "somebody checked it and the `?` is CORRECT" -- an FS-GAP (an endpoint has
      no FS profile), a SCHOLARLY HEDGE (FS asserts it and the best authority
      doubts it), or PRIVACY (an endpoint is living/unknown).
`lane_verify` keyed on the mark alone, so (b) looked exactly like (a) and was
re-offered every session. Measured on the reference vault: of 135 `?` edges only
35 were FS-checkable at all and 5 of those had already been judged; two more
carried hedges written in ordinary prose that no pattern matches -- which is
precisely why the marker has to live in the DATA and not in the narrative.

WHY IT MATTERED ENOUGH TO CHANGE THE GRAMMAR. The lane floor is a count of PEOPLE
(operator, 01 AUG 2026: at least 1.5% of the vault per draw, the same in every
lane), and `22-research-iterations` requires a disposition to REMOVE the person
from the pool -- "prose alone is not a disposition". So classifying an edge and
correctly retaining its `?` left the row in the pool forever and could NEVER count
toward the floor, however much work it took. This key is what makes that work
countable.

** WHY A SEPARATE KEY RATHER THAN A THIRD TOKEN STATE (`P-XXXXXX?!`). **
`build_edges.edge_value` regenerates every edge token as
`pid + ("" if verified else "?")`. Any suffix beyond the bare `?` is therefore
silently destroyed by the next `build_edges --apply` -- data loss with no error.
`upsert_edges` splices parents:/spouse: "WITHOUT disturbing any other field", so a
sibling key survives by construction. That is the whole design rationale, and it
is asserted here (test: round-trip through build_edges preserves the key).

Every assertion is paired with a negative control that reintroduces the fault at
runtime. A regression fixture that cannot be made to fail proves nothing.
"""
import json
import os
import shutil
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import build_edges as BE
import person_store as PS
import session_plan as SP

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def vault(text):
    d = tempfile.mkdtemp(prefix="adjudicated-")
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        json.dump({"person_model": "narrative"}, f)
    with open(os.path.join(d, "Family_Tree_Fixture.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return d


def verify_rows(text, include_adjudicated=False):
    """{display_name: why-string} from lane_verify for a one-file fixture vault."""
    import gen_person_index as G
    d = vault(text)
    saved_g = G.VAULT
    try:
        G.VAULT = d
        return {r["name"]: r["why"]
                for r in SP.lane_verify(d, include_adjudicated=include_adjudicated)}
    finally:
        G.VAULT = saved_g
        shutil.rmtree(d)


class mark_only_counting:
    """Negative control: reinstate the exact fault -- count every `?` token and
    ignore the `adjudicated` key entirely, which is what the builder did before."""

    def __enter__(self):
        self._saved = SP.lane_verify
        SP.lane_verify = lambda v, include_adjudicated=False: self._saved(
            v, include_adjudicated=True)
        return self

    def __exit__(self, *exc):
        SP.lane_verify = self._saved
        return False


# --- fixtures ---------------------------------------------------------------

# Two `?` parent edges. NOTHING adjudicated: both are open work.
OPEN = """### Generation 9

**Ada Unwalked** (b. 1700; d. 1770)
- meta: {id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: AAAA-111, parents: '[P-BBB222?, P-CCC333?]'}
- Nobody has walked either edge.
"""

# The SAME entry with ONE of the two adjudicated: one open, one settled.
HALF = """### Generation 9

**Ada Unwalked** (b. 1700; d. 1770)
- meta: {id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: AAAA-111, parents: '[P-BBB222?, P-CCC333?]', adjudicated: '[P-CCC333]'}
- Walked 01 AUG 2026: the mother edge is an FS-GAP (she has no FS profile); `?` retained.
"""

# BOTH adjudicated: the entry is settled and must not be offered at all.
SETTLED = """### Generation 9

**Ada Unwalked** (b. 1700; d. 1770)
- meta: {id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: AAAA-111, parents: '[P-BBB222?, P-CCC333?]', adjudicated: '[P-BBB222, P-CCC333]'}
- Walked 01 AUG 2026: FS contradicts both, and the vault's reading rests on records.
"""

# A living person: excluded at source, adjudicated or not (privacy).
LIVING = """### Generation 3

**Bess Living** (b. 1950)
- meta: {id: P-DDD444, profile_status: partial, life_status: living, generation: 3, parents: '[P-EEE555?]'}
- Never web-searched.
"""


def main():
    print("== an unadjudicated `?` edge is still offered ==")
    o = verify_rows(OPEN)
    check("Ada Unwalked" in o, "the entry is offered")
    check("2 parents" in o.get("Ada Unwalked", ""), "both `?` edges counted as open")
    check("already adjudicated" not in o.get("Ada Unwalked", ""),
          "no settled-count note when nothing is adjudicated")

    print("\n== a PARTIALLY adjudicated entry offers only the open edge ==")
    h = verify_rows(HALF)
    check("Ada Unwalked" in h, "still offered - one edge remains open")
    check("1 parents" in h.get("Ada Unwalked", ""),
          "counts ONE open edge, not two (the adjudicated one is subtracted)")
    check("1 already adjudicated" in h.get("Ada Unwalked", ""),
          "...and SAYS the other was adjudicated, rather than hiding it")

    print("\n== a FULLY adjudicated entry is not offered at all ==")
    s = verify_rows(SETTLED)
    check("Ada Unwalked" not in s,
          "settled work leaves the pool - this is what makes it countable")

    print("\n== negative control: count the MARK only, ignore the key ==")
    with mark_only_counting():
        n_settled = verify_rows(SETTLED)
        n_half = verify_rows(HALF)
    check("Ada Unwalked" in n_settled,
          "the fully-adjudicated entry is re-offered again (control works)")
    check("2 parents" in n_half.get("Ada Unwalked", ""),
          "and the half-adjudicated entry counts both edges again")

    print("\n== --include-adjudicated brings them back for an audit pass ==")
    a = verify_rows(SETTLED, include_adjudicated=True)
    check("Ada Unwalked" in a, "settled entry is visible under the audit flag")
    check("2 parents" in a.get("Ada Unwalked", ""), "with its full `?` count")

    print("\n== privacy still wins: living entries never reach the lane ==")
    for flag in (False, True):
        check("Bess Living" not in verify_rows(LIVING, include_adjudicated=flag),
              f"living excluded at source (include_adjudicated={flag})")

    print("\n== the key round-trips through the person_store seam ==")
    d = vault(HALF)
    try:
        rec = [r for r in PS.iter_people(d) if r.id == "P-AAA111"][0]
        check(rec.adjudicated == ["P-CCC333"], "parsed off the meta block")
        check(sorted(rec.parents) == ["P-BBB222?", "P-CCC333?"],
              "and the `?` markers on the edges themselves are untouched")
        rec.adjudicated = ["P-BBB222", "P-CCC333"]
        PS.write_person(d, rec)
        back = [r for r in PS.iter_people(d) if r.id == "P-AAA111"][0]
        check(sorted(back.adjudicated) == ["P-BBB222", "P-CCC333"],
              "written and read back")
        check(sorted(back.parents) == ["P-BBB222?", "P-CCC333?"],
              "writing it does NOT disturb the edge tokens")
    finally:
        shutil.rmtree(d)

    print("\n== THE DESIGN RATIONALE: build_edges must not eat the key ==")
    # edge_value regenerates tokens as pid + ("" if verified else "?"), which is
    # why a `P-XXXXXX?!` third state could not survive. Assert both halves.
    regenerated = BE.edge_value("'[P-BBB222?, P-CCC333]'", [])
    check("P-BBB222?" in regenerated and "P-CCC333" in regenerated,
          "edge_value preserves each id's verified state")
    check("?!" not in BE.edge_value("'[P-BBB222?!]'", []),
          "...and would DESTROY a `?!` suffix - the reason for a separate key")
    line = ("- meta: {id: P-AAA111, generation: 9, parents: '[P-BBB222?]', "
            "adjudicated: '[P-CCC333]'}")
    spliced = BE.upsert_edges(line, ["P-BBB222"], None)
    check("adjudicated: '[P-CCC333]'" in spliced,
          "upsert_edges splices edges WITHOUT disturbing the adjudicated key")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
