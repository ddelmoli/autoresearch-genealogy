#!/usr/bin/env python3
"""sex_inference.infer: layer order (gedcom, pronoun, strong-name override, name,
spouse) on placeholder people."""
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sex_inference as si


@dataclass
class R:
    id: str
    name: str
    spouse: list = field(default_factory=list)


he = "**X** (b. 1800)\n- He farmed; his land passed to him by deed.\n- **Sources**: she her her her"
she = "**X** (b. 1800)\n- She was baptised; her father left her land.\n"
flat = "**X** (b. 1800)\n- Baptised 1800.\n"
people, bodies = {}, {}
for n in range(20):                                  # twenty Abels sexed M by pronoun
    people[f"P-A{n}"] = R(f"P-A{n}", f"Abel Example{n}"); bodies[f"P-A{n}"] = he
people["P-AW"] = R("P-AW", "Abel Wrong"); bodies["P-AW"] = she        # strong name overrules
people["P-AN"] = R("P-AN", "Abel Nopronoun"); bodies["P-AN"] = flat   # name layer
people["P-S1"] = R("P-S1", "Zed Unusual", ["P-G1?"]); bodies["P-S1"] = flat   # spouse layer
people["P-G1"] = R("P-G1", "Quill Seeded", ["P-S1"]); bodies["P-G1"] = flat
people["P-U"] = R("P-U", "Yolo Nobody"); bodies["P-U"] = flat

sex, src = si.infer(people, bodies, {"P-G1": "F"})
assert (sex["P-G1"], src["P-G1"]) == ("F", "gedcom")
assert (sex["P-A0"], src["P-A0"]) == ("M", "pronoun")      # text after Sources ignored
assert (sex["P-AW"], src["P-AW"]) == ("M", "name"), (sex["P-AW"], src["P-AW"])
assert (sex["P-AN"], src["P-AN"]) == ("M", "name")
assert (sex["P-S1"], src["P-S1"]) == ("M", "spouse")
assert "P-U" not in sex
assert si.given_name("Captain Thomas West [the elder]") == "thomas"
print("sex inference: layers and overrides ok")

# The vault field wins over the GEDCOM and every guess; a recorded U stops guessing.
sex, src = si.infer(people, bodies, {"P-G1": "F"}, {"P-G1": "M", "P-AN": "U"})
assert (sex["P-G1"], src["P-G1"]) == ("M", "field")
assert "P-AN" not in sex
assert sex["P-S1"] == "F"                                   # spouse now follows the field
print("sex inference: the recorded field wins ok")
