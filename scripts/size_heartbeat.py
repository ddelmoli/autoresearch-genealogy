#!/usr/bin/env python3
"""
size_heartbeat.py — detection-only heartbeat for vault housekeeping (Plan 1).

Reads the OPTIONAL vault/.maintenance.json and reports which growth-prone files
have a housekeeping action DUE. Prints ONE context segment for the SessionStart
hook (scripts/session_audit.sh). NO mutation — the actual archiving is done by
scripts/archive_sections.py, surfaced as an interactive "Vault Housekeeping"
checklist.

Key rule: an action is DUE only when the file is BOTH over its token threshold
AND has something archivable. A file can be legitimately large with nothing to
move (e.g. Open_Questions full of genuinely-open questions); we do not nag then.
Thresholds are in TOKENS (bytes/4), never lines — a 145-line file can be 35k tok.

Reuses archive_sections' planning functions so "what's archivable" has a single
source of truth. Silent-safe: no config => prints an all-clear and exits 0.
"""
import glob
import os
import sys

import archive_sections as A  # same dir on sys.path[0] when run as a script


def _archivable_count(text, t, ts="DRYRUN"):
    policy = t["policy"]
    if policy == "keep-n-recent":
        _, _, dropped = A.plan_keep_n_recent(text, t)
    elif policy == "drop-by-status":
        _, _, dropped = A.plan_drop_by_status(text, t, ts)
    elif policy == "drop-older-rows":
        _, _, dropped = A.plan_drop_older_rows(text, t)
    else:
        return 0
    return len(dropped)


def due_actions():
    cfg = A.load_config()
    actions = []
    for t in cfg.get("targets", []):
        path = A.VAULT / t["file"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        toks = A.est_tokens(text)
        over = toks >= t.get("threshold_tokens", 0)
        n = _archivable_count(text, t)
        if over and n > 0:
            actions.append((t["name"], t["label"], n, toks))
    shard_cfg = cfg.get("shards")
    shards = []
    if shard_cfg:
        thr = shard_cfg.get("threshold_tokens", 10 ** 12)
        for p in sorted(glob.glob(str(A.VAULT / shard_cfg["glob"]))):
            tk = A.est_tokens(open(p, encoding="utf-8").read())
            if tk >= thr:
                shards.append((os.path.basename(p), tk))
    return actions, shards, shard_cfg


def main():
    if not A.CONFIG.exists():
        print("HOUSEKEEPING: no .maintenance.json — skipped.")
        return 0
    actions, shards, shard_cfg = due_actions()
    total = len(actions) + (1 if shards else 0)
    if total == 0:
        print("HOUSEKEEPING: all clear (nothing over threshold with archivable backlog).")
        return 0

    bits = [f"{name} [{label.lower()}: {n} item(s), file ~{toks // 1000}k tok]"
            for name, label, n, toks in actions]
    if shards:
        thr = shard_cfg.get("threshold_tokens", 0) // 1000
        slist = ", ".join(f"{b} ~{tk // 1000}k" for b, tk in shards[:5])
        more = "" if len(shards) <= 5 else f" +{len(shards) - 5} more"
        bits.append(f"split-shard [{len(shards)} shard(s) over {thr}k: {slist}{more}]")

    print("VAULT HOUSEKEEPING: " + str(total) + " action(s) DUE — " + "; ".join(bits)
          + ". At session start, present these as a Vault Housekeeping checklist via "
            "AskUserQuestion (multiSelect) BEFORE other work. For each chosen archive item: "
            "`python3 scripts/archive_sections.py --target <name>` (dry-run) -> review -> add "
            "`--apply`. Split-shard is a manual semantic edit (see scripts/tree_locator.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
