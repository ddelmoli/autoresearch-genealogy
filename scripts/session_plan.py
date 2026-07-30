#!/usr/bin/env python3
"""session_plan.py — ONE ranked session-start worklist, with the lane DRAWN, not argued.

WHY IT EXISTS (29 JUL 2026 framework review). The toolkit answers "what should this
session work?" with FIVE partial answers that rank overlapping populations in
incompatible orders: extension_frontier (parentless, gen ascending), keystone_report
(LOAD x THIN), harvest_sources (ARK-count buckets), profile_review (bandit draw), and
buildout (edgeless nodes by cluster). Nothing joined them, so every session re-argued
the arbitration from prose — and the banner's information density (10 integrity gates
to 5 aggregate work counts) pointed the opposite way from the stated EXTENSION-first
priority. "Sessions trip over the priorities" was the operator's summary, and the
silent-leaf incident (leaf nodes without edges ignored until forced) was its symptom.

WHAT IT DOES. Builds one plan with four LANES, each fed by the existing tool's OWN
candidate-builder (imported, never re-derived — the "two readers, one entry" rule):

  EXPAND   extension_frontier SILENT rows: no parents edge, no declared reason.
           Ranked gen ascending (shallower = cheaper to verify, likelier to matter).
  IMPROVE  keystone_report rows: LOAD x THIN — the tree leans on them and nobody
           wrote them up. Ranked by score.
  VERIFY   entries whose `parents:`/`spouse:` lists carry `?`-marked (not yet
           FS-confirmed) edges. Ranked gen ascending. ⚠ Read the entry before
           stripping a `?` — it survives legitimately as FS-GAP, SCHOLARLY HEDGE,
           or PRIVACY (see CLAUDE.method.md).
  ROTATE   the profile-review bandit's draw for this session (delegated to
           profile_review.py, which owns that state).

...and DRAWS one recommended lane with a small bandit over lanes (state in the
vault's session_plan_snapshots.json):

  1. BOOTSTRAP FLOOR: while any non-empty lane has fewer than MIN_SAMPLE recorded
     sessions, draw the least-sampled lane. No exploitation on tiny n — the same
     rule the profile-review rotation states, here enforced in code.
  2. STALENESS FLOOR: any lane not drawn within the last STALE_AFTER draws is due.
     The anti-assumption device: no lane silently falls off the rotation.
  3. Otherwise EXPLOIT: highest Laplace-smoothed win rate (wins+1)/(sessions+2).

A "win" is the session moving its lane's metric (frontier SILENT down; a keystone
worked; `?` edges adjudicated; rotation hits) — recorded at close by session_close.py
via `--record`. The draw is a RECOMMENDATION: the operator can override it, and the
override is itself recordable (record the lane actually worked, not the drawn one).

USAGE
  python3 scripts/session_plan.py                    # the session-start quality report
  python3 scripts/session_plan.py --limit 8          # more rows per lane
  python3 scripts/session_plan.py --json
  python3 scripts/session_plan.py --heartbeat        # cheap one-liner (SessionStart banner;
                                                     #   reads state only, builds nothing)
  python3 scripts/session_plan.py --record --lane EXPAND --outcome hit --note "..."
                                                     # at close (session_close.py runs this)

Zero dependencies. Absent state file = fresh bandit (bootstrap floor governs).
Optional .maintenance.json `session_plan` block: {"per_lane": N, "min_sample": N,
"stale_after": N}; absent = defaults. Advisory: never blocks anything.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

SNAPSHOT_FILE = "session_plan_snapshots.json"
CONFIG_KEY = "session_plan"
LANES = ("EXPAND", "IMPROVE", "VERIFY", "ROTATE")
# Defaults; override via .maintenance.json `session_plan` block.
PER_LANE = 5          # rows shown per lane
MIN_SAMPLE = 2        # bootstrap floor: no exploitation until every lane has this many
STALE_AFTER = 6       # staleness floor: a lane undrawn for this many draws is due


# ---------------------------------------------------------------------------
# Lane candidate-builders. Each delegates to the owning tool's own logic.
# ---------------------------------------------------------------------------
def lane_expand(vault):
    import extension_frontier as ef
    rows = [r for r in ef.rows_with_bodies(vault) if not r["declared"]]
    rows.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0,
                             ef.TIER_ORDER.get(r["tier"], 3)))
    return [{"id": r["id"], "name": r["name"], "gen": r["gen"], "file": r["file"],
             "why": "no parents edge, no declared reason"
                    + (" (spouse-linked leaf)" if r["spouse"] else "")}
            for r in rows]


def lane_improve(vault):
    import keystone_report as kr
    rows = [r for r in kr.build_rows(vault) if r["load"] >= 1 and r["thin"] >= 3]
    rows.sort(key=lambda o: (-o["score"], -o["load"], -o["thin"], o["name"]))
    return [{"id": r["id"], "name": r["name"], "gen": r["gen"], "file": r["file"],
             "why": f"keystone: {r['load']} people lean on it, thin {r['thin']}/6 ({r['why']})"}
            for r in rows]


def lane_verify(vault):
    import re
    import gen_person_index as g
    edge_re = re.compile(r"(parents|spouse):\s*'\[([^\]]*)\]'")
    living_re = re.compile(r"life_status:\s*(living|unknown)")
    rows = []
    for p in g.parse_narrative():
        meta = p.get("block") or ""
        if living_re.search(meta):
            continue  # privacy: a `?` here is unclearable by web research
        marked = []
        for kind, ids in edge_re.findall(meta):
            n = ids.count("?")
            if n:
                marked.append(f"{n} {kind}")
        if marked:
            rows.append({"id": p.get("id"), "name": p.get("name") or "?",
                         "gen": p.get("gen"), "file": p.get("file") or "?",
                         "why": "unconfirmed edges: " + ", ".join(marked)
                                + " — read entry before stripping ? (FS-gap/hedge)"})
    rows.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0))
    return rows


def lane_rotate(vault, sample_percent=None):
    """The profile-review draw, delegated: that tool owns its own bandit state.
    Subprocess, not import — its draw path reads/derives its own census and the
    --json contract is the stable surface."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile_review.py")
    try:
        cmd = [sys.executable, script, "--json"]
        if sample_percent:                      # per-session rate override, forwarded
            cmd += ["--sample-percent", str(sample_percent)]
        r = subprocess.run(cmd,
                           capture_output=True, text=True, timeout=600,
                           env={**os.environ, "AUTORESEARCH_VAULT": vault})
        d = json.loads(r.stdout)
    except Exception as e:
        # ** DO NOT return [] SILENTLY. ** An empty list renders as "ROTATE 0
        # candidates", which reads as "nothing to poll" when it actually means
        # the subprocess failed or its --json contract broke. That exact
        # confusion happened on 30 JUL 2026 when a banner was written to stdout.
        print(f"session_plan: WARNING - the ROTATE lane could not be read from "
              f"profile_review.py ({type(e).__name__}: {e}). Reporting 0 "
              f"candidates, which is a TOOL FAILURE, not an empty worklist.",
              file=sys.stderr)
        return []
    return [{"id": e.get("id"), "name": e.get("name"), "gen": e.get("gen"),
             "file": e.get("region") or "", "why": f"rotation draw [{e.get('arm')}]: "
             f"{e.get('draw_reason')}; {e.get('_why') or ''}"}
            for e in d.get("draw", [])]


# ---------------------------------------------------------------------------
# The lane bandit
# ---------------------------------------------------------------------------
def load_state(vault):
    p = os.path.join(vault, SNAPSHOT_FILE)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"arms": {}, "history": [], "pending": None}


def save_state(vault, state):
    p = os.path.join(vault, SNAPSHOT_FILE)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
        f.write("\n")


def draw_lane(state, lane_sizes, min_sample=MIN_SAMPLE, stale_after=STALE_AFTER):
    """Pick the recommended lane. Pure function of (state, lane_sizes) — pinned by
    scripts/test_session_plan.py. Returns (lane, reason)."""
    live = [ln for ln in LANES if lane_sizes.get(ln, 0) > 0]
    if not live:
        return None, "all lanes empty"
    arms = {ln: state.get("arms", {}).get(ln, {"sessions": 0, "wins": 0}) for ln in live}

    # 1. Bootstrap floor: no exploitation while any live lane is undersampled.
    under = [ln for ln in live if arms[ln].get("sessions", 0) < min_sample]
    if under:
        pick = min(under, key=lambda ln: (arms[ln].get("sessions", 0), LANES.index(ln)))
        return pick, (f"bootstrap floor: {pick} has {arms[pick].get('sessions', 0)} "
                      f"recorded sessions (< {min_sample}); no exploitation on tiny n")

    # 2. Staleness floor: a lane undrawn for stale_after draws is due.
    recent = [h.get("lane") for h in state.get("history", [])[-stale_after:]]
    stale = [ln for ln in live if ln not in recent]
    if stale:
        pick = stale[0]
        return pick, f"staleness floor: {pick} not drawn in the last {stale_after} sessions"

    # 3. Exploit the Laplace-smoothed win rate.
    def rate(ln):
        a = arms[ln]
        return (a.get("wins", 0) + 1) / (a.get("sessions", 0) + 2)
    pick = max(live, key=lambda ln: (rate(ln), -LANES.index(ln)))
    return pick, (f"exploit: win rate {rate(pick):.2f} over "
                  f"{arms[pick].get('sessions', 0)} sessions")


def record(state, lane, outcome, note=""):
    if lane not in LANES:
        raise SystemExit(f"unknown lane {lane!r}; one of {', '.join(LANES)}")
    if outcome not in ("hit", "miss"):
        raise SystemExit("outcome must be hit or miss")
    arm = state.setdefault("arms", {}).setdefault(lane, {"sessions": 0, "wins": 0})
    arm["sessions"] += 1
    arm["wins"] += 1 if outcome == "hit" else 0
    state.setdefault("history", []).append(
        {"date": date.today().isoformat(), "lane": lane, "outcome": outcome,
         **({"note": note} if note else {})})
    state["pending"] = None
    return state


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def heartbeat(state):
    """Cheap: reads state only, builds no lanes (the SessionStart hook budget is
    the whole point — the full plan is the session's FIRST COMMAND, not hook work)."""
    pend = state.get("pending")
    hist = state.get("history", [])
    if pend:
        line = (f"PLAN: lane {pend.get('lane')} drawn {pend.get('date')} and NOT yet "
                f"recorded — session_close.py records it; run scripts/session_plan.py "
                f"for this session's plan")
    elif hist:
        h = hist[-1]
        line = (f"PLAN: last lane {h.get('lane')} ({h.get('outcome')}, {h.get('date')}); "
                f"run scripts/session_plan.py FIRST for this session's ranked plan")
    else:
        line = ("PLAN: no lane history yet; run scripts/session_plan.py FIRST for this "
                "session's ranked plan (it draws the lane and prints the worklist)")
    print(line)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--limit", type=int, help="rows per lane (default 5)")
    ap.add_argument("--sample-percent", "--pct", type=float, dest="sample_percent",
                    metavar="X",
                    help="Sample X%% of the pool in the ROTATE lane THIS SESSION only "
                         "(forwarded to profile_review.py). The standing rate is "
                         "`sample_percent` in .maintenance.json.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--record", action="store_true",
                    help="record a lane outcome (with --lane/--outcome[/--note])")
    ap.add_argument("--lane")
    ap.add_argument("--outcome", choices=["hit", "miss"])
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    cfg = {}
    try:
        with open(os.path.join(vault, ".maintenance.json"), encoding="utf-8") as f:
            cfg = json.load(f).get(CONFIG_KEY, {}) or {}
    except Exception:
        pass
    per_lane = a.limit or int(cfg.get("per_lane", PER_LANE))
    min_sample = int(cfg.get("min_sample", MIN_SAMPLE))
    stale_after = int(cfg.get("stale_after", STALE_AFTER))

    state = load_state(vault)

    if a.heartbeat:
        heartbeat(state)
        return 0

    if a.record:
        if not (a.lane and a.outcome):
            raise SystemExit("--record needs --lane and --outcome")
        save_state(vault, record(state, a.lane.upper(), a.outcome, a.note))
        print(f"PLAN: recorded lane {a.lane.upper()} -> {a.outcome}")
        return 0

    # The full plan.
    lanes = {
        "EXPAND": lane_expand(vault),
        "IMPROVE": lane_improve(vault),
        "VERIFY": lane_verify(vault),
        "ROTATE": lane_rotate(vault, a.sample_percent),
    }
    if a.sample_percent:
        print(f"** ROTATE sample rate overridden for this session: {a.sample_percent:g}% "
              f"(standing rate is `sample_percent` in .maintenance.json). **")
    sizes = {ln: len(rows) for ln, rows in lanes.items()}
    pick, reason = draw_lane(state, sizes, min_sample, stale_after)

    if pick:
        state["pending"] = {"date": date.today().isoformat(), "lane": pick}
        save_state(vault, state)

    if a.json:
        print(json.dumps({"date": date.today().isoformat(), "lane": pick,
                          "reason": reason, "sizes": sizes,
                          "lanes": {ln: rows[:per_lane] for ln, rows in lanes.items()}},
                         indent=1, default=str))
        return 0

    counts = " / ".join(f"{ln} {sizes[ln]}" for ln in LANES)
    print("=== SESSION PLAN — one ranked worklist, one drawn lane ===")
    print(f"  {counts}")
    print(f"  RECOMMENDED LANE: {pick}  ({reason})")
    print("  The draw is a recommendation; if you work a different lane, record THAT")
    print("  one at close: python3 scripts/session_close.py --lane <L> --outcome hit|miss")
    ordered = ([pick] if pick else []) + [ln for ln in LANES if ln != pick]
    for ln in ordered:
        rows = lanes[ln]
        mark = " <-- THIS SESSION" if ln == pick else ""
        print(f"\n  [{ln}] {sizes[ln]} candidates{mark}")
        for r in rows[:per_lane]:
            gen = f"Gen {r['gen']:>2}" if r.get("gen") not in (None, "") else "Gen  ?"
            print(f"    {gen}  {str(r.get('name'))[:42]:44} {r.get('why')}")
        if sizes[ln] > per_lane:
            print(f"    ... and {sizes[ln] - per_lane} more (--limit N, or the owning "
                  f"tool for the full list)")
    print(f"\nPLAN: lane {pick}; {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
