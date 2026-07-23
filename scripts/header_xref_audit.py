#!/usr/bin/env python3
"""header_xref_audit.py — advisory audit for cross-reference PIDs in bold-name header lines.

CLAUDE.md invariant #6 sub-rule (adopted 22 JUN 2026): a narrative entry's bold-name HEADER
must carry ONLY that entry's own FS PID, inside the name parenthetical:
    **Name** (vitals; FS PID XXXX-XXX)
Cross-reference PIDs (spouse / parent / child / sibling) belong in a body bullet, never the
name parenthetical. A foreign PID in the parenthetical breaks scripted Recipe-S source-bullet
insertion (it anchors on the header PID -> mis-attribution; see the 22 JUN 2026 header-PID
mis-attribution incident, which wrongly attached bullets to living relatives).

Refined 24 JUN 2026 (was: "any bold line with >1 PID anywhere"). The old heuristic counted
every PID on the bold-name LINE, but this vault writes a whole narrative paragraph ON that
line, so it flagged legitimate analytical prose and note/section lines (Q-notes, "REFUTED",
"Overlap validation", multi-person sibling lines) that merely *cite* multiple PIDs. Those are
not the anti-pattern: the machine-authoritative anchor is the meta `fs:`, and a PID downstream
in prose is not confusable with the entry's own PID. The refined audit:

  * Only considers a bold line that is a real PERSON ENTRY — i.e. followed by a `- meta:`
    block within 2 lines. Note/section lines (no meta) are skipped.
  * Counts only PIDs inside the bold-NAME PARENTHETICAL (the first balanced (...) right after
    the **bold name**). PIDs in the trailing narrative prose are ignored.

Two categories:
  HEADER_XREF        — >1 distinct PID in the name parenthetical (a foreign cross-ref where it
                       would be mistaken for the entry's own anchor). The real rule-6 violation.
  ANCHORLESS_LIVING  — the entry has NO own PID in its parenthetical but DOES carry PID(s) in
                       its line, AND its meta is life_status: living. This is the precise
                       incident hazard: a no-anchor LIVING entry whose line leads with a
                       relative's PID, which a line-based write-back could attach to a living
                       person. (Deceased no-anchor entries that cite kin PIDs are not flagged —
                       they are not the living-relative hazard.)

ARK fragments (1:1:/3:1:) are excluded so source bullets are never matched. Advisory only:
exit 0 always; --strict exits 1 when violations exist. --file scopes to one file.
"""
import argparse, glob, re, sys, os

PID = re.compile(r'(?<![:/A-Z0-9])([A-Z0-9]{4}-[A-Z0-9]{3})(?![A-Z0-9])')
ARK = re.compile(r'[13]:1:[A-Z0-9-]+')


def _pids(text):
    """Distinct PIDs in text, excluding any inside an ARK token."""
    masked = ARK.sub(' ', text)
    seen = []
    for m in PID.finditer(masked):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def name_paren(line):
    """The substring inside the first balanced (...) that immediately follows the leading
    **bold name** token. '' if there is no such parenthetical."""
    s = line.lstrip()
    if not s.startswith('**'):
        return ''
    close = s.find('**', 2)
    if close == -1:
        return ''
    rest = s[close + 2:]
    i = rest.find('(')
    if i == -1:
        return ''
    depth = 0
    for j in range(i, len(rest)):
        if rest[j] == '(':
            depth += 1
        elif rest[j] == ')':
            depth -= 1
            if depth == 0:
                return rest[i + 1:j]
    return rest[i + 1:]


def _meta_within(lines, i, lookahead=3):
    """Return the `- meta:` line text following header line index i, or None."""
    for k in range(i + 1, min(i + 1 + lookahead, len(lines))):
        if lines[k].lstrip().startswith('- meta:'):
            return lines[k]
    return None


def audit_file(path):
    """Return (header_xref, anchorless) lists of (lineno, own, foreign, snippet)."""
    lines = open(path, encoding='utf-8').read().split('\n')
    header_xref, anchorless = [], []
    for i, l in enumerate(lines):
        if not l.lstrip().startswith('**'):
            continue
        meta = _meta_within(lines, i)
        if meta is None:                       # not a person entry (note/section line)
            continue
        own = _pids(name_paren(l))
        if len(own) > 1:
            header_xref.append((i + 1, own[0], own[1:], l.strip()))
            continue
        if not own:
            line_pids = _pids(l)
            if line_pids and 'life_status: living' in meta:
                anchorless.append((i + 1, None, line_pids, l.strip()))
    return header_xref, anchorless


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', help='audit a single file')
    ap.add_argument('--strict', action='store_true', help='exit 1 if any violation')
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import vault_config
    files = [a.file] if a.file else sorted(glob.glob(os.path.join(vault_config.resolve_vault(), 'Family_Tree*.md')))
    total_hx = total_al = 0
    per_hx = {}
    print('=== header cross-reference PID audit (CLAUDE.md invariant #6) ===')
    for f in files:
        hx, al = audit_file(f)
        base = os.path.basename(f)
        if hx:
            per_hx[base] = len(hx)
            total_hx += len(hx)
            print(f'\n--- {base} ({len(hx)}) ---')
            for ln, own, foreign, snip in hx:
                print(f'  L{ln}: own={own} foreign={",".join(foreign)}')
                print(f'        {snip[:100]}')
        for ln, _own, foreign, snip in al:
            total_al += 1
            print(f'\n--- {base} [ANCHORLESS_LIVING] ---')
            print(f'  L{ln}: no own PID, line PIDs={",".join(foreign)} (life_status: living)')
            print(f'        {snip[:100]}')
    print('\n=== SUMMARY ===')
    print(f'  HEADER_XREF violations: {total_hx}')
    print(f'  ANCHORLESS_LIVING (no own PID + PID on a living entry line): {total_al}')
    for k, n in sorted(per_hx.items(), key=lambda x: -x[1]):
        print(f'    {n:>3}  {k}')
    if a.strict and (total_hx or total_al):
        sys.exit(1)


if __name__ == '__main__':
    main()
