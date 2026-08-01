#!/usr/bin/env python3
"""Pins the candidate-rotation contract in session_plan.py (operator-directed,
01 AUG 2026, session #127).

WHAT IS BEING DEFENDED. Three of the four lanes ranked candidates with a
deterministic sort and took the top N, so a row that was open but HARD sat at the
head of its lane every session for ever. On the reference vault one parent edge was
walked and classified a permanent FS-GAP in three separate sittings and still ranked
first in the next draw. The fix is a cooldown (a guarantee) plus a seeded stratified sample
(variety), NOT randomisation on its own -- a shuffle can hand you the same row
twice running, and it would throw away the real priority that gen-ascending
encodes.

The tests below are mostly NEGATIVE CONTROLS, because every failure mode here is
silent: a rotation that quietly drops rows, or a cooldown that never expires, or a
stamp that fires when nobody worked the lane, all look like a working plan.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp  # noqa: E402


def hist(*sittings):
    """History with one observation per named sitting, oldest first."""
    return [{"date": "2026-08-01", "lane": "VERIFY", "outcome": "hit", "session": s}
            for s in sittings]


def rows(n, prefix="P-"):
    return [{"id": f"{prefix}{i:05d}", "name": f"row {i}", "gen": i} for i in range(n)]


class TestCooling(unittest.TestCase):
    def test_unstamped_row_is_not_cooling(self):
        st = {"history": hist(1, 2, 3)}
        self.assertEqual(sp.cooling(st, "VERIFY", "P-00001"), (False, None))

    def test_row_stamped_this_sitting_is_cooling(self):
        st = {"history": hist(1, 2, 3), "offered": {"VERIFY": {"P-00001": "S3"}}}
        is_cool, since = sp.cooling(st, "VERIFY", "P-00001")
        self.assertTrue(is_cool)
        self.assertEqual(since, 0)

    def test_cooldown_expires_after_OFFER_COOLDOWN_sittings(self):
        # stamped at S1, and S1..S4 have happened -> 3 sittings since -> expired
        st = {"history": hist(1, 2, 3, 4), "offered": {"VERIFY": {"P-00001": "S1"}}}
        is_cool, since = sp.cooling(st, "VERIFY", "P-00001")
        self.assertEqual(since, 3)
        self.assertFalse(is_cool, "a row must come BACK; a cooldown that never expires "
                                  "is just a deletion")

    def test_still_cooling_one_sitting_before_expiry(self):
        st = {"history": hist(1, 2, 3), "offered": {"VERIFY": {"P-00001": "S1"}}}
        self.assertTrue(sp.cooling(st, "VERIFY", "P-00001")[0])

    def test_unknown_stamp_reads_cold_not_error(self):
        """History is trimmed by epoch; an unreadable stamp must not pin a row for ever."""
        st = {"history": hist(5, 6), "offered": {"VERIFY": {"P-00001": "S1"}}}
        self.assertEqual(sp.cooling(st, "VERIFY", "P-00001"), (False, None))

    def test_cooldown_is_PER_LANE(self):
        """Offering someone in VERIFY must not cool them in EXPAND -- different work."""
        st = {"history": hist(1), "offered": {"VERIFY": {"P-00001": "S1"}}}
        self.assertTrue(sp.cooling(st, "VERIFY", "P-00001")[0])
        self.assertFalse(sp.cooling(st, "EXPAND", "P-00001")[0])

    def test_keyed_on_vault_id_not_external_pid(self):
        """NEGATIVE CONTROL for the 30 JUL 2026 ROTATE bug: profile_review PRINTED the
        FS PID but keyed the cooldown on the vault id, so recording the displayed key
        never entered cooldown and the same people were redrawn every session."""
        st = {"history": hist(1), "offered": {"VERIFY": {"XXXX-XXX": "S1"}}}
        self.assertFalse(sp.cooling(st, "VERIFY", "P-00001")[0],
                         "an FS PID in the store must not cool a vault id")


class TestRotate(unittest.TestCase):
    def test_length_is_always_preserved(self):
        """It REORDERS, never filters -- the lane size must stay honest."""
        st = {"history": hist(1), "offered": {"VERIFY": {"P-00000": "S1", "P-00002": "S1"}}}
        out, n_cool = sp.rotate_candidates(rows(10), st, "VERIFY", target=6)
        self.assertEqual(len(out), 10)
        self.assertEqual(n_cool, 2)
        self.assertEqual({r["id"] for r in out}, {r["id"] for r in rows(10)})

    def test_cooled_rows_go_to_the_back(self):
        st = {"history": hist(1), "offered": {"VERIFY": {"P-00000": "S1", "P-00001": "S1"}}}
        out, _ = sp.rotate_candidates(rows(10), st, "VERIFY", target=6)
        self.assertEqual({out[-1]["id"], out[-2]["id"]}, {"P-00000", "P-00001"})

    def test_priority_head_survives_the_sample(self):
        """gen-ascending is real priority; the top of the order must still be offered."""
        out, _ = sp.rotate_candidates(rows(30), {"history": []}, "VERIFY", target=21)
        head_k = max(1, 21 // sp.HEAD_FRACTION)
        self.assertEqual([r["id"] for r in out[:head_k]],
                         [r["id"] for r in rows(30)[:head_k]])

    def test_sample_reaches_past_the_head(self):
        """The whole point: rows a strict top-N would never reach must appear."""
        out, _ = sp.rotate_candidates(rows(60), {"history": []}, "VERIFY", target=21)
        offered = [r["gen"] for r in out[:21]]
        self.assertTrue(max(offered) > 21,
                        "a deep row should surface; got %r" % (offered,))

    def test_all_cooling_returns_plain_order(self):
        """Deprioritising everything is meaningless, and emptying the lane is a lie."""
        st = {"history": hist(1),
              "offered": {"VERIFY": {f"P-{i:05d}": "S1" for i in range(5)}}}
        out, n_cool = sp.rotate_candidates(rows(5), st, "VERIFY", target=3)
        self.assertEqual([r["id"] for r in out], [r["id"] for r in rows(5)])
        self.assertEqual(n_cool, 5)

    def test_empty_lane_is_safe(self):
        self.assertEqual(sp.rotate_candidates([], {"history": []}, "VERIFY", 21), ([], 0))

    def test_stable_within_a_sitting(self):
        """The plan is run several times per iteration; the printed list must not move."""
        st = {"history": hist(1, 2)}
        a, _ = sp.rotate_candidates(rows(40), st, "VERIFY", target=21)
        b, _ = sp.rotate_candidates(rows(40), st, "VERIFY", target=21)
        self.assertEqual([r["id"] for r in a], [r["id"] for r in b])

    def test_resamples_once_an_observation_is_recorded(self):
        a, _ = sp.rotate_candidates(rows(40), {"history": hist(1, 2)}, "VERIFY", 21)
        b, _ = sp.rotate_candidates(rows(40), {"history": hist(1, 2, 3)}, "VERIFY", 21)
        self.assertNotEqual([r["id"] for r in a], [r["id"] for r in b],
                            "the next iteration should see a different sample")

    def test_different_lanes_sample_differently(self):
        st = {"history": hist(1)}
        a, _ = sp.rotate_candidates(rows(40), st, "VERIFY", 21)
        b, _ = sp.rotate_candidates(rows(40), st, "EXPAND", 21)
        self.assertNotEqual([r["id"] for r in a], [r["id"] for r in b])


class TestVerifyShare(unittest.TestCase):
    """VERIFY carries two populations of wildly different size (~34 edges vs ~1,131
    unconfirmed PIDs on the reference vault). Merged and sampled, the edge rows would
    be 3% of the lane -- half a row per draw -- and the work the lane exists for would
    vanish. The share fixes the edge quota FIRST."""

    def edges(self, n):
        return [{"id": f"E-{i:05d}", "name": f"edge {i}", "gen": i} for i in range(n)]

    def pids(self, n):
        return [{"id": f"P-{i:05d}", "_cool_key": f"pid:P-{i:05d}",
                 "name": f"pid {i}", "gen": i} for i in range(n)]

    def test_edges_are_reserved_before_pids_get_any(self):
        out, eq, pq = sp.compose_verify(self.edges(34), self.pids(1131), target=21)
        self.assertEqual(eq, 10)
        self.assertEqual(pq, 11)
        self.assertTrue(all(r["id"].startswith("E-") for r in out[:eq]))
        self.assertTrue(all(r["id"].startswith("P-") for r in out[eq:eq + pq]))

    def test_the_swamping_scenario_is_what_this_prevents(self):
        """NEGATIVE CONTROL: a plain merge would return ~0 edge rows in the draw."""
        merged = self.edges(34) + self.pids(1131)
        naive = sum(1 for r in merged[:21] if r["id"].startswith("E-"))
        out, _, _ = sp.compose_verify(self.edges(34), self.pids(1131), 21)
        shared = sum(1 for r in out[:21] if r["id"].startswith("E-"))
        self.assertGreater(shared, 0)
        self.assertEqual(shared, 10)
        # the naive merge only looks fine because these fixtures are ordered; the
        # real builder SAMPLES, which is what drops edges to ~3% of the draw.
        self.assertEqual(naive, 21)

    def test_short_edge_pool_gives_its_quota_back_to_pids(self):
        out, eq, pq = sp.compose_verify(self.edges(3), self.pids(100), target=21)
        self.assertEqual(eq, 3)
        self.assertEqual(pq, 18)
        self.assertEqual(len(out), 103, "composition must never drop rows")

    def test_no_edges_at_all(self):
        out, eq, pq = sp.compose_verify([], self.pids(50), target=21)
        self.assertEqual((eq, pq), (0, 21))
        self.assertEqual(len(out), 50)

    def test_no_pids_at_all(self):
        out, eq, pq = sp.compose_verify(self.edges(50), [], target=21)
        self.assertEqual(eq, 10)
        self.assertEqual(len(out), 50)

    def test_everything_is_preserved(self):
        out, _, _ = sp.compose_verify(self.edges(9), self.pids(9), target=21)
        self.assertEqual(sorted(r["id"] for r in out),
                         sorted([r["id"] for r in self.edges(9)]
                                + [r["id"] for r in self.pids(9)]))


class TestCoolKeyNamespacing(unittest.TestCase):
    def test_pid_row_uses_a_namespaced_key(self):
        self.assertEqual(sp.cool_key({"id": "P-00001", "_cool_key": "pid:P-00001"}),
                         "pid:P-00001")

    def test_edge_row_uses_the_bare_vault_id(self):
        self.assertEqual(sp.cool_key({"id": "P-00001"}), "P-00001")

    def test_the_two_kinds_of_work_cool_INDEPENDENTLY(self):
        """Same person, two jobs. Offering the PID check must not hide the `?` edge."""
        st = {"history": hist(1), "offered": {"VERIFY": {"pid:P-00001": "S1"}}}
        self.assertTrue(sp.cooling(st, "VERIFY", "pid:P-00001")[0])
        self.assertFalse(sp.cooling(st, "VERIFY", "P-00001")[0])


class TestStampOnRecord(unittest.TestCase):
    def _pending(self, lane="VERIFY"):
        return {"arms": {}, "history": [], "offered": {},
                "pending": {"date": "2026-08-01", "lane": lane,
                            "offered": ["P-00001", "P-00002"]}}

    def test_recording_the_drawn_lane_stamps_its_offers(self):
        st = sp.record(self._pending(), "VERIFY", "hit", session=127, today="2026-08-01")
        self.assertEqual(st["offered"]["VERIFY"], {"P-00001": "S127", "P-00002": "S127"})
        self.assertIsNone(st["pending"])

    def test_the_stamped_rows_read_as_cooling_immediately(self):
        st = sp.record(self._pending(), "VERIFY", "hit", session=127, today="2026-08-01")
        self.assertTrue(sp.cooling(st, "VERIFY", "P-00001")[0])

    def test_working_a_DIFFERENT_lane_cools_nothing(self):
        """NEGATIVE CONTROL. Overriding the draw is allowed and explicitly supported;
        nobody looked at the drawn lane's rows, so they must stay hot."""
        st = sp.record(self._pending("VERIFY"), "IMPROVE", "hit",
                       session=127, today="2026-08-01")
        self.assertEqual(st.get("offered", {}).get("VERIFY", {}), {})
        self.assertIsNotNone(st["pending"], "an unconsumed draw must survive")

    def test_no_pending_means_no_stamp(self):
        st = {"arms": {}, "history": [], "pending": None}
        st = sp.record(st, "VERIFY", "hit", session=127, today="2026-08-01")
        self.assertEqual(st.get("offered", {}), {})

    def test_legacy_pending_without_offered_is_safe(self):
        """State written before this change carries no `offered` key."""
        st = {"arms": {}, "history": [],
              "pending": {"date": "2026-08-01", "lane": "VERIFY"}}
        st = sp.record(st, "VERIFY", "hit", session=127, today="2026-08-01")
        self.assertIsNone(st["pending"])
        self.assertEqual(st.get("offered", {}).get("VERIFY", {}), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
