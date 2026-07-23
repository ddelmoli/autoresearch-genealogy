#!/usr/bin/env python3
"""
meta_presence_audit.py — two structural checks on `- meta:` blocks.

1. META_PRESENCE — person narratives that carry NO `- meta:` block.

   gen_person_index detects entries *by* their `- meta:` line, so a person
   narrative with no meta block at all is invisible to the integrity gate
   (MISSING_ID can't fire — it needs a detected entry). Such an entry has no id,
   never appears in the roster, and (as a lineage-file split once showed) can be
   mis-routed by tooling that keys on meta. This walks the narratives directly
   and reports person-like bold headers whose block lacks a meta line.

   Person detection reuses tree_locator's heuristic (capitalized name tokens +
   particles, a date signal in the parenthetical, no embedded year) so
   section-label bold lines are not flagged.

2. ORPHANED_META — a meta block SEPARATED from its bold-name header.

   The mirror-image blind spot, and a nastier one because the entry still looks
   healthy. `gen_person_index.parse_narrative()` reads an entry's display name
   (and its vitals) from the line IMMEDIATELY ABOVE the meta line. If an editing
   session inserts explanatory bullets between the bold name and its meta block,
   the parser silently adopts whatever text precedes it: the roster then shows
   the person under a prose fragment, and `prose_audit` — which builds its
   canonical fact map from the same parser — files them under that fragment too,
   so no prose about that person can ever be drift-checked. Vitals get scraped
   from the wrong line as well.

   Nothing else catches this: the id is unique and the meta complete, so the
   integrity gate passes, and display names are not validated anywhere.

   Real instances found on the first run (22 JUL 2026): a Gen-35 ancestor whose
   roster row read "Also rejected:", and two Gen-3/Gen-4 ancestors whose rows read
   "MOLLIE HERSELF WAS A THREE-WAY OVER-MERGE ..." and "FS PROFILE CORRECTED
   20 JUL 2026 ..." — the latter also picking up nonsense birth/death years.

   The heuristic flags a meta block when the preceding non-blank line either has
   no leading bold segment at all, or has one that reads as prose rather than a
   name: an opening glyph (warning/check marks), a trailing colon, an ALL-CAPS
   run, or a date-stamp month token. It deliberately does NOT flag a trailing
   "Sr."/"Jr."/"Esq." or a year in the name parenthetical — both are legitimate
   naming conventions.

Both advisory (exit 0). Run standalone or from the SessionStart / pre-commit
suites.
"""
import glob
import os
import re
import sys

import tree_locator as T

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
META = re.compile(r"^\s*-\s*meta:")
# LENIENT header match — capture the bold name (ANY non-* chars, so names with
# embedded parens/slashes/quotes like "Evelyn (Eva) Maiden Smith" or
# "Abraham Meyer / Meier" are caught) + its parenthetical. tree_locator's
# strict HDR_A misses exactly these, which is why such entries became the blind
# spot. T._is_person then filters non-people (label bolds, year-in-name) via the
# same heuristic the rest of the suite uses.
HDR_LENIENT = re.compile(r"^\*\*([^*]+?)\*\*\s*\(([^)]{0,400})")

# --- ORPHANED_META ---------------------------------------------------------
# Strip bullet / blockquote / whitespace ONLY. Never strip '*' — that would eat
# the '**' bold markers this check depends on.
LEAD = re.compile(r"^[->\s]+")
BOLD_LEAD = re.compile(r"^\*\*(.+?)\*\*")
# Uppercase month tokens: the vault's date convention is "20 JUL 2026". Matching
# only the ALL-CAPS form keeps "May" as a given name from tripping the check.
MONTH_STAMP = re.compile(r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b")
NAME_OPENERS = "\"“[('"


def _prose_reason(name):
    """Return a short reason if this bold text reads as prose, else None.

    Tuned against the full corpus to zero false positives. Note what is
    deliberately NOT a signal: a trailing '.' (legitimate on "Sr." / "Jr." /
    "Esq." / "Gent.") and a bare year (the vault disambiguates same-name
    collaterals as "Given Surname (1795)").
    """
    n = (name or "").strip()
    if not n:
        return "empty"
    if not (n[0].isalpha() or n[0].isdigit() or n[0] in NAME_OPENERS):
        return "glyph"          # leading ✅ / ⚠ / ⛔ / ⭐ etc.
    if n.endswith(":"):
        return "colon"          # "Also rejected:", "Note:"
    if MONTH_STAMP.search(n):
        return "datestamp"      # "Update 20 JUL 2026"
    caps = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", n) if w.isupper()]
    if len(caps) >= 3:
        return "allcaps"        # shouted resolution notes
    return None


def audit_orphaned(vault=VAULT):
    """Meta blocks whose preceding non-blank line is not a bold-name header."""
    issues = []
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            if not META.match(line):
                continue
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            prev = lines[j].strip() if j >= 0 else ""
            mid = re.search(r"id:\s*(P-[0-9A-Z]+)", line)
            pid = mid.group(1) if mid else "?"
            m = BOLD_LEAD.match(LEAD.sub("", prev))
            if not m:
                issues.append((os.path.basename(path), i + 1, pid, "no-bold", prev[:70]))
                continue
            reason = _prose_reason(m.group(1))
            if reason:
                issues.append((os.path.basename(path), i + 1, pid, reason, m.group(1)[:70]))
    return issues


def audit(vault=VAULT):
    issues = []
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        bounds = [i for i, l in enumerate(lines)
                  if l.startswith("**") or re.match(r"^#{1,4}\s", l)]
        bounds.append(len(lines))
        for k, i in enumerate(bounds[:-1]):
            m = HDR_LENIENT.match(lines[i])
            if not m:
                continue
            name, paren = m.group(1), m.group(2)
            if not T._is_person(name, paren):
                continue
            if not any(META.match(b) for b in lines[i:bounds[k + 1]]):
                issues.append((os.path.basename(path), name.strip()))
    return issues


def main():
    vault_config.require_vault(VAULT)
    from collections import Counter

    issues = audit()
    print(f"META_PRESENCE violations: {len(issues)}  (person narratives with no `- meta:` block)")
    for fn, c in Counter(f for f, _ in issues).most_common():
        print(f"  {c:>3}  {fn}")
    for fn, name in issues:
        print(f"    - {fn}: {name}")

    orphans = audit_orphaned()
    print(f"ORPHANED_META violations: {len(orphans)}  "
          f"(`- meta:` separated from its bold-name header — parser reads the WRONG display name)")
    for fn, c in Counter(o[0] for o in orphans).most_common():
        print(f"  {c:>3}  {fn}")
    for fn, ln, pid, reason, text in orphans:
        print(f"    - {fn}:{ln}  {pid}  [{reason}]  reads as: {text}")
    if orphans:
        print("    FIX: move the `- meta:` line back to be the FIRST body bullet "
              "directly under its bold name (move it; never re-mint the id).")

    return 0  # advisory


if __name__ == "__main__":
    sys.exit(main())
