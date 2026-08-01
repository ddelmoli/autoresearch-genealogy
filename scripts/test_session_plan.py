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


def hist(*lanes_per_sitting):
    """History from an explicit list of sittings: hist(("EXPAND","IMPROVE"), ("VERIFY",))
    is two sittings, the first of which worked two lanes."""
    out = []
    for i, lanes in enumerate(lanes_per_sitting, start=1):
        for ln in lanes:
            out.append({"date": "2026-07-31", "lane": ln, "outcome": "hit", "session": i})
    return out


# Two sittings for every lane: enough to clear the bootstrap floor, so a test that
# is about STALENESS or EXPLOIT is not silently answered by the floor above it.
WARMUP = (("EXPAND",), ("IMPROVE",), ("VERIFY",), ("ROTATE",)) * 2


def arms(sittings=WARMUP, **kw):
    """State with the given arms over an explicit list of SITTINGS.

    Each arm is (iterations, wins) -- the reward unit. The floors read the history
    instead, because they count SITTINGS; keeping the two apart is what the 31 JUL
    fix is about, and it is why this helper has to build both consistently."""
    return {"arms": {ln: {"iterations": n, "wins": w} for ln, (n, w) in kw.items()},
            "history": hist(*sittings), "pending": None}


class DrawTests(unittest.TestCase):
    def test_empty_state_bootstraps_first_lane(self):
        lane, reason = sp.draw_lane({"arms": {}, "history": []}, ALL_FULL)
        self.assertEqual(lane, "EXPAND")
        self.assertIn("bootstrap", reason)

    def test_bootstrap_prefers_least_sampled(self):
        # ROTATE has been worked in no sitting at all; VERIFY in one.
        st = arms((("EXPAND",), ("EXPAND",), ("IMPROVE",), ("IMPROVE",), ("VERIFY",)),
                  EXPAND=(2, 2), IMPROVE=(2, 0), VERIFY=(1, 1), ROTATE=(0, 0))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "ROTATE")
        self.assertIn("bootstrap", reason)

    def test_no_exploitation_on_tiny_n_even_with_perfect_record(self):
        # EXPAND is 1-for-1 (rate 1.0) but VERIFY is unsampled: floor wins.
        st = arms((("EXPAND",), ("IMPROVE",), ("IMPROVE",), ("ROTATE",), ("ROTATE",)),
                  EXPAND=(1, 1), IMPROVE=(2, 0), VERIFY=(0, 0), ROTATE=(2, 1))
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
        st = arms(WARMUP + (("EXPAND",), ("IMPROVE",), ("ROTATE",),
                            ("EXPAND",), ("IMPROVE",), ("ROTATE",)),
                  EXPAND=(6, 5), IMPROVE=(6, 1), VERIFY=(2, 0), ROTATE=(6, 2))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "VERIFY")
        self.assertIn("staleness", reason)

    def test_exploit_picks_best_smoothed_rate(self):
        st = arms(WARMUP + (("EXPAND",), ("IMPROVE",), ("VERIFY",),
                            ("ROTATE",), ("EXPAND",), ("IMPROVE",)),
                  EXPAND=(6, 5), IMPROVE=(6, 1), VERIFY=(6, 3), ROTATE=(6, 2))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "EXPAND")  # (5+1)/(6+2) = 0.75, the max
        self.assertIn("exploit", reason)

    def test_exploit_tie_breaks_by_lane_order(self):
        st = arms(WARMUP + (("ROTATE",), ("VERIFY",), ("IMPROVE",),
                            ("EXPAND",), ("ROTATE",), ("VERIFY",)),
                  EXPAND=(6, 3), IMPROVE=(6, 3), VERIFY=(6, 3), ROTATE=(6, 3))
        lane, _ = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "EXPAND")


class SittingTests(unittest.TestCase):
    """** THE FLOORS COUNT SITTINGS, NOT OBSERVATIONS (31 JUL 2026). **

    They were written when one sitting produced one observation. `Iterations: N`
    (30 JUL) broke that silently: a ten-draw afternoon satisfied the bootstrap floor
    and closed the staleness window by itself, so the bandit behaved as though ten
    sessions had passed."""

    def test_many_iterations_in_one_sitting_do_not_satisfy_the_bootstrap_floor(self):
        # EXPAND worked ten times, all in sitting #1. That is ONE sample.
        st = {"arms": {"EXPAND": {"iterations": 10, "wins": 10}},
              "history": hist(("EXPAND",) * 10), "pending": None}
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertIn("bootstrap", reason)
        self.assertNotEqual(lane, "EXPAND")

    def test_staleness_window_is_sittings_not_observations(self):
        # One huge sitting cannot age VERIFY out of the window on its own.
        base = dict(EXPAND=(2, 2), IMPROVE=(2, 2), VERIFY=(2, 2), ROTATE=(2, 2))
        # A twenty-iteration EXPAND sitting is ONE sitting, so VERIFY is still inside
        # a two-sitting window. Under the old observation-counting it was long gone.
        st = arms(WARMUP + (("VERIFY",), ("EXPAND",) * 20), **base)
        lane, _ = sp.draw_lane(st, ALL_FULL, stale_after=2)
        self.assertNotEqual(lane, "VERIFY")
        # Three more sittings and it has genuinely aged out. (stale_after=3 so that
        # VERIFY is the ONLY stale lane; with a 2-window EXPAND is stale too and wins
        # on lane order, which would prove nothing about the unit under test.)
        st = arms(WARMUP + (("VERIFY",), ("EXPAND",), ("IMPROVE",), ("ROTATE",)), **base)
        lane, reason = sp.draw_lane(st, ALL_FULL, stale_after=3)
        self.assertEqual(lane, "VERIFY")
        self.assertIn("staleness", reason)

    def test_legacy_rows_without_a_session_fall_back_to_the_date(self):
        st = {"arms": {}, "history": [{"date": "2026-07-30", "lane": "EXPAND"},
                                      {"date": "2026-07-30", "lane": "EXPAND"}],
              "pending": None}
        self.assertEqual(len(sp.sittings_in_order(st["history"])), 1)

    def test_arm_of_accepts_the_legacy_sessions_key(self):
        st = {"arms": {"EXPAND": {"sessions": 4, "wins": 3}}}
        self.assertEqual(sp.arm_of(st, "EXPAND"), {"wins": 3, "iterations": 4})


class ResetEpochTests(unittest.TestCase):
    """** A RESET RESETS BOTH HALVES. ** Zeroing `arms` while the floors still read the
    whole of `history` sends the draw straight to exploit at the 0.50 prior, where the
    tie-break hands out one lane repeatedly -- observed on the reference vault the
    moment its arms were reset."""

    def test_pre_reset_observations_do_not_satisfy_the_bootstrap_floor(self):
        st = {"arms": {}, "pending": None,
              "arms_reset": {"date": "2026-07-31"},
              "history": [{"date": "2026-07-29", "lane": ln, "outcome": "hit"}
                          for ln in ("EXPAND", "IMPROVE", "VERIFY", "ROTATE")] * 3}
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertIn("bootstrap", reason)

    def test_post_reset_observations_do_count(self):
        st = {"arms": {}, "pending": None, "arms_reset": {"date": "2026-07-31"},
              "history": [{"date": "2026-08-0%d" % d, "lane": ln, "outcome": "hit",
                           "session": 100 + d}
                          for d in (1, 2) for ln in sp.LANES]}
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertNotIn("bootstrap", reason)

    def test_no_epoch_means_all_history_counts(self):
        st = {"arms": {}, "pending": None,
              "history": [{"date": "2026-07-29", "lane": ln, "outcome": "hit",
                           "session": s} for s in (1, 2) for ln in sp.LANES]}
        _, reason = sp.draw_lane(st, ALL_FULL)
        self.assertNotIn("bootstrap", reason)


class PendingGuardTests(unittest.TestCase):
    """** A RECORD CLEARS ONLY THE DRAW IT CONSUMED (31 JUL 2026). **

    `record()` used to clear `pending` unconditionally, so a plan run for the NEXT
    session and then recorded over lost the draw it had just registered -- the Handoff
    announced an EXPAND draw the state file did not hold."""

    def test_record_clears_the_draw_it_consumed(self):
        st = {"arms": {}, "history": [], "pending": {"date": "2026-07-30", "lane": "EXPAND"}}
        st = sp.record(st, "EXPAND", "hit", today="2026-07-31")
        self.assertIsNone(st["pending"])

    def test_record_does_not_clear_a_draw_for_a_different_lane(self):
        st = {"arms": {}, "history": [], "pending": {"date": "2026-07-31", "lane": "ROTATE"}}
        st = sp.record(st, "EXPAND", "hit", today="2026-07-31")
        self.assertEqual(st["pending"], {"date": "2026-07-31", "lane": "ROTATE"})

    def test_record_does_not_clear_a_draw_registered_after_the_work(self):
        st = {"arms": {}, "history": [], "pending": {"date": "2026-08-01", "lane": "EXPAND"}}
        st = sp.record(st, "EXPAND", "hit", today="2026-07-31")
        self.assertEqual(st["pending"]["date"], "2026-08-01")

    def test_record_stamps_the_sitting(self):
        st = sp.record({"arms": {}, "history": [], "pending": None},
                       "VERIFY", "miss", session=124, today="2026-07-31")
        self.assertEqual(st["history"][-1]["session"], 124)


class RecordTests(unittest.TestCase):
    def test_record_hit_and_miss(self):
        st = {"arms": {}, "history": [], "pending": {"date": "2026-07-29", "lane": "EXPAND"}}
        st = sp.record(st, "EXPAND", "hit", "note")
        st = sp.record(st, "EXPAND", "miss")
        self.assertEqual(st["arms"]["EXPAND"], {"iterations": 2, "wins": 1})
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

    def test_lane_target_is_never_capped_to_lane_size(self):
        """** THE TARGET IS NOT CAPPED TO THE LANE SIZE ** (operator, 31 JUL 2026: "I don't
        see any value in the cap").

        main() used to print `min(lane_target, lane_size)`, which turned an EMPTY LANE into
        a met goal: with 1 candidate it printed "LANE TARGET: 1", so any work at all was a
        full-strength hit. Same "an arm that never loses carries no signal" defect the arms
        reset was called to fix. It had already fired -- IMPROVE was drawn twice under the
        new hit rule and capped BOTH times (5 of 21, then 1 of 21), so the configured target
        had never once been tested.

        Every case carries its negative control, because the risk of this change is
        over-reporting dryness on a healthy lane.
        """
        # the case that motivated it: lane far smaller than target
        self.assertEqual(sp.target_and_dryness(21, 1), (21, True),
                         "a 1-row lane must still report the full target, and flag dryness")
        # NEGATIVE CONTROL: a lane bigger than target is NOT dry and must not be flagged
        self.assertEqual(sp.target_and_dryness(21, 305), (21, False),
                         "a healthy lane is not dry")
        # boundary: exactly enough is NOT dry
        self.assertEqual(sp.target_and_dryness(21, 21), (21, False),
                         "lane_size == target is reachable, not dry")
        self.assertEqual(sp.target_and_dryness(21, 20), (21, True),
                         "one short IS dry")
        # an empty lane reports the target and is dry -- it never reports 0
        self.assertEqual(sp.target_and_dryness(21, 0), (21, True),
                         "an empty lane must not print a target of 0")

    def test_per_lane_epoch_retires_only_that_lane(self):
        """** A LANE WHOSE DEFINITION CHANGES NEEDS ITS OWN RESET ** (deferred 24,
        31 JUL 2026). IMPROVE was redefined from keystone LOAD x THIN to the
        SOURCE_GAP harvest worklist, so its old observations describe a population
        the lane no longer draws from -- while EXPAND/VERIFY/ROTATE observations
        stay perfectly valid.

        A GLOBAL reset would have thrown away three good arms to fix one, which is
        why `lane_epochs` exists and why it COMPOSES with `arms_reset.date` instead
        of replacing it.
        """
        st = {"history": [
            {"date": "2026-07-30", "lane": "IMPROVE", "outcome": "hit"},
            {"date": "2026-07-30", "lane": "VERIFY", "outcome": "hit"},
            {"date": "2026-08-02", "lane": "IMPROVE", "outcome": "miss"},
            {"date": "2026-08-02", "lane": "VERIFY", "outcome": "hit"},
        ]}
        # no epochs at all -> everything is visible (the pre-existing behaviour)
        self.assertEqual(len(sp.since_epoch(st)), 4, "absent epochs must change nothing")

        # a PER-LANE epoch retires only that lane's older rows
        st["lane_epochs"] = {"IMPROVE": "2026-08-01"}
        seen = sp.since_epoch(st)
        improve = [h for h in seen if h["lane"] == "IMPROVE"]
        verify = [h for h in seen if h["lane"] == "VERIFY"]
        self.assertEqual(len(improve), 1, "IMPROVE's pre-epoch row is retired")
        self.assertEqual(improve[0]["date"], "2026-08-02")
        # NEGATIVE CONTROL: the other lane is untouched. If this ever drops to 1 the
        # per-lane epoch has become global again, which is the whole thing it avoids.
        self.assertEqual(len(verify), 2, "a per-lane epoch must NOT touch other lanes")

        # it COMPOSES with the global epoch rather than overriding it
        st["arms_reset"] = {"date": "2026-08-02"}
        seen = sp.since_epoch(st)
        self.assertEqual(len(seen), 2, "the global epoch still applies to every lane")
        self.assertTrue(all(h["date"] >= "2026-08-02" for h in seen))

        # and the history itself is never mutated -- the record is kept, only the
        # FLOORS' view narrows
        self.assertEqual(len(st["history"]), 4, "since_epoch must not drop rows from history")

    def test_harvestable_pid(self):
        """IMPROVE only offers entries a Recipe-S harvest can actually run against."""
        # Placeholders, never real PIDs: this is the PUBLIC repo, and a record
        # identifier is a pointer to a person even with no name beside it.
        for good in ("ABCD-123", "  EFGH-4JK "):
            self.assertTrue(sp.harvestable_pid(good), good)
        # NEGATIVE CONTROLS: the placeholders the vault uses for "not looked up yet"
        # and "looked, none exists" are NOT harvestable and must never enter the lane.
        for bad in (None, "", "   ", "TBD", "tbd", "none", "NONE", "-"):
            self.assertFalse(sp.harvestable_pid(bad), repr(bad))

    def test_record_rejects_unknown_lane_and_outcome(self):
        with self.assertRaises(SystemExit):
            sp.record({"arms": {}, "history": []}, "NOPE", "hit")
        with self.assertRaises(SystemExit):
            sp.record({"arms": {}, "history": []}, "EXPAND", "maybe")


if __name__ == "__main__":
    unittest.main()
