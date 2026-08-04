#!/usr/bin/env python3
"""Put a POINTER TO PRIOR RESEARCH on the person entry that prior research is about.

⭐ WHY THIS EXISTS, and it is the operator's diagnosis, not mine (03 AUG 2026,
session #138). Over roughly twenty sittings the dominant failure has been
**re-deriving work already done**: a route re-proposed that a log closed months
earlier, a candidate re-suggested that an earlier session rejected, a finding
written up that a prior log already retracted. Session #137 lost two findings that
way and wrote a bolded warning into `Handoff.md` -- "BEFORE RESEARCHING ANY
QUESTION, GREP logs/". Session #138 read that warning during phase 1 and then made
the same mistake four more times.

So the rule was DELIVERED, READ, AND INEFFECTIVE. This vault's standing principle
is that an un-mechanized rule drifts; this script is that principle applied to the
prior-work check.

⭐ **THE INSIGHT IS THAT THE ENTRY IS THE UNAVOIDABLE SURFACE.** A coverage ledger
or a lookup script needs somebody to REMEMBER it. The person's entry does not --
it is already open, because it is impossible to work a person without reading it.
Put the pointer where the reader already is.

MEASURED BEFORE BUILDING (03 AUG 2026):

    log files in the vault                    443
    people identifiable in logs             1,073
    people whose entry links >= 1 log         101
    PEOPLE WITH LOG WORK AND NO POINTER     1,071
    missing (person, log) pairs             2,832

    worst: one ancestor with 19 prior sessions and zero pointers; another whose
    30 attached sources were being audited in the very sitting that raised this
    had 12, including a prior source-harvest log for his own line.

⚠ **MATCHED ON IDENTIFIERS, NEVER ON NAMES.** A log is credited to a person only
when it contains that person's vault `id` or one of their external ids (FS/WT/ANC)
AND that id resolves to exactly one vault entry. Name matching would attach the
wrong [ANCESTOR] to the wrong entry in a village where three generations share a
forename -- the exact hazard this methodology checks on identifiers everywhere
else.

⚠ **A CREDITED LOG IS "THIS LOG DISCUSSED THIS IDENTIFIER", NOT "THIS LOG IS ABOUT
THIS PERSON."** A log that considered and REJECTED a PID still cites it, and that
is correct behaviour here: the rejection is exactly the prior work a later session
must not redo.

Usage:
    python3 scripts/log_backlinks.py                 # report the gap (default)
    python3 scripts/log_backlinks.py --limit 20      # worst N offenders
    python3 scripts/log_backlinks.py --person P-XXXXXX
    python3 scripts/log_backlinks.py --apply         # write the bullets
    python3 scripts/log_backlinks.py --heartbeat     # one line, for the banner
"""
import argparse
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import person_store  # noqa: E402
import vault_config  # noqa: E402

VAULT_ID_RE = re.compile(r"\bP-[0-9A-Z]{6}\b")
# External-id shape (FS PID / WikiTree-ish). Deliberately loose: it is only ever
# used to LOOK UP a token in the vault's own id table, so a false shape match
# simply fails the lookup and is discarded.
EXT_ID_RE = re.compile(r"\b[0-9A-Z]{4}-[0-9A-Z]{3,4}\b")

LOG_LINK_RE = re.compile(r"\[\[(logs/[^\]|#]+?)\s*(?:\||\]\])")
BOLD_HEADER_RE = re.compile(r"^\*\*(.+?)\*\*")
META_RE = re.compile(r"^\s*-\s*meta:\s*\{")
META_ID_RE = re.compile(r"\bid:\s*(P-[0-9A-Za-z]+)")

BULLET_MARK = "**Prior work**"
# Regenerated in place, so re-running updates rather than duplicating.
BULLET_RE = re.compile(r"^- \*\*Prior work\*\*.*$", re.M)


def build_identifier_table(people):
    """token -> vault id, for tokens that resolve UNIQUELY.

    ⚠ A token claimed by two people is DROPPED, not guessed. DUP_FS_PID is an
    advisory gate with a real (if small) baseline, and a shared PID must never
    silently attach one person's history to another."""
    claims = collections.defaultdict(set)
    for p in people:
        claims[p.id].add(p.id)
        for value in (p.external_ids or {}).values():
            if not value:
                continue
            v = str(value)
            if v in ("TBD", "none") or v.startswith("~"):
                continue  # not-searched / no-profile / DECLINED are not identities
            claims[v].add(p.id)
    return {tok: next(iter(ids)) for tok, ids in claims.items() if len(ids) == 1}


def logs_mentioning(vault, ident):
    """vault id -> set of log slugs that cite one of that person's identifiers."""
    out = collections.defaultdict(set)
    for path in glob.glob(os.path.join(vault, "logs", "*.md")):
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        slug = "logs/" + os.path.basename(path)[: -len(".md")]
        for tok in set(VAULT_ID_RE.findall(text)) | set(EXT_ID_RE.findall(text)):
            vid = ident.get(tok)
            if vid:
                out[vid].add(slug)
    return out


def iter_entry_blocks(vault):
    """Yield (path, lines, start, end, vault_id) per bold-name entry.

    Entry boundaries follow the vault's own rule: a bold name AT LINE START opens
    an entry (spec/entry-boundary). Identity is the meta `id:`, never the name."""
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().split("\n")
        starts = [i for i, l in enumerate(lines) if BOLD_HEADER_RE.match(l)]
        for n, i in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(lines)
            block = "\n".join(lines[i:end])
            m = META_ID_RE.search(block) if "- meta:" in block else None
            if m:
                yield path, lines, i, end, m.group(1)


def existing_links(block):
    return {s.rstrip() for s in LOG_LINK_RE.findall(block)}


def render_bullet(slugs):
    """Newest first -- log slugs begin YYYY-MM-DD, so a reverse sort is by date."""
    ordered = sorted(slugs, reverse=True)
    links = ", ".join(f"[[{s}]]" for s in ordered)
    n = len(ordered)
    return (f"- {BULLET_MARK} ({n} prior session{'s' if n != 1 else ''}, newest first) "
            f"-- READ BEFORE RESEARCHING THIS PERSON: {links}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--apply", action="store_true", help="write the bullets")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--person", help="report one vault id")
    ap.add_argument("--heartbeat", action="store_true")
    args = ap.parse_args(argv)

    vault = vault_config.resolve_vault(args.vault)
    people = list(person_store.iter_people(vault))
    byid = {p.id: p for p in people}
    ident = build_identifier_table(people)
    mentions = logs_mentioning(vault, ident)

    gap, linked, total_pairs = {}, 0, 0
    for path, lines, start, end, vid in iter_entry_blocks(vault):
        block = "\n".join(lines[start:end])
        have = existing_links(block)
        if have:
            linked += 1
        want = mentions.get(vid, set())
        missing = want - have
        if missing:
            gap[vid] = (path, start, end, want, missing)
            total_pairs += len(missing)

    if args.heartbeat:
        print(f"LOG_BACKLINKS: {len(gap)} entries with prior log work and no pointer "
              f"({total_pairs} pairs); {linked} entries already linked  [advisory]")
        return 0

    if args.person:
        vid = args.person
        want = mentions.get(vid, set())
        p = byid.get(vid)
        print(f"{vid}  {p.name if p else '(not found)'}")
        if not want:
            print("  no log cites this person's identifiers")
        for s in sorted(want, reverse=True):
            print(f"  {s}")
        return 0

    print("=== LOG BACKLINKS — prior research reachable from the entry? ===")
    print(f"  people identifiable in logs          : {len(mentions)}")
    print(f"  entries already linking >= 1 log     : {linked}")
    print(f"  ENTRIES WITH LOG WORK, NO POINTER    : {len(gap)}")
    print(f"  missing (person, log) pairs          : {total_pairs}")
    if gap:
        print(f"\n  worst {min(args.limit, len(gap))} (most prior sessions, no pointer):")
        for vid, (_p, _s, _e, _w, missing) in sorted(
                gap.items(), key=lambda kv: -len(kv[1][4]))[:args.limit]:
            p = byid.get(vid)
            print(f"    {vid}  {(p.name[:38] if p else '?'):40} {len(missing)} logs")

    if not args.apply:
        print("\n  (report only; --apply writes a `- **Prior work**` bullet per entry)")
        return 0

    # Write, file by file, bottom-up so earlier insertions cannot shift later ones.
    by_file = collections.defaultdict(list)
    for vid, (path, start, end, want, _m) in gap.items():
        by_file[path].append((start, end, vid, want))
    written = 0
    for path, items in by_file.items():
        lines = open(path, encoding="utf-8").read().split("\n")
        for start, end, vid, want in sorted(items, key=lambda t: -t[0]):
            block_lines = lines[start:end]
            # Drop any previous bullet so this is a regeneration, not an append.
            block_lines = [l for l in block_lines if not BULLET_RE.match(l)]
            # ⚠ INSERT AFTER THE `- meta:` LINE. The vault's meta_presence gate
            # warns that a bullet placed ABOVE it makes the roster and prose_audit
            # read the WRONG display name and vitals.
            pos = next((k for k, l in enumerate(block_lines) if META_RE.match(l)), None)
            if pos is None:
                continue
            block_lines.insert(pos + 1, render_bullet(want))
            lines[start:end] = block_lines
            written += 1
        open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"\n  APPLIED: {written} entries given a `{BULLET_MARK}` pointer bullet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
