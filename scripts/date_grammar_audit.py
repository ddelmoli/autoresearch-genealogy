#!/usr/bin/env python3
"""date_grammar_audit.py — does a STORED date field parse as a GEDCOM 7 DateValue?

WHY IT EXISTS (Q338, raised 26 AUG 2026). Every date gate in the vault — DATE_DRIFT,
DATE_IMPOSSIBLE, DATE_UNATTESTED — reaches a date through `gdate.resolve_year()`,
which is deliberately FORGIVING: it normalises, strips a residue and returns a year.

    '1969, Somewhereton, MA'        -> resolve_year = 1969
    '. 16 AUG 1646, Somewhereton'   -> resolve_year = 1646   (residue dropped)

So all three gates pass on a value that `gdate` itself reports `valid=False`. **The
validator already existed and no gate asked it.** This gate asks it.

⛔ DO NOT WIDEN `resolve_year` TO REJECT THESE. It is forgiving on purpose — it is
what lets the year-based gates read a legacy field at all. The fix is a NEW check
that asks `is_valid`, never a change to the old one.

⭐⭐ WHAT Q338 ACTUALLY MEASURED, AND WHY THE SCOPE HERE IS NARROWER THAN ITS SPEC.
Q338 reported **309 stored fields** breaking the grammar, in two classes (271 storing
the literal *unknown*, 38 carrying a place inside the date), and specced a bulk key
delete plus 38 hand fixes. **Re-measured 26 AUG 2026 with two independent readers:
the vault stores 2,322 `born`/`died` fields and NOT ONE of them is invalid.** The 306
this reproduces are reached through `PersonRecord.born`/`.died`, which **fall back to
the HEADER parenthetical when no meta key exists** (`person_store._record_from_meta`).
They were header text all along, and the two big classes are LEGAL there:

  - the literal `unknown` is **explicitly permitted** by the header grammar
    ("a `b.`/`bapt.`/`chr.`/`d.` field carries a GEDCOM 7 DateValue **or the literal
    `unknown`**"), so storing-a-forbidden-value was never happening;
  - the place rides along because the header grammar is `date, place` BY DESIGN, and
    "move the place into the header parenthetical" asks for where it already is.

So Q338's steps 2 and 3 are NOT OWED, and this gate does not implement them. What
survives is its step 1, and it is worth having at **baseline 0**: the stored
population is clean today, and a gate that locks a clean invariant catches the FIRST
bad value someone writes instead of the three-hundredth.

⚠ THE SCOPE DISTINCTION IS THE WHOLE POINT AND MUST NOT BE QUIETLY WIDENED. Auditing
the record ATTRIBUTE re-reports 306 legal header values as defects; auditing the
STORED KEY reports what the rule actually forbids. The filter is
`raw['meta_date_keys']` (the file model: the frontmatter keys present). `--headers`
prints the header population for anyone tempted to re-raise Q338 from the attribute.

WHAT COUNTS
  DATE_GRAMMAR   a STORED `born`/`died` whose value is not a valid GEDCOM 7
                 DateValue. Advisory, baseline 0 — a non-zero is a REGRESSION,
                 not a backlog.

USAGE
  python3 scripts/date_grammar_audit.py             # full report
  python3 scripts/date_grammar_audit.py --headers   # the header population (Q338's 306)
  python3 scripts/date_grammar_audit.py --heartbeat # one line for the banner
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdate  # noqa: E402
import person_store  # noqa: E402
import vault_config  # noqa: E402

DATE_FIELDS = ("born", "died")


def stored_date_fields(vault):
    """Yield (record, key, value) for each date field the record actually STORES.

    ⚠ Never `getattr(rec, 'born')` without this filter: on the narrative model that
    attribute falls back to the header parenthetical, and the fallback value is
    header text under a different grammar. That conflation is what Q338 measured.
    """
    for rec in person_store.iter_people(vault):
        stored = set(rec.raw.get("meta_date_keys", ()) or ())
        for key in DATE_FIELDS:
            if key not in stored:
                continue
            value = (rec.raw.get("read_dates", {}) or {}).get(key, getattr(rec, key))
            if value is None:
                continue
            yield rec, key, value


def header_date_values(vault):
    """Yield (record, key, value) for date values that came from the HEADER only.

    Informational. These are NOT DATE_GRAMMAR findings — see the module docstring.
    """
    for rec in person_store.iter_people(vault):
        stored = set(rec.raw.get("meta_date_keys", ()) or ())
        for key in DATE_FIELDS:
            if key in stored:
                continue
            value = getattr(rec, key)
            if value is not None:
                yield rec, key, value


def classify_header(value):
    """Split the header population into what the header grammar ALLOWS and what it
    does not. Only the residue is anybody's defect, and it belongs to the header
    gate, not to a date-field gate.

    ⚠ VALIDITY IS ASKED FIRST, and it must be. Most header values are ordinary
    DateValues that simply have no meta key beside them; classifying before
    validating reported `26 OCT 899` and `ABT 1788` as unparsed residue, which is
    the flattering direction for a sweep whose residue list is meant to be read.
    """
    s = str(value).strip()
    if gdate.is_valid(s):
        return "VALID"                # a plain date; it just has no stored key
    if s.lower() == "unknown":
        return "LEGAL_UNKNOWN"        # the header grammar names this literal
    if "," in s:
        return "HEADER_DATE_PLACE"    # the header grammar is `date, place`
    return "UNPARSED"                 # none of the above: a real header defect


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--headers", action="store_true",
                    help="report the HEADER-derived population (Q338's 306) instead. "
                         "Not findings; printed so the conflation is not re-discovered.")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)

    if a.headers:
        rows = list(header_date_values(vault))
        tally = Counter(classify_header(v) for _r, _k, v in rows)
        print("=== HEADER-derived date values — NOT DATE_GRAMMAR findings ===")
        print("  These reach PersonRecord through the header fallback, not a stored")
        print("  key. `unknown` and a trailing place are BOTH legal in a header.\n")
        for cls, n in tally.most_common():
            print(f"  {cls:20} {n}")
        residue = [(r, k, v) for r, k, v in rows if classify_header(v) == "UNPARSED"]
        if residue:
            print(f"\n  --- UNPARSED ({len(residue)}): neither a DateValue, nor the legal")
            print("      literal, nor date+place. A HEADER defect (header_audit's")
            print("      territory), listed here because this sweep is what surfaces them ---")
            for r, k, v in residue:
                print(f"      {r.source_file}  [{r.id}]  {k}: {v!r}")
        return 0

    findings = [(r, k, v) for r, k, v in stored_date_fields(vault)
                if not gdate.is_valid(v)]
    total = sum(1 for _ in stored_date_fields(vault))

    if a.heartbeat:
        print(f"DATE_GRAMMAR: {len(findings)}  [advisory; baseline 0 — a non-zero is a "
              f"REGRESSION]  ({total} stored born/died field(s) checked)")
        return 0

    print("=== DATE_GRAMMAR — a stored date field that is not a GEDCOM 7 DateValue ===")
    print(f"  {total} stored born/died field(s) checked.")
    print("  Validate one by hand with: python3 scripts/gdate.py '<value>'\n")
    for r, k, v in findings:
        print(f"  {r.source_file}  [{r.id}]  {k}: {v!r}")
    if not findings:
        print("  (none)")
    print(f"\nDATE_GRAMMAR: {len(findings)}  [advisory; baseline 0]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
