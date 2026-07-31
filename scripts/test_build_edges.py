#!/usr/bin/env python3
"""Regression tests for build_edges.validate_edges (deferred_decisions 8 + 16).

Runnable with no test framework: `python3 test_build_edges.py` (exit 0 = pass).

Both checks under test exist because a reader could not see what it was supposed
to police, so EVERY case here carries its negative control -- a gate that reports
0 is only meaningful if the same gate has been shown to report non-zero on a
deliberately broken tree.

  MALFORMED_EDGE_REF (item 8) -- `parents: '[NOT_AN_ID]'` used to report a fully
  green tree: 0 dangling, 0 structural. The extractor regex did not match the
  token, so it was neither dangling nor malformed nor anything. Two live sessions
  came within a hand-grep of shipping edges pointing at nothing.

  GEN_COLLAPSE (item 16) -- a declared pedigree-collapse edge must move OUT of
  PARENT-GEN MISMATCH and into its own line, so the advisory means "unexplained"
  rather than silently mixing known collapse with real generation bugs.
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import vault_config

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


# Two people, wired child -> parent. `{PARENTS}` is the slot each case fills, so a
# case differs from its control by the edge value alone and nothing else.
TREE = """---
type: lineage
created: 2026-07-31
tags: [test]
---

# Test Lineage

### Generation 1

**Child Example** (b. 1900)
- meta: {{id: P-CCCCCC, generation: 1, parents: '{PARENTS}'}}
- Body bullet.

### Generation 2

**Parent Example** (b. {PGEN_BIRTH})
- meta: {{id: P-PPPPPP, generation: {PGEN}}}
- Body bullet.
"""


def build_vault(tmp, parents, pgen=2, collapse=None):
    """Write a two-person narrative vault and return its path."""
    with open(os.path.join(tmp, ".autoresearch.json"), "w", encoding="utf-8") as fh:
        cfg = {"person_model": "narrative"}
        if collapse is not None:
            cfg["known_gen_collapse"] = collapse
        json.dump(cfg, fh)
    with open(os.path.join(tmp, "Family_Tree_Test.md"), "w", encoding="utf-8") as fh:
        fh.write(TREE.format(PARENTS=parents, PGEN=pgen, PGEN_BIRTH=1850))
    return tmp


def run_validate(vault):
    """Point the module globals at `vault` and capture the validator's report.

    build_edges and gen_person_index both resolve VAULT at import time, so a test
    reassigns the globals rather than re-importing."""
    vault_config.load_config.cache_clear()
    import gen_person_index as G
    import build_edges as BE
    G.VAULT = vault
    BE.VAULT = vault
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = BE.validate_edges()
    return buf.getvalue(), rc


def value_of(report, label):
    """Pull the integer a report line ends with, e.g. 'MALFORMED_EDGE_REF ...: 3'."""
    for line in report.splitlines():
        if label in line:
            return int(line.rsplit(":", 1)[1].split()[0])
    raise AssertionError(f"no line matching {label!r} in report:\n{report}")


def main():
    print("build_edges.validate_edges")

    # --- item 8: MALFORMED_EDGE_REF ------------------------------------------
    # Control: a well-formed edge is clean, and stays clean. Without this the
    # tests below could pass on a validator that flags everything.
    with tempfile.TemporaryDirectory() as tmp:
        rep, rc = run_validate(build_vault(tmp, "[P-PPPPPP]"))
        check(value_of(rep, "MALFORMED_EDGE_REF") == 0, "well-formed edge: MALFORMED 0")
        check(value_of(rep, "structural violations") == 0, "well-formed edge: structural 0")
        check(rc == 0, "well-formed edge: exit 0")

    # The exact reproduction from deferred_decisions 8: a token that is not
    # id-shaped at all. Before the fix this was invisible -- not dangling, not
    # anything -- and the whole report stayed green.
    with tempfile.TemporaryDirectory() as tmp:
        rep, rc = run_validate(build_vault(tmp, "[NOT_AN_ID]"))
        check(value_of(rep, "MALFORMED_EDGE_REF") == 1, "NOT_AN_ID: MALFORMED 1")
        check(value_of(rep, "structural violations") == 1, "NOT_AN_ID: counted structural")
        check(rc == 1, "NOT_AN_ID: exit 1")

    # The recurrence from session #104: a placeholder that LOOKS like an id but
    # carries a non-Crockford character. `I` is the one that actually shipped.
    with tempfile.TemporaryDirectory() as tmp:
        rep, _ = run_validate(build_vault(tmp, "[P-MINTW2?]"))
        check(value_of(rep, "MALFORMED_EDGE_REF") == 1, "P-MINTW2 (I not in Crockford): MALFORMED 1")

    # Wrong LENGTH, right charset -- the other half of the grammar. `P-` + 5.
    with tempfile.TemporaryDirectory() as tmp:
        rep, _ = run_validate(build_vault(tmp, "[P-ABC12]"))
        check(value_of(rep, "MALFORMED_EDGE_REF") == 1, "P-ABC12 (5 chars): MALFORMED 1")

    # A malformed token must not be double-counted as dangling as well.
    with tempfile.TemporaryDirectory() as tmp:
        rep, _ = run_validate(build_vault(tmp, "[NOT_AN_ID]"))
        check(value_of(rep, "DANGLING id refs") == 0, "NOT_AN_ID: not also counted DANGLING")

    # A well-formed id that simply is not in the vault stays DANGLING, not
    # malformed -- the two failures are different and must read differently.
    with tempfile.TemporaryDirectory() as tmp:
        rep, _ = run_validate(build_vault(tmp, "[P-ZZZZZZ]"))
        check(value_of(rep, "MALFORMED_EDGE_REF") == 0, "absent-but-valid id: MALFORMED 0")
        check(value_of(rep, "DANGLING id refs") == 1, "absent-but-valid id: DANGLING 1")

    # --- item 16: GEN_COLLAPSE -----------------------------------------------
    # Control: an UNDECLARED mismatch is still reported as a mismatch. This is the
    # test that stops the collapse list becoming a way to silence real bugs.
    with tempfile.TemporaryDirectory() as tmp:
        rep, _ = run_validate(build_vault(tmp, "[P-PPPPPP]", pgen=4))
        check(value_of(rep, "PARENT-GEN MISMATCH") == 1, "undeclared collapse: MISMATCH 1")
        check(value_of(rep, "GEN_COLLAPSE") == 0, "undeclared collapse: GEN_COLLAPSE 0")

    # Declared: the same tree, with the edge named in known_gen_collapse. The row
    # moves; it does not disappear.
    with tempfile.TemporaryDirectory() as tmp:
        declared = [{"child": "P-CCCCCC", "parent": "P-PPPPPP", "note": "reached by two paths"}]
        rep, rc = run_validate(build_vault(tmp, "[P-PPPPPP]", pgen=4, collapse=declared))
        check(value_of(rep, "PARENT-GEN MISMATCH") == 0, "declared collapse: MISMATCH 0")
        check(value_of(rep, "GEN_COLLAPSE") == 1, "declared collapse: GEN_COLLAPSE 1")
        check("reached by two paths" in rep, "declared collapse: note is displayed")
        check(rc == 0, "declared collapse: not a structural violation")

    # A declaration naming a DIFFERENT edge must not launder this one.
    with tempfile.TemporaryDirectory() as tmp:
        declared = [{"child": "P-CCCCCC", "parent": "P-QQQQQQ", "note": "unrelated"}]
        rep, _ = run_validate(build_vault(tmp, "[P-PPPPPP]", pgen=4, collapse=declared))
        check(value_of(rep, "PARENT-GEN MISMATCH") == 1, "mismatched declaration: MISMATCH still 1")
        check(value_of(rep, "GEN_COLLAPSE") == 0, "mismatched declaration: GEN_COLLAPSE 0")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
