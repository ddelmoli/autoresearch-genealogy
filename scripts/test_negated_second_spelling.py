#!/usr/bin/env python3
"""Regression tests for deferred_decisions 63 — ONE RECORD, TWO SPELLINGS.

Runnable with no test framework: `python3 test_negated_second_spelling.py` (exit 0 = pass).

`~` suppresses the SPAN it prefixes. A locator routinely appears TWICE, and the second
spelling kept counting — so an entry could state in terms that a record is excluded while
the census counted it. A token negated ANYWHERE in the text under examination is now
negated everywhere in it.

⛔ THIS IS NOT WHAT THE ITEM DIAGNOSED, and re-measuring before fixing is the only reason
that was caught. Deferred 63 blamed the host registry's `url_pattern`, on the theory that
a bare link counts as a locator. **It does not — `url_pattern` has no consumer in the
counting path at all**, so the proposed "derive a URL branch from url_pattern" fix would
have changed nothing. What makes a URL count is the locator token embedded in its path.
The effect was real; the mechanism was wrong.

THE FOUR LIVE SHAPES, each a different reason a second spelling exists:
  (a) an ARCHIVE URL beside the id — the URL path ENDS in the filename that is the
      locator, so the route re-credits the record;
  (b) the FS WRITE-BACK GRAMMAR'S OWN `— evidence <locator>` slot, which restated three
      locators the same bullet had just negated — two documented conventions in conflict;
  (c) NARRATIVE ORDER — "The record (`fs:1:1:X`) reads: …" and, later, "Not adopted, not
      counted: `~fs:1:1:X`". The verdict came last and lost;
  (d) CROSS-LINE — an exclusion bullet ("these are his CHILDREN's births, limb (g)")
      negates the ids, while the entry's big harvest bullet still lists them unnegated.
      This is the largest shape and the line-level scan that found (a)-(c) was blind to
      it: one entry alone carried EIGHT such tokens.

⚠⚠ THE POSITIVE CONTROLS ARE THE POINT. A suppressor that suppresses everything is
indistinguishable from one that works. A DIFFERENT, unmarked locator on the same line
must still count, and a longer id that merely EXTENDS a negated one must be untouched.
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


def records(text, want, label):
    got = H.count_records(text)
    check(got == want, f"{label} (want {want}, got {got})")


def main():
    print("THE FOUR SHAPES — the second spelling must not resurrect the record")
    records(
        "- act — ~agad:PL_1_300_874_0117.jpg — "
        "<http://agadd2.home.net.pl/metrykalia/300_new/album/874/PL_1_300_874_0117.jpg>",
        0, "(a) archive URL whose path ends in the negated filename")
    records(
        "- DETACH three attachments (~fs:1:1:AAAA-111); (~fs:1:1:BBBB-222); "
        "(~fs:1:1:CCCC-333) — evidence fs:1:1:AAAA-111, fs:1:1:BBBB-222, "
        "fs:1:1:CCCC-333 — life_status: deceased",
        0, "(b) the write-back grammar's own `evidence` slot")
    records(
        "- The record (`fs:1:1:AAAA-111`) reads: ... Not adopted, not counted: "
        "~fs:1:1:AAAA-111.",
        0, "(c) cited early in the sentence, negated at the end")
    records(
        "- **these are his CHILDREN's births**, limb (g) — ~fs:1:1:AAAA-111, "
        "~fs:1:1:BBBB-222\n"
        "- **Sources — his OWN profile** (Recipe-S, 2 record ARKs): "
        "fs:1:1:AAAA-111, fs:1:1:BBBB-222",
        0, "(d) CROSS-LINE: negated in an exclusion bullet, restated in the harvest")

    print("\n⚠ POSITIVE CONTROLS — these must KEEP counting")
    records("- excluded ~fs:1:1:AAAA-111 but the real one is fs:1:1:BBBB-222",
            1, "a DIFFERENT unmarked locator on the same line still counts")
    records("- 1910 census — fs:1:1:AAAA-111, fs:1:1:BBBB-222",
            1, "nothing negated: one line is one RECORD, not two locators")
    records("- ~fs:1:1:AAAA-111 and fs:1:1:AAAA-1119",
            1, "a longer id that merely EXTENDS a negated one is untouched")
    records("- a — ~fs:1:1:AAAA-111\n- b — fs:1:1:BBBB-222",
            1, "cross-line: an unrelated record on another line survives")
    records("- plain prose with a ~tilde and no locator at all",
            0, "no locators anywhere")

    print("\nLOCATOR LEVEL — the surviving set is exactly the unnegated one")
    check(H.record_locators(
        "- excluded ~fs:1:1:AAAA-111 but the real one is fs:1:1:BBBB-222"
    ) == ["fs:1:1:BBBB-222"], "record_locators drops only the negated token")

    print("\nNO RECURSION — the token pass must not re-enter the stripper")
    # `_negated_tokens` once called `extract_arks`, which calls `strip_negated_locators`,
    # which calls `_negated_tokens` … until the stack blew. Pin it.
    try:
        H.strip_negated_locators("~fs:1:1:AAAA-111 and ~agad:PL_1_300_874_0117.jpg")
        check(True, "strip_negated_locators terminates on nested negations")
    except RecursionError:
        check(False, "strip_negated_locators terminates on nested negations")

    print("\nBOUNDARY — the guard must not block the contexts it exists to reach")
    # The first cut excluded `:` and `/` from the lookbehind, which rejected every live
    # case (the token sits after `fs:1:1:` and after a URL's last `/`) while still
    # passing the substring control — a guard that blocked only the intended matches.
    check(H.count_records("- x — ~fs:1:1:AAAA-111 — <http://h.example/p/AAAA-111>") == 0,
          "a token after a URL's final `/` is reached")
    check(H.count_records("- x — ~fs:1:1:ZZZZ-9999 — see ark:/61903/1:1:ZZZZ-9999") == 0,
          "a token after a `1:1:` prefix, in a second locator form, is reached")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
