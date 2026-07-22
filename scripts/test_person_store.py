#!/usr/bin/env python3
"""Smoke tests for person_store.py (spec/optional-person-model Spec 03).

Runnable with no test framework: `python3 test_person_store.py` (exit 0 = pass).
Covers the Spec-03 acceptance criteria: FileBackend read, byte-identical no-op
write, surgical single-field write (body preserved), backend selection, the
NarrativeBackend stub, and PersonRecord equality rules.
"""
import json
import os
import shutil
import tempfile

import gdate
import vault_config
import person_store as ps

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


PERSON_A = """---
type: person
name: "Jane Example"
born: 1840-03-01
died: 1901-11-12
life_status: deceased
family: "Example"
evidence_tier: strong_signal
profile_status: complete
id: P-7K3QM2
generation: 6
parents: [P-AAAAAA, P-BBBBBB]
spouse: [P-CCCCCC]
flags: [Q12]
fs: XXXX-XXX
sources:
  - "1880 US Census, Anytown"
  - "1901 death certificate"
created: 2026-05-19
tags: [genealogy, person]
---

# Jane Example

## Biography

Narrative body that must survive writes verbatim. Contains a date 1899-01-01 in prose.
"""

PERSON_LIVING = """---
type: person
name: "Chris Living"
born: 1990
died:
life_status: living
family: "Living"
evidence_tier: moderate_signal
profile_status: partial
id: P-LIV001
generation: 2
created: 2026-05-19
tags: [genealogy, person]
---

# Chris Living
"""


def make_vault(person_model=None):
    d = tempfile.mkdtemp()
    if person_model is not None:
        with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
            json.dump({"person_model": person_model}, fh)
    with open(os.path.join(d, "Jane_Example.md"), "w") as fh:
        fh.write(PERSON_A)
    with open(os.path.join(d, "Chris_Living.md"), "w") as fh:
        fh.write(PERSON_LIVING)
    # a template must be IGNORED (it also has type: person)
    os.makedirs(os.path.join(d, "templates"))
    with open(os.path.join(d, "templates", "person.md"), "w") as fh:
        fh.write("---\ntype: person\nname: \"[Full Name]\"\nid: P-XXXXXX\n---\n# [Full Name]\n")
    vault_config.load_config.cache_clear()
    return d


NARRATIVE_FILE = """---
type: family_tree
---

### Generation 6: Example

**Jane Example Ancestor** (b. 1840; d. 1873; FS PID XXXX-XXX)
- meta: {id: P-7K3QM2, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 6, fs: XXXX-XXX, parents: '[P-AAAAAA?, P-BBBBBB?]', spouse: '[P-CCCCCC]'}
- A body bullet that is not a person.

### Generation 7: Example

**John Example** (b. 1810; d. 1880; FS: YYYY-YYY)
- meta: {id: P-J0HN01, evidence_tier: moderate_signal, profile_status: partial, life_status: deceased, generation: 7, fs: YYYY-YYY}
- **Sources**
  - 1850 US Census, Anytown — fs:1:1:AAAA-AAA
  - 1880 death record — fs:3:1:BBBB-BBBB-BBBB
- Body.
"""


def make_narrative_vault():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(d, "Family_Tree_Example.md"), "w") as fh:
        fh.write(NARRATIVE_FILE)
    vault_config.load_config.cache_clear()
    return d


NARRATIVE_PRIVACY = """---
type: family_tree
---

### Generation 1: Test

**Alive Approx** (b. 1990)
- meta: {id: P-ALIVE1, profile_status: partial, life_status: living, generation: 1}

**Alive Exact** (b. 1990-04-12)
- meta: {id: P-ALIVE2, profile_status: partial, life_status: living, generation: 1}

### Generation 2: Test

**Dead Exact** (b. 12 Apr 1850; d. 3 Mar 1920)
- meta: {id: P-DEAD01, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 2}

**Unknown Exact** (b. May 5, 1900)
- meta: {id: P-UNK001, profile_status: stub, life_status: unknown, generation: 3}
"""


def make_privacy_vault(text=NARRATIVE_PRIVACY):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(d, "Family_Tree_Priv.md"), "w") as fh:
        fh.write(text)
    vault_config.load_config.cache_clear()
    return d


NARRATIVE_SURGICAL = """---
type: family_tree
---

### Generation 3: Surgical

**Order Test** (b. 1800; d. 1870)
- meta: {id: P-ORD001, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 3, fs: ZZZZ-ZZZ, spouse: '[P-SP0001]', parents: '[P-PA0001, P-PA0002]'}
- body bullet

**No Id Yet** (b. 1805)
- meta: {profile_status: stub, life_status: deceased, generation: 3}
- body bullet
"""


def make_surgical_vault():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(d, "Family_Tree_Surg.md"), "w") as fh:
        fh.write(NARRATIVE_SURGICAL)
    vault_config.load_config.cache_clear()
    return d


NARRATIVE_DATES = """---
type: family_tree
---

### Generation 8: Dated

**Fielded Ancestor** (b. 3 SEP 1780, Somewhereton)
- meta: {id: P-DATE01, profile_status: complete, life_status: deceased, generation: 8, fs: XXXX-XXX, born: '3 SEP 1780', died: 'BET 1816 AND 13 FEB 1823'}
- body bullet

**Dual Dated Ancestor** (b. 30 January 1648/49)
- meta: {id: P-DATE02, profile_status: complete, life_status: deceased, generation: 9, born: 'JULIAN 30 JAN 1649', born_phrase: '30 January 1648/49'}

**Legacy Prose Ancestor** (b. 1969, Somewhereton, MA)
- meta: {id: P-DATE03, profile_status: stub, life_status: deceased, generation: 2}
"""

PERSON_DATED = """---
type: person
name: "Dated Example"
born: JULIAN 30 JAN 1649
born_phrase: 30 January 1648/49
life_status: deceased
evidence_tier: strong_signal
profile_status: complete
id: P-FILE01
generation: 9
tags: [genealogy, person]
---

# Dated Example
"""


def make_dates_vault():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(d, "Family_Tree_Dates.md"), "w") as fh:
        fh.write(NARRATIVE_DATES)
    vault_config.load_config.cache_clear()
    return d


def make_dates_file_vault():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "file"}, fh)
    with open(os.path.join(d, "Dated.md"), "w") as fh:
        fh.write(PERSON_DATED)
    vault_config.load_config.cache_clear()
    return d


def main():
    # ---- 1. FileBackend iter_people -------------------------------------- #
    v = make_vault()  # no person_model key -> defaults to "file"
    check(ps.backend_name(v) == "file", "no person_model key -> file backend")
    people = {r.id: r for r in ps.iter_people(v)}
    check(set(people) == {"P-7K3QM2", "P-LIV001"},
          "iter_people finds both person files, template EXCLUDED")

    jane = people["P-7K3QM2"]
    check(jane.name == "Jane Example", "name read")
    check(jane.born == "1840-03-01" and isinstance(jane.born, str),
          "born kept VERBATIM as string (not coerced to date)")
    check(jane.generation == 6, "generation parsed as int")
    check(jane.evidence_tier == "strong_signal" and jane.life_status == "deceased",
          "tier + life_status read")
    check(jane.parents == ["P-AAAAAA", "P-BBBBBB"] and jane.spouse == ["P-CCCCCC"],
          "parents + spouse edges read")
    check(jane.flags == ["Q12"], "flags read")
    check(jane.external_ids == {"fs": "XXXX-XXX"}, "external id (fs) read")
    check(len(jane.sources) == 2, "sources list read")

    # ---- 2. get_person --------------------------------------------------- #
    check(ps.get_person(v, "P-LIV001").name == "Chris Living", "get_person by id")
    check(ps.get_person(v, "P-NOPE") is None, "get_person missing -> None")

    # ---- 3. no-op write is BYTE-IDENTICAL -------------------------------- #
    before_jane = open(os.path.join(v, "Jane_Example.md")).read()
    before_chris = open(os.path.join(v, "Chris_Living.md")).read()
    ps.write_person(v, jane)  # unchanged record
    after_jane = open(os.path.join(v, "Jane_Example.md")).read()
    after_chris = open(os.path.join(v, "Chris_Living.md")).read()
    check(after_jane == before_jane, "no-op write_person: target file byte-identical")
    check(after_chris == before_chris, "no-op write_person: OTHER files untouched")

    # ---- 4. surgical single-field write; body preserved ------------------ #
    jane.profile_status = "partial"
    ps.write_person(v, jane)
    txt = open(os.path.join(v, "Jane_Example.md")).read()
    check("profile_status: partial" in txt, "changed field written")
    check("evidence_tier: strong_signal" in txt, "sibling field untouched")
    check("Narrative body that must survive writes verbatim" in txt
          and "1899-01-01 in prose" in txt, "body preserved verbatim")
    reread = ps.get_person(v, "P-7K3QM2")
    check(reread.profile_status == "partial", "change round-trips back through iter")

    # ---- 5. NarrativeBackend: selection + iter_people read (Spec 04a) ----- #
    vn = make_narrative_vault()
    check(ps.backend_name(vn) == "narrative", "person_model narrative -> narrative backend")
    npeople = {r.id: r for r in ps.iter_people(vn)}
    check(set(npeople) == {"P-7K3QM2", "P-J0HN01"},
          "narrative iter_people: both meta entries found")
    nj = npeople["P-7K3QM2"]
    check(nj.name == "Jane Example Ancestor", "narrative: bold name read for display")
    check(nj.generation == 6 and nj.evidence_tier == "strong_signal",
          "narrative: generation + full evidence_tier from meta")
    check(nj.born == "1840" and nj.died == "1873", "narrative: vitals from header paren")
    check(nj.parents == ["P-AAAAAA?", "P-BBBBBB?"] and nj.spouse == ["P-CCCCCC"],
          "narrative: parents/spouse lists parsed, '?' preserved")
    check(nj.external_ids == {"fs": "XXXX-XXX"}, "narrative: fs external id from meta")
    check(nj.source_file == "Family_Tree_Example.md", "narrative: source_file = lineage file")
    check(nj.sources == [], "narrative: entry with no Sources bullet has empty sources")
    check(npeople["P-J0HN01"].sources ==
          ["1850 US Census, Anytown — fs:1:1:AAAA-AAA", "1880 death record — fs:3:1:BBBB-BBBB-BBBB"],
          "narrative: **Sources** sub-bullets captured verbatim")

    # ---- 5b. NarrativeBackend.write_person (Spec 04b) --------------------- #
    nf = os.path.join(vn, "Family_Tree_Example.md")
    before = open(nf).read()
    ps.write_person(vn, nj)  # unchanged record
    check(open(nf).read() == before, "narrative no-op write: file byte-identical")

    nj.profile_status = "partial"
    ps.write_person(vn, nj)
    after = open(nf).read()
    check("profile_status: partial" in after, "narrative: changed meta field written")
    check("**Jane Example Ancestor** (b. 1840; d. 1873; FS PID XXXX-XXX)" in after,
          "narrative: bold-name header preserved verbatim")
    check("A body bullet that is not a person." in after, "narrative: body bullet preserved")
    check("id: P-J0HN01" in after, "narrative: sibling entry untouched")
    reread = {r.id: r for r in ps.iter_people(vn)}["P-7K3QM2"]
    check(reread.profile_status == "partial", "narrative: change round-trips via iter")
    check(reread.parents == ["P-AAAAAA?", "P-BBBBBB?"] and reread.spouse == ["P-CCCCCC"],
          "narrative: parents/spouse survive the write")
    check(reread.external_ids == {"fs": "XXXX-XXX"}, "narrative: fs survives the write")

    orphan = ps.PersonRecord(id="P-NEW", name="New Person", generation=8)
    try:
        ps.write_person(vn, orphan)
        check(False, "narrative write of unlocated record should raise (4c)")
    except NotImplementedError:
        check(True, "narrative write of NEW (unlocated) record raises (4c pending)")

    # ---- 6. PersonRecord equality rules ---------------------------------- #
    a = ps.PersonRecord(id="P-1", born="ABT 1832", parents=["P-A", "P-B"],
                        source_file="a.md", raw={"x": 1})
    b = ps.PersonRecord(id="P-1", born="ABT 1832", parents=["P-B", "P-A"],
                        source_file="DIFFERENT.md", raw={"y": 2})
    check(a == b, "equality: parents order-independent + source_file/raw excluded")
    c = ps.PersonRecord(id="P-1", born="ABT 1832", parents=["P-A", "P-B?"])
    check(a != c, "equality: '?' unverified marker is significant")
    d = ps.PersonRecord(id="P-1", born="abt 1832", parents=["P-A", "P-B"])
    check(a != d, "equality: born compared VERBATIM (case-sensitive)")

    # ---- 7. converter round-trip (Spec 04c) ------------------------------ #
    import convert_person_model as conv
    vn2 = make_narrative_vault()   # fresh (vn was mutated by the write tests)
    v2 = make_vault()

    rn = conv.roundtrip(vn2, "narrative")
    check(rn["id_sets_equal"] and not rn["modeled_mismatches"],
          "converter: narrative->file->narrative lossless on modeled fields")
    check(rn["n_src"] == rn["n_back"] == 2, "converter: narrative round-trip preserves count")

    check(not rn["source_mismatches"] and rn["records_with_sources"] >= 1,
          "converter: narrative sources round-trip (John's 2 records)")

    rf = conv.roundtrip(v2, "file")
    check(rf["id_sets_equal"] and not rf["modeled_mismatches"],
          "converter: file->narrative->file lossless (incl. sources)")
    check(not rf["source_mismatches"] and rf["records_with_sources"] >= 1,
          "converter: file sources round-trip through narrative")

    # idempotent apply: same input -> byte-identical output
    d1, d2 = tempfile.mkdtemp(), tempfile.mkdtemp()
    recs = conv.read_as(vn2, "narrative")
    conv.write_file_model(d1, recs, apply=True)
    conv.write_file_model(d2, recs, apply=True)
    f1 = sorted(os.listdir(d1))
    same = f1 == sorted(os.listdir(d2)) and all(
        open(os.path.join(d1, f)).read() == open(os.path.join(d2, f)).read() for f in f1)
    check(same and len(f1) == 2, "converter: --apply is idempotent (byte-identical)")

    # ---- 8. narrative privacy validator (Spec 04d) ----------------------- #
    import check_narrative_privacy as cnp
    vp = make_privacy_vault()
    viol = cnp.check(vp)
    ids = " ".join(viol)
    check("P-ALIVE2" in ids, "privacy: living person with EXACT birth date flagged")
    check("P-UNK001" in ids, "privacy: unknown person with EXACT birth date flagged")
    check("P-ALIVE1" not in ids, "privacy: living person with approx YEAR not flagged")
    check("P-DEAD01" not in ids, "privacy: deceased person with exact dates allowed")
    check(not any("exposes an exact" in m and ("1990-04-12" in m or "1900" in m) for m in viol),
          "privacy: violation messages do NOT echo the private date value")
    # a clean vault passes
    clean = make_privacy_vault("---\ntype: family_tree\n---\n\n### Generation 2: T\n\n"
                               "**Ok Person** (b. 1850; d. 1920)\n"
                               "- meta: {id: P-OKOK01, profile_status: complete, life_status: deceased, generation: 2}\n")
    check(cnp.check(clean) == [], "privacy: clean narrative vault has 0 violations")

    # ---- 9. surgical narrative write: order/spacing preserved (Spec 05 writers) --- #
    vs = make_surgical_vault()
    sf = os.path.join(vs, "Family_Tree_Surg.md")
    people = {r.id: r for r in ps.iter_people(vs)}
    ordr = people["P-ORD001"]
    ordr.profile_status = "partial"          # change ONE unrelated field
    ps.write_person(vs, ordr)
    txt = open(sf).read()
    check("spouse: '[P-SP0001]', parents: '[P-PA0001, P-PA0002]'" in txt,
          "surgical: out-of-order spouse-before-parents NOT reformatted")
    check("profile_status: partial" in txt and "evidence_tier: strong_signal" in txt,
          "surgical: only the changed field changed")
    check("fs: ZZZZ-ZZZ" in txt, "surgical: fs untouched")

    # mint_ids' exact operation: seed an id into an idless block -> id inserted FIRST
    noid = [r for r in ps.iter_people(vs) if r.id is None][0]
    noid.id = "P-NEW999"
    ps.write_person(vs, noid)
    txt2 = open(sf).read()
    check("- meta: {id: P-NEW999, profile_status: stub, life_status: deceased, generation: 3}" in txt2,
          "surgical: new id inserted as FIRST meta key, rest byte-preserved")

    # insert a new key at its canonical slot (flags goes last)
    ordr2 = {r.id: r for r in ps.iter_people(vs)}["P-ORD001"]
    ordr2.flags = ["Q9"]
    ps.write_person(vs, ordr2)
    txt3 = open(sf).read()
    check("parents: '[P-PA0001, P-PA0002]', flags: '[Q9]'}" in txt3,
          "surgical: new key inserted at canonical slot (flags last)")

    # ---- 9b. nested-paren header vitals (spec/structured-dates Spec 04) ---- #
    # Vault headers nest a parenthetical inside the vitals. A first-')' scan
    # truncates at the INNER close, hiding everything after it — in practice the
    # whole death date. Measured on the live vault: balanced capture + the ')'
    # terminator gained 16 real death dates, changed 0, lost 0.
    nested = ps._vitals_paren("Gideon Example", " (b. 3 SEP 1780 (FS XXXX-XXX + a book p.61; "
                              "alternate 5 SEP 1780), Boston, Mass. — a long note. "
                              "d. between 1816 and 13 FEB 1823, likely at sea)")
    nb, nd = ps._parse_vitals(nested)
    # born runs to the ';' and so carries trailing citation prose — pre-existing
    # behaviour, and exactly what happens on the live vault; gdate strips it.
    check(nb.startswith("3 SEP 1780") and gdate.normalise(nb)[0] == "3 SEP 1780",
          f"nested paren: born read past the inner '(' and normalises clean (got {nb!r})")
    check(nd.startswith("between 1816 and 13 FEB 1823"),
          f"nested paren: died is no longer hidden by the inner ')' (got {nd[:40]!r})")
    check(gdate.normalise(nd)[0] == "BET 1816 AND 13 FEB 1823",
          "nested paren: the recovered died normalises to the Spec 04 spot-check value")
    # the pairing: a ')' INSIDE the born segment must not kill the born match
    pb, pd = ps._parse_vitals(ps._vitals_paren(
        "Minnie Example", " (b. 5 FEB 1871, Gloucester (Barton St Mary), d. 25 MAY 1934, Weymouth)"))
    check(pb == "5 FEB 1871, Gloucester (Barton St Mary" and pd.startswith("25 MAY 1934"),
          f"nested paren: born survives an inner ')' AND died is still found (got {pb!r} / {pd!r})")

    # ---- 10. structured date keys (spec/structured-dates Spec 03) --------- #
    vd = make_dates_vault()
    df = os.path.join(vd, "Family_Tree_Dates.md")
    before = open(df).read()
    dpeople = {r.id: r for r in ps.iter_people(vd)}

    # read: the meta FIELD is authoritative; the header is the fallback and stays
    # available for the Spec 06 DATE_DRIFT comparison.
    fielded = dpeople["P-DATE01"]
    check(fielded.born == "3 SEP 1780" and fielded.died == "BET 1816 AND 13 FEB 1823",
          "date keys: meta born/died read as the record's value")
    check(fielded.raw["header_vitals"] == ("3 SEP 1780, Somewhereton", None),
          "date keys: the header parenthetical stays in raw['header_vitals']")
    dual = dpeople["P-DATE02"]
    check(dual.born == "JULIAN 30 JAN 1649" and dual.born_phrase == "30 January 1648/49",
          "date keys: born_phrase (the GEDCOM 7 PHRASE escape hatch) is read")
    legacy = dpeople["P-DATE03"]
    check(legacy.born == "1969, Somewhereton, MA" and legacy.raw["meta_date_keys"] == (),
          "date keys: with no meta date key, born still falls back to the header")

    # no-op write is byte-identical, for entries with AND without date keys
    for r in dpeople.values():
        ps.write_person(vd, r)
    check(open(df).read() == before, "date keys: no-op write is BYTE-IDENTICAL")

    # THE regression this rule exists for: an unrelated write must NOT promote a
    # header-derived value into a meta date key. Otherwise one `mint_ids --apply`
    # silently migrates the whole vault to values scraped out of prose.
    legacy2 = {r.id: r for r in ps.iter_people(vd)}["P-DATE03"]
    legacy2.profile_status = "partial"
    ps.write_person(vd, legacy2)
    line = [ln for ln in open(df).read().split("\n") if "P-DATE03" in ln][0]
    check("born:" not in line and "profile_status: partial" in line,
          "date keys: an unrelated write does NOT promote the header into a meta field")

    # a deliberate set DOES write, quoted, at its canonical slot
    legacy3 = {r.id: r for r in ps.iter_people(vd)}["P-DATE03"]
    legacy3.born = "ABT 1969"
    ps.write_person(vd, legacy3)
    line = [ln for ln in open(df).read().split("\n") if "P-DATE03" in ln][0]
    check("born: 'ABT 1969'" in line, "date keys: a deliberate set is written, single-quoted")
    check(line.index("born:") > line.index("generation:"),
          "date keys: born lands at its canonical slot (after generation/fs)")

    # an invalid value is a CLEAR ERROR, not a silent drop
    bad = {r.id: r for r in ps.iter_people(vd)}["P-DATE01"]
    bad.born = "sometime in the 1780s"
    try:
        ps.write_person(vd, bad)
        check(False, "date keys: invalid value raises InvalidDateValue")
    except ps.InvalidDateValue as exc:
        check("not a valid GEDCOM 7 DateValue" in str(exc),
              "date keys: invalid value raises InvalidDateValue with a clear message")
    # …and the phrase key is free text, so it is NOT grammar-checked
    okp = {r.id: r for r in ps.iter_people(vd)}["P-DATE01"]
    okp.died_phrase = "sometime after the fire"
    ps.write_person(vd, okp)
    check("died_phrase: 'sometime after the fire'" in open(df).read(),
          "date keys: *_phrase is free text (a PHRASE is exactly that) and is not grammar-checked")

    # file model: the same four keys, surgically
    vdf = make_dates_file_vault()
    pf = os.path.join(vdf, "Dated.md")
    fbefore = open(pf).read()
    frec = {r.id: r for r in ps.iter_people(vdf)}["P-FILE01"]
    check((frec.born, frec.born_phrase) == ("JULIAN 30 JAN 1649", "30 January 1648/49"),
          "file model: born/born_phrase read from frontmatter")
    ps.write_person(vdf, frec)
    check(open(pf).read() == fbefore, "file model: no-op write with date keys is BYTE-IDENTICAL")
    frec.died = "ABT 1700"
    ps.write_person(vdf, frec)
    check("died: ABT 1700" in open(pf).read(), "file model: changed date key written")
    frec2 = {r.id: r for r in ps.iter_people(vdf)}["P-FILE01"]
    frec2.born = "not a date at all"
    try:
        ps.write_person(vdf, frec2)
        check(False, "file model: invalid value raises")
    except ps.InvalidDateValue:
        check(True, "file model: invalid value raises InvalidDateValue")

    # narrative -> file -> narrative preserves all four keys
    import convert_person_model as CPM
    recs = list(ps.NarrativeBackend.iter_people(vd))
    d_f = tempfile.mkdtemp()
    CPM.write_file_model(d_f, recs, apply=True)
    with open(os.path.join(d_f, ".autoresearch.json"), "w") as fh:
        json.dump({"person_model": "file"}, fh)
    vault_config.load_config.cache_clear()
    back = {r.id: r for r in ps.iter_people(d_f)}
    rt = back["P-DATE02"]
    check((rt.born, rt.born_phrase) == ("JULIAN 30 JAN 1649", "30 January 1648/49"),
          "narrative -> file: all four date keys survive")
    d_n = tempfile.mkdtemp()
    CPM.write_narrative_model(d_n, list(back.values()), apply=True)
    ntext = open(os.path.join(d_n, "Family_Tree_Converted.md")).read()
    check("born: 'JULIAN 30 JAN 1649'" in ntext and "born_phrase: '30 January 1648/49'" in ntext,
          "narrative -> file -> narrative: the date FIELD round-trips into the meta block")
    check("born: '1969, Somewhereton, MA'" not in ntext,
          "file -> narrative: legacy PROSE is not promoted into a meta date key "
          "(it stays header display; converting it is Spec 04's job)")

    for dd in (vd, vdf, d_f, d_n):
        shutil.rmtree(dd)

    for dd in (vn2, v2, d1, d2, vp, clean, vs):
        shutil.rmtree(dd)
    shutil.rmtree(v); shutil.rmtree(vn)
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
