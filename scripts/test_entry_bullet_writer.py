#!/usr/bin/env python3
"""Pins `person_store.add_entry_bullet` and the PersonRecord accessor traps.

Both exist because of session #175 (20 AUG 2026):

  * a reader wrote `getattr(rec, "fs", None)`, got None for FIFTEEN consecutive
    rows, and only noticed because the session plan — reading the same vault
    through the seam — reported all fifteen as walkable. A wrong answer shaped
    like data, with no error anywhere.
  * a note-insertion loop enumerated a snapshot of a file's lines while inserting
    into the live list, so every insertion after the first in a file landed at a
    stale index. SIX OF FOURTEEN bullets went onto neighbouring entries, and
    `entry_boundary_audit` read 0 throughout because the markdown was perfectly
    well formed — just attached to the wrong person.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import person_store as ps

ENTRY = """# Family_Tree_Test

### Generation 5: Test

**Alpha One** (b. 1800)
- meta: {id: P-AAA111, generation: 5, fs: AAAA-111}
- **Prior work** (1 prior session, newest first) -- READ BEFORE RESEARCHING: [[logs/x]]
- Alpha's first body bullet.

**Beta Two** (b. 1802)
- meta: {id: P-BBB222, generation: 5, fs: TBD}
- Beta's first body bullet.

**Gamma Three** (b. 1804)
- meta: {id: P-CCC333, generation: 5, fs: '~DDDD-999'}
- Gamma's first body bullet.
"""

def vault():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "Family_Tree_Test.md"), "w").write(ENTRY)
    open(os.path.join(d, ".autoresearch.json"), "w").write('{"person_model": "narrative"}')
    return d

def body(v):
    return open(os.path.join(v, "Family_Tree_Test.md")).read()

def owner_of(v, needle):
    """Which entry does a line belong to? Uses the SEAM's own scan, not a regex —
    an ad-hoc `^\\*\\*` matcher cannot see bullet-form entries."""
    for rec, _p, _h, block in ps.iter_entry_blocks(v):
        if needle in block:
            return rec.id
    return None

fails = []
def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)

print("accessor traps:")
r = ps.PersonRecord(id="P-AAA111", external_ids={"fs": "AAAA-111"})
try:
    got = getattr(r, "fs", None)
    check("getattr(rec,'fs',None) must NOT silently return a default", False, f"returned {got!r}")
except ps.WrongAccessor:
    check("getattr(rec,'fs',None) raises through the default", True)
check("unknown attributes still take the default", getattr(r, "nope", "dflt") == "dflt")
check("fs() reads the live id", ps.fs(r) == "AAAA-111")
check("fs() is None for TBD", ps.fs(ps.PersonRecord(external_ids={"fs": "TBD"})) is None)
check("fs() is None for a ~REJECTED pid",
      ps.fs(ps.PersonRecord(external_ids={"fs": "~DDDD-999"})) is None)

print("writer places by ID, not by offset:")
v = vault()
ps.add_entry_bullet(v, "P-BBB222", "- BETA NOTE.")
ps.add_entry_bullet(v, "P-AAA111", "- ALPHA NOTE.\n  - alpha sub.")
ps.add_entry_bullet(v, "P-CCC333", "- GAMMA NOTE.")
check("beta note landed on beta",   owner_of(v, "BETA NOTE")  == "P-BBB222", owner_of(v, "BETA NOTE"))
check("alpha note landed on alpha", owner_of(v, "ALPHA NOTE") == "P-AAA111", owner_of(v, "ALPHA NOTE"))
check("gamma note landed on gamma", owner_of(v, "GAMMA NOTE") == "P-CCC333", owner_of(v, "GAMMA NOTE"))
check("sub-bullet stayed with its parent", owner_of(v, "alpha sub") == "P-AAA111")

lines = body(v).splitlines()
ai = lines.index("- **Prior work** (1 prior session, newest first) -- READ BEFORE RESEARCHING: [[logs/x]]")
check("Prior work stays directly under meta (note goes BELOW it)",
      lines[ai - 1].startswith("- meta:") and lines[ai + 1] == "- ALPHA NOTE.")
bi = [i for i, l in enumerate(lines) if l.startswith("- meta:") and "P-BBB222" in l][0]
check("with no Prior work, the note sits directly under meta", lines[bi + 1] == "- BETA NOTE.")

print("writer refuses what it cannot place safely:")
def raises(fn, exc):
    try:
        fn(); return False
    except exc:
        return True
    except Exception:
        return False
check("unknown id raises", raises(lambda: ps.add_entry_bullet(v, "P-ZZZ999", "- x"), KeyError))
check("non-bullet text raises", raises(lambda: ps.add_entry_bullet(v, "P-AAA111", "**Phantom** (b. 1) text"), ValueError))
check("un-indented continuation raises",
      raises(lambda: ps.add_entry_bullet(v, "P-AAA111", "- ok\nnot indented"), ValueError))
check("duplicate bullet raises", raises(lambda: ps.add_entry_bullet(v, "P-AAA111", "- ALPHA NOTE."), ValueError))
check("duplicate allowed when asked",
      ps.add_entry_bullet(v, "P-AAA111", "- ALPHA NOTE.", allow_duplicate=True) is not None)

print()
if fails:
    print(f"FAILED {len(fails)}: {fails}")
    sys.exit(1)
print("all entry-bullet writer + accessor pins pass")
