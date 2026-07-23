#!/usr/bin/env python3
"""
Headless WikiTree drift checker for the contributor-change Watchlist.

WikiTree exposes a public, no-login API. For each WikiTree ID cited in
vault/Watchlist.md this script fetches the profile's `Touched` (last-modified)
timestamp + name, compares it to the stored snapshot in
vault/watchlist_snapshots.json, and reports any that changed since the last
baseline. This is the FULLY AUTOMATED half of the Watchlist (the FS half needs
the operator's logged-in Chrome — see liveness_sweep.py + the Recipe-S flow).

Usage:
  python3 scripts/watchlist_wikitree.py            # report drift vs snapshot (read-only)
  python3 scripts/watchlist_wikitree.py --update   # report, then write new baseline
  python3 scripts/watchlist_wikitree.py --ids A-1 B-2   # check explicit IDs instead of the Watchlist

Exit code: 0 = no drift (or --update wrote a baseline), 2 = drift detected,
3 = one or more fetches failed (network/rate-limit). Designed to be safe to run
from the SessionStart hook or a cron; on network failure it reports and exits 3
without clobbering the snapshot.

Notes:
- WikiTree rate-limits fast batches; this sleeps ~1.2s between requests.
- `Touched` is a 14-digit UTC stamp (YYYYMMDDHHMMSS).
- The snapshot file is shared with liveness_sweep.py (top-level keys
  "wikitree" and "fs"); each script only touches its own key.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
WATCHLIST = os.path.join(VAULT, "Watchlist.md") if VAULT else None
SNAPSHOTS = os.path.join(VAULT, "watchlist_snapshots.json") if VAULT else None

API = "https://api.wikitree.com/api.php"
USER_AGENT = "autoresearch-genealogy-watchlist/1.0 (personal genealogy vault drift check)"


def parse_watchlist_wikitree_ids():
    """Return list of (person_label, wikitree_id) from the Watchlist tables.

    Tables are: | Person | FS PID | WikiTree | Why | Last-seen modified |
    The WikiTree column is group 3. Skip separators, the header, and '—'.
    """
    out = []
    if not os.path.exists(WATCHLIST):
        return out
    with open(WATCHLIST) as f:
        for line in f:
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5:
                continue
            person, _fs, wt = cells[0], cells[1], cells[2]
            if wt in ("", "—", "WikiTree") or set(wt) <= {"-", ":"}:
                continue
            # A WikiTree ID looks like Surname-1234
            if re.match(r"^[A-Za-z'’.\-]+-\d+$", wt):
                out.append((person, wt))
    # de-dupe by ID, keep first label
    seen, uniq = set(), []
    for label, wt in out:
        if wt not in seen:
            seen.add(wt)
            uniq.append((label, wt))
    return uniq


def fetch_profile(wt_id):
    """Return dict with Touched/Name/LastNameAtBirth, or raise."""
    params = {
        "action": "getProfile",
        "key": wt_id,
        "fields": "Id,Name,LastNameAtBirth,Touched",
        "format": "json",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    # Response is a list of result objects; the profile is under "profile".
    if isinstance(data, list) and data:
        prof = data[0].get("profile") or {}
        status = data[0].get("status")
        if not prof and status:
            raise RuntimeError(f"API status: {status}")
        return {
            "Touched": str(prof.get("Touched") or ""),
            "Name": prof.get("Name") or "",
            "LastNameAtBirth": prof.get("LastNameAtBirth") or "",
        }
    raise RuntimeError("unexpected API response shape")


def load_snapshots():
    if os.path.exists(SNAPSHOTS):
        with open(SNAPSHOTS) as f:
            return json.load(f)
    return {}


def save_snapshots(snap):
    with open(SNAPSHOTS, "w") as f:
        json.dump(snap, f, indent=2, sort_keys=True)
        f.write("\n")


def fmt_touched(t):
    if re.match(r"^\d{14}$", t):
        return f"{t[0:4]}-{t[4:6]}-{t[6:8]}"
    return t or "?"


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser(description="Headless WikiTree drift checker for the Watchlist.")
    ap.add_argument("--update", action="store_true", help="Write a new baseline snapshot after reporting.")
    ap.add_argument("--ids", nargs="*", help="Check these WikiTree IDs instead of parsing the Watchlist.")
    ap.add_argument("--sleep", type=float, default=1.2, help="Seconds between API calls (rate-limit).")
    args = ap.parse_args()

    if args.ids:
        targets = [("(cli)", i) for i in args.ids]
    else:
        targets = parse_watchlist_wikitree_ids()

    if not targets:
        print("No WikiTree IDs found to check.")
        return 0

    snap = load_snapshots()
    wt_snap = snap.get("wikitree", {})

    drifted, errors, unchanged, new = [], [], [], []
    results = {}

    for i, (label, wt_id) in enumerate(targets):
        if i:
            time.sleep(args.sleep)
        try:
            prof = fetch_profile(wt_id)
        except Exception as e:  # network / rate-limit / shape
            errors.append((wt_id, label, str(e)))
            continue
        results[wt_id] = prof
        prev = wt_snap.get(wt_id)
        cur_t = prof["Touched"]
        if prev is None:
            new.append((wt_id, label, cur_t))
        elif prev.get("Touched") != cur_t:
            drifted.append((wt_id, label, prev.get("Touched", "?"), cur_t))
        else:
            unchanged.append((wt_id, label))

    print("=== WikiTree Watchlist drift check ===")
    print(f"Checked {len(results)}/{len(targets)} profiles "
          f"({len(unchanged)} unchanged, {len(drifted)} DRIFTED, {len(new)} new, {len(errors)} errors)\n")

    if drifted:
        print("[!] DRIFT — review the profile's Changes tab:")
        for wt_id, label, old, cur in drifted:
            print(f"  {wt_id:<16} {label[:40]:<40} {fmt_touched(old)} -> {fmt_touched(cur)}")
        print()
    if new:
        print("[+] NEW (no prior baseline — recorded on --update):")
        for wt_id, label, cur in new:
            print(f"  {wt_id:<16} {label[:40]:<40} touched {fmt_touched(cur)}")
        print()
    if errors:
        print("[x] FETCH ERRORS (snapshot left unchanged for these):")
        for wt_id, label, err in errors:
            print(f"  {wt_id:<16} {label[:40]:<40} {err}")
        print()
    if unchanged and not (drifted or new):
        print("All watched WikiTree profiles unchanged since the last baseline.\n")

    if args.update:
        # Merge new results into the snapshot (keep prior entries we couldn't fetch).
        for wt_id, prof in results.items():
            wt_snap[wt_id] = {"Touched": prof["Touched"], "Name": prof["Name"]}
        snap["wikitree"] = wt_snap
        save_snapshots(snap)
        print(f"Baseline updated for {len(results)} profiles -> {os.path.relpath(SNAPSHOTS)}")
        return 0

    if errors:
        return 3
    if drifted:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
