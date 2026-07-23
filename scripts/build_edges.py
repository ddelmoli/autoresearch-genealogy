#!/usr/bin/env python3
"""
build_edges.py — Phase 2 of the Person_Index retirement (see memory
project_person_index_retirement): build parents:/spouse: id-edges into the
narrative `- meta:` blocks.

EDGE SOURCE (operator decision 25 JUN 2026): the GEDCOM (vault/<name>.ged, resolved via .autoresearch.json)
is read ONCE as a migration SEED — every INDI carries an `_FSFTID` (FS PID) and
FAMC/FAMS pointers into FAM records (HUSB/WIFE/CHIL), so it already encodes
parent + spouse edges keyed on FS PID. We translate those FS-PID edges into the
vault's own `id` edges (P-xxxxxx) via the narrative fs->id map. Edges written this
pass are tagged gedcom-sourced + UNVERIFIED; an authoritative FS-walk verification
pass flips them later (operator's 'FS is the authority' stance — the GEDCOM is a
stale snapshot, good enough to seed but not to trust permanently).

Identity rule (CLAUDE.local invariant): edges reference the vault `id`, NEVER a
name/date/FS PID. The FS PID is only the JOIN KEY between GEDCOM and narrative;
the written edge is pure id.

READ-ONLY. Default mode is a dry-run report: how many GEDCOM edges resolve to a
clean id->id pair, how many dangle (endpoint PID has no vault entry), how many
vault people are absent from the GEDCOM, and the ambiguous FS-PID->2-id cases.
NO vault mutation until the numbers are reviewed (--apply is intentionally not yet
implemented in this dry-run build).
"""
import re, os, sys, glob, argparse
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import gen_person_index as G
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
# GEDCOM filename is a per-vault constant (vault/.autoresearch.json -> "gedcom";
# falls back to the single *.ged in the vault). See vault_config.py.
GED = vault_config.gedcom_path(VAULT) if VAULT else None

PID_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{3})\b")
VAULT_ID_RE = re.compile(r"P-[0-9A-TV-Z?]+")   # P- + Crockford base32 (no I/L/O/U), optional ? suffix


def edge_value(existing, new_ids):
    """Build the single-quoted id flow-list value for a parents:/spouse: edge.
    Merges any EXISTING edge value (preserving each id's verified state — a bare
    id is FS-confirmed, a `?`-suffixed id is gedcom-seeded/unverified) with the
    NEW gedcom ids (added unverified, i.e. with `?`). Idempotent + re-runnable:
    an id already present keeps its state; the FS-walk pass later drops the `?`."""
    cur = {}                                   # id -> verified(bool)
    for tok in VAULT_ID_RE.findall(existing or ""):
        pid = tok.rstrip("?")
        cur[pid] = cur.get(pid, False) or not tok.endswith("?")
    for nid in new_ids:
        cur.setdefault(nid, False)             # gedcom-seeded => unverified
    parts = [pid + ("" if v else "?") for pid, v in sorted(cur.items())]
    return "'[" + ", ".join(parts) + "]'"


def upsert_edges(line, parents, spouse):
    """Splice parents:/spouse: edges into a raw `- meta: {...}` line WITHOUT
    disturbing any other field's text/quoting. Replaces an existing key's value
    in place; otherwise inserts the new key just before `flags:` (kept last) or
    before the closing brace. Conventional order: ...fs, parents, spouse, flags."""
    meta = G.parse_meta(line)
    updates = []
    if parents:
        updates.append(("parents", edge_value(meta.get("parents"), parents)))
    if spouse:
        updates.append(("spouse", edge_value(meta.get("spouse"), spouse)))
    for key, val in updates:
        if key in meta:                        # replace value in place
            pat = re.compile(rf"(\b{key}\s*:\s*)('?\[[^\]]*\]'?|[^,}}]*)")
            line = pat.sub(lambda m: m.group(1) + val, line, count=1)
        else:                                  # insert before flags / closing brace
            frag = f", {key}: {val}"
            if re.search(r",\s*flags\s*:", line):
                line = re.sub(r"(,\s*flags\s*:)", lambda m: frag + m.group(1), line, count=1)
            else:
                idx = line.rfind("}")
                line = line[:idx] + frag + line[idx:]
    return line


def edge_ids(val):
    """Extract (id, verified) pairs from a parents/spouse edge value string."""
    out = []
    for tok in VAULT_ID_RE.findall(val or ""):
        out.append((tok.rstrip("?"), not tok.endswith("?")))
    return out


def validate_edges(limit=20):
    """Read-only edge-graph integrity checks over the written meta blocks.
    Advisory (NOT the HARD gate — gen mismatches may be the known gen backlog,
    not edge bugs). Surfaces: dangling id refs, broken spouse reciprocity,
    parent-generation inconsistency (a parent must be generation+1), self-edges."""
    rows = G.parse_narrative()
    id2row = {r["id"]: r for r in rows if r["id"]}
    parents = defaultdict(set)        # id -> {parent_id}
    spouses = defaultdict(set)        # id -> {spouse_id}
    for r in rows:
        if not r["id"]:
            continue
        meta = G.parse_meta(r["block"])
        for pid, _ in edge_ids(meta.get("parents")):
            parents[r["id"]].add(pid)
        for sid, _ in edge_ids(meta.get("spouse")):
            spouses[r["id"]].add(sid)

    dangling, selfedge, recip, gen_bad = [], [], [], []
    nm = lambda i: id2row.get(i, {}).get("name", "?")
    for cid, pset in parents.items():
        for p in pset:
            if p == cid:
                selfedge.append((cid, "parents", p))
            elif p not in id2row:
                dangling.append((cid, "parents", p))
            else:
                cg, pg = id2row[cid]["gen"], id2row[p]["gen"]
                if cg is not None and pg is not None and pg != cg + 1:
                    gen_bad.append((cid, p, cg, pg))
    for sid, sset in spouses.items():
        for s in sset:
            if s == sid:
                selfedge.append((sid, "spouse", s))
            elif s not in id2row:
                dangling.append((sid, "spouse", s))
            elif sid not in spouses.get(s, set()):
                recip.append((sid, s))

    print("=" * 70)
    print("EDGE-GRAPH INTEGRITY (advisory; read-only)")
    print("=" * 70)
    print(f"  entries with parent edges: {len(parents)}   spouse edges: {len(spouses)}")
    print(f"\n  DANGLING id refs (edge -> nonexistent id):   {len(dangling)}   [should be 0]")
    print(f"  SELF-EDGES (id points to itself):            {len(selfedge)}   [should be 0]")
    print(f"  BROKEN SPOUSE RECIPROCITY (A->B, no B->A):   {len(recip)}   [should be 0]")
    print(f"  PARENT-GEN MISMATCH (parent != child gen+1): {len(gen_bad)}   [gen-backlog signal, not necessarily an edge bug]")
    for c, k, p in dangling[:limit]:
        print(f"    DANGLING  {nm(c)} ({c}) {k} -> {p} (no such id)")
    for c, k, p in selfedge[:limit]:
        print(f"    SELF-EDGE {nm(c)} ({c}) {k} -> itself")
    for a, b in recip[:limit]:
        print(f"    RECIP     {nm(a)} ({a}) spouse {nm(b)} ({b}); but {b} lacks {a}")
    for c, p, cg, pg in gen_bad[:limit]:
        print(f"    GEN       {nm(c)} (gen {cg}) <- parent {nm(p)} (gen {pg}; expected {cg+1})")
    if len(gen_bad) > limit:
        print(f"    ... and {len(gen_bad)-limit} more gen mismatches")
    hard = len(dangling) + len(selfedge) + len(recip)
    print(f"\n  structural violations (dangling+self+recip): {hard}  [target 0]")
    return 1 if hard else 0


def parse_gedcom(path):
    """Return (indi, fam): indi[xref] = {fsftid, name, famc:set, fams:set};
    fam[xref] = {husb, wife, chil:list}. A 0-level record opens a context."""
    indi, fam = {}, {}
    cur_type = cur_xref = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = re.match(r"^0 @([^@]+)@ (\w+)", line)
            if m:
                cur_xref, cur_type = m.group(1), m.group(2)
                if cur_type == "INDI":
                    indi[cur_xref] = dict(fsftid=None, name=None,
                                          famc=set(), fams=set())
                elif cur_type == "FAM":
                    fam[cur_xref] = dict(husb=None, wife=None, chil=[])
                continue
            if cur_type == "INDI":
                r = indi[cur_xref]
                if line.startswith("1 _FSFTID "):
                    r["fsftid"] = line[10:].strip()
                elif line.startswith("1 NAME "):
                    r["name"] = line[7:].strip().replace("/", "")
                elif line.startswith("1 FAMC @"):
                    r["famc"].add(line[8:].strip().rstrip("@"))
                elif line.startswith("1 FAMS @"):
                    r["fams"].add(line[8:].strip().rstrip("@"))
            elif cur_type == "FAM":
                r = fam[cur_xref]
                if line.startswith("1 HUSB @"):
                    r["husb"] = line[8:].strip().rstrip("@")
                elif line.startswith("1 WIFE @"):
                    r["wife"] = line[8:].strip().rstrip("@")
                elif line.startswith("1 CHIL @"):
                    r["chil"].append(line[8:].strip().rstrip("@"))
    return indi, fam


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--show", choices=["dangling", "absent", "resolved", "ambig"],
                    help="list the named category in full")
    ap.add_argument("--apply", action="store_true",
                    help="WRITE the resolved edges into the meta blocks (per-file "
                         ".bak). Default is a write-preview only.")
    ap.add_argument("--validate", action="store_true",
                    help="read-only edge-graph integrity checks over the written "
                         "edges (dangling refs, spouse reciprocity, parent-gen). "
                         "Advisory. Exit 1 on a structural violation.")
    args = ap.parse_args()

    if args.validate:
        return validate_edges(args.limit)

    # --- vault side: fs PID <-> vault id ---
    rows = G.parse_narrative()
    fs2ids = defaultdict(set)        # FS PID -> {vault id}  (set: surfaces dups)
    id2row = {}
    for r in rows:
        if r["id"]:
            id2row[r["id"]] = r
        if r["pid"]:
            fs2ids[r["pid"]].add(r["id"])
    fs2id = {p: next(iter(ids)) for p, ids in fs2ids.items() if len(ids) == 1}
    ambig_pids = {p: ids for p, ids in fs2ids.items() if len(ids) > 1}

    # --- gedcom side ---
    indi, fam = parse_gedcom(GED)
    # FS PID -> gedcom indi xref (for reverse lookups); flag gedcom-internal dups
    fsftid_to_xref = {}
    ged_dup_fsftid = defaultdict(list)
    for x, r in indi.items():
        if r["fsftid"]:
            ged_dup_fsftid[r["fsftid"]].append(x)
    for fsftid, xrefs in ged_dup_fsftid.items():
        fsftid_to_xref[fsftid] = xrefs[0]

    def parents_of(xref):
        """FS PIDs of the HUSB/WIFE in every family this indi is a CHILD in."""
        out = []
        for fxref in indi[xref]["famc"]:
            f = fam.get(fxref)
            if not f:
                continue
            for slot in ("husb", "wife"):
                px = f[slot]
                if px and indi.get(px, {}).get("fsftid"):
                    out.append(indi[px]["fsftid"])
        return out

    def spouses_of(xref):
        """FS PIDs of the OTHER spouse in every family this indi is a spouse in."""
        out = []
        for fxref in indi[xref]["fams"]:
            f = fam.get(fxref)
            if not f:
                continue
            for sx in (f["husb"], f["wife"]):
                if sx and sx != xref and indi.get(sx, {}).get("fsftid"):
                    out.append(indi[sx]["fsftid"])
        return out

    # --- build edges for every vault person who has an FS PID & is in the GEDCOM ---
    vault_pids = {r["pid"] for r in rows if r["pid"]}
    matched_in_ged = vault_pids & set(fsftid_to_xref)
    vault_pids_absent = vault_pids - set(fsftid_to_xref)

    resolved_parent = []     # (child_id, parent_id)
    resolved_spouse = []     # (a_id, b_id)
    dangling_parent = []     # (child_id, parent_pid)  parent has no vault id
    dangling_spouse = []
    children_with_parent_edges = set()
    children_with_any_parent_in_ged = set()

    for r in rows:
        cpid = r["pid"]
        if not cpid or cpid not in fsftid_to_xref:
            continue
        cid = r["id"]
        cx = fsftid_to_xref[cpid]
        ppids = parents_of(cx)
        if ppids:
            children_with_any_parent_in_ged.add(cid)
        for ppid in ppids:
            pid_id = fs2id.get(ppid)
            if pid_id and pid_id != cid:
                resolved_parent.append((cid, pid_id))
                children_with_parent_edges.add(cid)
            elif ppid not in fs2id:
                dangling_parent.append((cid, ppid))
        for spid in spouses_of(cx):
            sid = fs2id.get(spid)
            if sid and sid != cid:
                resolved_spouse.append(tuple(sorted((cid, sid))))
            elif spid not in fs2id:
                dangling_spouse.append((cid, spid))

    resolved_spouse = sorted(set(resolved_spouse))
    # dedup parent edges
    resolved_parent = sorted(set(resolved_parent))

    nm = lambda i: (id2row.get(i, {}).get("name", "?")) if i else "?"

    print("=" * 70)
    print("PHASE 2 EDGE-BUILDER — GEDCOM SEED DRY-RUN (read-only)")
    print("=" * 70)
    print(f"\nVAULT: {len(rows)} narrative entries; "
          f"{len(vault_pids)} carry an FS PID; {len(id2row)} have an id")
    print(f"GEDCOM: {len(indi)} individuals ({sum(1 for r in indi.values() if r['fsftid'])} "
          f"with _FSFTID), {len(fam)} families")

    print("\n--- JOIN (FS PID is the GEDCOM<->vault join key) ---")
    print(f"  vault PIDs matched in GEDCOM:     {len(matched_in_ged)}")
    print(f"  vault PIDs ABSENT from GEDCOM:    {len(vault_pids_absent)}  "
          f"(no edges seedable for these)")
    print(f"  FS PID -> >1 vault id (ambiguous): {len(ambig_pids)}  "
          f"(compare against your .autoresearch.json known_dup_fs_pids baseline)")
    print(f"  duplicate _FSFTID inside GEDCOM:  "
          f"{sum(1 for v in ged_dup_fsftid.values() if len(v) > 1)}")

    print("\n--- PARENT EDGES ---")
    print(f"  vault children with >=1 parent in GEDCOM:  {len(children_with_any_parent_in_ged)}")
    print(f"  RESOLVED parent edges (id->id):            {len(resolved_parent)}")
    print(f"  children getting >=1 resolved parent edge: {len(children_with_parent_edges)}")
    print(f"  DANGLING parent edges (parent not in vault):{len(dangling_parent)}")

    print("\n--- SPOUSE EDGES ---")
    print(f"  RESOLVED spouse edges (id<->id):           {len(resolved_spouse)}")
    print(f"  DANGLING spouse edges (spouse not in vault):{len(dangling_spouse)}")

    cov = 100.0 * len(children_with_parent_edges) / max(1, len(id2row))
    print(f"\n--- COVERAGE ---")
    print(f"  {len(children_with_parent_edges)}/{len(id2row)} vault entries would gain "
          f">=1 parent edge ({cov:.1f}%)")

    if ambig_pids:
        print("\n  ambiguous FS PIDs (skipped — can't pick an id):")
        for p, ids in ambig_pids.items():
            print(f"    {p}: {', '.join(sorted(ids))}")

    # --- collect edges per vault id (parents on the child; spouse symmetric) ---
    parents_by = defaultdict(set)
    for c, p in resolved_parent:
        parents_by[c].add(p)
    spouse_by = defaultdict(set)
    for a, b in resolved_spouse:
        spouse_by[a].add(b)
        spouse_by[b].add(a)
    edged_ids = set(parents_by) | set(spouse_by)

    # --- write-preview / apply ---
    preview = []
    files_touched = defaultdict(int)
    for path in sorted(glob.glob(os.path.join(VAULT, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            if not G.META.match(line):
                continue
            cid = G.parse_meta(line).get("id")
            if cid not in edged_ids:
                continue
            newl = upsert_edges(line, parents_by.get(cid, set()), spouse_by.get(cid, set()))
            if newl != line:
                if len(preview) < args.limit:
                    preview.append((os.path.basename(path), nm(cid), newl.strip()))
                lines[i] = newl
                changed = True
                files_touched[os.path.basename(path)] += 1
        if changed and args.apply:
            with open(path + ".bak", "w", encoding="utf-8") as b:
                b.write(open(path, encoding="utf-8").read())
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)

    print("\n--- WRITE %s ---" % ("APPLIED" if args.apply else "PREVIEW (no changes written; pass --apply)"))
    print(f"  entries that would gain/merge edges: {len(edged_ids)}")
    print(f"  files touched: {len(files_touched)}  ("
          + ", ".join(f"{k.replace('Family_Tree_','').replace('.md','')}:{v}"
                      for k, v in sorted(files_touched.items())) + ")")
    for fn, name, l in preview:
        print(f"\n    [{fn.replace('Family_Tree_','').replace('.md','')}] {name}")
        print(f"    {l}")
    if args.apply:
        print("\n  WROTE edges (.bak per touched file). Next: re-run the integrity "
              "gate:\n    python3 scripts/gen_person_index.py --integrity")
    else:
        print(f"\n  (write-preview shows first {args.limit}; pass --apply to write)")

    if args.show == "resolved":
        print("\n  RESOLVED parent edges (child <- parent):")
        for c, p in resolved_parent:
            print(f"    {nm(c)} ({c})  <-  {nm(p)} ({p})")
    elif args.show == "dangling":
        print("\n  DANGLING parent edges (parent PID has no vault entry):")
        seen = Counter(p for _, p in dangling_parent)
        for ppid, n in seen.most_common(args.limit):
            gname = indi.get(fsftid_to_xref.get(ppid, ""), {}).get("name", "?")
            print(f"    {ppid}  {gname}  (would-be parent of {n} vault child(ren))")
    elif args.show == "absent":
        print("\n  vault PIDs absent from GEDCOM:")
        for p in sorted(vault_pids_absent):
            ids = fs2ids[p]
            print(f"    {p}  {nm(next(iter(ids)))}")
    else:
        print(f"\n  (use --show resolved|dangling|absent|ambig for detail; "
              f"--limit N caps lists)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
