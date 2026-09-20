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
  python3 scripts/log_session.py --log "logs/2026-06-25-foo" --summary "..." --replace
  add --dry-run to preview without writing. Appends by default (additive, low-risk).

** --replace: A RE-CLOSE CORRECTS ITS OWN ROW (added 20 SEP 2026). ** A long sitting is
often closed, extended, then closed again (session_close.py's own tests say so). The first
close writes the sitting's index row; the extension then makes it WRONG, and the file is
append-only, so there was no sanctioned way to fix it. session_close.py told the agent to
"correct the existing row in place with a targeted replacement" while offering no tool
to do it, and the Edit tool is forbidden on this file. Measured on one sitting: the row
said "IMPROVE x2", "a 5-of-25 profile poll", "exactly one tracked metric moved" and "the
census correctly flat throughout" -- four claims, all false by the re-close.

--replace keeps the INTENT of append-only (never corrupt another sitting's history,
never hand-splice the file) while allowing the correction. It is deliberately narrow:
  * the row is matched on its LOG-LINK cell exactly, never on date or summary text, so
    it can only ever touch the sitting that --log names;
  * 0 matches -> REFUSE (there is nothing of this sitting's to correct; append instead);
  * 2+ matches -> REFUSE (a genuine duplicate already exists and needs a human);
  * the ORIGINAL date cell is kept unless --date is given: the row records when the
    sitting HAPPENED, and a next-day cleanup must not re-date it.
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


def rows_for_log(lines, link):
    """Indices of Session Index rows whose LOG-LINK cell equals `link` exactly.

    Only rows inside the Session Index section are considered, and only the second cell
    is compared -- a summary that merely MENTIONS another sitting's log is never matched."""
    try:
        sec = next(i for i, ln in enumerate(lines) if ln.rstrip("\n") == SECTION)
    except StopIteration:
        return []
    hits = []
    for i in range(sec + 1, len(lines)):
        s = lines[i].lstrip()
        if s.startswith("## "):
            break
        if not s.startswith("|") or _SEP_RE.match(lines[i]):
            continue
        cells = [c.strip() for c in s.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1] == link:
            hits.append(i)
    return hits


def _link(log):
    link = (log or "").strip()
    return link if (not link or link.startswith("[[")) else f"[[{link}]]"


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--row", help="full pre-formatted '| ... |' row")
    ap.add_argument("--log", help="session log path/wikilink, e.g. logs/2026-06-25-foo")
    ap.add_argument("--summary", help="one-line summary text")
    ap.add_argument("--date", default=None,
                    help="YYYY-MM-DD (default: today when appending; the ORIGINAL date "
                         "when --replace)")
    ap.add_argument("--replace", action="store_true",
                    help="REPLACE this sitting's existing row (matched on its log link) "
                         "instead of appending a second one -- the re-close path")
    ap.add_argument("--dry-run", action="store_true", help="preview; write nothing")
    args = ap.parse_args()

    if not RLOG.exists():
        print(f"ERROR: {RLOG} not found")
        return 1

    lines = RLOG.read_text(encoding="utf-8").splitlines(keepends=True)

    if args.replace:
        if args.row or not (args.log and args.summary):
            print("ERROR: --replace needs --log and --summary (the log link is the match key).")
            return 2
        link = _link(args.log)
        hits = rows_for_log(lines, link)
        if not hits:
            print(f"ERROR: --replace found NO existing row for {link}; nothing of this "
                  "sitting's to correct. Drop --replace to append.")
            return 4
        if len(hits) > 1:
            print(f"ERROR: --replace found {len(hits)} rows for {link} (lines "
                  f"{', '.join(str(h + 1) for h in hits)}); a duplicate already exists and "
                  "needs a human decision, not a guess.")
            return 5
        at = hits[0]
        old = lines[at].rstrip("\n")
        orig_date = old.strip().strip("|").split("|")[0].strip()
        row = build_row(args.date or orig_date, link, args.summary)
        print(f"replace line {at + 1} (this sitting's own row):")
        print(f"  - {old[:160]}")
        print(f"  + {row[:160]}")
        if args.dry_run:
            print("[dry-run] nothing written.")
            return 0
        lines[at] = row + "\n"
        RLOG.write_text("".join(lines), encoding="utf-8")
        print(f"replaced in {RLOG.relative_to(ROOT) if RLOG.is_relative_to(ROOT) else RLOG.name}")
        return 0

    if args.row:
        row = args.row.rstrip("\n")
    elif args.summary:
        row = build_row(args.date or datetime.date.today().isoformat(),
                        args.log or "", args.summary)
    else:
        print("ERROR: provide --row, or --summary (with --log).")
        return 2
    if not row.lstrip().startswith("|"):
        print(f"ERROR: row is not a markdown table row: {row!r}")
        return 2

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
    print(f"appended to {RLOG.relative_to(ROOT) if RLOG.is_relative_to(ROOT) else RLOG.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
