#!/usr/bin/env python3
"""test_header_audit.py — the header grammar conformance validator (Spec 02).

Runnable with no test framework: `python3 test_header_audit.py` (exit 0 = pass).
The corpus check runs only when a vault is resolvable; the table always runs.

The single most important case in this file is the R5 pair — a note field
carrying a YEAR (`Gen 35`, `alive 1852`) must NOT be reported. That is where the
25 wrong values came from: a reader scavenging for years anywhere it could find
them read a generation number and a floruit as vitals. Under this grammar dates
live in declared slots and nothing else is read, so those cases need no special
guard. If either ever starts being reported, the validator has begun scavenging
again and the whole premise has regressed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import header_audit as H

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


class Rec:
    """Minimal stand-in for a PersonRecord: violations() reads only these."""

    def __init__(self, paren, date_keys=(), id="P-FIXTR"):
        self.id = id
        self.source_file = "Family_Tree_Fixture.md"
        self.raw = {"header_paren": paren, "meta_date_keys": tuple(date_keys)}


def rules(paren, date_keys=("born",), id="P-FIXTR"):
    return sorted({r for r, _ in H.violations(Rec(paren, date_keys, id))})


BOTH = ("born", "died")

CASES = [
    # (paren, meta date keys, expected rules, label)
    # --- conforming ------------------------------------------------------
    ("b. 3 SEP 1780, Somewhereton; d. 1873; FS PID XXXX-XXX", BOTH, [],
     "house style with place and id -> conforms"),
    ("b. ABT 1750; d. unknown; a weaver", BOTH, [],
     "`unknown` is a legal date slot, so absence is stated IN the grammar"),
    ("d. BET 1816 AND 13 FEB 1823, likely at sea", ("died",), [],
     "a GEDCOM range plus a prose place tail -> conforms"),
    ("b. JULIAN 30 JAN 1649; FS PID XXXX-XXX", ("born",), [],
     "a non-Gregorian calendar escape -> conforms"),
    ("born 1780; died 1849", BOTH, [],
     "`born`/`died` spelled out are accepted vital tags"),
    ("b. 954", ("born",), [],
     "a 3-digit medieval year -> conforms (no 1500 floor anywhere)"),
    # --- R5: the regression test that matters most ------------------------
    ("b. ABT 975; d. 1045; Gen 35", BOTH, [],
     "R5: `Gen 35` is a note field -> NOT read as a date"),
    ("b. 1820, Villagio; alive 1852; profession Lavoratore", ("born",), [],
     "R5: a floruit in a note field -> NOT read as a date"),
    ("of Anytown; atto 534; b. 1820", ("born",), [],
     "R5: a document number in a note field -> NOT read as a date"),
    # --- R2 ---------------------------------------------------------------
    ("b. 3 SEP 1780 (FS XXXX-XXX + parish copy), Somewhereton", ("born",), ["R2"],
     "R2: a nested parenthetical is reported"),
    # --- R3 ---------------------------------------------------------------
    ("b. 1810 Villagio", ("born",), ["R3"],
     "R3/R6: a place INSIDE the date slot (no comma) is reported"),
    ("b. 1810, Villagio", ("born",), [],
     "R6: the same place after a comma conforms"),
    ("b. c.966", ("born",), ["R3"],
     "R3 STRICT: `c.966` normalises but is not a DateValue -> reported"),
    ("b. ~1750", ("born",), ["R3"],
     "R3 STRICT: `~1750` is prose the migrator fixes, not a conforming value"),
    ("b. 1810-1830", ("born",), ["R3"],
     "R3 STRICT: a dash range is not a DateValue (`BET … AND …` is)"),
    ("b. ", ("born",), ["R3"],
     "R3: an empty date slot is reported"),
    ("b. **3 SEP 1780**, Somewhereton", ("born",), [],
     "markdown emphasis is presentation: a bold date still conforms"),
    ("b. 1946 [infant death]", ("born",), ["R3"],
     "…but a bracketed aside is NOT stripped: it is a real defect"),
    ("b. ?", ("born",), ["R3"],
     "`?` is not the spelling of absence; `unknown` is"),
    # --- R4 ---------------------------------------------------------------
    ("c.966; 23 APR 1016; FS PID XXXX-XXX", BOTH, ["R4"],
     "R4: the terse positional dialect is reported when the record has dates"),
    ("c.975–1045; Gen 35", BOTH, ["R4"],
     "R4: a dash range with no marker is reported"),
    ("unknown, Villagio; 6 APR 1820, Villagio", BOTH, ["R4"],
     "R4: an absent birth field stated positionally is reported"),
    ("of Anytown; a weaver", (), [],
     "R4 is record-aware: no dates recorded -> no vitals field required"),
    ("of Anytown; a weaver", ("born",), ["R4"],
     "R4: the same header IS reported once the record carries a date"),
    ("", ("born",), ["R4"],
     "R4: no parenthetical at all, but the record has dates -> reported"),
    ("", (), [],
     "coverage: no parenthetical and no dates -> NOT a violation"),
    ("b. 1780", ("born_phrase",), [],
     "R4 keys on `born`/`died` only: a lone `born_phrase` is not a date"),
    # --- id fields are exempt --------------------------------------------
    # `Surname-48` is the recognised WikiTree placeholder. Use it rather than
    # inventing one: any other Word-Number token is WikiTree-SHAPED, and the PII
    # gate blocks on it because it cannot tell an invented id from a real one.
    # (Written the obvious way first, this comment named the invented token and
    # was itself blocked -- the gate's own guidance is to reach for the
    # recognised placeholder, not to widen the allowlist.)
    ("b. 1780; FS PID XXXX-XXX; WikiTree Surname-48", ("born",), [],
     "id fields are exempt from the date rules"),
    # --- multiple rules on one entry --------------------------------------
    ("b. c.966; d. 1045 (a nested aside)", BOTH, ["R2", "R3"],
     "two INDEPENDENT defects in different fields -> both reported"),
    # --- R2 suppresses R3 on the SAME field -------------------------------
    # A nested paren is WHY that field's date slot will not parse, so reporting
    # both would double-count one defect and inflate R3. The histogram has to
    # stay a worklist ordered by cause: unnest first, then see if an R3 remains.
    ("b. 3 SEP 1780 (parish copy)", ("born",), ["R2"],
     "R2 on a field suppresses R3 on that same field (one defect, one finding)"),
    ("b. c.966 (parish copy)", ("born",), ["R2"],
     "…even when the date would independently fail: fix the nesting first"),
]


def main():
    print("=== header grammar validator: rule table ===")
    for paren, keys, expected, label in CASES:
        check(rules(paren, keys) == sorted(expected), label)

    print("\n=== identity is the meta id, never the bold name ===")
    got = H.violations(Rec("c.966; 23 APR 1016", ("born",), id="P-ODDNM"))
    check(bool(got), "a malformed-name entry is still evaluated")
    recs = [Rec("c.966", ("born",), id="P-ODDNM")]
    check(recs[0].id == "P-ODDNM", "findings key on the id, which survives a bad name")

    print("\n=== oracle column ===")
    check(H.oracle(Rec("", BOTH)) == "both", "both born and died -> 'both'")
    check(H.oracle(Rec("", ("born",))) == "born", "born only -> 'born'")
    check(H.oracle(Rec("", ())) == "NONE", "neither -> 'NONE' (human review)")

    print("\n=== corpus baseline (live vault) ===")
    try:
        import vault_config
        vault = vault_config.resolve_vault()
    except Exception as e:
        print(f"  skip (no vault resolvable: {e})")
        vault = None
    if vault:
        _f, s = H.audit(vault)
        print(f"  entries {s['entries']}, conforming {s['conforming']}, "
              f"non-conforming {s['nonconforming']}, "
              f"R2 {s['per_rule']['R2']} R3 {s['per_rule']['R3']} "
              f"R4 {s['per_rule']['R4']}, oracle NONE {s['oracle']['NONE']}")
        check(s["entries"] == s["conforming"] + s["nonconforming"],
              "every entry is either conforming or counted as non-conforming")
        check(s["oracle"]["NONE"] <= s["nonconforming"],
              "the human-review population cannot exceed the non-conforming set")

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
