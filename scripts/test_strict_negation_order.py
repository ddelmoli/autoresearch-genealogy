#!/usr/bin/env python3
"""Regression tests: `count_records_strict` must resolve negation BEFORE narrowing.

Runnable with no test framework: `python3 test_strict_negation_order.py` (exit 0 = pass).

WHY THIS EXISTS (found 10 AUG 2026, session #159, while working Open_Questions Q229).

`count_records_strict` is `count_records` restricted to the `- **Sources**` bullet, and
it is the counter the deferred-19 flip switches the census to. It used to narrow the
body to that bullet and only then strip `~`-negated locators.

That order throws the negation away, because **the `~` almost never lives inside the
Sources bullet.** It is written where the rejection is explained — a write-back queue
bullet, an audit note, a `Named-in` block — while the bare token stays in the harvest
list. Slicing first discards the mark and keeps the token.

Measured on the reference vault before the fix: **10 entries, 27 records** re-credited,
every one of them a locator the entry rejects in words.

THE DIAGNOSTIC IS `strict > loose`. Strict is a RESTRICTION of loose, so it can never
exceed it. All 10 entries were inversions, and the first case below asserts the
invariant directly rather than a specific number — a count can drift, an invariant
cannot.

EVERY case carries its positive control. A strict counter that returns 0 for everything
would pass a negation test and be useless, so each case also asserts what must STILL
count. That is this repo's standing rule for suppressor tests.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as H

PASS = 0
FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok   {label}  ({got})")
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r}")


# The shape that produced the bug: the `~` is in a write-back bullet, the bare token
# is in the Sources list. This is the shape of the worst real row, reduced.
NEGATED_OUTSIDE_BULLET = """
- **FS write-back QUEUED** (DETACH an attachment that documents another man):
  the census names a DIFFERENT same-name man, not him (`~fs:1:1:XXXX-XXX`).
- **Sources** (harvest, 3 record ARKs):
  - fs:1:1:XXXX-XXX
  - fs:1:1:AAAA-AAA
  - fs:1:1:BBBB-BBB
"""

# Control: nothing negated anywhere. All three must count under both counters.
NOTHING_NEGATED = """
- **Sources** (harvest, 3 record ARKs):
  - fs:1:1:XXXX-XXX
  - fs:1:1:AAAA-AAA
  - fs:1:1:BBBB-BBB
"""

# The `~` written INSIDE the Sources bullet — the case that always worked, kept so a
# future change cannot fix the outside case by breaking the inside one.
NEGATED_INSIDE_BULLET = """
- **Sources** (harvest, 3 record ARKs):
  - ~fs:1:1:XXXX-XXX
  - fs:1:1:AAAA-AAA
  - fs:1:1:BBBB-BBB
"""

# A locator negated outside the bullet and NOT present inside it. Strict counts the
# bullet, so this must not change the strict count at all: guards against a fix that
# over-reaches and starts subtracting things the bullet never claimed.
NEGATED_OUTSIDE_ONLY = """
- **Named-in** (off the metric; documents his son):
  - son's 1946 death — ~fs:1:1:ZZZZ-ZZZ
- **Sources** (harvest, 2 record ARKs):
  - fs:1:1:AAAA-AAA
  - fs:1:1:BBBB-BBB
"""

print("count_records_strict: negation resolves before narrowing")

# 1. THE INVARIANT. strict is a restriction of loose and can never exceed it.
for label, body in [
    ("negated outside bullet", NEGATED_OUTSIDE_BULLET),
    ("nothing negated", NOTHING_NEGATED),
    ("negated inside bullet", NEGATED_INSIDE_BULLET),
    ("negated outside only", NEGATED_OUTSIDE_ONLY),
]:
    loose = H.count_records(body)
    strict = H.count_records_strict(body)
    check(f"strict <= loose [{label}]", strict <= loose, True)

# 2. The bug itself: the token negated in the write-back bullet must not be counted
#    from the Sources list. Two survivors are the positive control.
check("negated-outside token is suppressed",
      H.count_records_strict(NEGATED_OUTSIDE_BULLET), 2)

# 3. Positive control: with nothing negated the same bullet counts all three. Without
#    this, a strict counter that always returned 2 would pass case 2.
check("un-negated bullet still counts all three",
      H.count_records_strict(NOTHING_NEGATED), 3)

# 4. The inside-the-bullet case must keep working.
check("negated-inside token is suppressed",
      H.count_records_strict(NEGATED_INSIDE_BULLET), 2)

# 5. Over-reach guard: negating something the bullet never cited changes nothing.
check("negation of an uncited token does not shrink the bullet",
      H.count_records_strict(NEGATED_OUTSIDE_ONLY), 2)

# 6. The specific tokens: suppression must hit the RIGHT one, not just "one of them".
locs = H.record_locators(
    H.sources_bullet_text(H.strip_negated_locators(NEGATED_OUTSIDE_BULLET)))
joined = " ".join(locs).lower()
check("the rejected token is gone", "xxxx-xxx" in joined, False)
check("the innocent token survives", "aaaa-aaa" in joined, True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
