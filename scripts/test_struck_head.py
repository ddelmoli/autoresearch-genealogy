#!/usr/bin/env python3
"""Regression tests for `struck_out_head` — deferred_decisions 59 (a), THE RESIDUE.

Runnable with no test framework: `python3 test_struck_head.py` (exit 0 = pass).

`struck_out_for_pid` (deferred 59 (a), 08 AUG 2026) asks whether THIS pid sits inside a
`~~struck~~` span on the head. That is right for a pid written on the head itself, and
blind to the other half: a roster item whose SUBJECT is struck still pulls in its
sub-bullets, and any pid named THERE keeps crediting. Measured 09 AUG 2026 on the
reference vault: 2 credits / 6 records, off a head reading

    `5. ~~<Name> (1879-1958, FS PID <PID>)~~ -- **REMOVED 04 JUN 2026: ...`

whose removal note names the man's ACTUAL parents, so their two entries were credited
three records each off a block that exists to say he is not this family's.

⛔⛔ THE OBVIOUS RULE — "the head contains `~~`" — IS WRONG, AND THE NEGATIVE CONTROLS
BELOW ARE THE REASON. This vault also strikes a COMPLETED FOLLOW-UP: a real head carries
`(c) ~~FS write-back: ... create the two Gen-5 parents~~ **DONE 17 JUL 2026 ...**`, where
the strike means DONE and the pids it credits are the two parents that write-back
CREATED. A blanket rule silences 3 legitimate credits to suppress 6 bad ones.

**The discriminator is POSITION**: the struck span must OPEN the head's subject. Every
case here carries its control — a suppressor that suppresses everything is
indistinguishable from one that works, and this repo has shipped that mistake before.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as H

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def main():
    print("STRUCK SUBJECT — the head's subject is retracted, so the block credits nobody")
    for head, label in [
        ("5. ~~Example Ancestor (1879-1958, FS PID XXXX-XXX)~~ — **REMOVED 04 JUN 2026: ...**",
         "numbered roster item, struck subject (the live defect)"),
        ("- ~~John Doe (FS ABCD-123)~~ — retracted 01 JAN 2026",
         "plain bullet, struck subject"),
        ("- **~~Jane Roe~~** (FS ABCD-123) — not this family's",
         "bold wrapper around the struck subject"),
        ("3) ~~Someone~~ removed", "paren-style roster number"),
        ("- ⛔ ~~Someone~~ removed", "status decoration before the strike"),
        ("**~~Bold Name~~** (b. 1800)", "bold-name header with no bullet marker"),
        ("+ ~~Another~~ removed", "'+' bullet"),
    ]:
        check(H.struck_out_head(head), label)

    print("\nCONTROLS — a strike LATER in the line is an aside, and must NOT suppress")
    for head, label in [
        ('- **DEATH CORRECTED + GEN-5 PARENTS RESOLVED**: ... (a) ~~the NUMIDENT on YYYY-YYY~~ '
         '**READ 16 JUL 2026 = no payload**; (c) ~~FS write-back: create the two Gen-5 parents~~ '
         '**DONE 17 JUL 2026**',
         "struck FOLLOW-UPS meaning DONE — the 3 legitimate credits this must preserve"),
        ("- **Sources** (Recipe-S harvest 21 JUN 2026; ~~46 sources~~ corrected to 39)",
         "struck COUNT inside a Sources bullet"),
        ("- Married Jane Placeholder (b. 4 JUL 1717; ~~d. 8 NOV 1800~~ corrected to 8 MAR 1800)",
         "struck superseded DATE mid-line"),
        ("5. **Another Ancestor** (b. 1893; Geneteka 1893 #101)",
         "numbered roster item, NOT struck"),
        ("- Children (6): a, b, c", "kin list — a different rule owns this one"),
        ("**Example Person** (b. 1911; FS PID ZZZZ-ZZZ)", "ordinary bold-name header"),
        ("- plain prose with no strike at all", "no strikethrough anywhere"),
        ("", "empty head"),
    ]:
        check(not H.struck_out_head(head), label)

    print("\nSIBLING RULE — struck_out_for_pid stays scoped to the pid, unchanged")
    head = "- ~~Candidate A (FS AAAA-111)~~ rejected; live alternative B (FS BBBB-222)"
    check(H.struck_out_for_pid(head, "AAAA-111"),
          "a pid INSIDE the struck span is struck out for that pid")
    check(not H.struck_out_for_pid(head, "BBBB-222"),
          "a pid OUTSIDE the struck span is not — the entry still asserts it")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
