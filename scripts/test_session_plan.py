#!/usr/bin/env python3
"""Pin session_plan's lane-bandit draw logic (pure function, no vault needed).

The rules under test, in precedence order:
  1. bootstrap floor — no exploitation while any live lane is undersampled
  2. staleness floor — a lane undrawn for stale_after draws is due
  3. exploit — highest Laplace-smoothed win rate
Plus: empty lanes never drawn; record() arithmetic.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp  # noqa: E402

ALL_FULL = {"EXPAND": 10, "IMPROVE": 10, "VERIFY": 10, "ROTATE": 10}


def arms(**kw):
    """State with the given arms; history long enough that no lane is stale."""
    hist = [{"lane": ln} for ln in kw] * 3
    return {"arms": {ln: {"sessions": s, "wins": w} for ln, (s, w) in kw.items()},
            "history": hist, "pending": None}


class DrawTests(unittest.TestCase):
    def test_empty_state_bootstraps_first_lane(self):
        lane, reason = sp.draw_lane({"arms": {}, "history": []}, ALL_FULL)
        self.assertEqual(lane, "EXPAND")
        self.assertIn("bootstrap", reason)

    def test_bootstrap_prefers_least_sampled(self):
        st = arms(EXPAND=(2, 2), IMPROVE=(2, 0), VERIFY=(1, 1), ROTATE=(0, 0))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "ROTATE")
        self.assertIn("bootstrap", reason)

    def test_no_exploitation_on_tiny_n_even_with_perfect_record(self):
        # EXPAND is 1-for-1 (rate 1.0) but VERIFY is unsampled: floor wins.
        st = arms(EXPAND=(1, 1), IMPROVE=(2, 0), VERIFY=(0, 0), ROTATE=(2, 1))
        lane, _ = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "VERIFY")

    def test_empty_lane_never_drawn(self):
        st = {"arms": {}, "history": []}
        sizes = {"EXPAND": 0, "IMPROVE": 5, "VERIFY": 0, "ROTATE": 0}
        lane, _ = sp.draw_lane(st, sizes)
        self.assertEqual(lane, "IMPROVE")

    def test_all_lanes_empty(self):
        lane, reason = sp.draw_lane({"arms": {}, "history": []},
                                    {ln: 0 for ln in sp.LANES})
        self.assertIsNone(lane)
        self.assertIn("empty", reason)

    def test_staleness_floor_beats_exploit(self):
        # All sampled past the floor; VERIFY absent from the recent window.
        st = arms(EXPAND=(6, 5), IMPROVE=(6, 1), VERIFY=(2, 0), ROTATE=(6, 2))
        st["history"] = [{"lane": ln} for ln in
                        ("EXPAND", "IMPROVE", "ROTATE", "EXPAND", "IMPROVE", "ROTATE")]
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "VERIFY")
        self.assertIn("staleness", reason)

    def test_exploit_picks_best_smoothed_rate(self):
        st = arms(EXPAND=(6, 5), IMPROVE=(6, 1), VERIFY=(6, 3), ROTATE=(6, 2))
        st["history"] = [{"lane": ln} for ln in
                        ("EXPAND", "IMPROVE", "VERIFY", "ROTATE", "EXPAND", "IMPROVE")]
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "EXPAND")  # (5+1)/(6+2) = 0.75, the max
        self.assertIn("exploit", reason)

    def test_exploit_tie_breaks_by_lane_order(self):
        st = arms(EXPAND=(6, 3), IMPROVE=(6, 3), VERIFY=(6, 3), ROTATE=(6, 3))
        st["history"] = [{"lane": ln} for ln in
                        ("ROTATE", "VERIFY", "IMPROVE", "EXPAND", "ROTATE", "VERIFY")]
        lane, _ = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "EXPAND")


class RecordTests(unittest.TestCase):
    def test_record_hit_and_miss(self):
        st = {"arms": {}, "history": [], "pending": {"date": "2026-07-29", "lane": "EXPAND"}}
        st = sp.record(st, "EXPAND", "hit", "note")
        st = sp.record(st, "EXPAND", "miss")
        self.assertEqual(st["arms"]["EXPAND"], {"sessions": 2, "wins": 1})
        self.assertEqual(len(st["history"]), 2)
        self.assertIsNone(st["pending"])
        self.assertEqual(st["history"][0].get("note"), "note")

    def test_lane_target_percent_precedence(self):
        """** THE LANE TARGET IS A PERCENT OF THE VAULT, NOT A ROW COUNT ** (operator,
        30 JUL 2026: "lane targets should use the sample size metric"). Same form as
        profile_review's sample rate, so one number describes a session's workload
        whatever lane is drawn, and it scales with the vault instead of ageing.

        Precedence pinned here because it spans TWO config blocks: it falls back to
        `profile_review.sample_percent` so a vault that sets one rate gets both loops,
        and that cross-block fallback is the part a later refactor would silently drop.
        """
        import tempfile, json as _j, os as _o, shutil
        tmp = tempfile.mkdtemp(prefix="sp_lt_")
        try:
            with open(_o.path.join(tmp, ".maintenance.json"), "w") as f:
                _j.dump({"profile_review": {"sample_percent": 2.0}}, f)
            _r, pct, src = sp.resolve_lane_target(tmp, {})
            self.assertEqual((pct, src), (2.0, "sample_percent"),
                             "falls back to the profile-review rate")
            _r, pct, src = sp.resolve_lane_target(tmp, {"lane_target_percent": 4.0})
            self.assertEqual((pct, src), (4.0, "config"),
                             "its own config key wins over the fallback")
            _r, pct, src = sp.resolve_lane_target(tmp, {"lane_target_percent": 4.0}, 7.5)
            self.assertEqual((pct, src), (7.5, "session-override"),
                             "a per-session override wins over both")
            with self.assertRaises(SystemExit):
                sp.resolve_lane_target(tmp, {}, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_record_rejects_unknown_lane_and_outcome(self):
        with self.assertRaises(SystemExit):
            sp.record({"arms": {}, "history": []}, "NOPE", "hit")
        with self.assertRaises(SystemExit):
            sp.record({"arms": {}, "history": []}, "EXPAND", "maybe")


if __name__ == "__main__":
    unittest.main()
