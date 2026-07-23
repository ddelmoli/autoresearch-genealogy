#!/usr/bin/env python3
"""test_migrate_headers.py — Phase A (R3) header migration, spec/header-grammar 04.

Runnable with no test framework: `python3 test_migrate_headers.py` (exit 0 = pass).

THE INVARIANT UNDER TEST: no date value changes, and no non-date content is lost.
The second half is not decoration. The FIRST dry run of this tool proposed

    "b. ~1799 Staffordshire"              -> "b. ABT 1799"
    "b. Sep 1843 [GRO Q3], Bristol …"     -> "b. SEP 1843, Bristol …"

deleting a place and a source reference while every DATE stayed identical — which
is precisely how a rewrite mangles entries while passing a date-only check. The
residue guard and `content_preserved` exist because of those measured cases, and
these tests pin them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdate as G
import migrate_headers as M

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
    def __init__(self, paren, born=None, died=None, id="P-FIXTR"):
        self.id = id
        self.source_file = "Family_Tree_Fixture.md"
        self.born = born
        self.died = died
        keys = tuple(k for k, val in (("born", born), ("died", died)) if val)
        self.raw = {"header_paren": paren, "meta_date_keys": keys}


def proposals(paren, born=None, died=None):
    p, r = M.propose_r3(Rec(paren, born, died))
    return [(a, b) for a, b, _n in p], [why for _f, why in r]


# (paren, born, died, expected new field or None if it must be REFUSED, label)
CASES = [
    ("b. ~1750, Villagio", "ABT 1750", None, "b. ABT 1750, Villagio",
     "tilde approximation -> ABT, place preserved"),
    ("b. c.966", "ABT 966", None, "b. ABT 966",
     "c. approximation -> ABT (medieval, no 1500 floor)"),
    ("b. bef. 9 OCT 1774, Minchinhampton", "BEF 9 OCT 1774", None,
     "b. BEF 9 OCT 1774, Minchinhampton", "bef. -> BEF, multi-word place kept"),
    ("d. Dec 1840, Somewhereton", None, "DEC 1840", "d. DEC 1840, Somewhereton",
     "month case normalised"),
    ("d. bet. 9 JUL 1744 and 3 MAR 1747, Anytown", None, "BET 9 JUL 1744 AND 3 MAR 1747",
     "d. BET 9 JUL 1744 AND 3 MAR 1747, Anytown", "bet…and -> BET…AND"),
    ("b. **20 Feb 1853**, Somewhereton", "20 FEB 1853", None,
     "b. 20 FEB 1853, Somewhereton", "markdown emphasis dropped from the slot only"),
    # --- the refusals that matter -----------------------------------------
    ("b. ~1799 Staffordshire", "ABT 1799", None, None,
     "REFUSE: a place with no comma would be DELETED by normalise"),
    ("b. Sep 1843 [GRO Q3], Bristol district", "SEP 1843", None, None,
     "REFUSE: a bracketed source reference is residue, not a date"),
    ("b. unknown", None, None, None,
     "an absence marker is already conforming -> no proposal, no refusal"),
    ("b. 3 SEP 1780, Somewhereton", "3 SEP 1780", None, None,
     "an already-conforming field is left alone"),
]


def main():
    print("=== Phase A proposals ===")
    for paren, born, died, expected, label in CASES:
        props, refs = proposals(paren, born, died)
        if expected is None:
            check(not props, label)
        else:
            check(len(props) == 1 and props[0][1] == expected,
                  f"{label}  -> {props[0][1] if props else refs}")

    print("\n=== the residue guard (the silent-deletion class) ===")
    for slot in ("~1799 Staffordshire", 'Sep 1843 [GRO Q3]',
                 '9 SEP 1764 "Mary Wix," Horsley'):
        value, residue = G.normalise(slot)
        check(bool(value) and bool(residue.strip()),
              f"normalise reports residue for {slot!r} — ignoring it deletes content")
        props, _r = proposals(f"b. {slot}")
        check(not props, f"…and propose_r3 REFUSES rather than dropping it")

    print("\n=== content_preserved ===")
    check(M.content_preserved("b. ~1750, Villagio", "b. ABT 1750, Villagio"),
          "pure notation change passes")
    check(not M.content_preserved("b. ~1799 Staffordshire", "b. ABT 1799"),
          "a dropped place is caught")
    check(not M.content_preserved("b. 1843, Bristol", "b. 1843"),
          "a dropped comma-place is caught")

    print("\n=== the oracle ===")
    r = Rec("b. ~1750", born="ABT 1650")
    check(M.check_oracle(r, "b", "ABT 1750") is not None,
          "a header/field year disagreement is refused, not written")
    check(M.check_oracle(Rec("b. ~1750", born="ABT 1750"), "b", "ABT 1750") is None,
          "agreement passes")
    check(M.check_oracle(Rec("b. ~1750"), "b", "ABT 1750") is None,
          "no field = no oracle = not a disagreement")

    print("\n=== idempotence + line rewriting ===")
    line = "**Jane Example Ancestor** (b. ~1750, Villagio; d. 1800; FS PID XXXX-XXX)"
    props, _r = proposals("b. ~1750, Villagio; d. 1800; FS PID XXXX-XXX", "ABT 1750", "1800")
    once = M.migrate_line(line, [(a, b, "") for a, b in props])
    check(once == "**Jane Example Ancestor** (b. ABT 1750, Villagio; d. 1800; FS PID XXXX-XXX)",
          "only the date slot changes; the rest of the line is byte-identical")
    again, _r2 = proposals("b. ABT 1750, Villagio; d. 1800; FS PID XXXX-XXX", "ABT 1750", "1800")
    check(not again, "re-running on a migrated header proposes nothing (idempotent)")

    print("\n=== corpus property: EVERY proposal preserves year + content ===")
    try:
        import vault_config
        vault = vault_config.resolve_vault()
    except Exception as e:
        print(f"  skip (no vault: {e})")
        vault = None
    if vault:
        plans, refusals = M.run(vault)
        bad_year = bad_content = 0
        fields = 0
        for _rel, _rec, props in plans:
            for old, new, _n in props:
                fields += 1
                o = M.H.VITAL_TAG.match(old).group(2)
                n = M.H.VITAL_TAG.match(new).group(2)
                od, _p = M._split_place(M.H.EMPHASIS.sub("", o).strip())
                nd, _p2 = M._split_place(n)
                if G.resolve_year(od) != G.year(nd):
                    bad_year += 1
                if not M.content_preserved(old, new):
                    bad_content += 1
                if not G.is_valid(nd):
                    bad_content += 1
        print(f"  {len(plans)} entries, {fields} fields, {len(refusals)} refusals")
        check(bad_year == 0, "no proposal changes a YEAR (checked exhaustively)")
        check(bad_content == 0,
              "no proposal loses content or yields an invalid DateValue")

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
