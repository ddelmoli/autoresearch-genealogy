#!/usr/bin/env python3
"""
FamilySearch PID liveness / identity sweep.

The contributor-change Watchlist (vault/Watchlist.md) deep-watches ~two dozen
hand-picked profiles. But the vault cites ~900 FS PIDs, and PID rot can hit ANY
of them — e.g. a cited profile XXXX-XXX ("John Doe") silently became a different
person after an FS merge, and another YYYY-YYY became an empty "[Unknown Name]"
stub (tracked as an Open_Question). Those were caught only incidentally by a
source-harvest re-read, NOT by the Watchlist.

This sweep generalizes the tripwire to the WHOLE tree with a CHEAP check: does
each PID still resolve to a person whose NAME (and roughly, birth year) matches
the vault? No change-log diffing — just the FS person-page <title>, which is
"<Name> (<birth>–<death>) • Person • Family Tree".

FS person pages need the operator's logged-in Chrome, so this script does NOT
fetch them itself. It is the vault-side half of a two-step flow:

  1. EMIT a worklist of PIDs + expected name/birth-year:
       python3 scripts/liveness_sweep.py --emit --confidence S --out /tmp/targets.json
     (filters: --confidence S/M/Sp/U, --region Italian/Colonial/..., --gen-range 3-5, --limit N)

  2. Claude-in-Chrome navigates each PID's /tree/person/details/<PID> and records
     document.title, producing an "observed" JSON: { "<PID>": "<title string>", ... }

  3. CHECK the observed titles against the vault expectations:
       python3 scripts/liveness_sweep.py --check /tmp/observed.json
     Classifies each PID: OK / NAME_VARIANT / YEAR_DRIFT / NAME_MISMATCH / EMPTY /
     UNRENDERED / UNKNOWN_PID. Exit 2 if any hard flags (NAME_MISMATCH/EMPTY) are found.

This file does NOT edit anything. NAME_MISMATCH + EMPTY are the rot signals;
YEAR_DRIFT and NAME_VARIANT are advisory. NAME_VARIANT = the name tokens didn't
match but birth years do (and death years don't conflict) — almost always the SAME
person under a name variant (Gaelic↔anglicized "Duncan"/"Donnchad", maiden/married,
extra descriptors), not rot. YEAR_DRIFT is often a legit FS refinement (~1510 -> 1513).
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

import shard_manifest
import gen_person_index as G
import vault_config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
# | Name | Gen | Born | Died | FS PID | Notes |
PI_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([A-Z0-9]{4}-[A-Z0-9]{3})\s*\|\s*([^|]*?)\s*\|\s*$"
)
SECTION_HDR_RE = re.compile(r"^##\s+(\S.*?)\s*$")
APPENDIX_RE = re.compile(r"^##\s+Appendix")

# Honorifics / particles to drop before comparing name tokens.
STOP = {
    "lady", "sir", "esq", "esquire", "jr", "sr", "capt", "captain", "rev",
    "dr", "mr", "mrs", "miss", "the", "of", "de", "von", "van", "di", "del",
    "i", "ii", "iii", "iv", "v", "lord", "dame", "hon",
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def name_tokens(name):
    s = strip_accents(name).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    toks = [t for t in s.split() if t and t not in STOP]
    return toks


def first_year(s):
    # 3-4 digit years so zero-padded medieval dates ("0836") and pre-1000 years parse.
    m = re.search(r"\b(\d{3,4})\b", s or "")
    return int(m.group(1)) if m else None


def lifespan_years(s):
    """All 3-4 digit years in a lifespan string, in order: [birth, death?]."""
    return [int(y) for y in re.findall(r"\b(\d{3,4})\b", s or "")]


def levenshtein(a, b, cap=3):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def token_matches(vault_tok, fs_toks):
    """Fuzzy: exact, shared 4-char prefix, or Levenshtein<=2 (variant spellings)."""
    for ft in fs_toks:
        if vault_tok == ft:
            return True
        if len(vault_tok) >= 4 and len(ft) >= 4 and vault_tok[:4] == ft[:4]:
            return True
        if levenshtein(vault_tok, ft, cap=2) <= 2:
            return True
    return False


def parse_title(title):
    """Return (name, birth_year, death_year, kind). kind: 'normal' | 'empty' | 'unrendered'."""
    if not title:
        return ("", None, None, "unrendered")
    t = title.strip()
    # Pages that didn't render the SPA, or non-person pages.
    if t in ("FamilySearch.org", "All Changes") or "•" not in t:
        return ("", None, None, "unrendered")
    # Strip the trailing " • Person • Family Tree" / " • Change Log • ..." segments.
    head = t.split("•")[0].strip()
    if re.search(r"unknown name", head, re.IGNORECASE):
        return (head, None, None, "empty")
    # head looks like "Name (1513–1586)" / "Name (1914–Deceased)" / "Name (UNKNOWN)" / "Name"
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", head)
    if m:
        nm = m.group(1).strip()
        years = lifespan_years(m.group(2))
        birth = years[0] if years else None
        death = years[1] if len(years) >= 2 else None
        if re.search(r"unknown", m.group(2), re.IGNORECASE) and not years:
            # "(UNKNOWN)" lifespan but a real name -> treat as normal name, no years
            return (nm, None, None, "normal")
        return (nm, birth, death, "normal")
    return (head, None, None, "normal")


def _ylabel(name, birth, death):
    """'Name b.1631/d.1716' for the NAME_VARIANT corroboration display."""
    bits = []
    if birth is not None:
        bits.append(f"b.{birth}")
    if death is not None:
        bits.append(f"d.{death}")
    return f"{name} ({'/'.join(bits)})" if bits else name


def parse_person_index():
    """Yield dicts {pid, name, gen, born_year, died_year, confidence, section}.

    Sourced from the NARRATIVES via gen_person_index.parse_narrative() — each
    entry's bold-name header + `- meta:` block (Person_Index.md retired; see memory
    project_person_index_retirement). Only FS-PID-bearing entries are emitted (the
    sweep visits /tree/person/details/<PID>). `section` is the narrative file
    basename without `.md` (region_of() classifies it via the shard manifest)."""
    rows, seen = [], set()
    for e in G.parse_narrative():
        pid = e["pid"]
        if not pid or pid in seen:   # first occurrence wins (PID can be dup-flagged)
            continue
        seen.add(pid)
        section = e["file"][:-3] if e["file"].endswith(".md") else e["file"]
        rows.append({
            "pid": pid,
            "name": e["name"].strip("* "),
            "gen": e["gen"],
            "born_year": first_year(e["born"]),
            "died_year": first_year(e["died"]),
            "confidence": e["tier"] or "U",
            "section": section,
        })
    return rows


_MANIFEST = None


def region_of(section):
    """Classify a Person_Index section header into a region via the optional
    shard manifest in Family_Tree.md (see shard_manifest.py). Loaded once and
    cached. Projects without a manifest fall back to a generic label."""
    global _MANIFEST
    if _MANIFEST is None:
        _MANIFEST = shard_manifest.load_shard_manifest(VAULT)
    return shard_manifest.region_for(section, _MANIFEST)


def apply_filters(rows, args):
    lo = hi = None
    if args.gen_range:
        a, b = args.gen_range.split("-")
        lo, hi = int(a), int(b)
    out = []
    for r in rows:
        if args.confidence and r["confidence"] != args.confidence:
            continue
        if args.region and args.region.lower() not in region_of(r["section"]).lower():
            continue
        if lo is not None and (r["gen"] is None or r["gen"] < lo or r["gen"] > hi):
            continue
        out.append(r)
    out.sort(key=lambda r: (r["gen"] if r["gen"] is not None else 999, r["pid"]))
    if args.limit:
        out = out[: args.limit]
    return out


def cmd_emit(args):
    rows = apply_filters(parse_person_index(), args)
    payload = [{"pid": r["pid"], "name": r["name"], "born_year": r["born_year"],
                "gen": r["gen"], "confidence": r["confidence"], "region": region_of(r["section"])}
               for r in rows]
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"Emitted {len(payload)} target PIDs -> {args.out}")
        print("Next: capture each PID's FS /details title into an observed JSON {pid: title}, "
              "then run --check.")
    else:
        print(text)
    return 0


def cmd_check(args):
    with open(args.check) as f:
        observed = json.load(f)
    # Accept {pid: title} or [{pid, title}].
    if isinstance(observed, list):
        observed = {o["pid"]: o.get("title", "") for o in observed}

    idx = {r["pid"]: r for r in parse_person_index()}
    buckets = defaultdict(list)

    for pid, title in observed.items():
        vault = idx.get(pid)
        if not vault:
            buckets["UNKNOWN_PID"].append((pid, title, None))
            continue
        fs_name, fs_year, fs_death, kind = parse_title(title)
        if kind == "unrendered":
            buckets["UNRENDERED"].append((pid, vault["name"], fs_name or title))
            continue
        if kind == "empty":
            buckets["EMPTY"].append((pid, vault["name"], fs_name))
            continue
        v_toks = name_tokens(vault["name"])
        f_toks = name_tokens(fs_name)
        # Name match if the vault surname (last token) OR given (first token) matches.
        name_ok = False
        if v_toks and f_toks:
            surname_ok = token_matches(v_toks[-1], f_toks)
            given_ok = token_matches(v_toks[0], f_toks)
            name_ok = surname_ok or given_ok
        vy, fy = vault["born_year"], fs_year
        vd, fd = vault.get("died_year"), fs_death
        if not name_ok:
            # A name-token mismatch is usually rot — BUT if birth years match (and death
            # years don't conflict), it's almost always the SAME person under a name
            # variant (Gaelic↔anglicized "Duncan"/"Donnchad", "Stanisława"/"Stella",
            # married vs maiden, extra descriptors). Downgrade those to advisory.
            birth_match = vy is not None and fy is not None and abs(vy - fy) <= args.year_tol
            death_conflict = vd is not None and fd is not None and abs(vd - fd) > args.year_tol
            if birth_match and not death_conflict:
                buckets["NAME_VARIANT"].append(
                    (pid, _ylabel(vault["name"], vy, vd), _ylabel(fs_name, fy, fd)))
            else:
                buckets["NAME_MISMATCH"].append((pid, vault["name"], fs_name))
            continue
        if vy and fy and abs(vy - fy) > args.year_tol:
            buckets["YEAR_DRIFT"].append((pid, f'{vault["name"]} b.{vy}', f"{fs_name} b.{fy}"))
            continue
        buckets["OK"].append((pid, vault["name"], fs_name))

    order = ["EMPTY", "NAME_MISMATCH", "UNKNOWN_PID", "NAME_VARIANT", "YEAR_DRIFT", "UNRENDERED", "OK"]
    print("=== FS PID liveness sweep — results ===")
    print(f"Checked {len(observed)} observed titles "
          f"(year tolerance ±{args.year_tol})\n")
    hard = 0
    for cat in order:
        items = buckets[cat]
        if not items:
            continue
        if cat in ("EMPTY", "NAME_MISMATCH"):
            hard += len(items)
        tag = {
            "EMPTY": "[!!] EMPTY / DELETED STUB (rot — re-point)",
            "NAME_MISMATCH": "[!!] NAME MISMATCH (rot — wrong/merged PID; re-point)",
            "UNKNOWN_PID": "[?] PID not in Person_Index (stale observed list?)",
            "NAME_VARIANT": "[~] NAME VARIANT, years corroborate (advisory — same person, e.g. Gaelic/anglicized, maiden/married)",
            "YEAR_DRIFT": "[~] BIRTH-YEAR DRIFT (advisory — verify; may be a refinement)",
            "UNRENDERED": "[.] page did not render (retry capture)",
            "OK": "[ok] resolves to the expected person",
        }[cat]
        print(f"{tag}: {len(items)}")
        show = items if cat != "OK" else items[: args.show_ok]
        for pid, vname, fname in show:
            print(f"   {pid:<10} vault: {str(vname)[:42]:<42} FS: {fname}")
        if cat == "OK" and len(items) > args.show_ok:
            print(f"   ... and {len(items) - args.show_ok} more OK")
        print()

    if hard:
        print(f"RESULT: {hard} PID(s) need re-pointing (EMPTY/NAME_MISMATCH). "
              "Fix via the daughter/spouse-walk method (Open_Questions Q104).")
        return 2
    print("RESULT: no rot detected (no EMPTY/NAME_MISMATCH).")
    return 0


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description="FamilySearch PID liveness / identity sweep (vault side).")
    sub = ap.add_mutually_exclusive_group(required=True)
    sub.add_argument("--emit", action="store_true", help="Emit a worklist of PIDs + expected name/year.")
    sub.add_argument("--check", metavar="OBSERVED_JSON", help="Compare observed FS titles {pid: title} to the vault.")
    ap.add_argument("--confidence", help="Filter (emit): S/M/Sp/U.")
    ap.add_argument("--region", help="Filter (emit): substring of a region label from the Family_Tree.md manifest.")
    ap.add_argument("--gen-range", help="Filter (emit): e.g. 3-8.")
    ap.add_argument("--limit", type=int, help="Filter (emit): cap count.")
    ap.add_argument("--out", help="Emit target: write JSON here instead of stdout.")
    ap.add_argument("--year-tol", type=int, default=8, help="Check: birth-year drift tolerance (default 8).")
    ap.add_argument("--show-ok", type=int, default=0, help="Check: how many OK rows to print (default 0).")
    args = ap.parse_args()

    if args.emit:
        return cmd_emit(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
