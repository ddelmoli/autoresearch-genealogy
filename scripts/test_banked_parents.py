#!/usr/bin/env python3
"""test_banked_parents.py — the `banked_parents` meta key and its IMPROVE tier.

** WHAT THIS PINS, AND WHY EACH TEST EXISTS. **

`banked_parents: <host>` marks a frontier row whose parents were LOCATED on another
tree and deliberately NOT wired (an FS couple is a tree assertion, not a source).
The row then counts as DECLARED, so `extension_frontier` reads it closed and EXPAND
never offers it again — which is how 11 rows of located, cheap-to-finish work
accumulated with nothing drawing them. The key makes them a drawable IMPROVE
sub-population.

The tests below are the failure modes that were actually possible here:

  1. ROUND-TRIP through `set_meta_key` — the writer this vault requires (deferred 25:
     splicing text can write a key twice, and last-wins silently discards a value).
  2. ** SURVIVES `build_edges.upsert_edges` ** — the one data-loss path that killed
     the obvious `P-XXXXXX?!` design for `adjudicated`. `edge_value` REGENERATES
     every edge token, so anything encoded IN a token is destroyed; a sibling key
     must survive, and this proves it rather than assuming it.
  3. NEGATIVE CONTROLS on the reader — an absent key, an unknown host, the legacy
     `;` meta form, and a non-meta line must all read None. A loose reader here
     would silently enrol rows nobody banked.
  4. ** A WIRED ROW IS NOT OFFERED ** — the exit test is the `parents` edge, not the
     key. Without this the lane would re-offer work that is finished.
  5. `BANKED_STALE` fires exactly when the key outlives the wiring.

Run: python3 scripts/test_banked_parents.py
"""
import os, sys, tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import person_store as ps
import build_edges as be

FAILED = []


def check(name, got, want):
    if got != want:
        FAILED.append(f"{name}: got {got!r}, want {want!r}")
        print(f"  FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"  ok   {name}")


META = ("- meta: {id: P-0XAMP1, evidence_tier: strong_signal, profile_status: partial, "
        "life_status: deceased, generation: 13, fs: ABCD-123}")

print("1. round-trip through set_meta_key")
line = ps.set_meta_key(META, "banked_parents", "fs")
check("key is written", ps.banked_parents_host(line), "fs")
check("id still readable", "P-0XAMP1" in line, True)
# Idempotent + no duplicate: writing again REPLACES, it does not append.
line2 = ps.set_meta_key(line, "banked_parents", "fs")
check("re-write does not duplicate", line2.count("banked_parents"), 1)
check("re-write is stable", ps.banked_parents_host(line2), "fs")
# A changed host replaces in place rather than accumulating.
line3 = ps.set_meta_key(line2, "banked_parents", "wt")
check("host can be changed", ps.banked_parents_host(line3), "wt")
check("change did not duplicate", line3.count("banked_parents"), 1)

print("\n2. SURVIVES build_edges.upsert_edges (the adjudicated data-loss path)")
spliced = be.upsert_edges(line, ["P-AAAAAA"], ["P-BBBBBB"])
check("banked_parents survives an edge splice", ps.banked_parents_host(spliced), "fs")
check("parents were actually written", "P-AAAAAA" in spliced, True)
check("spouse was actually written", "P-BBBBBB" in spliced, True)
# And a SECOND splice (the idempotent re-run) must not eat it either.
spliced2 = be.upsert_edges(spliced, ["P-AAAAAA"], ["P-BBBBBB"])
check("survives a second splice", ps.banked_parents_host(spliced2), "fs")

print("\n3. NEGATIVE CONTROLS — the reader must not over-match")
check("absent key -> None", ps.banked_parents_host(META), None)
check("unknown host -> None",
      ps.banked_parents_host(ps.set_meta_key(META, "banked_parents", "geni")), None)
check("empty value -> None",
      ps.banked_parents_host(ps.set_meta_key(META, "banked_parents", "")), None)
check("legacy `;` meta form -> None",
      ps.banked_parents_host("- meta: id: P-0XAMP1; generation: 4; banked_parents: fs"), None)
check("non-meta line -> None",
      ps.banked_parents_host("- **Prior work** banked_parents: fs"), None)
check("prose mentioning the phrase -> None",
      ps.banked_parents_host("- parents are NAMED ON FAMILYSEARCH and not wired"), None)
check("None input -> None", ps.banked_parents_host(None), None)
# A near-miss key name must not match (substring hazard).
check("banked_parents_note is not banked_parents",
      ps.banked_parents_host(ps.set_meta_key(META, "banked_parents_note", "fs")), None)

print("\n4. lane_banked: a WIRED row is not offered")
import session_plan as sp


class _Rec:
    def __init__(self, rid, parents, meta, gen=5, name="X"):
        self.id, self.parents, self.raw = rid, parents, {"line": meta}
        self.generation, self.name, self.source_file = gen, name, "F.md"


banked_meta = ps.set_meta_key(META, "banked_parents", "fs")
fake = [
    _Rec("P-0XAMP1", [], banked_meta, name="Unwired"),          # offered
    _Rec("P-0XAMP2", ["P-AAAAAA?"], banked_meta, name="Wired"),  # NOT offered
    _Rec("P-0XAMP3", [], META, name="NotBanked"),                # NOT offered
]
_orig = ps.iter_people
try:
    ps.iter_people = lambda vault: iter(fake)
    rows = sp.lane_banked("/nonexistent")
finally:
    ps.iter_people = _orig
check("only the unwired banked row is offered", [r["id"] for r in rows], ["P-0XAMP1"])
check("row carries the banked defect tag", rows[0]["_defect"], "banked")
check("banked ranks below `edge`",
      sp._DEFECT_RANK["banked"] > sp._DEFECT_RANK["edge"], True)
check("banked ranks above `audit`",
      sp._DEFECT_RANK["banked"] < sp._DEFECT_RANK["audit"], True)

print("\n5. BANKED_STALE fires only when the key outlives the wiring")
# validate_edges reads narrative rows, so exercise the RULE directly against the
# same two predicates it uses, keeping this test independent of a live vault.
stale = lambda meta_line, parents: bool(
    ps.banked_parents_host(meta_line)) and bool(be.edge_tokens(parents))
check("banked + unwired -> not stale", stale(banked_meta, None), False)
check("banked + wired -> STALE", stale(banked_meta, "'[P-AAAAAA?]'"), True)
check("not banked + wired -> not stale", stale(META, "'[P-AAAAAA?]'"), False)

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print("all banked_parents tests pass")
