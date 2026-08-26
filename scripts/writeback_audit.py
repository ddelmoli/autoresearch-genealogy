#!/usr/bin/env python3
"""writeback_audit.py — the FS write-back queue, read through ONE parser.

WHY IT EXISTS (26 AUG 2026). The queue has no file: rule 8 says the flag lives on
the person entry and "a grep is the ledger". That is a deliberate design and it
works — but it left the ITEM unparsed. The SessionStart banner counts marker
TOKENS, nothing reads an item's BODY, and so nothing could say whether an item was
well formed.

⛔⛔ THE COST WAS THREE ANSWERS TO ONE QUESTION. Asked how many queued items lacked
the required evidence clause, three hand-written readers in two sittings said
**7**, **1** and **24**; asked how many were HELD, they said **16** and **27**.
Every one of those numbers went in front of the operator as fact. This module
exists so that the next answer comes from a parser with a name, and can be wrong
in a way somebody can find.

⭐ THE ITEM STARTS AT THE MARKER, NOT AT THE BULLET, and that is the whole reason
the readers disagreed. A well-formed item legitimately sits mid-line, after a
sentence of context, inside a nested sub-bullet — one of the live queue's items
does exactly that, carrying its PID, evidence and life_status correctly. Any reader
anchored on "a line beginning with `- **FS write-back`" silently drops it. The body
then runs to the end of the LOGICAL line: wrapped continuations included, stopping
at a blank line or at the next bullet indented no deeper than the one the item sits on.

THE GRAMMAR (CLAUDE.method.md rule 8), which this checks:

    - **FS write-back QUEUED 31 JUL 2026** (`XXXX-XXX`; promote birth conclusion): FS
      carries year-only 1909; the vault holds 12 OCT 1908 — evidence fs:1:1:XXXX-XXX
      (birth record) — life_status: deceased

  token   `FS write-back` + QUEUED / DONE / DROPPED, then the date. Three states, no
          fourth. Read tolerantly: case-insensitive, `writeback` accepted, a leading
          check mark ignored — the corpus held five spellings when rule 8 was written
          and a case-sensitive counter once undercounted DONE by four.
  paren   `(<PID>; <action>)` — semicolons inside, never commas.
  body    what and why, then `— evidence <host:locator>`, then `— life_status: <v>`.
  HELD    NOT a fourth state: a waiting item stays QUEUED and says
          `— **HELD, do not act yet**`.

WHAT COUNTS (all advisory; this gate blocks nothing and no lane draws this work)
  WB_NO_EVIDENCE     a QUEUED item with no `evidence` clause AT ALL.
                     ⭐ THE POINT: such an item asks a future sitting to redo the
                     research that justified it. ⚠ Presence, not adequacy — see the
                     three legitimate clause forms at EVIDENCE_RE.
  WB_NO_LIFE_STATUS  a QUEUED item not stating life_status — the per-target privacy
                     gate's input (scripts/privacy_gate.py).
  WB_NO_PID          a QUEUED item whose parenthetical names no FS PID and does not
                     declare `no PID`. ⚠ A probe-then-CREATE item legitimately has no
                     PID yet and says so; that is a shape, not a missing slot.
  WB_COMMA_SEPARATOR a comma where rule 8 wants a semicolon BETWEEN THE SLOTS. ⛔ Not
                     "a comma anywhere in the parenthetical" — the action text is
                     prose and commas belong in it.

⚠ HELD IS REPORTED, NEVER FLAGGED. A held item is correctly parked, not defective.

⚠ AGE IS REPORTED, NEVER FLAGGED. An old item is not wrong; it is unreviewed, and
FS state may have moved under it. `--stale DAYS` lists the oldest.

USAGE
  python3 scripts/writeback_audit.py                # conformance report
  python3 scripts/writeback_audit.py --stale 21     # queued items older than N days
  python3 scripts/writeback_audit.py --list         # every item, with its slots
  python3 scripts/writeback_audit.py --heartbeat    # one line
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob as _glob
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

STATES = ("QUEUED", "DONE", "DROPPED")
MARKER_RE = re.compile(r"FS\s+write-?back\s+(QUEUED|DONE|DROPPED)\s*\**\s*"
                       r"(\d{1,2}\s+[A-Z]{3,}\s+\d{4})?", re.I)
PAREN_RE = re.compile(r"\(([^)]*)\)")
PID_RE = re.compile(r"\b([0-9A-Z]{4}-[0-9A-Z]{3})\b")
# ⭐⭐ THE EVIDENCE TEST IS THE PRESENCE OF THE CLAUSE, NOT THE SHAPE OF ITS CONTENT.
# A first version demanded an un-negated `host:locator` and reported 63 of 101 items
# defective. Reading the flagged rows killed it: the clause legitimately takes THREE
# forms, and two of them that version scored as absent.
#   (a) a plain locator            — the ordinary case
#   (b) a `~`-NEGATED locator      — CORRECT for a DETACH item: what a detach cites is
#                                    the record being detached, which is negated on the
#                                    entry precisely because it is not evidence for
#                                    this person. Demanding an un-negated locator makes
#                                    the best-formed detach items look like the worst.
#   (c) PROSE naming a record or authority — required where a locator cannot be used:
#                                    `~` suppresses a token across the WHOLE entry, so
#                                    an item re-citing the entry's own record must name
#                                    it in words or destroy that citation (rule 8).
# Whether a clause's content is ADEQUATE is a judgement no regex makes. This asks only
# whether the item cites its reasons at all; `--evidence-forms` prints the breakdown.
EVIDENCE_RE = re.compile(r"\bevidence\b", re.I)
LOCATOR_RE = re.compile(r"(?<![~\w])([a-z][a-z0-9_]{1,20}:[^\s,;)]+)")
NEG_LOCATOR_RE = re.compile(r"~([a-z][a-z0-9_]{1,20}:[^\s,;)]+)")
LIFE_STATUS_RE = re.compile(r"life_status\s*:\s*(living|deceased|unknown)", re.I)
HELD_RE = re.compile(r"\bHELD\b", re.I)
# ⚠ Rule 8's "semicolons inside, never commas" governs the SLOT SEPARATOR — what
# divides the PID from the action — not commas in the action's prose. A first version
# flagged any comma anywhere in the parenthetical and reported 27 findings; reading
# them, every one was ordinary English inside a correctly semicolon-separated action
# ("triage two duplicated children — compare, do NOT merge"). Test the separator.
SEPARATOR_RE = re.compile(r"^\s*[`'\"]?(?:[0-9A-Z]{4}-[0-9A-Z]{3}|no\s+PID)[`'\"]?\s*([;,])", re.I)
# An item that will CREATE a person has no PID yet and says so. That is a legitimate
# shape, not a missing slot: the probe-then-create item at Berkshire is the live example.
NO_PID_DECLARED_RE = re.compile(r"\bno\s+PID\b", re.I)
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def _parse_date(text):
    if not text:
        return None
    m = re.match(r"(\d{1,2})\s+([A-Z]{3})[A-Z]*\s+(\d{4})", text.strip(), re.I)
    if not m:
        return None
    mon = MONTHS.get(m.group(2).upper())
    if not mon:
        return None
    try:
        return _dt.date(int(m.group(3)), mon, int(m.group(1)))
    except ValueError:
        return None


def _body(lines, idx, start_col):
    """The item's text: from the marker to the end of its LOGICAL line.

    Continuations are wrapped prose. The body stops at a blank line, or at a bullet
    whose indent is no deeper than the indent of the line the item sits on — so a
    nested sub-bullet UNDER the item is kept, and the next sibling item is not.
    """
    first = lines[idx]
    indent = len(first) - len(first.lstrip())
    out = [first[start_col:]]
    j = idx + 1
    while j < len(lines):
        nxt = lines[j]
        if not nxt.strip():
            break
        nind = len(nxt) - len(nxt.lstrip())
        if re.match(r"^\s*[-*]\s", nxt) and nind <= indent:
            break
        if MARKER_RE.search(nxt):
            break
        out.append(nxt)
        j += 1
    return "\n".join(out)


def scan(vault):
    """Yield one dict per write-back item, from every Family_Tree shard."""
    items = []
    for path in sorted(_glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            for m in MARKER_RE.finditer(line):
                body = _body(lines, i, m.start())
                paren = PAREN_RE.search(body)
                ptext = paren.group(1) if paren else ""
                ev = EVIDENCE_RE.search(body)
                items.append({
                    "file": os.path.basename(path),
                    "line": i + 1,
                    "state": m.group(1).upper(),
                    "date": _parse_date(m.group(2)),
                    "date_text": (m.group(2) or "").strip(),
                    # ⛔ THE PID COMES FROM THE PARENTHETICAL ONLY. A first version
                    # fell back to scanning the item body, and an FS ARK is
                    # PID-SHAPED (`ZZZZ-999`) — so an item with no PID at all
                    # silently adopted its own EVIDENCE locator as its PID and
                    # looked well formed. A fallback that cannot fail is not a
                    # fallback, it is a wrong answer with no error.
                    "pid": (PID_RE.search(ptext).group(1)
                            if PID_RE.search(ptext) else None),
                    "paren": ptext,
                    "held": bool(HELD_RE.search(body)),
                    "evidence": bool(ev),
                    "evidence_form": (
                        None if not ev else
                        "locator" if LOCATOR_RE.search(body[ev.end():ev.end() + 200]) else
                        "negated" if NEG_LOCATOR_RE.search(body[ev.end():ev.end() + 200]) else
                        "prose"),
                    "life_status": (LIFE_STATUS_RE.search(body) or [None])[0],
                    "body": body,
                })
    return items


def findings(items):
    """Grammar findings on QUEUED items only. HELD and AGE are not findings."""
    out = []
    for it in items:
        if it["state"] != "QUEUED":
            continue
        if not it["evidence"]:
            out.append(("WB_NO_EVIDENCE", it))
        if not it["life_status"]:
            out.append(("WB_NO_LIFE_STATUS", it))
        if not it["pid"] and not NO_PID_DECLARED_RE.search(it["paren"]):
            out.append(("WB_NO_PID", it))
        sep = SEPARATOR_RE.match(it["paren"])
        if sep and sep.group(1) == ",":
            out.append(("WB_COMMA_SEPARATOR", it))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--list", action="store_true", help="every item with its slots")
    ap.add_argument("--evidence-forms", action="store_true",
                    help="how QUEUED items cite their evidence: a plain locator, a "
                         "`~`-negated one (the detach shape), or prose. Informational "
                         "— all three are legitimate.")
    ap.add_argument("--stale", type=int, metavar="DAYS",
                    help="list QUEUED items older than DAYS (age is not a defect)")
    ap.add_argument("--today", help="ISO date to age against (default: today)")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    items = scan(vault)
    queued = [i for i in items if i["state"] == "QUEUED"]
    held = [i for i in queued if i["held"]]
    finds = findings(items)
    tally = Counter(k for k, _ in finds)
    today = _dt.date.fromisoformat(a.today) if a.today else _dt.date.today()

    if a.heartbeat:
        n = sum(tally.values())
        print(f"WRITEBACK_GRAMMAR: {n} finding(s) on {len(queued)} QUEUED item(s) "
              f"[advisory] ("
              + ", ".join(f"{k} {tally[k]}" for k in sorted(tally)) + f"; {len(held)} HELD)")
        return 0

    if a.evidence_forms:
        forms = Counter(i["evidence_form"] for i in queued)
        print("=== how QUEUED items cite evidence (all three forms are legitimate) ===")
        print("  locator  a plain host:locator — the ordinary case")
        print("  negated  a `~`-negated locator — CORRECT for a DETACH: the cited")
        print("           record is the one being detached")
        print("  prose    a record or authority named in words — required where `~`")
        print("           would destroy the entry's own citation")
        print("  None     no evidence clause at all — the WB_NO_EVIDENCE finding\n")
        for k in ("locator", "negated", "prose", None):
            print(f"  {str(k):9} {forms.get(k, 0)}")
        return 0

    if a.list:
        for it in items:
            print(f"  {it['file']}:{it['line']} [{it['state']}]"
                  f"{' HELD' if it['held'] else ''} pid={it['pid']} "
                  f"ev={'y' if it['evidence'] else 'n'} "
                  f"ls={'y' if it['life_status'] else 'n'} {it['date_text']}")
        return 0

    if a.stale is not None:
        old = sorted([i for i in queued if i["date"]
                      and (today - i["date"]).days >= a.stale],
                     key=lambda i: i["date"])
        print(f"=== QUEUED items older than {a.stale} days ({len(old)}) ===")
        print("  ⚠ AGE IS NOT A DEFECT. An old item is unreviewed, and FS state may")
        print("  have moved under it — check it is still live before acting.\n")
        for it in old:
            print(f"  {(today - it['date']).days:>4}d  {it['file']}:{it['line']}  "
                  f"{it['pid']}{'  [HELD]' if it['held'] else ''}")
            print(f"        {it['paren'][:96]}")
        return 0

    print("=== FS WRITE-BACK QUEUE — grammar conformance (advisory) ===")
    print(f"  {len(items)} item(s) total: {len(queued)} QUEUED "
          f"({len(held)} of them HELD), "
          f"{sum(1 for i in items if i['state'] == 'DONE')} DONE, "
          f"{sum(1 for i in items if i['state'] == 'DROPPED')} DROPPED.\n")
    for kind in ("WB_NO_EVIDENCE", "WB_NO_LIFE_STATUS", "WB_NO_PID", "WB_COMMA_SEPARATOR"):
        rows = [it for k, it in finds if k == kind]
        print(f"  --- {kind}: {len(rows)} ---")
        for it in rows:
            print(f"      {it['file']}:{it['line']}  {it['pid']}"
                  f"{'  [HELD]' if it['held'] else ''}")
            print(f"          {it['paren'][:92]}")
        if not rows:
            print("      (none)")
    print(f"\nWRITEBACK_GRAMMAR: {sum(tally.values())} finding(s) on "
          f"{len(queued)} QUEUED item(s)  [advisory]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
