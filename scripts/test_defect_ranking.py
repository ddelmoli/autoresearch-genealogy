#!/usr/bin/env python3
"""What the IMPROVE defect pool DEMOTES, and why — deferred 44 (+ a bug it exposed).

** TWO WAYS ALREADY-EXAMINED WORK WAS OUTRANKING WORK NOBODY HAD LOOKED AT. **

1. **deferred 44 — a GATE finding already tracked as an Open_Question.** Measured
   03 AUG 2026 (session #135): both of the vault's remaining PARENT-GEN mismatches were
   fully characterised in Q126, inversion warning and all, and the lane still offered one
   at rank 1. Prompt 22 counts a question ONCE, for the sitting that did the work, so the
   row was unworkable for credit and would have ranked first every draw. `adjudicated`
   fixed exactly this for `?` edges (deferred 32); the gate half never got the equivalent.

2. **The `revisit` tag was being CLOBBERED.** `lane_verify` deliberately appends its
   FS-GAP RE-CHECK rows last — *"a settled edge worth a second look must never outrank an
   edge nobody has looked at"* — by tagging them `revisit`. `lane_defects` then rebuilt
   every row as `{**r, "_defect": "edge"}`, which threw the tag away. Measured on the
   reference vault the same day: **all 7 re-check rows came back at rank 1** and, being
   low-generation, sorted ahead of every genuinely open edge. The lane's own stated
   intent had been silently inverted, and nothing failed.

⚠ **DEMOTED, NEVER REMOVED, in both cases.** The lane size has to stay honest — the
point is ordering, not hiding. That is also why the Open_Questions read is allowed to be
coarse: a false positive costs a row its place in the queue, not its existence.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp


def row(vid, name, meta, gen=5):
    return {"id": vid, "name": name, "gen": gen, "file": "F.md", "block": meta}


class OpenQuestionIds(unittest.TestCase):

    def _vault(self, text, fname="Open_Questions.md"):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, fname), "w", encoding="utf-8") as fh:
            fh.write(text)
        return d

    def test_reads_ids_out_of_the_live_register(self):
        v = self._vault("### 126. A mismatch\n\nAbout P-AAAAAA and P-BBBBBB.\n")
        self.assertEqual(sp.open_question_ids(v), {"P-AAAAAA", "P-BBBBBB"})

    def test_a_missing_register_is_not_a_hard_failure(self):
        # A fresh vault has no Open_Questions.md. Nothing is tracked; nothing explodes.
        self.assertEqual(sp.open_question_ids(tempfile.mkdtemp()), set())

    def test_the_RESOLVED_file_is_NOT_read(self):
        # NEGATIVE CONTROL. A resolved question must stop suppressing its row, so only
        # the live register counts. Writing the id ONLY into the resolved file must
        # leave it untracked.
        d = self._vault("### 9. Done — RESOLVED\n\nP-CCCCCC settled.\n",
                        fname="Open_Questions_Resolved.md")
        self.assertEqual(sp.open_question_ids(d), set())


class DefectRanking(unittest.TestCase):
    """The ordering contract, asserted on ranks rather than on list positions."""

    def test_demoted_kinds_rank_behind_every_unexamined_kind(self):
        r = sp._DEFECT_RANK
        for demoted in ("gate-tracked", "revisit"):
            for fresh in ("gate", "edge", "audit"):
                self.assertGreater(
                    r[demoted], r[fresh],
                    f"{demoted} must never outrank {fresh} — that is the whole fix")

    def test_a_tracked_gate_finding_still_outranks_nothing_it_should_not(self):
        # gate-tracked is demoted below `audit`, but it is still a KNOWN specific defect,
        # so it must stay ahead of the cheap re-checks.
        self.assertLess(sp._DEFECT_RANK["gate-tracked"], sp._DEFECT_RANK["revisit"])

    def test_every_kind_the_builder_emits_has_an_explicit_rank(self):
        # A kind missing from the table falls to the default 9 and is silently demoted
        # past everything — which is exactly how the `revisit` bug hid.
        for kind in ("gate", "gate-tracked", "edge", "audit", "revisit"):
            self.assertIn(kind, sp._DEFECT_RANK)


class RevisitTagSurvives(unittest.TestCase):
    """The regression test for the clobber. Pins behaviour, not implementation."""

    def tearDown(self):
        import gen_person_index as g
        if hasattr(self, "_saved"):
            g.parse_narrative = self._saved

    def test_lane_defects_preserves_an_incoming_defect_tag(self):
        import gen_person_index as g
        self._saved = g.parse_narrative
        g.parse_narrative = lambda *a, **k: []

        saved_verify = sp.lane_verify
        try:
            # One already-demoted row and one ordinary open-edge row.
            sp.lane_verify = lambda *a, **k: [
                {"id": "P-RRRRRR", "name": "Recheck", "gen": 6, "file": "F.md",
                 "_defect": "revisit", "why": "RE-CHECK an FS-GAP adjudication"},
                {"id": "P-EEEEEE", "name": "OpenEdge", "gen": 40, "file": "F.md",
                 "why": "unconfirmed edges: 1 parents"},
            ]
            sp.lane_edge_audit = lambda *a, **k: []
            out = sp.lane_defects(tempfile.mkdtemp())
        finally:
            sp.lane_verify = saved_verify

        kinds = {r["id"]: r["_defect"] for r in out}
        self.assertEqual(kinds["P-RRRRRR"], "revisit",
                         "the revisit tag was clobbered back to 'edge' again")
        self.assertEqual(kinds["P-EEEEEE"], "edge",
                         "an untagged row must still default to 'edge'")

        # ...and the ORDER is the thing that actually matters: the Gen-6 settled row must
        # come AFTER the Gen-40 open one, which plain generation-sorting would reverse.
        order = [r["id"] for r in out]
        self.assertLess(order.index("P-EEEEEE"), order.index("P-RRRRRR"),
                        "a settled re-check outranked an edge nobody has looked at")


if __name__ == "__main__":
    unittest.main(verbosity=2)
