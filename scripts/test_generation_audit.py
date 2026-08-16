#!/usr/bin/env python3
"""Pins generation_audit.py.

** THE BEHAVIOUR WORTH PINNING IS THE ONE THAT NEARLY WENT WRONG. ** The naive
shortest-path walk flags the entire ancestry ABOVE every declared pedigree
collapse. Measured on the real vault: naive 26 rows, all correct; collapse-aware
0. Acting on the naive result would have renumbered 19 correct ancestors and
silently undone 5 declarations.

So this file pins BOTH directions: the collapse-aware walk must stay silent above
a declaration, and the naive walk must still flag it — because the day the naive
walk goes quiet is the day the pin stops proving anything.

Run: python3 scripts/test_generation_audit.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generation_audit as G  # noqa: E402

FAILED = []


def check(desc, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    if not ok:
        print(f"       got {got!r}, want {want!r}")
        FAILED.append(desc)


def mk(spec):
    """spec: {id: (gen, [parent ids])} -> (people, parents)."""
    people = {p: {"id": p, "name": p, "gen": g, "file": "T.md"} for p, (g, _) in spec.items()}
    parents = {p: list(ps) for p, (_, ps) in spec.items()}
    return people, parents


def drift(people, parents, anchors, declared, aware=True):
    d = G.compute(people, parents, anchors, declared, collapse_aware=aware)
    return sorted(p for p in d if people[p]["gen"] is not None and people[p]["gen"] != d[p])


print("A clean chain computes its generations and reports no drift:")
people, parents = mk({"A": (1, ["B"]), "B": (2, ["C"]), "C": (3, [])})
check("no drift on a correct chain", drift(people, parents, ["A"], set()), [])

print("\nA STALE label is caught (the 03 AUG detach residue, in miniature):")
people, parents = mk({"A": (1, ["B"]), "B": (2, ["C"]), "C": (9, [])})
check("the wrong label is reported", drift(people, parents, ["A"], set()), ["C"])

print("\n⛔ THE TRAP: ancestry ABOVE a declared collapse.")
# G is reached down two paths of different length: A->B->G (3) and A->C->D->G (4).
# The vault deliberately keeps the LONGER label, declared on the (D,G) edge.
# H is G's own parent and must follow G's declared label, not the short path.
spec = {"A": (1, ["B", "C"]), "B": (2, ["G"]), "C": (2, ["D"]),
        "D": (3, ["G"]), "G": (4, ["H"]), "H": (5, [])}
people, parents = mk(spec)
check("collapse-aware: silent on G and its ancestor H",
      drift(people, parents, ["A"], {"G"}), [])
check("⛔ naive: WOULD wrongly flag both — this is the failure being prevented",
      drift(people, parents, ["A"], {"G"}, aware=False), ["G", "H"])

print("\nA genuine error ABOVE a collapse is still caught (the pin must not go blind):")
spec2 = dict(spec); spec2["H"] = (99, [])
people, parents = mk(spec2)
check("H's bad label is reported even though G is pinned",
      drift(people, parents, ["A"], {"G"}), ["H"])

print("\nUNREACHABLE people are never reported as drift:")
people, parents = mk({"A": (1, []), "Z": (7, [])})
check("a disconnected row is not drift", drift(people, parents, ["A"], set()), [])

print("\n⚠ BOTH entry forms are read — a line-start bold AND the bullet form.")
print("   A line-start-only reader attaches the PREVIOUS entry's name to every")
print("   bullet-form entry, which really happened during this session.")
with tempfile.TemporaryDirectory() as d:
    with open(os.path.join(d, "Family_Tree_T.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "**Alpha Person** (b. 1800)\n"
            "- meta: {id: P-AAAAAA, generation: 1}\n"
            "- **Beta Person** (b. 1770; bullet-form entry)\n"
            "- meta: {id: P-BBBBBB, generation: 2, parents: '[P-CCCCCC?]'}\n"
            "**Gamma Person** (b. 1740)\n"
            "- meta: {id: P-CCCCCC, generation: 3}\n")
    ppl, par, anch, decl = G.load(d)
    check("bullet-form entry keeps its OWN name", ppl["P-BBBBBB"]["name"], "Beta Person")
    check("line-start entry unaffected", ppl["P-CCCCCC"]["name"], "Gamma Person")
    check("its parents edge is still parsed", par["P-BBBBBB"], ["P-CCCCCC"])

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    sys.exit(1)
print("all generation-audit checks passed")
