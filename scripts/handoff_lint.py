#!/usr/bin/env python3
"""
handoff_lint.py — structural lint for the vault's Handoff.md close block.

WHY THIS EXISTS. Handoff.md reached 1,815 lines / ~48,800 tokens, 4x its own
12,000-token threshold, and three blocks were 92% of it. There was no template
saying what belongs in the handoff versus in the session log, so a session wrote
629 lines of narrative into the handoff while its own log already held all of it.
It also FORGOT: hand-copied metrics went stale silently (`SOURCE_GAP 218` was
carried forward while the live value was 243; the DATE_DRIFT coverage line is
documented in the vault baseline as having been wrong TWICE), and a required
field nobody was required to fill got filled only when someone felt like it.

WHAT IT CHECKS (spec: vault deferred_decisions.md item 12, decided 28 JUL 2026):

  MISSING_FIELD   the live close block lacks a required template field. RETRACTIONS
                  and NEGATIVES / DO-NOT-REDO are required precisely because they
                  are the two that get skipped: one session produced FOUR
                  retractions and recorded them only by choice.
  CLOSE_TOO_LONG  the live close block exceeds the line cap (~120). The session LOG
                  is the home for narrative; the handoff is an INDEX into it.
  MULTI_CLOSE     more than one close block is live. Archive-on-write keeps exactly
                  one (.maintenance.json handoff.keep: 1).
  BARE_METRIC     a derivable metric is hand-copied into prose with a bare value.
                  Every one of these is computed by the SessionStart banner.

  ** ADVISORY FIRST. ** Exit code is 0 unless --strict. Promote to blocking only
  once the baseline is 0 — the same path meta_presence, header_xref and
  entry_boundary all took.

THE HARD PART IS BARE_METRIC, AND ITS EXCEPTION IS THE POINT.

  "SOURCE_GAP 218 -> 243 is minting, not regression" is LOAD-BEARING: the whole
  claim IS the two values and the movement between them. Deleting the numbers
  destroys the sentence. So a metric value is EXEMPT when it is:

    (a) a TRANSITION      SOURCE_GAP 218 -> 243   |   canonical 1,277 to 1,324
    (b) a CONTRAST        SOURCE_GAP is 243, not 218   |   309 vs 319
    (c) inside a FENCE    ``` ... ``` (command examples, template blocks)
    (d) explicitly marked with a trailing `[finding]` on the line — the escape
        hatch for a load-bearing number the two heuristics above do not cover.

  ** THIS RULE IS THE ONE MOST LIKELY TO PRODUCE FALSE POSITIVES, and this vault
  has been bitten repeatedly by a check whose first number was an artefact
  (meta_presence's first run said 698 and ~11 were real). READ THE ROWS IT
  FLAGS BEFORE BELIEVING THE COUNT. ** The fixtures in test_handoff_lint.py pin
  both directions; if a real handoff line trips it, fix the CHECK, not the prose.

Usage:
  python3 scripts/handoff_lint.py                 # advisory report (exit 0)
  python3 scripts/handoff_lint.py --strict        # exit 1 on any violation
  python3 scripts/handoff_lint.py --quiet         # one summary line (banner use)
  python3 scripts/handoff_lint.py --file PATH     # lint an arbitrary file
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_config

LINE_CAP = 120

# The close-block template (Operating_Protocol.md "THE HANDOFF CLOSE-BLOCK TEMPLATE").
# REQUIRED are the fields whose absence is a defect; RECOMMENDED are reported but
# not counted, because a session can honestly have neither a new trap nor a queue
# change and padding a field with "none" teaches nobody anything.
REQUIRED_FIELDS = [
    "GATES",
    "WHAT MOVED",
    "FINDINGS",
    "RETRACTIONS",
    "NEGATIVES / DO-NOT-REDO",
    "OPEN / NEXT",
]
RECOMMENDED_FIELDS = [
    "NEW TRAPS",
    "OPERATOR QUEUE DELTA",
]

# A close block heading, in either spelling this vault has used:
#   "## SESSION #109 CLOSE (28 JUL 2026) -> ..."
#   "## ==> STATE AT THE #109 CLOSE (28 JUL 2026). ..."
CLOSE_HEADING_RE = re.compile(
    r"^##\s+(?:==>\s*)?(?:\*\*\s*)?(?:SESSION\s+#\d+\s+CLOSE|STATE\s+AT\s+THE\s+#\d+\s+CLOSE)",
    re.I,
)

# Metrics the SessionStart banner computes every session. A hand-copy of any of
# these is a stale value waiting to be read as current.
METRICS = [
    "canonical",
    "SOURCE_GAP", "LOW_COVERAGE", "WELL_SOURCED", "UNCITED", "BOOK_SOURCED",
    "NO_NARRATIVE",
    "SILENT", "DECLARED",
    "DATE_DRIFT", "DATE_IMPOSSIBLE", "DATE_UNATTESTED",
    "DUP_ID", "MISSING_ID", "DUP_FS_PID", "NEEDS_META", "ID_GRAMMAR",
    "META_PRESENCE", "ORPHANED_META",
    "HEADER_XREF", "HEADER_GRAMMAR",
    "ENTRY_MISATTRIBUTION", "SOURCE_MISATTRIBUTION",
    "DUP_NAME_STRONG", "DUP_NAME_POSSIBLE",
    "CHRONOLOGY",
    # question-register metrics (15 AUG 2026) — the banner computes all of these
    # (oq-structure / oq-headings / oq-archive / questions lines); a hand-copied
    # live-question count was the THIRD disagreeing number the register carried
    "QUESTION_AUDIT", "ZOMBIE_Q", "DUP_LIVE_Q", "Q_BELOW_INDEX",
    "HEADING_LINT", "ARCHIVE_LINT", "BARE_ARK",
]
_METRIC_ALT = "|".join(sorted((re.escape(m) for m in METRICS), key=len, reverse=True))

# METRIC, then only connector words, then a number. The connector list is
# deliberately SHORT: the further the number sits from the metric name, the more
# likely it belongs to a different clause, and a false positive here costs more
# than a miss (a missed stale number is what we already have; a false positive
# trains people to ignore the check).
# The `|` and `*` alternatives are what let a MARKDOWN TABLE ROW be caught:
# "| canonical entries | **1,324** |" is the exact shape the retired
# "WHERE THE NUMBERS STAND" tables used, and it is the worst offender of the
# class — a whole grid of values that all go stale together.
_CONNECT = (r"(?:\s*(?:is|was|are|were|now|still|at|stands|stood|reads|held|of"
            r"|entries|rows|count|counts|value|violations|total|tokens"
            r"|=|:|,|\||\*)\s*)*")
_NUM = r"\d[\d,]*"
METRIC_VALUE_RE = re.compile(
    rf"\b({_METRIC_ALT})\b{_CONNECT}\s*({_NUM})\b",
    re.I,
)

# Exemption (a) TRANSITION and (b) CONTRAST, applied to the matched value itself:
# a second number linked to it by an arrow, "to", or a contrast word.
_TRANSITION_AFTER = re.compile(rf"^\s*(?:->|-->|to|through|=>)\s*{_NUM}\b", re.I)
_CONTRAST_AFTER = re.compile(rf"^\s*,?\s*(?:not|vs\.?|versus|against|from|but)\s+{_NUM}\b", re.I)
_TRANSITION_BEFORE = re.compile(rf"{_NUM}\s*(?:->|-->|to|=>)\s*$", re.I)
_CONTRAST_BEFORE = re.compile(rf"{_NUM}\s*(?:,?\s*(?:not|vs\.?|versus|against)\s+)$", re.I)

# Exemption (d): the explicit escape hatch.
FINDING_MARK_RE = re.compile(r"\[finding\]", re.I)


def _field_present(block_lines, field):
    """A template field may be spelled as a heading (`### FINDINGS`) or as a bold
    lead-in (`**GATES:** ...`). Match the field name at the START of the line,
    after stripping markdown ornament — NOT anywhere on the line, so a sentence
    that merely says the word "findings" cannot satisfy the check."""
    want = re.sub(r"[^A-Z]", "", field.upper())
    for ln in block_lines:
        s = ln.strip()
        s = re.sub(r"^[#>\-\*\s]+", "", s)          # heading hashes, quotes, bullets, bold
        s = re.sub(r"^\*+", "", s).strip()
        # Split on ':' and ' (' ONLY. Do NOT split on '-': the field name
        # "NEGATIVES / DO-NOT-REDO" contains hyphens, and splitting on them
        # truncated it to "NEGATIVES / DO", so the single most important
        # required field could never be found and every close block read as
        # non-conforming. Caught by the fixture, which is what it is for.
        head = re.split(r"[:—]| \(", s, maxsplit=1)[0].strip()
        norm = re.sub(r"[^A-Z]", "", head.upper())
        if norm == want or norm.startswith(want):
            return True
    return False


def _fence_mask(lines):
    """True for every line inside a ``` fenced block (fence lines included)."""
    mask = [False] * len(lines)
    inside = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            mask[i] = True
            inside = not inside
            continue
        mask[i] = inside
    return mask


def find_bare_metrics(lines):
    """Return [(lineno, metric, value, line)] for hand-copied derivable metrics
    that are NOT load-bearing. See the module docstring for the four exemptions."""
    out = []
    fenced = _fence_mask(lines)
    for i, ln in enumerate(lines, start=1):
        if fenced[i - 1]:
            continue
        if FINDING_MARK_RE.search(ln):
            continue
        for m in METRIC_VALUE_RE.finditer(ln):
            after = ln[m.end():]
            before = ln[: m.start(2)]
            if _TRANSITION_AFTER.match(after) or _CONTRAST_AFTER.match(after):
                continue
            if _TRANSITION_BEFORE.search(before) or _CONTRAST_BEFORE.search(before):
                continue
            out.append((i, m.group(1), m.group(2), ln.rstrip()))
    return out


def lint_text(text):
    """Lint one Handoff document. Returns a dict of findings. Pure function so the
    fixtures in test_handoff_lint.py can exercise it without a vault."""
    lines = text.splitlines()
    findings = {
        "missing_fields": [],
        "missing_recommended": [],
        "close_len": 0,
        "close_heading": None,
        "too_long": False,
        "close_headings": [],
        "bare_metrics": [],
    }

    # --- close blocks -------------------------------------------------------
    h2 = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    closes = [i for i in h2 if CLOSE_HEADING_RE.match(lines[i])]
    findings["close_headings"] = [lines[i].strip() for i in closes]

    if closes:
        start = closes[0]
        nxt = [i for i in h2 if i > start]
        end = nxt[0] if nxt else len(lines)
        block = lines[start:end]
        while block and not block[-1].strip():
            block.pop()
        findings["close_heading"] = lines[start].strip()
        findings["close_len"] = len(block)
        findings["too_long"] = len(block) > LINE_CAP
        for f in REQUIRED_FIELDS:
            if not _field_present(block, f):
                findings["missing_fields"].append(f)
        for f in RECOMMENDED_FIELDS:
            if not _field_present(block, f):
                findings["missing_recommended"].append(f)
    else:
        findings["missing_fields"] = list(REQUIRED_FIELDS)

    # --- bare metrics (whole file: stale numbers rot wherever they sit) ------
    findings["bare_metrics"] = find_bare_metrics(lines)
    return findings


def total(findings):
    n = len(findings["missing_fields"]) + len(findings["bare_metrics"])
    if findings["too_long"]:
        n += 1
    if len(findings["close_headings"]) > 1:
        n += len(findings["close_headings"]) - 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", help="vault root (else AUTORESEARCH_VAULT)")
    ap.add_argument("--file", help="lint this file instead of <vault>/Handoff.md")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any violation (promote to blocking)")
    ap.add_argument("--quiet", action="store_true", help="one summary line only")
    args = ap.parse_args()

    if args.file:
        path = Path(args.file)
    else:
        path = Path(vault_config.resolve_vault(args.vault)) / "Handoff.md"
    if not path.exists():
        print(f"handoff_lint: {path} not found", file=sys.stderr)
        return 0

    f = lint_text(path.read_text(encoding="utf-8"))
    n = total(f)

    if args.quiet:
        bits = [f"close {f['close_len']}/{LINE_CAP} lines"]
        if f["missing_fields"]:
            bits.append(f"MISSING_FIELD {len(f['missing_fields'])}")
        if f["too_long"]:
            bits.append("CLOSE_TOO_LONG")
        if len(f["close_headings"]) > 1:
            bits.append(f"MULTI_CLOSE {len(f['close_headings'])}")
        if f["bare_metrics"]:
            bits.append(f"BARE_METRIC {len(f['bare_metrics'])}")
        print(f"HANDOFF_LINT: {'; '.join(bits)}"
              + ("" if n else " OK") + "  [advisory]")
        return 1 if (args.strict and n) else 0

    print("=== handoff_lint (advisory) ===")
    print(f"file: {path}")
    print(f"live close block: {f['close_heading'] or '(none found)'}")
    print(f"close block length: {f['close_len']} lines (cap {LINE_CAP})"
          + ("   <-- CLOSE_TOO_LONG" if f["too_long"] else ""))

    if len(f["close_headings"]) > 1:
        print(f"\nMULTI_CLOSE: {len(f['close_headings'])} close blocks are live; "
              f"archive-on-write keeps exactly ONE.")
        for h in f["close_headings"]:
            print(f"  - {h[:110]}")
        print("  FIX: python3 scripts/archive_sections.py --target handoff --apply")

    if f["missing_fields"]:
        print("\nMISSING_FIELD (required by the close-block template):")
        for x in f["missing_fields"]:
            print(f"  - {x}")
        print("  FIX: see Operating_Protocol.md 'THE HANDOFF CLOSE-BLOCK TEMPLATE'.")
        print("  RETRACTIONS and NEGATIVES / DO-NOT-REDO may say \"none\" — but must be there.")
    if f["missing_recommended"]:
        print("\n(recommended, not counted): "
              + ", ".join(f["missing_recommended"]))

    if f["bare_metrics"]:
        print(f"\nBARE_METRIC ({len(f['bare_metrics'])}): a derivable metric hand-copied into prose.")
        print("  The SessionStart banner computes every one of these each session.")
        print("  ** READ THESE ROWS BEFORE BELIEVING THE COUNT. ** If the number IS the")
        print("  finding, the fix is the CHECK, not the prose: a transition (218 -> 243) or")
        print("  a contrast (243, not 218) is already exempt; otherwise mark the line [finding].")
        for lineno, metric, val, ln in f["bare_metrics"]:
            print(f"  L{lineno}: {metric} {val}")
            print(f"        {ln[:150]}")

    print(f"\nHANDOFF_LINT violations: {n}   [advisory]")
    return 1 if (args.strict and n) else 0


if __name__ == "__main__":
    sys.exit(main())
