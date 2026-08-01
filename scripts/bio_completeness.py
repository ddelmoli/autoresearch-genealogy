#!/usr/bin/env python3
"""bio_completeness.py — how complete is each person's BIOGRAPHY, as opposed to how
many records they cite.

** WHY IT EXISTS (operator, 01 AUG 2026). ** The standing goal is "for every person in
the vault to have as complete a biographical entry as possible". Nothing measured that.
What the vault measured was:

  - the source census (SOURCE_GAP / LOW_COVERAGE / WELL_SOURCED) — a count of RECORDS,
  - `profile_status` — which resolves to "does this entry have a Sources bullet",
  - the frontier (SILENT / DECLARED) — a count of missing PARENT EDGES.

None of those is a biography. An entry with thirty census ARKs and no prose about the
person's life scores WELL_SOURCED and profile_status: complete, and is not finished
work by the stated goal.

** AND THE ONE THING THAT DID MEASURE IT WAS RETIRED THREE DAYS EARLIER. **
`keystone_report`'s LOAD x THIN measured whether an entry had been WRITTEN UP, and on
31 JUL 2026 (deferred_decisions 24) it was demoted out of the lane system for
"measuring whether an entry was WRITTEN UP rather than whether it is SOURCED". That
demotion was right about sourcing and wrong to leave nothing behind: write-up
completeness is a DIFFERENT axis, and against the goal above it is the primary one.
This module is that axis, restored and made explicit.

FACETS. Two groups, because they answer different questions.

  CORE — applies to essentially everybody, so an absence is a genuine gap:
    born, died, parents, spouse_or_children, sources
  LIFE — the texture that makes an entry a biography rather than a data row. These
    are NOT universally applicable (not everyone emigrated or left a will), so they
    are reported as ENRICHMENT, never scored as failures:
    occupation, residence, migration, military, probate, narrative

! THE LIFE FACETS ARE KEYWORD-DETECTED AND ARE THEREFORE A FLOOR, NOT A COUNT. An
entry that describes a trade without using any of the words below reads as having no
occupation. Treat a zero as "not detected", investigate the rows, and never quote
these as totals — the same discipline the (e) memorial policy needs for the same
reason: a bare fact in prose is invisible to a pattern.

USAGE
  python3 scripts/bio_completeness.py --summary
  python3 scripts/bio_completeness.py --worklist [--limit N] [--gen-range 3-8]
  python3 scripts/bio_completeness.py --json

Zero dependencies. Advisory: never blocks anything.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402
import person_store as PS  # noqa: E402

CORE = ("born", "died", "parents", "spouse_or_children", "sources")
LIFE = ("occupation", "residence", "migration", "military", "probate", "narrative")

OCCUPATION_RE = re.compile(
    r"\b(occupation|labou?rer|farmer|yeoman|weaver|butcher|miller|smith|carpenter|"
    r"mason|tailor|shoemaker|servant|clerk|merchant|mariner|seaman|husbandman|"
    r"agricola|contadino|muratore|schoolmaster|physician|attorney|minister|rector|"
    r"vicar|priest|soldier|peddler|tinsmith|glazier|baker|cooper|blacksmith)\b", re.I)
RESIDENCE_RE = re.compile(
    r"\b(resid\w+|of the parish|abode|lived at|removed to|settled (?:at|in)|"
    r"household|dwelling|street|farm at)\b", re.I)
MIGRATION_RE = re.compile(
    r"\b(emigrat\w+|immigrat\w+|naturaliz\w+|arrived|passenger|manifest|"
    r"port of|steamship|declaration of intention|petition for naturalization)\b", re.I)
MILITARY_RE = re.compile(
    r"\b(regiment|enlisted|draft (?:card|registration)|militia|company [A-K]\b|"
    r"war of 1812|civil war|revolutionary war|wwi|wwii|world war|veteran|"
    r"pension file|service record)\b", re.I)
PROBATE_RE = re.compile(
    r"\b(will (?:of|proved|dated)|probate|administration|inventory|testator|"
    r"bequeath\w*|letters of admin|estate of)\b", re.I)
SOURCES_RE = re.compile(r"^\s*-\s*\*\*(?:Sources|FS-attached sources)\*\*", re.M)
META_RE = re.compile(r"^\s*-\s*meta:.*$", re.M)

# Prose that is ABOUT the entry rather than about the person still counts as body
# text, so a length test alone would call a stub with three research notes a
# biography. Count only lines that are neither the meta block nor a Sources locator.
LOCATOR_LINE_RE = re.compile(r"^\s*-\s*~?[a-z]+:", re.I)


def narrative_lines(block: str) -> int:
    n = 0
    for ln in (block or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("**") or META_RE.match(ln) or LOCATOR_LINE_RE.match(ln):
            continue
        n += 1
    return n


def facets(rec, block, has_children):
    """Which facets this entry carries. Returns {facet: bool}."""
    body = block or ""
    f = {
        "born": bool(rec.born or rec.born_phrase),
        "died": bool(rec.died or rec.died_phrase),
        "parents": bool(rec.parents),
        "spouse_or_children": bool(rec.spouse) or has_children,
        "sources": bool(SOURCES_RE.search(body)),
        "occupation": bool(OCCUPATION_RE.search(body)),
        "residence": bool(RESIDENCE_RE.search(body)),
        "migration": bool(MIGRATION_RE.search(body)),
        "military": bool(MILITARY_RE.search(body)),
        "probate": bool(PROBATE_RE.search(body)),
        "narrative": narrative_lines(body) >= 4,
    }
    return f


def gather(vault, gen_lo=None, gen_hi=None):
    blocks = list(PS.iter_entry_blocks(vault))
    # who is named as somebody's parent
    parent_ids = set()
    for rec, _p, _i, _b in blocks:
        for t in list(rec.parents or []):
            parent_ids.add(str(t).strip().rstrip("?"))
    rows = []
    for rec, path, _i, block in blocks:
        if (rec.life_status or "") in ("living", "unknown"):
            continue  # not web-researched at all; a completeness caption cannot apply
        if gen_lo is not None:
            g = rec.generation
            if g is None or g < gen_lo or g > gen_hi:
                continue
        f = facets(rec, block, rec.id in parent_ids)
        rows.append({
            "id": rec.id, "name": rec.name, "gen": rec.generation,
            "file": os.path.basename(path or ""),
            "facets": f,
            "core": sum(1 for k in CORE if f[k]),
            "life": sum(1 for k in LIFE if f[k]),
        })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--heartbeat", action="store_true",
                    help="one line for the SessionStart banner")
    ap.add_argument("--worklist", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--gen-range", dest="gen_range", metavar="LO-HI")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    lo = hi = None
    if a.gen_range:
        lo, hi = (int(x) for x in a.gen_range.split("-", 1))
    rows = gather(vault, lo, hi)
    if not rows:
        print("bio_completeness: no rows")
        return 0

    if a.json:
        print(json.dumps(rows, indent=1, default=str))
        return 0

    if a.heartbeat:
        n = len(rows)
        comp = sum(1 for r in rows if r["core"] == len(CORE))
        thin = sum(1 for r in rows if r["core"] <= 2)
        life = Counter()
        for r in rows:
            for k in LIFE:
                if r["facets"][k]:
                    life[k] += 1
        print(f"BIO_COMPLETE {comp}/{n} ({comp*100//n}% carry all {len(CORE)} core "
              f"facets: born, died, parents, spouse/children, sources); BIO_THIN "
              f"{thin} (<=2); occupation {life['occupation']}, residence "
              f"{life['residence']}, migration {life['migration']} "
              f"[keyword-detected = a FLOOR, read the rows]")
        return 0

    if a.worklist:
        # thinnest first: fewest core facets, then fewest life facets, shallowest gen
        rows.sort(key=lambda r: (r["core"], r["life"],
                                 r["gen"] is None, r["gen"] or 0))
        print(f"=== BIO WORKLIST — thinnest biographies first ({len(rows)} scanned) ===")
        for r in rows[:a.limit]:
            missing = [k for k in CORE if not r["facets"][k]]
            print(f"  Gen {str(r['gen'] or '?'):>3}  {str(r['name'])[:38]:<40} "
                  f"core {r['core']}/{len(CORE)}  life {r['life']}/{len(LIFE)}"
                  + (f"  missing: {', '.join(missing)}" if missing else ""))
        if len(rows) > a.limit:
            print(f"  ... and {len(rows) - a.limit} more (--limit N)")
        return 0

    # summary (default)
    n = len(rows)
    core_dist = Counter(r["core"] for r in rows)
    facet_n = Counter()
    for r in rows:
        for k, v in r["facets"].items():
            if v:
                facet_n[k] += 1
    print(f"=== BIOGRAPHICAL COMPLETENESS — {n} researchable entries ===")
    print("\n  CORE facets (apply to essentially everyone; an absence is a real gap)")
    for k in CORE:
        print(f"    {k:<20} {facet_n[k]:>5}  ({facet_n[k]*100//n}%)")
    print("\n  LIFE facets (enrichment; keyword-detected, so a FLOOR not a count)")
    for k in LIFE:
        print(f"    {k:<20} {facet_n[k]:>5}  ({facet_n[k]*100//n}%)")
    print("\n  entries by CORE facets present:")
    for c in range(len(CORE) + 1):
        bar = "#" * (core_dist[c] // 20)
        print(f"    {c}/{len(CORE)}: {core_dist[c]:>5}  {bar}")
    complete = core_dist[len(CORE)]
    print(f"\n  BIO_COMPLETE (all {len(CORE)} core facets): {complete}  "
          f"({complete*100//n}%)")
    print(f"  BIO_THIN (<=2 core facets): {sum(core_dist[c] for c in range(3))}")
    print("\n  ! LIFE facets are keyword-detected. A zero means NOT DETECTED, not "
          "absent —\n    read the rows before quoting any of these as a total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
