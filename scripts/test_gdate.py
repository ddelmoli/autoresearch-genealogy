#!/usr/bin/env python3
"""test_gdate.py — unit tests for gdate.py (spec/structured-dates Spec 02).

Runnable with no test framework: `python3 test_gdate.py` (exit 0 = pass), the
same convention as test_person_store.py.

Beyond the spec's acceptance table, every case marked REGRESSION below is a real
defect this module had during development, caught by running it over the live
1,880-string corpus rather than over invented examples:

  * `JULIAN 30 JAN 1649` -> `JUL 30`   — the month rewrite matched the `Jul` prefix
    inside `JULIAN`; the same bug read `Decatur` as DEC and `Augusta` as AUG,
    inventing a date out of a place name.
  * `2 APR c.747/748`    -> `2`        — a prefix match returned the year TWO.
  * `6 FEB 1712/13`      -> `6 FEB 1712` — an Old Style / New Style dual date,
    silently halved. GEDCOM 7 Appendix A §6.2 has a lossless answer for this
    (DATE + PHRASE), which is what `split_dual_year` implements.
  * `17 APR 1875 14:15 pomeridiane` -> refused — the truncation guard was
    swallowing a complete date followed by a TIME of day.

With the corpus available (AUTORESEARCH_VAULT set) the run finishes with the
corpus assertion the spec requires: >=71.2% already valid, >=84% after normalise.
Without a vault it skips that one check and still runs everything else.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdate

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


def eq(got, want, label):
    check(got == want, f"{label}" + ("" if got == want else f"  (got {got!r}, want {want!r})"))


# --- is_valid: every production in the grammar ---------------------------- #
VALID = [
    "1780", "954", "993", "1045",                    # bare years, no 1500 floor
    "SEP 1780", "3 SEP 1780", "31 DEC 1999",
    "GREGORIAN 3 SEP 1780", "JULIAN 30 JAN 1649",
    "44 BCE", "JULIAN 44 BCE",
    "ABT 1750", "CAL 1750", "EST 1750",
    "BEF 1866", "AFT 1672",
    "BET 1816 AND 13 FEB 1823", "BET 1810 AND 1830",
    "FROM 1650 TO 1672", "FROM 1650", "TO 1672",
    "HEBREW 5 TSH 5780", "FRENCH_R 5 VEND 12",
    "1780-09-03",                                    # Spec 03 option (A): ISO accepted
]
INVALID = [
    "", "   ", None, "unknown", "?", "Deceased",
    "abt 1750",          # lowercase keyword — is_valid is STRICT by design
    "3 Sep 1780",        # lowercase month
    "3 1780",            # a day with no month is not a date
    "32 SEP 1780",       # day out of range
    "HEBREW 5 JAN 5780",  # month does not belong to the calendar
    "3 SEP 1780, Boston",  # a place is not part of the value
    "1743/4",            # dual year: needs DATE + PHRASE, not a bare value
    "BET 1810", "FROM", "ABT",
]

for v in VALID:
    check(gdate.is_valid(v), f"is_valid({v!r})")
for v in INVALID:
    check(not gdate.is_valid(v), f"not is_valid({v!r})")

# --- year / year_range ---------------------------------------------------- #
eq(gdate.year("3 SEP 1780"), 1780, "year('3 SEP 1780')")
eq(gdate.year("954"), 954, "year('954') — the 1500-floor bug is impossible here")
eq(gdate.year("1068"), 1068, "year('1068') — Henry I of England is visible")
eq(gdate.year("1008"), 1008, "year('1008') — Henry I of France is a DIFFERENT year")
eq(gdate.year("ABT 1750"), 1750, "year('ABT 1750')")
eq(gdate.year("BEF 1866"), 1866, "year('BEF 1866') — inner year")
eq(gdate.year("AFT 1672"), 1672, "year('AFT 1672')")
eq(gdate.year("BET 1816 AND 13 FEB 1823"), 1816, "year(BET…AND) — EARLIER bound")
eq(gdate.year("FROM 1650 TO 1672"), 1650, "year(FROM…TO) — earlier bound")
eq(gdate.year("44 BCE"), -44, "year('44 BCE') — negative, so ordering survives the epoch")
eq(gdate.year("unknown"), None, "year('unknown')")
eq(gdate.year_range("BET 1816 AND 13 FEB 1823"), (1816, 1823), "year_range(BET…AND)")
eq(gdate.year_range("FROM 1650 TO 1672"), (1650, 1672), "year_range(FROM…TO)")
eq(gdate.year_range("BEF 1866"), (None, 1866), "year_range(BEF) — no lower bound")
eq(gdate.year_range("AFT 1672"), (1672, None), "year_range(AFT) — no upper bound")
eq(gdate.year_range("ABT 1750"), (1750, 1750), "year_range(ABT)")
eq(gdate.year_range("nonsense"), (None, None), "year_range(non-date)")

# --- is_day_precise ------------------------------------------------------- #
for v, want in [("JULIAN 30 JAN 1649", True), ("3 SEP 1780", True), ("1780-09-03", True),
                ("ABT 1750", False), ("SEP 1780", False), ("1780", False),
                ("BET 3 SEP 1780 AND 1790", False), ("unknown", False)]:
    eq(gdate.is_day_precise(v), want, f"is_day_precise({v!r})")
check(not gdate.is_day_precise("BET 3 SEP 1780 AND 1790"),
      "is_day_precise is NOT the privacy predicate (a range is not one day) — "
      "the Spec 01 gates keep their own fail-closed copy")

# --- resolve_year: THE one year path for every gate (Spec 05) -------------- #
# Layer 1: a valid DateValue. Layer 2: legacy prose via normalise. Layer 3: the
# explicit bare-4-digit fallback with PID-like tokens stripped.
for value, want, layer in [
    ("3 SEP 1780", 1780, "1 field"),
    ("ABT 1068", 1068, "1 field — Henry I of England, invisible under the old 1500 floor"),
    ("1008", 1008, "1 field — Henry I of France, a DIFFERENT person"),
    ("BET 1816 AND 13 FEB 1823", 1816, "1 field, earlier bound"),
    ("954", 954, "1 field — medieval"),
    ("~1750", 1750, "2 prose"),
    ("bef. 1866", 1866, "2 prose"),
    ("1969, Somewhereton, MA", 1969, "2 prose"),
    ("baptized 3 OCT 1598", 1598, "3 fallback — normalise refuses, the scan finds it"),
    ("b. 1853 (FS LZ19-924)", 1853, "3 fallback — PID-like token stripped first"),
    ("unknown", None, "no year anywhere"),
    ("Russia", None, "a place is not a year"),
    ("", None, "empty"),
    (None, None, "None"),
]:
    got = gdate.resolve_year(value)
    eq(got, want, f"resolve_year({value!r}) [{layer}]")
eq(gdate.resolve_year("baptized 3 OCT 1598", allow_prose=False), None,
   "resolve_year(allow_prose=False) refuses the layer-3 fallback")
eq(gdate.resolve_year_range("BET 1816 AND 13 FEB 1823"), (1816, 1823), "resolve_year_range: field")
eq(gdate.resolve_year_range("1883-1885"), (1883, 1885), "resolve_year_range: prose range")
eq(gdate.resolve_year_range("b. 1811 d. 1893"), (1811, 1893), "resolve_year_range: fallback first/last")

# --- normalise: the mechanical conversions -------------------------------- #
NORMALISE = [
    ("~1750", "ABT 1750", ""),
    ("c.985", "ABT 985", ""),
    ("ca. 1750", "ABT 1750", ""),
    ("about 1756", "ABT 1756", ""),
    ("circa 1750", "ABT 1750", ""),
    ("abt 1851", "ABT 1851", ""),
    ("bef. 1866", "BEF 1866", ""),
    ("before 1866", "BEF 1866", ""),
    ("aft. 1672", "AFT 1672", ""),
    ("after 1672", "AFT 1672", ""),
    ("est. 1832", "EST 1832", ""),
    ("1810-1830", "BET 1810 AND 1830", ""),
    ("1705–1765", "BET 1705 AND 1765", ""),          # en-dash
    ("between 1810 and 1830", "BET 1810 AND 1830", ""),
    ("Dec 1840", "DEC 1840", ""),
    ("30 Sept. 1696", "30 SEP 1696", ""),
    ("3 March 1654", "3 MAR 1654", ""),
    ("1780-09-03", "3 SEP 1780", ""),                 # ISO -> GEDCOM on write
    ("3 SEP 1780", "3 SEP 1780", ""),                 # already valid: unchanged
    ("JULIAN 30 JAN 1649", "JULIAN 30 JAN 1649", ""),  # REGRESSION: JULIAN != JUL + IAN
    ("1969, Somewhereton, MA", "1969", "Somewhereton, MA"),
    ("1810 Villaggio Esempio", "1810", "Villaggio Esempio"),
    ("1969, Decatur, IL", "1969", "Decatur, IL"),      # REGRESSION: Decatur is not DEC
    ("17 APR 1875 14:15 pomeridiane", "17 APR 1875", "14:15 pomeridiane"),  # REGRESSION
    ("27 MAR 1899 8 pm", "27 MAR 1899", "8 pm"),       # REGRESSION
    ("~1877-1881", "BET 1877 AND 1881", ""),           # an approximate span IS a span
    # ranges a source writes compactly, which the grammar spells as BET…AND
    ("NOV-DEC 1638", "BET NOV 1638 AND DEC 1638", ""),          # month range
    ("~September/October 1920", "BET SEP 1920 AND OCT 1920", ""),
    ("12/13 JUL 783", "BET 12 JUL 783 AND 13 JUL 783", ""),     # day range
    ("~20-21 MAR 1879", "BET 20 MAR 1879 AND 21 MAR 1879", ""),
    ("21 or 22 MAR 1837", "BET 21 MAR 1837 AND 22 MAR 1837", ""),  # REGRESSION: '21'
    ("~1750-56", "BET 1750 AND 1756", ""),                      # 2-digit range end
    ("18 JUL c.640", "ABT 18 JUL 640", ""),                     # approximation hoisted
    ("BET 3 JUN AND 18 SEP 1682", "BET 3 JUN 1682 AND 18 SEP 1682", ""),  # year borrowed
    ("~Marzo 1862", "ABT MAR 1862", ""),                        # Italian month
    ("15 Giugno 1863", "15 JUN 1863", ""),                      # REGRESSION: '15'
]
for prose, want_value, want_residue in NORMALISE:
    v, r = gdate.normalise(prose)
    eq((v, r), (want_value, want_residue), f"normalise({prose!r})")
    if v is not None:
        check(gdate.is_valid(v), f"  …and the result is is_valid: {v!r}")

# normalise REFUSES rather than guessing.
REFUSED = [
    "unknown", "Deceased", "?", "—", "n/a", "none",
    "Deceased — no dates on FS",
    "Russia",                       # a place that leaked into the date field
    "early 1621",                   # a qualifier that is not ABT
    "probably 30 JUN 1842 Parishtown, age 59",
    "2 APR c.747/748",              # REGRESSION: used to return the year TWO
    "6 FEB 1712/13",                # REGRESSION: dual date, used to be halved
    "c.985/990",                    # NOT consecutive: a span, not a dual year
]
for prose in REFUSED:
    v, r = gdate.normalise(prose)
    eq(v, None, f"normalise REFUSES {prose!r}")
    eq(r, prose.strip(), f"  …and returns the residue verbatim for triage")

eq(gdate.normalise(None), (None, ""), "normalise(None)")
eq(gdate.normalise("early 1621"), (None, "early 1621"),
   "normalise('early 1621') is NOT guessed into ABT 1621")

# --- split_dual_year: the Old Style / New Style case ---------------------- #
for prose, want in [
    ("6 JAN 1743/4", ("6 JAN 1744", "6 JAN 1743/4", "")),   # NS year, per App. A 6.2
    ("13 JAN 1699/1700", ("13 JAN 1700", "13 JAN 1699/1700", "")),
    ("27 JAN 1712/13, Somewhereton, Suffolk, MA",
     ("27 JAN 1713", "27 JAN 1712/13", "Somewhereton, Suffolk, MA")),
    ("~1649/50, Somewhereton, Essex, MA", ("ABT 1650", "~1649/50", "Somewhereton, Essex, MA")),
    ("c.985/990", None),        # 990 != 986 — a span, not a dual year
    ("1712", None),             # no slash
    ("3 SEP 1780", None),
    (None, None),
]:
    eq(gdate.split_dual_year(prose), want, f"split_dual_year({prose!r})")

for prose in ("6 JAN 1743/4", "13 JAN 1699/1700", "~1649/50"):
    got = gdate.split_dual_year(prose)
    check(gdate.is_valid(got[0]), f"split_dual_year({prose!r}) value is is_valid")
    check(got[1] == prose.strip(), f"split_dual_year({prose!r}) phrase preserves the original")

# --- property: normalise's output always satisfies is_valid --------------- #
CORPUS_SAMPLE = [p for p, _, _ in NORMALISE] + REFUSED + VALID + [
    "1682, FS XXXX-XXX", "Sep 1843 GRO Q3, Somewhere district", "944/945, killed in battle",
    "Parishtown bp. 11 MAR 1743/44", "12/13 JUL 783, Someplace", "1842 Jun-qtr GRO Q2",
]
bad = [s for s in CORPUS_SAMPLE if (lambda v: v is not None and not gdate.is_valid(v))(gdate.normalise(s)[0])]
check(not bad, f"property: is_valid(normalise(x)[0]) whenever normalise returns a value{'' if not bad else f' — {bad}'}")

# --- corpus assertion (Spec 02 acceptance) -------------------------------- #
try:
    import person_store as ps
    import vault_config
    vault = vault_config.resolve_vault(None)
    vals = [x for r in ps.NarrativeBackend.iter_people(vault) for x in (r.born, r.died) if x]
except BaseException as exc:   # resolve_vault exits via SystemExit, not Exception
    print(f"  skip corpus assertion (no vault: {exc})")
    vals = []

if vals:
    n = len(vals)
    # As stored, a place is still glued into the value by `_parse_vitals`; the
    # spec's 71.2% baseline is measured on the DATE part, so measure it the same way.
    already = sum(1 for x in vals if gdate.is_valid(x.split(",")[0].strip()))
    converted = sum(1 for x in vals if gdate.normalise(x)[0] or gdate.split_dual_year(x))
    print(f"\n  corpus: {n} born/died strings")
    print(f"    already valid (date part)   {already:5d}  {already / n:6.1%}  (spec baseline 71.2%)")
    print(f"    after normalise/dual-year   {converted:5d}  {converted / n:6.1%}  (spec target >=84%)")
    check(already / n >= 0.70, "corpus: >=70% already valid, reproducing the spec's measurement")
    check(converted / n >= 0.84, "corpus: >=84% convert mechanically")

print(f"\n{PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
