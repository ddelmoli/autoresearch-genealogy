#!/usr/bin/env python3
r"""Headless-block audit: a person's body bullets sitting under NO header of their own.

WHY THIS EXISTS. A narrative lineage file is parsed entry by entry: an entry is a
bold-name header whose next non-blank line is its `- meta:` block, and its body runs
until the next header or structural break. A BLANK LINE IS NOT A BREAK. So when a
block of body bullets loses its header -- a shard split that moves a header and meta
line but leaves the body behind, or a minting pass that writes the body below a blank
line instead of under the meta -- the parser silently folds the whole block into
whichever entry precedes it. That entry is credited with the orphan's text, its
`Sources` bullet included, and the real owner reads as having nothing.

The defect is invisible to every other gate, by construction:

* `entry_boundary_audit.py` compares the parser's attribution with a STRUCTURAL
  reading of the same Markdown. Both readings agree that a headless block belongs to
  the entry above it -- the Markdown really does say so -- so the invariant holds.
* `meta_presence_audit.py` looks for headers with no meta; a headless block has
  neither.
* `entry_attribution_audit.py` looks for text naming another person's id; a body
  rarely names its own owner's id.

Measured on the first vault it was run against (a sitting of 18 SEP 2026): five
headless blocks, each the body and scholarly `Sources` bullet of a person minted
weeks earlier, credited to the entry above; four of the five owners read UNCITED
while carrying citations, and every gate reported 0.

THE CHECK
---------
HEADLESS_BLOCK  (advisory, baseline 0)
    A run of lines that follows one or more BLANK lines inside an entry's body, whose
    first line is a top-level bullet (not a header, not a meta line, not a break),
    AND that shows one of the two marks of a separate person's body:

    (a) IDENTITY LEDE -- its first bullet announces an entry of its own: a
        `MINTED`, `CREATED` or `ADDED ... resolving` bullet (the vault's minting
        and structure-pass ledes).
        ⛔ NOT a pronoun-led bullet ("She ...", "His own ..."). It was tried and
        measured on the calibration vault: 0 true hits, 1 false one -- a host
        entry continuing across a blank line with "She was in a record this entry
        already cited", where "she" IS the host. A pronoun cannot say whose it is.
    (b) SECOND SOURCES -- the block carries its own `- **Sources**` bullet while the
        entry above already has one before the blank line. One person, one Sources
        bullet; two means two people.

    Why a DISCRIMINATOR and not "any bullet after a blank line": entries legitimately
    continue across a blank line (a `###` sub-heading inside an entry, a double blank
    line between an entry's bullets, an essay file). On the calibration vault a bare
    blank-then-bullet scan found the five real blocks plus three such continuations;
    the discriminator keeps the five and drops the three. It is still a heuristic:
    READ EVERY FLAGGED ROW before moving anything.

WHAT IT CANNOT SEE. A misfiled block with NO blank line above it -- bullets moved
into the middle of another entry's body -- is indistinguishable from that entry's
own text to any structural reader. The same sitting found one (two bullets about one
king sitting on another king's entry); only reading the entry caught it.

FIX, when a row is real: move the block under its owner's `- meta:` line with the
Edit tool (the owner is usually named in the block itself), then diff the census by
row (`census_diff.py`): the owner should gain its citation and the host should move
by exactly what it had borrowed.

Read-only. Edits nothing.

Usage:
    python3 scripts/headless_block_audit.py              # advisory; exit 0
    python3 scripts/headless_block_audit.py --strict     # exit 1 on any finding
"""

import argparse
import glob
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import vault_config
from harvest_sources import BREAK_LINE  # one definition of "structural break"
from entry_boundary_audit import _header_name_at_line, SOURCES_BULLET, META_LINE

# A TOP-LEVEL bullet: `- ` at column 0. An indented sub-bullet after a blank line is
# a continuation of the bullet above it, never a new body.
TOP_BULLET = re.compile(r"^[-*]\s+\S")

# Strip the emphasis marks and bold that lead a vault bullet, to reach its words.
_LEAD = re.compile(r"^[-*]\s+(?:[^\w\s*`\[]+\s*)*")

# (a) identity ledes. MINTED / CREATED are the vault's minting ledes; "ADDED ...
# resolving" is the structure-pass lede. Matched on the bullet's opening words only.
IDENTITY_LEDE = re.compile(
    r"^\**\s*(?:MINTED\b|CREATED\b|ADDED\b[^\n]{0,80}\bresolving\b)")


def _opening_words(line):
    """The bullet's text after its dash, emphasis marks and opening bold markers."""
    return _LEAD.sub("", line, count=1).lstrip("*").lstrip()


def identity_lede(line):
    """Why this first bullet reads as a new person's lede, or None."""
    return "identity lede" if IDENTITY_LEDE.match(_opening_words(line)) else None


def scan_text(text, fname="<text>"):
    """Return the HEADLESS_BLOCK findings in one file's text: a list of dicts."""
    lines = text.splitlines()
    findings = []
    owner = None            # name of the entry whose body we are in
    owner_line = None
    owner_has_sources = False
    blank_run = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if BREAK_LINE.match(line):
            owner, blank_run = None, 0
            i += 1
            continue
        name = _header_name_at_line(lines, i)
        if name:
            owner, owner_line, owner_has_sources, blank_run = name, i + 1, False, 0
            i += 1
            continue
        if not line.strip():
            blank_run += 1
            i += 1
            continue
        if owner and blank_run and TOP_BULLET.match(line) and not META_LINE.match(line):
            # A block starts here. It runs to the next blank line, header or break.
            j = i
            block_sources = False
            while j < len(lines) and lines[j].strip() and not BREAK_LINE.match(lines[j]) \
                    and not _header_name_at_line(lines, j):
                if SOURCES_BULLET.match(lines[j]):
                    block_sources = True
                j += 1
            reasons = []
            lede = identity_lede(line)
            if lede:
                reasons.append(lede)
            if block_sources and owner_has_sources:
                reasons.append("second Sources bullet")
            if reasons:
                findings.append({
                    "file": fname, "line": i + 1, "host": owner,
                    "host_line": owner_line, "lines": j - i,
                    "reasons": reasons, "first": line.strip()[:110],
                })
            if block_sources:
                owner_has_sources = True
            blank_run = 0
            i = j
            continue
        if SOURCES_BULLET.match(line):
            owner_has_sources = True
        blank_run = 0
        i += 1
    return findings


def audit(vault):
    """HEADLESS_BLOCK findings across every narrative lineage file of the vault."""
    if vault_config.get_person_model(vault) != "narrative":
        return []           # the file model has one person per file: no boundaries
    out = []
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        with open(path, encoding="utf-8") as f:
            out.extend(scan_text(f.read(), os.path.basename(path)))
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Headless-block audit: body bullets folded into the preceding entry.")
    ap.add_argument("--vault", default=None, help="Vault path (else AUTORESEARCH_VAULT).")
    ap.add_argument("--strict", action="store_true", help="Exit 1 on any finding.")
    ap.add_argument("--limit", type=int, default=20, help="Cap listing length.")
    args = ap.parse_args()

    vault = vault_config.resolve_vault(args.vault)
    found = audit(vault)

    print("=== HEADLESS-BLOCK AUDIT ===")
    print()
    for r in found[: args.limit]:
        print(f"  {r['file']}:{r['line']} ({r['lines']} lines, {', '.join(r['reasons'])})"
              f"  folded into '{r['host']}' (header line {r['host_line']})")
        print(f"      {r['first']}")
    if len(found) > args.limit:
        print(f"  ... and {len(found) - args.limit} more")
    if found:
        print("  READ EACH ROW: a candidate, not a verdict. If the block is another person's")
        print("  body, move it under that person's `- meta:` line and run census_diff.py.")
        print()
    print(f"HEADLESS_BLOCK: {len(found)}  [advisory; baseline 0]")
    return 1 if (found and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
