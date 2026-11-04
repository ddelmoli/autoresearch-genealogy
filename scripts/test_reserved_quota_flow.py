#!/usr/bin/env python3
"""Pins the cooled-reservation rule of `session_plan.compose_share` (04 NOV 2026, deferred 75).

WHAT IS BEING DEFENDED. A lane reserves a share of its draw for a primary population.
When that population is small and every row in it was already offered this sitting,
the reservation used to be filled with those same cooled rows, so a three-person
group was offered in four successive draws of one sitting. Now a reservation holds
only as many slots as the primary has FRESH rows, and the rest pass to the secondary.

The negative controls matter as much as the fix: cooled rows must never be REMOVED
(the lane size is the honest pool), omitting the counts must leave the old behaviour,
and when the secondary has nothing fresh either the share is unchanged.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp  # noqa: E402


def rows(*ids):
    return [{"id": i, "why": ""} for i in ids]


def ids(out):
    return [r["id"] for r in out]


class ReservedQuotaFlow(unittest.TestCase):

    def test_fully_cooled_primary_passes_its_slots_on(self):
        primary = rows("G1", "G2", "G3")          # all cooled
        secondary = rows("C1", "C2", "C3", "C4", "C5", "C6")
        out, pq, sq = sp.compose_share(primary, secondary, 6, 0.5,
                                       primary_hot=0, secondary_hot=6)
        self.assertEqual((pq, sq), (0, 6))
        self.assertEqual(ids(out)[:6], ["C1", "C2", "C3", "C4", "C5", "C6"])

    def test_partly_cooled_primary_keeps_only_its_fresh_rows(self):
        primary = rows("G1", "G2", "G3")          # G1 fresh, G2-G3 cooled (at the back)
        secondary = rows("C1", "C2", "C3", "C4", "C5")
        out, pq, sq = sp.compose_share(primary, secondary, 6, 0.5,
                                       primary_hot=1, secondary_hot=5)
        self.assertEqual((pq, sq), (1, 5))
        self.assertEqual(ids(out)[:6], ["G1", "C1", "C2", "C3", "C4", "C5"])

    def test_cooled_rows_are_never_removed(self):
        primary = rows("G1", "G2", "G3")
        secondary = rows("C1", "C2", "C3", "C4")
        out, _, _ = sp.compose_share(primary, secondary, 4, 0.5,
                                     primary_hot=0, secondary_hot=4)
        self.assertEqual(sorted(ids(out)), sorted(ids(primary + secondary)))

    def test_counts_omitted_keeps_the_old_share(self):
        primary = rows("G1", "G2", "G3")
        secondary = rows("C1", "C2", "C3", "C4")
        out, pq, sq = sp.compose_share(primary, secondary, 6, 0.5)
        self.assertEqual((pq, sq), (3, 3))

    def test_secondary_with_nothing_fresh_keeps_the_share(self):
        primary = rows("G1", "G2", "G3")
        secondary = rows("C1", "C2", "C3", "C4")
        _, pq, sq = sp.compose_share(primary, secondary, 6, 0.5,
                                     primary_hot=0, secondary_hot=0)
        self.assertEqual((pq, sq), (3, 3))

    def test_fresh_primary_keeps_its_full_share(self):
        primary = rows("G1", "G2", "G3", "G4")
        secondary = rows("C1", "C2", "C3", "C4", "C5")
        _, pq, _ = sp.compose_share(primary, secondary, 6, 0.5,
                                    primary_hot=4, secondary_hot=5)
        self.assertEqual(pq, 3)


if __name__ == "__main__":
    unittest.main()
