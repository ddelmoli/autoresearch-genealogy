#!/usr/bin/env python3
"""Pin session_plan.open_question_labels — the Q numbers printed beside a drawn row.

WHY IT EXISTS (24 AUG 2026). The live register named **359** people; only **28**
entries carried a `flags: [Q##]`. So for **338** of them a lane draw surfaced
nothing, and the drawer re-derived from scratch what a live question had already
established. Measured the same day: one woman sat in FOUR live questions with her
entry flagging none, and a man flagged for one question was also the subject of a
second. The register held the link the whole time — nothing printed it.

⚠⚠ THE ASSERTION THAT MATTERS MOST IS `test_ids_contract_not_narrowed`, and it is
here because the first cut of this feature BROKE it. Building `open_question_ids`
on top of the labels made it block-scoped, which silently drops every id named in
the ROUTER's brick-wall tables — the router holds no question blocks at all. That
is the same narrowing that collapsed the suppression set 238 -> 3 on 15 AUG and
put Q126's characterised rows back at IMPROVE rank 1-2. `test_open_question_ids`
caught it within a minute. The two products keep DIFFERENT scopes on purpose:

    ids     file-scoped   -> suppression (must stay wide)
    labels  block-scoped  -> pointing    (a Q number needs a heading)

⚠ ALL FIXTURES BELOW ARE SYNTHETIC. This file is in the PUBLIC framework repo,
which carries zero real family names (CONTRIBUTING.md, "the framework/private
boundary").
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp


def _vault(d):
    def w(name, text):
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    # the ROUTER: no question blocks, but it names ids in prose
    w("Open_Questions.md", "# Router\n\nbrick wall table names `P-ROUTR1`\n")
    # a live shard: two blocks, one id in both, one id mentioned incidentally
    w("Open_Questions_Testland.md",
      "### 7. A live question (raised 01 AUG 2026)\n\n"
      "names `P-AAAAAA` and, in passing, `P-CCCCCC`\n\n"
      "### 12a. A live sub-question (raised 02 AUG 2026)\n\n"
      "also about `P-AAAAAA` and `P-BBBBBB`\n\n"
      "### 9. A settled one — RESOLVED 03 AUG 2026\n\n"
      "names `P-DDDDDD`\n")
    # the stores that must never be read
    w("Open_Questions_Resolved.md",
      "### 99. Archived — RESOLVED 01 AUG 2026\n\nnames `P-EEEEEE`\n")
    w("Open_Questions_Index.md", "| **Q1** | ... | `P-FFFFFF` |\n")


def main():
    bad = []

    def check(name, cond):
        if not cond:
            bad.append(name)

    with tempfile.TemporaryDirectory() as d:
        _vault(d)
        lab = sp.open_question_labels(d)
        ids = sp.open_question_ids(d)

        # --- the pointer itself
        check("an id in two live blocks carries BOTH labels",
              lab.get("P-AAAAAA") == ["Q7", "Q12a"])
        check("an id in one live block carries one label",
              lab.get("P-BBBBBB") == ["Q12a"])
        check("a sub-question label keeps its letter", "Q12a" in lab.get("P-AAAAAA", []))
        check("an INCIDENTAL mention is still labelled (coarse by design)",
              lab.get("P-CCCCCC") == ["Q7"])

        # --- what must NOT point
        check("a RESOLVED block in a live shard does not point",
              "P-DDDDDD" not in lab)
        check("the Resolved store does not point", "P-EEEEEE" not in lab)
        check("the generated index does not point", "P-FFFFFF" not in lab)
        check("an id outside any block does not point (no heading, no Q number)",
              "P-ROUTR1" not in lab)

        # --- ⚠⚠ THE CONTRACT THE FIRST CUT BROKE
        check("test_ids_contract_not_narrowed: the ROUTER id still SUPPRESSES",
              "P-ROUTR1" in ids)
        check("ids stays a superset of the labelled ids",
              set(lab).issubset(ids))
        check("a resolved-block id still suppresses (file-scoped ids)",
              "P-DDDDDD" in ids)

        # --- degenerate inputs must not raise
        empty = tempfile.mkdtemp()
        check("no register -> empty labels, no crash", sp.open_question_labels(empty) == {})

    if bad:
        print("QUESTION_LABELS test FAILED:")
        for b in bad:
            print("   ", b)
        return 1
    print("QUESTION_LABELS test ok (multi-label, sub-question labels, coarse-by-design "
          "mentions, resolved/index/archive excluded, and the ids contract NOT narrowed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
