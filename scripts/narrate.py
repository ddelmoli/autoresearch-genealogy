#!/usr/bin/env python3
"""narrate.py -- say WHY, for the session visualizer.

The hooks record what ran; this records the reasoning a watcher needs. Every
subcommand appends one event to the stream `scripts/visualizer.py` serves (see
`scripts/visualizer_events.py` for where it lives and why it is private).

  narrate.py start --title "Research sitting" begin a visualized sitting: archive the old stream,
                                              turn the hooks on
  narrate.py stop                             turn the hooks off
  narrate.py say "Plain English sentence"     a narration line
  narrate.py phase "Research iterations" [--lane EXPAND] [--detail "..."]
  narrate.py person ["Jane Example"] --id P-XXXXXX [--gen 7] [--born 1801] [--died 1870]
                    [--place "Somewhereton"] [--why "why this person was drawn"]
  narrate.py evidence "1850 census, Somewhereton" --verdict counted|excluded|candidate
                    --why "names her with husband and three children" [--host fs]
                    [--person P-XXXXXX]   (whose evidence it is; switches the person card)
  narrate.py negative "Searched the town vital records 1790-1810" [--why "..."]
  narrate.py finding "Her father is named in the 1805 deed" [--tier strong|moderate|speculative]
  narrate.py term "ARK" "a permanent link to one record on FamilySearch"
  narrate.py question Q270 [--pos "3 of 10"] [--why "why it might close today"]
                    (title, age and what would settle it are read from the register)
  narrate.py outcome Q270 --status resolved|advanced|blocked|untouched|swapped
                    --why "what was found, or what stopped it"

Anything but start and stop is recorded only while the visualizer is active, so a stray
narration in an ordinary sitting writes nothing.
"""
import argparse
import datetime as _dt
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import visualizer_events as ve  # noqa: E402


def cmd_start(a):
    ve.VIS_DIR.mkdir(parents=True, exist_ok=True)
    if ve.EVENTS.exists() and ve.EVENTS.stat().st_size:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(ve.EVENTS), str(ve.VIS_DIR / f"events-{stamp}.jsonl"))
    ve.ACTIVE.write_text(a.title + "\n", encoding="utf-8")
    if ve.SAID.exists():
        ve.SAID.unlink()             # a new sitting shows its own chat text only
    ve._remember(None)
    ve.append({"type": "start", "title": a.title})
    print(f"visualizer active: {ve.EVENTS}")


def cmd_stop(_a):
    if ve.ACTIVE.exists():
        ve.append({"type": "stop"})
        ve.ACTIVE.unlink()
    print("visualizer stopped")


def vault_person(person_id):
    """The vault's own record for an id (display name, generation, dates), or None."""
    if not person_id:
        return None
    try:
        import person_store as ps
        import vault_config as vc
        for r in ps.iter_people(vc.resolve_vault(None)):
            if r.id == person_id:
                return {"name": (r.name or r.id).split(" [", 1)[0].strip(), "gen": r.generation,
                        "born": r.born_phrase or r.born, "died": r.died_phrase or r.died}
    except Exception:
        return None
    return None


def person_event(name=None, pid=None, **given):
    """A person event, with anything the session did not say filled from the vault."""
    rec = vault_person(pid) or {}
    ev = {"type": "person", "name": name or rec.get("name") or pid, "id": pid,
          "gen": given.get("gen") or rec.get("gen"),
          "born": given.get("born") or rec.get("born"),
          "died": given.get("died") or rec.get("died"),
          "place": given.get("place"), "why": given.get("why"), "kin": kinship(pid)}
    return ev


def kinship(person_id):
    """How this person is related to each anchor (Gen 1) and each anchor's parent,
    read from the vault's parent edges.

    Returns a list of dicts, one per anchor or anchor parent the person is related to:

      * kind "ancestor": {id, name, role, steps}. The person is that watcher's
        ancestor, `steps` parent links up (1 = parent).
      * kind "collateral": {id, name, role, up, down, common}. Blood kin who is not
        an ancestor: `up` parent links from the person to the closest shared
        ancestor, `down` from the watcher to the same ancestor, `common` the shared
        ancestor's (or ancestral couple's) display names. The page turns (up, down)
        into sibling / aunt or uncle / niece or nephew / cousin N times removed.
      * kind "spouse": {id, name, role, spouse, rel}. No blood path, but a spouse has
        one; `rel` is that spouse's own entry (an ancestor or collateral dict).

    An empty list means no edge path joins the person to any anchor (a line not yet
    wired). None means the vault could not be read, and the page then makes no
    relationship claim at all.

    WHY FROM EDGES. The first version took a watcher's generation number and
    subtracted. In a couple-anchored vault, and for any one parent of an anchor,
    most of the tree is on somebody else's line: a generation number says how far
    up a person is, never whose ancestor they are. Unconfirmed (`?`) edges are walked
    like confirmed ones, as everywhere else in the session plan.
    """
    if not person_id:
        return None
    try:
        import person_store as ps
        import vault_config as vc
        vault = vc.resolve_vault(None)
        people = {r.id: r for r in ps.iter_people(vault)}
        anchors = [a["id"] for a in (vc.get_anchor(vault) or {}).get("people", [])]
    except Exception:
        return None
    if person_id not in people:
        return None
    return relations(person_id, people, anchors)


def _ids(tokens):
    return [str(p).rstrip("?") for p in (tokens or [])]


def _display(r):
    return (r.name or r.id).split(" [", 1)[0].strip()


def _ancestors(pid, people):
    """{ancestor id: fewest parent links up}, the person itself at 0."""
    dist, frontier = {pid: 0}, [pid]
    while frontier:
        nxt = []
        for n in frontier:
            for p in _ids(people[n].parents) if n in people else []:
                if p in people and p not in dist:
                    dist[p] = dist[n] + 1
                    nxt.append(p)
        frontier = nxt
    return dist


def _blood(person_id, people, watchers):
    up_p = _ancestors(person_id, people)
    out = []
    for w, role in watchers.items():
        if w == person_id:
            continue
        up_w = _ancestors(w, people)
        name = _display(people[w])
        if person_id in up_w:
            out.append({"kind": "ancestor", "id": w, "name": name, "role": role,
                        "steps": up_w[person_id]})
            continue
        shared = set(up_p) & set(up_w)
        if not shared:
            continue
        best = min((up_p[c] + up_w[c], max(up_p[c], up_w[c])) for c in shared)
        closest = sorted(c for c in shared if (up_p[c] + up_w[c], max(up_p[c], up_w[c])) == best)
        a, b = up_p[closest[0]], up_w[closest[0]]
        out.append({"kind": "collateral", "id": w, "name": name, "role": role,
                    "up": a, "down": b,
                    "common": [_display(people[c]) for c in closest[:2]]})
    return out


def relations(person_id, people, anchors):
    """kinship() on an already-read vault: `people` {id: record}, `anchors` [ids]."""
    watchers = {}
    for aid in anchors:
        if aid in people:
            watchers[aid] = "anchor"
            for pid in _ids(people[aid].parents):
                if pid in people:
                    watchers.setdefault(pid, "anchor parent")
    out = _blood(person_id, people, watchers)
    if out:
        return out
    for s in _ids(people[person_id].spouse):
        if s in people:
            for rel in _blood(s, people, watchers):
                out.append({"kind": "spouse", "id": rel["id"], "name": rel["name"],
                            "role": rel["role"], "spouse": _display(people[s]), "rel": rel})
    return out


def emit(ev):
    if not ve.is_active():
        print("visualizer not active; nothing recorded (run: narrate.py start)", file=sys.stderr)
        return
    ve.append({k: v for k, v in ev.items() if v not in (None, "")})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start"); s.add_argument("--title", default="Research sitting")
    sub.add_parser("stop")
    s = sub.add_parser("say"); s.add_argument("text")
    s = sub.add_parser("phase"); s.add_argument("name"); s.add_argument("--lane"); s.add_argument("--detail")
    s = sub.add_parser("person"); s.add_argument("name", nargs="?"); s.add_argument("--id"); s.add_argument("--gen", type=int)
    s.add_argument("--born"); s.add_argument("--died"); s.add_argument("--place"); s.add_argument("--why")
    s = sub.add_parser("evidence"); s.add_argument("record")
    s.add_argument("--verdict", required=True, choices=["counted", "excluded", "candidate"])
    s.add_argument("--why", required=True); s.add_argument("--host")
    s.add_argument("--person", help="vault id of the person this record is evidence FOR; "
                   "switches the page's person card when it differs")
    s = sub.add_parser("negative"); s.add_argument("text"); s.add_argument("--why")
    s = sub.add_parser("finding"); s.add_argument("text")
    s.add_argument("--tier", choices=["strong", "moderate", "speculative"])
    s = sub.add_parser("term"); s.add_argument("term"); s.add_argument("meaning")
    s = sub.add_parser("question"); s.add_argument("label"); s.add_argument("--pos"); s.add_argument("--why")
    s = sub.add_parser("outcome"); s.add_argument("label")
    s.add_argument("--status", required=True,
                   choices=["resolved", "advanced", "blocked", "untouched", "swapped"])
    s.add_argument("--why", required=True)

    a = p.parse_args(argv)
    if a.cmd == "start":
        return cmd_start(a)
    if a.cmd == "stop":
        return cmd_stop(a)
    if a.cmd == "say":
        emit({"type": "say", "text": a.text})
    elif a.cmd == "phase":
        emit({"type": "phase", "name": a.name, "lane": a.lane, "detail": a.detail})
    elif a.cmd == "person":
        if not (a.name or a.id):
            p.error("person needs a name or --id")
        emit(person_event(a.name, a.id, gen=a.gen, born=a.born, died=a.died, place=a.place, why=a.why))
        if a.id and ve.is_active():
            ve._remember(a.id)
    elif a.cmd == "evidence":
        subject = None
        if a.person:
            pe = person_event(pid=a.person)
            subject = {k: v for k, v in pe.items() if k != "type" and v not in (None, "")}
            if ve.is_active():
                ve._remember(a.person)
        emit({"type": "evidence", "record": a.record, "verdict": a.verdict, "why": a.why,
              "subject": subject,
              "host": a.host})
    elif a.cmd == "negative":
        emit({"type": "negative", "text": a.text, "why": a.why})
    elif a.cmd == "finding":
        emit({"type": "finding", "text": a.text, "tier": a.tier})
    elif a.cmd == "question":
        q = ve.question_context(a.label) or {"label": a.label.upper(), "title": "(not found in the register)"}
        emit({"type": "question", **q, "pos": a.pos, "why": a.why})
        if ve.is_active():
            ve._remember(None)       # the page clears the person card for a new question
    elif a.cmd == "outcome":
        q = ve.question_context(a.label) or {}
        emit({"type": "q_outcome", "label": q.get("label", a.label.upper()), "title": q.get("title"),
              "status": a.status, "why": a.why})
    elif a.cmd == "term":
        emit({"type": "term", "term": a.term, "meaning": a.meaning})


if __name__ == "__main__":
    main()
