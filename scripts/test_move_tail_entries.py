#!/usr/bin/env python3
"""Regression tests for move_tail_entries.

Runnable with no test framework: `python3 test_move_tail_entries.py` (exit 0 = pass).

Every refusal here carries its NEGATIVE CONTROL -- the same tree, cut at a legal
boundary, must succeed. A guard that refuses everything is indistinguishable from
a guard that works, and this repo has shipped both.

The two guards, and why each exists:

  ANCHOR MUST BE AN ENTRY BOUNDARY. A tail move splits at a line, so it cannot
  lose an id by construction -- which means the id-set check passes even when the
  cut lands INSIDE an entry, leaving the bold name in the source and its `- meta:`
  block in the dest. One entry with no record, one record with no name, and every
  count balanced. This is the failure the conservation check cannot see, so it is
  checked separately.

  ID SET CONSERVED. Kept even though a line split makes it hard to violate,
  because it is the check that survives future edits to how the tail is chosen --
  and because #121 lost a person to an index splice while every gate stayed green.
  Its negative control drives `conservation()` directly, since the CLI cannot
  produce a dropped id on its own.
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import move_tail_entries as mte

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


SHARD = """---
type: reference
created: 2026-01-01
updated: 2026-01-01
tags: [test]
---

# Test Lineage

### Generation 1

**Ancestor One** (b. 1900)
- meta: {id: P-AAAAAA, generation: 1}
- A body bullet that is NOT an entry boundary.

## Collateral stub entries

**Collateral Two** (b. 1910)
- meta: {id: P-BBBBBB, generation: 2}
- Body.

**Collateral Three** (b. 1920)
- meta: {id: P-CCCCCC, generation: 2}
- Body.
"""

MASTER = """---
type: reference
created: 2026-01-01
tags: [test]
---

# Family Tree

## File Index

| File | Region | Content |
|---|---|---|
| [[Family_Tree_Test]] | Test | the source shard |
"""


def build_vault(tmp):
    v = Path(tmp)
    (v / "Family_Tree_Test.md").write_text(SHARD, encoding="utf-8")
    (v / "Family_Tree.md").write_text(MASTER, encoding="utf-8")
    return v


def run(vault, anchor, apply=False, dest="Family_Tree_Test_Collateral.md"):
    """Drive the CLI against a temp vault.

    AUTORESEARCH_VAULT is set rather than only passing --vault: per the
    multi-vault contract in vault_config.resolve_vault, the ENV VAR OUTRANKS the
    --vault argument. An earlier draft of this test passed --vault alone and
    passed on a clean shell -- then aimed at the operator's real vault the moment
    the suite ran with AUTORESEARCH_VAULT exported, which is how it is normally
    run. Nothing was written (the source shard does not exist there, so the tool
    refused), but the test was only ever one filename away from editing live
    data. Set the env var, and restore it, so the fixture wins unconditionally.
    """
    argv = ["--source", "Family_Tree_Test.md", "--dest", dest,
            "--anchor", anchor, "--title", "T", "--tags", "test",
            "--intro", "> intro", "--stub", "> moved",
            "--region", "Test", "--content", "moved entries",
            "--vault", str(vault)]
    if apply:
        argv.append("--apply")
    prior = os.environ.get("AUTORESEARCH_VAULT")
    os.environ["AUTORESEARCH_VAULT"] = str(vault)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = mte.main(argv)
    finally:
        if prior is None:
            os.environ.pop("AUTORESEARCH_VAULT", None)
        else:
            os.environ["AUTORESEARCH_VAULT"] = prior
    return buf.getvalue(), rc


def main():
    print("move_tail_entries — anchor boundary guard")

    # NEGATIVE CONTROL: cutting at the heading is legal and must work.
    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        out, rc = run(v, "## Collateral stub entries", apply=True)
        dest = (v / "Family_Tree_Test_Collateral.md").read_text()
        src = (v / "Family_Tree_Test.md").read_text()
        check(rc == 0, "heading anchor: accepted")
        check("P-BBBBBB" in dest and "P-CCCCCC" in dest, "heading anchor: both entries moved")
        check("P-AAAAAA" in src, "heading anchor: unmoved entry stays")
        check("P-BBBBBB" not in src, "heading anchor: moved entry is gone from source")
        check("> moved" in src, "heading anchor: pointer stub left behind")
        check("[[Family_Tree_Test_Collateral]]" in (v / "Family_Tree.md").read_text(),
              "heading anchor: File Index row added")

    # NEGATIVE CONTROL: a bold-name header at line start is also legal.
    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        out, rc = run(v, "**Collateral Three**", apply=True)
        dest = (v / "Family_Tree_Test_Collateral.md").read_text()
        check(rc == 0, "bold-name anchor: accepted")
        check("P-CCCCCC" in dest and "P-BBBBBB" not in dest,
              "bold-name anchor: cut is exactly at that entry")

    # THE GUARD: a body bullet is inside an entry. Refused -- and note the id set
    # WOULD have balanced, which is the whole point.
    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        out, rc = run(v, "- meta: {id: P-CCCCCC", apply=True)
        check(rc == 2, "meta-line anchor: refused")
        check("not an entry boundary" in out, "meta-line anchor: says why")
        check(not (v / "Family_Tree_Test_Collateral.md").exists(),
              "meta-line anchor: nothing written")

    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        out, rc = run(v, "- A body bullet", apply=True)
        check(rc == 2, "body-bullet anchor: refused")

    print("move_tail_entries — anchor resolution")

    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        out, rc = run(v, "**No Such Person**", apply=True)
        check(rc == 2 and "matched no line" in out, "absent anchor: refused")

    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        # "**Collateral" prefixes two headers: ambiguity is an error, not a
        # first-match, because the caller is naming ONE cut point.
        out, rc = run(v, "**Collateral", apply=True)
        check(rc == 2 and "matched 2 lines" in out, "ambiguous anchor: refused")

    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        (v / "Already_There.md").write_text("existing\n", encoding="utf-8")
        out, rc = run(v, "## Collateral stub entries", apply=True, dest="Already_There.md")
        check(rc == 2 and "already exists" in out, "existing dest: refused")
        check((v / "Already_There.md").read_text() == "existing\n",
              "existing dest: not overwritten")

    print("move_tail_entries — dry-run is the default")

    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        before = (v / "Family_Tree_Test.md").read_text()
        out, rc = run(v, "## Collateral stub entries", apply=False)
        check(rc == 0, "dry-run: exits clean")
        check(not (v / "Family_Tree_Test_Collateral.md").exists(), "dry-run: no dest written")
        check((v / "Family_Tree_Test.md").read_text() == before, "dry-run: source untouched")

    print("move_tail_entries — the test's own isolation")

    # This test must be pinned to its fixture under BOTH invocations: a bare
    # shell, and the exported-AUTORESEARCH_VAULT shell the suite normally runs
    # in. See run()'s docstring -- the env var outranks --vault, so a test that
    # relies on --vault alone silently retargets.
    with tempfile.TemporaryDirectory() as tmp:
        v = build_vault(tmp)
        prior = os.environ.get("AUTORESEARCH_VAULT")
        os.environ["AUTORESEARCH_VAULT"] = "/nonexistent/other-vault"
        try:
            out, rc = run(v, "## Collateral stub entries", apply=True)
        finally:
            if prior is None:
                os.environ.pop("AUTORESEARCH_VAULT", None)
            else:
                os.environ["AUTORESEARCH_VAULT"] = prior
        check(rc == 0 and (v / "Family_Tree_Test_Collateral.md").exists(),
              "hostile AUTORESEARCH_VAULT: still operates on the fixture")

    print("move_tail_entries — id-set conservation")

    # The CLI cannot drop an id, so the gate is driven directly. Without this the
    # check is only ever observed passing, which proves nothing about whether it
    # can fail.
    original = "- meta: {id: P-AAAAAA}\n- meta: {id: P-BBBBBB}\n"
    ok, lost, gained, dupes = mte.conservation(original, "- meta: {id: P-AAAAAA}\n",
                                               "- meta: {id: P-BBBBBB}\n")
    check(ok and not lost and not gained, "conservation: clean split passes")

    ok, lost, gained, dupes = mte.conservation(original, "- meta: {id: P-AAAAAA}\n", "")
    check(not ok and lost == ["P-BBBBBB"], "conservation: a DROPPED id is caught")

    ok, lost, gained, dupes = mte.conservation(original, original, "- meta: {id: P-BBBBBB}\n")
    check(not ok and dupes == ["P-BBBBBB"], "conservation: a DUPLICATED id is caught")

    ok, lost, gained, dupes = mte.conservation(
        original, original, "- meta: {id: P-ZZZZZZ}\n")
    check(not ok and gained == ["P-ZZZZZZ"], "conservation: an INVENTED id is caught")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
