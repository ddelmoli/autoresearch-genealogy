#!/usr/bin/env python3
"""migrate_profile_status.py — re-derive `profile_status` where it UNDERSTATES the work.

WHY IT EXISTS (25 JUL 2026). `profile_status` is a documented field with defined
semantics in CLAUDE.method.md:

    complete   the entry carries a `- **Sources**` bullet citing either independent
               primary records (host:locator) or scholarly apparatus with pages
    partial    tiered but unsourced
    stub       thin / unassessed collateral

Measured on the reference vault, **97 entries say `stub` while the source census
credits them with records** — 26 of them `WELL_SOURCED`, one with **63 ARKs**. The
worst case was a **Gen-8 direct ancestor**: five primary records, a decisive 1850 census
proof, a full life trajectory written up in May 2026 — and a meta block still
reading `stub`, because nobody relabelled it afterwards.

**That is not a cosmetic problem.** `profile_status` is an input to other
judgements. A report that trusts it ranks a well-documented ancestor as unworked;
any "how complete is the vault" statement built on it is wrong by ~97 entries. The
field was quietly lying, and the fix belongs in the DATA, not in a veto bolted onto
each consumer.

WHAT IT CHANGES, AND WHAT IT REFUSES TO.

  UPGRADES ONLY, and only where an INDEPENDENT source proves the work exists:
    stub -> partial     when `harvest_sources` credits the person with >= 1 record
                        but the entry has no `- **Sources**` bullet, so `complete`
                        is not yet earned under the spec.
    stub -> complete    when the entry DOES carry a `- **Sources**` bullet.

  IT NEVER DOWNGRADES. A downgrade would delete a human judgement, and there is no
  mechanical way to tell "mislabelled complete" from "complete on scholarly
  apparatus this script cannot parse". Downgrades are a human call.

  IT NEVER TOUCHES `evidence_tier`. Absence of a tier means "unassessed", which is
  a legitimate state the spec defines — and quality is not derivable from record
  COUNT. A person with 60 ARKs can still be a Moderate identification.

⚠ WHAT IT CANNOT FIX, and why the residue is real work rather than a bug: an entry
whose sources sit in PROSE rather than in a `- **Sources**` bullet can only reach
`partial` here. Promoting it to `complete` means migrating those citations into the
bullet grammar, which needs a human because freeform prose does not map mechanically
onto one-record-per-sub-bullet. The type specimen in the reference vault has her
ARKs spread across four narrative bullets and a trailing `- Source:` line.

Dry-run by default, like every other migrator here. `--apply` writes.
"""

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_person_index as g  # noqa: E402
import vault_config  # noqa: E402

SOURCES_BULLET_RE = re.compile(r"^\s*-\s*\*\*Sources\*\*", re.M)
STATUS_RE = re.compile(r"(profile_status:\s*)(stub)\b")


def census_records(vault):
    """FS PID -> (record count, category) from harvest_sources. The independent witness.

    The CATEGORY matters as much as the count: `BOOK_SOURCED` means 0 ARKs but real
    scholarly apparatus, which the 23 JUL 2026 amendment to CLAUDE.method.md says
    earns `complete` just as records do — deliberately, so that medieval and peerage
    lines documented by charters and compilations are not permanently stuck at
    `stub` for lack of an ARK that can never exist.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, os.path.join(here, "harvest_sources.py"), "--csv"],
                       capture_output=True, text=True, timeout=900,
                       env={**os.environ, "AUTORESEARCH_VAULT": vault})
    out = {}
    for ln in r.stdout.splitlines()[1:]:
        p = ln.split(",")
        if len(p) > 6 and p[6].strip().isdigit():
            out[p[0]] = (int(p[6]), p[5].strip())
    return out


def bodies_by_id(vault):
    import person_store as PS
    out = {}
    for rec, _p, _h, block in PS.iter_entry_blocks(vault):
        if not rec.id:
            continue
        t = block if isinstance(block, str) else "\n".join(block)
        if rec.id not in out or len(t) > len(out[rec.id]):
            out[rec.id] = t
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    rows = [r for r in g.parse_narrative() if r.get("id")]
    recs = census_records(vault)
    if not recs:
        print("ERROR: source census returned nothing; refusing to migrate blind.",
              file=sys.stderr)
        return 2
    bodies = bodies_by_id(vault)

    plan = []
    for r in rows:
        if (r.get("profile_status") or "").strip() != "stub":
            continue
        pid = (r.get("pid") or "").strip()
        n, cat = recs.get(pid, (0, ""))
        # Proof of work = the census found RECORDS, or it found scholarly APPARATUS.
        if n < 1 and cat != "BOOK_SOURCED":
            continue  # no independent proof of work; leave it alone
        has_bullet = bool(SOURCES_BULLET_RE.search(bodies.get(r["id"], "")))
        plan.append({"id": r["id"], "name": r.get("name") or "?",
                     "file": r.get("file") or "?", "recs": n, "cat": cat,
                     "to": "complete" if has_bullet else "partial"})

    plan.sort(key=lambda x: (-x["recs"], x["cat"], x["name"]))
    to_c = sum(1 for p in plan if p["to"] == "complete")
    to_p = len(plan) - to_c

    print("=== profile_status re-derivation — UPGRADES ONLY ===")
    nbook = sum(1 for p in plan if p["cat"] == "BOOK_SOURCED")
    print(f"    {len(plan)} entries say `stub` while the census shows real work")
    print(f"    ({len(plan)-nbook} credited with RECORDS, {nbook} BOOK_SOURCED on scholarly apparatus).")
    print(f"    -> complete : {to_c}  (entry already has a `- **Sources**` bullet)")
    print(f"    -> partial  : {to_p}  (sources exist but in PROSE; `complete` not yet earned)")
    print()
    print(f"{'ARKs':>5}  {'CENSUS':<14} {'TO':<9} NAME")
    for p in plan[:a.limit]:
        print(f'{p["recs"]:>5}  {p["cat"][:14]:<14} {p["to"]:<9} {p["name"][:48]}')
    if len(plan) > a.limit:
        print(f"      ... and {len(plan)-a.limit} more")
    print()

    if not a.apply:
        print("(dry-run; re-run with --apply to write)")
        print("NOTE: nothing is ever downgraded, and evidence_tier is never touched.")
        return 0

    by_file = {}
    for p in plan:
        by_file.setdefault(p["file"], []).append(p)

    changed = files = 0
    for fname, items in sorted(by_file.items()):
        path = os.path.join(vault, fname)
        if not os.path.exists(path):
            print(f"  [skip] {fname}: not found", file=sys.stderr)
            continue
        lines = open(path, encoding="utf-8").read().split("\n")
        want = {p["id"]: p["to"] for p in items}
        hits = 0
        for i, ln in enumerate(lines):
            if "meta:" not in ln or "profile_status:" not in ln:
                continue
            m = re.search(r"\bid:\s*(P-[0-9A-Za-z]{4,10})", ln)
            if not m or m.group(1) not in want:
                continue
            # Rewrite ONLY this entry's own meta line, and only the stub token.
            new, n = STATUS_RE.subn(lambda mm: mm.group(1) + want[m.group(1)], ln, count=1)
            if n:
                lines[i] = new
                hits += 1
        if hits:
            open(path, "w", encoding="utf-8").write("\n".join(lines))
            files += 1
            changed += hits
        if hits != len(items):
            print(f"  [warn] {fname}: planned {len(items)}, rewrote {hits}", file=sys.stderr)

    print(f"APPLIED: {changed} meta blocks re-derived across {files} files.")
    print("Nothing downgraded; evidence_tier untouched.")
    print("Run the gates: gen_person_index --integrity, prose_audit, build_edges --validate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
