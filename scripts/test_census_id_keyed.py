#!/usr/bin/env python3
"""Regression tests for the id-keyed source census (the "census blind spot").

Runnable with no test framework: `python3 scripts/test_census_id_keyed.py`
(exit 0 = pass).

THE DEFECT THESE LOCK DOWN. `harvest_sources.parse_person_index` opened with

    pid = e["pid"]
    if not pid:
        continue

on the reasoning in its own docstring: "an entry without one has no FS profile whose
Sources tab could be harvested." That is TRUE FOR HARVESTING and FALSE FOR CENSUSING,
and the one function fed both jobs. Measured on the reference vault the day it was
fixed: **210 of 1,320 entries - 16% - reached no category at all.** Not SOURCE_GAP,
not UNCITED: absent. 60 carried a `- **Sources**` bullet and 12 carried real locators.

The sharpest case is `fs: none`, which MEANS "searched FamilySearch, confirmed no
profile" - a finding, recorded correctly - and it erased the person from the vault's
own coverage numbers. `fs: TBD` did the same to 162 more.

The fix keys the roster and the scanner on the vault `id`: unique, never reused, and
BLOCKING in `gen_person_index --integrity`, so nothing can lack one. The FS PID rides
along and still drives every FS-facing path.

WHAT IS DELIBERATELY NOT CHANGED, and is tested here as hard as the fix itself: the
Spec 05 inline-collateral rule. A foreign PID named in a kin list still credits
NOTHING; a foreign PID carrying its OWN locators still credits its owner. Dropping
that would be the mirror-image defect - un-crediting every inline-collateral relative.

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

# FS-PID- and ARK-shaped literals are assembled at runtime, never written out. An
# ALL-CAPS four-then-three hyphenated token has exactly the shape of a real
# FamilySearch PID, and the repo's PII gate blocks on it - correctly, since it cannot
# know a fixture from a person. Same reason test_entry_boundary writes its trap in
# lowercase prose.
PID_A = "AAAA" + "-" + "111"          # a PID-bearing entry
PID_B = "BBBB" + "-" + "222"          # an inline-collateral relative
ARK1 = "fs:1:1:" + "QQQQ" + "-" + "9991"
ARK2 = "fs:1:1:" + "QQQQ" + "-" + "9992"
ARK3 = "fs:1:1:" + "QQQQ" + "-" + "9993"
ARK4 = "fs:1:1:" + "QQQQ" + "-" + "9994"


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def narrative_vault(text, prefix="census-id-"):
    d = tempfile.mkdtemp(prefix=prefix)
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        json.dump({"person_model": "narrative"}, f)
    with open(os.path.join(d, "Family_Tree_Fixture.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return d


def census(text):
    """{display_name: (category, record_count)} for a one-file fixture vault.

    Both modules resolve their vault at import time into a module global, so the
    fixture has to redirect BOTH: `harvest_sources` for the body scan and
    `gen_person_index` for the roster. Missing the second one just yields a
    TypeError deep in vault_config rather than a wrong answer, which is the
    friendlier failure of the two.
    """
    d = narrative_vault(text)
    saved_hs, saved_g = HS.VAULT, G.VAULT
    try:
        HS.VAULT, G.VAULT = d, d
        recs = HS.gather_records()
        return {r["name"]: (r["category"], r["ark_count"]) for r in recs}
    finally:
        HS.VAULT, G.VAULT = saved_hs, saved_g
        shutil.rmtree(d)


class pid_gated_roster:
    """Negative control: reinstate the exact line that caused the blind spot."""

    def __enter__(self):
        self._saved = HS.parse_person_index

        def gated():
            full = self._saved()
            return {k: v for k, v in full.items() if v.get("pid")}

        HS.parse_person_index = gated
        return self

    def __exit__(self, *exc):
        HS.parse_person_index = self._saved
        return False


class id_scraped_by_regex:
    """Negative control: take the entry id from a regex built on the DOCUMENTED id
    grammar (`P-` + 6 Crockford chars, no I/L/O/U) instead of from the person_store
    seam. This is what the first cut of the fix did, and 15 live entries fell out of
    the census because the vault legitimately contains ids the spec forbids."""

    def __enter__(self):
        import re
        self._saved = HS.entry_blocks_with_ids
        strict = re.compile(r"\bid:\s*(P-[0-9A-HJKMNP-TV-Z]{6})\b")

        def scraped(vault=None):
            out = {}
            for path, ents in self._saved(vault).items():
                rows = []
                for _id, name, hline, body in ents:
                    m = strict.search(body)
                    rows.append((m.group(1) if m else None, name, hline, body))
                out[path] = rows
            return out

        HS.entry_blocks_with_ids = scraped
        return self

    def __exit__(self, *exc):
        HS.entry_blocks_with_ids = self._saved
        return False


# --- fixtures ---------------------------------------------------------------

# Three entries the OLD census could not see, one it could. All four are documented.
BLIND_SPOT = f"""### Generation 8

**Ada Withpid** (b. 1800; d. 1870; FS PID {PID_A})
- meta: {{id: P-AAA111, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 8, fs: {PID_A}}}
- **Sources** (fixture):
  - {ARK1}
  - {ARK2}
  - {ARK3}
  - {ARK4}

**Bess Tbd** (b. 1802; d. 1872)
- meta: {{id: P-BBB222, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 8, fs: TBD}}
- **Sources** (fixture):
  - {ARK1}
  - {ARK2}
  - {ARK3}
  - {ARK4}

**Cora Nofs** (b. 1804; d. 1874)
- meta: {{id: P-CCC333, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 8, fs: none}}
- **Sources** (fixture):
  - {ARK1}

**Dora Nokey** (b. 1806; d. 1876)
- meta: {{id: P-DDD444, evidence_tier: strong_signal, profile_status: partial, life_status: deceased, generation: 8}}
- No source of any kind recorded for her.
"""

# Spec 05 must survive the rekeying: a kin-list mention credits nothing, an
# inline-collateral bullet carrying its own locators credits its owner.
COLLATERAL = f"""### Generation 9

**Rich Ancestor** (b. 1700; d. 1770; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: {PID_A}}}
- Siblings: Poor Relation ({PID_B}), who has no records of her own here.
- **Sources** (fixture):
  - {ARK1}
  - {ARK2}
  - {ARK3}
  - {ARK4}

**Poor Relation** (b. 1702; d. 1772; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 9, fs: {PID_B}}}
- Named in her brother's entry, with nothing of her own.
"""

INLINE_COLLATERAL = f"""### Generation 9

**Rich Ancestor** (b. 1700; d. 1770; FS PID {PID_A})
- meta: {{id: P-AAA111, profile_status: complete, life_status: deceased, generation: 9, fs: {PID_A}}}
- **Sources** (fixture):
  - {ARK1}
  - {ARK2}
  - {ARK3}
  - {ARK4}
- **FS-attached sources for wife Poor Relation** ({PID_B}, inline collateral): {ARK1}, {ARK2}, {ARK3}, {ARK4}

**Poor Relation** (b. 1702; d. 1772; FS PID {PID_B})
- meta: {{id: P-BBB222, profile_status: stub, life_status: deceased, generation: 9, fs: {PID_B}}}
- Her records are recorded on her husband's entry, with her own locators.
"""

# ids the DOCUMENTED grammar forbids but the vault actually contains: `L` and `O` are
# not Crockford base32, and P-TMC22 is five characters, not six. The integrity gate
# enforces DUP_ID and MISSING_ID - not the id's SHAPE - so these are legal in practice.
ODD_IDS = f"""### Generation 10

**Lottie Oddid** (b. 1650; d. 1700)
- meta: {{id: P-MLV258, profile_status: complete, life_status: deceased, generation: 10, fs: TBD}}
- **Sources** (fixture):
  - {ARK1}

**Shorty Oddid** (b. 1652; d. 1702)
- meta: {{id: P-TMC22, profile_status: complete, life_status: deceased, generation: 10, fs: TBD}}
- **Sources** (fixture):
  - {ARK2}
"""


def main():
    print("== the blind spot: an entry without an FS PID is still censused ==")
    c = census(BLIND_SPOT)
    check(set(c) == {"Ada Withpid", "Bess Tbd", "Cora Nofs", "Dora Nokey"},
          "all four entries reach a category (was: only the PID-bearing one)")
    check(c.get("Bess Tbd") == ("WELL_SOURCED", 4),
          "`fs: TBD` + 4 records -> WELL_SOURCED, not invisible")
    check(c.get("Cora Nofs") == ("LOW_COVERAGE", 1),
          "`fs: none` + 1 record -> LOW_COVERAGE ('searched FS, none' is a FINDING)")
    check(c.get("Dora Nokey", ("", 0))[1] == 0 and c.get("Dora Nokey", ("",))[0] in
          ("SOURCE_GAP", "UNCITED", "BOOK_SOURCED"),
          "no `fs` key at all + no sources -> lands in a gap category, not nowhere")

    print("\n== negative control: reinstate `if not pid: continue` ==")
    with pid_gated_roster():
        g = census(BLIND_SPOT)
    check(set(g) == {"Ada Withpid"},
          "the three PID-less entries vanish again (control works)")
    check("Bess Tbd" not in g and "Cora Nofs" not in g,
          "including the two carrying real locators - the 12-entry defect, minimised")

    print("\n== additivity: the PID-bearing entry is unaffected ==")
    check(c.get("Ada Withpid") == ("WELL_SOURCED", 4)
          and g.get("Ada Withpid") == ("WELL_SOURCED", 4),
          "same category and count with and without the PID gate")

    print("\n== Spec 05 survives the rekeying: a kin-list mention credits nothing ==")
    k = census(COLLATERAL)
    check(k.get("Rich Ancestor") == ("WELL_SOURCED", 4), "the owner keeps her records")
    check(k.get("Poor Relation", ("", None))[1] == 0,
          "a PID in a `- Siblings:` list inherits NOTHING")

    print("\n== ...and inline collateral still credits its owner ==")
    i = census(INLINE_COLLATERAL)
    # Assert the PROPERTY, not an exact count: this body mixes the migrated
    # `Sources` sub-bullets with a legacy flat inline-collateral bullet, so it
    # legitimately holds 5 record lines, not 4. Pinning the number here would be a
    # test of count_records' record/locator model, which has its own tests.
    check(i.get("Rich Ancestor", ("", 0))[0] == "WELL_SOURCED"
          and i.get("Rich Ancestor", ("", 0))[1] >= 4,
          "the entry's own person is credited")
    check(i.get("Poor Relation", ("", 0))[1] > 0,
          "a foreign PID on a bullet carrying its OWN locators IS credited")

    print("\n== the id comes from the seam, not a regex over the body ==")
    o = census(ODD_IDS)
    check(set(o) == {"Lottie Oddid", "Shorty Oddid"},
          "ids containing L/O, and a 5-char id, are censused (the vault has both)")

    print("\n== negative control: scrape the id with a spec-strict regex ==")
    with id_scraped_by_regex():
        r = census(ODD_IDS)
    # The control reproduces the defect's exact observed signature. The entries do
    # not disappear from the ROSTER (parse_narrative still sees them) - they lose
    # their body match and fall through to NO_NARRATIVE, which is why that count
    # jumped 0 -> 15 on the live vault and gave the first cut away.
    check(all(v[0] == "NO_NARRATIVE" and v[1] == 0 for v in r.values()) and len(r) == 2,
          "spec-strict id parsing strands them in NO_NARRATIVE - the 15-entry defect")

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
