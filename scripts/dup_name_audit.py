#!/usr/bin/env python3
"""dup_name_audit.py — advisory detector for same-person / different-id duplicates.

WHY THIS EXISTS. The HARD integrity gate (gen_person_index.py --integrity) keys
identity on the vault-owned meta `id`, so it catches DUP_ID (one id on two
entries) and flags DUP_FS_PID (one FS PID on two entries). It STRUCTURALLY cannot
catch the opposite failure: ONE real person adopted as TWO entries under two
DIFFERENT FS PIDs and two DIFFERENT ids. That pair has neither a shared id nor a
shared FS PID, so integrity passes clean. A "James A Smith XXXX-XXX / YYYY-YYY"
pair (one person adopted twice under two PIDs) is that class — found only by
manually listing the living. This advisory surfaces the class automatically.

DETECTION. Group entries (from gen_person_index.parse_narrative) by a normalized
name key (lowercased, punctuation stripped, single-letter middle initials
dropped, spaces removed — so "James A Smith" == "James Smith", and
"Anna Maria Da Costa" == "Annamaria Da Costa"). Within a name group that
spans >1 distinct id:

  DUP_STRONG    — two distinct ids share the SAME parsed birth year. High
                  precision: same name + same birth year is almost always one
                  person under two profiles.
  DUP_POSSIBLE  — two distinct ids share the SAME generation AND a birth year is
                  missing on at least one side (so we cannot prove they are
                  distinct). Review-needed, not a confident dup.

NOT flagged: same name + DIFFERENT known birth years. That is the legitimate
same-name-kin pattern endemic to onomastic naming traditions (e.g. two same-named
siblings b.1776 / b.1788 where the elder died in infancy; recurring given names
across cousins in the same parish). Flagging it would be pure noise.

Advisory only: exit 0 unless --strict (then exit 1 if any DUP_STRONG). Prints the
`DUP_NAME_STRONG:` / `DUP_NAME_POSSIBLE:` summary lines that session_audit.sh and
the pre-commit hook grep.
"""
import argparse, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_person_index as G
import harvest_pids as H


def nkey(name):
    """Normalized grouping key: lowercase, punctuation-free, single-letter tokens
    dropped, spaces removed."""
    s = re.sub(r'[^a-z0-9\s]', ' ', (name or '').lower())
    return ''.join(t for t in s.split() if len(t) > 1)


def _fmt(e):
    yr = e.get('_year') or '?'
    return (f"id {e.get('id')}  fs {e.get('pid') or e.get('fs') or '-'}  "
            f"Gen {e.get('gen')}  b.{yr}  [{e.get('file')}]  {e.get('name')}")


def audit():
    entries = G.parse_narrative()
    by_name = defaultdict(list)
    for e in entries:
        if not e.get('name'):
            continue
        e['_year'] = H.extract_year(e.get('born') or '')
        by_name[nkey(e['name'])].append(e)

    strong, possible = {}, {}      # frozenset(ids) -> (label, entries)
    for k, es in by_name.items():
        if not k or len({e['id'] for e in es}) < 2:
            continue
        # STRONG: same parsed birth year, distinct ids
        by_year = defaultdict(list)
        for e in es:
            by_year[e['_year']].append(e)
        for y, grp in by_year.items():
            ids = {e['id'] for e in grp}
            if y and len(ids) > 1:
                strong[frozenset(ids)] = (f'b.{y}', grp)
        # POSSIBLE: same generation, a birth year missing on >=1, not already STRONG
        by_gen = defaultdict(list)
        for e in es:
            by_gen[e['gen']].append(e)
        for g, grp in by_gen.items():
            ids = frozenset(e['id'] for e in grp)
            if len(ids) > 1 and any(not e['_year'] for e in grp) and ids not in strong:
                possible[ids] = (f'Gen {g}', grp)
    return strong, possible


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='exit 1 if any DUP_STRONG')
    a = ap.parse_args()
    strong, possible = audit()
    print('=== same-person duplicate audit (name + vitals; complements id-based integrity) ===')
    for label, grp in strong.values():
        print(f'\n--- DUP_STRONG ({label}; {len(grp)} entries, distinct ids) ---')
        for e in sorted(grp, key=lambda x: str(x.get('id'))):
            print('  ' + _fmt(e))
    for label, grp in possible.values():
        print(f'\n--- DUP_POSSIBLE ({label}; birth year missing on >=1) ---')
        for e in sorted(grp, key=lambda x: str(x.get('id'))):
            print('  ' + _fmt(e))
    print('\n=== SUMMARY ===')
    print(f'  DUP_NAME_STRONG: {len(strong)}')
    print(f'  DUP_NAME_POSSIBLE: {len(possible)}')
    if a.strict and strong:
        sys.exit(1)


if __name__ == '__main__':
    main()
