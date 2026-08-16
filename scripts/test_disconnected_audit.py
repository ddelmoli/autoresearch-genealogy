#!/usr/bin/env python3
"""Pins the behaviour of disconnected_audit.py.

** WHY THIS FILE EXISTS. ** The tool produced a confidently WRONG edge twice
during its own development, in the space of a few minutes:

  1. It proposed re-wiring **Emma Example to Hugh Example** — the edge a
     session had DISPROVED and deliberately detached. A refutation names a
     relationship in order to deny it, and a bare regex cannot tell a denial from
     an assertion.
  2. Fixing the by-name handling then made it match **Joan Example to Thomas
     Example Jr.**, the wrong man, because the tail-trimmer cut "Thomas
     Example the Husbandman" back to "Thomas Example" and threw away the only
     token that separates four contemporary men of that name.

Both failures are the SAME failure the vault keeps meeting in the wild, and both
were silent — the output looked more useful after each regression, not less.
That is exactly the "flattering direction" this vault treats as a warning sign,
so the behaviours are pinned rather than trusted.

Run: python3 scripts/test_disconnected_audit.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disconnected_audit as D  # noqa: E402

FAILED = []


def check(desc, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    if not ok:
        print(f"       got {got!r}, want {want!r}")
        FAILED.append(desc)


def build(entries):
    """entries: [(id, name, meta_extra, [body lines])] -> (records, inbound)."""
    records, inbound = {}, __import__("collections").Counter()
    for pid, name, extra, body in entries:
        edges = set(D.ID_RE.findall(extra)) - {pid}
        records[pid] = {"id": pid, "name": name, "file": "T.md", "body": list(body),
                        "gen": None, "has_parents": "parents:" in extra,
                        "has_spouse": "spouse:" in extra, "living": False,
                        "edges": edges}
        for e in edges:
            inbound[e] += 1
    return records, inbound


def run(entries):
    records, _ = build(entries)
    owners = {}
    for pid, r in records.items():
        k = D.norm_name(r["name"])
        if k:
            owners.setdefault(k, []).append(pid)
    by_name = {k: v[0] for k, v in owners.items() if len(v) == 1}
    ambiguous = {k for k, v in owners.items() if len(v) > 1}
    return D.find_candidates(records, by_name, ambiguous)


print("A REFUTED relationship is never proposed as a wiring:")
out, _dropped, refuted = run([
    ("P-AAAAAA", "Emma Example", "", [
        "- ⚠ **DISPROVED 27 JUL 2026. SHE IS NOT THE MOTHER OF Hugh Example.**",
    ]),
    ("P-BBBBBB", "Hugh Example", "", []),
])
check("refuted line yields no candidate", len(out), 0)
check("and is counted as suppressed", refuted, 1)

print("\nAn ASSERTED relationship on a clean line IS proposed:")
out, _d, _r = run([
    ("P-AAAAAA", "Joan Example", "", ["- Mother of Thomas Example the Husbandman"]),
    ("P-BBBBBB", "Thomas Example [the Husbandman]", "", []),
])
check("clean line yields one candidate", len(out), 1)
check("and points at the right person", out[0][2]["id"] if out else None, "P-BBBBBB")

print("\nThe BY-NAME is a discriminator, not noise (the regression that shipped a wrong man):")
out, _d, _r = run([
    ("P-AAAAAA", "Joan Example", "", ["- Mother of Thomas Example the Husbandman"]),
    ("P-BBBBBB", "Thomas Example [the Husbandman]", "", []),
    ("P-CCCCCC", "Thomas Example Jr.", "", []),
])
check("two same-surname men present, still exactly one candidate", len(out), 1)
check("⛔ and it is the HUSBANDMAN, not Jr.", out[0][2]["id"] if out else None, "P-BBBBBB")

print("\nAn AMBIGUOUS bare name is dropped, never guessed between:")
out, dropped, _r = run([
    ("P-AAAAAA", "Someone Else", "", ["- Mother of Thomas Example"]),
    ("P-BBBBBB", "Thomas Example", "", []),
    ("P-CCCCCC", "Thomas Example", "", []),
])
check("no candidate emitted", len(out), 0)
check("and the drop is counted", dropped, 1)

print("\nA single-token name is never matched at all:")
out, _d, _r = run([
    ("P-AAAAAA", "Josiah Example", "", ["- Married Mary"]),
    ("P-BBBBBB", "Mary", "", []),
])
check("bare forename yields nothing", len(out), 0)

print("\nAn ALREADY-WIRED pair is not re-reported, in either direction:")
out, _d, _r = run([
    ("P-AAAAAA", "Joan Example", "", ["- Mother of Thomas Example [the Husbandman]"]),
    ("P-BBBBBB", "Thomas Example [the Husbandman]", "parents: '[P-AAAAAA?]'", []),
])
check("edge on the FAR end suppresses the finding", len(out), 0)

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    sys.exit(1)
print("all disconnected-audit checks passed")
