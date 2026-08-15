#!/usr/bin/env python3
"""Gate: MIGRATE OR NEGATE -- never leave a bare ARK in prose.

A *bare ARK* is a record id the LEGACY counter (`harvest_sources.extract_arks`)
credits but the Spec 03 counter (`record_locators`) does not -- i.e. a token carrying
no `host:` prefix. The vault credits it either way, so the two spellings differ only in
whether a reader, a migrator, or a NEGATION can find it.

⭐⭐ WHY IT MATTERS, AND IT IS NOT TIDINESS (Open_Questions Q211). `~fs:1:1:XXXX-YYYY`
does not negate a bare `XXXX-YYYY` -- the `~` must attach to the token AS WRITTEN. So
the documented remedy is the wrong shape for exactly the sentences most likely to need
it, because retraction prose names an ARK the way a person talks about it:

    "it derived solely from the FS index of the 1857 marriage (ARK XXXX-YYYY,
     which lists '[a different woman]')"          <- credited, in the act of refuting it

Three confirmed instances were found that way, and two more on 14 AUG 2026 that a
retraction-word scan could not see because they exclude by IDENTITY instead
("a DIFFERENT [Name] ... NOT ours"; "REMOVED ... NOT this couple").

⛔⛔ THE RULE IS "MIGRATE OR NEGATE", NEVER "NEGATE". Measured 10 AUG 2026: of the
bare-token population, ~91% is ORDINARY EVIDENCE somebody never migrated -- a census
cited in a sentence, a christening index behind a parentage claim. They are counted and
they SHOULD be. Bulk-prefixing `~` would have silently destroyed 519 real citations,
which is the mirror image of the bug this gate exists for. Fix a finding by giving the
token its host prefix (`fs:1:1:...`), or by negating it (`~1:1:...`) when the prose is
refuting it. Never by deleting it.

TWO MODES, matching `header_audit.py`:
  (default)        whole vault, ADVISORY -- the migration backlog, watched for growth
  --changed-only   only lines added/modified in the STAGED diff, BLOCKING (exit 1)

The backlog is large and is burnt down incrementally; what must not happen is a commit
ADDING a new one. That asymmetry is the same one `header_audit` uses for the ~750-entry
legacy header backlog, and for the same reason: a gate nobody can pass is a gate
everybody disables.

    python3 scripts/bare_ark_audit.py                 # advisory report
    python3 scripts/bare_ark_audit.py --changed-only  # pre-commit gate
"""
import argparse
import os
import pathlib
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as H
import vault_config
from header_audit import staged_header_lines, materialise_staged   # ONE home for the diff plumbing


def bare_tokens(line: str):
    """Ids the legacy counter credits on this line that the Spec 03 counter does not.

    Both sides run `strip_negated_locators` first, so a `~`-negated token is absent
    from BOTH and is correctly never reported -- negation is a valid fix.
    """
    legacy = H.extract_arks(line)
    if not legacy:
        return []
    spec = {t.split(":")[-1] for t in H.record_locators(line)}
    return sorted(legacy - spec)


def audit(vault, only=None):
    """-> [(relpath, lineno, [tokens], line)] over Family_Tree*.md.

    `only` = {relpath: {linenos}} restricts the scan (the --changed-only mode).
    ⚠ Blockquoted lines are skipped: `route_digest.py` mirrors entry prose into a
    `> `-quoted digest at the head of each lineage file, so counting them would report
    every finding twice and make a fix look ineffective.
    """
    out = []
    for path in sorted(vault.glob("Family_Tree*.md")):
        rel = path.name
        if only is not None and rel not in only:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if only is not None and i not in only[rel]:
                continue
            if line.lstrip().startswith(">"):
                continue
            toks = bare_tokens(line)
            if toks:
                out.append((rel, i, toks, line.strip()))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", help="vault path (default: resolved as usual)")
    ap.add_argument("--changed-only", action="store_true",
                    help="judge ONLY lines added/modified in the staged diff; "
                         "EXITS 1 on a violation (pre-commit gate)")
    ap.add_argument("--warn-only", action="store_true",
                    help="with --changed-only: report but do not block")
    ap.add_argument("--list", action="store_true", help="print every finding")
    a = ap.parse_args()

    vault = pathlib.Path(vault_config.resolve_vault(a.vault))

    if a.changed_only:
        changed = staged_header_lines(vault)
        if not changed:
            print("=== bare ARKs in prose (spec/migrate-or-negate) — changed lines (staged) ===")
            print("  no Family_Tree line added or modified in this commit.\n")
            print("=== SUMMARY ===\n  changed lines evaluated:  0\n  BARE_ARK (changed):       0  [BLOCKING]")
            return 0
        with tempfile.TemporaryDirectory() as tmp:
            materialise_staged(vault, changed.keys(), tmp)
            findings = audit(pathlib.Path(tmp), only=changed)
        n = sum(len(t) for _, _, t, _ in findings)
        print("=== bare ARKs in prose (spec/migrate-or-negate) — changed lines (staged) ===")
        for rel, ln, toks, text in findings:
            print(f"  {rel}:{ln}  {','.join(toks)}")
            print(f"     {text[:150]}")
        if findings:
            print("\n  FIX: give the token its host prefix (`fs:1:1:...`) if it is a real "
                  "citation,\n       or negate it (`~1:1:...`) if the prose is refuting it. "
                  "Never delete it.")
        print(f"\n=== SUMMARY ===\n  changed lines evaluated:  {sum(len(v) for v in changed.values())}")
        print(f"  BARE_ARK (changed):       {n}  [{'advisory' if a.warn_only else 'BLOCKING'}]")
        return 1 if (n and not a.warn_only) else 0

    findings = audit(vault)
    ntok = sum(len(t) for _, _, t, _ in findings)
    distinct = len({t for _, _, toks, _ in findings for t in toks})
    files = len({f for f, _, _, _ in findings})
    if a.list:
        for rel, ln, toks, text in findings:
            print(f"  {rel}:{ln}  {','.join(toks)}")
            print(f"     {text[:150]}")
    print(f"BARE_ARK backlog: {ntok} token(s), {distinct} distinct, on {len(findings)} "
          f"line(s) across {files} file(s)  [advisory; MIGRATE or NEGATE, never delete]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
