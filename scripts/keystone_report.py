#!/usr/bin/env python3
"""keystone_report.py — which THIN entries is the most tree hanging off?

WHY IT EXISTS. This vault already asks two good questions about incompleteness and
gets useful answers to both:

  extension_frontier.py   "who has NO PARENTS, and is that on purpose?"
  harvest_sources.py      "who has NO RECORDS cited?"

Neither asks the third question, and a real person fell through the gap between
them (25 JUL 2026). A **Gen-29 woman**, the illegitimate daughter of a king. Her
whole entry is three lines: a header reading `(unknown; unknown)`, a meta block with
no `born` and no `died`, and one line of provenance. She arrived as one of 399
index-only stubs in a Person_Index retirement migration and was never worked.

**And 22 people are in that vault ONLY because of her** — measured, not asserted:
four generations at the top of one royal house, a comital family, a king and queen
consort, and then an entire dynastic line of ten. Remove one undated stub and all
of it leaves the tree.

⭐ **Note what the number CORRECTS, because this is the point of computing it rather
than eyeballing it.** That vault's own shard header called her the gateway to two
whole royal descents. She REACHES 69 ancestors — but only **22** depend on her
ALONE; the rest are double-connected through other lines and would survive her
removal. **"How much hangs off this person" and "how much do they reach" are
different questions, and only the first one tells you what to work.**

She is invisible to BOTH existing reports:

  - `extension_frontier` skips her, because she HAS a parents edge. It asks who is
    unextended ABOVE; she is unworked IN HERSELF.
  - `harvest_sources` sees her but files her as `LOW_COVERAGE, 2` — which reads as
    "nearly fine, a couple more ARKs would do it", not as "this is a bare migration
    stub with no vitals and no prose".
  - `gen_person_index --gap-report` deliberately does not flag her: it reports
    missing id/generation only, and says of the rest "no evidence_tier: 539 —
    expected/OK".

So nothing in the toolkit could have surfaced her, and nothing weighted her by the
fact that a large part of the tree hangs off her. **That is what this script adds.**

WHAT IT REPORTS. For every person it computes two numbers and multiplies them:

  LOAD   how many OTHER people become unreachable from the vault's roots if this
         person is removed. This is a dominator/cut-vertex count over the
         child -> parents graph, computed by actual removal rather than by
         heuristic. LOAD 0 means the person is a leaf or is bypassed by another
         path (a pedigree collapse); LOAD 300 means three hundred ancestors are in
         this vault only because of them.

  THIN   how UNWORKED the entry is, 0-6, measured from the BODY: no write-up at
         all; no born AND no died; no source of any kind, record or scholarly; a
         placeholder header. ⚠ **CAPPED when the census credits real records** —
         see the note on `thinness()`, whose first version measured metadata
         staleness instead and put a WELL_SOURCED entry at the top of the queue.

**A keystone is an entry with high LOAD and high THIN** — the tree leans on it and
nobody has written it up. That is a strictly better work queue than either input on
its own, because LOAD is what makes an omission expensive and THIN is what makes it
cheap to fix.

A SECOND MODE, `--stale-meta`, reports the opposite failure: entries whose meta
block UNDERSTATES the work done (`profile_status: stub` or no `evidence_tier` on a
person the census credits with records). On the reference vault that is **97
entries, 26 of them WELL_SOURCED and one with 63 ARKs** — so `profile_status` is
not trustworthy as an input to anything, which is exactly why THIN stopped using it.

A SECOND MODE, `--stale-meta`, reports the opposite failure: entries whose meta
block UNDERSTATES the work done. That mode is what found the 97-entry labelling
backlog; `migrate_profile_status.py` then fixed it, and the mode now reports the
residue rather than a systemic problem.

WHAT IT IS NOT. It is not a defect list and nothing here blocks a commit. A high
LOAD with THIN 0 is a well-worked keystone, which is the desired end state. A high
THIN with LOAD 0 is a collateral stub, which may be perfectly fine to leave.

CAVEAT WORTH KNOWING. LOAD is computed on the parents graph as recorded. A person
whose ancestry the vault has not yet entered scores LOAD 0 no matter how important
they are in life — the number measures what THIS VAULT would lose, not historical
significance. Read it as "what does the vault stand to lose here", nothing more.
"""

import argparse
import os
import re
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_person_index as g  # noqa: E402
import vault_config  # noqa: E402

PARENT_IDS_RE = re.compile(r"parents:\s*'\[([^\]]*)\]'")
ID_RE = re.compile(r"(P-[0-9A-Za-z]{4,10})")
LIVING_RE = re.compile(r"life_status:\s*(living|unknown)")
SOURCES_RE = re.compile(r"^\s*-\s*\*\*(?:Sources|FS-attached sources)", re.M)
PLACEHOLDER_RE = re.compile(r"^\s*unknown\s*;\s*unknown\s*(;|$)", re.I)
LOCATOR_RE = re.compile(r"ark:/\d+/|\b(?:fs|antenati|metryki|anc|wt):[0-9a-zA-Z:./_-]{4,}|\b\d:\d:[0-9A-Z-]{4,}")
APPARATUS_RE = re.compile(r"Cawley|Medlands|Richardson|Complete Peerage|ODNB|Copinger|Coppinger|"
                          r"Visitation|History of Parliament|VCH|Great Migration|NEHGR|Macnamara|"
                          r"Muskett|Vital Records of|inquisition|will dated|Domesday", re.I)


def parent_ids(meta_block):
    """The `id`s in this entry's `parents:` list, with any trailing `?` stripped."""
    m = PARENT_IDS_RE.search(meta_block or "")
    if not m:
        return []
    return ID_RE.findall(m.group(1))


def bodies_by_id(vault):
    """Full narrative block per entry, through the model-agnostic person_store seam.

    Same reasoning as extension_frontier.rows_with_bodies: the meta line alone does
    not tell you whether an entry has been written up, and a shape-based chunker
    misses entries written as `- **Name**` bullets.
    """
    import person_store as PS
    out = {}
    for rec, _path, _hline, block in PS.iter_entry_blocks(vault):
        if not rec.id:
            continue
        text = block if isinstance(block, str) else "\n".join(block)
        if rec.id not in out or len(text) > len(out[rec.id]):
            out[rec.id] = text
    return out


def thinness(row, body, records):
    """0-6, measuring whether the person has been WORKED. Higher = barer entry.

    ⚠ THIS IS THE SECOND VERSION, AND THE FIRST ONE WAS WRONG (25 JUL 2026).
    v1 scored `profile_status: stub`, a missing `evidence_tier` and a missing
    `- **Sources**` bullet. Those measure whether an entry follows the CURRENT
    METADATA CONVENTIONS, not whether anyone researched the person — and the two
    diverge badly for entries written before the conventions tightened.

    v1's top-ranked keystone was **a Gen-8 direct ancestor** who is one of the
    best-documented people in the reference vault: WELL_SOURCED with 5 record ARKs,
    five primary records, a decisive 1850 census proof, a full life trajectory. Her
    only real defect is that her meta block still says `stub` because nobody
    relabelled it after the May 2026 research. **Measured across that vault, 97
    entries are labelled `stub` while the census credits them records, 26 of them
    WELL_SOURCED and one with 63 ARKs.** So the label is unreliable and must not be
    the input.

    v2 measures the BODY and the RECORD COUNT instead, with the census as a veto.
    Metadata staleness is still worth fixing, but it is a different and much cheaper
    problem — see `stale_meta()` and `--stale-meta`.
    """
    score, why = 0, []
    bullets = len([ln for ln in (body or "").splitlines()
                   if ln.strip().startswith("-") and "meta:" not in ln])
    has_loc = bool(LOCATOR_RE.search(body or ""))
    has_app = bool(APPARATUS_RE.search(body or ""))
    if bullets <= 1:
        score += 3; why.append(f"no-writeup({bullets}b)")
    elif bullets <= 3:
        score += 1; why.append(f"thin-writeup({bullets}b)")
    if not (row.get("born") or "").strip() and not (row.get("died") or "").strip():
        score += 2; why.append("no-vitals")
    if not has_loc and not has_app:
        score += 1; why.append("no-source-of-any-kind")
    paren = (row.get("header_paren") or "").strip()
    if PLACEHOLDER_RE.match(paren):
        score += 1; why.append("placeholder-header")
    # THE VETO: a person the census credits with records has demonstrably been
    # researched, whatever their meta block claims.
    if records >= 4:
        score = min(score, 1); why.append("[capped: WELL_SOURCED]")
    elif records >= 1:
        score = min(score, 3); why.append(f"[capped: {records} ARKs]")
    return min(score, 6), why


def stale_meta(row, body, records):
    """Entry has clearly been worked but its meta block still understates it.

    A different problem from thinness and a much cheaper one: it is a relabelling,
    not research. It matters because `profile_status` and `evidence_tier` are inputs
    to other judgements, so a stale label quietly corrupts them.
    """
    ps = (row.get("profile_status") or "").strip()
    tier = (row.get("tier") or "").strip()
    bullets = len([ln for ln in (body or "").splitlines()
                   if ln.strip().startswith("-") and "meta:" not in ln])
    worked = records >= 1 or bullets >= 4 or APPARATUS_RE.search(body or "")
    if not worked:
        return None
    flags = []
    if ps == "stub":
        flags.append(f"says-stub(but {records} ARKs, {bullets} bullets)")
    if not tier or tier == "None":
        flags.append("no-evidence_tier")
    return ", ".join(flags) or None


def reachable(roots, edges, skip=None):
    """Everything reachable from `roots` following child -> parent edges."""
    seen, q = set(), deque(r for r in roots if r != skip)
    seen.update(q)
    while q:
        n = q.popleft()
        for p in edges.get(n, ()):
            if p == skip or p in seen:
                continue
            seen.add(p); q.append(p)
    return seen


def census_records(vault):
    """FS PID -> record count, from harvest_sources. The one honest answer to
    "has anyone actually sourced this person?" — it counts RECORDS, not labels.
    Returns {} if the census cannot be run, in which case THIN loses its veto and
    the report says so rather than silently over-flagging."""
    import subprocess
    try:
        r = subprocess.run([sys.executable,
                            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "harvest_sources.py"), "--csv"],
                           capture_output=True, text=True, timeout=600,
                           env={**os.environ, "AUTORESEARCH_VAULT": vault})
    except Exception:
        return {}
    out = {}
    for ln in r.stdout.splitlines()[1:]:
        parts = ln.split(",")
        if len(parts) > 6 and parts[6].strip().isdigit():
            out[parts[0]] = int(parts[6])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--limit", type=int, default=25,
                    help="rows to print (default 25)")
    ap.add_argument("--min-load", type=int, default=1,
                    help="only rows carrying at least this many dependants (default 1)")
    ap.add_argument("--min-thin", type=int, default=3,
                    help="only rows this bare or barer, 0-6 (default 3)")
    ap.add_argument("--all", action="store_true",
                    help="ignore --min-load/--min-thin; rank everything")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--stale-meta", action="store_true",
                    help="instead: entries the meta block UNDERSTATES "
                         "(says stub / no tier while the body and the census "
                         "show real work). A relabelling backlog, not research.")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    rows = {r["id"]: r for r in g.parse_narrative() if r.get("id")}
    bodies = bodies_by_id(vault)
    recs = census_records(vault)
    if not recs:
        print('  [warn] census unavailable; THIN veto disabled', file=sys.stderr)

    # child -> parents, restricted to ids that actually exist (build_edges --validate
    # keeps dangling refs at 0, but never trust that here; a dangling ref would
    # silently inflate LOAD).
    edges = {}
    for pid, r in rows.items():
        ps = [p for p in parent_ids(r.get("block")) if p in rows]
        if ps:
            edges[pid] = ps

    # Roots = people nobody names as a parent: the anchors, plus any recorded
    # collateral descendants. Using in-degree rather than the configured anchor
    # avoids matching people by name, which is exactly what this vault's identity
    # model exists to prevent.
    is_parent = {p for ps in edges.values() for p in ps}
    roots = [pid for pid in rows if pid not in is_parent]

    base = reachable(roots, edges)
    load = {}
    for pid in rows:
        if pid not in base:
            load[pid] = 0
            continue
        lost = len(base) - len(reachable(roots, edges, skip=pid))
        load[pid] = max(lost - 1, 0)  # exclude the removed person themself

    out = []
    for pid, r in rows.items():
        if LIVING_RE.search(r.get("block") or ""):
            continue  # never a research target
        body = bodies.get(pid, "")
        n = recs.get((r.get("pid") or "").strip(), 0)
        thin, why = thinness(r, body, n)
        out.append({
            "id": pid, "name": r.get("name") or "?", "gen": r.get("gen") or "",
            "file": r.get("file") or "?", "load": load.get(pid, 0),
            "thin": thin, "why": ",".join(why), "recs": n,
            "stale": stale_meta(r, body, n) or "",
            "score": load.get(pid, 0) * thin,
        })

    if not a.all:
        out = [o for o in out if o["load"] >= a.min_load and o["thin"] >= a.min_thin]
    out.sort(key=lambda o: (-o["score"], -o["load"], -o["thin"], o["name"]))

    if a.stale_meta:
        st = [o for o in out if o["stale"]]
        st.sort(key=lambda o: (-o["recs"], -o["load"], o["name"]))
        print("=== STALE META — entries whose meta block UNDERSTATES the work done ===")
        print("    Not research: a relabelling. It matters because profile_status and")
        print("    evidence_tier feed other judgements, so a stale label corrupts them.")
        print()
        print(f"{'ARKs':>5} {'LOAD':>5}  {'NAME':<40} FLAGS")
        for o in st[:a.limit]:
            print(f'{o["recs"]:>5} {o["load"]:>5}  {o["name"][:40]:<40} {o["stale"]}')
        print(f"\n  {len(st)} entries understate themselves; showing {min(a.limit,len(st))}.")
        return 0

    if a.summary:
        print(f"KEYSTONES: {len(out)} thin entries carrying dependants "
              f"(load>={a.min_load}, thin>={a.min_thin}); "
              f"top score {out[0]['score'] if out else 0}")
        return 0

    if a.csv:
        print("id,name,gen,load,thin,score,why,file")
        for o in out[:a.limit if a.limit else None]:
            print(f'{o["id"]},"{o["name"]}",{o["gen"]},{o["load"]},{o["thin"]},'
                  f'{o["score"]},{o["why"]},{o["file"]}')
        return 0

    print("=== KEYSTONE REPORT — thin entries the tree leans on ===")
    print(f"    LOAD = people who become unreachable if this entry is removed")
    print(f"    THIN = how UNWORKED the entry is, 0-6 (no write-up, no vitals, no source")
    print(f"           of any kind). Capped when the census credits real records.")
    print(f"    filters: load>={a.min_load}, thin>={a.min_thin}"
          + ("  [DISABLED: --all]" if a.all else ""))
    print()
    print(f"{'SCORE':>6} {'LOAD':>5} {'THIN':>4}  {'GEN':>3}  {'NAME':<38} WHY")
    for o in out[:a.limit]:
        print(f'{o["score"]:>6} {o["load"]:>5} {o["thin"]:>4}  {o["gen"]:>3}  '
              f'{o["name"][:38]:<38} {o["why"]}')
    print()
    print(f"  {len(out)} rows match; showing {min(a.limit, len(out))}.")
    print("  A keystone is high LOAD + high THIN: the tree leans on it and nobody")
    print("  has written it up. High LOAD with THIN 0 is the desired end state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
