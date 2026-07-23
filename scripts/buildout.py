#!/usr/bin/env python3
"""
buildout.py — Phase-2 FULL EDGE BUILD-OUT helper (companion to verify_edges.py).

Goal: edge every in-vault relationship (collateral + spine) BEFORE any FS
write-backs. Persistent home for the build-out tooling so it survives across
sessions (framework tooling, like gen_person_index.py / verify_edges.py; the DATA
it accumulates is what stays local, not the script).

THREE subcommands:

  buildout.py worklist [--out DIR]
      Regenerate the per-cluster walk set: every PID-bearing, deceased node with
      NO parent edge, grouped by Family_Tree file. Writes <DIR>/<File>.json
      (default DIR=/tmp/clusters) + prints counts. NOTE: a cluster's leftover
      count after processing = its TERMINAL line-tops (parents non-vault) which
      are correctly edgeless — a cluster is "done" when its non-terminal nodes
      are edged, not when this count hits 0.

  buildout.py extractor
      Print the COMBINED browser extractor JS (parents + spouse + children in one
      walk). Paste into a Claude-in-Chrome javascript_tool call per /tree/person/
      family/{PID} page. Letter-filters PID matches (real FS PIDs always contain a
      letter) so marriage-date ranges like "1642-1643" aren't mis-read as people.
      Returns {a:anchor, p:[[parent-couples]], s:[spouse pids], c:{coParent:[kids]}}.

  buildout.py match [--data FILE] [--spec FILE]
      Read accumulated walk records (default --data scripts/.buildout_data.json,
      a STABLE gitignored data path that survives sessions — NOT the session
      scratchpad), produce a verify_edges spec (default /tmp/buildout_spec.json),
      and PRINT THE NAME-LEVEL REVIEW. Maps via the fs->id map + the canonical
      override for the ambiguous DUP_FS_PID pair, fills anchor parents (only if
      the anchor lacks a parent edge) + spouse, and CHILD-EDGES every in-vault kid
      that lacks a parent edge (~2x leverage: walk the parent couples, not every
      leaf). Held-out conflations auto-skip (any node with an existing seeded `?`
      edge is untouched). REVIEW the printout, then:
          python3 scripts/verify_edges.py /tmp/buildout_spec.json --apply
          python3 scripts/build_edges.py --validate      # structural must stay 0
          python3 scripts/gen_person_index.py --integrity # HARD 0
      then commit to the vault repo, one cluster per commit, pausing for operator
      go-ahead.

DELICATE clusters — do NOT blind-fill, hand-review: any medieval/peerage cluster
(FS merge churn plus contested noble-descent joins) and any known same-name
conflation. Both need a human verdict per edge, not a mechanical fill.
"""
import re, os, sys, json, argparse
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import gen_person_index as G
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
# Canonical FS-PID -> vault-id override for the ambiguous DUP_FS_PID entries (one
# FS PID legitimately pointing at two distinct vault ids after an FS conflation).
# Per-vault, declared in .autoresearch.json ("dup_fs_pid_overrides"); empty by default.
OVR = vault_config.load_config(VAULT).get("dup_fs_pid_overrides", {}) if VAULT else {}
DEFAULT_DATA = os.path.join(SCRIPT_DIR, ".buildout_data.json")
DEFAULT_SPEC = "/tmp/buildout_spec.json"

EXTRACTOR_JS = r"""var RE=/\b[0-9A-Z]{4}-[0-9A-Z]{3,4}\b/g;var LET=p=>/[A-Z]/.test(p);var tx='';for(var i=0;i<45;i++){tx=document.body.innerText;if(/Parents and Siblings/.test(tx)&&(new Set(tx.match(RE)||[])).size>=1)break;await new Promise(r=>setTimeout(r,300));}await new Promise(r=>setTimeout(r,400));var A=location.pathname.split('/').pop();var txt=document.body.innerText;var sc=txt.indexOf('Spouses and Children'),ps=txt.indexOf('Parents and Siblings');var sr=sc>=0?txt.slice(sc,ps>sc?ps:undefined):'';var ch={},sps=[];for(var b of sr.split('ADD CHILD')){var ci=b.indexOf('Children (');if(ci<0){var s0=(b.match(RE)||[]).filter(p=>p!==A&&LET(p));if(s0.length)sps.push(s0[s0.length-1]);continue;}var hd=b.slice(0,ci),tl=b.slice(ci);var s1=(hd.match(RE)||[]).filter(p=>p!==A&&LET(p));var co=s1.length?s1[s1.length-1]:'NONE';if(co!=='NONE')sps.push(co);ch[co]=(ch[co]||[]).concat((tl.match(RE)||[]).filter(LET));}var pr=ps>=0?txt.slice(ps):'';var par=[];for(var b of pr.split('ADD CHILD')){var ci=b.indexOf('Children (');var hd=ci>=0?b.slice(0,ci):b;var pp=(hd.match(RE)||[]).filter(p=>p!==A&&LET(p));if(pp.length)par.push(pp.slice(0,2));}JSON.stringify({a:A,p:par,s:[...new Set(sps)],c:ch})"""


def load_vault():
    rows = G.parse_narrative()
    id2 = {r["id"]: r for r in rows if r["id"]}
    fs2ids = defaultdict(set)
    for r in rows:
        if r["pid"]:
            fs2ids[r["pid"]].add(r["id"])
    fs2id = {p: next(iter(s)) for p, s in fs2ids.items() if len(s) == 1}
    refs = lambda v: [t.rstrip("?") for t in re.findall(r"P-[0-9A-TV-Z?]+", v or "")]
    haspar = {r["id"] for r in rows if r["id"] and refs(G.parse_meta(r["block"]).get("parents"))}
    return rows, id2, fs2id, haspar


def cmd_worklist(args):
    rows, id2, fs2id, haspar = load_vault()
    os.makedirs(args.out, exist_ok=True)
    byfile = defaultdict(list)
    for r in rows:
        i = r["id"]
        if not i or i in haspar:
            continue
        m = G.parse_meta(r["block"])
        if m.get("life_status") in ("living", "unknown") or not r["pid"] or r["pid"] == "TBD":
            continue
        byfile[id2[i]["file"]].append(r["pid"])
    for f, pids in byfile.items():
        short = f.replace("Family_Tree_", "").replace("Family_Tree", "main").replace(".md", "")
        json.dump(pids, open(os.path.join(args.out, short + ".json"), "w"))
    print(f"worklist -> {args.out}/  ({sum(len(v) for v in byfile.values())} nodes, "
          f"{len(byfile)} files)")
    for f, pids in sorted(byfile.items(), key=lambda x: -len(x[1])):
        short = f.replace("Family_Tree_", "").replace("Family_Tree", "main").replace(".md", "")
        print(f"  {len(pids):>3}  {short}")


def cmd_extractor(args):
    print(EXTRACTOR_JS)


def cmd_match(args):
    rows, id2, fs2id, haspar = load_vault()
    m = lambda pid: OVR.get(pid) or fs2id.get(pid)
    data = json.load(open(args.data))
    spec = defaultdict(lambda: {"parents": set(), "spouse": set()})
    for rec in data:
        aid = m(rec["a"])
        if not aid:
            continue
        if aid not in haspar and rec.get("p"):
            best = max(rec["p"], key=lambda b: sum(1 for x in b if m(x)))
            vids = [m(x) for x in best if m(x)]
            if vids:
                spec[aid]["parents"].update(vids)
        for sp in rec.get("s", []):
            sid = m(sp)
            if sid and sid != aid:
                spec[aid]["spouse"].add(sid)
        for co, kids in rec.get("c", {}).items():
            coid = m(co) if co != "NONE" else None
            for k in kids:
                kid = m(k)
                if not kid or kid in haspar or kid == aid:
                    continue
                spec[kid]["parents"].update({aid} | ({coid} if coid else set()))
    out = {}
    for i, d in spec.items():
        e = {}
        if d["parents"]:
            e["parents"] = sorted(d["parents"])
        if d["spouse"]:
            e["spouse"] = sorted(d["spouse"])
        if e:
            out[i] = e
    json.dump(out, open(args.spec, "w"), indent=1)
    np = sum(1 for e in out.values() if "parents" in e)
    ns = sum(1 for e in out.values() if "spouse" in e)
    print(f"records: {len(data)}  -> spec {args.spec}: {len(out)} nodes "
          f"(parent {np}, spouse {ns})")
    print("--- REVIEW (verify names before --apply) ---")
    nm = lambda i: id2[i]["name"][:30] if i in id2 else "?"
    for i, e in out.items():
        par = [nm(p) for p in e.get("parents", [])]
        sp = [nm(s) for s in e.get("spouse", [])]
        print(f"  {nm(i):30} P={par} S={sp}")


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description="Phase-2 full edge build-out helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worklist"); w.add_argument("--out", default="/tmp/clusters"); w.set_defaults(fn=cmd_worklist)
    e = sub.add_parser("extractor"); e.set_defaults(fn=cmd_extractor)
    mt = sub.add_parser("match")
    mt.add_argument("--data", default=DEFAULT_DATA)
    mt.add_argument("--spec", default=DEFAULT_SPEC)
    mt.set_defaults(fn=cmd_match)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
