#!/usr/bin/env python3
"""Pin the deferred-heading repair: what it rewrites, and what it REFUSES.

WHY THE TOOL EXISTED. `deferred_decisions.md` sat at ~83,500 tokens against a 30,000
threshold with 45 of its 47 items settled, and the archiver drained ZERO of them --
the archiver reads the text after the LAST em-dash as the status slot, and almost no
heading in the file put it there. It looked like a file that needed splitting; it
needed its headings fixed, after which the existing archiver took it to ~17,200.

WHY THE REFUSALS ARE THE SUBSTANCE. This rewrites TITLES of settled operator
decisions. Every case it cannot identify with certainty must come out as a refusal a
human reads, never a guess -- and on the live file 9 of 47 did exactly that, all 9
correctly.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fix_deferred_headings as F  # noqa: E402
import question_block as QB  # noqa: E402

FAILED = []
ST = ["DONE", "RESOLVED", "FULLY RESOLVED", "IMPLEMENTED", "SUPERSEDED",
      "WITHDRAWN", "RULED OUT", "CLOSED"]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(label)


def kind(h):
    return F.classify(h, ST)[0]


def out(h):
    return F.classify(h, ST)[1]


print("STATUS_FIRST — the status moves to the slot and the summary becomes the title:")
h = "## 13. RESOLVED 02 AUG 2026 (session #132) — TEN merges done"
check("classified", kind(h), "status_first")
check("rewritten", out(h), "## 13. TEN merges done — RESOLVED 02 AUG 2026 (session #132)")
check("and it now parses as terminal", QB.matches_terminal(QB.heading_status(out(h)), ST), True)

print("\n⭐ A title containing its OWN em-dash still ends with the status:")
h2 = ("## 51. ✅ **RESOLVED 08 AUG 2026 (option 3)** — THE BANDIT OPTIMISES HIT-RATE "
      "— so the cheap lane crowds out the rest (raised 07 AUG 2026)")
check("terminal after the move", QB.matches_terminal(QB.heading_status(out(h2)), ST), True)
check("the status is the LAST segment, not the first",
      QB.heading_status(out(h2)).startswith("RESOLVED"), True)

print("\nDECORATED — the status is already last, only the decoration comes off:")
h3 = "## 22. HEADER CLEANUP — ✅ **RESOLVED 07 AUG 2026 (session #151)**"
check("classified", kind(h3), "decorated")
check("terminal after the strip", QB.matches_terminal(QB.heading_status(out(h3)), ST), True)
check("⚠ the ORPHANED closing ** goes too", "**" in out(h3), False)
check("nothing else moved", out(h3).startswith("## 22. HEADER CLEANUP —"), True)

print("\n  ...and bold that is genuinely PAIRED inside the slot is left alone:")
h4 = "## 24. A TITLE — RESOLVED 07 AUG 2026 (the **measured** result)"
check("already conforming, untouched", kind(h4), "ok")
check("its paired bold survives", "**measured**" in out(h4), True)

print("\n⛔ REFUSALS — each is a case where a guess would rewrite a settled decision:")
check("MOVED is not an archive status (a policy question, not a rewrite)",
      kind("## 2. MOVED 03 AUG 2026 to [[Open_Questions]] Q130 — FS harvest remnants"),
      "refused")
check("⭐ `FULLY CLOSED` is not `CLOSED` — matches_terminal anchors at the START",
      kind("## 27. FULLY CLOSED 01 AUG 2026 — (a)+(b) RETRACTED"), "refused")
check("a status sandwiched between two em-dashes",
      kind("## 60. THE AUDIT TIER CANNOT SAY SO — ✅ **RESOLVED 09 AUG 2026** — a "
           "confirmed row is re-offered for ever (raised 08 AUG 2026)"), "refused")
check("a placeholder with no status at all",
      kind("## 5. (placeholder — new items appended below as they arise)"), "refused")
check("a genuinely LIVE item is never touched",
      kind("## 62. FS SERVES NON-DOCUMENT ARTIFACTS — \"DNA Connections\" (raised 09 AUG 2026)"),
      "refused")
check("no em-dash to move a status across",
      kind("## 70. RESOLVED 01 JAN 2026 with no separator"), "refused")

print("\n⭐ `FULLY RESOLVED` is tried before `RESOLVED` (longest-first matters):")
h5 = "## 30. FULLY RESOLVED 01 AUG 2026 (session #129) — the scrape gap is closed"
check("classified", kind(h5), "status_first")
check("the whole status travels, not just its tail",
      QB.heading_status(out(h5)).startswith("FULLY RESOLVED"), True)

print()
if FAILED:
    print(f"FAILED ({len(FAILED)}): " + "; ".join(FAILED))
    sys.exit(1)
print("All fix_deferred_headings pins pass.")
