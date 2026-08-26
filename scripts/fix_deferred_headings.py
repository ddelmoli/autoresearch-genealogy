#!/usr/bin/env python3
"""fix_deferred_headings.py — put the terminal status back in the slot that archives.

WHY IT EXISTS (26 AUG 2026). `deferred_decisions.md` stood at ~83,500 tokens against a
30,000 threshold while the Handoff told every session to read it. It looked like a file
that needed splitting. It is not: **45 of its 47 items are settled, and the archiver
drains 0 of them**, because the archiver reads the text after the LAST em-dash as the
status slot and almost no heading in the file puts it there.

    ## 13. RESOLVED 02 AUG 2026 (session #132) — TEN id-level merges done ...
                                                 ^ the parser reads THIS as the status

Measured dialects, all 47 items:

    29  status FIRST, summary last          -> the slot holds the summary
    11  status last but BOLD/emoji-wrapped  -> `matches_terminal` anchors at the
                                               START, so `✅ **RESOLVED` fails
     5  status buried mid-heading           -> needs a human
     2  genuinely live                      -> left alone

⭐ This is the same defect `HEADING_LINT` was built for on the question register,
and the lint DELIBERATELY SKIPS THIS FILE: it filters on `item_heading == "### "`,
and deferred items are `## `. An 83k-token file had been fully drainable for weeks
with nothing able to say so.

WHAT IT DOES, and the refusals matter more than the rewrites:

  DECORATED   the status is already last, wrapped in `✅` / `**`. Strip the
              decoration off the FRONT of the slot only. Lowest-risk case: no text
              moves.
  STATUS_FIRST  `## N. <STATUS> <date> (<note>) — <title>` becomes
              `## N. <title> — <STATUS> <date> (<note>)`. The title moves to the
              front and the status to the slot. ⚠ A title may itself contain an
              em-dash; only the LAST segment decides, so appending is safe.
  ⛔ REFUSED   everything else, listed for hand treatment. In particular:
              - a leading status word NOT in the target's `archive_statuses`
                (`FULLY CLOSED` is not `CLOSED`: `matches_terminal` anchors at the
                start, so the word order is the whole difference);
              - `MOVED ... to [[Open_Questions]] Q##`, which is not an archive
                status at all — whether relocating an item closes it is a POLICY
                question for the operator, not a rewrite;
              - anything whose status token this cannot identify confidently.

⚠ IT REWRITES TITLES, so it is dry-run by default, prints every old -> new pair for
reading, snapshots the file before applying, and re-parses afterwards to assert the
item count did not move.

USAGE
  python3 scripts/fix_deferred_headings.py              # dry-run: every proposed pair
  python3 scripts/fix_deferred_headings.py --refused    # only what it will not touch
  python3 scripts/fix_deferred_headings.py --apply
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import question_block as QB  # noqa: E402
import vault_config  # noqa: E402

EMDASH = "—"
DECOR = re.compile(r"^[\s✅⚠⛔⭐*_]+")     # ✅ ⚠ ⛔ ⭐ and ** __
DATE = r"\d{1,2}\s+[A-Z]{3,}\s+\d{4}"


def _balance_bold(s):
    """Drop a now-orphaned `**`.

    ⚠ Stripping the OPENING `**` off a status slot leaves its CLOSER behind, and the
    result renders the rest of the heading as stray literal asterisks. Removing the
    decoration is only half the edit; the other half is the closer that decoration
    was paired with.
    """
    while s.count("**") % 2 == 1:
        i = s.rfind("**")
        if i < 0:
            break
        s = s[:i] + s[i + 2:]
    return s.replace("  ", " ").strip()


def _target(vault):
    cfg = json.loads((Path(vault) / ".maintenance.json").read_text(encoding="utf-8"))
    for t in cfg.get("targets", []):
        if t.get("name") == "deferred-decisions":
            return t
    raise SystemExit("no `deferred-decisions` target in .maintenance.json")


def classify(heading, statuses):
    """(kind, new_heading_or_reason). kind: ok | decorated | status_first | refused."""
    slot = QB.heading_status(heading)
    if QB.matches_terminal(slot, statuses):
        return "ok", heading

    # --- DECORATED: the status is already in the slot, behind ✅ / ** ---
    if slot:
        stripped = DECOR.sub("", slot)
        if QB.matches_terminal(stripped, statuses):
            head, _sep, _old = heading.rpartition(EMDASH)
            return "decorated", f"{head.rstrip()} {EMDASH} {_balance_bold(stripped)}"

    # --- STATUS_FIRST: `## N. <STATUS> <date> (<note>) — <title>` ---
    m = re.match(r"^(##\s*\d+[a-z]?\.\s*)(.+)$", heading)
    if not m or EMDASH not in heading:
        return "refused", "no `## N.` prefix, or no em-dash to move a status across"
    prefix, rest = m.group(1), m.group(2)
    lead, _sep, tail = rest.partition(EMDASH)
    lead, tail = lead.strip(), tail.strip()
    # The leading run must START with an allowed status token, longest first — so
    # `FULLY RESOLVED` is tried before `RESOLVED`, and `FULLY CLOSED` matches neither.
    kw = next((k for k in sorted(statuses, key=len, reverse=True)
               if re.match(re.escape(k) + r"\b", DECOR.sub("", lead), re.I)), None)
    if not kw:
        first = DECOR.sub("", lead).split("(")[0].strip()
        return "refused", f"leading text is not an allowed status: {first[:56]!r}"
    if not tail:
        return "refused", "nothing after the em-dash to promote to a title"
    status_clause = _balance_bold(DECOR.sub("", lead)).rstrip(":;,")
    return "status_first", f"{prefix}{_balance_bold(tail)} {EMDASH} {status_clause}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--refused", action="store_true", help="show only what it will not touch")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    t = _target(vault)
    path = Path(vault) / t["file"]
    statuses = t["archive_statuses"]
    lines = path.read_text(encoding="utf-8").split("\n")

    head_idx = [i for i, ln in enumerate(lines) if re.match(r"^##\s*\d+[a-z]?\.", ln)]
    counts = {"ok": 0, "decorated": 0, "status_first": 0, "refused": 0}
    changes, refused = [], []
    for i in head_idx:
        kind, out = classify(lines[i], statuses)
        counts[kind] += 1
        if kind in ("decorated", "status_first"):
            # ⛔ POST-CONDITION, CHECKED BEFORE THE CHANGE IS EVEN OFFERED: the whole
            # point of the rewrite is that the archiver can read the status. A
            # proposal that still fails `matches_terminal` would move text for no
            # gain, which is the worst outcome available here -- the file looks
            # repaired and drains exactly as before.
            if not QB.matches_terminal(QB.heading_status(out), statuses):
                counts[kind] -= 1
                counts["refused"] += 1
                refused.append((i, lines[i],
                                "rewrite would STILL not parse as terminal — not offered"))
                continue
            changes.append((i, kind, lines[i], out))
        elif kind == "refused":
            refused.append((i, lines[i], out))

    print(f"=== {t['file']}: {len(head_idx)} item heading(s) ===")
    print(f"  already conforming : {counts['ok']}")
    print(f"  DECORATED  (strip) : {counts['decorated']}")
    print(f"  STATUS_FIRST (move): {counts['status_first']}")
    print(f"  ⛔ REFUSED         : {counts['refused']}\n")

    if not a.refused:
        for i, kind, old, new in changes:
            print(f"  L{i+1} [{kind}]")
            print(f"    -  {old[:150]}")
            print(f"    +  {new[:150]}")
    for i, old, why in refused:
        print(f"  L{i+1} ⛔ REFUSED — {why}")
        print(f"       {old[:140]}")

    if not a.apply:
        print(f"\n[dry-run] {len(changes)} heading(s) would change. Re-run with --apply.")
        return 0

    ts = _dt.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    snap_dir = Path(vault) / t.get("snapshot_dir", "deferred_decisions_Archive")
    snap_dir.mkdir(exist_ok=True)
    snap = snap_dir / f"{path.stem}_preheadingfix_{ts}.md"
    snap.write_text("\n".join(lines), encoding="utf-8")
    for i, _kind, _old, new in changes:
        lines[i] = new
    path.write_text("\n".join(lines), encoding="utf-8")

    after = [ln for ln in lines if re.match(r"^##\s*\d+[a-z]?\.", ln)]
    assert len(after) == len(head_idx), "item count moved — this must never happen"
    now_ok = sum(1 for ln in after if QB.matches_terminal(QB.heading_status(ln), statuses))
    print(f"\n  snapshot: {snap.relative_to(Path(vault))}")
    print(f"  wrote {t['file']}: {len(changes)} heading(s) changed, "
          f"item count {len(head_idx)} unchanged")
    print(f"  archivable now: {now_ok} (was {counts['ok']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
