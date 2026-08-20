#!/usr/bin/env python3
"""Pins ENTRY_ATTRIBUTION: catches text on the wrong person, ignores kin talk.

Both halves matter equally. A gate that misses the misfiling is useless; a gate
that reports every cousin mentioned in an entry gets switched off, and then it is
also useless. The first cut of this one reported 292 on a real vault because it
did not know about siblings.

The shape being pinned is the real incident (session #175, 20 AUG 2026): a bullet
about one man's parents landed on an unrelated woman's entry, naming the two
parents' FS PIDs. Well-formed markdown, real header, wrong person —
`entry_boundary_audit` read 0 for it, correctly, because that is not its question.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entry_attribution_audit as eaa

VAULT = """# Family_Tree_Test

### Generation 5: Test

**Parent One** (b. 1800)
- meta: {id: P-PAR001, generation: 5, fs: PPPP-111}

**Parent Two** (b. 1802)
- meta: {id: P-PAR002, generation: 5, fs: QQQQ-222, spouse: '[P-PAR001]'}

**Child A** (b. 1830)
- meta: {id: P-KID00A, generation: 4, fs: KKKK-333, parents: '[P-PAR001, P-PAR002]'}
- Legit: names a PARENT's pid PPPP-111 in ordinary prose.

**Child B** (b. 1832)
- meta: {id: P-KID00B, generation: 4, fs: LLLL-444, parents: '[P-PAR001, P-PAR002]'}
- Legit: names a SIBLING's pid KKKK-333, the commonest cross-reference there is.

**Stranger** (b. 1900)
- meta: {id: P-STR999, generation: 3, fs: SSSS-999}
- MISFILED: a bullet about Child A's parents, naming PPPP-111 and QQQQ-222.
- Legit: names its own pid SSSS-999.
"""

def build():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "Family_Tree_Test.md"), "w").write(VAULT)
    open(os.path.join(d, ".autoresearch.json"), "w").write('{"person_model": "narrative"}')
    return d

fails = []
def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)

v = build()
found = eaa.scan(v)
owners = [f["owner"] for f in found]
texts = " | ".join(f["text"] for f in found)

print("catches the incident shape:")
check("the misfiled bullet is reported", any("MISFILED" in f["text"] for f in found), texts)
check("it is reported against the entry it LANDED in", "P-STR999" in owners, str(owners))

print("stays quiet on ordinary kin cross-references:")
check("a parent's pid on a child's entry is not reported",
      not any(f["owner"] == "P-KID00A" for f in found), str(owners))
check("a SIBLING's pid is not reported",
      not any(f["owner"] == "P-KID00B" for f in found), str(owners))
check("an entry naming its OWN pid is not reported",
      not any("its own pid" in f["text"] for f in found), texts)
check("exactly one finding overall", len(found) == 1, f"{len(found)}: {texts}")

print("known blind spot, pinned so it is not mistaken for coverage:")
BLIND = VAULT + """
**Spouse Of Stranger** (b. 1902)
- meta: {id: P-SPO111, generation: 3, fs: TTTT-777, spouse: '[P-STR999]'}
- MISFILED-BLIND: a bullet about the spouse, citing only SSSS-999, the owner's own pid.
"""
d2 = tempfile.mkdtemp()
open(os.path.join(d2, "Family_Tree_Test.md"), "w").write(BLIND)
open(os.path.join(d2, ".autoresearch.json"), "w").write('{"person_model": "narrative"}')
blind = eaa.scan(d2)
check("a bullet naming ONLY the owner's own identifier is NOT caught "
      "(the incident's hardest case: a note landed on the SPOUSE and cited the spouse's "
      "own pid, so there was no foreign identifier to catch)",
      not any("MISFILED-BLIND" in f["text"] for f in blind))

print("the SILENT-ZERO regression, pinned hardest of all:")
# --changed-only judges a temp dir holding only the staged files. If the identifier
# index is built from THAT, no foreign PID resolves to anybody and the gate reports 0
# forever -- passing because it cannot see. It shipped with exactly this bug and a
# 37-file validation commit hid it; a one-file commit exposed it immediately.
import shutil
staged = tempfile.mkdtemp()          # pretend only the Stranger's file was staged
open(os.path.join(staged, "Family_Tree_Test.md"), "w").write(
    "\n".join(VAULT.split("**Parent One**")[0].splitlines()) + """
**Stranger** (b. 1900)
- meta: {id: P-STR999, generation: 3, fs: SSSS-999}
- MISFILED: a bullet about Child A's parents, naming PPPP-111 and QQQQ-222.
""")
open(os.path.join(staged, ".autoresearch.json"), "w").write('{"person_model": "narrative"}')
only = {"Family_Tree_Test.md": set(range(1, 40))}

blind_index = eaa.scan(staged, only=only)                       # index from the staged dir
with_index  = eaa.scan(staged, only=only, index_vault=v)        # index from the real vault
check("index built from the staged subset sees NOTHING (the bug)", len(blind_index) == 0,
      f"{len(blind_index)}")
check("index_vault=<real vault> catches the misfile in a ONE-FILE commit",
      any("MISFILED" in f["text"] for f in with_index), str(with_index))

print()
if fails:
    print(f"FAILED {len(fails)}: {fails}")
    sys.exit(1)
print("all entry-attribution pins pass")
