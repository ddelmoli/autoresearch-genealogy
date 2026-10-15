#!/usr/bin/env python3
"""Pins the EXPAND offline-route demotion in session_plan.py (operator ruling
15 OCT 2026, deferred 74 option 1).

WHAT IS BEING DEFENDED. A row whose declared `route` names an archive that is not
online cannot be advanced from a desk, but EXPAND's offer cooldown returned it at
its old rank every few sittings: on the reference vault one pair was drawn six
times, each time recorded "not worked". The fix DEMOTES such rows behind every
workable row. It must never REMOVE them: a demotion that quietly drops rows would
look exactly like a working plan, which is why most tests here are negative
controls on length and membership.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp  # noqa: E402


def hist(*sittings):
    return [{"date": "2026-10-01", "lane": "EXPAND", "outcome": "miss", "session": s}
            for s in sittings]


def rows(spec):
    """spec: list of (id, route-or-None)."""
    return [{"id": i, "route": r, "why": ""} for i, r in spec]


OFFLINE = sp.offline_route_predicate(["como-diocesan", "laquila-diocesan"])


class Predicate(unittest.TestCase):
    def test_empty_list_is_inert(self):
        self.assertIsNone(sp.offline_route_predicate([]))
        self.assertIsNone(sp.offline_route_predicate(None))
        self.assertIsNone(sp.offline_route_predicate(["", "  "]))

    def test_matches_case_insensitively_and_only_listed_slugs(self):
        self.assertTrue(OFFLINE({"route": "Como-Diocesan"}))
        self.assertFalse(OFFLINE({"route": "medlands"}))
        self.assertFalse(OFFLINE({"route": None}))
        self.assertFalse(OFFLINE({}))

    def test_framework_default_demotes_nothing(self):
        self.assertIsNone(sp.offline_route_predicate(sp.OFFLINE_ROUTES))


class Demotion(unittest.TestCase):
    def test_offline_rows_go_behind_every_workable_row(self):
        rs = rows([("A", "como-diocesan"), ("B", None), ("C", "medlands"),
                   ("D", "laquila-diocesan"), ("E", None)])
        out, _ = sp.rotate_candidates(rs, {"history": hist(1)}, "EXPAND", 2,
                                      demote=OFFLINE)
        ids = [r["id"] for r in out]
        self.assertEqual(set(ids[-2:]), {"A", "D"})
        self.assertEqual(set(ids[:3]), {"B", "C", "E"})

    def test_never_removes_a_row(self):
        rs = rows([(f"P{i}", "como-diocesan" if i % 2 else None) for i in range(20)])
        out, _ = sp.rotate_candidates(rs, {"history": hist(1)}, "EXPAND", 6,
                                      demote=OFFLINE)
        self.assertEqual(len(out), len(rs))
        self.assertEqual({r["id"] for r in out}, {r["id"] for r in rs})

    def test_all_offline_is_ordered_as_live_not_emptied(self):
        rs = rows([("A", "como-diocesan"), ("B", "como-diocesan")])
        out, n_cold = sp.rotate_candidates(rs, {"history": hist(1)}, "EXPAND", 1,
                                           demote=OFFLINE)
        self.assertEqual(len(out), 2)
        self.assertEqual(n_cold, 0)

    def test_cooled_rows_still_come_last(self):
        rs = rows([("A", "como-diocesan"), ("B", None), ("C", None)])
        st = {"history": hist(1, 2), "offered": {"EXPAND": {"C": "S2"}}}
        out, n_cold = sp.rotate_candidates(rs, st, "EXPAND", 1, demote=OFFLINE)
        self.assertEqual([r["id"] for r in out], ["B", "A", "C"])
        self.assertEqual(n_cold, 1)

    def test_no_predicate_leaves_the_order_unchanged(self):
        rs = rows([("A", "como-diocesan"), ("B", None)])
        with_none, _ = sp.rotate_candidates(rs, {"history": hist(1)}, "EXPAND", 2)
        explicit, _ = sp.rotate_candidates(rs, {"history": hist(1)}, "EXPAND", 2,
                                           demote=None)
        self.assertEqual([r["id"] for r in with_none], [r["id"] for r in explicit])


if __name__ == "__main__":
    unittest.main()
