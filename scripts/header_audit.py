#!/usr/bin/env python3
"""
header_audit.py — conformance of bold-name headers to the header grammar
(spec/header-grammar/01_grammar.md). ADVISORY: exits 0 even with findings.

WHY THIS EXISTS. The `- meta:` block is machine-grade and gated; the header
beside it was free prose that a parser had to GUESS at. Eight dialects
accumulated, each introduced incrementally by an assistant adding an entry with
no grammar constraining what it wrote, and the whole of 22-23 JUL 2026 went into
widening the READER to cope. A reader that must accommodate eight dialects will
meet a ninth. This reports the gap at the WRITE end instead.

THE RULES CHECKED (R1 and R5-R7 are not checkable here; see below):

  R2  the vitals parenthetical must not contain a NESTED parenthetical.
  R3  a field opening with a vital tag must carry a valid GEDCOM 7 DateValue
      (or the literal `unknown`) in its date slot, optionally followed by
      ", place".
  R4  if the record carries a `born`/`died` meta field, the header must expose
      at least one marked vital field.

  R1 (the vitals paren is the FIRST balanced paren) is not a *check* but a
     definition — it is how the paren under test is chosen, and it is honoured
     by consuming person_store's own `raw['header_paren']` rather than
     re-deriving it. The validator must judge the same paren the reader uses, or
     it grades a different document than the one being read.
  R5 (years in note fields are not dates) is unfalsifiable by construction: this
     validator never looks outside a date slot, which IS R5.
  R6's ordering half (jurisdictions smallest to largest) is semantic and cannot
     be checked without a gazetteer; its structural half (place after a comma,
     never inside the date slot) is enforced as part of R3.
  R7 (only the entry's own external id) is already enforced by
     header_xref_audit.py and is not duplicated here.

⚠ STRICT BY DESIGN: a date slot that merely NORMALISES does not conform.
`c.966` is not a DateValue; it is prose that `gdate.normalise` can rescue into
`ABT 966`. Counting it as conforming would mean the header never actually
converges on GEDCOM 7 and would leave the reader carrying the cost forever,
which is the exact failure this lane was opened to correct. Normalisation is the
MIGRATOR's job (Spec 04), not the validator's excuse.

THE ORACLE COLUMN. For every non-conforming entry this reports whether the
record carries `born`/`died`. A migration can only DERIVE a corrected header
where such a field exists; everywhere else it must refuse and route to human
review. The 22 JUL bulk header rewrite was rejected precisely because no such
oracle existed and it was reduced to guessing at prose.

Findings key on the meta `id`, never the bold name: identity is the id, and a
malformed display name is exactly the case this report has to survive.

Usage:
  python3 scripts/header_audit.py
  python3 scripts/header_audit.py --rule R4 --limit 20
  python3 scripts/header_audit.py --file Family_Tree_Example.md --csv
"""
import argparse
import csv
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import gdate as G
import person_store as ps
import vault_config

# A field opens a VITAL SLOT with one of these tags. `born`/`died` spelled out are
# accepted alongside the abbreviations: an explicit, unambiguous marker is what the
# grammar needs, and banning a second spelling of one would create migration churn
# for no readability gain. What was never acceptable is an UNMARKED field, which is
# where every wrong value came from.
#
# `\s*(.*)` rather than `\s+(.+)`: a tag with an EMPTY slot ("b. ") is a marked
# vital field whose date is missing, and must be diagnosed as R3. Requiring a
# non-empty remainder made the field invisible as a vital field, so R4 fired
# instead — "no marked vital field" about a header that plainly has one, which
# would send the migrator looking for the wrong fix.
# The `\b` on the spelled-out words is what keeps `\s*` safe: without it `born`
# would match inside `borne`.
VITAL_TAG = re.compile(r"\A(b\.|bapt\.|chr\.|d\.|born\b|died\b)\s*(.*)\Z", re.I | re.S)

# An id field is exempt from the date rules. Left deliberately open-ended rather
# than closed to a fixed tag list: header_xref_audit already polices the real
# hazard (a FOREIGN pid in a header), so a second list to maintain buys nothing.
ID_FIELD = re.compile(r"\A(?:FS\s+PID|FS:|WikiTree|WT:|anc:|Ancestry)\b", re.I)

# R6 structural half: "<date>, <place>". Non-greedy so the FIRST comma splits --
# a place may itself be a comma-delimited jurisdiction list.
PLACE_TAIL = re.compile(r"\A(.*?),\s+(.+)\Z", re.S)

# Absence stated explicitly. `unknown` is a legal date slot precisely so a writer
# can say "no birth date recorded" IN the grammar instead of resorting to an
# unmarked positional field, which is the dialect that caused the damage.
UNKNOWN = re.compile(r"\Aunknown\Z", re.I)

RULES = ("R2", "R3", "R4")


# Markdown emphasis is PRESENTATION, not content. `b. **3 SEP 1780**` renders in
# Obsidian as a perfectly good date, and person_store's reader already strips `*`
# before storing the value — so flagging it would report a defect the human cannot
# see and send the migrator to rewrite ~49 headers without changing a single fact.
# The dual contract cuts both ways: a rule added for the machine has to be checked
# against a human reading the file with no tooling.
#
# Emphasis and code ticks ONLY. Square brackets are deliberately NOT stripped: an
# aside like `1946 [infant death]` belongs in a note field or after the comma, and
# silently absorbing it into the date slot would hide a real defect.
EMPHASIS = re.compile(r"[*`]")


def _date_slot_ok(value):
    """True when a vital field's date slot holds a valid DateValue (or `unknown`),
    optionally followed by ", place". Strict: normalisable prose is NOT valid."""
    v = EMPHASIS.sub("", value).strip()
    if not v:
        return False
    if G.is_valid(v) or UNKNOWN.match(v):
        return True
    tail = PLACE_TAIL.match(v)
    if tail:
        head = tail.group(1).strip()
        if G.is_valid(head) or UNKNOWN.match(head):
            return True
    return False


def _fields(paren):
    return [f.strip() for f in paren.split(";") if f.strip()]


def violations(record):
    """Every rule this record's header breaks, as [(rule, detail), ...].

    Returns [] for a conforming header. An entry may break more than one rule and
    each is reported, so the histogram is a worklist ordered by cause rather than
    a pile of overlapping flags.
    """
    paren = record.raw.get("header_paren") or ""
    meta_keys = record.raw.get("meta_date_keys", ())
    # R4 keys on the DATE fields only -- a lone `born_phrase` is not a date.
    has_record_date = any(k in meta_keys for k in ("born", "died"))

    found = []
    if not paren.strip():
        # No vitals parenthetical at all. A violation only if the record HAS
        # dates: an entry with none needs no paren, and requiring one would force
        # a writer to invent content. Otherwise it is COVERAGE, not a finding.
        if has_record_date:
            found.append(("R4", "no vitals parenthetical, but the record has dates"))
        return found

    if "(" in paren:
        found.append(("R2", "nested parenthetical inside the vitals parenthetical"))

    saw_vital = False
    for field in _fields(paren):
        m = VITAL_TAG.match(field)
        if not m:
            continue                    # an id field or a note field: R5, not read
        saw_vital = True
        if "(" in field:
            # Already reported as R2, and the nested paren is WHY the date slot
            # will not parse. Reporting R3 as well would double-count one defect
            # and inflate R3, breaking the property that the histogram is a
            # worklist ordered by CAUSE. Unnest it first; the R3 may not exist.
            continue
        if not _date_slot_ok(m.group(2)):
            found.append(("R3", f"date slot is not a DateValue: {m.group(1)} …"))
    if not saw_vital and has_record_date:
        found.append(("R4", "record has dates, header has no marked vital field"))
    return found


def oracle(record):
    keys = record.raw.get("meta_date_keys", ())
    b, d = "born" in keys, "died" in keys
    return "both" if (b and d) else "born" if b else "died" if d else "NONE"


def audit(vault):
    """-> (findings, stats). findings: [(file, id, rule, detail, oracle)]."""
    findings, stats = [], {
        "entries": 0, "conforming": 0, "nonconforming": 0,
        "no_paren_no_dates": 0, "per_rule": {r: 0 for r in RULES},
        "oracle": {"both": 0, "born": 0, "died": 0, "NONE": 0}, "per_file": {},
    }
    for rec in ps.iter_people(vault):
        stats["entries"] += 1
        paren = rec.raw.get("header_paren") or ""
        keys = rec.raw.get("meta_date_keys", ())
        if not paren.strip() and not any(k in keys for k in ("born", "died")):
            stats["no_paren_no_dates"] += 1
        vs = violations(rec)
        if not vs:
            stats["conforming"] += 1
            continue
        stats["nonconforming"] += 1
        stats["oracle"][oracle(rec)] += 1
        f = rec.source_file or "?"
        stats["per_file"][f] = stats["per_file"].get(f, 0) + 1
        for rule in {r for r, _ in vs}:
            stats["per_rule"][rule] += 1
        for rule, detail in vs:
            findings.append((f, rec.id, rule, detail, oracle(rec)))
    return findings, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--vault", help="vault path (else AUTORESEARCH_VAULT)")
    ap.add_argument("--rule", choices=RULES, help="only this rule")
    ap.add_argument("--file", help="only this lineage file (basename)")
    ap.add_argument("--limit", type=int, help="cap findings printed")
    ap.add_argument("--csv", action="store_true", help="findings as CSV on stdout")
    a = ap.parse_args()

    vault = vault_config.resolve_vault(a.vault)
    findings, stats = audit(vault)

    shown = findings
    if a.rule:
        shown = [f for f in shown if f[2] == a.rule]
    if a.file:
        shown = [f for f in shown if os.path.basename(f[0]) == a.file]
    if a.limit:
        shown = shown[:a.limit]

    if a.csv:
        w = csv.writer(sys.stdout)
        w.writerow(("file", "id", "rule", "detail", "oracle"))
        w.writerows(shown)
        return

    print("=== header grammar conformance (spec/header-grammar) ===")
    cur = None
    for f, pid, rule, detail, orc in shown:
        if f != cur:
            cur, = (f,)
            print(f"\n--- {f} ---")
        print(f"  {rule}  {pid}  [oracle: {orc}]  {detail}")

    e = stats["entries"] or 1
    print("\n=== SUMMARY ===")
    print(f"  entries:            {stats['entries']}")
    print(f"  CONFORMING:         {stats['conforming']}  "
          f"({stats['conforming'] * 100.0 / e:.1f}%)")
    print(f"  HEADER_GRAMMAR:     {stats['nonconforming']}  [advisory]")
    for r in RULES:
        print(f"    {r}: {stats['per_rule'][r]}")
    print(f"  coverage (no paren + no record dates, out of scope): "
          f"{stats['no_paren_no_dates']}")
    o = stats["oracle"]
    print(f"  oracle for the non-conforming — both {o['both']}, born {o['born']}, "
          f"died {o['died']}, NONE {o['NONE']}  (NONE = human review)")
    for k, n in sorted(stats["per_file"].items(), key=lambda x: -x[1])[:10]:
        print(f"    {n:>4}  {os.path.basename(k)}")


if __name__ == "__main__":
    main()
