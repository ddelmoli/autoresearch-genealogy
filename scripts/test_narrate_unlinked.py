#!/usr/bin/env python3
"""narrate.descended_to: a person with no path to an anchor is named by the
descendant nearest the anchors (lowest generation), on a fixture tree with
placeholder ids. Pins the fallback behind the person card's "no recorded link" line."""
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
    generation: int = None


# A (anchor) has no tie to the cluster below.
# OLD -> MID -> NEAR (gen 3, the collateral the cluster was added for)
# OLD -> SIDE (gen 6, a further branch): NEAR wins on generation, not on steps.
# LONE has no descendant at all.
tree = [R("P-A00000", "Anchor", generation=1),
        R("P-OLD000", "Old Ancestor [father of Mid]", generation=7),
        R("P-MID000", "Mid", ["P-OLD000?"], generation=6),
        R("P-NEAR00", "Near Cousin", ["P-MID000"], generation=3),
        R("P-SIDE00", "Side Branch", ["P-OLD000"], generation=6),
        R("P-LONE00", "Lone")]
people = {r.id: r for r in tree}

assert narrate.relations("P-OLD000", people, ["P-A00000"]) == []
u = narrate.descended_to("P-OLD000", people)
assert (u["id"], u["name"], u["steps"], u["gen"]) == ("P-NEAR00", "Near Cousin", 2, 3), u
assert narrate.descended_to("P-LONE00", people) is None
assert narrate.descended_to("P-NEAR00", people) is None        # a leaf has no descendant
print("narrate unlinked fallback: descendant nearest the anchors ok")
