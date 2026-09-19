#!/usr/bin/env python3
"""question_drain.py — the per-sitting QUESTION SLICE: draw, record, check, heartbeat.

** WHY THIS EXISTS, AND IT IS A MEASURED FAILURE. ** Until this script, the only rule
that sent a sitting to the Open_Questions register was prompt 22's "when the lane runs
dry, drain the register". Lanes almost never run dry, so the rule almost never fired.
Measured 18 SEP 2026 on the reference vault: September raised 36 questions and closed 3,
against 145 closed in August, and the live register stood at 206. A rule that fires on
an event that does not happen is not a rule.

** THE FIX IS AN OBLIGATION, SHAPED LIKE THE PROFILE-REVIEW SLICE. ** That slice is the
one per-sitting duty the loop reliably performs, because a script draws it, the banner
reports it and the close command checks it. This copies all three:

  * a DRAW of `per_session` questions (default 5; raised from 3 by operator ruling 19 SEP 2026), registered for the sitting;
  * a RECORD per drawn question with one of four outcomes;
  * a CHECK the close command runs (FAIL if the slice was not worked);
  * a HEARTBEAT line with the register's NET FLOW, so growth is visible every session.

** THE FOUR OUTCOMES, AND WHY "advanced" IS NOT "resolved". **
  resolved   the question's block now carries a terminal status (write it with
             question_store.py --resolve; this script does not edit the register)
  advanced   the next document is now NAMED specifically (appended with --append)
  blocked    an access limit stopped the read (restricted image, site refusing,
             in-person only); the question cools off for `blocked_cooldown` sittings
  untouched  drawn and not worked (recorded honestly rather than left silent)

** SWAP: replacing a drawn question before it is worked (added 18 SEP 2026). ** The ranking
is keyword-derived, so a draw can hand the sitting a question that is not closable at all
(a collection-wide policy question, say). `--swap Q202 --note "why"` takes it out of the
pending slice and puts the next-ranked eligible question in its place (`--with Q378` names
the replacement instead). The swapped-out question is written to history with outcome
`swapped` and its reason, so the close gate counts it as dealt with, the replacement counts
as DRAWN (not off-slice) when recorded, and the swapped question sits out `swap_cooldown`
sittings like a blocked one, so the same draw does not hand it straight back. A question
already recorded this sitting cannot be swapped: swap is for what was NOT worked. `swapped`
is not a `--record` outcome; only `--swap` writes it.
"Advanced" is real work but it does not shrink the register; August's advanced notes are
how the register grew while looking busy. The heartbeat therefore counts CLOSURES from
the headings themselves, not from this script's own records.

** RANKING (a triage heuristic, not a verdict). ** Candidates are the live questions from
gen_question_index.parse() (ONE home for the block grammar and liveness). Excluded:
`op-gated` and `BIG` tags, a question recorded `blocked` within the cooldown, and any
question whose body matches a `blocked_routes` pattern (a site currently refusing, e.g.
set ["Antenati"] while it 403s). Scored: located-but-unread source +3, a named free route
+2, a named resolver line +1, a small block (<5 KB) +1; ties go to the OLDEST question
number. ⚠ The tags are keyword-derived (see gen_question_index's docstring), so a draw is
a candidate list: read each question before working it.

** NET FLOW IS DERIVED FROM THE HEADINGS, NOT FROM THIS SCRIPT. ** "Raised" dates come
from the title's provenance clause `(raised DD MON YYYY ...)`; "closed" dates from a
terminal status `— RESOLVED DD MON YYYY` (any terminal keyword). Both live shards and the
Resolved store are read, deduplicated by block title (the vault has genuine duplicate Q
numbers), so a closure made by ANY lane counts, not only one made through the slice.

Usage:
    python3 scripts/question_drain.py --session N              # show the draw (dry run)
    python3 scripts/question_drain.py --session N --draw       # register it for sitting N
    python3 scripts/question_drain.py --session N --record Q185 --outcome resolved --note "..."
    python3 scripts/question_drain.py --session N --swap Q202 [--with Q378] --note "why"
    python3 scripts/question_drain.py --session N --check      # close-command gate
    python3 scripts/question_drain.py --heartbeat              # banner line
    python3 scripts/question_drain.py --net [--days 30]        # raised vs closed by week

Config (optional) in .maintenance.json:
    "question_drain": {"per_session": 5, "blocked_cooldown": 3, "swap_cooldown": 3,
                       "blocked_routes": []}

Exit codes for --check: 0 PASS, 1 FAIL (slice missing or unrecorded), 2 WARN (the sitting
raised questions and closed none).
"""
import argparse
import json
import os
import re
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import vault_config  # noqa: E402
import question_block as QB  # noqa: E402
import gen_question_index as GQI  # noqa: E402

SNAPSHOT_FILE = "question_drain_snapshots.json"
MAINTENANCE_FILE = ".maintenance.json"
CONFIG_KEY = "question_drain"
OUTCOMES = ("resolved", "advanced", "blocked", "untouched")
SWAPPED = "swapped"    # written only by --swap, never a --record outcome
DEFAULTS = {"per_session": 5, "blocked_cooldown": 3, "swap_cooldown": 3, "blocked_routes": []}

MONTHS = {m: i for i, m in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
DATE_RX = r"(\d{1,2}) (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]* (\d{4})"
RAISED_RX = re.compile(r"\((?:raised|opened)\s+" + DATE_RX, re.I)
RAISED_SESSION_RX = re.compile(r"\((?:raised|opened)[^)]*session #(\d+)", re.I)
STATUS_DATE_RX = re.compile(DATE_RX, re.I)


# ---------------------------------------------------------------- state / config
def empty_state():
    return {"pending": None, "history": []}


def load_state(vault):
    path = os.path.join(vault, SNAPSHOT_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
    except FileNotFoundError:
        return empty_state()
    except (json.JSONDecodeError, OSError) as e:
        raise SystemExit(f"question_drain: {SNAPSHOT_FILE} unreadable ({e})")
    st.setdefault("pending", None)
    st.setdefault("history", [])
    return st


def save_state(vault, state):
    path = os.path.join(vault, SNAPSHOT_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def load_config(vault):
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(vault, MAINTENANCE_FILE), encoding="utf-8") as f:
            cfg.update(json.load(f).get(CONFIG_KEY) or {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return cfg


def _date(d, mon, y):
    return date(int(y), MONTHS[mon.upper()[:3]], int(d))


# ---------------------------------------------------------------- candidates
def _qkey(label):
    """Normalise 'Q185' / '185' / 'q143a' to the index's qlabel form ('185', '143a')."""
    return str(label).strip().upper().lstrip("Q").lower()


def _sessions_since(history, qkey, outcome):
    """Distinct sittings recorded AFTER the last `outcome` for this question, or None."""
    last = None
    for i, h in enumerate(history):
        if h["q"] == qkey and h["outcome"] == outcome:
            last = i
    if last is None:
        return None
    return len({h.get("session") for h in history[last + 1:] if h.get("session") is not None})


def _body(vault, row):
    hits = QB.find_live_blocks(vault, row["num"], row["suffix"])
    if not hits:
        return ""
    _p, s, e, _h, lines = hits[0]
    return "\n".join(lines[s:e])


def candidates(vault, cfg, state):
    rows = GQI.parse(vault)
    cooldown = int(cfg.get("blocked_cooldown", 3))
    swap_cool = int(cfg.get("swap_cooldown", 3))
    routes = [re.compile(p, re.I) for p in (cfg.get("blocked_routes") or [])]
    out = []
    for r in rows:
        if "op-gated" in r["tags"] or "BIG" in r["tags"]:
            continue
        q = r["qlabel"]
        since = _sessions_since(state["history"], q, "blocked")
        if since is not None and since < cooldown:
            continue
        since = _sessions_since(state["history"], q, SWAPPED)
        if since is not None and since < swap_cool:
            continue
        score = (3 if "UNREAD-SRC" in r["tags"] else 0) + (2 if "free" in r["tags"] else 0) \
            + (1 if r["resolver"] else 0) + (1 if r["kb"] < 5 else 0)
        out.append((score, r))
    out.sort(key=lambda t: (-t[0], t[1]["num"], t[1]["suffix"]))
    if routes:
        kept = []
        for score, r in out:
            if len(kept) >= 60:
                break
            body = _body(vault, r)
            if any(rx.search(body) for rx in routes):
                continue
            kept.append((score, r))
        out = kept
    return out


# ---------------------------------------------------------------- net flow
def heading_dates(vault):
    """{block_key: (raised_date|None, closed_date|None, raised_session|None)} over live
    shards AND the Resolved store, deduplicated by title."""
    seen = {}
    paths = list(QB.question_files(vault))
    rf = QB.resolved_file(vault)
    if os.path.exists(rf):
        paths.append(rf)
    for p in paths:
        for s, _e, h, lines in QB.iter_questions(p):
            head = lines[s]
            if h["original"]:
                continue
            key = QB.block_key(head)
            m = RAISED_RX.search(h["title"])
            raised = _date(*m.groups()) if m else None
            ms = RAISED_SESSION_RX.search(h["title"])
            rsess = int(ms.group(1)) if ms else None
            closed = None
            if h["terminal"]:
                md = STATUS_DATE_RX.search(h["status"])
                closed = _date(*md.groups()) if md else None
            prev = seen.get(key)
            if prev is None:
                seen[key] = (raised, closed, rsess)
            else:   # merge a live copy and an archived copy of the same block
                seen[key] = (prev[0] or raised, prev[1] or closed, prev[2] or rsess)
    return seen


def net_flow(vault, days, today=None):
    today = today or date.today()
    since = today - timedelta(days=days)
    raised = closed = 0
    for r, c, _s in heading_dates(vault).values():
        raised += bool(r and r > since)
        closed += bool(c and c > since)
    return raised, closed


def live_count(vault):
    return len(GQI.parse(vault))


# ---------------------------------------------------------------- commands
def draw(vault, session, register):
    cfg = load_config(vault)
    state = load_state(vault)
    pend = state.get("pending")
    if pend and pend.get("session") == session:
        print(f"QUESTION SLICE for sitting #{session} already drawn "
              f"{pend['date']}: {', '.join('Q' + q for q in pend['offered'])}")
        return 0
    cands = candidates(vault, cfg, state)
    n = int(cfg.get("per_session", DEFAULTS["per_session"]))
    pick = cands[:n]
    print(f"=== QUESTION SLICE — sitting #{session}: {len(pick)} of {len(cands)} eligible "
          f"({live_count(vault)} live) ===")
    for score, r in pick:
        print(f"  Q{r['qlabel']:<6} [{score}] {r['kb']:4.1f} KB  {' '.join(r['tags']) or '-':<18} "
              f"{r['title'][:70]}")
        if r["resolver"]:
            print(f"          resolver: {r['resolver'][:100]}")
    if pend and pend.get("session") != session:
        unrec = _unrecorded(state, pend)
        if unrec:
            print(f"  ⚠ the previous slice (sitting #{pend['session']}) left "
                  f"{', '.join('Q' + q for q in unrec)} unrecorded; recording them as "
                  "untouched on --draw")
    if not register:
        print("  (dry run: --draw registers this slice for the sitting)")
        return 0
    if pend and pend.get("session") != session:
        for q in _unrecorded(state, pend):
            state["history"].append({"date": date.today().isoformat(), "session": pend["session"],
                                     "q": q, "outcome": "untouched",
                                     "note": "auto: not recorded before the next draw"})
    state["pending"] = {"session": session, "date": date.today().isoformat(),
                        "offered": [r["qlabel"] for _s, r in pick]}
    save_state(vault, state)
    print(f"  registered in {SNAPSHOT_FILE}")
    return 0


def _unrecorded(state, pend):
    done = {h["q"] for h in state["history"] if h.get("session") == pend["session"]}
    return [q for q in pend["offered"] if q not in done]


def record(vault, session, label, outcome, note):
    q = _qkey(label)
    state = load_state(vault)
    live = {r["qlabel"] for r in GQI.parse(vault)}
    if outcome == "resolved" and q in live:
        print(f"question_drain: Q{q} is still LIVE in the register. Write its terminal "
              "heading first (question_store.py --resolve), then record it resolved.",
              file=sys.stderr)
        return 1
    pend = state.get("pending") or {}
    offered = pend.get("session") == session and q in pend.get("offered", [])
    state["history"].append({"date": date.today().isoformat(), "session": session, "q": q,
                             "outcome": outcome, "note": note,
                             "drawn": bool(offered)})
    save_state(vault, state)
    print(f"recorded Q{q}: {outcome} (sitting #{session}"
          f"{'' if offered else ', off-slice'})")
    return 0


def swap(vault, session, label, replacement=None, note=""):
    """Replace one question of the sitting's PENDING slice before it is worked."""
    out_q = _qkey(label)
    state = load_state(vault)
    pend = state.get("pending")
    if not pend or pend.get("session") != session:
        print(f"question_drain: no slice drawn for sitting #{session}; --draw first.",
              file=sys.stderr)
        return 1
    if out_q not in pend["offered"]:
        print(f"question_drain: Q{out_q} is not in sitting #{session}'s slice "
              f"({', '.join('Q' + q for q in pend['offered'])}).", file=sys.stderr)
        return 1
    done = {h["q"] for h in state["history"] if h.get("session") == session}
    if out_q in done:
        print(f"question_drain: Q{out_q} is already recorded for sitting #{session}; "
              "a swap is for a question that was NOT worked.", file=sys.stderr)
        return 1
    if not note.strip():
        print("question_drain: --swap needs --note saying why the question is swapped out.",
              file=sys.stderr)
        return 1
    if replacement:
        in_q = _qkey(replacement)
        if in_q not in {r["qlabel"] for r in GQI.parse(vault)}:
            print(f"question_drain: Q{in_q} is not a live question.", file=sys.stderr)
            return 1
    else:
        taken = set(pend["offered"]) | done
        pool = [r["qlabel"] for _s, r in candidates(vault, load_config(vault), state)
                if r["qlabel"] not in taken]
        if not pool:
            print("question_drain: no eligible replacement left in the register.",
                  file=sys.stderr)
            return 1
        in_q = pool[0]
    if in_q in pend["offered"] or in_q in done:
        print(f"question_drain: Q{in_q} is already in or recorded for this sitting's slice.",
              file=sys.stderr)
        return 1
    pend["offered"] = [in_q if q == out_q else q for q in pend["offered"]]
    pend.setdefault("swaps", []).append({"out": out_q, "in": in_q, "note": note,
                                         "date": date.today().isoformat()})
    state["history"].append({"date": date.today().isoformat(), "session": session,
                             "q": out_q, "outcome": SWAPPED, "note": note, "drawn": True,
                             "replaced_by": in_q})
    save_state(vault, state)
    print(f"swapped Q{out_q} -> Q{in_q} in sitting #{session}'s slice "
          f"(Q{out_q} sits out {load_config(vault).get('swap_cooldown', 3)} sittings)")
    return 0


def check(vault, session, today=None):
    """Close gate. Returns (code, message): 0 PASS, 1 FAIL, 2 WARN."""
    today = today or date.today()
    state = load_state(vault)
    pend = state.get("pending")
    if not pend or pend.get("session") != session:
        if not candidates(vault, load_config(vault), state):
            return 0, "no drawable questions in the register: nothing owed"
        return 1, (f"no question slice drawn for sitting #{session}: run "
                   f"question_drain.py --session {session} --draw, work it, --record each")
    unrec = _unrecorded(state, pend)
    if unrec:
        return 1, (f"slice drawn but {', '.join('Q' + q for q in unrec)} unrecorded "
                   "(record each: resolved / advanced / blocked / untouched)")
    mine = [h for h in state["history"] if h.get("session") == session]
    tally = {o: sum(h["outcome"] == o for h in mine) for o in OUTCOMES + (SWAPPED,)}
    raised = sum(1 for _r, _c, s in heading_dates(vault).values() if s == session)
    closed_today = sum(1 for _r, c, _s in heading_dates(vault).values() if c == today)
    summary = (f"slice worked: {tally['resolved']} resolved, {tally['advanced']} advanced, "
               f"{tally['blocked']} blocked, {tally['untouched']} untouched, "
               f"{tally[SWAPPED]} swapped; this sitting "
               f"raised {raised}, register closures dated today {closed_today}")
    if raised and not closed_today and not tally["resolved"]:
        return 2, summary + " — raised questions and closed none: say why in the close block"
    return 0, summary


def heartbeat(vault, today=None):
    today = today or date.today()
    state = load_state(vault)
    r14, c14 = net_flow(vault, 14, today)
    r30, c30 = net_flow(vault, 30, today)
    pend = state.get("pending")
    if pend:
        unrec = _unrecorded(state, pend)
        slice_txt = (f"last slice #{pend['session']} ({pend['date']}) "
                     + (f"{len(unrec)} unrecorded" if unrec else "fully recorded"))
    else:
        slice_txt = "no slice drawn yet"
    return (f"Question-Drain: {live_count(vault)} live; net flow 14d raised {r14} / closed "
            f"{c14} ({r14 - c14:+d}), 30d {r30} / {c30} ({r30 - c30:+d}); {slice_txt}; "
            f"DUE every sitting: question_drain.py --session N --draw, work it, --record each")


def net_table(vault, days, today=None):
    today = today or date.today()
    data = heading_dates(vault).values()
    print(f"week ending   raised  closed   net")
    for w in range(days // 7, -1, -1):
        end = today - timedelta(days=7 * w)
        start = end - timedelta(days=7)
        r = sum(1 for x, _c, _s in data if x and start < x <= end)
        c = sum(1 for _r, x, _s in data if x and start < x <= end)
        print(f"{end.isoformat()}   {r:>6}  {c:>6}  {r - c:+5d}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--session", type=int, help="the sitting number phase 1 established")
    ap.add_argument("--draw", action="store_true", help="register the slice for --session")
    ap.add_argument("--record", metavar="QLABEL")
    ap.add_argument("--outcome", choices=OUTCOMES)
    ap.add_argument("--note", default="")
    ap.add_argument("--swap", metavar="QLABEL",
                    help="replace this drawn, unworked question in the pending slice")
    ap.add_argument("--with", dest="with_q", metavar="QLABEL",
                    help="with --swap: the replacement (default: next-ranked eligible)")
    ap.add_argument("--check", action="store_true", help="close gate for --session")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--net", action="store_true")
    ap.add_argument("--days", type=int, default=28)
    a = ap.parse_args(argv)
    vault = vault_config.resolve_vault(a.vault)

    if a.heartbeat:
        print(heartbeat(vault))
        return 0
    if a.net:
        return net_table(vault, a.days)
    if a.session is None:
        ap.error("--session N is required for draw / record / check")
    if a.record:
        if not a.outcome:
            ap.error("--record needs --outcome")
        return record(vault, a.session, a.record, a.outcome, a.note)
    if a.swap:
        return swap(vault, a.session, a.swap, a.with_q, a.note)
    if a.with_q:
        ap.error("--with only goes with --swap")
    if a.check:
        code, msg = check(vault, a.session)
        print(("PASS " if code == 0 else "FAIL " if code == 1 else "WARN ") + msg)
        return code
    return draw(vault, a.session, a.draw)


if __name__ == "__main__":
    sys.exit(main())
