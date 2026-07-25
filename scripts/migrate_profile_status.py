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
STATUS_RE = re.compile(r"(profile_status:\s*)(stub|partial)\b")
LOCATOR_RE = re.compile(r"ark:/\d+/|\b(?:fs|antenati|metryki|anc|wt|szukajwarchiwach):[0-9a-zA-Z:./_-]{4,}"
                        r"|\b\d:\d:[0-9A-Z-]{4,}")
APPARATUS_RE = re.compile(r"(?:Cawley|Medlands|Richardson|Complete Peerage|ODNB|Copinger|Visitation|"
                          r"History of Parliament|VCH|Great Migration|NEHGR|Macnamara|Muskett|"
                          r"Vital Records of|FreeREG|inquisition|will dated)", re.I)


def sources_bullet_text(body):
    """The `- **Sources**` bullet and its sub-bullets, or '' if there is none.

    Read directly from the entry because the source CENSUS only covers PID-bearing
    people: an entry sourced entirely to Ancestry or a parish register, with
    `fs: TBD`, is invisible to `harvest_sources` however well documented it is.
    Three such entries were found on the reference vault carrying real `anc:`
    locators and FreeREG register readings. Trusting only the census would have
    left them mislabelled forever.
    """
    m = SOURCES_BULLET_RE.search(body or "")
    if not m:
        return ""
    out, started = [], False
    for ln in (body or "").splitlines():
        if SOURCES_BULLET_RE.match(ln):
            started = True; out.append(ln); continue
        if started:
            if ln.strip().startswith("-") and not ln.startswith((" ", "\t")):
                break          # next top-level bullet ends the block
            out.append(ln)
    return "\n".join(out)


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
    empty_bullets = []
    for r in rows:
        cur = (r.get("profile_status") or "").strip()
        if cur not in ("stub", "partial"):
            continue
        body = bodies.get(r["id"], "")
        pid = (r.get("pid") or "").strip()
        n, cat = recs.get(pid, (0, ""))
        bullet = sources_bullet_text(body)
        # A bullet EARNS `complete` only if it actually cites something. An empty
        # `- **Sources**:` line is itself a defect, not a qualification.
        bullet_cites = bool(bullet) and bool(LOCATOR_RE.search(bullet)
                                             or APPARATUS_RE.search(bullet))
        # ⚠ A bullet that cites no LOCATOR is not thereby empty. Most such bullets
        # record a documented NEGATIVE ("0 record ARKs — structural gap", "primary
        # records at the parish, not on FS"), which CLAUDE.md's style rule
        # explicitly asks for: "Log negative results." Only a bullet with NO
        # payload at all is a defect.
        payload = re.sub(r"^\s*-\s*\*\*Sources\*\*\s*", "", bullet).strip(" :.\n\t")
        if bullet and not payload:
            empty_bullets.append(r.get("name") or "?")
        proof = (n >= 1) or cat == "BOOK_SOURCED" or bullet_cites
        if not proof:
            continue  # no independent proof of work; leave it alone
        to = "complete" if bullet_cites else "partial"
        if to == cur:
            continue  # already correct
        if cur == "partial" and to == "partial":
            continue
        plan.append({"id": r["id"], "name": r.get("name") or "?",
                     "file": r.get("file") or "?", "recs": n, "cat": cat,
                     "frm": cur, "to": to})

    plan.sort(key=lambda x: (x["frm"], -x["recs"], x["name"]))
    to_c = sum(1 for p in plan if p["to"] == "complete")
    to_p = len(plan) - to_c

    print("=== profile_status re-derivation — UPGRADES ONLY ===")
    fs_ = {}
    for p in plan:
        fs_[(p["frm"], p["to"])] = fs_.get((p["frm"], p["to"]), 0) + 1
    print(f"    {len(plan)} entries whose profile_status UNDERSTATES the work done.")
    for (frm, to), k in sorted(fs_.items()):
        note = ("entry carries a `- **Sources**` bullet that cites something"
                if to == "complete" else
                "sources exist but in PROSE; `complete` not yet earned")
        print(f"    {frm:>8} -> {to:<9} {k:>4}   ({note})")
    print()
    print(f"{'ARKs':>5}  {'CENSUS':<14} {'FROM':<8} {'TO':<9} NAME")
    for p in plan[:a.limit]:
        print(f'{p["recs"]:>5}  {p["cat"][:14]:<14} {p["frm"]:<8} {p["to"]:<9} {p["name"][:40]}')
    if len(plan) > a.limit:
        print(f"      ... and {len(plan)-a.limit} more")
    print()

    if empty_bullets:
        print(f"\n  [flag] {len(empty_bullets)} entries carry a `- **Sources**` bullet with NO")
        print( "         payload at all — a heading and nothing else. That IS a defect.")
        for nm in empty_bullets[:8]:
            print(f"           {nm[:60]}")
    else:
        print("\n  [ok] no contentless `- **Sources**` bullets.")
        print("       ⚠ NOTE FOR THE NEXT READER: a Sources bullet carrying no LOCATOR is")
        print("       NOT a defect. On the reference vault 43 such bullets record a")
        print("       documented NEGATIVE — '0 record ARKs, structural gap', 'primary")
        print("       records at the parish, not on FS', 'confirmed genuine gap, not a")
        print("       harvest miss'. CLAUDE.md asks for exactly that: 'Log negative")
        print("       results.' An earlier version of this flag reported them as empty")
        print("       and was wrong. Do not delete them and do not upgrade them.")
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
