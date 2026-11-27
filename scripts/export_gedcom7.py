#!/usr/bin/env python3
"""Export every person in a vault to a GEDCOM 7.0 file.

Reads people only through the model-agnostic seam (`person_store.iter_people`),
so it works for both person models. What goes into the file:

  INDI   one per vault person: NAME, SEX (only a RECORDED `sex` meta value; a
         guess is never written), BIRT/DEAT with DATE (the GEDCOM 7 DateValue
         field, authoritative) or a PHRASE, and PLAC taken from the header's
         "date, place" display slot with its bracketed research annotation
         removed; REFN = the vault id; EXID = live external
         ids (FamilySearch, WikiTree); a NOTE with the evidence tier and profile
         status.
  FAM    built from the edges: one family per distinct parent set named by a
         child's `parents`, plus one per `spouse` pair not already covered. A
         parent edge still carrying `?` (not yet FS-confirmed) is exported with a
         NOTE saying so, never silently promoted.
  SOUR   one record per distinct source LOCATOR cited in a person's rule-8
         `- **Sources**` bullet: TITL is the sub-bullet's record description,
         REFN carries the `host:locator` token itself. Each citing person gets a
         `1 SOUR @S..@` citation, with `2 PAGE` only where that entry words the
         record differently from the SOUR record's own TITL. A locator cited by a
         whole household therefore resolves to ONE shared SOUR record. The
         include/exclude POLICY is not re-decided here: the locators come from
         `harvest_sources`, which owns rule 8.

The evidence tier is NOT a source. It is a confidence label and it stays in the
NOTE where it has always been; promoting it to a SOUR claim would write exactly
the guess this exporter refuses to write elsewhere. A person with no cited
locators gets no SOUR, and that absence is the honest reading.

Privacy: a person whose life_status is `living` or `unknown` is exported with
`RESN PRIVACY`, name, sex and family links only. Their dates, places, external
ids AND source locators are withheld unless `--include-living-details` is
passed: a locator is a record identifier for a named person, so it sits on the
withheld side of that line with the dates it would otherwise reveal. Rejected
external ids (`~PID`) and the `TBD`/`none` states are never exported.

Usage:
  AUTORESEARCH_VAULT=/path/to/vault python3 scripts/export_gedcom7.py [--out FILE]
      [--include-living-details] [--check-only]

The default output is <vault>/exports/<vault-name>-<YYYY-MM-DD>.ged. The file
holds real people: it belongs with the vault, never in this repository.
"""
import argparse
import datetime
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdate  # noqa: E402
import harvest_sources as hs  # noqa: E402
import person_store as ps  # noqa: E402
import vault_config as vc  # noqa: E402

EXID_TYPES = {
    "fs": "https://www.familysearch.org/tree/person/details/",
    "wt": "https://www.wikitree.com/wiki/",
}
PRIVATE = {"living", "unknown"}
LINE_RE = re.compile(r"^(0|[1-9][0-9]*) (?:(@[A-Z0-9_]+@) )?([A-Z_][A-Z0-9_]*)(?: (.*))?$")


def xref(kind, pid):
    return "@%s%s@" % (kind, re.sub(r"[^A-Z0-9]", "", pid.upper()))


def esc(text):
    """GEDCOM 7: a payload starting with '@' doubles it; strip control chars."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text)).strip()
    return "@" + text if text.startswith("@") else text


def gedcom_name(display):
    """`Given /Surname/` from a display name. The surname is the last word that
    is not in brackets or parentheses; the rest stays as written."""
    clean = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", display)
    clean = re.sub(r"[*`]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" ,")
    words = clean.split(" ")
    if len(words) >= 2 and re.match(r"^[^\W\d_][\w'\-.]*$", words[-1]):
        return "%s /%s/" % (" ".join(words[:-1]), words[-1])
    return clean or "Unknown"


# ⚠ CALL THIS ON `person_store.header_vitals_unannotated`, NEVER ON
# `raw['header_vitals']`. The latter is verbatim by design (it is the DATE_DRIFT
# comparison target), so a header's bracketed annotation reaches it as bare prose
# welded onto the town — `Othertown [age 22, cert. N°534]` arriving as
# `Othertown age 22, cert. N°534`. No amount of cutting here recovers the boundary,
# and on an annotation containing a `;` the real place tail is already gone: see
# that function for the worked case. Strip the brackets, then split.
#
# ⚠ THE LIST BELOW IS WHAT SURVIVES THAT, and it is now UNBRACKETED annotation
# only. Measured over 1,620 place halves of the reference vault once the brackets
# are stripped upstream: dash 10, `bapt./bur./chr.` 6, `, age` 6, ` per ` 3,
# `primary` 2, `CONFIRMED` 1 — and `⚠` and `⭐` fire ZERO times, because those two
# only ever matched bracket contents. They are dropped rather than kept as dead
# alternatives; everything left is a real vault spelling with a row behind it.
#
# ⚠ `\s\(` is a TRUNCATION and is correct as one. `_parse_vitals` matches the slot
# with `[^;)]`, so a parenthetical in a header is ALWAYS already cut at its `)` by
# the time it gets here (`Someland (Old Empire`, `Somewhereton (St Mary parish`).
# There is no balanced span left to remove, so removing the span and truncating at
# the `(` give the same answer on every row in the corpus.
ANNOTATION = re.compile(
    r"\s+[—–-]{1,2}\s+|\s\(|\s+(?:bapt?\.|bur\.|chr\.)\s|,\s*age\s|\s+per\s"
    r"|\s+primary\b|\s+CONFIRMED\b")

# ⚠ A STATED ABSENCE IS NOT A PLACE. The vault writes the gap honestly in the slot
# where the place would go — `b. ABT 1756, origin unknown [the prior "of
# Someplace, Oldshire" was a mis-link artifact …]` — and a GEDCOM consumer reading
# that as a PLAC says "born in: origin unknown". Four lines in the reference vault
# (`origin unknown`, `parish unknown`, `place uncertain`, `location unknown`), one
# of which only appeared once the brackets stopped burying it. Matched whole, never
# as a substring: `Unknown` is a real surname and `Mount Unknown` would be a place.
NO_PLACE = re.compile(
    r"^(?:origin|location|parish|place|town|county|birthplace)?\s*"
    r"(?:unknown|uncertain|unclear|not known|tbd|n/?a)$", re.I)


def place_of(header_value):
    """The PLACE half of a header `date, place` slot, or ''.

    Takes a slot from `person_store.header_vitals_unannotated`, not from
    `raw['header_vitals']`; see the note above."""
    if not header_value or "," not in header_value:
        return ""
    place = header_value.split(",", 1)[1]
    # What is left of the slot is display prose: cut it at the first annotation.
    place = ANNOTATION.split(place, maxsplit=1)[0]
    place = re.sub(r"\s+", " ", place)
    place = re.sub(r"\s+([,;])", r"\1", place).strip(" ,;:")
    if not place or NO_PLACE.match(place) or re.search(r"\b(FS|PID|ARK)\b", place):
        return ""
    return place


ABSENT = re.compile(r"^\s*(unknown|unk\.?|\?+|deceased|living|n/?a)\s*(,|$)", re.I)


def event_lines(tag, date, phrase, place):
    out = []
    if date and ABSENT.match(date):
        date = None
    if date and not gdate.is_valid(date):
        value, residue = gdate.normalise(date)
        rest = date.strip()[len(value):] if value and date.strip().upper().startswith(value.upper()) else None
        if value and (not residue.strip(" ,;") or (rest is not None and rest.lstrip().startswith(","))):
            if not (rest is not None and rest.lstrip().startswith(",")) and date.strip().upper() != value.upper():
                phrase = phrase or date   # keep the original wording when it was not merely date + place
            date = value
    if not (date or phrase or place):
        return out
    out.append("1 %s" % tag)
    if date and gdate.is_valid(date):
        out.append("2 DATE %s" % esc(date))
        if phrase:
            out.append("3 PHRASE %s" % esc(phrase))
    elif date or phrase:
        out.append("2 DATE")
        out.append("3 PHRASE %s" % esc(phrase or date))
    if place:
        out.append("2 PLAC %s" % esc(place))
    return out


# ── SOURCES (rule 8) ───────────────────────────────────────────────────────────
#
# ** THE POLICY IS NOT RE-DECIDED HERE. ** Which locator counts as a source is
# rule 8, and rule 8's one implementation is `harvest_sources`: the include limbs,
# the `~` negation, the title screens and the Sources-bullet boundary all come
# from there. This file only shapes what those helpers return into GEDCOM. A
# second opinion about what a source is would be a second policy.
#
# ⚠ NEGATION IS RESOLVED OVER THE WHOLE BODY *BEFORE* THE BODY IS NARROWED to the
# Sources bullet, the ordering `count_records_strict` documents: the `~` is almost
# never written inside the Sources bullet, it is written where the rejection is
# explained (a write-back queue bullet, an audit note, a `Named-in` block), so
# narrowing first throws the negation away and re-credits the exact locators the
# vault did the work to reject.
#
# ⚠ TWO SCREENS ARE DELIBERATELY NOT APPLIED as exclusions, and both of their own
# docstrings say why. `is_memorial_collection` decides the CLASS and not the TIER,
# and a tier-1 photographed stone IS a record (rule 8 limb (e)). The obituary
# screen is, in its own words, "safe as a screen and unsafe as a verdict": applied
# as one on the reference vault it fires on six Sources lines of which THREE are
# real records, among them a state birth index and a government interment register
# that limb (e) explicitly counts, because the stem `obituar` turns up elsewhere in
# the same prose line. Both classes are already kept out by the `~` the vault
# writes when it screens them at harvest time, which is the authoritative
# mechanism; a false positive here would destroy a real record for nothing.
SOURCE_SEP = re.compile(r"\s+[\u2014\u2013]\s+|\s+--\s+")
EXCLUDED_SCREENS = frozenset(("book", "reference-c", "reference-d", "analysis-artifact"))
SOURCE_DESC_MAX = 160


def _close_parens(text):
    """Drop a trailing parenthetical the length cap or the dash split cut open."""
    while text.count("(") > text.count(")"):
        text = text[:text.rindex("(")].rstrip(" ,;:")
    return text


def record_description(line):
    """The record-NAME half of a rule-8 Sources sub-bullet, or ''.

    The grammar is `- <what the record is> — <host:locator>, <host:locator>`, so
    the description is everything before the first dash separator.

    ⚠ A BARE LOCATOR IS NOT A DESCRIPTION. Rule 8 says to name the record and
    never to cite the locator FORM, so a sub-bullet that is only its locator (the
    tail of an un-narrated harvest) describes nothing: every locator token is
    removed before the remainder is judged, and `1 TITL fs:1:1:XXXX-XXX` never
    reaches the file. A locator says where; only the description says what."""
    text = re.sub(r"^\s*[-*+]\s+", "", (line or "").strip())
    text = SOURCE_SEP.split(text)[0]
    text = re.sub(r"\*\*|[*`_]", "", text)
    text = " ".join(w for w in text.split() if not hs.is_record_locator(
        hs.strip_trailing_markup(w).lstrip("~")))
    text = re.sub(r"^[^\w(\"]+", "", text)        # leading emphasis glyph or dash
    text = re.sub(r"\s+", " ", text).strip(" ,;:.()\u2014\u2013-")
    if not re.search(r"\w", text):
        return ""
    if len(text) > SOURCE_DESC_MAX:
        text = text[:SOURCE_DESC_MAX].rsplit(" ", 1)[0] + "..."
    return _close_parens(text)


def person_sources(body):
    """[(locator, description)] for one entry body: the include-limb record
    locators its Sources bullet cites, in order, each locator once."""
    if not body:
        return []
    bullet = hs.sources_bullet_text(hs.strip_negated_locators(body))
    out, seen = [], set()
    for ln in bullet.splitlines():
        locators = hs.record_locators(ln)
        if not locators:
            continue
        # The bullet's own header line is prose about the harvest, not a record.
        desc = "" if hs.SOURCES_BULLET_RE.search(ln) else record_description(ln)
        if desc and EXCLUDED_SCREENS & set(hs.screen_title(desc)):
            continue
        for tok in locators:
            if tok not in seen:
                seen.add(tok)
                out.append((tok, desc))
    return out


def host_labels(vault):
    """Short host id -> registry label. Registering a host is the whole job: this
    reads the registry, never a prose list."""
    out = {}
    try:
        # BaseException for the reason harvest_sources documents: a config read
        # can signal "no vault" with SystemExit, which is not an Exception. A
        # missing label costs a NOTE; it must never cost the export.
        hosts = vc.get_hosts(vault) or {}
    except BaseException:
        return out
    for key, spec in hosts.items():
        spec = spec or {}
        out[str(spec.get("short") or key).lower()] = str(spec.get("label") or key)
    return out


def strip_q(tok):
    return tok.rstrip("?")


def build(vault, include_living_details=False):
    people = OrderedDict()
    for rec in ps.iter_people(vault):
        if rec.id:
            people[rec.id] = rec

    # Families: a parent set (frozenset of ids) -> {partners, children[(id, unconfirmed)]}
    fams = OrderedDict()

    def fam_for(partners):
        key = frozenset(partners)
        if key not in fams:
            fams[key] = {"partners": sorted(key), "children": [], "unconfirmed": set()}
        return fams[key]

    for pid, rec in people.items():
        par = [t for t in (rec.parents or []) if strip_q(t) in people]
        if par:
            f = fam_for(strip_q(t) for t in par)
            f["children"].append((pid, any(t.endswith("?") for t in par)))
    for pid, rec in people.items():
        for t in rec.spouse or []:
            other = strip_q(t)
            if other in people and other != pid:
                f = fam_for([pid, other])
                if t.endswith("?"):
                    f["unconfirmed"].add("couple")

    fam_ids = {}
    for i, key in enumerate(fams, 1):
        fam_ids[key] = "@F%d@" % i

    famc = {}  # child id -> [(fam xref, unconfirmed)]
    fams_of = {}  # partner id -> [fam xref]
    for key, f in fams.items():
        fx = fam_ids[key]
        for p in f["partners"]:
            fams_of.setdefault(p, []).append(fx)
        for c, unconf in f["children"]:
            famc.setdefault(c, []).append((fx, unconf))

    today = datetime.date.today()
    lines = [
        "0 HEAD",
        "1 GEDC",
        "2 VERS 7.0",
        "1 SOUR autoresearch-genealogy",
        "2 NAME autoresearch-genealogy vault export",
        "1 DATE %s" % today.strftime("%d %b %Y").upper().lstrip("0"),
        "1 NOTE Exported from an autoresearch-genealogy vault. Vault ids are in REFN (TYPE autoresearch-vault-id). "
        "Living and unknown-status people carry RESN PRIVACY.",
    ]

    labels = host_labels(vault)
    sources = OrderedDict()   # locator -> {"xref", "titl"}

    def source_for(locator, desc):
        entry = sources.get(locator)
        if entry is None:
            entry = sources[locator] = {"xref": "@S%d@" % (len(sources) + 1), "titl": desc}
        elif desc and not entry["titl"]:
            entry["titl"] = desc   # first entry to NAME the record titles it
        return entry

    stats = {"indi": 0, "fam": len(fams), "private": 0, "birt": 0, "deat": 0,
             "unconfirmed_famc": 0, "sourced": 0, "citations": 0, "sour": 0}
    for pid, rec in people.items():
        private = (rec.life_status or "unknown") in PRIVATE
        hide = private and not include_living_details
        stats["indi"] += 1
        stats["private"] += private
        lines.append("0 %s INDI" % xref("I", pid))
        if private:
            lines.append("1 RESN PRIVACY")
        lines.append("1 NAME %s" % esc(gedcom_name(rec.name or pid)))
        sex = ps.sex(rec)
        if sex in ("M", "F", "X", "U"):
            lines.append("1 SEX %s" % sex)
        if not hide:
            hb, hd = ps.header_vitals_unannotated(rec)
            b = event_lines("BIRT", rec.born, rec.born_phrase, place_of(hb))
            d = event_lines("DEAT", rec.died, rec.died_phrase, place_of(hd))
            if not d and rec.life_status == "deceased":
                d = ["1 DEAT Y"]
            stats["birt"] += bool(b)
            stats["deat"] += bool(d) and d != ["1 DEAT Y"]
            lines += b + d
        for fx, unconf in famc.get(pid, []):
            lines.append("1 FAMC %s" % fx)
            if unconf:
                stats["unconfirmed_famc"] += 1
                lines.append("2 NOTE Parent link not yet confirmed (vault edge marked ?)")
        for fx in fams_of.get(pid, []):
            lines.append("1 FAMS %s" % fx)
        lines.append("1 REFN %s" % pid)
        lines.append("2 TYPE autoresearch-vault-id")
        if not hide:
            for host, uri in EXID_TYPES.items():
                val = (rec.external_ids or {}).get(host)
                live = ps.live_external_id(val) if val else None
                if live:
                    lines.append("1 EXID %s" % esc(live))
                    lines.append("2 TYPE %s" % uri)
        bits = []
        if rec.generation is not None:
            bits.append("generation %s" % rec.generation)
        if rec.evidence_tier:
            bits.append("evidence %s" % rec.evidence_tier.replace("_", " "))
        if rec.profile_status:
            bits.append("profile %s" % rec.profile_status)
        if bits:
            lines.append("1 NOTE Vault: %s" % "; ".join(bits))
        if not hide:
            # A locator is a record identifier for a named person: it is withheld
            # for a living or unknown-status person exactly as the dates are.
            cited = person_sources(ps.entry_text(rec))
            stats["sourced"] += bool(cited)
            stats["citations"] += len(cited)
            for locator, desc in cited:
                entry = source_for(locator, desc)
                lines.append("1 SOUR %s" % entry["xref"])
                if desc and desc != entry["titl"]:
                    # Only this entry's own wording of the record; the wording that
                    # titled the SOUR record is already on it.
                    lines.append("2 PAGE %s" % esc(desc))

    for key, f in fams.items():
        lines.append("0 %s FAM" % fam_ids[key])
        partners = f["partners"]
        sexes = {p: ps.sex(people[p]) for p in partners}
        husb = [p for p in partners if sexes[p] == "M"]
        wife = [p for p in partners if sexes[p] == "F"]
        rest = [p for p in partners if p not in husb and p not in wife]
        for p in rest:  # unrecorded sex: fill whichever slot is free
            (husb if not husb else wife).append(p)
        for p in husb[:1]:
            lines.append("1 HUSB %s" % xref("I", p))
        for p in wife[:1]:
            lines.append("1 WIFE %s" % xref("I", p))
        for p in (husb[1:] + wife[1:]):  # same-sex or >2 partners: keep as notes, not lost
            lines.append("1 NOTE Also a partner in this family: vault id %s" % p)
        for c, _u in f["children"]:
            lines.append("1 CHIL %s" % xref("I", c))
        if "couple" in f["unconfirmed"]:
            lines.append("1 NOTE Couple link not yet confirmed (vault edge marked ?)")

    stats["sour"] = len(sources)
    for locator, entry in sources.items():
        lines.append("0 %s SOUR" % entry["xref"])
        if entry["titl"]:
            lines.append("1 TITL %s" % esc(entry["titl"]))
        lines.append("1 REFN %s" % esc(locator))
        lines.append("2 TYPE autoresearch-source-locator")
        label = labels.get(locator.split(":", 1)[0].lower())
        if label:
            lines.append("1 NOTE Cited on %s." % esc(label))
    lines.append("0 TRLR")
    return lines, stats


def check(lines):
    """Structural check: line grammar, level steps, every pointer resolves."""
    errors, defined, used = [], set(), []
    prev = -1
    for n, line in enumerate(lines, 1):
        m = LINE_RE.match(line)
        if not m:
            errors.append("line %d: bad grammar: %r" % (n, line[:80]))
            continue
        lvl = int(m.group(1))
        if lvl > prev + 1:
            errors.append("line %d: level jumps %d -> %d" % (n, prev, lvl))
        prev = lvl
        if m.group(2):
            if m.group(2) in defined:
                errors.append("line %d: duplicate xref %s" % (n, m.group(2)))
            defined.add(m.group(2))
        val = m.group(4) or ""
        if re.fullmatch(r"@[A-Z0-9_]+@", val):
            used.append((n, val))
    for n, val in used:
        if val not in defined:
            errors.append("line %d: pointer %s does not resolve" % (n, val))
    if lines[0] != "0 HEAD" or lines[-1] != "0 TRLR":
        errors.append("missing HEAD or TRLR")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vault")
    ap.add_argument("--out")
    ap.add_argument("--include-living-details", action="store_true")
    ap.add_argument("--check-only", action="store_true", help="build and check, write nothing")
    a = ap.parse_args()
    vault = vc.resolve_vault(a.vault)
    lines, stats = build(vault, a.include_living_details)
    errors = check(lines)
    for e in errors[:20]:
        print("ERROR", e)
    print("individuals %(indi)d (private %(private)d), families %(fam)d, births %(birt)d, "
          "dated deaths %(deat)d, unconfirmed parent links %(unconfirmed_famc)d" % stats)
    print("sourced individuals %(sourced)d, source citations %(citations)d, "
          "SOUR records %(sour)d" % stats)
    print("structural errors: %d" % len(errors))
    if a.check_only or errors:
        return 1 if errors else 0
    out = a.out or os.path.join(vault, "exports", "%s-%s.ged" % (
        os.path.basename(os.path.normpath(vault)), datetime.date.today().isoformat()))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
