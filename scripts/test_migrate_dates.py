#!/usr/bin/env python3
"""test_migrate_dates.py — fixture tests for the Spec 04 migration.

Runnable with no test framework: `python3 test_migrate_dates.py` (exit 0 = pass).

One case per residue class, plus the invariants the migration promises: headers
untouched, idempotent, living/unknown skipped, no phrase written by default.

The MIXED case is the one that matters most. It is a person whose born is residue
(`c.985/990` — Eudes of Vermandois) and whose died converts cleanly. On the first
live run that combination raised InvalidDateValue *mid-apply*, after 51 entries had
already been written, because `promote_dates=True` promotes every date field set on
the record and `record.born` falls back to the header. The Spec 03 write-time gate
caught it; this test is so it can never come back.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import migrate_dates as M
import person_store as ps
import vault_config

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


FIXTURE = """---
type: family_tree
---

### Generation 5: Fixture

**Clean Convert** (b. ~1750, Somewhereton; d. bef. 1866)
- meta: {id: P-CLEAN1, profile_status: partial, life_status: deceased, generation: 5}

**Already Valid** (b. 3 SEP 1780, Somewhereton, MA)
- meta: {id: P-VALID1, profile_status: complete, life_status: deceased, generation: 5}

**Mixed Residue And Value** (b. c.985/990; d. 25 MAY 1045)
- meta: {id: P-MIXED1, profile_status: stub, life_status: deceased, generation: 6}

**Absence Marker** (b. unknown; d. Deceased)
- meta: {id: P-ABSEN1, profile_status: stub, life_status: deceased, generation: 5}

**Place In Date Slot** (b. Russia)
- meta: {id: P-PLACE1, profile_status: stub, life_status: deceased, generation: 5}

**Dual Year Ancestor** (b. 6 JAN 1743/4, Somewhereton)
- meta: {id: P-DUAL01, profile_status: partial, life_status: deceased, generation: 5}

**Unstructurable Qualifier** (b. early 1621, Somewhereton)
- meta: {id: P-UNSTR1, profile_status: stub, life_status: deceased, generation: 5}

**Living Approx Person** (b. ~1980)
- meta: {id: P-LIVIN1, profile_status: partial, life_status: living, generation: 1}

**Living Exact Person** (b. 3 SEP 1980)
- meta: {id: P-LIVIN2, profile_status: partial, life_status: living, generation: 1}

**Nested Paren Header** (b. **3 SEP 1780** (a citation p.61; alt 5 SEP 1780), Somewhereton — a note. d. **between 1816 and 13 FEB 1823**, likely at sea)
- meta: {id: P-NESTD1, profile_status: complete, life_status: deceased, generation: 5}
"""

FNAME = "Family_Tree_Fixture.md"


def make_vault():
    d = tempfile.mkdtemp(prefix="migrate-dates-")
    with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(d, FNAME), "w") as fh:
        fh.write(FIXTURE)
    vault_config.load_config.cache_clear()
    return d


def meta_of(vault, pid):
    for line in open(os.path.join(vault, FNAME), encoding="utf-8"):
        if pid in line:
            return line
    return ""


def main():
    v = make_vault()
    try:
        before_headers = M.header_lines(v)
        before_text = open(os.path.join(v, FNAME), encoding="utf-8").read()

        # ---- classification, one case per residue class ------------------ #
        for value, want in [("unknown", "absence"), ("Deceased", "absence"),
                            ("?", "absence"), ("Russia", "place-leak"),
                            ("6 JAN 1743/4", "dual-year"), ("early 1621", "unstructurable"),
                            ("c.985/990", "unstructurable")]:
            got = M.classify(value)
            check(got == want, f"classify({value!r}) -> {want}"
                  + ("" if got == want else f" (got {got})"))

        # ---- the plan ----------------------------------------------------- #
        plan = M.build_plan(v)
        conv = {(r.id, k): new for r, k, _o, new in plan.converted}
        res = {(r.id, k): kl for r, k, _v, kl in plan.residue}
        check(conv.get(("P-CLEAN1", "born")) == "ABT 1750", "convert: ~1750 -> ABT 1750")
        check(conv.get(("P-CLEAN1", "died")) == "BEF 1866", "convert: bef. 1866 -> BEF 1866")
        check(conv.get(("P-VALID1", "born")) == "3 SEP 1780",
              "convert: an already-valid value is carried through (place dropped)")
        check(conv.get(("P-NESTD1", "died")) == "BET 1816 AND 13 FEB 1823",
              "convert: the nested-paren death window is found and normalised")
        check(("P-ABSEN1", "born") in res and ("P-ABSEN1", "died") in res,
              "residue: absence markers are refused, not stored")
        check(res.get(("P-PLACE1", "born")) == "place-leak", "residue: place-in-date-slot flagged")
        check(res.get(("P-DUAL01", "born")) == "dual-year", "residue: dual year classified")
        check(("P-LIVIN1", "born") not in conv and ("P-LIVIN2", "born") not in conv,
              "living/unknown skipped by DEFAULT (both anchors of a real vault are living)")

        # THE regression: mixed residue-born + valid-died on one record.
        check(("P-MIXED1", "died") in conv and ("P-MIXED1", "born") in res,
              "mixed: died converts while born stays residue")

        # ---- apply --------------------------------------------------------- #
        written = M.apply_plan(v, plan)
        check(written > 0, f"apply wrote {written} entries")
        check(meta_of(v, "P-MIXED1").count("born:") == 0
              and "died: '25 MAY 1045'" in meta_of(v, "P-MIXED1"),
              "mixed: the residue born is NOT promoted, the valid died IS "
              "(the bug that raised InvalidDateValue mid-apply on the live vault)")
        check("born: 'ABT 1750'" in meta_of(v, "P-CLEAN1")
              and "died: 'BEF 1866'" in meta_of(v, "P-CLEAN1"),
              "apply: values written single-quoted into the meta block")
        check("born:" not in meta_of(v, "P-ABSEN1"),
              "apply: an absence marker leaves the key ABSENT (absence = unknown)")
        check("phrase" not in open(os.path.join(v, FNAME), encoding="utf-8").read(),
              "apply: NO *_phrase is ever written by a default run")

        # ---- the invariants ------------------------------------------------ #
        after_headers = M.header_lines(v)
        check(before_headers == after_headers, "apply: every header line byte-identical")
        body_before = [ln for ln in before_text.split("\n") if not ln.lstrip().startswith("- meta:")]
        body_after = [ln for ln in open(os.path.join(v, FNAME), encoding="utf-8").read().split("\n")
                      if not ln.lstrip().startswith("- meta:")]
        check(body_before == body_after, "apply: ONLY meta lines changed; all other text untouched")

        # ---- idempotence ---------------------------------------------------- #
        text1 = open(os.path.join(v, FNAME), encoding="utf-8").read()
        plan2 = M.build_plan(v)
        check(not plan2.converted and plan2.skipped_existing > 0,
              f"second run converts nothing ({plan2.skipped_existing} keys already present)")
        M.apply_plan(v, plan2)
        check(open(os.path.join(v, FNAME), encoding="utf-8").read() == text1,
              "second --apply is BYTE-IDENTICAL (idempotent)")

        # ---- --include-living still honours the Spec 01 screen -------------- #
        v2 = make_vault()
        plan3 = M.build_plan(v2, include_living=True)
        conv3 = {(r.id, k) for r, k, _o, _n in plan3.converted}
        blocked = {(r.id, k) for r, k, _v in plan3.blocked_private}
        check(("P-LIVIN1", "born") in conv3,
              "--include-living: a living person MAY gain an approximate year")
        check(("P-LIVIN2", "born") in blocked and ("P-LIVIN2", "born") not in conv3,
              "--include-living: a DAY-PRECISE value is still blocked for a living person")
        M.apply_plan(v2, plan3)
        check("born: 'ABT 1980'" in meta_of(v2, "P-LIVIN1")
              and "born:" not in meta_of(v2, "P-LIVIN2"),
              "--include-living: the screen holds through the write")
        shutil.rmtree(v2)

        # ---- --dual-year is opt-in ------------------------------------------ #
        v3 = make_vault()
        plan4 = M.build_plan(v3, dual_year=True)
        dual = {(r.id, k): (val, ph) for r, k, _o, val, ph in plan4.dual}
        check(dual.get(("P-DUAL01", "born")) == ("6 JAN 1744", "6 JAN 1743/4"),
              "--dual-year: proposes the lossless DATE + PHRASE pair")
        M.apply_plan(v3, plan4)
        check("born: '6 JAN 1744'" in meta_of(v3, "P-DUAL01")
              and "born_phrase: '6 JAN 1743/4'" in meta_of(v3, "P-DUAL01"),
              "--dual-year: writes both keys")
        shutil.rmtree(v3)
    finally:
        shutil.rmtree(v)

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
