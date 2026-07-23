#!/usr/bin/env python3
"""Archive old session sections from vault/Handoff.md to keep it small.

Handoff.md accumulates one dated "## <date> (LATEST N) ..." section per
research session (newest first), plus a few standing/pinned blocks. Left
unmanaged it grows without bound (1200+ lines). This script trims it to the
most recent N session sections while VERSIONING the file: before any edit it
writes a full timestamped snapshot of the current file to
vault/Handoff_Archive/, so nothing is ever lost (and git keeps its own
history on top of that).

Classification:
  - PINNED sections (always kept, in place): the watchlist reminder at the top
    and the standing footer blocks. Matched by title (see PINNED_PATTERNS).
  - SESSION sections: every other "## " section. They appear newest-first in
    document order, so the newest --keep are retained and the rest are dropped
    from the live file (still present in the snapshot).

Usage:
  python3 scripts/archive_next_session.py [--keep N] [--dry-run]

Defaults: --keep 5. Idempotent: a previously inserted archive-pointer line is
stripped and re-added each run, and re-running with nothing to drop is a no-op.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_config

ROOT = Path(__file__).resolve().parent.parent
_V = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
VAULT = Path(_V) if _V else None
NS = (VAULT / "Handoff.md") if VAULT else None
ARCHIVE_DIR = (VAULT / "Handoff_Archive") if VAULT else None

# Section headers (## ...) that must never be archived, kept in their original
# position. Matched as case-insensitive substrings of the header text.
PINNED_PATTERNS = [
    r"Start here",
    r"WATCHLIST AGING REMINDER",
    r"LONGER-TERM OPTIONS",
    r"Quick-resume commands",
    r"Reminders for next session",
]

POINTER_RE = re.compile(r"^> \*\*Archive:\*\*.*?(?:\n>.*)*\n\n", re.M)


def is_pinned(header: str) -> bool:
    return any(re.search(p, header, re.I) for p in PINNED_PATTERNS)


# Session closes are `### #NN CLOSE` headings NESTED inside the pinned
# "Start here" H2 (the convention changed from the older top-level
# `## <date> (LATEST NN)` form and this script was never taught the new one).
# Because "Start here" is pinned, the H2 pass can never reach them -- which
# made the script structurally unable to shrink the file even when those
# blocks were 73% of it, while the SessionStart heartbeat kept nudging on
# line count. Trimming them here is what makes that nudge actionable.
CLOSE_RE = re.compile(r"^### #\d+ CLOSE", re.M)


def trim_closes(sec_text: str, keep: int):
    """Keep the newest `keep` `### #NN CLOSE` blocks in a section, drop older.

    Closes are in newest-first document order, and run to the end of their
    section, so dropping is a single truncation. Returns (new_text, dropped)."""
    lines = sec_text.splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if CLOSE_RE.match(ln)]
    if len(starts) <= keep:
        return sec_text, []
    cut = starts[keep]
    dropped = [lines[i].rstrip("\n")[:96] for i in starts[keep:]]
    return "".join(lines[:cut]), dropped


def main() -> int:
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", type=int, default=5,
                    help="number of most-recent session sections to retain (default 5)")
    ap.add_argument("--keep-closes", type=int, default=3,
                    help="number of most-recent `### #NN CLOSE` blocks to retain inside "
                         "a pinned section (default 3, matching the Handoff standard)")
    ap.add_argument("--dry-run", action="store_true", help="preview only; write nothing")
    args = ap.parse_args()

    if not NS.exists():
        print(f"ERROR: {NS} not found")
        return 1

    text = NS.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    sec_starts = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    if not sec_starts:
        print("No '## ' sections found; nothing to do.")
        return 0

    # Everything before the first '## ' = head (frontmatter + H1 + intro).
    head = "".join(lines[: sec_starts[0]])
    head = POINTER_RE.sub("", head)  # drop a stale pointer from a prior run
    if not head.endswith("\n\n"):
        head = head.rstrip("\n") + "\n\n"

    sections = []
    for j, s in enumerate(sec_starts):
        e = sec_starts[j + 1] if j + 1 < len(sec_starts) else len(lines)
        sections.append({"header": lines[s].rstrip("\n"), "text": "".join(lines[s:e])})

    pinned_idx = [k for k, sec in enumerate(sections) if is_pinned(sec["header"])]
    session_idx = [k for k, sec in enumerate(sections) if not is_pinned(sec["header"])]
    keep_idx = set(pinned_idx) | set(session_idx[: args.keep])
    drop_idx = session_idx[args.keep:]

    # Nested `### #NN CLOSE` blocks inside PINNED sections (see trim_closes).
    closes_dropped = []
    for k in pinned_idx:
        trimmed, dropped = trim_closes(sections[k]["text"], args.keep_closes)
        if dropped:
            sections[k]["text"] = trimmed
            closes_dropped.extend(dropped)

    print(f"Sections: {len(sections)} total | pinned {len(pinned_idx)} | session {len(session_idx)}")
    if not drop_idx and not closes_dropped:
        print(f"Session sections ({len(session_idx)}) <= keep ({args.keep}) and nested closes "
              f"<= keep-closes ({args.keep_closes}); nothing to archive.")
        return 0

    if drop_idx:
        print(f"Keeping newest {args.keep} session sections + {len(pinned_idx)} pinned; "
              f"archiving {len(drop_idx)} older session section(s):")
        for k in drop_idx:
            print("  - " + sections[k]["header"][:96])
    if closes_dropped:
        print(f"Keeping newest {args.keep_closes} nested close block(s); "
              f"archiving {len(closes_dropped)} older:")
        for h in closes_dropped:
            print("  - " + h)

    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    snap = ARCHIVE_DIR / f"Handoff_{ts}.md"

    pointer = (
        f"> **Archive:** trimmed to the {args.keep_closes} most recent session sections. "
        f"Full prior history is versioned in `vault/Handoff_Archive/` "
        f"(latest snapshot: `Handoff_{ts}.md`).\n\n"
    )

    kept = [sec["text"] for k, sec in enumerate(sections) if k in keep_idx]
    new_text = head + pointer + "".join(kept)

    new_lines = new_text.count("\n") + 1
    print(f"Snapshot:  {snap.relative_to(ROOT)}  (full copy, {len(lines)} lines)")
    print(f"Live file: {len(lines)} -> {new_lines} lines")

    if args.dry_run:
        print("\n[dry-run] no files written.")
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    snap.write_text(text, encoding="utf-8")
    NS.write_text(new_text, encoding="utf-8")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
