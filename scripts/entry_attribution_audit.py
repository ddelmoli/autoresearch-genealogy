#!/usr/bin/env python3
"""ENTRY_ATTRIBUTION — narrative text that landed on the WRONG PERSON.

The fault this catches is not malformed markdown. It is *well-formed markdown
attached to the wrong entry*: a bullet that reads perfectly, sits under a real
bold-name header, and is about somebody else.

** WHY A SEPARATE GATE FROM entry_boundary_audit. ** That gate asks whether the
PARSER and the markdown agree about where entries begin, and when it fires its
own instruction is "the fault is in the parser, do not rewrite the narrative".
This asks a different question — whether the CONTENT belongs to the entry it
landed in — and the two must not be merged, or a gate with a precise meaning
becomes a vague one. On 20 AUG 2026 (session #175) six of fourteen bullets went
onto neighbouring entries and entry_boundary_audit read 0 for all of them,
correctly.

HOW IT JUDGES. For each line in scope it finds the entry that owns it, extracts
the identifiers the line names (vault `P-` ids and external ids from the host
registry), and reports a line that names an identifier belonging to some OTHER
entry which is not edge-adjacent to the owner. Cross-references between related
people are ordinary and are not reported.

⚠⚠ WHAT IT CANNOT SEE, said plainly so nobody trusts it further than it goes:

  * a misfiled bullet that names NO identifier at all, or names only the owning
    entry's own. This is not hypothetical: in the incident one note landed on the
    subject's SPOUSE and cited only the spouse's own PID, so there was no foreign
    identifier to notice. **Five of those six were catchable here; that one was not.**
  * anything about whether the PROSE is true.

The real fix for the class is `person_store.add_entry_bullet`, which places a
bullet by PERSON ID and so cannot land at a stale offset. This gate is the
backstop for hand-edits and for text that arrived before that writer existed.

** THIS GATE IS CHANGED-ONLY BY DESIGN, AND ITS WHOLE-VAULT COUNT IS NOT A
BASELINE. ** Measured on a real vault the full scan reports ~235, and reading them
shows they are overwhelmingly ORDINARY: an entry naming a cousin, a merged
duplicate, an FS dup-found profile. ⛔ Do NOT drive that number to zero — the
cross-references it lands on are the ones a genealogy exists to make, and
"fixing" them would damage the vault. Run the survey to LOOK for something; run
`--changed-only` to gate.

CALIBRATION, on the commit that produced the incident (vault `3fc2f81`, #175 iter
3): **210 added lines across 37 files -> 1 finding, and it was the misfiled
bullet.** Zero false positives on the other 209.

USAGE
  python3 scripts/entry_attribution_audit.py --changed-only   # staged, pre-commit
  python3 scripts/entry_attribution_audit.py --backlog        # un-triaged survey
"""
import argparse
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import person_store
import vault_config
from header_audit import staged_header_lines, materialise_staged

PATHSPECS = ("Family_Tree*.md",)

_VAULT_ID = re.compile(r"\bP-[0-9A-Z]{6}\b")
# FS-PID shape: XXXX-XXX. Deliberately narrow: a wider pattern collects dates,
# film numbers and ARK fragments, and a noisy gate gets switched off.
_FS_PID = re.compile(r"\b[0-9A-Z]{4}-[0-9A-Z]{3}\b")


def _adjacency(people):
    """id -> set of ids it may mention without comment: parents, spouse, children,
    and SIBLINGS.

    ⚠ Siblings matter more than the other three put together here. A first cut
    without them reported 292 findings on a real vault, and the samples were
    almost all ordinary prose — a sibling named in passing, a merged-duplicate
    note, an FS dup-found record. Those are exactly the cross-references a
    genealogy entry exists to make, and a gate that reports them is a gate that
    gets turned off.
    """
    adj = {p.id: set() for p in people if p.id}
    kids_of = {}
    for p in people:
        if not p.id:
            continue
        for tok in list(p.parents or []) + list(p.spouse or []):
            other = str(tok).rstrip("?").strip()
            if other in adj:
                adj[p.id].add(other)
                adj[other].add(p.id)
        for tok in (p.parents or []):
            kids_of.setdefault(str(tok).rstrip("?").strip(), set()).add(p.id)
    for sibs in kids_of.values():          # share a parent -> siblings
        for a in sibs:
            adj.setdefault(a, set()).update(sibs - {a})
    return adj


def _identifier_owners(people):
    """identifier -> owning vault id, for both vault ids and live external ids."""
    owners = {}
    for p in people:
        if not p.id:
            continue
        owners[p.id] = p.id
        for host in (p.external_ids or {}):
            live = person_store.live_external_id((p.external_ids or {}).get(host))
            if live:
                owners.setdefault(live, p.id)
    return owners


def scan(vault, only=None, index_vault=None):
    """only = {relpath: {1-based linenos}} restricts the scan (--changed-only).

    ⚠⚠ `index_vault` is not optional in practice, and getting it wrong makes the
    gate SILENTLY USELESS. In --changed-only mode `vault` is a temp dir holding
    only the STAGED files, which is right for reading the text about to be
    committed — but an identifier index built from it knows only the people in
    those few files, so every foreign PID resolves to nobody and nothing is ever
    reported. That is a gate that passes because it cannot see, and it survived a
    validation run only because the commit tested happened to touch 37 files.
    Pass the REAL vault here: ownership and kinship are judged against the whole
    vault, the TEXT against the staged copy.
    """
    people = list(person_store.iter_people(index_vault or vault))
    owners = _identifier_owners(people)
    adj = _adjacency(people)
    names = {p.id: (p.name or "")[:34] for p in people if p.id}

    findings = []
    for rec, path, hline, block in person_store.iter_entry_blocks(vault):
        if not rec.id:
            continue
        rel = os.path.relpath(path, vault)
        wanted = only.get(rel) if only is not None else None
        if only is not None and not wanted:
            continue
        for off, line in enumerate(block.splitlines()):
            lineno = hline + off + 1          # 1-based
            if only is not None and lineno not in wanted:
                continue
            stripped = line.lstrip()
            if stripped.startswith(">"):      # generated route digest
                continue
            if stripped.startswith("- meta:"):  # edges legitimately name others
                continue
            if off == 0:                       # the bold-name header itself
                continue
            named = set(_VAULT_ID.findall(line)) | set(_FS_PID.findall(line))
            foreign = set()
            for ident in named:
                owner = owners.get(ident)
                if owner and owner != rec.id and owner not in adj.get(rec.id, ()):
                    foreign.add((ident, owner))
            if foreign:
                findings.append({
                    "path": rel, "line": lineno, "owner": rec.id,
                    "owner_name": names.get(rec.id, ""),
                    "foreign": sorted(foreign), "text": line.strip()[:88],
                })
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--changed-only", action="store_true",
                    help="judge ONLY lines added/modified in the staged diff")
    ap.add_argument("--backlog", action="store_true",
                    help="whole-vault survey. NOT a baseline-0 gate: most hits are "
                         "ordinary cross-references. Use it to look, not to zero.")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any finding (with --changed-only)")
    a = ap.parse_args()
    vault = vault_config.resolve_vault(a.vault)

    print("=== ENTRY_ATTRIBUTION — text credited to the wrong person ===\n")
    if a.changed_only:
        changed = staged_header_lines(vault, pathspecs=PATHSPECS)
        if not changed:
            print("  nothing staged in Family_Tree*.md.\n")
            print("ENTRY_ATTRIBUTION (changed): 0")
            return 0
        with tempfile.TemporaryDirectory() as tmp:
            materialise_staged(vault, list(changed), tmp)
            findings = scan(tmp, only=changed, index_vault=vault)
    elif a.backlog:
        findings = scan(vault)
    else:
        ap.error("choose --changed-only (the gate) or --backlog (the survey). "
                 "There is deliberately no default: the whole-vault count is not "
                 "a number to drive to zero.")

    for f in findings:
        print(f"  {f['path']}:{f['line']}  sits in {f['owner']} ({f['owner_name']})")
        for ident, owner in f["foreign"]:
            print(f"      names {ident}, which belongs to {owner} — not edge-adjacent")
        print(f"      {f['text']}")
    if findings:
        print("\n  Each is a CANDIDATE, not a verdict: an entry may legitimately discuss an")
        print("  unrelated person. Read the line. If the text is about the named person")
        print("  rather than the owner, it was misfiled — move it with")
        print("  person_store.add_entry_bullet(vault, <that person's id>, text).")
    if a.backlog:
        print("\n  ⛔ This is a SURVEY, not a baseline. Most of these are ordinary")
        print("     cross-references; driving the count to zero would damage the vault.")
    print(f"\nENTRY_ATTRIBUTION{' (changed)' if a.changed_only else ' (backlog survey)'}"
          f": {len(findings)}"
          f"{'  [BLOCKING]' if (a.changed_only and a.strict) else '  [advisory]'}")
    return 1 if (findings and a.changed_only and a.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
