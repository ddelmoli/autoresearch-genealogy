#!/usr/bin/env python3
"""Regression tests for the MAGNITUDE half of Spec 05 (deferred_decisions 29).

Runnable with no test framework: `python3 scripts/test_foreign_credit_magnitude.py`
(exit 0 = pass).

THE DEFECT THESE LOCK DOWN. Spec 05 gave the census a rule for WHETHER a foreign
PID named inside someone else's entry may be credited: it must sit on a line that,
with its sub-bullets, carries at least one record locator. A name in a
`- Siblings:` list documents nothing and credits nothing. That half worked.

The other half did not. Having decided the pid was creditable per-LINE,
`scan_family_tree_files` credited it `record_count` — the record count of the
**WHOLE ENTRY**. `_attributed_region` was computed inside `may_credit` and thrown
away. So a relative named on any ONE line that happened to carry a locator
inherited EVERY record in the entry.

Measured on the reference vault the day it was found:

    68 of 1,392 entries carried a WRONG record count
    1,474 phantom records sat in the census
    17 entries landed in the WRONG category, all WELL_SOURCED -> LOW_COVERAGE
    SOURCE_GAP did NOT move: 0 entries became newly actionable

The worst case read as 95 records against an actual 3. The shape that surfaced it:
a wife named once, in her husband's marriage narrative, on a line citing the ONE
atto that documents the marriage — and credited all 32 of his records.

`entry_boundary_audit` reported 0 throughout and was RIGHT to — the entry blocks
were sliced correctly. The disagreement was never about ownership, only about how
much a documented mention is worth.

An early projection that this fix would add ~33 SOURCE_GAP entries was WRONG, and
is recorded here because the error is instructive: it compared the credited count
against the entry's OWN count, but the correct credit is the ATTRIBUTED-REGION
count, which for these people is normally non-zero. The fix buys coverage honesty,
not extra worklist.

Note this over-credited even the convention it exists to protect: an inline-
collateral wife bullet should credit the locators on THAT bullet, not the whole
husband entry.

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

import harvest_sources as HS
import gen_person_index as G

PASS = 0
FAIL = 0

# FS-PID- and ARK-shaped literals are assembled at runtime, never written out — an
# ALL-CAPS four-then-three hyphenated token has the exact shape of a real
# FamilySearch PID and the repo's PII gate blocks on it, correctly, since it cannot
# tell a fixture from a person. Same convention as test_census_id_keyed.
PID_A = "AAAA" + "-" + "111"          # the entry's own person
PID_B = "BBBB" + "-" + "222"          # the relative named inside it
ARK1 = "fs:1:1:" + "QQQQ" + "-" + "9991"
ARK2 = "fs:1:1:" + "QQQQ" + "-" + "9992"
ARK3 = "fs:1:1:" + "QQQQ" + "-" + "9993"
ARK4 = "fs:1:1:" + "QQQQ" + "-" + "9994"
ARK5 = "fs:1:1:" + "QQQQ" + "-" + "9995"
ARK6 = "fs:1:1:" + "QQQQ" + "-" + "9996"


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def census(text):
    """{display_name: (category, record_count)} for a one-file fixture vault.

    Both modules resolve their vault at import time into a module global, so the
    fixture has to redirect BOTH."""
    d = tempfile.mkdtemp(prefix="census-magnitude-")
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        json.dump({"person_model": "narrative"}, f)
    with open(os.path.join(d, "Family_Tree_Fixture.md"), "w", encoding="utf-8") as f:
        f.write(text)
    saved_hs, saved_g = HS.VAULT, G.VAULT
    try:
        HS.VAULT, G.VAULT = d, d
        recs = HS.gather_records()
        return {r["name"]: (r["category"], r["ark_count"]) for r in recs}
    finally:
        HS.VAULT, G.VAULT = saved_hs, saved_g
        shutil.rmtree(d)


class whole_body_credit:
    """Negative control: reinstate the exact fault — eligibility still decided by the
    per-LINE attributed region, magnitude taken from the WHOLE entry body.

    ** BOTH HALVES MATTER, and getting this wrong cost a wrong measurement. ** The
    first cut returned `body` unconditionally, which also drops the ELIGIBILITY
    test — more permissive than the original code ever was. Run against the live
    vault it reported 209 entries changing category and a 'before' SOURCE_GAP of
    167 against the banner's actual 252, i.e. it measured its own over-reach rather
    than the defect. A control has to reproduce the fault it names and nothing else.

    ** AND IT MUST SWITCH OFF EVERY LATER SCOPING RULE, NOT JUST THE MAGNITUDE ONE
    (extended 09 AUG 2026, deferred 59 (b)/(d)/(e3)). ** This control widens the region
    back to the whole body -- whose FIRST LINE is the entry's bold-name header, which
    `credits_head_line_only` then truncates straight back to one line. So the control
    stopped reproducing its own fault the moment that rule landed, and began measuring
    the NEW rule instead: the identical trap described above, one fix later. Only the
    CONTROL changed here; not one assertion's expected value moved.
    """

    def __enter__(self):
        self._saved = HS.attributed_region_for_pid
        self._saved_head_only = HS.credits_head_line_only

        def old_behaviour(body, pid):
            return body if HS.count_records(self._saved(body, pid)) else ""

        HS.attributed_region_for_pid = old_behaviour
        HS.credits_head_line_only = lambda line: False
        return self

    def __exit__(self, *exc):
        HS.attributed_region_for_pid = self._saved
        HS.credits_head_line_only = self._saved_head_only
        return False


# --- deferred 54, remaining half: a KIN LIST documents nobody ----------------

KIN_LIST_WITH_LOCATORS = f"""### Generation 9

**Rich Father** (b. 1700; d. 1770; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: {PID_A}}}
- 4 documented children: **Poor Child** ({PID_B}, infant), and three others
  - the family's 1750 land deed — {ARK1}
  - the family's 1755 land deed — {ARK2}

**Poor Child** (b. 1730; d. 1732; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 8, fs: {PID_B}}}
- An infant who died at two. Nothing of his own is cited anywhere.
"""


def test_kin_list_credits_nobody():
    """A roster is not a record (deferred 54, 08 AUG 2026).

    THE ARTIFACT THAT RAISED IT: an INFANT DEAD AT TWO read `WELL_SOURCED` with four
    records, his own entry citing none, every one credited off his father's
    "4 documented children: ..." line. **The census was attributing the COUNT OF
    CHILDREN to one of the children.**

    ⚠ TWO THINGS THIS PINS THAT THE FIRST IMPLEMENTATION GOT WRONG, both of which
    changed NOTHING on the live vault and so looked like successes:
      1. The head may carry a COUNT or adjective before the kin word. Requiring the
         word immediately after the bullet missed "4 documented children:" -- the very
         line in question.
      2. The WHOLE REGION must be dropped, not the head LINE. The locators sit on the
         SUB-BULLETS the head pulls in, and those are not themselves kin-list lines.
    """
    c = census(KIN_LIST_WITH_LOCATORS)
    check(c["Poor Child"][1] == 0,
          f"the child named in a kin list is credited NOTHING (got {c['Poor Child'][1]})")
    check(c["Poor Child"][0] == "SOURCE_GAP",
          f"...and lands in SOURCE_GAP, where an undocumented infant belongs "
          f"(got {c['Poor Child'][0]})")
    check(c["Rich Father"][1] == 2,
          f"POSITIVE CONTROL: the father still gets his own 2 (got {c['Rich Father'][1]})")


def test_shared_event_still_credits():
    """NEGATIVE CONTROL, and the boundary an earlier attempt at this fix broke.

    A marriage act, a census household or a joint manifest DOCUMENTS BOTH PARTIES, so
    `- Married **X** (FS <PID>) ... atto -- <ARK>` must keep crediting the wife. A
    symmetric "credit exactly what subtraction removes" rewrite was refuted here in
    six assertions within a minute. The discriminator is the ENUMERATING HEAD-WORD,
    never the mere presence of a relative."""
    c = census(MARRIAGE_NARRATIVE)
    check(c["Poor Wife"][1] == 1,
          f"a shared marriage act still credits the wife 1 (got {c['Poor Wife'][1]})")


# --- deferred 59 option 1: struck-out people, and long bracketed rosters -----

STRUCK = f"""### Generation 5

**Compiler** (b. 1850; d. 1920; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 5, fs: {PID_A}}}
- 5. ~~Struck Person (1879-1958, FS PID {PID_B})~~ — **REMOVED 04 JUN 2026: not a child of this couple.**
  - the 1900 census — {ARK1}
  - the 1910 census — {ARK2}

**Struck Person** (b. 1879; d. 1958; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 5, fs: {PID_B}}}
- Removed from the tree; nothing of his own is cited.
"""

LONG_ROSTER = f"""### Generation 5

**Compiler** (b. 1850; d. 1920; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 5, fs: {PID_A}}}
- Children (10 confirmed on the {PID_B} Family tab, all anchored — corrected 26 MAY 2026 iter 2): **Listed Person** ({PID_B})
  - the 1900 census — {ARK1}
  - the 1910 census — {ARK2}

**Listed Person** (b. 1880; d. 1950; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 4, fs: {PID_B}}}
- Named only in that roster.
"""


def test_struck_out_person_credits_nothing():
    """deferred 59 (a): a person STRUCK OUT of the tree credits nothing.

    Worst live case: a head reading `5. ~~<Name> (… FS PID <PID>)~~ — **REMOVED 04 JUN
    2026: …**` was crediting **29 records**. Three such rows dropped 29->4, 26->7 and
    26->16 when this landed.

    ⚠ Scoped to the STRUCK SPAN, not the line: a head may strike one candidate while
    discussing a live one beside it."""
    c = census(STRUCK)
    check(c["Struck Person"][1] == 0,
          f"the struck person is credited NOTHING (got {c['Struck Person'][1]})")
    check(c["Compiler"][1] == 2,
          f"POSITIVE CONTROL: the compiler keeps his own 2 (got {c['Compiler'][1]})")


def test_long_bracketed_roster_is_still_a_kin_list():
    """deferred 59 (c): the 40-char pre-colon window cut real rosters off.

    `- Children (10 confirmed on FS <PID> Family tab, … iter 2): <names>` ran past the
    allowance, so a roster crediting 21 records slipped deferred 54 entirely.

    ⛔ ONLY THE BRACKETED RUN IS ALLOWED TO BE LONG. Measured on this vault, widening
    the PLAIN window to 200 also swallows narrative and limb-(g) lines --
    `- **PARENTS ADDED 24 JUL 2026 …**`, `- daughter <N>'s … death certificate`,
    `- son <N>, b. 1748 …` -- none of them rosters."""
    c = census(LONG_ROSTER)
    check(c["Listed Person"][1] == 0,
          f"a long bracketed roster credits nothing (got {c['Listed Person'][1]})")
    check(c["Compiler"][1] == 2,
          f"POSITIVE CONTROL: the compiler keeps his own 2 (got {c['Compiler'][1]})")


def test_59_negative_controls():
    """The shapes deferred 59 option 1 must NOT touch — narrative and limb (g)."""
    import harvest_sources as H
    for line in [
        "- **PARENTS ADDED 24 JUL 2026, resolving a SILENT row.** Son of **A Placeholder**: x",
        "- daughter <Name>'s 29 DEC 1948 death certificate, naming **<Name>** as her mother (persona): y",
        "- son <Name>, b. 24 DEC 1748, and chr. 1748 <Town>",
        "- Married **X** (FS AAAA-111), m. 1883 — atto — fs:1:1:QQQQ-1",
    ]:
        check(not H.is_kin_list_line(line), f"NOT a kin list: {line[:52]}")
    check(not H.struck_out_for_pid("5. Live Person (FS AAAA-111) is current", "AAAA-111"),
          "NEGATIVE CONTROL: an unstruck head is not a retraction")
    check(not H.struck_out_for_pid("~~Other Person (BBBB-222)~~ but AAAA-111 stands", "AAAA-111"),
          "NEGATIVE CONTROL: a pid OUTSIDE the struck span is untouched")


# --- fixtures ---------------------------------------------------------------

# THE P-BEAZEM SHAPE. The wife is named once, in a marriage narrative that cites the
# ONE record documenting that marriage. The husband's entry holds four more records
# that have nothing to do with her.
MARRIAGE_NARRATIVE = f"""### Generation 5

**Rich Husband** (b. 1850; d. 1920; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 5, fs: {PID_A}}}
- Married **Poor Wife** (FS {PID_B}), m. 17 JAN 1883 — marriage atto no 2 — {ARK5}
- **Sources** (fixture):
  - 1900 census — {ARK1}
  - 1910 census — {ARK2}
  - 1920 census — {ARK3}
  - death certificate — {ARK4}

**Poor Wife** (b. 1859; d. 1936; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: partial, life_status: deceased, generation: 5, fs: {PID_B}}}
- Nothing of her own is cited here; the marriage record is on her husband's entry.
"""

# THE CONVENTION THAT MUST KEEP WORKING, at the right magnitude: an inline-collateral
# bullet carrying its own locators credits its owner THOSE locators — not the four
# unrelated records elsewhere in the entry.
INLINE_COLLATERAL = f"""### Generation 9

**Rich Husband** (b. 1700; d. 1770; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: {PID_A}}}
- **Sources** (fixture):
  - 1750 deed — {ARK1}
  - 1755 deed — {ARK2}
  - 1760 will — {ARK3}
  - 1770 probate — {ARK4}
- **FS-attached sources for wife Poor Wife** ({PID_B}, inline collateral):
  - her baptism — {ARK5}
  - her burial — {ARK6}

**Poor Wife** (b. 1702; d. 1772; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 9, fs: {PID_B}}}
- Her records are recorded on her husband's entry, with her own locators.
"""

# THE ELIGIBILITY HALF, unchanged: a kin-list mention carries no locator of its own
# and must still credit nothing at all.
KIN_LIST = f"""### Generation 9

**Rich Husband** (b. 1700; d. 1770; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: {PID_A}}}
- Siblings: Poor Wife ({PID_B}), who has no records of her own here.
- **Sources** (fixture):
  - 1750 deed — {ARK1}
  - 1755 deed — {ARK2}
  - 1760 will — {ARK3}
  - 1770 probate — {ARK4}

**Poor Wife** (b. 1702; d. 1772; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 9, fs: {PID_B}}}
- Named in her brother's entry, with nothing of her own.
"""


def main():
    print("== the P-BEAZEM shape: a documented mention credits ITS OWN record ==")
    c = census(MARRIAGE_NARRATIVE)
    check(c.get("Rich Husband", ("", 0))[1] == 5,
          "the entry's own person keeps all 5 records in his body")
    check(c.get("Poor Wife", ("", None))[1] == 1,
          "the wife is credited the ONE marriage record naming her, not his 5")
    check(c.get("Poor Wife", ("", 0))[0] == "LOW_COVERAGE",
          "...so she lands in LOW_COVERAGE, where a 1-record person belongs")

    print("\n== negative control: credit the whole body again ==")
    with whole_body_credit():
        n = census(MARRIAGE_NARRATIVE)
    check(n.get("Poor Wife", ("", None))[1] == 5,
          "she inherits all 5 of his records again (control works)")
    check(n.get("Poor Wife", ("", 0))[0] == "WELL_SOURCED",
          "...and reads WELL_SOURCED off a husband's entry - the live defect")
    check(n.get("Rich Husband") == c.get("Rich Husband"),
          "the entry's OWN person is unaffected either way (path 1 untouched)")

    print("\n== inline collateral still credits its owner, at ITS magnitude ==")
    i = census(INLINE_COLLATERAL)
    check(i.get("Poor Wife", ("", None))[1] == 2,
          "the wife gets the 2 locators on her own bullet, not the entry's 6")
    check(i.get("Poor Wife", ("", 0))[0] == "LOW_COVERAGE",
          "...LOW_COVERAGE, not WELL_SOURCED off her husband's deeds")
    # ** SUPERSEDED BY deferred_decisions 49 (04 AUG 2026). ** This asserted 6 —
    # the husband keeping every record in his body, the wife's inline-collateral
    # baptism and burial included. That was deliberate when deferred 29 landed:
    # that fix scoped only the FOREIGN path and left the own-person path crediting
    # count_records(body).
    #
    # It is now 4. The two locators on the wife's own bullet are HERS, and
    # crediting them to him as well was the mirror image of the defect this very
    # file exists to pin — "neither does a documented one inherit the whole entry"
    # applied in one direction only. On the reference vault the asymmetry credited
    # 12 entries with 226 records that were not theirs; the worst read 95 where its
    # own Sources bullet says "13 record ARKs".
    check(i.get("Rich Husband", ("", 0))[1] == 4,
          "the husband keeps his OWN 4 records — the wife's 2 are hers (deferred 49)")
    check(i.get("Rich Husband", ("", 0))[0] == "WELL_SOURCED",
          "...and 4 still reads WELL_SOURCED, so the scoping did not over-correct")

    print("\n== negative control: the convention must be BREAKABLE ==")
    with whole_body_credit():
        m = census(INLINE_COLLATERAL)
    check(m.get("Poor Wife", ("", None))[1] == 6,
          "she inherits all 6 again (control works on this fixture too)")

    print("\n== the eligibility half is UNCHANGED: a kin list credits nothing ==")
    k = census(KIN_LIST)
    check(k.get("Rich Husband", ("", 0))[1] == 4, "the owner keeps his records")
    check(k.get("Poor Wife", ("", None))[1] == 0,
          "a PID in a `- Siblings:` list still inherits NOTHING")
    check(k.get("Poor Wife", ("", 0))[0] in ("SOURCE_GAP", "UNCITED", "BOOK_SOURCED"),
          "...and lands in a gap category, where the IMPROVE lane can see her")

    print("\n== the mirror-image defect is NOT introduced ==")
    check(i.get("Poor Wife", ("", 0))[1] > 0 and c.get("Poor Wife", ("", 0))[1] > 0,
          "a documented relative is never un-credited to zero")

    print("\n== deferred 54, remaining half: a KIN LIST documents nobody ==")
    test_kin_list_credits_nobody()
    test_shared_event_still_credits()

    print("\n== deferred 59 option 1: struck-out people + long bracketed rosters ==")
    test_struck_out_person_credits_nothing()
    test_long_bracketed_roster_is_still_a_kin_list()
    test_59_negative_controls()

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
