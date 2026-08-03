#!/usr/bin/env python3
"""`adjudicated_why`, and which adjudications come back — deferred 38.

** THE ITEM ASKED FOR A BLANKET CLOCK AND THE MEASUREMENT SAID NO. ** Over 47 live
adjudications a clock helps SEVEN: fs-gap 24 / contradicted 7 / hedge 6 / unstated 12,
and of the fs-gap rows only 7 have a real PID at the far end. A HEDGE expires when the
named resolver is READ and a CONTRADICTION when the sources are adjudicated — events a
clock cannot detect — while an fs-gap ending at `fs: none`/`TBD` can only be re-checked
by a full existence probe, which is the expensive work the adjudication exists to record.

So the rule under test is narrow on purpose, and these tests exist to keep it narrow.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp


class _Vault:
    """A tiny stand-in for the narrative reader `lane_verify` uses."""
    def __init__(self, rows):
        self.rows = rows


def _patch(monkey_rows):
    """Point gen_person_index.parse_narrative at a fixture."""
    import gen_person_index as g
    saved = g.parse_narrative
    g.parse_narrative = lambda *a, **k: monkey_rows
    return saved


def row(vid, name, meta, gen=5):
    return {"id": vid, "name": name, "gen": gen, "file": "F.md", "block": meta}


class ReofferRules(unittest.TestCase):

    def tearDown(self):
        import gen_person_index as g
        if hasattr(self, "_saved"):
            g.parse_narrative = self._saved

    def _run(self, rows):
        import gen_person_index as g
        self._saved = g.parse_narrative
        g.parse_narrative = lambda *a, **k: rows
        return sp.lane_verify("/nonexistent")

    def test_an_FS_GAP_with_a_LIVE_far_end_PID_comes_back(self):
        rows = [
            row("P-AAAAAA", "Child", "- meta: {id: P-AAAAAA, generation: 5, "
                "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]', "
                "adjudicated_why: fs-gap}"),
            row("P-BBBBBB", "Parent", "- meta: {id: P-BBBBBB, generation: 6, fs: ABCD-123}"),
        ]
        out = self._run(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["_defect"], "revisit")
        self.assertIn("RE-CHECK", out[0]["why"])

    def test_NEGATIVE_CONTROL_an_FS_GAP_ending_at_fs_none_does_NOT(self):
        """Re-checking this means an existence probe with identifier rejection —
        re-running the expensive work the adjudication records."""
        for far in ("fs: none", "fs: TBD", ""):
            rows = [
                row("P-AAAAAA", "Child", "- meta: {id: P-AAAAAA, generation: 5, "
                    "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]', "
                    "adjudicated_why: fs-gap}"),
                row("P-BBBBBB", "Parent",
                    "- meta: {id: P-BBBBBB, generation: 6" + (", " + far if far else "") + "}"),
            ]
            self.assertEqual(self._run(rows), [], f"far end {far!r} must not be re-offered")

    def test_NEGATIVE_CONTROL_a_HEDGE_never_comes_back_on_a_clock(self):
        """A scholarly hedge expires when the named source is READ. Re-offering it
        is the noise `adjudicated` was introduced to remove."""
        rows = [
            row("P-AAAAAA", "Child", "- meta: {id: P-AAAAAA, generation: 5, "
                "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]', "
                "adjudicated_why: hedge}"),
            row("P-BBBBBB", "Parent", "- meta: {id: P-BBBBBB, generation: 6, fs: ABCD-123}"),
        ]
        self.assertEqual(self._run(rows), [])

    def test_NEGATIVE_CONTROL_CONTRADICTED_never_comes_back_either(self):
        rows = [
            row("P-AAAAAA", "Child", "- meta: {id: P-AAAAAA, generation: 5, "
                "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]', "
                "adjudicated_why: contradicted}"),
            row("P-BBBBBB", "Parent", "- meta: {id: P-BBBBBB, generation: 6, fs: ABCD-123}"),
        ]
        self.assertEqual(self._run(rows), [])

    def test_an_UNSTATED_reason_does_not_silently_become_fs_gap(self):
        """12 live rows state no reason. They must not be guessed into the
        re-offer pool — `ADJUDICATED_UNEXPLAINED` surfaces them instead."""
        rows = [
            row("P-AAAAAA", "Child", "- meta: {id: P-AAAAAA, generation: 5, "
                "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]'}"),
            row("P-BBBBBB", "Parent", "- meta: {id: P-BBBBBB, generation: 6, fs: ABCD-123}"),
        ]
        self.assertEqual(self._run(rows), [])

    def test_a_revisit_never_outranks_a_genuinely_OPEN_edge(self):
        """An edge nobody has looked at must come first."""
        rows = [
            row("P-AAAAAA", "Settled", "- meta: {id: P-AAAAAA, generation: 2, "
                "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]', "
                "adjudicated_why: fs-gap}", gen=2),
            row("P-BBBBBB", "Parent", "- meta: {id: P-BBBBBB, generation: 6, fs: ABCD-123}"),
            row("P-CCCCCC", "Untouched", "- meta: {id: P-CCCCCC, generation: 40, "
                "parents: '[P-DDDDDD?]'}", gen=40),
        ]
        out = self._run(rows)
        self.assertEqual([r["id"] for r in out], ["P-CCCCCC", "P-AAAAAA"],
                         "the open edge leads even though its generation is deeper")

    def test_the_adjudicated_id_is_NOT_reported_as_an_open_edge(self):
        """A revisit is a SETTLED row worth a second look. Letting it fall through
        as an ordinary `?` row would present adjudicated work as never-looked-at."""
        rows = [
            row("P-AAAAAA", "Child", "- meta: {id: P-AAAAAA, generation: 5, "
                "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]', "
                "adjudicated_why: fs-gap}"),
            row("P-BBBBBB", "Parent", "- meta: {id: P-BBBBBB, generation: 6, fs: ABCD-123}"),
        ]
        out = self._run(rows)
        self.assertNotIn("unconfirmed edges", out[0]["why"])

    def test_include_adjudicated_still_returns_everything(self):
        rows = [
            row("P-AAAAAA", "Child", "- meta: {id: P-AAAAAA, generation: 5, "
                "parents: '[P-BBBBBB?]', adjudicated: '[P-BBBBBB]', "
                "adjudicated_why: hedge}"),
            row("P-BBBBBB", "Parent", "- meta: {id: P-BBBBBB, generation: 6, fs: ABCD-123}"),
        ]
        import gen_person_index as g
        self._saved = g.parse_narrative
        g.parse_narrative = lambda *a, **k: rows
        out = sp.lane_verify("/nonexistent", include_adjudicated=True)
        self.assertEqual(len(out), 1)
        self.assertIn("unconfirmed edges", out[0]["why"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
