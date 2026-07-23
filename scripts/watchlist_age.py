#!/usr/bin/env python3
"""Watchlist aging heartbeat.

Reads the `last_checked` frontmatter field of vault/Watchlist.md and reports how
long it has been since the contributor-change watchlist was last polled, with a
per-tier OVERDUE/OK status. Run standalone (`python3 scripts/watchlist_age.py`)
or via the SessionStart audit suite (scripts/session_audit.sh), which greps the
line beginning "Watchlist:".

Tier cadences (days): Tier 1 = 30, Tier 2 = 90, Tier 3 = 180.
A tier is OVERDUE when days-since-last-check >= its interval. `last_checked: never`
(the pre-baseline state) reports all tiers DUE-baseline.
"""
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config

VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
WATCHLIST = os.path.join(VAULT, "Watchlist.md") if VAULT else None
TIERS = [("T1", 30), ("T2", 90), ("T3", 180)]


def read_last_checked(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return None, "MISSING"
    m = re.search(r"(?m)^last_checked:\s*(.+)$", text)
    if not m:
        return None, "NO_FIELD"
    val = m.group(1).strip()
    if re.search(r"\bnever\b", val, re.I):
        return None, "never"
    d = re.search(r"(\d{4})-(\d{2})-(\d{2})", val)
    if not d:
        return None, "UNPARSEABLE"
    return date(int(d.group(1)), int(d.group(2)), int(d.group(3))), "date"


def main():
    vault_config.require_vault(VAULT)
    last, kind = read_last_checked(WATCHLIST)
    if kind in ("MISSING", "NO_FIELD", "UNPARSEABLE"):
        print(f"Watchlist: {kind} — cannot determine aging (check {WATCHLIST} frontmatter `last_checked`)")
        return
    if kind == "never":
        tiers = "; ".join(f"{name}({iv}d): DUE-baseline" for name, iv in TIERS)
        print(f"Watchlist: NEVER polled — baseline snapshot capture is the first poll. {tiers}")
        return
    days = (date.today() - last).days
    status = "; ".join(
        f"{name}({iv}d): {'OVERDUE' if days >= iv else 'OK'}" for name, iv in TIERS
    )
    print(f"Watchlist: last checked {days} days ago ({last.isoformat()}). {status}")
    if days >= TIERS[0][1]:
        print(f"Watchlist: ACTION — at least one tier is overdue; run the poll in {WATCHLIST} and reset last_checked.")


if __name__ == "__main__":
    main()
    sys.exit(0)
