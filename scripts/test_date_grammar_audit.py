"""Pin DATE_GRAMMAR to the STORED field, never the record attribute.

⭐⭐ THIS IS THE WHOLE POINT OF THE GATE AND IT IS ONE LINE WIDE. On the narrative
model `PersonRecord.born` FALLS BACK to the header parenthetical when no meta key
exists, so `getattr(rec, 'born')` returns header TEXT under a different grammar.
Q338 measured that attribute, reported **309 stored fields breaking the date rules**,
and specced a bulk key delete for 271 of them. Re-measured with two independent
readers: the vault stores 2,322 date fields and **not one is invalid**. Every one of
the 306 was header text, and the two big classes are LEGAL in a header -- the literal
`unknown` is named by the header grammar, and the place is there because the header
grammar is `date, place`.

So the pins below are mostly NEGATIVE, and that is deliberate: a gate that widens to
the attribute would report 306 findings on a clean vault, and 306 findings that are
all correct-by-design is how a gate gets ignored.

The second pin is `classify_header` asking VALIDITY FIRST. Most header values are
ordinary dates with no meta key beside them; classifying before validating put
`26 OCT 899` in the unparsed-residue list, which is the one list in this tool a
human is asked to read.
"""
import os
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import date_grammar_audit as DGA  # noqa: E402
import gdate  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(label)


def vault_with(entry):
    """A scratch narrative vault holding one entry. See test_manifest_audit for why
    the person_model declaration is not optional."""
    d = tempfile.mkdtemp()
    open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8").write(
        '{"person_model": "narrative"}')
    open(os.path.join(d, "Family_Tree_Scratch.md"), "w", encoding="utf-8").write(
        "### Generation 9: Placeholder\n\n" + entry)
    return d


def findings(entry):
    v = vault_with(entry)
    return [(k, val) for _r, k, val in DGA.stored_date_fields(v) if not gdate.is_valid(val)]


def stored_count(entry):
    return len(list(DGA.stored_date_fields(vault_with(entry))))


HDR_UNKNOWN = "**Placeholder One** (b. 1700; d. unknown)\n"
HDR_PLACE = "**Placeholder Two** (b. 16 AUG 1646, Somewhereton, MA; d. 1700)\n"

print("A header-only value is NOT a stored field and is NOT a finding:")
check("header `d. unknown`, no meta date key",
      findings(HDR_UNKNOWN + "- meta: {id: P-TEST01, generation: 9}\n"), [])
check("header `date, place`, no meta date key",
      findings(HDR_PLACE + "- meta: {id: P-TEST02, generation: 9}\n"), [])
check("neither is even COUNTED as a stored field",
      stored_count(HDR_UNKNOWN + "- meta: {id: P-TEST01, generation: 9}\n"), 0)

print("\nA stored field IS checked, and a valid one passes:")
check("stored valid dates",
      findings("**Placeholder Three** (b. 1700; d. 1750)\n"
               "- meta: {id: P-TEST03, generation: 9, born: '1700', died: 'ABT 1750'}\n"), [])
check("both stored fields counted",
      stored_count("**Placeholder Three** (b. 1700; d. 1750)\n"
                   "- meta: {id: P-TEST03, generation: 9, born: '1700', died: 'ABT 1750'}\n"), 2)

print("\n⛔ A genuinely invalid STORED value IS a finding (what the gate is for):")
check("stored literal unknown",
      findings("**Placeholder Four** (b. 1700; d. unknown)\n"
               "- meta: {id: P-TEST04, generation: 9, died: 'unknown'}\n"),
      [("died", "unknown")])
check("stored place inside the date",
      findings("**Placeholder Five** (b. 1969, Somewhereton; d. 2000)\n"
               "- meta: {id: P-TEST05, generation: 9, born: '1969, Somewhereton, MA'}\n"),
      [("born", "1969, Somewhereton, MA")])
check("stored lowercase keyword (is_valid is STRICT)",
      findings("**Placeholder Six** (b. ABT 1700; d. 1750)\n"
               "- meta: {id: P-TEST06, generation: 9, born: 'abt 1700'}\n"),
      [("born", "abt 1700")])

print("\n⭐ How the year-based gates miss these — and the two classes miss DIFFERENTLY:")
print("   a place-bearing value yields a plausible YEAR, so DATE_DRIFT compares it")
print("   and MATCHES; the literal `unknown` yields no year at all, so those gates")
print("   SKIP the row. Wrongly passed vs never examined -- both invisible, and the")
print("   first is the worse of the two.")
for bad in ["1969, Somewhereton, MA", ". 16 AUG 1646, Somewhereton, MA"]:
    check(f"invalid but resolve_year answers: {bad!r}",
          gdate.resolve_year(bad) is not None and not gdate.is_valid(bad), True)
check("`unknown` yields NO year (skipped, not passed)", gdate.resolve_year("unknown"), None)
check("`unknown` is still invalid", gdate.is_valid("unknown"), False)

print("\nclassify_header asks VALIDITY FIRST:")
check("a plain date is VALID, not residue", DGA.classify_header("26 OCT 899"), "VALID")
check("an approximate date is VALID", DGA.classify_header("ABT 1788"), "VALID")
check("the legal literal", DGA.classify_header("unknown"), "LEGAL_UNKNOWN")
check("date + place", DGA.classify_header("16 AUG 1646, Somewhereton, MA"), "HEADER_DATE_PLACE")
check("free prose IS residue", DGA.classify_header("young"), "UNPARSED")

print()
if FAILED:
    print(f"FAILED ({len(FAILED)}): " + "; ".join(FAILED))
    sys.exit(1)
print("All date_grammar_audit pins pass.")
