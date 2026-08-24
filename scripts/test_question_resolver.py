#!/usr/bin/env python3
"""Pin the resolver grammar (question_block.RESOLVER_RE) and its two consumers.

A question that does not name what would settle it is a complaint, not a
research task -- so `question_audit` reports RESOLVERLESS and the register is
supposed to burn it down. Until 24 AUG 2026 it could not be: the check knew four
phrasings (`what would settle it`, `what is left`, `what would name`, the
next-step marker) and the register writes at least eleven. It reported 30 of 163
live questions resolverless; reading all 30 found a named resolver in every one.

TWO defects, one cause, both pinned here:

  * THE DETECTOR WAS ASSERTING WHAT ITS OWN SIBLING DISCLAIMED. The identical
    regex lived twice. In `gen_question_index._resolver` its docstring said a
    miss "is NOT a claim that the question names no resolver -- open the
    question"; `question_audit` copied the regex and named the finding
    RESOLVERLESS. Same screen, opposite epistemics. It now has ONE home and the
    caveat travels with it.
  * THE ROWS WERE UNINSPECTABLE. `--list` documents itself as "print advisory
    rows too" and printed AMBIGUOUS_HEAD and BIG_BLOCK but never RESOLVERLESS --
    collected, counted, never shown. The largest advisory population in the
    register could be counted and not read, which is how 30 false positives sat
    for months. `test_list_prints_resolverless` is the regression pin.

⚠ THE NEGATIVE CONTROLS ARE THE POINT OF THIS FILE. The seven questions still
flagged after the widening name their resolvers with ordinary verbs -- "requires
the 1846 birth register", "needs the full-resolution image". Adding `requires|
needs` would take the count to ~0 and take the finding's meaning with it: those
verbs appear in questions that name nothing. The residual is meant to be read
and LABELLED in the question, never regexed away, and MUST_NOT_MATCH pins that
the widening stopped where the evidence stopped.

⚠ ALL FIXTURES BELOW ARE SYNTHETIC. This file is in the PUBLIC framework repo,
which carries zero real family names (CONTRIBUTING.md, "the framework/private
boundary"); the strings mirror the SHAPE of the measured lines, not the people.
"""
import io
import os
import sys
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import question_block as QB
import question_audit as QAUD
import gen_question_index as QIDX

# Every shape measured in the register, one line each. The first four were
# already recognised; the rest are what the 24 AUG enumeration added, and each
# was verified at its own matching line before being admitted.
MUST_MATCH = [
    "- **⏭ What would settle it**: the 1712 probate file",          # marker + label
    "**What would settle it:** the parish burial register",
    "- **What is left**: one unread deed",
    "- **What would name her**: her son's marriage act",
    "- **What settles it:** cite the apparatus with page refs",     # settles, not would settle
    "**What would settle them:**",                                  # plural, no text after
    "- **Next step**: browse the Placeholt film image by image",
    "- **Highest-priority next step**: search the county baptisms",  # qualified lead
    "- **Decisive next step (operator/archive image):** read the act",
    "**Revised next step:** the 1807 baptism",
    "- (d) paid next steps for the genuine brick walls",            # mid-sentence, plural
    "- **Minimum record needed**: the 1826 register, record #2",
    "- **Resolution path**: re-read the image at full resolution",
    "- **THE RESOLVER (specific):** read the two register images",
    "Remaining resolvers: the printed county series (paid)",        # mid-sentence
    "would show whether a petition was docketed. This is the resolver.",
    "- **What would unlock it**, in order: (1) his 1505 will",
    "- **Decisive confirmation (operator/paid, unchanged):** the birth act",
    "- **Named routes:** (1) the 1922 printing, read at source",
]

# Lines that must stay quiet. The first group is the residual's own phrasing --
# admitting it would clear the count and destroy the finding. The second is
# ordinary question prose that happens to sit near a resolver word.
MUST_NOT_MATCH = [
    "- This requires the Placeholt Stato Civile 1846 Nati register.",
    "- Needs the full-resolution image before the given name can be read.",
    "- **Solvability**: LOW from free online sources.",             # a rating, not a route
    "- **Payoff**: MODERATE (extends the line one generation).",
    "- **The conflict**: the marriage post-dates the eldest child.",
    "- **Impact**: does not affect lineage.",
    "- **Status**: PARTIALLY_RESOLVED, the date still unlocated.",  # RESOLVED != RESOLVER
    "- The route was CLOSED 17 JUL 2026 and is not reopened.",
    "- A step forward was made on the naming pattern.",             # 'step' without 'next'
    "- She was resolved to be a different woman entirely.",
]


def test_dialects():
    bad = []
    for ln in MUST_MATCH:
        if not QB.RESOLVER_RE.search(ln):
            bad.append(f"MISSED (should match): {ln}")
    for ln in MUST_NOT_MATCH:
        if QB.RESOLVER_RE.search(ln):
            bad.append(f"OVER-WIDE (should stay quiet): {ln}")
    return bad


def test_one_home():
    """Both consumers must BE the shared object, not a copy of it.

    The whole incident was two copies drifting apart, so identity is the
    assertion -- equality of pattern text would still allow a second literal.
    """
    bad = []
    if QAUD.SETTLE_RE is not QB.RESOLVER_RE:
        bad.append("question_audit.SETTLE_RE is not question_block.RESOLVER_RE")
    if QIDX.SETTLE_HDR is not QB.RESOLVER_RE:
        bad.append("gen_question_index.SETTLE_HDR is not question_block.RESOLVER_RE")
    return bad


def test_list_prints_resolverless():
    """`--list` must PRINT the rows it collects, not just count them."""
    f = {"Q_BELOW_INDEX": [], "DUP_LIVE_Q": [], "ZOMBIE_Q": [], "AMBIGUOUS_HEAD": [],
         "BIG_BLOCK": [], "RESOLVERLESS": [("Open_Questions_Example.md", 42, "77")],
         "LIVE": []}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        QAUD.report(f, hard_only=False)
    out = buf.getvalue()
    bad = []
    if "RESOLVERLESS" not in out or "Q77" not in out:
        bad.append("report(--list) did not print the RESOLVERLESS row")
    if "Open_Questions_Example.md:42" not in out:
        bad.append("report(--list) printed no file:line to open")
    # and it must NOT leak into the hard-only (pre-commit) view
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        n = QAUD.report(f, hard_only=True)
    if "RESOLVERLESS" in buf2.getvalue() or n != 0:
        bad.append("RESOLVERLESS leaked into the hard/pre-commit view")
    return bad


def main():
    bad = test_dialects() + test_one_home() + test_list_prints_resolverless()
    if bad:
        print("RESOLVER grammar test FAILED:")
        for b in bad:
            print("   ", b)
        return 1
    print(f"RESOLVER grammar test ok ({len(MUST_MATCH)} dialects, "
          f"{len(MUST_NOT_MATCH)} negative controls, 2 consumers share one home, "
          f"--list prints its rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
