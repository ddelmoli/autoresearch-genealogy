#!/usr/bin/env python3
"""
gen_person_index.py — Phase 1 of the Person_Index retirement (see memory
project_person_index_retirement).

Generates a Person_Index-equivalent table from the Family_Tree*.md narratives,
treating the narrative as the source of truth. Each person's machine fields are
read from a `- meta:` block when present:

    - meta: FS: XXXX-XXX; tier: S; parents: [[Thomas_Smith]] (YYYY-YYY) + ...

Where a meta block is absent (during the transition) the generator falls back to
what the narrative ALONE provides — name, generation (### Generation N heading),
born/died (header parenthetical), and the header-parenthetical PID — and flags
the still-missing pieces (tier, and any PID not yet in the narrative) as gaps.

Modes:
  --check (default)  generate, diff vs the committed vault/Person_Index.md, and
                     print a migration dashboard (reproducible / needs-meta /
                     field-drift / index-only stubs / narrative-only). Exit 1 if
                     any hard drift (field mismatch on a reproducible row).
  --write FILE       write the generated table to FILE (preview; never overwrites
                     Person_Index.md unless FILE is that path AND --force given).
  --gap-report       list every entry whose meta block is missing tier/PID
                     (the Phase-1 authoring worklist).
  --limit N          cap sample output (default 25).

Read-only by default. Reuses harvest_pids (name matching) + tree_locator
(_is_person filter). Does NOT build parent edges — that is Phase 2 (FS walk).
"""
import re, glob, os, sys, argparse
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import vault_config
VAULT = vault_config.resolve_vault()
import harvest_pids as H
import tree_locator as TL

PID_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{3})\b")
SENTINEL = {"TBD", "none"}
GEN_HDR = re.compile(r"^#{1,4}\s+Generation\s+(\d+)", re.M | re.I)
# {0,8}: allow single-token given-name entries (wives recorded as "Sarah",
# "Katharine"). The is_person_entry() filter below rejects non-person bolds.
# name class includes [ ] ? so uncertain/placeholder surnames match
# ("Sarah [Alverson?] Ramsdell", "Phebe [surname unknown]", "Ann [Dixey]").
HDR = re.compile(
    r"^[\-\*\s]*\*\*([A-ZÀ-Ý][\w\.\-'À-ÿ\[\]?]+(?:\s+[\w\.\-'À-ÿ\[\]?]+){0,8})\*\*\s*\(([^)]{0,800})\)",
    re.M)
META = re.compile(r"^\s*-\s*meta:\s*(.+)$", re.M | re.I)
# A person entry is signalled by a PID, a relationship marker, OR a date in the
# parenthetical — date alone was missing spouse stubs like "(wife of X; FS: …)".
DATE_SIG = re.compile(r"\b\d{3,4}\b|\b[bdm]\.\s|born|died|bapt|chr\.", re.I)
REL_SIG = re.compile(r"\b(wife|husband|son|daughter|child|widow) of\b", re.I)
# A relational kinship phrase ("<kin> of <Name>" or "née <Name>") in the
# parenthetical also marks a person — covers no-date/no-PID stubs whose only signal
# is a relationship-to-anchor ("brother of X", "father of Y", "née Z").
# The "of"/"née" requirement is deliberate: a BARE kin word falsely promoted
# surname-distribution bullets like "<Surname> (Gen-9 wife <Forename>)".
KIN_SIG = re.compile(
    r"\b(?:father|mother|brother|sister|son|daughter|child|grand(?:father|mother|son|daughter)"
    r"|uncle|aunt|cousin|wife|husband|widow|niece|nephew)\s+of\b|\bn[ée]e\s+\w", re.I)
# single-token bolds that are section labels, not people
LABEL_DENY = {"note", "notes", "sources", "source", "parents", "married",
              "children", "background", "summary", "lineage", "researched",
              "primary", "document", "birth", "death", "overview", "scope"}
# document / record / institution words: if ANY name token is one of these, the
# bold is a source title, not a person ("Chronicle of <Abbey>", "Pipe Rolls").
DOC_DENY = {"chronicle", "chronicles", "register", "registers", "registration",
            "rolls", "roll", "calendar", "survey", "cartulary", "charter",
            "peerage", "visitation", "pedigree", "society", "order", "annals",
            "inquisition", "subsidy", "muster", "domesday", "doomsday", "fines",
            "patent", "abstract", "ledger", "pension", "payment", "passenger",
            "mayflower", "draft", "nara", "agad", "wwii", "archive", "archives",
            # note/hypothesis lead-ins that get bolded like a name
            "plausibly", "likely", "possibly", "probably", "father", "mother"}
# Maps every evidence-tier spelling to a compact internal code for the roster.
# v3 stores upstream's full values (strong_signal / moderate_signal / speculative);
# legacy stored S / M / Sp / U. `U` is retired in v3 (an unassessed entry simply
# has NO evidence_tier — it's profile_status: stub instead).
TIER_WORD = {"strong_signal": "S", "moderate_signal": "M", "speculative": "Sp",
             "strong": "S", "moderate": "M",
             "s": "S", "m": "M", "sp": "Sp", "u": "U"}


def is_person_entry(name, paren):
    """Broader than tree_locator._is_person: a person bold-name entry has a
    name that reads like a personal name (no embedded year, not a section label)
    AND a parenthetical carrying a PID, relationship marker, or date."""
    # strip bracketed uncertainty ("[surname unknown]", "[Alverson?]") before the
    # name-shape checks, so its lowercase words don't read as label tokens.
    name = re.sub(r"\s*\[[^\]]*\]\s*", " ", name).strip() or name
    if re.search(r"\d{4}", name):              # year in the name -> not a person
        return False
    if not TL._looks_like_name(name):          # lowercase-label tokens -> not a person
        return False
    toks = [t for t in re.split(r"[\s\-]", name.lower()) if t]
    if len(toks) == 1 and toks[0] in LABEL_DENY:
        return False
    if any(t in DOC_DENY for t in toks):       # source/document title, not a person
        return False
    return bool(PID_RE.search(paren) or REL_SIG.search(paren)
                or DATE_SIG.search(paren) or KIN_SIG.search(paren))


def _parse_flow_mapping(s):
    """Parse a YAML flow-mapping `{k: v, k: v}` to a dict, zero-dependency.

    The v3 meta block is a VALID YAML flow-mapping (so any YAML tool / merge-back
    reads it), but the local tooling must not hard-depend on PyYAML. If PyYAML is
    present we use it; otherwise this small reader handles the simple subset we
    emit (flat scalar values, optional quoting, ints). Values never contain an
    unquoted comma/brace (the emitter quotes any that would)."""
    s = s.strip()
    try:
        import yaml  # optional; used if installed
        return {str(k).lower(): v for k, v in (yaml.safe_load(s) or {}).items()}
    except ImportError:
        pass
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out, buf, depth, inq = [], "", 0, None
    for ch in s:                      # comma-split respecting quotes/brackets
        if inq:
            buf += ch
            if ch == inq:
                inq = None
        elif ch in "'\"":
            inq = ch; buf += ch
        elif ch in "[{":
            depth += 1; buf += ch
        elif ch in "]}":
            depth -= 1; buf += ch
        elif ch == "," and depth == 0:
            out.append(buf); buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    d = {}
    for part in out:
        k, _, v = part.partition(":")
        k, v = k.strip().lower(), v.strip()
        if len(v) >= 2 and v[0] in "'\"" and v[-1] == v[0]:
            v = v[1:-1]
        elif re.fullmatch(r"-?\d+", v):
            v = int(v)
        if k and v != "":
            d[k] = v
    return d


def parse_meta(block):
    """Return the meta dict from a `- meta:` line, or {}. Handles BOTH the v3
    YAML flow-mapping `- meta: {id: P-x, evidence_tier: strong_signal, ...}` and
    the legacy `;`-delimited `- meta: id: P-x; FS: ...; tier: ...` form, so reads
    are stable before / during / after the v3 migration."""
    m = META.search(block)
    if not m:
        return {}
    raw = m.group(1).strip()
    if raw.startswith("{"):
        return _parse_flow_mapping(raw)
    out = {}
    for part in raw.split(";"):
        k, _, v = part.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k and v:
            out[k] = v
    return out


def parse_vitals(paren):
    """Pull (born, died) display strings from a header parenthetical.
    Handles 'b. <date>, <place>; d. <date>, <place>' and '(1820-1890)' ranges."""
    born = died = ""
    # Require a real birth marker: "b." (with period), "born", "bapt", "chr." —
    # NOT a bare "b" (which matched "bef.", "bet.", "before" and grabbed a wrong year).
    bm = re.search(r"(?:\bb\.|\bborn\b|\bbapt|\bchr\.)\s*([^;)]*?)(?=;|\bd\.|\bdied\b|$)", paren, re.I)
    dm = re.search(r"(?:\bd\.|\bdied\b)\s*([^;)]*)", paren, re.I)
    if bm:
        born = bm.group(1).strip(" ,")
    if dm:
        died = dm.group(1).strip(" ,")
    if not born and not died:
        yrs = re.findall(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", paren)
        if yrs:
            born = yrs[0]
            if len(yrs) >= 2:
                died = yrs[-1]
    clean = lambda s: re.sub(r"[*\[\]`]", "", s).strip(" ,")
    return clean(born), clean(died)


def tier_norm(v):
    return TIER_WORD.get(v.strip().lower()) if v else None


BOLD = re.compile(r"^\s*[-*]*\s*\*\*(.+?)\*\*(.*)$")


def _vitals_paren(name, rest):
    """The vitals parenthetical = the first (...) after the bold name; if the bold
    swallowed it (legacy 'Name (vitals)' style), fall back to a paren in the name."""
    m = re.search(r"\(([^)]*)\)", rest)
    if m:
        return m.group(1)
    m = re.search(r"\(([^)]*)\)", name)
    return m.group(1) if m else ""


def parse_narrative():
    """Canonical person entries, META-ANCHORED. Now DELEGATES to the model-agnostic
    person_store seam (spec/optional-person-model, Spec 05): `person_store.iter_people`
    dispatches on the vault's `person_model` (narrative here) and returns the shared
    PersonRecord, which this maps to the legacy row-dict shape consumers expect
    (`id/name/file/gen/born/died/pid/tier/profile_status/life_status/block`). The
    narrative parsing primitives now live ONCE in person_store; this keeps its exact
    prior output (verified byte-identical on the live vault) while making every
    consumer of parse_narrative model-agnostic for free.

    Born/died come from the header's vitals paren; id/FS/tier/gen from the meta
    block; identity keys on the meta `id`. `block` is the raw meta line (buildout /
    build_edges re-parse it)."""
    import person_store as PS
    rows_all = []
    for r in PS.iter_people(VAULT):
        pid = r.external_ids.get("fs")
        if pid in SENTINEL or (pid and not PID_RE.fullmatch(str(pid))):
            pid = None
        rows_all.append(dict(
            id=r.id, name=r.name, file=r.source_file, gen=r.generation,
            born=r.born or "", died=r.died or "", pid=pid,
            # The HEADER parenthetical's vitals, alongside the authoritative field
            # (spec/structured-dates Spec 06). Two stores, one fact: `born`/`died`
            # are the machine value, `header_born`/`header_died` are what the human
            # display says, and DATE_DRIFT compares their YEARS. Consumers that want
            # the place still read the header — a date FIELD holds no place by design.
            header_born=(r.raw or {}).get("header_vitals", ("", ""))[0] or "",
            header_died=(r.raw or {}).get("header_vitals", ("", ""))[1] or "",
            # which date keys the meta block ACTUALLY carries — `born`/`died` above
            # fall back to the header, so they cannot answer "is there a field?"
            meta_date_keys=tuple((r.raw or {}).get("meta_date_keys") or ()),
            tier=tier_norm(r.evidence_tier),
            profile_status=r.profile_status, life_status=r.life_status,
            has_meta=True, block=(r.raw or {}).get("line", "")))

    # Dedup by the vault-owned id (unique per person). Idless rows (legacy, pre-mint)
    # fall back to a positional key so they aren't merged together.
    seen = {}
    for n, r in enumerate(rows_all):
        seen.setdefault(r["id"] or f"_noid_{n}", r)
    return list(seen.values())


def parse_index():
    # Person_Index.md was RETIRED (see memory project_person_index_retirement):
    # narratives + their `- meta:` blocks are the single source of truth, and the
    # gen-sorted roster is produced ON DEMAND by --write. If the file is absent the
    # migration-comparison modes (--check) simply have nothing to diff against; the
    # narrative-native modes (--write / --integrity / --gap-report) are unaffected.
    path = os.path.join(VAULT, "Person_Index.md")
    if not os.path.exists(path):
        return []
    rows = []
    for lineno, line in enumerate(open(path), 1):
        if line.startswith("## Appendix"):
            break
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.split("|")[1:-1]]
        if len(c) < 6 or c[0] in ("Name", "") or set(c[0]) <= set("-: "):
            continue
        name, gen, born, died, pid, notes = c[:6]
        rows.append(dict(name=name, gen=gen, born=born, died=died,
                         pid=pid if PID_RE.fullmatch(pid) else None,
                         notes=notes, tier=tier_from_notes(notes), lineno=lineno))
    return rows


def tier_from_notes(notes):
    head = notes.strip().split(";")[0].strip().lower()
    if head in TIER_WORD:
        return TIER_WORD[head]
    for w in ("strong", "moderate", "speculative"):
        if re.search(rf"\b{w}\b", notes, re.I):
            return TIER_WORD[w]
    return None


def yr(s):
    return H.extract_year(s or "")


def years_compatible(a, b, tol=1):
    """True if the year-sets of two date strings overlap or fall within tol.
    Handles ranges ('1810-1816', 'ABT 1634-1638') vs points so a value inside a
    range is not a false drift."""
    ya = [int(x) for x in re.findall(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", a or "")]
    yb = [int(x) for x in re.findall(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", b or "")]
    if not ya or not yb:
        return True   # can't compare -> not a drift
    la, ha, lb, hb = min(ya), max(ya), min(yb), max(yb)
    if la <= hb and lb <= ha:          # ranges overlap
        return True
    return min(abs(la - hb), abs(lb - ha)) <= tol


def build_pidmap(index_rows):
    m = {}
    for r in index_rows:
        if r["pid"]:
            m.setdefault(r["pid"], r)
    return m


def match(entry, index_rows, pidmap=None):
    # PID-first: an entry's own PID is the unambiguous key, resolving same-named
    # people (three same-named women, six same-named men in one parish) that
    # name+year cannot.
    ep = entry.get("pid")
    if ep and ep not in SENTINEL:
        pm = pidmap if pidmap is not None else build_pidmap(index_rows)
        if ep in pm:
            return pm[ep]
    ey = yr(entry["born"]) or yr(entry["died"])
    best = None
    for r in index_rows:
        kind = H.names_match(entry["name"], r["name"])
        if not kind:
            continue
        ry = yr(r["born"]) or yr(r["died"])
        if ey and ry and abs(ey - ry) > 4:
            continue
        score = (0 if kind == "exact" else 1, abs((ey or 0) - (ry or 0)) if ey and ry else 99)
        if best is None or score < best[0]:
            best = (score, r)
    return best[1] if best else None


def integrity_check(entries, args):
    """Narrative-native HARD invariants, post-Person_Index-retirement. Replaces
    the index drift-policing gate (duplicate_rows + harvest_pids) with checks the
    narratives alone can enforce now that they are the source of truth:
      DUP_ID         — two entries share an internal id `P-xxxxxx` (HARD; ids are
                       the primary key and must be unique / never reused).
      MISSING_ID     — entry has no internal id (HARD; every person needs one —
                       run mint_ids.py --apply).
      DUP_FS_PID     — one FS PID on two entries (ADVISORY only: FS PID is now an
                       external attribute, not the identity key, so FS conflation/
                       merge can legitimately point two distinct ids at one PID;
                       some may be known pre-existing cross-file rows recorded in
                       your .autoresearch.json baseline). Review, do not block.
      NEEDS_META     — entry missing tier / gen (ADVISORY; meta is incomplete).
    Exit 1 only on a HARD violation (DUP_ID or MISSING_ID)."""
    from collections import Counter
    id_counts = Counter(e["id"] for e in entries if e["id"])
    dup_ids = {i: c for i, c in id_counts.items() if c > 1}
    noid = [e for e in entries if not e["id"]]

    pid_to_ids = defaultdict(set)
    for e in entries:
        if e["pid"]:
            pid_to_ids[e["pid"]].add(e["id"] or e["name"])
    dup_pids = {p: ids for p, ids in pid_to_ids.items() if len(ids) > 1}

    # v3: required = id + generation. evidence_tier is OPTIONAL (absent = unassessed
    # = profile_status: stub), so it is NOT part of the completeness check anymore.
    needs_meta = [e for e in entries
                  if not (e["id"] and e["gen"] is not None)]

    print(f"narrative canonical entries: {len(entries)}")
    print("\n=== NARRATIVE INTEGRITY (post-Person_Index retirement) ===")
    print(f"  DUP_ID (same id on >1 entry):        {len(dup_ids)}   [HARD]")
    print(f"  MISSING_ID (entry has no id):        {len(noid)}   [HARD]")
    print(f"  DUP_FS_PID (1 FS PID, >1 entry):     {len(dup_pids)}   [advisory; compare vs your .autoresearch.json baseline]")
    print(f"  NEEDS_META (no id or no generation): {len(needs_meta)}   [advisory]")
    for i, c in list(dup_ids.items())[:args.limit]:
        print(f"    DUP_ID {i} x{c}")
    for e in noid[:args.limit]:
        print(f"    MISSING_ID {e['file']:<34} {e['name'][:34]}")
    for p, ids in list(dup_pids.items())[:args.limit]:
        print(f"    DUP_FS_PID {p}: {', '.join(sorted(ids))}")
    for e in needs_meta[:args.limit]:
        miss = ([] if e["id"] else ["id"]) + ([] if e["gen"] is not None else ["generation"])
        print(f"    NEEDS_META {e['file']:<34} {e['name'][:34]:<34} missing {','.join(miss)}")
    hard = len(dup_ids) + len(noid)
    print(f"\n  HARD violations (DUP_ID + MISSING_ID): {hard}")
    return 1 if hard else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", metavar="FILE")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--gap-report", action="store_true")
    ap.add_argument("--integrity", action="store_true",
                    help="narrative-native HARD gate (replaces duplicate_rows + "
                         "harvest_pids): unique ids, no FS PID shared across distinct "
                         "people, complete meta. Exit 1 on any violation.")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    entries = parse_narrative()

    if args.integrity:
        return integrity_check(entries, args)

    index_rows = parse_index()

    print(f"narrative canonical entries: {len(entries)}")
    print(f"committed Person_Index rows: {len(index_rows)}"
          + ("  (RETIRED — file absent; narrative is the source of truth)"
             if not index_rows else ""))

    if args.gap_report:
        no_id = [e for e in entries if not e["id"]]
        # v3: required = id + generation. evidence_tier / FS pid are optional.
        gaps = [e for e in entries if not e["id"] or e["gen"] is None]
        no_tier = sum(1 for e in entries if e["tier"] is None)
        no_gen = sum(1 for e in entries if e["gen"] is None)
        no_fs = sum(1 for e in entries if not e["pid"])
        print(f"\nentries with an INCOMPLETE meta block (missing id/generation): {len(gaps)}")
        print(f"  missing id: {len(no_id)}   missing generation: {no_gen}")
        print(f"  (no evidence_tier: {no_tier} — expected/OK; absent = unassessed = profile_status stub)")
        print(f"  (no FS pid: {no_fs} — expected/OK; FS is an optional external attribute)")
        for e in gaps[:args.limit]:
            print(f"  {e['file']:<38} {e['name']}")
        if len(gaps) > args.limit:
            print(f"  ... and {len(gaps)-args.limit} more")
        return 0

    # default: check / dashboard. With Person_Index retired the comparison has
    # nothing to diff against — emit the narrative integrity report instead and
    # remind that --write produces the on-demand roster.
    if not index_rows:
        if args.write:
            write_table(entries, index_rows, args)
        else:
            print("\nPerson_Index.md is RETIRED — no committed index to compare against.")
            print("Use  --integrity  for the narrative HARD gate, "
                  "or  --write FILE  for the on-demand gen-sorted roster.")
        return 0

    pidmap = build_pidmap(index_rows)
    matched_lineno = set()
    reproducible = needs_meta = field_drift = 0
    drift_samples = []
    narrative_only = 0
    for e in entries:
        m = match(e, index_rows, pidmap)
        if m is None:
            narrative_only += 1
            continue
        matched_lineno.add(m["lineno"])
        # hard field drift on what the narrative claims to reproduce
        hard = []
        if e["gen"] is not None and m["gen"].isdigit() and e["gen"] != int(m["gen"]):
            hard.append(f"gen {e['gen']}≠{m['gen']}")
        if not years_compatible(e["born"], m["born"]):
            hard.append(f"born {yr(e['born'])}≠{yr(m['born'])}")
        if e["pid"] and m["pid"] and e["pid"] not in SENTINEL and e["pid"] != m["pid"]:
            hard.append(f"pid {e['pid']}≠{m['pid']}")
        if hard:
            field_drift += 1
            if len(drift_samples) < args.limit:
                drift_samples.append(f"{e['name']} [{e['file'].replace('Family_Tree_','').replace('.md','')}]: " + ", ".join(hard))
        elif e["id"] and e["gen"] is not None:
            reproducible += 1     # complete meta (id+generation); evidence_tier + FS optional
        else:
            needs_meta += 1

    index_only = [r for r in index_rows if r["lineno"] not in matched_lineno]

    print("\n=== PHASE 1 MIGRATION DASHBOARD ===")
    print(f"  FULLY REPRODUCIBLE (meta block complete):   {reproducible}")
    print(f"  NEEDS META (no/partial meta block):         {needs_meta}  <- seed FS/tier")
    print(f"  HARD FIELD DRIFT (narrative≠index):         {field_drift}  <- investigate")
    print(f"  INDEX-ONLY rows (stub, no narrative):       {len(index_only)}  <- Phase-1 stub conversion")
    print(f"  NARRATIVE-ONLY (entry, no index row):       {narrative_only}")
    if drift_samples:
        print("\n  field-drift samples:")
        for s in drift_samples:
            print("   ", s)
    print("\n  meta-block coverage: "
          f"{sum(1 for e in entries if e['has_meta'])}/{len(entries)} entries have a `- meta:` block")
    print("  (when NEEDS_META + field_drift both reach 0, the file can flip to generated)")

    if args.write:
        write_table(entries, index_rows, args)
    return 1 if field_drift else 0


def write_table(entries, index_rows, args):
    target = os.path.join(VAULT, "Person_Index.md")
    if os.path.abspath(args.write) == os.path.abspath(target) and not args.force:
        print(f"\nREFUSING to overwrite {target} without --force.")
        return
    by_file = defaultdict(list)
    for e in entries:
        by_file[e["file"]].append(e)
    out = ["# Person_Index (GENERATED — do not hand-edit; see gen_person_index.py)\n"]
    for fn in sorted(by_file):
        out.append(f"\n## {fn}\n")
        out.append("| Name | Gen | Born | Died | FS PID | Tier | Profile | Life |")
        out.append("|---|---|---|---|---|---|---|---|")
        for e in sorted(by_file[fn], key=lambda x: (x["gen"] if x["gen"] is not None else 999, x["name"])):
            out.append(f"| {e['name']} | {e['gen'] if e['gen'] is not None else '?'} "
                       f"| {e['born'] or '—'} | {e['died'] or '—'} "
                       f"| {e['pid'] or 'TBD'} | {e['tier'] or '—'} "
                       f"| {e.get('profile_status') or '—'} | {e.get('life_status') or '—'} |")
    open(args.write, "w").write("\n".join(out) + "\n")
    print(f"\nwrote generated table ({len(entries)} rows) to {args.write}")


if __name__ == "__main__":
    sys.exit(main())
