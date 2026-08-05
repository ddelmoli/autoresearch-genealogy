#!/usr/bin/env python3
"""Regression tests for `own_region` — the entry's own person is credited its OWN
text, not the whole body (deferred_decisions 49).

Runnable with no test framework: `python3 test_own_region.py` (exit 0 = pass).

THE DEFECT. `attributed_region_for_pid` (deferred 29) scoped a FOREIGN pid's credit
to the region documenting it, but the entry's OWN person kept being credited
`count_records(body)` — the whole body. So the sanctioned inline-collateral
convention inflated its HOST: an entry carrying
`- **FS-attached sources for son <Name>** (<PID>, inline collateral): <21 locators>`
read as 26 records against 6 real ones. 66 entries, 317 phantom records.

⚠ THE NEGATIVE CONTROL IS THE POINT OF THIS FILE. The obvious implementation —
"drop any region whose line names a pid and carries locators" — is WRONG, and
wrong in a way that looks like a much bigger win. `PID_RE` matches the 4-3/4-4
shape, which is ALSO the shape of an ARK suffix, so a bare `- fs:1:1:WWWW-111`
sub-bullet scans as a line naming a pid. A first measurement written that way
reported 545 entries / 5,096 records, because it was deleting entries' own
Sources bullets: one entry's own 24 locators became "24 foreign pids" and it
reported 0 records of its own. The 5,096 figure measured the measuring script.

`own_region` therefore excludes a region ONLY when the pid RESOLVES in `pid_to_id`.
An ARK suffix owns no entry, so the collision is defeated by construction. Every
case below that drops something is paired with a case that must NOT drop.
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


def records(body, owners=(), roster=None):
    """Records credited to the entry's OWN person."""
    return H.count_records(H.own_region(body, set(owners), roster or {}))


def main():
    # ---------------------------------------------------------------- the defect
    print("the defect: an inline-collateral bullet must not credit its HOST")
    body = "\n".join([
        "- meta: {id: P-AAAAAA, fs: AAAA-111}",
        "- **Sources** (his own):",
        "  - his 1879 death act — fs:3:1:AAAA-BBBB",
        "- **FS-attached sources for son Ferdinando** (BBBB-222, inline collateral):",
        "  - fs:1:1:CCCC-DDD",
        "  - fs:1:1:EEEE-FFF",
        "  - fs:1:1:GGGG-HHH",
    ])
    roster = {"BBBB-222": "P-SONSON"}
    check(records(body, {"AAAA-111"}, roster) == 1,
          "host credited only his OWN 1 record, not the son's 3")
    # positive control: the son still gets them, via step (2)
    region = H.attributed_region_for_pid(body, "BBBB-222")
    check(H.count_records(region) == 3,
          "positive control — the SON is still credited all 3 (step 2 unchanged)")

    # ------------------------------------------------- THE ARK-SUFFIX COLLISION
    print("\nNEGATIVE CONTROL — an ARK suffix must never be read as a foreign pid")
    own_only = "\n".join([
        "- meta: {id: P-BBBBBB, fs: CCCC-333}",
        "- **Sources** (Recipe-S harvest, 4 record ARKs):",
        "  - fs:1:1:WWWW-111",
        "  - fs:1:1:YYYY-222",
        "  - fs:1:1:QQQQ-333",
        "  - fs:1:1:RRRR-444",
    ])
    # WWWW-111 etc. all match PID_RE. With an empty roster none resolves, so none
    # may be treated as foreign. This is the case that produced the bogus 5,096.
    check(records(own_only, {"CCCC-333"}, {}) == 4,
          "entry keeps all 4 of its OWN bare locators (roster empty)")
    check(records(own_only, {"CCCC-333"}, {"BBBB-222": "P-SONSON"}) == 4,
          "still 4 when the roster holds an UNRELATED pid")
    # and the collision is real, not hypothetical — assert PID_RE does match them
    check("WWWW-111" in set(H.PID_RE.findall(own_only)),
          "the collision is real: PID_RE does match the ARK suffix WWWW-111")

    # -------------------------------------------------------- cross-references
    print("\na cross-reference carries no locators, so it drops nothing (Spec 05)")
    xref = "\n".join([
        "- meta: {id: P-CCCCCC, fs: AAAA-111}",
        "- Children (3, with FS PIDs): Anna BBBB-222; Jan CCCC-333",
        "- **Sources**:",
        "  - fs:1:1:XXXX-YYY",
        "  - fs:1:1:ZZZZ-WWW",
    ])
    check(records(xref, {"AAAA-111"}, {"BBBB-222": "P-1", "CCCC-333": "P-2"}) == 2,
          "children named in a list do not remove the entry's own 2 records")

    # ------------------------------------------------------------- own pid line
    print("\nthe entry's OWN pid never triggers a drop")
    ownline = "\n".join([
        "- meta: {id: P-DDDDDD, fs: AAAA-111}",
        "- **Sources** for AAAA-111:",
        "  - fs:1:1:XXXX-YYY",
    ])
    check(records(ownline, {"AAAA-111"}, {"AAAA-111": "P-DDDDDD"}) == 1,
          "own pid on a locator-bearing line keeps its record")

    # --------------------------------------------------------- nested / overlap
    print("\noverlapping regions are subtracted once, not repeatedly")
    nested = "\n".join([
        "- meta: {id: P-EEEEEE, fs: AAAA-111}",
        "- **Sources for wife BBBB-222 and son BBBB-222** (inline collateral):",
        "  - fs:1:1:XXXX-YYY",
        "- **Sources** (his own):",
        "  - fs:1:1:ZZZZ-WWW",
    ])
    check(records(nested, {"AAAA-111"}, {"BBBB-222": "P-WIFE"}) == 1,
          "a pid named twice on one line drops that region once; own record survives")

    # ------------------------------------------------------- scholarly scoping
    print("\nscholarly apparatus is scoped the same way as records")
    schol = "\n".join([
        "- meta: {id: P-FFFFFF, fs: AAAA-111}",
        "- **Sources for son BBBB-222** (inline collateral):",
        "  - Cawley, FMG Medlands ENGLAND — fs:1:1:XXXX-YYY",
    ])
    own = H.own_region(schol, {"AAAA-111"}, {"BBBB-222": "P-SON"})
    check(not H.has_scholarly_citation(own),
          "a Cawley cite inside the SON's bullet does not make the host BOOK_SOURCED")
    # positive control — the host's own Cawley cite still counts
    schol_own = schol + "\n- Cawley, FMG Medlands ENGLAND, for this man himself"
    own2 = H.own_region(schol_own, {"AAAA-111"}, {"BBBB-222": "P-SON"})
    check(H.has_scholarly_citation(own2),
          "positive control — the host's OWN Cawley cite still counts")

    # ------------------------------------------------------------- host scoping
    print("\nper-host locators are scoped too (MULTI_SOURCED must stay honest)")
    hosts = "\n".join([
        "- meta: {id: P-GGGGGG, fs: AAAA-111}",
        "- **Sources for son BBBB-222** (inline collateral):",
        "  - anc:1234:5678",
        "- **Sources** (his own):",
        "  - fs:1:1:XXXX-YYY",
    ])
    ph = H.per_host_locators(H.own_region(hosts, {"AAAA-111"}, {"BBBB-222": "P-SON"}))
    check("anc" not in ph,
          "the son's Ancestry locator does not make the host MULTI_SOURCED")
    # NB the map keys on the REGISTRY key (`familysearch`), not the emitted short
    # name (`fs`) — only emission applies `short`. Asserting "fs" here failed once
    # and the test was the thing that was wrong, not the scoping.
    check(ph.get("familysearch", 0) == 1,
          "positive control — the host keeps his own familysearch locator")

    # ------------------------------------------------------ a body with nothing
    print("\ndegenerate cases")
    check(records("", (), {}) == 0, "empty body → 0")
    check(records("- meta: {id: P-HHHHHH}", (), {}) == 0, "meta only → 0")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
