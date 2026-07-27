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

   ⚠ IT ALSO READS BULLET-FORM ENTRIES (`- **Name** (vitals)`), added 27 JUL 2026.
   It did not before, and that was a blind spot, not a design choice: the record
   layer (`person_store._BOLD`) has always accepted a leading bullet, so those
   people were real entries that this check could not see. It reported 0 while the
   deep-royal shards were full of meta-less person write-ups.

   KNOWN PRECISION, measured on the reference vault at the change (16 reported):
   11 are real, all in one file. The residue is 3 label bullets whose
   parenthetical happens to open with a date (`Sources`, `WWII Draft
   Registration`, a `Society of Descendants ...` line) plus 2 `SURNAME,FORENAME`
   military-audit rows that are arguably real people. Two structural false-positive
   classes ARE filtered: role-prefixed cross-references (`- **Wife: ...**`) and
   indented child-list items. **This is an ADVISORY count with a known ~30% false
   positive rate — read the rows, do not treat the number as a defect total.**
   There is also a known FALSE NEGATIVE class: `T._is_person` rejects bold names
   carrying an embedded parenthetical (`Duncan I (Donnchad mac Crínáin), King of
   Scots`), so some bullet entries are still missed. Tightening that is future work.

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
#
# ⚠ THE BULLET PREFIX IS LOAD-BEARING (added 27 JUL 2026). This pattern was
# anchored `^\*\*`, i.e. LINE START only — while `person_store._BOLD`, the reader
# that actually decides what an entry is, has always been `^\s*[-*]*\s*\*\*`, which
# ACCEPTS a leading bullet. So a person written as `- **Name** (vitals)` was a valid
# entry to the record layer and INVISIBLE to the audit whose whole job is to find
# missing meta blocks: META_PRESENCE could not report them, and reported 0 while the
# deep-royal shards were full of them. That bullet form is not a rarity — it is the
# dominant style in those shards (extension_frontier's docstring says so, having been
# bitten by the same divergence). Two readers disagreeing about what an entry is, the
# same defect family as spec/entry-boundary and the census PID-keying bug.
# Keep this prefix identical to `person_store._BOLD`'s.
HDR_LENIENT = re.compile(r"^\s*[-*]*\s*\*\*([^*]+?)\*\*\s*\(([^)]{0,400})")

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


# A bullet-form entry needs a STRICTER person test than a line-start one.
# `T._is_person` accepts any capitalized bold text whose parenthetical carries a
# date signal — fine at line start, where a body-bullet label never appears, and
# useless on bullets, where `- **Sources** (Recipe-S harvest 22 JUN 2026, ...)` is
# the single most common line in the vault. Enabling the bullet prefix without
# this filter reported 698 violations, of which the overwhelming majority were
# `Sources` bullets: a number that looks like a finding and is an artefact.
#
# The discriminator is the VITALS SLOT, which is what the header grammar already
# requires of a real entry: the parenthetical must OPEN with a date token (or
# carry an explicit `Gen N` / `FS PID`), not merely contain a date somewhere in
# running prose.
VITALS_PAREN = re.compile(
    r"^\s*(?:b\.|d\.|bapt\.|chr\.|born|died|m\.|c\.\s*\d|ABT|BEF|AFT|EST|CAL|BET|FROM|"
    r"\d{3,4}\s*[-–—]|\d{1,2}\s+[A-Z]{3}\s+\d{3,4}|\d{3,4}\s*[;)])",
    re.I)
GEN_OR_PID = re.compile(r"\bGen\s*\d+\b|\bFS(?:\s+PID|:)\s*[A-Z0-9]{4}-[A-Z0-9]{3}\b")


def _is_entry_paren(paren):
    """True when this parenthetical reads as an entry's vitals slot."""
    return bool(VITALS_PAREN.match(paren) or GEN_OR_PID.search(paren))


# Two structural shapes that are never entries, both observed in the first run:
#   `- **Wife: Lena Dora Buchdrucker** (1878-1943, FS ...)`  — a ROLE-PREFIXED
#     cross-reference. The vault writes kin cross-refs this way on purpose
#     (integrity rule 6 sends foreign PIDs to body bullets), so a colon inside the
#     bold name marks a pointer at somebody, not that person's own entry.
#   `  - **Thomas** (bapt. 25 SEP 1810 - Gen 7, our ancestor)` — an INDENTED
#     child-list item. A real entry bullet sits at column 0; a nested list is a
#     sub-item of the entry above it.
ROLE_PREFIX = re.compile(r"^\s*(?:wife|husband|spouse|sibling|siblings|child|children|"
                         r"son|daughter|father|mother|parents?|widow|widower)\s*:", re.I)


def _is_crossref_bullet(raw_line, name):
    return bool(raw_line[:1].isspace() or ":" in name or ROLE_PREFIX.match(name))


def audit(vault=VAULT):
    issues = []
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        # Block boundaries must use the SAME entry shape as HDR_LENIENT above,
        # or a bullet-style entry's block would run on to the next line-start
        # header and swallow that neighbour's meta line — reporting 0 for exactly
        # the entries this check exists to find.
        bounds = [i for i, l in enumerate(lines)
                  if re.match(r"^\s*[-*]*\s*\*\*", l) or re.match(r"^#{1,4}\s", l)]
        bounds.append(len(lines))
        for k, i in enumerate(bounds[:-1]):
            m = HDR_LENIENT.match(lines[i])
            if not m:
                continue
            name, paren = m.group(1), m.group(2)
            if not T._is_person(name, paren):
                continue
            # Bullet-form candidates must additionally show a vitals slot; a
            # line-start header is trusted as before, so this cannot mask any
            # violation the check already reported.
            if not lines[i].startswith("**"):
                if not _is_entry_paren(paren):
                    continue
                if _is_crossref_bullet(lines[i], name):
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
