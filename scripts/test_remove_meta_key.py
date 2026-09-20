#!/usr/bin/env python3
"""test_remove_meta_key.py — pins `person_store.remove_meta_key`.

** WHY THIS EXISTS. ** `set_meta_key` can only WRITE; passing None or "" writes `key: `
with an empty value rather than deleting the key, and that empty form is itself pinned
behaviour elsewhere. So there was no supported way to RETRACT a meta key, while
hand-splicing a meta block is forbidden by the same rule that mandates the writer.

The live cost, measured 20 SEP 2026: a `fs_probed` stamp asserts "the attached-source set
was READ and holds no records", and the 16 SEP limb-(g) ruling made a relative's record
that NAMES the person count — so stamps written before that date may now be false. **36
SOURCE_GAP rows carry one**, and `fs_probed` is itself what suppresses those rows from the
lane that would re-examine them. Retracting the key is the correcting write.

What is pinned:
  1. the key is removed and the rest of the mapping survives INTACT, in order;
  2. the call is IDEMPOTENT — removing an absent key changes nothing;
  3. EVERY occurrence goes, so a pre-existing duplicate collapses away;
  4. ⛔ `id` cannot be removed and the attempt RAISES (its absence is a HARD gate);
  5. a non-meta line and the legacy `;` form are returned UNCHANGED;
  6. ⚠ the result is still parseable by the SAME readers — checked by round-tripping
     through `_parse_flow_mapping`, not by eyeballing the string;
  7. quoted values containing commas/brackets are not split by the removal.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import person_store as ps  # noqa: E402

try:
    import gen_person_index as G
    _PARSE = getattr(G, "_parse_flow_mapping", None)
except Exception:                                   # pragma: no cover
    _PARSE = None

FAILS: list[str] = []


def check(cond, label):
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


META = ("- meta: {id: P-AAAAAA, evidence_tier: moderate_signal, profile_status: partial, "
        "life_status: deceased, generation: 12, fs: XXXX-XXX, born: '1672', died: '1739', "
        "spouse: '[P-BBBBBB]', fs_probed: 2026-08-21, edges_audited: 2026-09-18}")


def main():
    print("remove_meta_key")

    out = ps.remove_meta_key(META, "fs_probed")
    check("fs_probed" not in out, "the key is gone")
    check("fs_probed: " not in out, "and NOT left as an empty value (the old workaround)")
    check(ps.fs_probed(out) is None, "the reader now sees it as absent")

    # everything else survives, in order
    for k, v in (("id", "P-AAAAAA"), ("fs", "XXXX-XXX"), ("generation", "12"),
                 ("born", "'1672'"), ("died", "'1739'"),
                 ("spouse", "'[P-BBBBBB]'"), ("edges_audited", "2026-09-18")):
        check(f"{k}: {v}" in out, f"{k} survives intact")
    check(out.index("id:") < out.index("fs:") < out.index("edges_audited:"),
          "key ORDER is preserved")
    check(ps.edges_audited(out) == "2026-09-18",
          "a neighbouring dated key still reads correctly")

    # the readers must still parse it -- string inspection is not the test
    if _PARSE:
        inner = out.split("{", 1)[1].rsplit("}", 1)[0]
        parsed = _PARSE("{" + inner + "}")
        check(isinstance(parsed, dict) and parsed.get("id") == "P-AAAAAA",
              "round-trips through the roster's own flow-mapping parser")
        check("fs_probed" not in parsed, "and the parser agrees the key is gone")
    else:                                            # pragma: no cover
        print("  ..    (roster parser unavailable; round-trip check skipped)")

    # idempotent
    check(ps.remove_meta_key(out, "fs_probed") == out,
          "removing an absent key is a no-op")
    check(ps.remove_meta_key(META, "never_set_this") == META,
          "removing a key that was never there returns the line unchanged")

    # duplicates collapse
    dup = ("- meta: {id: P-AAAAAA, fs_probed: 2026-08-21, fs: ABCD-123, "
           "fs_probed: 2026-09-01}")
    ddone = ps.remove_meta_key(dup, "fs_probed")
    check(ddone.count("fs_probed") == 0, "EVERY occurrence is removed, not just the first")
    check("fs: ABCD-123" in ddone, "the duplicate removal does not eat its neighbour")

    # id is protected
    try:
        ps.remove_meta_key(META, "id")
        check(False, "removing `id` RAISES")
    except ValueError:
        check(True, "removing `id` RAISES")
    try:
        ps.remove_meta_key(META, "ID")
        check(False, "the id guard is case-insensitive")
    except ValueError:
        check(True, "the id guard is case-insensitive")

    # non-meta and legacy forms untouched
    plain = "- Some ordinary narrative bullet with a colon: in it"
    check(ps.remove_meta_key(plain, "fs_probed") == plain,
          "a non-meta line is returned unchanged")
    legacy = "- meta: id: P-BBBBBB; fs: ABCD-123; fs_probed: 2026-08-21"
    check(ps.remove_meta_key(legacy, "fs_probed") == legacy,
          "the legacy `;` form is NOT rewritten")

    # a quoted value carrying commas/brackets must not be split by the removal
    commas = ("- meta: {id: P-CCCCCC, parents: '[P-AAA111, P-BBB222]', "
              "fs_probed: 2026-08-21, flags: '[Q1, Q2]'}")
    cdone = ps.remove_meta_key(commas, "fs_probed")
    check("parents: '[P-AAA111, P-BBB222]'" in cdone,
          "a quoted flow-list neighbour is preserved whole")
    check("flags: '[Q1, Q2]'" in cdone, "and so is a quoted flags list")
    check("fs_probed" not in cdone, "while the target key still goes")


if __name__ == "__main__":
    main()
    print()
    if FAILS:
        print(f"FAILED {len(FAILS)}:")
        for f in FAILS:
            print("   -", f)
        sys.exit(1)
    print("all remove_meta_key checks passed")
