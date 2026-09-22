#!/usr/bin/env python3
"""bio_slice.py — the per-sitting BIOGRAPHY SLICE: draw, record, check, heartbeat.

** WHY THIS EXISTS (operator ruling 22 SEP 2026). ** The standing goal since 01 AUG 2026 is
"a complete biographical entry for every person", and `bio_completeness.py` has measured it
since then. Nothing WORKED it. Measured over seven weeks on the reference vault: BIO_COMPLETE
went 22% -> 29% and moved about one point in the last five weeks, while BIO_THIN sat near
260. The lanes explain why:

  * IMPROVE's population is SOURCE_GAP / SINGLE_SOURCED / DEFECT rows and its dispositions
    are `--sourced` / `--corroborated` / `--verified`: all about CITATIONS. The 01 AUG
    biography ruling was turned into "more hosts" (MULTI_SOURCED), which is a sourcing
    measure, so the lane optimises records and never credits writing a life.
  * ROTATE's hit is "something new found outside the vault". Writing up what the vault
    already cites is, by that definition, not a hit.

So no lane's unit ever credited the work, and a unit is what decides what a sitting does.
This slice supplies one, shaped like the question slice: a script draws it, the close command
checks it, the banner reports it.

** THE UNIT IS MEASURED, NOT SELF-REPORTED. ** At the draw the slice snapshots each drawn
entry's facets (bio_completeness.facets) and its narrative line count. `--record ... written`
recomputes them and is REFUSED unless the entry gained a facet or at least
NARRATIVE_GAIN lines of biography. An entry whose sources hold nothing more to write is
recorded `nothing-to-add`, with a note naming what was read; an access limit is `blocked`.

** THE DRAW (a triage order, not a verdict). ** Candidates are bio_completeness rows (living
and unknown are already excluded there) not drawn within `cooldown` sittings. Ranked:
DIRECT ancestors of Gen 1 before collaterals; entries that already cite sources before those
that cite none (a life can be written from what is cited; an uncited stub needs IMPROVE or
EXPAND first); then fewest WRITABLE core facets (born, died, spouse/children: `parents` is
EXPAND's gap and `sources` IMPROVE's, so neither ranks here), then no narrative, then fewest
life facets, then the nearest generation.

Usage:
    python3 scripts/bio_slice.py --session N              # show the draw (dry run)
    python3 scripts/bio_slice.py --session N --draw       # register it for sitting N
    python3 scripts/bio_slice.py --session N --record P-XXXXXX --outcome written --note "..."
    python3 scripts/bio_slice.py --session N --check      # close-command gate
    python3 scripts/bio_slice.py --heartbeat              # banner line

Config (optional) in .maintenance.json:
    "bio_slice": {"per_session": 5, "cooldown": 5}

Exit codes for --check: 0 PASS, 1 FAIL (slice missing or unrecorded), 2 WARN (nothing written).
"""
import argparse
import json
import os
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import vault_config  # noqa: E402
import person_store as PS  # noqa: E402
import bio_completeness as BC  # noqa: E402

SNAPSHOT_FILE = "bio_slice_snapshots.json"
MAINTENANCE_FILE = ".maintenance.json"
CONFIG_KEY = "bio_slice"
OUTCOMES = ("written", "nothing-to-add", "blocked", "untouched")
DEFAULTS = {"per_session": 5, "cooldown": 5}
NARRATIVE_GAIN = 3   # lines of biography that count as "written" without a new facet
# The core facets a WRITE-UP can supply from what an entry already cites. `parents` is
# EXPAND's work (a missing parent is a frontier row, not a prose gap) and `sources` is
# IMPROVE's, so neither ranks the draw; both still count as gains if a write-up adds them.
WRITABLE_CORE = ("born", "died", "spouse_or_children")


def load_config(vault):
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(vault, MAINTENANCE_FILE), encoding="utf-8") as f:
            cfg.update(json.load(f).get(CONFIG_KEY) or {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return cfg


def empty_state():
    return {"pending": None, "history": []}


def load_state(vault):
    try:
        with open(os.path.join(vault, SNAPSHOT_FILE), encoding="utf-8") as f:
            st = json.load(f)
    except FileNotFoundError:
        return empty_state()
    except (json.JSONDecodeError, OSError) as e:
        raise SystemExit(f"bio_slice: {SNAPSHOT_FILE} unreadable ({e})")
    st.setdefault("pending", None)
    st.setdefault("history", [])
    return st


def save_state(vault, state):
    with open(os.path.join(vault, SNAPSHOT_FILE), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
        f.write("\n")


def live_rows(history):
    return [h for h in history if not h.get("superseded")]


# ---------------------------------------------------------------- measurement
def measure(vault):
    """{id: {"facets": {...}, "narrative": n, "name", "gen", "core", "life"}} for every
    researchable entry, through bio_completeness's own facet rules (one reader)."""
    blocks = list(PS.iter_entry_blocks(vault))
    parent_ids = {str(t).strip().rstrip("?") for rec, *_ in blocks for t in (rec.parents or [])}
    out = {}
    for rec, _path, _i, block in blocks:
        if not rec.id or (rec.life_status or "") in ("living", "unknown"):
            continue
        f = BC.facets(rec, block, rec.id in parent_ids)
        out[rec.id] = {"facets": f, "narrative": BC.narrative_lines(block),
                       "name": rec.name, "gen": rec.generation,
                       "core": sum(1 for k in BC.CORE if f[k]),
                       "life": sum(1 for k in BC.LIFE if f[k])}
    return out


def _direct_ids(vault):
    try:
        import session_plan
        return session_plan.direct_ancestor_ids(vault)
    except Exception:
        return set()


def _sessions_since_drawn(history, pid):
    last = None
    for i, h in enumerate(live_rows(history)):
        if h["id"] == pid:
            last = i
    if last is None:
        return None
    rows = live_rows(history)
    return len({h.get("session") for h in rows[last + 1:] if h.get("session") is not None})


def candidates(vault, cfg, state, measured=None):
    m = measured if measured is not None else measure(vault)
    direct = _direct_ids(vault)
    cool = int(cfg.get("cooldown", DEFAULTS["cooldown"]))
    pend = state.get("pending") or {}
    out = []
    for pid, r in m.items():
        if r["core"] == len(BC.CORE) and r["facets"]["narrative"]:
            continue   # a complete core with a written life: not slice work
        since = _sessions_since_drawn(state["history"], pid)
        if since is not None and since < cool:
            continue
        if pid in (pend.get("offered") or []):
            continue
        g = r["gen"] if isinstance(r["gen"], int) else 999
        writable = sum(1 for k in WRITABLE_CORE if r["facets"][k])
        key = (pid not in direct, not r["facets"]["sources"], writable,
               r["facets"]["narrative"], r["life"], g, pid)
        out.append((key, pid, r))
    out.sort()
    return [(pid, r, pid in direct) for _k, pid, r in out]


# ---------------------------------------------------------------- commands
def draw(vault, session, register):
    cfg = load_config(vault)
    state = load_state(vault)
    pend = state.get("pending")
    if pend and pend.get("session") == session:
        print(f"BIO SLICE for sitting #{session} already drawn {pend['date']}: "
              f"{', '.join(pend['offered'])}")
        return 0
    m = measure(vault)
    cands = candidates(vault, cfg, state, m)
    n = int(cfg.get("per_session", DEFAULTS["per_session"]))
    pick = cands[:n]
    print(f"=== BIO SLICE — sitting #{session}: {len(pick)} of {len(cands)} eligible ===")
    for pid, r, is_direct in pick:
        missing = [k for k in BC.CORE if not r["facets"][k]]
        print(f"  {pid}  Gen {str(r['gen'] or '?'):>3}  {str(r['name'])[:40]:<42} "
              f"core {r['core']}/{len(BC.CORE)}  life {r['life']}/{len(BC.LIFE)}  "
              f"narrative {r['narrative']} lines  "
              f"{'[direct]' if is_direct else '[collateral]'}"
              + (f"  missing: {', '.join(missing)}" if missing else ""))
    if pend and pend.get("session") != session:
        unrec = _unrecorded(state, pend)
        if unrec:
            print(f"  ⚠ the previous slice (sitting #{pend['session']}) left "
                  f"{', '.join(unrec)} unrecorded; recording them as untouched on --draw")
    if not register:
        print("  (dry run: --draw registers this slice for the sitting)")
        return 0
    if pend and pend.get("session") != session:
        for pid in _unrecorded(state, pend):
            state["history"].append({"date": date.today().isoformat(),
                                     "session": pend["session"], "id": pid,
                                     "outcome": "untouched",
                                     "note": "auto: not recorded before the next draw"})
    state["pending"] = {"session": session, "date": date.today().isoformat(),
                        "offered": [pid for pid, _r, _d in pick],
                        "before": {pid: {"facets": r["facets"], "narrative": r["narrative"]}
                                   for pid, r, _d in pick}}
    save_state(vault, state)
    print(f"  registered in {SNAPSHOT_FILE}")
    return 0


def _unrecorded(state, pend):
    done = {h["id"] for h in live_rows(state["history"]) if h.get("session") == pend["session"]}
    return [p for p in pend["offered"] if p not in done]


def gained(before, now):
    """(new facets, narrative line delta) between a draw snapshot and a re-measure."""
    new = sorted(k for k, v in now["facets"].items() if v and not before["facets"].get(k))
    return new, now["narrative"] - before["narrative"]


def record(vault, session, pid, outcome, note, supersede=False):
    state = load_state(vault)
    pend = state.get("pending") or {}
    prior = [h for h in live_rows(state["history"])
             if h.get("session") == session and h["id"] == pid]
    if prior and not supersede:
        print(f"bio_slice: {pid} is ALREADY recorded for sitting #{session} as "
              f"'{prior[-1]['outcome']}'. Pass --supersede to correct it.", file=sys.stderr)
        return 1
    if supersede and not prior:
        print(f"bio_slice: --supersede given but {pid} has no recorded outcome for "
              f"sitting #{session}.", file=sys.stderr)
        return 1
    offered = pend.get("session") == session and pid in pend.get("offered", [])
    before = (pend.get("before") or {}).get(pid) if offered else None
    now = measure(vault).get(pid)
    if now is None:
        print(f"bio_slice: {pid} is not a researchable entry (unknown id, or living/unknown).",
              file=sys.stderr)
        return 1
    new, dlines = gained(before, now) if before else ([], 0)
    if outcome == "written":
        if before is None:
            print(f"bio_slice: {pid} was not drawn this sitting, so there is no before-"
                  "snapshot to measure against; draw it or record it off the slice as "
                  "nothing-to-add.", file=sys.stderr)
            return 1
        if not new and dlines < NARRATIVE_GAIN:
            print(f"bio_slice: REFUSED 'written' for {pid}: no facet gained and narrative "
                  f"+{dlines} lines (needs a new facet or +{NARRATIVE_GAIN}). Write the "
                  "life into the entry first, or record nothing-to-add with what was read.",
                  file=sys.stderr)
            return 1
    if outcome == "nothing-to-add" and not note.strip():
        print("bio_slice: nothing-to-add needs --note naming what was read.", file=sys.stderr)
        return 1
    if supersede:
        for h in reversed(state["history"]):
            if h.get("session") == session and h["id"] == pid and not h.get("superseded"):
                h["superseded"] = True
                h["superseded_on"] = date.today().isoformat()
                break
    state["history"].append({"date": date.today().isoformat(), "session": session, "id": pid,
                             "outcome": outcome, "note": note, "drawn": bool(offered),
                             "facets_gained": new, "narrative_delta": dlines})
    save_state(vault, state)
    print(f"recorded {pid}: {outcome} (sitting #{session}"
          f"{'' if offered else ', off-slice'}; facets gained: {', '.join(new) or 'none'}; "
          f"narrative {dlines:+d} lines)")
    return 0


def check(vault, session):
    """Close gate. Returns (code, message): 0 PASS, 1 FAIL, 2 WARN."""
    state = load_state(vault)
    cfg = load_config(vault)
    if int(cfg.get("per_session", DEFAULTS["per_session"])) <= 0:
        return 0, "biography slice disabled (.maintenance.json bio_slice.per_session = 0)"
    pend = state.get("pending")
    if not pend or pend.get("session") != session:
        if not candidates(vault, cfg, state):
            return 0, "no drawable biographies: nothing owed"
        return 1, (f"no biography slice drawn for sitting #{session}: run bio_slice.py "
                   f"--session {session} --draw, write each life, --record each")
    unrec = _unrecorded(state, pend)
    if unrec:
        return 1, (f"slice drawn but {', '.join(unrec)} unrecorded "
                   "(record each: written / nothing-to-add / blocked / untouched)")
    mine = [h for h in live_rows(state["history"]) if h.get("session") == session]
    tally = {o: sum(h["outcome"] == o for h in mine) for o in OUTCOMES}
    facets_n = sum(len(h.get("facets_gained") or []) for h in mine)
    lines_n = sum(max(h.get("narrative_delta") or 0, 0) for h in mine)
    summary = (f"biographies WRITTEN {tally['written']} of {len(pend['offered'])} drawn "
               f"({facets_n} facets gained, +{lines_n} narrative lines); nothing-to-add "
               f"{tally['nothing-to-add']}, blocked {tally['blocked']}, untouched "
               f"{tally['untouched']}")
    if not tally["written"]:
        return 2, summary + " — nothing written: say why in the close block"
    return 0, summary


def heartbeat(vault):
    state = load_state(vault)
    m = measure(vault)
    n = len(m) or 1
    comp = sum(1 for r in m.values() if r["core"] == len(BC.CORE))
    rows = live_rows(state["history"])
    recent = sorted({h.get("session") for h in rows if h.get("session") is not None})[-5:]
    inrec = [h for h in rows if h.get("session") in recent]
    written = sum(h["outcome"] == "written" for h in inrec)
    facets_n = sum(len(h.get("facets_gained") or []) for h in inrec)
    pend = state.get("pending")
    if pend:
        unrec = _unrecorded(state, pend)
        slice_txt = (f"last slice #{pend['session']} ({pend['date']}) "
                     + (f"{len(unrec)} unrecorded" if unrec else "fully recorded"))
    else:
        slice_txt = "no slice drawn yet"
    return (f"Bio-Slice: BIO_COMPLETE {comp}/{len(m)} ({comp * 100 // n}%); last "
            f"{len(recent)} sittings wrote {written}/{len(inrec)} drawn, {facets_n} facets "
            f"gained; {slice_txt}; DUE every sitting: bio_slice.py --session N --draw, "
            "write each life, --record each")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--session", type=int, help="the sitting number phase 1 established")
    ap.add_argument("--draw", action="store_true", help="register the slice for --session")
    ap.add_argument("--record", metavar="VAULT_ID")
    ap.add_argument("--outcome", choices=OUTCOMES)
    ap.add_argument("--note", default="")
    ap.add_argument("--supersede", action="store_true",
                    help="this --record CORRECTS an outcome already recorded this sitting")
    ap.add_argument("--check", action="store_true", help="close gate for --session")
    ap.add_argument("--heartbeat", action="store_true")
    a = ap.parse_args(argv)
    vault = vault_config.resolve_vault(a.vault)
    if a.heartbeat:
        print(heartbeat(vault))
        return 0
    if a.session is None:
        ap.error("--session N is required for draw / record / check")
    if a.record:
        if not a.outcome:
            ap.error("--record needs --outcome")
        return record(vault, a.session, a.record, a.outcome, a.note, supersede=a.supersede)
    if a.check:
        code, msg = check(vault, a.session)
        print(("PASS " if code == 0 else "FAIL " if code == 1 else "WARN ") + msg)
        return code
    return draw(vault, a.session, a.draw)


if __name__ == "__main__":
    sys.exit(main())
