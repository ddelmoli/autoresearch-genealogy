#!/usr/bin/env python3
r"""Entry-boundary audit: does the source-census parser attribute each `Sources`
bullet to the person the Markdown says owns it?

WHY THIS EXISTS (spec/entry-boundary). The census used to locate person entries with
shape-based regexes and turn every accepted match into a BODY BOUNDARY. One of those
regexes was not anchored to line start, so a bold-wrapped `Words (parenthetical)` span
in mid-sentence prose — an archive name, a record series, a relative named in passing —
became a phantom entry. The real entry's body was truncated there and everything below
it, commonly the whole `Sources` bullet, was re-attributed to the phantom.

That shape reader is GONE (23 JUL 2026): entries are detected by their `- meta:` block
through the `person_store` seam, which makes the phantom class unrepresentable rather
than merely filtered. This gate remains because the defect it guards is a CLASS, not
that one regex — any future boundary fault lands here.

That defect was SILENT. Every other gate stayed green (they use different parsers),
and whether the census actually lost the records depended on where the PID happened
to appear, so it surfaced only as the coverage number moving the WRONG WAY after an
unrelated edit. Measured on the reference vault before the fix: 124 latent phantom
headers, 92 under-credited people, and 3 entries reported as having ZERO sources
that in fact held 16, 11 and 3 records.

A patch alone does not close a silent defect class, so this is the detector.

THE CHECK
---------
ENTRY_MISATTRIBUTION  (HARD, baseline 0, exits 1)
    The parser-invariant test. For EVERY non-blank line in every lineage file, the
    owner computed STRUCTURALLY — the nearest bold-name header preceding it AT LINE
    START, with no `---` rule or `## ` heading in between — must equal the owner the
    census actually returned.

    The structural side is a deliberately independent implementation: a top-down
    line scan, where "starts its line" is a property of the line, not of regex
    offset arithmetic. So this asserts an INVARIANT rather than a regex. It catches
    any future boundary fault — an un-anchored pattern, a bad `body_end`, a broken
    structural-break rule, a dedup window that swallows a real header — regardless
    of which piece of the parser caused it.

    Scoped to whole-file ownership rather than to `Sources` bullets alone (the
    narrower first version) because the narrow check inherited the original bug's
    own conditionality: a phantom that truncates an entry carrying no `Sources`
    bullet was invisible to it. Widening cost one upstream fix at the time (entry
    starts were reported at the regex's swallowed `[\-\*\s]*` prefix rather than at
    the header line, so the parser claimed `---` rules above its own header); the
    meta-anchored seam has no such prefix. The two implementations agree on 100% of
    lines, so the gate ships at a true zero rather than a whitelist.

    SOURCE_MISATTRIBUTION is reported as a subset: the disagreements that land on a
    `- **Sources**` bullet, i.e. the ones that move the coverage census today. The
    rest are the same defect caught before it reaches a record.

    Blank lines are deliberately excluded. Which entry "owns" a blank line between
    two entries is arbitrary, and pinning it would make the gate brittle against
    legitimate parser tweaks. (They happen to agree there too, as of 23 JUL 2026.)

RETIRED WITH THE SHAPE READER: a second advisory metric, MIDLINE_BOLD_HEADER, counted
bold `Name (parenthetical)` spans written mid-sentence — the shape that used to become a
phantom entry. Under meta-anchored detection such a span cannot be an entry whatever it
says, so the metric could only ever be inert, and an inert number in a gate people are
meant to read is noise.

Read-only. Edits nothing.

Usage:
    python3 scripts/entry_boundary_audit.py                # exit 1 on any finding
    python3 scripts/entry_boundary_audit.py --advisory     # never exit non-zero
"""

import argparse
import glob
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as HS
import vault_config

# A `Sources` bullet: the record-bearing block whose ownership this gate protects.
# Both grammars — the Spec 03 `**Sources**` form and the legacy flat
# `**FS-attached sources**` form that migrate_sources.py is still converting.
SOURCES_BULLET = re.compile(
    r"^\s*[-*]\s*\*\*(?:Sources|FS-attached sources)\*\*", re.IGNORECASE)

# The same structural breaks the census honours (`harvest_sources.truncate_at_break`):
# a horizontal rule or a section heading ends the current entry body.
BREAK_LINE = re.compile(r"^(?:---\s*|##\s.*)$")


BOLD_LINE = re.compile(r"^[\-\*\s]*\*\*(.+?)\*\*")
META_LINE = re.compile(r"^\s*-\s*meta:", re.IGNORECASE)


def _header_name_at_line(lines, i):
    """The person-entry header NAME that begins line `i`, or None.

    META-ANCHORED, matching what the census now does: a bold line at line start is
    an entry header when the next non-blank line is its `- meta:` block. Kept as an
    INDEPENDENT implementation of that rule — a forward line scan here, versus
    `person_store`'s two-pass parse — so the two can still disagree and be caught.

    Note what this rule does NOT need: any judgement about whether the bold text
    looks like a personal name. A bold span without a meta block under it is not an
    entry, whatever it is called, so the person-versus-institution problem that
    started this lane simply does not arise.
    """
    if not lines[i].strip():
        return None
    m = BOLD_LINE.match(lines[i])
    if not m:
        return None
    for j in range(i + 1, len(lines)):
        if not lines[j].strip():
            continue
        return m.group(1).strip() if META_LINE.match(lines[j]) else None
    return None


def structural_owner_by_line(text):
    """line index -> the name of the entry that owns that line, per the MARKDOWN.

    Top-down scan: a header at line start becomes the owner; a `---` rule or `## `
    heading clears it. This is the "what the file says" side of the invariant.
    """
    lines = text.splitlines()
    owners = [None] * len(lines)
    cur = None
    for i, line in enumerate(lines):
        if BREAK_LINE.match(line):
            cur = None
            owners[i] = None
            continue
        name = _header_name_at_line(lines, i)
        if name:
            cur = name
        owners[i] = cur
    return owners


def parser_owner_by_line(text, entries):
    """line index -> the name of the entry the CENSUS attributes it to.

    `entries` is the census's own list for this file — (name, header_line, body) —
    from `harvest_sources.entry_blocks_by_file()`.
    """
    lines = text.splitlines()
    owners = [None] * len(lines)
    for name, hline, body in entries:
        for i in range(hline, min(hline + len(body.splitlines()), len(lines))):
            owners[i] = name
    return owners


def audit(vault):
    """Return the misattribution findings: a list of dicts.

    A misattribution finding is a contiguous RUN of disagreeing non-blank lines
    sharing the same (expected, actual) pair: one boundary fault displaces a whole
    block, and reporting it per line would bury the count. `sources` marks a run
    that contains a `Sources` bullet, i.e. one that moves the census today.
    """
    mis = []
    # SCOPE: this gate audits the NARRATIVE person model, where many people share a
    # lineage file and entry boundaries are a thing that can be got wrong. On the
    # file model each person IS a file, so there are no boundaries to misattribute
    # and nothing here applies. Say so by returning empty rather than comparing two
    # parsers that were never meant to read the same thing.
    if vault_config.get_person_model(vault) != "narrative":
        return []
    # The census's own entry list, so the gate checks the attribution that actually
    # ships rather than a re-derivation of it.
    census = HS.entry_blocks_by_file(vault)
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        fname = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        lines = text.splitlines()

        struct = structural_owner_by_line(text)
        # `census.get(path, [])` — NOT `.get(path)`: a lineage file with no person
        # entries at all (an Origins essay, a master index) legitimately yields an
        # EMPTY list, and passing None there would silently fall back to the legacy
        # shape reader, which then reads bold prose bullets as entries. The gate
        # caught exactly that mistake in its own wiring.
        parsed = parser_owner_by_line(text, census.get(path, []))
        run = None
        for i, line in enumerate(lines):
            if not line.strip():
                continue  # blank-line ownership is arbitrary; see module docstring
            bad = struct[i] != parsed[i]
            key = (struct[i], parsed[i]) if bad else None
            if run and (not bad or run["key"] != key or i > run["last"] + 3):
                mis.append(run)
                run = None
            if bad:
                if run is None:
                    run = {"file": fname, "line": i + 1, "key": key,
                           "expected": struct[i] or "(none)",
                           "actual": parsed[i] or "(none)",
                           "lines": 0, "sources": False}
                run["lines"] += 1
                run["last"] = i
                if SOURCES_BULLET.match(line):
                    run["sources"] = True
        if run:
            mis.append(run)

    return mis


def main():
    ap = argparse.ArgumentParser(
        description="Entry-boundary audit: Sources-bullet attribution + phantom-header detector.")
    ap.add_argument("--vault", default=None, help="Vault path (else AUTORESEARCH_VAULT).")
    ap.add_argument("--advisory", action="store_true",
                    help="Never exit non-zero, even on SOURCE_MISATTRIBUTION.")
    ap.add_argument("--limit", type=int, default=20, help="Cap listing length.")
    args = ap.parse_args()

    vault = vault_config.resolve_vault(args.vault)
    mis = audit(vault)

    source_hits = [r for r in mis if r["sources"]]
    displaced = sum(r["lines"] for r in mis)

    print("=== ENTRY-BOUNDARY AUDIT ===")
    print()
    print(f"ENTRY_MISATTRIBUTION: {len(mis)}  [HARD, baseline 0]")
    print("  A block of narrative credited to an entry other than the bold-name header")
    print("  that most recently preceded it at line start. Counted as contiguous runs;")
    print(f"  {displaced} non-blank line(s) displaced in total.")
    print(f"  of which SOURCE_MISATTRIBUTION: {len(source_hits)}  "
          "(runs containing a `Sources` bullet — these move the coverage census)")
    for r in sorted(mis, key=lambda r: (not r["sources"], -r["lines"]))[: args.limit]:
        tag = "  <-- carries a Sources bullet" if r["sources"] else ""
        print(f"    {r['file']}:{r['line']} ({r['lines']} lines)  markdown says "
              f"'{r['expected']}' but the census parser says '{r['actual']}'{tag}")
    if len(mis) > args.limit:
        print(f"    ... and {len(mis) - args.limit} more")
    if mis:
        print("  FIX: the parser, not the vault. A boundary regex is matching somewhere it")
        print("       should not, or a body span is being cut short. See spec/entry-boundary.")
    print()

    print(f"ENTRY_BOUNDARY: ENTRY_MISATTRIBUTION {len(mis)} "
          f"({displaced} lines), SOURCE_MISATTRIBUTION {len(source_hits)}")

    if mis and not args.advisory:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
