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
    # `place` may already be present: "b. 1809 Droitwich, Worcestershire, England"
    # is the SAME defect -- only the FIRST jurisdiction is missing its comma -- so
    # the fix re-joins the recovered one in front of the existing tail rather than
    # bailing out. The guards below are what keep this safe; without them
    # "Sep 3, 1780" would split into date "Sep 3" + place "1780".
    value, residue = G.normalise(date_part)
    residue = residue.strip()
    if not value or not residue or not G.is_valid(value):
        return None
    if not _PLACEISH.match(residue):
        return None
    tail = f"{residue}, {place}" if place else residue
    return f"{tag} {value}, {tail}"


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
        for proposer in (propose_absence, propose_place_comma,
                         propose_dual_year, propose_medieval_span):
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
        if ya is None and yb is not None:
            # A GAIN, not a loss. "c.693/709" is unreadable to resolve_year, and
            # "BET 693 AND 709" is not -- which is the point: those medieval slash
            # headers are the very population LONGER_TERM parked as unresolvable
            # by DATE_DRIFT. Allowed only when the ORACLE does not contradict it.
            field = getattr(rec, label, None)
            if field is None or G.year(field) is None or G.year(field) == yb:
                continue
            return (f"{label}: gained year {yb} but the field says "
                    f"{G.year(field)}")
        if yb is None and ya is not None:
            return f"{label}: year LOST ({a!r} -> {b!r})"
        if ya is not None and ya != yb:
            # THE ONE SANCTIONED YEAR CHANGE: an Old Style/New Style dual.
            # "3 MAR 1696/7" resolves naively to 1696, but GEDCOM 7 Appendix A
            # §6.2 puts the NEW STYLE year in the DATE, and the meta field was
            # already migrated to it (1697) with born_phrase keeping "1696/7".
            # So the header moving 1696 -> 1697 is it being brought INTO
            # agreement with the authoritative field, not drifting from it.
            # Gated on the ORACLE, never allowed on its own say-so: the new year
            # must equal the meta field's year, or this is still a corruption.
            field = getattr(rec, label, None)
            if field is not None and G.year(field) == yb:
                continue
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
    ap.add_argument("--phase", choices=("a", "b"), default="a",
                    help="a = R3 date slots (default); b = R4 vital tags")
    a = ap.parse_args()

    vault = vault_config.resolve_vault(a.vault)
    if a.phase == "b":
        return main_r4(vault, a)
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



# --------------------------------------------------------------------------- #
# PHASE B1 — R4: give a TERSE header its vital tags.
#
# "(1940, MA; 1946 [infant death]; FS PID XXXX-XXX)" states its vitals
# POSITIONALLY. This adds the markers the grammar requires:
#   "(b. 1940, MA; d. 1946 [infant death]; FS PID XXXX-XXX)"
#
# ⚠ This RESTRUCTURES the parenthetical, which is the thing that mangled entries
# on 22 JUL. Three properties keep it honest, and all three are checked per entry:
#
#   1. IT NEVER DECIDES WHICH DATE IS WHICH. `person_store._terse_vitals` already
#      made that call -- it is the reader every other gate uses, complete with the
#      opens-with-a-date rule, the floruit guard and the absence-marker rule that
#      were added after the 25 wrong values. This tool only TAGS what the reader
#      already resolved. Where the reader recovers nothing (a floruit, a
#      name-first header), there is nothing to tag and the entry is refused.
#   2. THE RESULT IS VALIDATED BY THE VALIDATOR, not by this function's own idea
#      of correctness: the rewritten parenthetical is run back through
#      header_audit.violations and must come out clean. A rewrite that merely
#      moves a defect (a bracketed note left inside a now-tagged date slot) is
#      refused rather than counted as progress.
#   3. THE YEARS ARE RE-READ from the rewritten line and must be unchanged.
# --------------------------------------------------------------------------- #

# BARE absence only. An annotated one -- "Deceased [FS no date]" -- records WHY
# there is no date, which is research provenance, not noise: rewriting it to
# "d. unknown" drops that. content_preserved caught all three instances, but a
# defect caught as an APPLY FAILURE is a defect that blocks the batch, so it is
# refused here instead and goes to the worklist for a human to place.
_ABSENCE_SEG = re.compile(r"\A(?:deceased|unknown|unk|n/?a|\?+|—|--?)\Z", re.I)


class _Synthetic:
    """A record shim so a PROPOSED parenthetical can be graded by the validator."""

    def __init__(self, paren, meta_keys, born=None, died=None):
        self.id = "P-PROPOSED"
        self.source_file = None
        self.born, self.died = born, died
        self.raw = {"header_paren": paren, "meta_date_keys": meta_keys}


def propose_r4(record):
    """(new_paren, note) or (None, reason). Tags a terse header's vital fields."""
    paren = record.raw.get("header_paren") or ""
    if not paren.strip() or "(" in paren:
        return None, "no paren, or nested (Phase C)"
    hb, hd = record.raw.get("header_vitals", (None, None))
    if not hb and not hd:
        return None, "the reader recovers no vitals — floruit or name-first header"

    segs = [s.strip() for s in paren.split(";") if s.strip()]
    if any(H.VITAL_TAG.match(s) for s in segs):
        return None, "already has a marked vital field"

    def locate(value):
        """The unique segment this recovered value starts. None if 0 or >1."""
        hits = [i for i, s in enumerate(segs)
                if H.EMPHASIS.sub("", s).strip().startswith(value)]
        return hits[0] if len(hits) == 1 else None

    ib = locate(hb) if hb else None
    idx = locate(hd) if hd else None
    if hb and ib is None:
        return None, "birth value does not uniquely start a segment"
    if hd and idx is None:
        return None, "death value does not uniquely start a segment"
    if ib is not None and idx is not None and ib >= idx:
        return None, "death segment precedes birth segment — not this shape"

    out = list(segs)
    for i, value, tag in ((ib, hb, "b."), (idx, hd, "d.")):
        if i is None:
            continue
        seg = H.EMPHASIS.sub("", segs[i]).strip()
        rest = seg[len(value):]
        new_date, residue = G.normalise(value)
        if not new_date or residue.strip():
            return None, f"date {value!r} does not normalise cleanly"
        out[i] = f"{tag} {new_date}{rest}"

    # A lone `Deceased` / `—` segment beside a recovered birth is the DEATH field
    # stated as an absence. Tag it so the header says so in the grammar.
    if ib is not None and idx is None:
        for i, seg in enumerate(segs):
            if i != ib and _ABSENCE_SEG.match(H.EMPHASIS.sub("", seg).strip()):
                out[i] = "d. unknown"
                break

    new_paren = "; ".join(out)

    # (2) grade the PROPOSAL with the validator itself.
    bad = H.violations(_Synthetic(new_paren, record.raw.get("meta_date_keys", ())))
    if bad:
        return None, f"proposal still violates {sorted({r for r, _ in bad})}"
    return new_paren, "B1"


def run_r4(vault, only_file=None):
    """-> (plans, refusals) for Phase B1. plans: (rel, rec, old_paren, new_paren)."""
    plans, refusals = [], []
    for rec in ps.iter_people(vault):
        rel = rec.source_file or "?"
        if only_file and os.path.basename(rel) != only_file:
            continue
        if "R4" not in {r for r, _d in H.violations(rec)}:
            continue
        new_paren, why = propose_r4(rec)
        if not new_paren:
            refusals.append((rel, rec.id, rec.raw.get("header_paren", ""), why))
            continue
        plans.append((rel, rec, rec.raw.get("header_paren", ""), new_paren))
    return plans, refusals


def main_r4(vault, args):
    plans, refusals = run_r4(vault, args.file)
    edits, failed, shown = {}, [], 0

    for rel, rec, old_paren, new_paren in plans:
        path = os.path.join(vault, rel)
        lineno = rec.raw.get("header_line")
        lines = edits.setdefault(path, open(path, encoding="utf-8").read().splitlines())
        old_line = lines[lineno]
        if old_line.count(old_paren) != 1:
            failed.append((rel, rec.id, "parenthetical not uniquely located"))
            continue
        new_line = old_line.replace(old_paren, new_paren, 1)
        bad = verify(vault, path, old_line, new_line, rec)
        if bad:
            failed.append((rel, rec.id, bad))
            continue
        if not content_preserved(old_paren, new_paren):
            failed.append((rel, rec.id, "non-date content changed"))
            continue
        lines[lineno] = new_line
        if not args.limit or shown < args.limit:
            shown += 1
            print(f"  {rel}  {rec.id}\n      - ({old_paren})\n      + ({new_paren})")

    print("\n=== PHASE B1 (R4: tag a terse header's vital fields) ===")
    print(f"  entries rewritten:      {len(plans) - len(failed)}")
    print(f"  REFUSED (human review): {len(refusals)}")
    print(f"  FAILED the invariant:   {len(failed)}   [must be 0 to apply]")
    for rel, pid, why in failed[:20]:
        print(f"      {rel}  {pid}  {why}")

    if args.refusals:
        print("\n=== REFUSALS ===")
        c = {}
        for _r, _p, _f, why in refusals:
            c[why] = c.get(why, 0) + 1
        for why, n in sorted(c.items(), key=lambda x: -x[1]):
            print(f"  {n:4d}  {why}")

    if args.apply:
        if failed:
            print("\nREFUSING TO APPLY: the invariant failed above.")
            sys.exit(1)
        for path, lines in edits.items():
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        print(f"\nAPPLIED to {len(edits)} file(s).")
    else:
        print("\nDry run. Re-run with --apply to write.")


# --------------------------------------------------------------------------- #
# PHASE A3 — the two residue classes the operator decided (23 JUL 2026):
# "use the GEDCOM 7 formats". OS/NS takes the conforming date, a medieval slash
# becomes BET.
# --------------------------------------------------------------------------- #

# ⚠ THE TRAP: both classes are "YYYY/YYYY", and one of them is CONSECUTIVE.
# `944/945` is a 10th-century "one year or the other" span, but it is also
# consecutive, so split_dual_year would happily read it as an Old Style/New Style
# dual and silently resolve it to 945. The discriminator is the CALENDAR, not the
# arithmetic: an OS/NS dual year can only arise for a date between 1 January and
# 24 March, because that is the window in which the Old Style year had not yet
# rolled over. So a dual needs a DAY and a JAN/FEB/MAR month; a bare year pair is
# a span. `2 APR c.747/748` is April, so it is a span too, not a dual.
_OSNS_MONTHS = ("JAN", "FEB", "MAR")
_DUAL_SHAPE = re.compile(r"\A(?:ABT|EST|CAL|BEF|AFT)?\s*\d{1,2}\s+([A-Z]{3,9})\.?\s+"
                         r"\d{3,4}/\d{1,4}\Z", re.I)
# A medieval span: an optional approximation, then YEAR/YEAR and nothing else.
_SPAN_SHAPE = re.compile(r"\A(?:c\.?|ca\.?|~|abt\.?|about)?\s*"
                         r"(\d{3,4})\s*/\s*(\d{1,4})\Z", re.I)


def propose_dual_year(tag, slot):
    """`b. 6 JAN 1743/4` -> `b. 6 JAN 1744` (the NEW STYLE year, per GEDCOM 7)."""
    raw = H.EMPHASIS.sub("", slot).strip()
    date_part, place = _split_place(raw)
    m = _DUAL_SHAPE.match(date_part)
    if not m or m.group(1)[:3].upper() not in _OSNS_MONTHS:
        return None
    got = G.split_dual_year(date_part)
    if not got:
        return None
    value, _phrase, residue = got
    if residue.strip() or not G.is_valid(value):
        return None
    return f"{tag} {value}" + (f", {place}" if place else "")


def _expand(lo, hi):
    """'985','990' -> 990.  '1699','1700' -> 1700.  '1743','4' -> 1744."""
    if len(hi) >= len(lo):
        return int(hi)
    return int(lo[: len(lo) - len(hi)] + hi)


def propose_medieval_span(tag, slot):
    """`b. c.985/990` -> `b. BET 985 AND 990` (operator decision, 23 JUL 2026).

    The circa is DROPPED rather than kept: GEDCOM 7's `BET` takes plain dates, and
    the uncertainty the `c.` expressed is precisely what the span now states.
    """
    raw = H.EMPHASIS.sub("", slot).strip()
    date_part, place = _split_place(raw)
    m = _SPAN_SHAPE.match(date_part)
    if not m:
        return None
    lo, hi = m.group(1), _expand(m.group(1), m.group(2))
    if hi <= int(lo):
        return None                      # not an ascending span; leave it alone
    value = f"BET {int(lo)} AND {hi}"
    if not G.is_valid(value):
        return None
    return f"{tag} {value}" + (f", {place}" if place else "")

if __name__ == "__main__":
    main()
