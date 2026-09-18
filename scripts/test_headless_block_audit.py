#!/usr/bin/env python3
"""Regression tests for headless_block_audit.py (HEADLESS_BLOCK).

Runnable with no test framework: `python3 scripts/test_headless_block_audit.py`
(exit 0 = pass).

The defect: a person's body bullets separated from their header by a blank line (a
shard split that moved the header and meta but not the body, or a minting pass that
wrote the body below a blank line). A blank line is not a break, so the parser folds
the block into the PRECEDING entry, `Sources` bullet and all, and no other gate sees
it because the Markdown genuinely says the block belongs there.

Fixture names only. Every positive assertion is paired with a control that breaks the
detector at runtime; a test that cannot be made to fail proves nothing.
"""
import json
import os
import shutil
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import headless_block_audit as H

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


HOST = """**Arthur Example** (b. ABT 900; d. 950)
- meta: {id: P-TEST01, generation: 30}
- King of Nowhere.
- **Sources** (scholarly apparatus):
  - A Printed Chronicle, p. 1
"""

# The headless body of another person, minted weeks later, left below a blank line.
MINTED_BLOCK = """
- **MINTED 01 JAN 2026 (session #1, EXPAND lane) to complete her son's row.** A chronicle names her.
- **Sources** (scholarly apparatus):
  - A Printed Chronicle, p. 2
"""

# A block with no lede at all, but its own second Sources bullet.
SECOND_SOURCES_BLOCK = """
- A note about somebody else.
- **Sources**:
  - Another Chronicle, p. 9
"""

NEXT = """
**Bertha Example** (d. 960)
- meta: {id: P-TEST02, generation: 30}
- Queen of Somewhere.
"""


def t_minted_block_is_flagged():
    print("a MINTED block after a blank line is folded into the entry above, and flagged")
    f = H.scan_text(HOST + MINTED_BLOCK + NEXT, "Family_Tree_Fixture.md")
    check(len(f) == 1, "exactly one finding")
    check(f and f[0]["host"] == "Arthur Example", "the host is the entry above")
    check(f and "identity lede" in f[0]["reasons"], "reason: identity lede")
    check(f and "second Sources bullet" in f[0]["reasons"],
          "reason: second Sources bullet (the host already has one)")
    check(f and f[0]["line"] == HOST.count("\n") + 2, "line number points at the block")


def t_second_sources_alone_is_flagged():
    print("a block with no lede but its own Sources bullet under a sourced host is flagged")
    f = H.scan_text(HOST + SECOND_SOURCES_BLOCK + NEXT)
    check(len(f) == 1 and f[0]["reasons"] == ["second Sources bullet"],
          "flagged on the second-Sources mark alone")


def t_legitimate_continuations_are_not_flagged():
    print("legitimate continuations across a blank line are NOT flagged")
    plain = HOST + "\n- A further note on Arthur.\n" + NEXT
    check(H.scan_text(plain) == [], "an ordinary bullet after a blank line")
    double = HOST + "\n\n- Another note on Arthur, after two blank lines.\n" + NEXT
    check(H.scan_text(double) == [], "a double blank line inside an entry")
    # Pins the REMOVED pronoun rule: "She" here is the host herself.
    pronoun = HOST.replace("Arthur", "Alice") + \
        "\n- **She was in a record this entry already cited.** Read off it.\n" + NEXT
    check(H.scan_text(pronoun) == [], "a pronoun-led continuation (the host's own)")
    sub = HOST + "\n- Tracked as an open question.\n\n### A sub-heading inside the entry\n" \
        "\nProse under it.\n" + NEXT
    check(H.scan_text(sub) == [], "a continuation before a sub-heading")
    indented = HOST + "\n  - an indented sub-bullet after a blank line\n" + NEXT
    check(H.scan_text(indented) == [], "an indented sub-bullet is never a new body")


def t_no_host_no_finding():
    print("a block after a structural break has no host to be folded into")
    text = HOST + "\n## An essay section\n" + MINTED_BLOCK + NEXT
    check(H.scan_text(text) == [], "not reported after a `## ` break")


def t_header_after_blank_is_an_entry():
    print("a bold header with its meta after a blank line is a new entry, not a block")
    check(H.scan_text(HOST + NEXT) == [], "two well-formed entries give no finding")


def t_negative_control():
    print("NEGATIVE CONTROL: the detector breaks when its lede pattern is disabled")
    saved = H.IDENTITY_LEDE
    try:
        H.IDENTITY_LEDE = __import__("re").compile(r"(?!x)x")   # never matches
        f = H.scan_text(HOST.replace("- **Sources** (scholarly apparatus):\n"
                                     "  - A Printed Chronicle, p. 1\n", "")
                        + MINTED_BLOCK + NEXT)
        check(f == [], "with the lede disabled and no host Sources, the block goes unseen")
    finally:
        H.IDENTITY_LEDE = saved
    f = H.scan_text(HOST.replace("- **Sources** (scholarly apparatus):\n"
                                 "  - A Printed Chronicle, p. 1\n", "")
                    + MINTED_BLOCK + NEXT)
    check(len(f) == 1 and f[0]["reasons"] == ["identity lede"],
          "restored, the same text is caught by the lede alone")


def t_vault_scope():
    print("audit() reads narrative vaults only")
    for model, expect in (("narrative", 1), ("file", 0)):
        d = tempfile.mkdtemp(prefix="headless-")
        try:
            with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as fh:
                json.dump({"person_model": model}, fh)
            with open(os.path.join(d, "Family_Tree_Fixture.md"), "w", encoding="utf-8") as fh:
                fh.write(HOST + MINTED_BLOCK + NEXT)
            check(len(H.audit(d)) == expect, f"{model} model -> {expect} finding(s)")
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    for t in (t_minted_block_is_flagged, t_second_sources_alone_is_flagged,
              t_legitimate_continuations_are_not_flagged, t_no_host_no_finding,
              t_header_after_blank_is_an_entry, t_negative_control, t_vault_scope):
        t()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
