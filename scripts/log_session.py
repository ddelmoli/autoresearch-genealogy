#!/usr/bin/env python3
"""
log_session.py — append one row to the Research_Log.md "## Session Index" table.

WHY THIS EXISTS (Plan 4): the prompts say "append a one-line summary entry to the
session index" but name no tool, so an agent reaches for Edit — and this harness's
Edit tool requires a full Read first, paying ~35k tokens to add one row to an
append-only file nothing otherwise reads. This helper does the append in a
subprocess (the file never enters the conversation context), structure-aware so it
stays correct even if the file's section order changes.

Structure-aware: inserts after the LAST contiguous table row in the section (so the
row lands at the bottom of the ascending table), NOT a blind '>>' to EOF — if the
file ever regains a trailing section after the table (e.g. the upstream template
puts '## Logging Convention' last), a naked redirect would misplace the row.

Usage:
  python3 scripts/log_session.py --log "logs/2026-06-25-foo" --summary "..."   [--date YYYY-MM-DD]
  python3 scripts/log_session.py --row "| 2026-06-25 | [[logs/x]] | summary |"
  add --dry-run to preview without writing. Appends by default (additive, low-risk).
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_config

ROOT = Path(__file__).resolve().parent.parent
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
RLOG = (Path(VAULT) / "Research_Log.md") if VAULT else None
SECTION = "## Session Index"
_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


def build_row(date: str, log: str, summary: str) -> str:
    link = log.strip()
    if link and not link.startswith("[["):
        link = f"[[{link}]]"
    cells = [date.strip(), link, " ".join(summary.split())]
    return "| " + " | ".join(cells) + " |"


def insertion_index(lines):
    """Return the line index AFTER the last table row of the Session Index section,
    or None if the section/table can't be located."""
    try:
        sec = next(i for i, ln in enumerate(lines) if ln.rstrip("\n") == SECTION)
    except StopIteration:
        return None
    last_row = None
    for i in range(sec + 1, len(lines)):
        s = lines[i].lstrip()
        if s.startswith("|"):
            last_row = i
        elif s.startswith("## "):  # next section — stop scanning
            break
    return (last_row + 1) if last_row is not None else None


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--row", help="full pre-formatted '| ... |' row")
    ap.add_argument("--log", help="session log path/wikilink, e.g. logs/2026-06-25-foo")
    ap.add_argument("--summary", help="one-line summary text")
    ap.add_argument("--date", default=datetime.date.today().isoformat(),
                    help="YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true", help="preview; write nothing")
    args = ap.parse_args()

    if not RLOG.exists():
        print(f"ERROR: {RLOG} not found")
        return 1

    if args.row:
        row = args.row.rstrip("\n")
    elif args.summary:
        row = build_row(args.date, args.log or "", args.summary)
    else:
        print("ERROR: provide --row, or --summary (with --log).")
        return 2
    if not row.lstrip().startswith("|"):
        print(f"ERROR: row is not a markdown table row: {row!r}")
        return 2

    lines = RLOG.read_text(encoding="utf-8").splitlines(keepends=True)
    at = insertion_index(lines)
    if at is None:
        print(f"ERROR: could not locate the '{SECTION}' table in {RLOG.name}.")
        return 3

    new_line = row if row.endswith("\n") else row + "\n"
    print(f"insert at line {at} (after the last Session Index row):")
    print(f"  {row}")
    if args.dry_run:
        print("[dry-run] nothing written.")
        return 0

    lines.insert(at, new_line)
    RLOG.write_text("".join(lines), encoding="utf-8")
    print(f"appended to {RLOG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
