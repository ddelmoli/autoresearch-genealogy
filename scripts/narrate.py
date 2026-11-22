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
  narrate.py person "Jane Example" --id P-XXXXXX [--gen 7] [--born 1801] [--died 1870]
                    [--place "Somewhereton"] [--why "why this person was drawn"]
  narrate.py evidence "1850 census, Somewhereton" --verdict counted|excluded|candidate
                    --why "names her with husband and three children" [--host fs]
  narrate.py negative "Searched the town vital records 1790-1810" [--why "..."]
  narrate.py finding "Her father is named in the 1805 deed" [--tier strong|moderate|speculative]
  narrate.py term "ARK" "a permanent link to one record on FamilySearch"

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
    ve.append({"type": "start", "title": a.title})
    print(f"visualizer active: {ve.EVENTS}")


def cmd_stop(_a):
    if ve.ACTIVE.exists():
        ve.append({"type": "stop"})
        ve.ACTIVE.unlink()
    print("visualizer stopped")


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
    s = sub.add_parser("person"); s.add_argument("name"); s.add_argument("--id"); s.add_argument("--gen", type=int)
    s.add_argument("--born"); s.add_argument("--died"); s.add_argument("--place"); s.add_argument("--why")
    s = sub.add_parser("evidence"); s.add_argument("record")
    s.add_argument("--verdict", required=True, choices=["counted", "excluded", "candidate"])
    s.add_argument("--why", required=True); s.add_argument("--host")
    s = sub.add_parser("negative"); s.add_argument("text"); s.add_argument("--why")
    s = sub.add_parser("finding"); s.add_argument("text")
    s.add_argument("--tier", choices=["strong", "moderate", "speculative"])
    s = sub.add_parser("term"); s.add_argument("term"); s.add_argument("meaning")

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
        emit({"type": "person", "name": a.name, "id": a.id, "gen": a.gen, "born": a.born,
              "died": a.died, "place": a.place, "why": a.why})
    elif a.cmd == "evidence":
        emit({"type": "evidence", "record": a.record, "verdict": a.verdict, "why": a.why,
              "host": a.host})
    elif a.cmd == "negative":
        emit({"type": "negative", "text": a.text, "why": a.why})
    elif a.cmd == "finding":
        emit({"type": "finding", "text": a.text, "tier": a.tier})
    elif a.cmd == "term":
        emit({"type": "term", "term": a.term, "meaning": a.meaning})


if __name__ == "__main__":
    main()
