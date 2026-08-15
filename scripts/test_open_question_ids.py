#!/usr/bin/env python3
"""Pin session_plan.open_question_ids' FILE SET (deferred 44, shard-aware 15 AUG 2026).

⚠ THE INVARIANT: the suppression reader sees every LIVE question file — the
router AND the per-lineage shards — and never the Resolved/Archive stores or the
generated index. The 12 AUG shard split left it reading the router alone (which
holds zero question blocks), the suppression set collapsed 238 -> 3, and Q126's
two characterised gen-mismatch rows returned to IMPROVE rank 1-2: the exact
failure the function was built to prevent, back silently. The file set must come
from question_block.question_files, the ONE home, so a future re-layout moves
every reader together.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp


def main():
    bad = []

    def check(name, cond):
        if not cond:
            bad.append(name)

    with tempfile.TemporaryDirectory() as d:
        def w(name, text):
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write(text)

        w("Open_Questions.md", "# Router\n\nbrick wall table names `P-ROUTER1`\n")
        w("Open_Questions_Testland.md",
          "### 1. A live question naming `P-SHARD01` (raised 01 AUG 2026)\n\nbody\n")
        w("Open_Questions_Resolved.md",
          "### 2. Archived — RESOLVED 01 AUG 2026\n\nnames `P-RESOLV1`\n")
        w("Open_Questions_Index.md", "| **Q1** | ... | `P-INDEXD1` |\n")
        w("Open_Questions_Archive_snap.md", "names `P-ARCHIV1`\n")

        ids = sp.open_question_ids(d)
        check("router still read", "P-ROUTER1" in ids)
        check("shard read (the 12 AUG regression)", "P-SHARD01" in ids)
        check("resolved store NOT read", "P-RESOLV1" not in ids)
        check("generated index NOT read", "P-INDEXD1" not in ids)
        check("archive NOT read", "P-ARCHIV1" not in ids)

    if bad:
        print("OPEN_QUESTION_IDS test FAIL: " + ", ".join(bad))
        return 1
    print("OPEN_QUESTION_IDS test ok (router + shards read; Resolved/Index/Archive excluded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
