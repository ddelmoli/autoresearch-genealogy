#!/usr/bin/env python3
"""
test_edge_audit.py — pins deferred 39's RESIDUAL: the 96.8% of edges nothing
re-examines.

deferred 39 routed the GATE findings into the IMPROVE defect pool and deliberately
left this half open. The residual is that an edge is marked once, cleared once, and
never looked at again — and an edge that was NEVER marked is invisible for ever.

THE DESIGN THIS PINS, and the measurement behind it:

  * A uniform sample is THEATRE. 1,171 people carry unmarked edges; at 1-3 rows a
    draw that is 195-585 sittings for ONE pass. So the audit tier is RISK-RANKED
    instead — an unmarked edge on an entry that cites NO records, or is explicitly
    `speculative`, rests on nothing but the vault's own prior belief. That subset
    is 167 (14%), which a small share sweeps in ~17-28 sittings.
  * AUDIT ROWS RANK LAST, always. They carry no evidence of a problem, so they must
    never displace a gate finding or a `?` edge.
  * THE UNCOVERED REMAINDER IS PRINTED. deferred 39's actual complaint was that
    finishing the `?` work reads as "verification is done"; a number that is not on
    screen cannot prevent that.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import session_plan as SP
import vault_config

PASS = FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def main():
    print("=== deferred 39-residual: the unmarked-edge audit tier ===")
    vault = vault_config.resolve_vault()

    rows = SP.lane_defects(vault)
    kinds = [r.get("_defect") for r in rows]
    audit = [r for r in rows if r.get("_defect") == "audit"]
    gate = [r for r in rows if r.get("_defect") == "gate"]
    edge = [r for r in rows if r.get("_defect") == "edge"]

    check(bool(audit), "the audit tier is populated at all (the residual is closed)")

    # ORDERING IS THE SAFETY PROPERTY: a row with no evidence of a problem must
    # never be offered ahead of one with evidence.
    first_audit = kinds.index("audit") if "audit" in kinds else len(kinds)
    last_signal = max([i for i, k in enumerate(kinds) if k in ("gate", "edge")],
                      default=-1)
    check(first_audit > last_signal,
          "AUDIT rows rank strictly BEHIND every gate finding and `?` edge")
    check(all(k == "gate" for k in kinds[:len(gate)]) if gate else True,
          "gate findings still come first")

    # NEGATIVE CONTROL — the tier must be RISK-RANKED, not the whole population.
    # If it ever equals the full unmarked population the ranking has been lost and
    # the lane would be swamped by 1,171 no-signal rows.
    tot, marked, not_offered = SP.edge_audit_coverage(vault)
    check(tot > marked, "coverage: most edge tokens carry no `?` (that is the gap)")
    check(not_offered > 0,
          "NEGATIVE CONTROL: a large low-risk remainder is EXCLUDED, not swept in")
    check(len(audit) < not_offered,
          "NEGATIVE CONTROL: the offered audit set is far smaller than the remainder")

    # Every audit row must say it is NOT a defect -- the word does real work here,
    # because the pool it lives in is called `defects`.
    check(all("AUDIT" in (r.get("why") or "") for r in audit),
          "every audit row is labelled AUDIT in its reason")
    check(all("NOT a known defect" in (r.get("why") or "") for r in audit),
          "every audit row says in words that it is NOT a known defect")

    # And each names WHY it was selected, so the risk prior is auditable.
    check(all(("cites NO records" in (r.get("why") or ""))
              or ("speculative" in (r.get("why") or "")) for r in audit),
          "every audit row names the risk signal that selected it")

    print(f"\n  [measured] {tot} edge tokens, {marked} marked, "
          f"{len(audit)} audit rows offered, {not_offered} people not offered")
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
