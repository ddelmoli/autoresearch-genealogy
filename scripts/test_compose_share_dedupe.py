#!/usr/bin/env python3
"""Pins the overlap contract of `session_plan.compose_share` (session #184, 26 AUG 2026).

WHAT IS BEING DEFENDED. `compose_share` interleaves a lane's two populations while
reserving a quota for the primary one. It concatenated them, and **the two overlap**:
a person with an unconfirmed `?` edge who is ALSO SOURCE_GAP is emitted by
`lane_defects` and by `lane_improve` at once. Measured on the reference vault, an
IMPROVE draw offered **24 rows containing 23 distinct people** -- so a lane target of
24, which counts PEOPLE, could not be met from its own draw even in principle, and
the duplicate rendered twice in the printed worklist.

⚠ THE SUBTLE HALF, AND THE REASON THIS FILE EXISTS: the fix must dedupe on
`cool_key`, NEVER on `id`. That key deliberately namespaces sub-populations
(`pid:<id>` against the bare id) so that two DIFFERENT kinds of work on one person
cool independently. Deduping on `id` would silently delete the very distinction the
key was introduced to make -- a fix that reads correct and quietly removes real work
from the lane.

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

    def test_DIFFERENT_cool_keys_on_one_person_BOTH_survive(self):
        """⛔ THE OVER-REACH CONTROL. `pid:<id>` and the bare id are two kinds of
        work on one person and cool separately -- deduping on `id` would delete one."""
        primary = [row("P-AAA", "a ? edge to walk")]
        secondary = [row("P-AAA", "stale FS PID", cool="pid:P-AAA")]
        out, _, _ = sp.compose_share(primary, secondary, 4, 0.5)
        self.assertEqual(sorted(keys(out)), ["P-AAA", "pid:P-AAA"])

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
