#!/usr/bin/env python3
"""question_audit.py — structural gate for the Open_Questions register.

Until 15 AUG 2026 the register — 10 files, ~770 KB, ~140 live questions — passed
the vault pre-commit hook entirely unexamined: every gate in it was a
Family_Tree / Handoff gate, and all three question checks were advisory,
banner-only, and post-hoc. The measured consequences (8 orphaned write-ups, a
destroyed live question, a resolved question sitting live for 9 days, a live
sub-question invisible to the index) are catalogued on the 12-14 AUG framework
commits. This gate closes the register's half of that asymmetry.

CHECKS (all via the shared grammar in `question_block.py`):

  HARD (baseline 0; --changed-only exits 1):
    Q_BELOW_INDEX   a question block written BELOW the `## Resolved & Closed`
                    index — the layout in whose blast radius a live question was
                    destroyed by an index rebuild (8477d95).
    DUP_LIVE_Q      the same Q number live in more than one place. Q numbers are
                    GLOBAL; a duplicate makes every cross-reference ambiguous
                    and blocks question_store from writing.
    ZOMBIE_Q        a LIVE block whose number is already TERMINAL in the
                    Resolved store — a resolved-and-archived question still
                    sitting (and being indexed, and being offered as work) in a
                    live shard. Live instance at adoption: Q197. To legitimately
                    reopen an archived question, move its block back OUT of the
                    Resolved store; never write a second live copy.
    TRAP_HEADING    (changed lines only) a heading authored with a provenance
                    clause in the terminal-status slot — the shape that silently
                    blocks archiving (28 of 144 headings, 11 AUG 2026). The
                    whole-register version of this stays advisory in
                    `archive_sections --lint-headings`.

  ADVISORY (whole register, watched in the banner):
    AMBIGUOUS_HEAD  a `### ` line starting with a digit that is NOT a boundary
                    (`### 48 (original cluster…)` — a number with no period).
                    Legal content today, one typo away from flipping a write-up
                    into a boundary; prefer a non-numeric lead.
    BIG_BLOCK       a live block over the size cap (default 15 KB). A block that
                    big is session narration accreting in place of current
                    state; triage it — current state + resolver stay, dated
                    chronology moves to logs/, route facts to the route
                    register.
    RESOLVERLESS    a live block in which no resolver line is recognisable.
                    Advisory because the detector is keyword-shaped; the WRITE
                    side (`question_store --new`) is where it is required.

Usage:
    python3 scripts/question_audit.py                  # whole register, advisory
    python3 scripts/question_audit.py --changed-only   # pre-commit gate (exit 1)
"""
import argparse
import os
import pathlib
import re
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import question_block as QB
import vault_config
from header_audit import staged_header_lines, materialise_staged

BIG_KB = 15
# the same resolver shapes gen_question_index recognises
SETTLE_RE = re.compile(r"(what would settle it|what is left|what would name|⏭)", re.I)
AMBIG_RE = re.compile(r"^###\s+\d")


def collect(vault):
    """One pass over the register -> dict of findings lists."""
    vault = pathlib.Path(vault)
    f = {"Q_BELOW_INDEX": [], "DUP_LIVE_Q": [], "ZOMBIE_Q": [],
         "AMBIGUOUS_HEAD": [], "BIG_BLOCK": [], "RESOLVERLESS": [], "LIVE": []}

    live_by_label = {}
    for path in QB.question_files(vault):
        rel = os.path.basename(path)
        lines = open(path, encoding="utf-8").read().split("\n")
        index_at = next((i for i, ln in enumerate(lines)
                         if QB.RESOLVED_INDEX.match(ln)), None)
        for i, ln in enumerate(lines):
            if ln.startswith("### ") and AMBIG_RE.match(ln) \
                    and not QB.QUESTION_HEAD.match(ln):
                f["AMBIGUOUS_HEAD"].append((rel, i + 1, ln.strip()[:90]))
        for s, e in QB.split_blocks(lines):
            h = QB.parse_heading(lines[s])
            if h is None:
                continue
            if index_at is not None and s > index_at:
                f["Q_BELOW_INDEX"].append((rel, s + 1, h["qlabel"]))
            if not QB.is_live(h):
                continue
            f["LIVE"].append((rel, s + 1, h["qlabel"]))
            live_by_label.setdefault(h["qlabel"], []).append((rel, s + 1))
            kb = sum(len(l) + 1 for l in lines[s:e]) / 1024
            if kb >= BIG_KB:
                f["BIG_BLOCK"].append((rel, s + 1, h["qlabel"], round(kb, 1)))
            if not any(SETTLE_RE.search(l) for l in lines[s:e]):
                f["RESOLVERLESS"].append((rel, s + 1, h["qlabel"]))

    for label, places in sorted(live_by_label.items()):
        if len(places) > 1:
            f["DUP_LIVE_Q"].append((label, places))

    rf = QB.resolved_file(vault)
    if os.path.exists(rf):
        terminal = set()
        for _s, _e, h, _l in QB.iter_questions(rf):
            if h["terminal"]:
                terminal.add(h["qlabel"])
        for label, places in sorted(live_by_label.items()):
            if label in terminal:
                f["ZOMBIE_Q"].append((label, places))
    return f


def trap_headings(vault, only):
    """[(rel, lineno, heading)] for CHANGED lines that are question headings whose
    status slot holds a provenance clause."""
    out = []
    for rel, nums in only.items():
        p = pathlib.Path(vault) / rel
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").split("\n")
        for n in sorted(nums):
            if n - 1 >= len(lines):
                continue
            ln = lines[n - 1]
            h = QB.parse_heading(ln)
            if h and not h["tombstone"] and h["status"] \
                    and QB.PROVENANCE_RE.match(h["status"]):
                out.append((rel, n, ln.strip()[:100]))
    return out


def report(f, hard_only=False):
    n_hard = len(f["Q_BELOW_INDEX"]) + len(f["DUP_LIVE_Q"]) + len(f["ZOMBIE_Q"])
    for rel, ln, q in f["Q_BELOW_INDEX"]:
        print(f"  Q_BELOW_INDEX  {rel}:{ln}  Q{q}  (move it ABOVE the Resolved index "
              f"— below it is the index-rebuild blast radius)")
    for label, places in f["DUP_LIVE_Q"]:
        where = "; ".join(f"{r}:{l}" for r, l in places)
        print(f"  DUP_LIVE_Q     Q{label} live in {len(places)} places: {where}")
    for label, places in f["ZOMBIE_Q"]:
        where = "; ".join(f"{r}:{l}" for r, l in places)
        print(f"  ZOMBIE_Q       Q{label} is TERMINAL in the Resolved store but live at: "
              f"{where}")
    if not hard_only:
        for rel, ln, t in f["AMBIGUOUS_HEAD"]:
            print(f"  AMBIGUOUS_HEAD {rel}:{ln}  {t}")
        for rel, ln, q, kb in sorted(f["BIG_BLOCK"], key=lambda r: -r[3]):
            print(f"  BIG_BLOCK      Q{q} {kb} KB  ({rel}:{ln})")
    return n_hard


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--changed-only", action="store_true",
                    help="pre-commit gate: exit 1 on HARD findings when any "
                         "Open_Questions file is staged")
    ap.add_argument("--warn-only", action="store_true")
    ap.add_argument("--list", action="store_true", help="print advisory rows too")
    a = ap.parse_args()
    vault = pathlib.Path(vault_config.resolve_vault(a.vault))

    if a.changed_only:
        changed = staged_header_lines(vault, pathspecs=("Open_Questions*.md",))
        changed = {p: v for p, v in changed.items()
                   if not ("_Resolved" in p or "_Archive" in p or "_Index" in p)}
        print("=== question register (question_audit) — staged commit ===")
        if not changed:
            print("  no live Open_Questions file staged.")
            print("=== SUMMARY ===\n  QUESTION_AUDIT (hard): 0  [BLOCKING]")
            return 0
        # global structural checks run on the STAGED content of the whole register
        with tempfile.TemporaryDirectory() as tmp:
            all_q = [os.path.relpath(p, vault) for p in QB.question_files(vault)]
            rf = QB.resolved_file(vault)
            if os.path.exists(rf):
                all_q.append(os.path.relpath(rf, vault))
            materialise_staged(vault, all_q, tmp)
            f = collect(tmp)
            traps = trap_headings(tmp, changed)
        n = report(f, hard_only=True)
        for rel, ln, t in traps:
            print(f"  TRAP_HEADING   {rel}:{ln}  {t}")
            print("                 FIX: provenance goes in the title parens; the text "
                  "after the LAST em-dash is the status slot.")
        n += len(traps)
        print(f"\n=== SUMMARY ===\n  QUESTION_AUDIT (hard): {n}  "
              f"[{'advisory' if a.warn_only else 'BLOCKING'}]")
        return 1 if (n and not a.warn_only) else 0

    f = collect(vault)
    n_hard = report(f, hard_only=not a.list)
    print(f"QUESTION_AUDIT: hard {n_hard} (Q_BELOW_INDEX {len(f['Q_BELOW_INDEX'])}, "
          f"DUP_LIVE_Q {len(f['DUP_LIVE_Q'])}, ZOMBIE_Q {len(f['ZOMBIE_Q'])}) "
          f"[baseline 0]; advisory: AMBIGUOUS_HEAD {len(f['AMBIGUOUS_HEAD'])}, "
          f"BIG_BLOCK {len(f['BIG_BLOCK'])}, RESOLVERLESS {len(f['RESOLVERLESS'])} "
          f"of {len(f['LIVE'])} live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
