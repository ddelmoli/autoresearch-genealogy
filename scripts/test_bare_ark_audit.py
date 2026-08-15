#!/usr/bin/env python3
"""Pin the MIGRATE-OR-NEGATE gate (Open_Questions Q211, operator decision 14 AUG 2026).

⚠ BOTH FIXES MUST CLEAR THE GATE, and that is the whole design. The rule is "migrate
OR negate", because ~91% of the bare-token population is ordinary evidence nobody ever
migrated -- a gate that only accepted `~` would push a session toward destroying 519
real citations, which is the mirror of the defect it exists to catch.

⛔ AND AN FS PID MUST NEVER BE FLAGGED. `extract_arks()` requires the `1:1:`/`3:1:`
form, so a children list naming `ABCD-123` contributes nothing; a gate that flagged
PIDs would fire on every roster line in the vault and be switched off within a day.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bare_ark_audit as B

CASES = [
    # (label, line, expected tokens)
    ("bare ARK in refuting prose -- THE DEFECT",
     "- the prior name was WRONG: it derived from the 1857 marriage (ARK 1:1:XXXX-YYYY, "
     "which lists another woman)", ["XXXX-YYYY"]),
    ("bare ARK in an ordinary citation -- also a finding, fix by MIGRATING",
     "- Source: [Region], Civil Registration Marriage 1857 (FamilySearch ARK 1:1:XXXX-YYYY)",
     ["XXXX-YYYY"]),
    ("FIX A -- migrated to the host form",
     "- 1857 marriage, [Place] — fs:1:1:XXXX-YYYY", []),
    ("FIX B -- negated because the prose refutes it",
     "- the prior name was WRONG: (ARK ~1:1:XXXX-YYYY, which lists another woman)", []),
    ("negation written on the host form, token also host-prefixed",
     "- superseded — ~fs:1:1:XXXX-YYYY", []),
    ("an FS PID is NOT an ARK and must never be flagged",
     "- Children: [Child A] (b. 1856; ABCD-123); [Child B]; EFGH-4JK", []),
    ("a bare 3:1: image token",
     "- his birth atto, FS image 3:1:3QSQ-Q9QQ-QQQQ-Q, names other parents",
     ["3QSQ-Q9QQ-QQQQ-Q"]),
    ("prose naming the locator FORM, not a locator",
     "- browse-only registers attach as image ARKs rather than indexed ones", []),
]


def main():
    bad = []
    for label, line, want in CASES:
        got = B.bare_tokens(line)
        if got != want:
            bad.append(f"{label}\n        line: {line[:88]}\n        want {want}, got {got}")

    # the blockquote skip lives in audit(), not bare_tokens() -- pin it there
    import pathlib, tempfile
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "Family_Tree_Test.md"
        p.write_text(
            "- a real finding (ARK 1:1:AAAA-BBB)\n"
            "> - a route_digest MIRROR of the same line (ARK 1:1:AAAA-BBB)\n",
            encoding="utf-8")
        found = B.audit(pathlib.Path(d))
        n = sum(len(t) for _, _, t, _ in found)
        if n != 1:
            bad.append(f"blockquote handling: expected 1 finding (the mirror must be "
                       f"skipped), got {n}")

    if bad:
        print("BARE_ARK test FAILED:")
        for b in bad:
            print("   ", b)
        return 1
    print(f"BARE_ARK test ok ({len(CASES)} cases: the defect, both accepted fixes, "
          f"PID negative control, blockquote mirror skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
