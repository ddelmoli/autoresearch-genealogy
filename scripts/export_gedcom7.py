#!/usr/bin/env python3
"""Export every person in a vault to a GEDCOM 7.0 file.

Reads people only through the model-agnostic seam (`person_store.iter_people`),
so it works for both person models. What goes into the file:

  INDI   one per vault person: NAME, SEX (only a RECORDED `sex` meta value; a
         guess is never written), BIRT/DEAT with DATE (the GEDCOM 7 DateValue
         field, authoritative) or a PHRASE, and PLAC taken from the header's
         "date, place" display slot; REFN = the vault id; EXID = live external
         ids (FamilySearch, WikiTree); a NOTE with the evidence tier and profile
         status.
  FAM    built from the edges: one family per distinct parent set named by a
         child's `parents`, plus one per `spouse` pair not already covered. A
         parent edge still carrying `?` (not yet FS-confirmed) is exported with a
         NOTE saying so, never silently promoted.

Privacy: a person whose life_status is `living` or `unknown` is exported with
`RESN PRIVACY`, name, sex and family links only. Their dates, places and
external ids are withheld unless `--include-living-details` is passed. Rejected
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


def place_of(header_value):
    """The PLACE half of a header `date, place` slot, or ''."""
    if not header_value or "," not in header_value:
        return ""
    place = header_value.split(",", 1)[1]
    # The header slot is display prose: cut it at the first research annotation.
    place = re.split(r"\s+[—–-]{1,2}\s+|⚠|⭐|\s\(|\s+(?:bapt?\.|bur\.|chr\.)\s|,\s*age\s|\s+per\s|\s+primary\b|\s+CONFIRMED\b",
                     place, maxsplit=1)[0]
    place = re.sub(r"\s+", " ", place).strip(" ,;:")
    if not place or re.search(r"\b(FS|PID|ARK)\b", place):
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

    stats = {"indi": 0, "fam": len(fams), "private": 0, "birt": 0, "deat": 0, "unconfirmed_famc": 0}
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
            hv = (rec.raw or {}).get("header_vitals") if isinstance(rec.raw, dict) else None
            hb, hd = (hv or ("", ""))
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
