#!/usr/bin/env python3
"""New-Records Watch - headless leading-indicator scan (Ancestry / English half).

Fetches recent Genea-Musings "Added and Updated Ancestry.com Record Collections"
weekly posts via the public Blogger JSON feed and flags any post - newer than the
stored baseline - whose content mentions a watched region (`scan_keywords` in
.maintenance.json `new_records`). This is the zero-login, automatable half of the
New-Records Watch; the login/JS-gated providers (FS collections, Antenati,
Geneteka, AGAD) are the operator-Chrome half, driven by New_Records_Watch.md rows.

Usage:
  python3 scripts/new_records_scan.py           # report keyword hits newer than baseline
  python3 scripts/new_records_scan.py --update   # report, then write the newest post as baseline

Exit code: 0 = no new keyword-matching post (or --update wrote a baseline),
2 = a new relevant post found (go look), 3 = fetch failed (network) - snapshot
left untouched. Zero third-party deps (urllib). Absent config => no-op exit 0.
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import vault_config

VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
CONFIG = os.path.join(VAULT, ".maintenance.json") if VAULT else None
SNAPSHOTS = os.path.join(VAULT, "new_records_snapshots.json") if VAULT else None

FEED = ("https://www.geneamusings.com/feeds/posts/default"
        "?q=%22Added+and+Updated+Ancestry%22&alt=json&max-results=8")
USER_AGENT = "autoresearch-genealogy-newrecords/1.0 (personal genealogy vault discovery check)"


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def scan_keywords():
    cfg = _load_json(CONFIG, {})
    return cfg.get("new_records", {}).get("scan_keywords", [])


def fetch_feed():
    req = urllib.request.Request(FEED, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def entries(feed):
    out = []
    for e in feed.get("feed", {}).get("entry", []):
        title = e.get("title", {}).get("$t", "")
        if "ancestry" not in title.lower():
            continue
        content = html.unescape(re.sub(r"<[^>]+>", " ", e.get("content", {}).get("$t", "")))
        pub = e.get("published", {}).get("$t", "")
        pid = e.get("id", {}).get("$t", "")
        link = next((l.get("href") for l in e.get("link", []) if l.get("rel") == "alternate"), "")
        out.append({"id": pid, "title": title, "published": pub, "content": content, "link": link})
    return out


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="write the newest post as the new baseline")
    args = ap.parse_args()

    kws = scan_keywords()
    if not kws:
        print("New-Records scan: not configured (no new_records.scan_keywords)")
        return 0

    snap = _load_json(SNAPSHOTS, {})
    base = snap.get("geneamusings", {}) or {}
    base_date = base.get("last_checked")

    try:
        feed = fetch_feed()
    except Exception as e:  # network / parse - do not clobber the snapshot
        print(f"New-Records scan: FETCH FAILED ({e}); snapshot untouched")
        return 3

    posts = entries(feed)
    if not posts:
        print("New-Records scan: no 'Added and Updated Ancestry' posts in feed")
        return 0

    def newer(pub):
        if not base_date:
            return True  # no baseline yet => everything is 'new' (first run)
        return pub[:10] > str(base_date)[:10]

    hits = []
    for p in posts:
        if not newer(p["published"]):
            continue
        matched = sorted({k for k in kws if re.search(re.escape(k), p["content"], re.I)})
        if matched:
            hits.append((p, matched))

    if hits:
        print(f"New-Records scan: {len(hits)} NEW post(s) mentioning watched regions:")
        for p, matched in hits:
            print(f"  - {p['published'][:10]} [{', '.join(matched)}] {p['title'].strip()}")
            print(f"    {p['link']}")
    else:
        newest = posts[0]["published"][:10]
        print(f"New-Records scan: no new region-matching Ancestry post (newest feed post {newest}; keywords {', '.join(kws)})")

    if args.update:
        snap["geneamusings"] = {
            "last_post_id": posts[0]["id"],
            "last_checked": datetime.now(timezone.utc).date().isoformat(),
        }
        with open(SNAPSHOTS, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"New-Records scan: baseline updated (newest post {posts[0]['published'][:10]})")
        return 0

    return 2 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
