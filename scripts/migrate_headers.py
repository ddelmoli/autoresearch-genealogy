#!/usr/bin/env python3
"""
migrate_headers.py — bring non-conforming bold-name headers to the header grammar
(spec/header-grammar/04_migration.md). DRY RUN by default; `--apply` writes.

⚠ THE INVARIANT, AND IT IS THE WHOLE TOOL:

        NO DATE VALUE CHANGES. EVER.

Every proposal is checked by extracting the header's dates BEFORE and AFTER with
the same reader and comparing years, and by checking the result against the
record's `- meta:` date field. A proposal that changes, adds or drops a date is
NOT applied — it is refused and routed to human review. A wrong date is far worse
than an unmigrated header, which is the contract `gdate.normalise` and
`person_store._terse_vitals` already hold.

WHY THIS IS NOT THE 22 JUL RETRY. A bulk header rewrite was attempted on 22 JUL
2026 and rejected on measurement: it mangled entries on a dry run. Two things are
different now.

  1. THERE IS AN ORACLE. In July the header was the ONLY store of a person's
     dates, so a rewrite had nothing to check itself against and was reduced to
     guessing at prose. Since spec/structured-dates 03/04, `born`/`died` are
     machine-authoritative fields, and only 14 of the 752 non-conforming entries
     lack one.
  2. THE TRANSFORMATION IS SMALLER. July tried to normalise whole headers. This
     moves markers and normalises a date slot IN PLACE.

PHASE A (this file, today) — R3 ONLY: rewrite the DATE SLOT of a field that is
ALREADY marked, in place, changing nothing else on the line. `b. ~1750, Villagio`
becomes `b. ABT 1750, Villagio`. The header's structure is untouched, so the class
of damage July produced is not reachable from here.

  R4 (add vital tags to a terse header) and R2 (unnest a parenthetical) both
  RESTRUCTURE the parenthetical, which is precisely what mangled entries in July.
  They are deliberately NOT in Phase A. They come after Phase A has been applied
  and reviewed on real files, as separate phases with their own measurement.

⚠ THE SOURCE IS THE HEADER, THE ORACLE IS THE FIELD. The new slot is
`gdate.normalise(<what the header already says>)` — a pure NOTATION conversion —
not the meta value copied in. Copying the field would silently change the human
display's precision: a header reading `~1750` beside a field reading `1750` would
lose its approximation marker, which is a fact about the evidence, not formatting.
The field is used to CHECK the result, never to produce it.

Usage:
  python3 scripts/migrate_headers.py                     # dry run, whole vault
  python3 scripts/migrate_headers.py --file Family_Tree_Example.md
  python3 scripts/migrate_headers.py --file Family_Tree_Example.md --apply
  python3 scripts/migrate_headers.py --refusals          # the human-review worklist
"""
import argparse
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import gdate as G
import header_audit as H
import person_store as ps
import vault_config


def _split_place(slot):
    """('<date part>', '<place tail or None>') for a vital field's date slot.

    The FIRST comma splits, because a place may itself be a comma-delimited
    jurisdiction list ("Villagio, Provincia"). A GEDCOM DateValue never contains
    a comma, so this cannot cut a date in half — but US prose ("Sep 3, 1780") can
    be split wrongly, which is why the result is always re-validated rather than
    trusted.
    """
    m = H.PLACE_TAIL.match(slot)
    return (m.group(1).strip(), m.group(2).strip()) if m else (slot.strip(), None)


# --------------------------------------------------------------------------- #
# PHASE A2 — two further MECHANICAL classes, added after triaging the 141 Phase A
# refusals. Both are narrow by construction; everything else stays refused.
# --------------------------------------------------------------------------- #

# A2a. ABSENCE STATED IN A DIALECT. `d. Deceased` / `d. ?` mean "died, date not
# recorded". The grammar has a declared spelling for exactly that -- `unknown` --
# so this is a notation fix like any other, not a loss of information. Note the
# `\Z` rather than `\b`: a trailing `\b` after `?` never matches at end of string,
# which silently dropped all 7 `?` entries out of this class on the first pass.
_ABSENCE = re.compile(r"\A(?:deceased|unknown|unk|n/?a|\?+|—|--?)"
                      r"(?:\s*[—-]\s*no\s+dates?\b.*)?\Z", re.I)

# A2b. A PLACE WITH NO COMMA BEFORE IT: "b. 1809 Droitwich" -> "b. 1809, Droitwich".
# R6 says the place follows the date behind a comma, and `normalise` hands back the
# unconsumed tail, so the fix is punctuation only.
#
# ⚠ TIGHTLY GUARDED, because the first cut of this rule proposed turning
# "b. 1841 [FS" into "b. 1841, [FS" -- reading a truncated bracket as a place
# because "FS" is a capitalised word. A place here must be capitalised words ONLY,
# and the slot must carry no bracket or quote at all: anything with punctuation is
# a note, a citation or an alias, and placing those is a human's judgement.
_PLACEISH = re.compile(r"[A-Z][A-Za-z'\u2019\-]*(?:\s+(?:[A-Z][A-Za-z'\u2019\-]*|d[eia]|del|della|di|of|upon|on))*\Z")
_NOT_PLACE_CHARS = re.compile(r"[\[\]\"\u201c\u201d()/;]")


def propose_absence(tag, slot):
    """`d. Deceased` -> `d. unknown`, keeping any place tail."""
    date_part, place = _split_place(H.EMPHASIS.sub("", slot).strip())
    if not _ABSENCE.match(date_part.strip()):
        return None
    return f"{tag} unknown" + (f", {place}" if place else "")


def propose_place_comma(tag, slot):
    """`b. 1809 Droitwich` -> `b. 1809, Droitwich`. Punctuation only."""
    raw = H.EMPHASIS.sub("", slot).strip()
    if _NOT_PLACE_CHARS.search(raw):
        return None                      # a note/citation/alias, not a bare place
    date_part, place = _split_place(raw)
    if place:
        return None                      # already comma-separated: not this class
    value, residue = G.normalise(date_part)
    residue = residue.strip()
    if not value or not residue or not G.is_valid(value):
        return None
    if not _PLACEISH.match(residue):
        return None
    return f"{tag} {value}, {residue}"


def propose_r3(record):
    """[(old_field, new_field, note), ...] for this record's R3 fields.

    Returns only proposals whose result is a VALID DateValue with the SAME year.
    Anything else is a refusal, reported separately.
    """
    paren = record.raw.get("header_paren") or ""
    proposals, refusals = [], []
    if not paren.strip() or "(" in paren:
        return proposals, refusals          # R2 territory: not Phase A
    for field in [f.strip() for f in paren.split(";") if f.strip()]:
        m = H.VITAL_TAG.match(field)
        if not m or "(" in field:
            continue
        tag, slot = m.group(1), m.group(2)
        if H._date_slot_ok(slot):
            continue                        # already conforming
        for proposer in (propose_absence, propose_place_comma):
            candidate = proposer(tag, slot)
            if candidate and content_preserved(field, candidate):
                proposals.append((field, candidate, "A2"))
                break
        else:
            pass
        if proposals and proposals[-1][0] == field:
            continue                        # handled by an A2 rule
        date_part, place = _split_place(H.EMPHASIS.sub("", slot).strip())
        new_date, residue = G.normalise(date_part)
        if not new_date:
            refusals.append((field, f"normalise() refuses {date_part!r} — not a "
                                    f"date this tool may guess at"))
            continue
        # ⚠ THE RESIDUE IS NOT OPTIONAL TO CHECK. `normalise` reports what it did
        # NOT consume, and ignoring that silently DELETES it. Measured on the first
        # dry run of this tool, which proposed:
        #     "b. ~1799 Staffordshire"            -> "b. ABT 1799"
        #     "b. Sep 1843 [GRO Q3], Bristol …"   -> "b. SEP 1843, Bristol …"
        #     'chr. 9 SEP 1764 "Mary Wix," Horsley' -> "chr. 9 SEP 1764"
        # losing a place, a GRO source reference and a recorded name variant. The
        # date-only invariant did not notice, because no DATE changed — which is
        # exactly how the 22 JUL rewrite mangled entries while looking correct.
        # A place with no comma before it is also a judgement call (is it a place,
        # or part of the date?), and this tool does not make judgement calls.
        if residue.strip():
            refusals.append((field, f"normalise() left residue {residue.strip()!r} "
                                    f"— content that is not the date; a human must "
                                    f"place it"))
            continue
        if not G.is_valid(new_date):
            refusals.append((field, f"normalise() produced an invalid value "
                                    f"{new_date!r}"))
            continue
        old_year = G.resolve_year(date_part)
        new_year = G.year(new_date)
        if old_year is not None and new_year != old_year:
            refusals.append((field, f"YEAR WOULD CHANGE {old_year} -> {new_year}"))
            continue
        new_field = f"{tag} {new_date}" + (f", {place}" if place else "")
        if not content_preserved(field, new_field):
            refusals.append((field, "non-date content would be lost or altered"))
            continue
        proposals.append((field, new_field, f"{date_part!r} -> {new_date!r}"))
    return proposals, refusals


def check_oracle(record, side, new_value):
    """The meta field is the ORACLE. Returns a refusal string, or None."""
    field_value = record.born if side == "b" else record.died
    if not field_value:
        return None                          # no oracle: not a disagreement
    fy, ny = G.year(field_value), G.year(new_value)
    if fy is not None and ny is not None and fy != ny:
        return (f"disagrees with the meta {'born' if side == 'b' else 'died'} "
                f"field ({fy} vs {ny})")
    return None


def migrate_line(line, proposals):
    """Apply proposals to one header line as exact substring replacements.

    Exact substring, deliberately: everything that is not a proposed field stays
    BYTE-IDENTICAL, so the diff is small and boring. A large diff on a header is a
    bug, not a thorough migration.
    """
    out = line
    for old, new, _note in proposals:
        if out.count(old) != 1:
            return None                      # ambiguous or vanished: refuse
        out = out.replace(old, new, 1)
    return out


def run(vault, only_file=None):
    plans, refusals = [], []
    for rec in ps.iter_people(vault):
        rel = rec.source_file or "?"
        if only_file and os.path.basename(rel) != only_file:
            continue
        props, refs = propose_r3(rec)
        for field, why in refs:
            refusals.append((rel, rec.id, field, why))
        if not props:
            continue
        # ⚠ ALL OR NOTHING PER HEADER. If any field on this line was refused, do
        # not rewrite the others either.
        #
        # Found by the Spec 03 gate BLOCKING this migration's own first tranche: a
        # header with two vital fields where `b.` was fixable and `d.` was not came
        # out half-migrated, and "touching a legacy header opts it in" then held the
        # commit against the leftover R3. The gate was right. A half-migrated header
        # is a worse state than an untouched one, because it LOOKS done -- and the
        # worklist would have to describe a partial fix rather than a whole entry.
        if refs:
            continue
        # Oracle check per side before anything is written.
        blocked = False
        for old, new, _n in props:
            side = "b" if re.match(r"\A(b\.|bapt\.|chr\.|born)", new, re.I) else "d"
            slot = H.VITAL_TAG.match(new).group(2)
            date_part, _p = _split_place(slot)
            bad = check_oracle(rec, side, date_part)
            if bad:
                refusals.append((rel, rec.id, old, bad))
                blocked = True
        if blocked:
            continue
        plans.append((rel, rec, props))
    return plans, refusals


# ⚠ ONLY RECOGNISED DATE TOKENS. Written first as `[A-Za-z]{3,9}` to catch month
# names, which silently ate EVERY alphabetic word -- "Staffordshire" was stripped as
# though it were a month, both sides compared as empty, and the whole check was a
# no-op that passed 340 proposals without inspecting one of them. The corpus
# property test built on it was vacuous too. An explicit vocabulary is the fix: a
# word this list does not name is CONTENT, and content must survive.
_MONTHS = (r"JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|"
           r"APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|SEPT")
# DECEASED / UNKNOWN / UNK are ABSENCE MARKERS -- values the date slot can hold,
# not prose content -- so they belong in this vocabulary. Without them the A2a
# rewrite `d. Deceased` -> `d. unknown` reads as one content word replacing
# another and content_preserved blocks its own fix.
_KEYWORDS = (r"ABT|EST|CAL|BEF|AFT|BET|AND|FROM|TO|JULIAN|GREGORIAN|FRENCH_R|HEBREW|"
             r"BCE|CA|ABOUT|BEFORE|AFTER|BETWEEN|CIRCA|DECEASED|UNKNOWN|UNK")
_DATEISH = re.compile(rf"(?:\b(?:{_MONTHS}|{_KEYWORDS})\b\.?|\d+|[~\-–—,\.\?/])", re.I)


def content_preserved(old_field, new_field):
    """Everything that is NOT the date must survive the rewrite.

    The date-only invariant is NECESSARY BUT NOT SUFFICIENT, and believing
    otherwise is what let the first dry run of this tool propose deleting a place,
    a GRO reference and a name variant while every date stayed identical. This is
    the second half of the invariant: strip date-ish tokens from both sides and
    require the remainder to be unchanged.

    Deliberately crude — it compares the leftover alphabetic words, so a place, an
    alias, a bracketed note or a citation cannot vanish, while `~1750` -> `ABT 1750`
    (pure notation) passes.
    """
    def rest(s):
        stripped = _DATEISH.sub(" ", s)
        return [w for w in re.findall(r"[A-Za-z]{2,}", stripped)]
    return rest(old_field) == rest(new_field)


def verify(vault, path, old_line, new_line, rec):
    """The invariant, re-checked through the READER rather than by assertion.

    Re-parses both header lines with person_store's own vitals parser and compares
    the extracted (born, died) YEARS. This is the check that would have caught the
    July mangling, and it is run on every single entry, never sampled.
    """
    name_old, rest_old = _split_header(old_line)
    name_new, rest_new = _split_header(new_line)
    b0, d0 = ps._parse_vitals(ps._vitals_paren(name_old, rest_old))
    b1, d1 = ps._parse_vitals(ps._vitals_paren(name_new, rest_new))
    for label, a, b in (("born", b0, b1), ("died", d0, d1)):
        ya, yb = G.resolve_year(a), G.resolve_year(b)
        if (ya is None) != (yb is None):
            return f"{label}: year presence changed ({a!r} -> {b!r})"
        if ya is not None and ya != yb:
            return f"{label}: YEAR CHANGED {ya} -> {yb}"
    if name_old != name_new:
        return "the bold name changed"
    return None


def _split_header(line):
    """(bold name, rest) — split with person_store's OWN header regex.

    Not a private copy. A hand-rolled `^\\*\\*(.+?)\\*\\*` version reported "the bold
    name changed" on 4 entries whose header is a LIST ITEM ("- **Name** (…)") with
    further **bold** spans later in the line: it failed to match, fell back to
    treating the whole line as the name, and then any edit anywhere looked like a
    name change. The proposals were correct; the CHECK was wrong.

    Same lesson as the validator consuming `header_paren`: when a tool has to agree
    with the reader, it must use the reader's parser, not an equivalent-looking one.
    """
    m = ps._BOLD.match(line)
    return (m.group(1), m.group(2)) if m else (line, "")


def main():
    ap = argparse.ArgumentParser(description="Phase A (R3) header migration.")
    ap.add_argument("--vault")
    ap.add_argument("--file", help="restrict to one lineage file (basename)")
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--refusals", action="store_true", help="show the worklist")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    vault = vault_config.resolve_vault(a.vault)
    plans, refusals = run(vault, a.file)

    # Build the per-file edits and verify EVERY one before touching anything.
    edits, failed = {}, []
    for rel, rec, props in plans:
        path = os.path.join(vault, rel)
        lineno = rec.raw.get("header_line")
        lines = edits.setdefault(path, open(path, encoding="utf-8").read().splitlines())
        old_line = lines[lineno]
        new_line = migrate_line(old_line, props)
        if new_line is None:
            failed.append((rel, rec.id, "field not uniquely located on the line"))
            continue
        bad = verify(vault, path, old_line, new_line, rec)
        if bad:
            failed.append((rel, rec.id, bad))
            continue
        lines[lineno] = new_line

    shown = 0
    for rel, rec, props in plans:
        if a.limit and shown >= a.limit:
            break
        if any(f[1] == rec.id for f in failed):
            continue
        shown += 1
        print(f"  {rel}  {rec.id}")
        for old, new, note in props:
            print(f"      - {old}")
            print(f"      + {new}")

    print("\n=== PHASE A (R3: date-slot notation, in place) ===")
    print(f"  entries with a proposal:  {len(plans) - len({f[1] for f in failed})}")
    print(f"  fields rewritten:         {sum(len(p) for _r, _rec, p in plans)}")
    print(f"  REFUSED (human review):   {len(refusals)}")
    print(f"  FAILED the invariant:     {len(failed)}   [must be 0 to apply]")
    for rel, pid, why in failed[:20]:
        print(f"      {rel}  {pid}  {why}")

    if a.refusals:
        print("\n=== REFUSALS (worklist; nothing was changed) ===")
        for rel, pid, field, why in refusals[:a.limit or 60]:
            print(f"  {os.path.basename(rel)}  {pid}  {why}")
            print(f"      field: {field}")

    if a.apply:
        if failed:
            print("\nREFUSING TO APPLY: the invariant failed above.")
            sys.exit(1)
        for path, lines in edits.items():
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        print(f"\nAPPLIED to {len(edits)} file(s).")
    else:
        print("\nDry run. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
