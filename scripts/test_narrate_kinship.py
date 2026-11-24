#!/usr/bin/env python3
"""narrate.relations: ancestors, collaterals (sibling, aunt/uncle, cousin removed) and
the spouse fallback, on a fixture tree with placeholder ids."""
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import narrate


@dataclass
class R:
    id: str
    name: str
    parents: list = field(default_factory=list)
    spouse: list = field(default_factory=list)


# GG -> G -> P -> A (anchor);  GG -> GU (great-uncle) -> C1 (1st cousin once removed of P)
# G -> AU (aunt/uncle of A) -> CO (1st cousin of A);  P -> SIB (sibling of A)
# W is CO's spouse, no blood path.  X stands alone.
tree = [R("P-GG0000", "Great Grand"), R("P-G00000", "Grand", ["P-GG0000?"]),
        R("P-P00000", "Parent", ["P-G00000"]), R("P-A00000", "Anchor", ["P-P00000"]),
        R("P-GU0000", "Great Uncle", ["P-GG0000"]), R("P-C10000", "Cousin One", ["P-GU0000"]),
        R("P-AU0000", "Aunt Uncle", ["P-G00000"]), R("P-C00000", "Cousin", ["P-AU0000"], ["P-W00000"]),
        R("P-SIB000", "Sibling", ["P-P00000"]), R("P-W00000", "Spouse In Law", [], ["P-C00000"]),
        R("P-X00000", "Unwired")]
people = {r.id: r for r in tree}
anchors = ["P-A00000"]


def rel(pid, watcher="P-A00000"):
    return next((k for k in narrate.relations(pid, people, anchors) if k["id"] == watcher), None)


k = rel("P-GG0000"); assert k["kind"] == "ancestor" and k["steps"] == 3, k
k = rel("P-SIB000"); assert (k["kind"], k["up"], k["down"]) == ("collateral", 1, 1), k
k = rel("P-AU0000"); assert (k["up"], k["down"]) == (1, 2), k
k = rel("P-GU0000"); assert (k["up"], k["down"]) == (1, 3), k
k = rel("P-C00000"); assert (k["up"], k["down"], k["common"]) == (2, 2, ["Grand"]), k
k = rel("P-C10000"); assert (k["up"], k["down"]) == (2, 3), k      # 1st cousin once removed
k = rel("P-C10000", "P-P00000"); assert (k["role"], k["up"], k["down"]) == ("anchor parent", 2, 2), k
k = rel("P-W00000"); assert k["kind"] == "spouse" and k["spouse"] == "Cousin" and k["rel"]["up"] == 2, k
assert narrate.relations("P-X00000", people, anchors) == []
print("narrate kinship: ancestors, collaterals and spouses ok")
