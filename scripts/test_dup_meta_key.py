#!/usr/bin/env python3
"""Tests for deferred 25 — DUP_META_KEY detection and the writer that prevents it.

** WHY BOTH HALVES ARE TESTED HERE. ** The defect is that a duplicated key in a
`- meta:` flow mapping is VALID YAML, LAST-WINS, and invisible to every gate: the
one real instance was caught only because two lanes contradicted each other. So a
detector that cannot be shown to FIRE is worth nothing, and a gate whose baseline
is 0 looks identical whether it works or is broken. Every positive assertion here
has a negative control beside it.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_person_index as G
import person_store as PS


class DetectorTests(unittest.TestCase):
    """`duplicate_meta_keys` — the gate side."""

    def test_the_REAL_case_fires(self):
        """The exact shape from the incident: a banked PID then a `TBD` that
        silently wins."""
        line = ("- meta: {id: P-0XAMP1, fs: VVVV-VVV, generation: 28, "
                "fs: TBD, life_status: deceased}")
        self.assertEqual(G.duplicate_meta_keys(line), ["fs"])

    def test_NEGATIVE_CONTROL_a_clean_line_is_silent(self):
        line = ("- meta: {id: P-0XAMP1, evidence_tier: strong_signal, "
                "generation: 28, fs: VVVV-VVV, life_status: deceased}")
        self.assertEqual(G.duplicate_meta_keys(line), [])

    def test_a_FLOW_LIST_comma_is_not_a_key_boundary(self):
        """`parents: '[P-A, P-B]'` must be ONE item. If the splitter tore on the
        inner comma it would see a bogus second key and fire falsely."""
        line = ("- meta: {id: P-AAAAAA, parents: '[P-BBBBBB, P-CCCCCC]', "
                "spouse: '[P-DDDDDD, P-EEEEEE]', generation: 9}")
        self.assertEqual(G.duplicate_meta_keys(line), [])

    def test_a_QUOTED_comma_is_not_a_key_boundary(self):
        """The case the first cut of this detector got wrong: a quoted value
        carrying a comma, with no brackets to protect it."""
        line = ("- meta: {id: P-AAAAAA, died_phrase: '15 or 17 January, 1240', "
                "born: 'BET 1195 AND 1197'}")
        self.assertEqual(G.duplicate_meta_keys(line), [])

    def test_it_catches_a_duplicate_that_SITS_AFTER_a_flow_list(self):
        line = ("- meta: {id: P-AAAAAA, parents: '[P-B, P-C]', fs: ABCD-123, "
                "generation: 4, fs: none}")
        self.assertEqual(G.duplicate_meta_keys(line), ["fs"])

    def test_two_different_duplicated_keys_are_both_reported(self):
        line = ("- meta: {id: P-AAAAAA, fs: A, gen: 1, fs: B, gen: 2}")
        self.assertEqual(G.duplicate_meta_keys(line), ["fs", "gen"])

    def test_case_is_not_a_loophole(self):
        """`FS:` and `fs:` are the same key to every reader, so they must be to
        the gate."""
        self.assertEqual(
            G.duplicate_meta_keys("- meta: {id: P-AAAAAA, FS: A, fs: B}"), ["fs"])

    def test_NEGATIVE_CONTROL_non_meta_and_legacy_lines_are_not_judged(self):
        self.assertEqual(G.duplicate_meta_keys("- Married Mary Smith (FS: X)"), [])
        self.assertEqual(G.duplicate_meta_keys("**Jane Doe** (b. 1800)"), [])
        # the legacy `;` form is not a flow mapping and is out of scope
        self.assertEqual(
            G.duplicate_meta_keys("- meta: id: P-AAAAAA; FS: X; tier: S"), [])


class WriterTests(unittest.TestCase):
    """`person_store.set_meta_key` — the half that stops one being written."""

    LINE = ("- meta: {id: P-0XAMP1, fs: TBD, generation: 28, "
            "life_status: deceased}")

    def test_it_REPLACES_rather_than_prepends(self):
        out = PS.set_meta_key(self.LINE, "fs", "VVVV-VVV")
        self.assertIn("fs: VVVV-VVV", out)
        self.assertNotIn("TBD", out)
        self.assertEqual(G.duplicate_meta_keys(out), [],
                         "the writer must not be able to create the defect")

    def test_the_written_line_still_PARSES_to_the_new_value(self):
        out = PS.set_meta_key(self.LINE, "fs", "VVVV-VVV")
        self.assertEqual(G.parse_meta(out).get("fs"), "VVVV-VVV")

    def test_it_INSERTS_a_key_that_was_absent(self):
        line = "- meta: {id: P-AAAAAA, generation: 9}"
        out = PS.set_meta_key(line, "fs", "ABCD-123")
        self.assertEqual(G.parse_meta(out).get("fs"), "ABCD-123")
        self.assertEqual(G.duplicate_meta_keys(out), [])

    def test_a_new_key_goes_BEFORE_flags(self):
        """`flags:` is last by convention, and build_edges.upsert_edges assumes it."""
        line = "- meta: {id: P-AAAAAA, generation: 9, flags: Q14}"
        out = PS.set_meta_key(line, "fs", "ABCD-123")
        self.assertLess(out.index("fs:"), out.index("flags:"))

    def test_it_does_not_disturb_a_flow_list_value(self):
        line = "- meta: {id: P-AAAAAA, parents: '[P-B?, P-C]', generation: 9}"
        out = PS.set_meta_key(line, "fs", "ABCD-123")
        self.assertIn("parents: '[P-B?, P-C]'", out)
        self.assertEqual(G.parse_meta(out).get("parents"), "[P-B?, P-C]")

    def test_it_COLLAPSES_a_pre_existing_duplicate(self):
        """Repair, not just prevention: writing through this helper cleans a line
        that already carried the defect."""
        bad = "- meta: {id: P-AAAAAA, fs: VVVV-VVV, generation: 28, fs: TBD}"
        self.assertEqual(G.duplicate_meta_keys(bad), ["fs"])
        out = PS.set_meta_key(bad, "fs", "VVVV-VVV")
        self.assertEqual(G.duplicate_meta_keys(out), [])
        self.assertEqual(G.parse_meta(out).get("fs"), "VVVV-VVV")

    def test_NEGATIVE_CONTROL_a_non_meta_line_is_returned_UNCHANGED(self):
        for line in ("- Married Mary Smith (FS: X)",
                     "**Jane Doe** (b. 1800)",
                     "- meta: id: P-AAAAAA; FS: X; tier: S"):
            self.assertEqual(PS.set_meta_key(line, "fs", "ZZZZ-999"), line)

    def test_NEGATIVE_CONTROL_it_does_not_touch_OTHER_keys(self):
        out = PS.set_meta_key(self.LINE, "fs", "VVVV-VVV")
        m = G.parse_meta(out)
        self.assertEqual(m.get("id"), "P-0XAMP1")
        self.assertEqual(m.get("generation"), 28)
        self.assertEqual(m.get("life_status"), "deceased")


class SharedSplitterTests(unittest.TestCase):
    """The gate and the reader must agree on item boundaries, or the gate can
    miss a duplicate the reader acts on (two readers, one entry)."""

    def test_the_reader_and_the_gate_use_the_same_split(self):
        raw = "{id: P-A, parents: '[P-B, P-C]', died_phrase: 'a, b', fs: X}"
        self.assertEqual(len(G._split_flow_items(raw)), 4)

    def test_last_wins_is_what_the_reader_actually_does(self):
        """Pins the PREMISE of the whole item. If this ever stopped being true,
        the gate would be guarding nothing."""
        line = "- meta: {id: P-AAAAAA, fs: FIRST, fs: LAST}"
        self.assertEqual(G.parse_meta(line).get("fs"), "LAST")


if __name__ == "__main__":
    unittest.main(verbosity=2)
