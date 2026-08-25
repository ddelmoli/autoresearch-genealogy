#!/usr/bin/env python3
"""Pin: `bare_ark_audit` must not demand a host prefix for an id that ALREADY HAS ONE.

The gate reports the ids the legacy counter credits that the Spec 03 counter does not.
It used to compare on `locator.split(":")[-1]`, which assumes the `host:ns:id` shape.
An ARK-style locator carries its own colons and slashes, so its last colon-segment is
the whole path and never equals the legacy id extracted from the same token -- and the
gate then demanded a host prefix for a correctly-migrated locator. There is no way to
satisfy that without corrupting the locator, and because the gate BLOCKS on changed
lines it made such a line uncommittable the moment anything touched it.

⚠ The second test is the one that matters: containment must be DELIMITED. A bare `in`
test would let a short id be swallowed by an unrelated locator on the same line and
hide a real bare token -- the exact failure this gate exists to catch.

All ids below are fabricated.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bare_ark_audit import bare_tokens

FAILURES = []


def check(label, line, want):
    got = bare_tokens(line)
    if got != want:
        FAILURES.append(f"{label}: got {got}, want {want}")
    print(f"  {'ok  ' if got == want else 'FAIL'} {label}")


def main():
    # 1. The regression: an ARK-path locator is already migrated. Report nothing.
    check("ARK-path locator is not bare",
          "her death act (`antenati:ark:/12657/an_ua00000000/aa0bCcd` -- Morti 1900)",
          [])

    # 2. The control that keeps the gate honest: a genuine bare token on the SAME
    #    line as an ARK-path locator is still reported.
    check("bare token beside an ARK-path locator is still caught",
          "(`antenati:ark:/12657/an_ua00000000/aa0bCcd`) and a stray 1:1:ABCD-EFGH",
          ["ABCD-EFGH"])

    # 3. Ordinary shapes are unchanged.
    check("plain bare token", "the FS index (ARK 1:1:ABCD-EFGH)", ["ABCD-EFGH"])
    check("host-prefixed token", "cited as fs:1:1:ABCD-EFGH", [])
    check("negated token", "seen and dismissed ~1:1:ABCD-EFGH", [])

    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print("  -", f)
        sys.exit(1)
    print("\nall pinned cases pass")


if __name__ == "__main__":
    main()
