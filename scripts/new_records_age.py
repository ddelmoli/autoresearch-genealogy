#!/usr/bin/env python3
"""New-Records Watch aging heartbeat.

Reads the `new_records` cadence block of vault/.maintenance.json and reports, per
tier, how long since that tier was last swept for newly-published record
collections, with a DUE/OK status. Run standalone (`python3 scripts/new_records_age.py`)
or via the SessionStart audit suite (scripts/session_audit.sh), which greps the
line beginning "New-Records:".

Tiers + intervals + per-tier last_checked live in .maintenance.json `new_records`
(the sibling of the `harvest` block); the registry rows + baselines live in
New_Records_Watch.md + new_records_snapshots.json. An absent block => a silent
"not configured" line, so the check stays upstream-safe.
"""
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config


def _parse_date(val):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(val or ""))
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def main():
    cfg_path = os.path.join(vault_config.resolve_vault(), ".maintenance.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print("New-Records: not configured (no .maintenance.json)")
        return
    except (json.JSONDecodeError, OSError) as e:
        print(f"New-Records: config unreadable ({e})")
        return

    nr = cfg.get("new_records")
    if not nr or not nr.get("tiers"):
        print("New-Records: not configured (no new_records block)")
        return

    today = date.today()
    parts, overdue = [], False
    for name in sorted(nr["tiers"]):
        t = nr["tiers"][name]
        iv = t.get("interval_days")
        d = _parse_date(t.get("last_checked"))
        if d is None:
            parts.append(f"{name}({iv}d): DUE-baseline")
            overdue = True
            continue
        days = (today - d).days
        due = iv is not None and days >= iv
        overdue = overdue or due
        parts.append(f"{name}({iv}d): {'DUE' if due else 'OK'}")

    print("New-Records: " + "; ".join(parts))
    if overdue:
        print(
            "New-Records: ACTION - a tier is due; sweep New_Records_Watch.md "
            "(scripts/new_records_scan.py for the headless Ancestry half), then reset "
            "that tier's last_checked in .maintenance.json + --update the snapshot."
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
