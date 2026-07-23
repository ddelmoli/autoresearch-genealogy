#!/usr/bin/env python3
"""
verify_edges.py — Phase 2 FS-walk VERIFICATION/FILL writer (companion to
build_edges.py). Where build_edges.py SEEDS `?`-unverified parents:/spouse:
edges from the stale GEDCOM, this script writes the AUTHORITATIVE result of an
operator-gated FamilySearch family-page walk:

  * DROP the `?` on a seeded edge the FS walk CONFIRMS (gedcom-seeded -> verified),
  * ADD a brand-new verified edge for a GEDCOM-ABSENT person (no seed existed),
  * REMOVE a seeded `?`-edge the FS walk CONTRADICTS (stale GEDCOM correction),

all keyed on the vault `id` (NEVER a name / date / external PID — CLAUDE.local
invariant). Idempotent: re-running the same spec yields byte-identical output.

INPUT — a JSON spec mapping vault id -> confirmed edges (from the FS walk):

    {
      "P-SAMSYV": {"parents": ["P-PZ4YD2", "P-QA1VKV"], "spouse": ["P-BAH7B0"]},
      "P-PZ4YD2": {"spouse": ["P-QA1VKV"]},
      "P-XXXXXX": {"parents": ["P-AAA"], "remove_parents": ["P-BBB"]}
    }

Semantics, per person, per key:
  * `parents` / `spouse`  = the FS-CONFIRMED ids. Each is written VERIFIED (bare,
    no `?`). If the id was already a seeded `?`-edge, the `?` is dropped; if it
    was absent, it is added (GEDCOM-absent fill). Providing the key does NOT
    auto-delete other seeded `?`-edges on that person — unconfirmed seed edges
    are LEFT `?` and REPORTED as residual (so an FS-vs-GEDCOM disagreement is
    surfaced, never silently dropped). Use remove_* for a deliberate correction.
  * `remove_parents` / `remove_spouse` = ids to DELETE outright (FS contradicts
    the seed).

SPOUSE EDGES ARE SYMMETRIC. A confirm or remove of A<->B is applied to BOTH
endpoints (writing A.spouse+=B AND B.spouse+=A), so spouse reciprocity stays 0
even if only one side is named in the spec. Parent edges are one-directional
(child -> parent), matching the vault model.

READ-ONLY by default (write-preview). Pass --apply to write (per-file .bak).
After --apply, re-run the gates:
    python3 scripts/build_edges.py --validate     # structural must stay 0
    python3 scripts/gen_person_index.py --integrity
"""
import re, os, sys, glob, json, argparse
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import gen_person_index as G
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
VAULT_ID_RE = re.compile(r"P-[0-9A-TV-Z?]+")   # P- + Crockford base32, optional ? suffix


def parse_edge(existing):
    """existing edge value string -> {id: verified(bool)} (insertion-agnostic)."""
    cur = {}
    for tok in VAULT_ID_RE.findall(existing or ""):
        pid = tok.rstrip("?")
        cur[pid] = cur.get(pid, False) or not tok.endswith("?")
    return cur


def render_edge(cur):
    """{id: verified} -> single-quoted flow-list value, or None if empty."""
    if not cur:
        return None
    parts = [pid + ("" if v else "?") for pid, v in sorted(cur.items())]
    return "'[" + ", ".join(parts) + "]'"


def new_edge_value(existing, confirm_ids, remove_ids):
    """Merge a confirmed/removed edge into an existing value. Returns (value, residual):
    value = new edge string or None (key should be deleted); residual = sorted
    list of ids LEFT unverified (seeded `?` not in confirm/remove) — surfaced
    as an FS-vs-seed disagreement to eyeball."""
    cur = parse_edge(existing)
    for rid in remove_ids:
        cur.pop(rid, None)
    for cid in confirm_ids:
        cur[cid] = True
    residual = sorted(i for i, v in cur.items() if not v)
    return render_edge(cur), residual


def splice(line, key, value):
    """Set/replace/delete `key` in a `- meta: {...}` line, preserving all other
    fields verbatim. value=None deletes the key; conventional order keeps new
    keys before flags:/closing brace (matches build_edges.upsert_edges)."""
    meta = G.parse_meta(line)
    if key in meta:
        if value is None:                                   # delete the key
            line = re.sub(rf",\s*{key}\s*:\s*('?\[[^\]]*\]'?|[^,}}]*)", "", line, count=1)
            line = re.sub(rf"{{\s*{key}\s*:\s*('?\[[^\]]*\]'?|[^,}}]*),\s*", "{", line, count=1)
        else:
            pat = re.compile(rf"(\b{key}\s*:\s*)('?\[[^\]]*\]'?|[^,}}]*)")
            line = pat.sub(lambda m: m.group(1) + value, line, count=1)
    elif value is not None:                                 # insert before flags / closing brace
        frag = f", {key}: {value}"
        if re.search(r",\s*flags\s*:", line):
            line = re.sub(r"(,\s*flags\s*:)", lambda m: frag + m.group(1), line, count=1)
        else:
            idx = line.rfind("}")
            line = line[:idx] + frag + line[idx:]
    return line


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="JSON spec file: {id: {parents/spouse/remove_*: [...]}}")
    ap.add_argument("--apply", action="store_true", help="write (per-file .bak); default is preview")
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))

    rows = G.parse_narrative()
    id2name = {r["id"]: r["name"] for r in rows if r["id"]}
    all_ids = set(id2name)

    # --- normalize spec; make spouse confirms/removes symmetric ---
    p_confirm, p_remove = defaultdict(set), defaultdict(set)
    s_confirm, s_remove = defaultdict(set), defaultdict(set)
    unknown = set()
    for cid, d in spec.items():
        if cid not in all_ids:
            unknown.add(cid)
        for pid in d.get("parents", []):
            p_confirm[cid].add(pid); unknown |= {pid} - all_ids
        for pid in d.get("remove_parents", []):
            p_remove[cid].add(pid)
        for sid in d.get("spouse", []):
            s_confirm[cid].add(sid); s_confirm[sid].add(cid); unknown |= {sid} - all_ids
        for sid in d.get("remove_spouse", []):
            s_remove[cid].add(sid); s_remove[sid].add(cid)

    if unknown:
        print("!! UNKNOWN ids in spec (no vault entry) — fix before --apply:")
        for u in sorted(unknown):
            print(f"     {u}")

    touched_ids = set(p_confirm) | set(p_remove) | set(s_confirm) | set(s_remove)

    changes, residuals, files_touched = [], [], defaultdict(int)
    seen_ids = set()
    for path in sorted(glob.glob(os.path.join(VAULT, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            if not G.META.match(line):
                continue
            cid = G.parse_meta(line).get("id")
            if cid not in touched_ids:
                continue
            seen_ids.add(cid)
            newl = line
            if cid in p_confirm or cid in p_remove:
                val, resid = new_edge_value(G.parse_meta(newl).get("parents"),
                                            p_confirm.get(cid, set()), p_remove.get(cid, set()))
                newl = splice(newl, "parents", val)
                if resid:
                    residuals.append((id2name.get(cid, "?"), cid, "parents", resid))
            if cid in s_confirm or cid in s_remove:
                val, resid = new_edge_value(G.parse_meta(newl).get("spouse"),
                                            s_confirm.get(cid, set()), s_remove.get(cid, set()))
                newl = splice(newl, "spouse", val)
                if resid:
                    residuals.append((id2name.get(cid, "?"), cid, "spouse", resid))
            if newl != line:
                changes.append((os.path.basename(path), id2name.get(cid, "?"), cid, newl.strip()))
                lines[i] = newl
                changed = True
                files_touched[os.path.basename(path)] += 1
        if changed and args.apply:
            with open(path + ".bak", "w", encoding="utf-8") as b:
                b.write("".join(open(path, encoding="utf-8").read()))
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)

    missing = touched_ids - seen_ids
    print("=" * 70)
    print("PHASE 2 FS-WALK VERIFICATION %s" % ("APPLIED" if args.apply else "PREVIEW (no writes; pass --apply)"))
    print("=" * 70)
    print(f"  people in spec: {len(spec)}   ids touched: {len(touched_ids)}   lines changed: {len(changes)}")
    print(f"  files: " + ", ".join(f"{k.replace('Family_Tree_','').replace('.md','')}:{v}"
                                    for k, v in sorted(files_touched.items())))
    if missing:
        print(f"\n  !! spec ids NOT FOUND in any Family_Tree file: {sorted(missing)}")
    print("\n  --- changed meta lines ---")
    for fn, name, cid, l in changes:
        print(f"    [{fn.replace('Family_Tree_','').replace('.md','')}] {name} ({cid})")
        print(f"      {l}")
    if residuals:
        print("\n  --- RESIDUAL `?` edges (seeded, NOT confirmed by this spec — eyeball for FS disagreement) ---")
        for name, cid, key, resid in residuals:
            print(f"    {name} ({cid}) {key}: still-unverified {resid}")
    if args.apply:
        print("\n  WROTE (.bak per file). Re-run gates:")
        print("    python3 scripts/build_edges.py --validate")
        print("    python3 scripts/gen_person_index.py --integrity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
