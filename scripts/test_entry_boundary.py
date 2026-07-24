#!/usr/bin/env python3
"""Regression tests for entry-boundary attribution (spec/entry-boundary).

Runnable with no test framework: `python3 scripts/test_entry_boundary.py`
(exit 0 = pass).

The defect these lock down: a bold `Words (parenthetical)` span written MID-SENTENCE
was accepted as a person-entry header, became a body boundary, and orphaned the
`Sources` bullet below it onto a phantom entry — silently zeroing a documented
person's source coverage.

The fix went further than a patch. Entry detection moved off name SHAPE and onto the
`- meta:` block, via the `person_store` seam, so the phantom class is now
unrepresentable rather than filtered: a bold span with no meta block under it is not
an entry, whatever it is called. These tests therefore assert the PROPERTY (the right
person is credited), not the old regexes, and one of them asserts the regexes are gone.

Every gate assertion is paired with a negative control that breaks the boundary logic
at runtime. A regression fixture that cannot be made to fail proves nothing.
"""
import json
import os
import shutil
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as HS
import entry_boundary_audit as EB
import person_store as PS

REPO_ROOT = os.path.dirname(SCRIPT_DIR)
FIXTURE_VAULT = os.path.join(REPO_ROOT, "fixtures", "minimal-vault")

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


def narrative_vault(text=None, prefix="entry-boundary-"):
    """A temp vault declared as the NARRATIVE person model, optionally seeded.

    The gate and the census both audit that model specifically (on the file model each
    person IS a file, so there are no entry boundaries to get wrong).
    """
    d = tempfile.mkdtemp(prefix=prefix)
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        json.dump({"person_model": "narrative"}, f)
    if text is not None:
        with open(os.path.join(d, "Family_Tree_Fixture.md"), "w", encoding="utf-8") as f:
            f.write(text)
    return d


class broken_break_rule:
    """Re-introduce a body-extent fault in the path the census actually uses.

    (Lowercase deliberately: an ALL-CAPS four-then-three hyphenated phrase has the
    same shape as a FamilySearch PID, and the repo's PII gate blocks on it. Correctly
    so — it cannot know the difference — which is why this reads as prose rather than
    as a loosened regex.)

    Note what can no longer be injected: the original un-anchored-header bug. Under
    meta-anchored detection a bold span is an entry only when a `- meta:` block
    follows it, so a mid-prose bold cannot become a boundary however anything is
    mangled. The defect class is gone by construction, which is why the negative
    control has to break something else — here, the rule that an entry ends at a
    `---` rule or `## ` heading.
    """

    def __enter__(self):
        self._saved = HS.truncate_at_break
        HS.truncate_at_break = lambda body: body
        return self

    def __exit__(self, *exc):
        HS.truncate_at_break = self._saved
        return False


def entries_of(text):
    """[(display_name, body)] as the census sees them, for a one-file vault."""
    d = narrative_vault(text)
    try:
        return [(n, b) for ents in HS.entry_blocks_by_file(d).values()
                for (n, _h, b) in ents]
    finally:
        shutil.rmtree(d)


def records_for(text, name_startswith):
    for n, body in entries_of(text):
        if n.startswith(name_startswith):
            return HS.count_records(body)
    return None


def owner_of_sources(text):
    """Display name of the entry whose body contains the `Sources` bullet."""
    for n, body in entries_of(text):
        if "- **Sources**" in body:
            return n
    return None


# The trap, minimised. An institution name with toponymic particles ("di"), bolded
# mid-sentence with a parenthetical — shape-identical to a personal name, which is why
# no name heuristic could ever reject it.
TRAP = """### Generation 5

**Marta Example** (b. 1868, Example Village; d. 1931, Harbor Town; FS PID XXXX-XXX)
- meta: {id: P-3XAMP2, generation: 5, fs: XXXX-XXX}
- Her birth atto sits in the **Archivio di Stato di Example (Stato Civile)** series.
- **Sources**
  - 1868 birth atto — fs:3:1:YYYY-YYY
  - 1900 census — fs:1:1:ZZZZ-ZZZ
  - 1931 death certificate — fs:1:1:WWWW-WWW
"""

# The second reproduction from the field report: writing the offending string inside
# BACKTICKS to document the bug re-triggered the bug.
TRAP_BACKTICKED = TRAP.replace(
    "**Archivio di Stato di Example (Stato Civile)**",
    "`**Archivio di Stato di Example (Stato Civile)**`")

# A person named in passing — the population no institution-word denylist would catch.
TRAP_PERSON_IN_PROSE = TRAP.replace(
    "Her birth atto sits in the **Archivio di Stato di Example (Stato Civile)** series.",
    "Her brother **Paolo Example (1871-1940)** appears as the declarant.")

# The "bold wraps the whole header" dialect, at line start.
DIALECT_B = """### Generation 6

**Anna Example (b. 1840, Example Village; FS PID AAAA-AAA)**
- meta: {id: P-4XAMP3, generation: 6, fs: AAAA-AAA}
- **Sources**
  - 1840 birth atto — fs:1:1:BBBB-BBB
"""

# Names the retired shape patterns could not express: embedded quotes, parentheses, a
# slash alias. 52 such entries were invisible to the census and inherited a neighbour's
# record count, which is why NO_NARRATIVE read 0 and looked vacuous.
AWKWARD_NAMES = """### Generation 4

**Matilda ("Tillie") Example** (b. BET 1911 AND 1913, New York; FS PID CCCC-CCC)
- meta: {id: P-5XAMP4, generation: 4, fs: CCCC-CCC}
- **Sources**
  - 1920 census — fs:1:1:DDDD-DDD

**Abraham Meyer / Meier Example** (b. 1878, Example Village; FS PID EEEE-EEE)
- meta: {id: P-6XAMP5, generation: 5, fs: EEEE-EEE}
- **Sources**
  - 1905 manifest — fs:1:1:FFFF-FFF
"""


def main():
    print("== the shape-based reader is gone, not merely bypassed ==")
    for sym in ("extract_entries", "ENTRY_HDR_A", "ENTRY_HDR_B", "_is_entry_header"):
        check(not hasattr(HS, sym), f"harvest_sources.{sym} no longer exists")

    print("== the mid-prose institution trap ==")
    check(owner_of_sources(TRAP) == "Marta Example",
          "the Sources bullet belongs to the person, not the bolded archive name")
    check(records_for(TRAP, "Marta Example") == 3,
          "all 3 records are credited to the person")
    check([n for n, _b in entries_of(TRAP)] == ["Marta Example"],
          "the bolded archive name is not an entry: no meta block, not a person")

    print("== the backticked reproduction (documenting the bug re-triggered it) ==")
    check(owner_of_sources(TRAP_BACKTICKED) == "Marta Example",
          "a backticked bold span is prose too, and does not split the entry")

    print("== a person named in passing (no denylist could catch this one) ==")
    check(owner_of_sources(TRAP_PERSON_IN_PROSE) == "Marta Example",
          "a relative named mid-sentence does not steal the Sources bullet")
    check(len(entries_of(TRAP_PERSON_IN_PROSE)) == 1,
          "and does not become an entry of his own")

    print("== the bold-wraps-everything dialect still works ==")
    ents = entries_of(DIALECT_B)
    check(len(ents) == 1 and ents[0][0].startswith("Anna Example"),
          "`**Name (vitals)**` at line start is one entry")
    check(records_for(DIALECT_B, "Anna Example") == 1, "its record is credited")

    print("== names the retired patterns could not express (the 52 class) ==")
    ents = entries_of(AWKWARD_NAMES)
    check(len(ents) == 2, "a name with quotes/parens and one with a slash alias are BOTH entries")
    check(records_for(AWKWARD_NAMES, 'Matilda ("Tillie")') == 1,
          "the quoted-nickname entry is credited its own record")
    check(records_for(AWKWARD_NAMES, "Abraham Meyer / Meier") == 1,
          "and so is the slash-alias entry (neither inherits the other's)")

    print("== an entry ends at a structural break ==")
    RULED = TRAP + "\n---\n\nSection prose after a break, citing fs:1:1:MMMM-MMM.\n"
    check(records_for(RULED, "Marta Example") == 3,
          "prose past a `---` rule cannot lend the last entry a fourth record")

    print("== the mirror hazard: a locator CLASS named in prose is not a record ==")
    for tok, want in [("fs:1:1:", False), ("fs:3:1:", False), ("fs:", False),
                      ("anc:dbid=", False), ("wt:", False),
                      ("fs:1:1:XXXX-XXX", True), ("fs:3:1:YYYY-YYY-ZZZ", True),
                      ("anc:dbid=1234", True), ("wt:Surname-48", True),
                      ("antenati:ark:/12657/an_ua1", True)]:
        check(HS.is_record_locator(tok) is want,
              f"is_record_locator({tok!r}) is {want}")
    PROSE_PREFIX = """**Rosa Example** (b. 1875, Example Village; FS PID GGGG-GGG)
- meta: {id: P-7XAMP6, generation: 5, fs: GGGG-GGG}
- Note: browse-only registers attach as fs:3:1: image ARKs, not fs:1:1: indexed records.
"""
    check(records_for(PROSE_PREFIX, "Rosa Example") == 0,
          "a methodology note naming the locator form invents no source")
    check(records_for(PROSE_PREFIX + "- **Sources**\n  - 1875 birth atto — fs:3:1:AAAA-BBB\n",
                      "Rosa Example") == 1,
          "and a real citation beside it still counts exactly once")

    print("== who a block may credit (cross-reference vs inline collateral) ==")
    XREF = """**Giulio Example** (b. 1746, Example Village; d. 1799; FS PID DDDD-DDD)
- meta: {id: P-8XAMP7, generation: 9, fs: DDDD-DDD}
- Siblings (2, with FS PIDs): **Marco Example (1744-1745, FS EEEE-EEE)** — died in infancy.
- **Sources**
  - 1746 birth atto — fs:1:1:FFFF-FFF
  - 1799 burial — fs:1:1:GGGG-GGG
"""
    body = entries_of(XREF)[0][1]
    check(HS.may_credit(body, "DDDD-DDD"), "the entry's own PID is creditable here")
    check(not HS.may_credit(body, "EEEE-EEE"),
          "a sibling named in a cross-reference list is NOT credited this entry's records")

    INLINE = """**James Example** (b. ABT 1600, Somewhereton; d. 1680; FS PID HHHH-HHH)
- meta: {id: P-9XAMP8, generation: 13, fs: HHHH-HHH}
- Wife: Alice Example (b. ABT 1613, Somewhereton; FS: IIII-III) — parentage unknown.
- **FS-attached sources for wife Alice Example** (IIII-III, inline collateral): 1:1:JJJJ-JJJ, 1:1:KKKK-KKK
- **Sources**
  - 1645 freeman record — fs:1:1:LLLL-LLL
"""
    body = entries_of(INLINE)[0][1]
    check(HS.may_credit(body, "IIII-III"),
          "a relative documented INLINE (her PID on a bullet carrying locators) is credited")
    check(HS.may_credit(body, "HHHH-HHH"), "and so is the entry's own person")

    print("== the gate itself (entry_boundary_audit) ==")
    tmp = narrative_vault(TRAP + "\n" + TRAP_PERSON_IN_PROSE + "\n" + DIALECT_B + "\n" + RULED)
    try:
        check(EB.audit(tmp) == [], "0 findings on a correctly-parsed vault")
        with broken_break_rule():
            mis = EB.audit(tmp)
        check(len(mis) > 0, "NEGATIVE CONTROL: it FIRES when the boundary logic regresses")
    finally:
        shutil.rmtree(tmp)

    # The SOURCE_MISATTRIBUTION subset: a displaced run that carries a `Sources`
    # bullet is the one that moves the census today, and is flagged as such.
    SOURCES_PAST_BREAK = """**Ada Example** (b. 1850, Somewhereton; FS PID PPPP-PPP)
- meta: {id: P-BXAMPA, generation: 6, fs: PPPP-PPP}
- A note about her.

## Unattributed section

- **Sources**
  - 1850 birth — fs:1:1:QQQQ-QQQ
"""
    tmp3 = narrative_vault(SOURCES_PAST_BREAK, prefix="entry-boundary-subset-")
    try:
        check(EB.audit(tmp3) == [], "a Sources bullet past a `## ` heading belongs to nobody")
        with broken_break_rule():
            mis = EB.audit(tmp3)
        check(any(r["sources"] for r in mis),
              "and when the boundary logic lets an entry claim it, the run is flagged "
              "as carrying a Sources bullet (census impact)")
    finally:
        shutil.rmtree(tmp3)

    print("== the blind spot the whole-file invariant closes ==")
    # A boundary fault in an entry with NO `Sources` bullet. The gate's first version
    # checked only Sources bullets and inherited the original defect's conditionality.
    NO_SOURCES = """**Elio Example** (b. 1830, Example Village; FS PID NNNN-NNN)
- meta: {id: P-AXAMP9, generation: 7, fs: NNNN-NNN}
- Registers for the parish sit in the **Archivio di Stato di Example (Stato Civile)** series.
- No civil record of his death has been located.

---

Section prose that belongs to no entry at all.
"""
    tmp2 = narrative_vault(NO_SOURCES, prefix="entry-boundary-blind-")
    try:
        check(EB.audit(tmp2) == [], "clean under the shipped parser")
        with broken_break_rule():
            mis = EB.audit(tmp2)
        check(len(mis) > 0,
              "a boundary fault IS caught with no Sources bullet anywhere in the entry")
        check(not any(r["sources"] for r in mis),
              "and is reported as a non-Sources run — invisible to the narrow check")
    finally:
        shutil.rmtree(tmp2)

    print("== the anonymised repo fixture (fixtures/minimal-vault) ==")
    with open(os.path.join(FIXTURE_VAULT, "Family_Tree.md"), encoding="utf-8") as f:
        fixture_text = f.read()
    check(owner_of_sources(fixture_text) == "Marta Example",
          "the shipped fixture entry keeps its Sources bullet")
    check(records_for(fixture_text, "Marta Example") == 3,
          "the shipped fixture entry is credited with 3 records")
    check(EB.audit(FIXTURE_VAULT) == [],
          "the gate no-ops on a FILE-model vault (no entry boundaries to get wrong)")
    fv = narrative_vault(prefix="entry-boundary-fixture-")
    try:
        shutil.copy(os.path.join(FIXTURE_VAULT, "Family_Tree.md"), fv)
        check(EB.audit(fv) == [], "and the same fixture passes it as a narrative vault")
        check([r.name for r, *_ in PS.iter_entry_blocks(fv)] == ["Marta Example"],
              "the seam finds exactly the one entry that carries a meta block")
    finally:
        shutil.rmtree(fv)

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
