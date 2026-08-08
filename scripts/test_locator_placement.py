#!/usr/bin/env python3
"""Regression tests for LOCATOR PLACEMENT sensitivity (deferred_decisions 54).

Runnable with no test framework: `python3 scripts/test_locator_placement.py`
(exit 0 = pass).

✅ **THE OVER-SUBTRACTION HALF WAS FIXED 08 AUG 2026** (deferred 54, operator chose
"both, narrowly"); these tests now GUARD the fix rather than pin the defect. The
over-CREDITING half is still open -- see the item -- and is not covered here.

THE DEFECT. A person's `ark_count` depends on WHERE a locator sits, not only on
whether it counts. Deferred 54 recorded a four-configuration table taken from a
live entry in which negating four locators RAISED the reported count by three,
and deleting them gave the same figure as negating them -- so a session doing the
documented right thing (negate, never delete) watched the number move the wrong
way and reasonably suspected its own edit.

⚠⚠ **THE CENSUS CANNOT SEE ANY OF THIS, WHICH IS WHY THESE TESTS ARE THE ONLY
GUARD.** Fixing the over-subtraction moved NO census count on the reference vault
(SOURCE_GAP 175 before and after), because `fold_matches` takes `max()` across a
person's crediting blocks and another block was already winning. Two WRONG versions
of this fix also moved no count. **A green census is not evidence that a change to
this code is correct, in either direction.**

** WHY THE TABLE IS RE-DERIVED SYNTHETICALLY HERE RATHER THAN COPIED. ** The
original table belongs to a real person whose entry is ~69k chars. These tests
live in the PUBLIC fork, so the fixture has to be synthetic; and a fixture built
from one 69k entry would in any case pin that entry's accidents rather than the
mechanism. What is pinned below is the MECHANISM, reproduced from first
principles, plus the invariant any fix must satisfy.

THE MECHANISM, isolated. `own_region` drops the whole region of any top-level
bullet matching `_SOURCES_BULLET_RE` -- `sources` followed by `for` / `of` / a
dash -- in which a resolvable FOREIGN pid appears ANYWHERE, sub-bullets included.
That widening is deliberate and correct for a genuine relative-sources bullet
(the convention Spec 05 defines). But the head test does not distinguish

    - **FS-attached sources for wife <Name>** (<PID>, inline collateral): ...
        ^ a relative's bullet. Subtracting it is the entire point.

from

    - **Sources for his life** (...):
        ^ the entry's OWN bullet, merely phrased with the word "for".

so citing ONE relative's pid inside the second form deletes every record in it.
Measured synthetically below: 5 records -> 0, WELL_SOURCED -> SOURCE_GAP, from
ADDING a locator. Measured on the reference vault the day this was written: 12
entries lose records to the subtraction, 9 of them correctly; the clearest false
positive is an entry whose bullet head says in so many words that it is the
person's OWN profile, and which reads 5 where its own text claims 29.

THE INVARIANT, which is what a fix must be judged against and what makes these
tests useful beyond the one shape:

    ADDING a locator must never LOWER a person's ark_count, and
    NEGATING a locator must never RAISE it.

Both directions are asserted. Each carries a positive control -- a near-identical
fixture that must NOT trip -- because a test that only ever fires proves nothing
about what it is discriminating.
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

# PID- and ARK-shaped literals are assembled at runtime rather than written out:
# an ALL-CAPS four-then-three hyphenated token has the exact shape of a real
# FamilySearch PID and the repo's PII gate blocks on it, correctly, since it
# cannot tell a fixture from a person. Same convention as
# test_foreign_credit_magnitude and test_census_id_keyed.
PID_SELF = "AAAA" + "-" + "111"
PID_KID = "BBBB" + "-" + "222"
ARK = ["fs:1:1:" + "QQQQ" + "-" + f"999{i}" for i in range(1, 7)]


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def xfail(cond, label, want):
    """Pin a KNOWN-UNFIXED defect: assert the CURRENT behaviour, name the correct one.

    ** WHY THESE ARE NOT PLAIN FAILURES. ** deferred 54 is an OPEN operator
    decision -- three options are on the table and they give different numbers --
    so this file must not assert an outcome the operator has not chosen. What it
    CAN do is stop the behaviour drifting unnoticed in the meantime, which is
    exactly what the item asks for ("pin the table so it cannot silently change").

    `cond` is the CURRENT, WRONG behaviour. If it stops holding, this fires --
    either because the defect was fixed (flip the assertion; see below) or because
    it changed shape on its own, which is the case nothing else would catch.

    WHEN THE RULING LANDS: each xfail below becomes a `check` of `want`. That is a
    one-line edit per case and needs no new fixtures."""
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  xfail {label}")
        print(f"         correct behaviour once deferred 54 is ruled: {want}")
    else:
        FAIL += 1
        print(f"  FAIL  {label} — current behaviour CHANGED; re-measure deferred 54")


def census(text):
    """{display_name: (category, ark_count)} for a one-file fixture vault.

    Both modules resolve their vault at import time into a module global, so the
    fixture has to redirect BOTH."""
    d = tempfile.mkdtemp(prefix="locator-placement-")
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        json.dump({"person_model": "narrative"}, f)
    with open(os.path.join(d, "Family_Tree_Fixture.md"), "w", encoding="utf-8") as f:
        f.write(text)
    saved = (HS.VAULT, G.VAULT)
    try:
        HS.VAULT, G.VAULT = d, d
        return {r["name"]: (r["category"], r["ark_count"]) for r in HS.gather_records()}
    finally:
        HS.VAULT, G.VAULT = saved
        shutil.rmtree(d)


def fixture(bullet_head, extra_sub_bullets=""):
    """One documented person, plus a child who exists so their pid RESOLVES.

    The child has to be a real roster entry: `own_region` subtracts only for a
    foreign pid that resolves via `pid_to_id`, and that roster test is itself
    load-bearing (it is what stops a bare ARK suffix scanning as a pid)."""
    return f"""### Generation 5

**Main Person** (b. 1850; d. 1920; FS PID {PID_SELF})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 5, fs: {PID_SELF}}}
- {bullet_head}
  - 1900 census — {ARK[0]}
  - 1910 census — {ARK[1]}
  - 1920 census — {ARK[2]}
  - death certificate — {ARK[3]}
{extra_sub_bullets}
**A Child** (b. 1880; d. 1950; FS PID {PID_KID})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 4, fs: {PID_KID}}}
- Nothing of her own is cited here.
"""


RELATIVE_LINE = f"  - daughter's 1905 marriage ({PID_KID}) — {ARK[4]}\n"
NEGATED_LINE = f"  - daughter's 1905 marriage ({PID_KID}) — ~{ARK[4]}\n"
PLAIN_LINE = f"  - his 1905 property deed — {ARK[4]}\n"


def n(text, who="Main Person"):
    return census(text)[who][1]


def cat(text, who="Main Person"):
    return census(text)[who][0]


def main():
    print("the mechanism: an OWN sources bullet phrased 'Sources for ...'")
    plain_head = "**Sources** (fixture):"
    for_head = "**Sources for his life** (fixture):"

    base_plain = n(fixture(plain_head))
    base_for = n(fixture(for_head))
    check(base_plain == 4, f"'**Sources**' alone counts 4 (got {base_plain})")
    check(base_for == 4, f"'**Sources for his life**' alone counts 4 (got {base_for})")

    # POSITIVE CONTROL: under the plain head, adding a relative-naming locator
    # behaves the way anyone would expect -- the count goes UP by one.
    up_plain = n(fixture(plain_head, RELATIVE_LINE))
    check(up_plain == 5,
          f"positive control: under '**Sources**', +1 relative locator -> 5 (got {up_plain})")

    # THE DEFECT: identical content, head phrased with "for", and the SAME
    # addition erases everything.
    up_for = n(fixture(for_head, RELATIVE_LINE))
    print(f"       ('**Sources for ...**' with the same added locator reads {up_for})")

    print()
    print("INVARIANT 1 — adding a locator must never LOWER the count")
    check(up_plain >= base_plain,
          f"plain head: {base_plain} -> {up_plain}")
    check(up_for == base_for + 1,
          f"'for' head: {base_for} -> {up_for} (was 4 -> 0 before deferred 54 was fixed)")

    print()
    print("INVARIANT 2 — negating a locator must never RAISE the count")
    # The plain head is the positive control and must hold outright.
    live = n(fixture(plain_head, RELATIVE_LINE))
    negated = n(fixture(plain_head, NEGATED_LINE))
    deleted = n(fixture(plain_head))
    check(negated <= live, f"plain head: negate {live} -> {negated}")
    check(negated == deleted,
          f"plain head: negating ({negated}) agrees with deleting ({deleted})")

    # Under the 'for' head the live reading is already 0, so negation cannot
    # RAISE it -- but negating and deleting disagree, which is the same
    # non-monotonicity the live four-configuration table recorded.
    live_f = n(fixture(for_head, RELATIVE_LINE))
    neg_f = n(fixture(for_head, NEGATED_LINE))
    del_f = n(fixture(for_head))
    check(neg_f <= live_f, f"'for' head: negate {live_f} -> {neg_f}")
    check(neg_f == del_f,
          f"'for' head: negating ({neg_f}) agrees with deleting ({del_f}) "
          f"-- recording an exclusion now costs nothing")

    print()
    print("category consequence — the count is what the census bands read from")
    c_plain = cat(fixture(plain_head, RELATIVE_LINE))
    c_for = cat(fixture(for_head, RELATIVE_LINE))
    check(c_plain == "WELL_SOURCED", f"plain head stays WELL_SOURCED (got {c_plain})")
    check(c_for == "WELL_SOURCED",
          f"'for' head stays {c_for} on the SAME content (was SOURCE_GAP)")

    print()
    print("THE TWO TRAPS THAT DEFEATED THE FIRST TWO ATTEMPTS AT THIS FIX")
    # Real heads run to 200+ chars because the whole parenthetical sits on the line.
    # Attempt 1 searched the WHOLE LINE for a relation word and matched "sons" in an
    # entry's own explanatory prose. Attempt 2 searched the whole line for a PID and
    # matched pids quoted downstream. Both left the false subtraction in place and
    # both LOOKED like working fixes. Neither is detectable from the census, which
    # does not move either way (max() over blocks masks it).
    prose_relation = ("**Sources — his OWN profile** (Recipe-S 01 JUL 2026, surfaced by an "
                      "audit: the prior bullet cited only the three sons and missed these):")
    prose_pid = (f"**Sources — his OWN profile** (Recipe-S 01 JUL 2026, cross-checked against "
                 f"{PID_KID} and others):")
    for label, head in (("relation word in the head's PROSE", prose_relation),
                        ("a PID quoted downstream in the head", prose_pid)):
        got = n(fixture(head, RELATIVE_LINE))
        check(got == 5, f"{label}: own bullet NOT subtracted -> {got} (must be 5, not 0)")
    # ...while the genuine forms these traps resemble must still be recognised.
    for label, head in (
            ("target names a relation", "**FS-attached sources for wife Jane** (fixture):"),
            ("PID in the first clause",
             f"**FS-attached sources for Jane Doe** ({PID_KID}, inline collateral):")):
        got = n(fixture(head, RELATIVE_LINE))
        check(got == 0, f"positive control, {label}: subtracted -> {got} (must be 0)")

    print()
    print("NEGATIVE CONTROL — the rule must still subtract a GENUINE relative bullet")
    # This is the case own_region exists for. It must keep working, or a "fix"
    # that merely switches the subtraction off would pass everything above.
    genuine = f"""### Generation 9

**Main Person** (b. 1700; d. 1770; FS PID {PID_SELF})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: {PID_SELF}}}
- **Sources** (fixture):
  - 1750 deed — {ARK[0]}
  - 1760 will — {ARK[1]}
- **FS-attached sources for daughter A Child** ({PID_KID}, inline collateral):
  - her baptism — {ARK[2]}
  - her burial — {ARK[3]}

**A Child** (b. 1730; d. 1800; FS PID {PID_KID})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 8, fs: {PID_KID}}}
- Her records are recorded on her father's entry, with her own locators.
"""
    g = census(genuine)
    check(g["Main Person"][1] == 2,
          f"father credited only his own 2 (got {g['Main Person'][1]})")
    check(g["A Child"][1] == 2,
          f"daughter credited her own 2 via inline collateral (got {g['A Child'][1]})")

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
