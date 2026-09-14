#!/usr/bin/env python3
"""Pins the overlap contract of `session_plan.compose_share` (session #184, 26 AUG 2026).

WHAT IS BEING DEFENDED. `compose_share` interleaves a lane's two populations while
reserving a quota for the primary one. It concatenated them, and **the two overlap**:
a person with an unconfirmed `?` edge who is ALSO SOURCE_GAP is emitted by
`lane_defects` and by `lane_improve` at once. Measured on the reference vault, an
IMPROVE draw offered **24 rows containing 23 distinct people** -- so a lane target of
24, which counts PEOPLE, could not be met from its own draw even in principle, and
the duplicate rendered twice in the printed worklist.

⛔ THE SUBTLE HALF, REVERSED 13 SEP 2026. The first fix deduped on `cool_key` and
pinned deduping on `id` as an over-reach, because the key namespaces sub-populations
(`corrob:<id>` against the bare id) so two kinds of work on one person cool
independently. That let one person through twice whenever the keys differed: 57
people on the reference vault, 1,210 rows for 1,153 people. The two concerns were
never in conflict. A ROW is what the lane counts and offers, so rows collapse per
PERSON; a COOL KEY is what cools, so the survivor carries every key and every one is
stamped. Each kind of work still cools on its own key (pinned in
test_candidate_rotation.TestCoolKeyNamespacing, unchanged).

Most of these are NEGATIVE CONTROLS, because each failure here is silent: a dedupe
that over-reaches drops work nobody notices is missing, and one that under-reaches
restores the miscount it was meant to fix.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp  # noqa: E402


def row(rid, why="", cool=None):
    r = {"id": rid, "why": why}
    if cool is not None:
        r["_cool_key"] = cool
    return r


def keys(rows):
    return [sp.cool_key(r) for r in rows]


class ComposeShareDedupe(unittest.TestCase):

    def test_overlapping_person_is_emitted_once(self):
        """The measured bug: same person in both halves came back twice."""
        primary = [row("P-AAA", "unconfirmed edges: 1 spouse"), row("P-BBB")]
        secondary = [row("P-AAA", "SOURCE_GAP: 0 records"), row("P-CCC")]
        out, _, _ = sp.compose_share(primary, secondary, 4, 0.5)
        self.assertEqual(len(keys(out)), len(set(keys(out))))
        self.assertEqual(keys(out).count("P-AAA"), 1)

    def test_no_row_is_lost(self):
        """Dedupe must not become a filter: every DISTINCT key still appears."""
        primary = [row("P-AAA"), row("P-BBB")]
        secondary = [row("P-AAA"), row("P-CCC"), row("P-DDD")]
        out, _, _ = sp.compose_share(primary, secondary, 4, 0.5)
        self.assertEqual(set(keys(out)), {"P-AAA", "P-BBB", "P-CCC", "P-DDD"})

    def test_primary_wins_and_keeps_its_position(self):
        """The PRIMARY row survives -- it holds the reserved quota."""
        primary = [row("P-AAA", "unconfirmed edges: 1 spouse")]
        secondary = [row("P-AAA", "SOURCE_GAP: 0 records")]
        out, _, _ = sp.compose_share(primary, secondary, 2, 0.5)
        self.assertEqual(len(out), 1)
        self.assertIn("unconfirmed edges", out[0]["why"])

    def test_the_dropped_reason_is_KEPT_on_the_survivor(self):
        """⭐ The second reason is folded in, not silently discarded."""
        primary = [row("P-AAA", "unconfirmed edges: 1 spouse")]
        secondary = [row("P-AAA", "SOURCE_GAP: 0 records")]
        out, _, _ = sp.compose_share(primary, secondary, 2, 0.5)
        self.assertIn("unconfirmed edges", out[0]["why"])
        self.assertIn("SOURCE_GAP: 0 records", out[0]["why"])

    def test_DIFFERENT_cool_keys_on_one_person_are_ONE_row_carrying_BOTH(self):
        """⛔ The under-reach the first fix shipped: a defect row (bare id) and a
        corroboration row (`corrob:<id>`) on one person came back as two rows."""
        primary = [row("P-AAA", "a ? edge to walk")]
        secondary = [row("P-AAA", "SINGLE_SOURCED: 1 record", cool="corrob:P-AAA")]
        out, _, _ = sp.compose_share(primary, secondary, 4, 0.5)
        self.assertEqual([r["id"] for r in out], ["P-AAA"])
        self.assertEqual(sp.cool_keys(out[0]), ["P-AAA", "corrob:P-AAA"])
        self.assertIn("SINGLE_SOURCED", out[0]["why"])

    def test_both_folded_keys_COOL_when_the_row_is_offered(self):
        """⭐ Collapsing the row must not cool only half the work it put in front of the
        sitting: stamping `cool_keys` cools both, and each still cools on its own key."""
        out, _, _ = sp.compose_share([row("P-AAA", "edge")],
                                     [row("P-AAA", "corrob", cool="corrob:P-AAA")], 2, 0.5)
        st = {"history": [{"session": 1, "date": "2026-09-13"}], "offered": {}}
        sitting = sp.sitting_of(st["history"][0])
        sp.stamp_offered(st, "IMPROVE", sp.cool_keys(out[0]), sitting)
        self.assertTrue(sp.cooling(st, "IMPROVE", "P-AAA")[0])
        self.assertTrue(sp.cooling(st, "IMPROVE", "corrob:P-AAA")[0])
        self.assertFalse(sp.cooling(st, "IMPROVE", "corrob:P-BBB")[0])

    def test_the_lane_is_sized_in_PEOPLE(self):
        """The construction-time dedupe feeds `sizes`, the printed count and the draw."""
        defects = [row("P-AAA", "edge"), row("P-BBB", "edge")]
        gaps = [row("P-BBB", "SOURCE_GAP"), row("P-CCC", "SOURCE_GAP")]
        corrob = [row("P-AAA", "one host", cool="corrob:P-AAA"),
                  row("P-DDD", "one host", cool="corrob:P-DDD")]
        lane = sp.dedupe_by_person(defects + gaps + corrob)
        self.assertEqual(sorted(r["id"] for r in lane), ["P-AAA", "P-BBB", "P-CCC", "P-DDD"])

    def test_a_person_in_two_populations_takes_her_BEST_position(self):
        """⛔ The first fix let the primary occurrence win even from beyond its quota,
        so being in two populations made a person LESS likely to be offered."""
        defects = [row("D1"), row("D2"), row("X", "edge")]
        gaps = [row("X", "gap"), row("G1"), row("G2"), row("G3")]
        out, pq, sq = sp.compose_share(defects, gaps, 4, 0.25)
        head = [r["id"] for r in out[:pq + sq]]
        self.assertIn("X", head)
        self.assertEqual(head, ["D1", "X", "G1", "G2"])
        # ...and her defect reason still rides along from the tail.
        self.assertIn("edge", out[1]["why"])
        # NEGATIVE CONTROL: without the overlap she sits exactly there anyway.
        solo, _, _ = sp.compose_share([row("D1"), row("D2")], gaps, 4, 0.25)
        self.assertEqual([r["id"] for r in solo[:4]], head)

    def test_a_duplicate_skipped_inside_a_quota_does_not_use_it_up(self):
        """The secondary quota counts rows PLACED: a person the primary already placed
        is skipped and the next secondary row takes the slot."""
        out, pq, sq = sp.compose_share([row("A"), row("B")],
                                       [row("A"), row("C"), row("D"), row("E")], 4, 0.5)
        self.assertEqual((pq, sq), (2, 2))
        self.assertEqual([r["id"] for r in out[:4]], ["A", "B", "C", "D"])

    def test_the_printed_split_is_COUNTED_from_the_slot(self):
        """⚠ The outer compose skips sourcing rows a defect already placed, so the inner
        quotas no longer describe what it took. Measured shape: defects [G1, G2, D9],
        gaps [G1, G2, G3], four corroboration rows, target 6."""
        gaps = [row("G1", "gap"), row("G2", "gap"), row("G3", "gap")]
        for r in gaps:
            r["_kind"] = "gap"
        corrob = [dict(row(f"C{i}", cool=f"corrob:C{i}"), _kind="corrob") for i in range(1, 5)]
        defects = [row("G1", "edge"), row("G2", "edge"), row("D9", "edge")]
        src, gq, cq = sp.compose_share(gaps, corrob, 6, 0.5)
        lane, dq, srcq = sp.compose_share(defects, src, 6, 0.25)
        g, c = sp.sourcing_split(lane, dq, srcq)
        self.assertEqual(dq + g + c, 6)
        self.assertEqual((dq, g, c), (1, 2, 3))
        # NEGATIVE CONTROL: the derivation it replaces reports a split that is not there.
        self.assertNotEqual((min(gq, srcq), srcq - min(gq, srcq)), (g, c))

    def test_caller_cool_key_lists_are_not_mutated(self):
        """A survivor owns its own `_cool_keys`: folding must not grow the caller's list."""
        p = dict(row("P-AAA"), _cool_keys=["P-AAA"])
        sp.compose_share([p], [row("P-AAA", cool="corrob:P-AAA")], 2, 0.5)
        self.assertEqual(p["_cool_keys"], ["P-AAA"])

    def test_duplicates_WITHIN_one_population_also_collapse(self):
        primary = [row("P-AAA"), row("P-AAA"), row("P-BBB")]
        out, _, _ = sp.compose_share(primary, [], 4, 0.5)
        self.assertEqual(keys(out), ["P-AAA", "P-BBB"])

    def test_quotas_describe_the_list_ACTUALLY_returned(self):
        """⚠ Dedupe runs BEFORE sizing. Quotas computed against pre-dedupe lengths
        are how this function once reported three numbers that could not all be
        true at once."""
        primary = [row("P-AAA"), row("P-BBB")]
        secondary = [row("P-AAA"), row("P-BBB"), row("P-CCC")]
        out, p_quota, s_quota = sp.compose_share(primary, secondary, 3, 0.5)
        self.assertLessEqual(p_quota, len(primary))
        self.assertLessEqual(p_quota + s_quota, len(out) + s_quota)
        self.assertEqual(len(keys(out)), len(set(keys(out))))

    def test_caller_rows_are_not_mutated(self):
        """The survivor is a COPY: folding a reason must not edit the caller's dict."""
        p = row("P-AAA", "unconfirmed edges")
        s = row("P-AAA", "SOURCE_GAP: 0 records")
        sp.compose_share([p], [s], 2, 0.5)
        self.assertEqual(p["why"], "unconfirmed edges")
        self.assertEqual(s["why"], "SOURCE_GAP: 0 records")

    def test_unkeyed_rows_pass_through(self):
        """A row with no id and no _cool_key cannot be compared; keep it."""
        out, _, _ = sp.compose_share([{"why": "x"}, {"why": "y"}], [], 2, 0.5)
        self.assertEqual(len(out), 2)

    def test_empty_populations_are_safe(self):
        self.assertEqual(sp.compose_share([], [], 3, 0.5)[0], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
