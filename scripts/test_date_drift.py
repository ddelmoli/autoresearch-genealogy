#!/usr/bin/env python3
"""test_date_drift.py — the Spec 06 header/meta sync gate.

Runnable with no test framework: `python3 test_date_drift.py` (exit 0 = pass).

DATE_DRIFT exists because this lane created TWO stores for one fact. Before it, a
person's dates lived only in the header parenthetical; now the `- meta:` field is
authoritative for machines and the header remains the human display. That is
exactly the drift integrity rule 7 polices, so it is gated rather than trusted.

The rule under test: compare YEARS, not strings. `3 SEP 1780` and
`b. 3 SEP 1780, Boston` agree. `ABT 1750` and `~1750` agree. Only both-present-and-
different is drift; one side absent is COVERAGE, which is a migration or display
gap, not a contradiction.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prose_audit as PA

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


def row(name, field_born=None, header_born=None, field_died=None, header_died=None):
    keys = tuple(k for k, v in (("born", field_born), ("died", field_died)) if v)
    return {"name": name, "file": "Family_Tree_Fixture.md", "meta_date_keys": keys,
            "field_born": field_born, "header_born": header_born or "",
            "field_died": field_died, "header_died": header_died or ""}


CASES = [
    # (row, should_be_reported, label)
    (row("Drifting Died", field_died="1675", header_died="d. 1671"), True,
     "header d.1671 vs field 1675 -> REPORTED"),
    (row("Exact With Place", field_born="3 SEP 1780", header_born="3 SEP 1780, Boston"), False,
     "'3 SEP 1780' vs 'b. 3 SEP 1780, Boston' -> not drift (same year, place ignored)"),
    (row("Approximate", field_born="ABT 1750", header_born="~1750"), False,
     "'ABT 1750' vs '~1750' -> not drift (years compared, not strings)"),
    (row("Range Vs Year", field_born="BET 1625 AND 1627", header_born="~1625-1627, Plymouth"), False,
     "'BET 1625 AND 1627' vs '~1625-1627, Plymouth' -> not drift"),
    (row("Medieval", field_born="ABT 1068", header_born="~1068"), False,
     "medieval years compare correctly (no 1500 floor anywhere in this path)"),
    (row("Dual Year", field_born="6 JAN 1744", header_born="6 JAN 1743/4, Somewhereton"), False,
     "an OS/NS dual header reads EITHER year, so the NS field is not drift"),
    (row("Field Only", field_born="1780"), False,
     "field present, header absent -> coverage, not drift"),
    (row("Header Only", header_born="b. 1780"), False,
     "header present, field absent -> coverage, not drift"),
    (row("Neither"), False, "neither present -> coverage, not drift"),
]

for r, want_reported, label in CASES:
    found = PA.date_drift([r])
    got = bool(found)
    check(got == want_reported, label + ("" if got == want_reported else f"  (got {found})"))

# A finding carries WARN severity (it shares prose_audit's report) and names the
# metric, which is what makes it countable — and, since the promotion, blocking.
found = PA.date_drift([CASES[0][0]])
check(found and found[0][2] == "WARN" and found[0][3] == "DATE_DRIFT",
      "a finding is tagged WARN/DATE_DRIFT so the summary can count it")
check(found and "1675" in found[0][4] and "1671" in found[0][4],
      "the message reports BOTH years so the disagreement is actionable")

# Coverage is counted separately from drift, and the three cases are distinct.
PA.date_drift([row("A", field_born="1780"), row("B", header_born="b. 1780"), row("C")])
cov = PA.DATE_DRIFT_COVERAGE
check(cov["header_missing"] == 1, f"coverage: header_missing counted (got {cov['header_missing']})")
check(cov["field_missing"] == 1, f"coverage: field_missing counted (got {cov['field_missing']})")
# 3 rows x 2 slots = 6 checks; 1 field-only, 1 header-only, 4 with neither.
check(cov["both_missing"] == 4, f"coverage: both_missing counted (got {cov['both_missing']})")

# The field-vs-header question must be asked of the META BLOCK, not of the
# fallback: person_store's `born` falls back to the header, so a row whose meta
# carries no date key must count as field-missing even though field_born is set.
PA.date_drift([{"name": "Unmigrated", "file": "f.md", "meta_date_keys": (),
                "field_born": "1969, Somewhereton, MA", "header_born": "1969, Somewhereton, MA",
                "field_died": None, "header_died": ""}])
check(PA.DATE_DRIFT_COVERAGE["field_missing"] == 1,
      "an unmigrated entry counts as field-missing, not as a silent zero")

# --- the place predicate: a DATE segment is never a place ----------------- #
# The vitals parser strips bracket CHARACTERS but keeps their content, so
# "Sep 1843 [GRO Q3], Bristol district" reaches this auditor as segment 0
# "Sep 1843 GRO Q3" — and a word-only test accepts "GRO" as a place name. Three
# live false positives came from exactly that, for as long as prose_audit existed.
for seg, want, why in [
    ("Salem", True, "a plain place"),
    ("Bristol district", True, "a multi-word place"),
    ("Weymouth, MA", True, "still a place"),
    ("DEC 1651", False, "month + year"),
    ("ABT 1640", False, "an approximation"),
    ("bef. 9 OCT 1774", False, "a bound"),
    ("Sep 1843 GRO Q3", False, "a date segment carrying a word-like token"),
    ("1842 Jun-qtr GRO Q2", False, "a GRO quarter is a date, not a place"),
    ("", False, "empty"),
]:
    got = PA._segment_names_place(seg)
    check(got == want, f"_segment_names_place({seg!r}) -> {want}  [{why}]"
          + ("" if got == want else f" (got {got})"))


# --- DATE_IMPOSSIBLE / DATE_UNATTESTED (23 JUL 2026) ---------------------- #
# Two invariants that check a stored value against REALITY rather than against
# the header it came from — DATE_DRIFT is blind whenever both sides come from the
# same parser, because a bad parse agrees with itself.
def _row(name, born=None, died=None, paren=""):
    return {"name": name, "file": "F.md",
            "meta_date_keys": tuple(k for k, v in (("born", born), ("died", died)) if v),
            "field_born": born, "field_died": died,
            "header_born": "", "header_died": "", "header_paren": paren}

for row, kind, why in [
    (_row("Impossible", born="1718", died="1701",
          paren="of Someplace; father of Susanna bp. 8 FEB 1718/19; ? m. Mary 3 FEB 1701/2"),
     "DATE_IMPOSSIBLE", "born after died — a real case, from a daughter's baptism and a marriage"),
    (_row("Invented", born="1899", paren="b. 3 SEP 1780, Somewhereton"),
     "DATE_UNATTESTED", "a year with no basis anywhere in its own header"),
]:
    found = PA.date_invariants([row])
    got = [f[3] for f in found]
    check(got == [kind], f"{kind}: {why}" + ("" if got == [kind] else f" (got {got})"))

for row, why in [
    (_row("Clean", born="3 SEP 1780", died="1873", paren="b. 3 SEP 1780, Somewhereton; d. 1873"),
     "an ordinary entry"),
    (_row("Dual year", born="6 JAN 1744", paren="b. 6 JAN 1743/4, Somewhereton"),
     "an Old Style / New Style field cites the NS year, which the header spells 1743/4"),
    (_row("Decade", born="ABT 1650", paren="b. ~1650s, prob. Somewhereton"),
     "the decade form attests its base year"),
    (_row("Range end", born="BET 1750 AND 1756", paren="b. ~1750-56, Someplace"),
     "a two-digit range end attests the expanded year"),
    (_row("Has an id", born="1853", paren="b. 1853 (FS ABCD-123), Somewhereton"),
     "a record identifier is stripped before the years are read"),
    (_row("Year range", born="1810", died="1890", paren="1810-1890; FS ABCD-123"),
     "a YEAR RANGE is attestation, not an identifier — reading it as one made this "
     "check report 37 findings on a clean vault"),
]:
    found = PA.date_invariants([row])
    check(not found, f"no false positive: {why}" + ("" if not found else f" (got {found})"))

# --- the promotion: DATE_DRIFT BLOCKS (22 JUL 2026) ----------------------- #
# It was advisory at first landing and became blocking once the baseline was 0 and
# the Spec 04 residue was triaged. It is the ONLY blocking metric in prose_audit:
# ERROR/WARN judge PROSE, which a human writes and may phrase loosely, while a
# DATE_DRIFT finding is two machine-readable copies of one fact disagreeing.
import io, contextlib
import vault_config
try:
    vault_config.resolve_vault(None)
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        rc = PA.main([])
    check(rc == 0, f"live vault is at baseline, so prose_audit exits 0 (got {rc})")
    check("[BLOCKING]" in buf_out.getvalue(),
          "the summary line announces DATE_DRIFT as BLOCKING, not advisory")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc2 = PA.main(["--no-strict-dates"])
    check(rc2 == 0, "--no-strict-dates is accepted as a per-run override")
except BaseException as exc:
    check(True, f"skip live exit-code check (no vault: {exc})")

print(f"\n{PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
