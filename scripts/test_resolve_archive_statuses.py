#!/usr/bin/env python3
"""Pin question_store's agreement with archive_sections on WHICH statuses archive.

⚠ THE INVARIANT THIS FILE EXISTS FOR (24 SEP 2026): `question_block.STATUS_KWS`
decides whether a heading is TERMINAL; the shard's `archive_statuses` in the vault's
`.maintenance.json` decides whether `archive_sections.py` ARCHIVES it. The two had
drifted: plain CONFIRMED was terminal but not archivable, so a question resolved with it
read as closed everywhere, could no longer be edited through --replace, and was never
archived. The operator ruled (24 SEP 2026) that plain CONFIRMED stays non-archivable, so:

  (a) --resolve refuses a status the shard's archive target will not archive;
  (b) --resolve still accepts an archivable status, and behaves as before when the
      vault has no .maintenance.json (nothing constrains it);
  (c) --restatus repairs a stranded heading, keeping its date and note, and refuses
      a heading that is live or already archivable.
"""
import json
import os
import sys
import tempfile
from argparse import Namespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import question_block as QB
import question_store as QS

SHARD = "Open_Questions_Testland.md"
BODY = """# Open Questions — Testland

### 20. An open question about a placeholder family (raised 01 AUG 2026, session #1)

body

**⏭ WHAT WOULD SETTLE IT:** read the register

### 21. A second open question (raised 02 AUG 2026, session #2)

body

**⏭ WHAT WOULD SETTLE IT:** read the register

### 22. A stranded one (raised 03 AUG 2026, session #3) — CONFIRMED 04 AUG 2026 (the note is kept)

resolution text
"""
ALLOW = ["RESOLVED", "FULLY RESOLVED", "RESOLVED NEGATIVE", "CONFIRMED FAIL",
         "RULED OUT", "CLOSED"]


def _vault(d, with_config=True):
    with open(os.path.join(d, SHARD), "w", encoding="utf-8") as fh:
        fh.write(BODY)
    if with_config:
        cfg = {"targets": [{"name": "open-questions-testland", "file": SHARD,
                            "policy": "drop-by-status", "archive_statuses": ALLOW}]}
        with open(os.path.join(d, ".maintenance.json"), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)


def _heading(d, num):
    for _s, _e, h, lines in QB.iter_questions(os.path.join(d, SHARD)):
        if h["num"] == num:
            return lines[_s]
    return None


def _refused(fn, ns):
    try:
        fn(ns)
    except SystemExit:
        return True
    return False


def main():
    bad = []

    def check(name, ok):
        if not ok:
            bad.append(name)

    with tempfile.TemporaryDirectory() as d:
        _vault(d)
        check("loader reads the shard's archive_statuses",
              QS.archive_statuses_for(d, os.path.join(d, SHARD)) == ALLOW)

        # (a) CONFIRMED is terminal but not archivable here: refused, file untouched
        before = _heading(d, 20)
        check("resolve refuses a non-archivable terminal status",
              _refused(lambda ns: QS.op_resolve(d, ns),
                       Namespace(resolve="20", status="CONFIRMED", note=None, apply=True)))
        check("refused resolve leaves the heading alone", _heading(d, 20) == before)

        # (b) an archivable status still resolves
        QS.op_resolve(d, Namespace(resolve="21", status="RESOLVED", note="worked",
                                   apply=True))
        check("archivable status resolves", " — RESOLVED " in (_heading(d, 21) or ""))

        # (c) restatus repairs the stranded heading, keeping date and note
        QS.op_restatus(d, Namespace(restatus="22", status="RESOLVED", apply=True))
        h22 = _heading(d, 22) or ""
        check("restatus rewrites the keyword",
              h22.endswith("— RESOLVED 04 AUG 2026 (the note is kept)"))
        check("restatus keeps the title", "A stranded one" in h22)
        check("restatus refuses an already-archivable heading",
              _refused(lambda ns: QS.op_restatus(d, ns),
                       Namespace(restatus="22", status="CLOSED", apply=True)))
        check("restatus refuses a live block",
              _refused(lambda ns: QS.op_restatus(d, ns),
                       Namespace(restatus="20", status="RESOLVED", apply=True)))

    with tempfile.TemporaryDirectory() as d:
        # (b) no .maintenance.json: behaviour unchanged, nothing constrains the status
        _vault(d, with_config=False)
        check("no config -> loader returns None",
              QS.archive_statuses_for(d, os.path.join(d, SHARD)) is None)
        QS.op_resolve(d, Namespace(resolve="20", status="CONFIRMED", note=None,
                                   apply=True))
        check("no config -> any terminal status resolves",
              " — CONFIRMED " in (_heading(d, 20) or ""))
        check("no config -> restatus has nothing to repair",
              _refused(lambda ns: QS.op_restatus(d, ns),
                       Namespace(restatus="22", status="RESOLVED", apply=True)))

    if bad:
        print("RESOLVE_ARCHIVE_STATUSES test FAIL: " + ", ".join(bad))
        return 1
    print("RESOLVE_ARCHIVE_STATUSES test ok (resolve refuses what the archiver will not "
          "archive; restatus repairs a stranded heading and nothing else)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
