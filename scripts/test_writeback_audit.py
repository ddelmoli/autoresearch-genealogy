#!/usr/bin/env python3
"""Pin the write-back item parser — every pin here is a number that was once wrong.

⛔⛔ FOUR READERS, FOUR ANSWERS, ONE QUESTION. Asked how many QUEUED items lacked the
required evidence clause, hand-written readers said **7**, then **1**, then **24**,
then this module's first draft said **63**. The true answer is **1**, and that one
item is correctly formed. Every wrong number was reported to the operator as fact,
and the Handoff's pre-drain instruction still tells the next sitting to repair seven
items that do not need repairing.

The three mistakes are pinned below because each is a different KIND of parser error:

  1. ANCHORING ON THE BULLET. A well-formed item legitimately sits mid-line, after a
     sentence of context, inside a nested sub-bullet. Readers keyed on "a line
     starting with `- **FS write-back`" silently drop it.
  2. DEMANDING ONE EVIDENCE SHAPE. The clause takes three legitimate forms, and the
     two that a plain-locator test scores as ABSENT are the interesting ones: a
     `~`-negated locator (what a DETACH cites is the record being detached) and prose
     naming an authority (required where `~` would destroy the entry's own citation).
     Demanding a plain locator made the best-formed detach items look like the worst.
  3. READING A RULE TOO LITERALLY. Rule 8's "semicolons inside, never commas" governs
     the SLOT SEPARATOR. Flagging every comma in the parenthetical reported 27
     findings, all of them ordinary English in a correctly-formed action clause.
"""
import os
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import writeback_audit as WB  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(label)


def scan(body):
    d = tempfile.mkdtemp()
    open(os.path.join(d, "Family_Tree_Scratch.md"), "w", encoding="utf-8").write(body)
    return WB.scan(d)


QUEUED = ("- **FS write-back QUEUED 31 JUL 2026** (`ABCD-123`; correct the birth date): FS "
          "carries 1909, the vault holds 1908 — evidence fs:1:1:ZZZZ-999 (birth record) "
          "— life_status: deceased\n")

print("The ordinary item parses into its slots:")
it = scan(QUEUED)[0]
check("state", it["state"], "QUEUED")
check("date", str(it["date"]), "2026-07-31")
check("pid", it["pid"], "ABCD-123")
check("evidence", it["evidence"], True)
check("life_status", bool(it["life_status"]), True)
check("not held", it["held"], False)

print("\n⛔ MISTAKE 1 — the item starts at the MARKER, not at the bullet:")
midline = ("- **`Some Collection`** ~fs:1:1:AAAA-111 — an English parish record. On its "
           "face a conflation. ⚠ **FS write-back QUEUED 02 AUG 2026** (`WWWW-777`; detach "
           "the parish source): the record cannot be his — evidence fs:1:1:BBBB-222 (his "
           "birth registration) — life_status: deceased\n")
mid = scan(midline)
check("a mid-line marker is still ONE item", len(mid), 1)
check("its PID is read from its own paren", mid[0]["pid"], "WWWW-777")
check("its evidence is found", mid[0]["evidence"], True)
check("its life_status is found", bool(mid[0]["life_status"]), True)

print("\n⛔ MISTAKE 2 — all THREE evidence forms count as citing evidence:")
detach = QUEUED.replace("evidence fs:1:1:ZZZZ-999", "evidence ~fs:1:1:ZZZZ-999")
prose = QUEUED.replace("evidence fs:1:1:ZZZZ-999 (birth record)",
                       "evidence the printed town Vital Records, vol. 1 p. 54")
check("(a) a plain locator", scan(QUEUED)[0]["evidence_form"], "locator")
check("(b) ⭐ a `~`-NEGATED locator — the DETACH shape", scan(detach)[0]["evidence_form"], "negated")
check("(c) prose naming an authority", scan(prose)[0]["evidence_form"], "prose")
for label, text in [("plain", QUEUED), ("negated", detach), ("prose", prose)]:
    check(f"    none of them is WB_NO_EVIDENCE ({label})",
          [k for k, _ in WB.findings(scan(text)) if k == "WB_NO_EVIDENCE"], [])

print("\n  ...and a missing clause IS a finding:")
noev = QUEUED.replace(" — evidence fs:1:1:ZZZZ-999 (birth record)", "")
check("no evidence clause at all", scan(noev)[0]["evidence"], False)
check("flagged", [k for k, _ in WB.findings(scan(noev)) if k == "WB_NO_EVIDENCE"],
      ["WB_NO_EVIDENCE"])

print("\n⛔ MISTAKE 3 — commas in the ACTION are prose; only the SEPARATOR is governed:")
comma_prose = QUEUED.replace("correct the birth date",
                             "triage two duplicated children — compare, do NOT merge")
comma_sep = QUEUED.replace("(`ABCD-123`; correct", "(`ABCD-123`, correct")
check("a comma inside the action is not a finding",
      [k for k, _ in WB.findings(scan(comma_prose)) if k == "WB_COMMA_SEPARATOR"], [])
check("a comma AS THE SEPARATOR is",
      [k for k, _ in WB.findings(scan(comma_sep)) if k == "WB_COMMA_SEPARATOR"],
      ["WB_COMMA_SEPARATOR"])

print("\nA probe-then-CREATE item has no PID yet and says so — a shape, not a defect:")
nopid = ("- **FS write-back QUEUED 10 AUG 2026** (no PID; **EXISTENCE PROBE FIRST, then "
         "create**): he is named on his son's death act — evidence fs:1:1:CCCC-333 "
         "— life_status: deceased\n")
check("declared `no PID` is not flagged",
      [k for k, _ in WB.findings(scan(nopid)) if k == "WB_NO_PID"], [])
undeclared = QUEUED.replace("`ABCD-123`; ", "")
check("but a paren naming neither IS flagged",
      [k for k, _ in WB.findings(scan(undeclared)) if k == "WB_NO_PID"], ["WB_NO_PID"])

print("\nHELD is reported, never flagged (it is correct parking, not a defect):")
held = QUEUED.replace("): FS", "): ⚠ **HELD, do not act yet** — FS")
check("held is detected", scan(held)[0]["held"], True)
check("held is still QUEUED, not a fourth state", scan(held)[0]["state"], "QUEUED")
check("held produces no finding", WB.findings(scan(held)), [])

print("\nThe tolerant token match (five spellings once cost a 4-item undercount):")
for label, variant in [
    ("lowercase", "- **fs write-back queued 31 JUL 2026** (`ABCD-123`; x): y — evidence "
                  "fs:1:1:A-1 — life_status: deceased\n"),
    ("no hyphen", "- **FS writeback QUEUED 31 JUL 2026** (`ABCD-123`; x): y — evidence "
                  "fs:1:1:A-1 — life_status: deceased\n"),
    ("leading check mark", "- ✅ **FS write-back DONE 31 JUL 2026** (`ABCD-123`; x): y\n"),
]:
    got = scan(variant)
    check(f"matched: {label}", len(got), 1)

print("\nAll three states parse, and there is no fourth:")
for state in ("QUEUED", "DONE", "DROPPED"):
    check(state, scan(QUEUED.replace("QUEUED", state))[0]["state"], state)

print("\nTwo sibling items on consecutive lines stay separate:")
two = QUEUED + QUEUED.replace("ABCD-123", "YYYY-888")
got = scan(two)
check("two items", len(got), 2)
check("distinct PIDs", sorted(i["pid"] for i in got), ["ABCD-123", "YYYY-888"])

print()
if FAILED:
    print(f"FAILED ({len(FAILED)}): " + "; ".join(FAILED))
    sys.exit(1)
print("All writeback_audit pins pass.")
