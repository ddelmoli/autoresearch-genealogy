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

ALL_FULL = {"EXPAND": 10, "IMPROVE": 10, "ROTATE": 10}


def hist(*lanes_per_sitting):
    """History from an explicit list of sittings: hist(("EXPAND","IMPROVE"), ("ROTATE",))
    is two sittings, the first of which worked two lanes."""
    out = []
    for i, lanes in enumerate(lanes_per_sitting, start=1):
        for ln in lanes:
            out.append({"date": "2026-07-31", "lane": ln, "outcome": "hit", "session": i})
    return out


# Two sittings for every lane: enough to clear the bootstrap floor, so a test that
# is about STALENESS or EXPLOIT is not silently answered by the floor above it.
WARMUP = (("EXPAND",), ("IMPROVE",), ("ROTATE",)) * 2


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
        # IMPROVE has been worked in no sitting at all. (Was ROTATE until 08 AUG
        # 2026; ROTATE left the bandit under deferred 51 option 3, so the floor is
        # now exercised with a lane the bandit can actually pick.)
        st = arms((("EXPAND",), ("EXPAND",)),
                  EXPAND=(2, 2), IMPROVE=(0, 0), ROTATE=(9, 9))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "IMPROVE")
        self.assertIn("bootstrap", reason)

    def test_no_exploitation_on_tiny_n_even_with_perfect_record(self):
        # EXPAND is 1-for-1 (rate 1.0) but IMPROVE is unsampled: floor wins.
        st = arms((("EXPAND",),),
                  EXPAND=(1, 1), IMPROVE=(0, 0), ROTATE=(9, 9))
        lane, _ = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "IMPROVE")

    def test_rotate_is_never_drawn_by_the_bandit(self):
        """deferred 51 option 3, 08 AUG 2026 -- the ruling, pinned.

        ROTATE is the EXPLOITATION arm and it won every draw (5/5 in session #154,
        with BOTH exploration lanes having to be forced by the operator). It left the
        bandit because it ALREADY has a cadence: the profile-review clock runs every
        session regardless of lane, so removing it from the draw removes no coverage.

        ⚠ It is still a LANE -- recordable and counted. Only unchooseable."""
        # A perfect ROTATE record against two poor ones must STILL not pick it.
        st = arms(WARMUP + (("EXPAND",), ("IMPROVE",), ("ROTATE",)) * 3,
                  EXPAND=(9, 1), IMPROVE=(9, 1), ROTATE=(9, 9))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertNotEqual(lane, "ROTATE", f"bandit picked the exploit arm: {reason}")
        self.assertIn(lane, ("EXPAND", "IMPROVE"))
        # ...and it is absent even when it is the ONLY lane with rows.
        lane, _ = sp.draw_lane(st, {"EXPAND": 0, "IMPROVE": 0, "ROTATE": 50})
        self.assertIsNone(lane, "ROTATE alone must read as 'no lane to draw'")
        # POSITIVE CONTROL: it remains a real, recordable lane.
        self.assertIn("ROTATE", sp.LANES)
        self.assertNotIn("ROTATE", sp.BANDIT_LANES)

    def test_empty_lane_never_drawn(self):
        st = {"arms": {}, "history": []}
        sizes = {"EXPAND": 0, "IMPROVE": 5, "ROTATE": 0}
        lane, _ = sp.draw_lane(st, sizes)
        self.assertEqual(lane, "IMPROVE")

    def test_all_lanes_empty(self):
        lane, reason = sp.draw_lane({"arms": {}, "history": []},
                                    {ln: 0 for ln in sp.LANES})
        self.assertIsNone(lane)
        self.assertIn("empty", reason)

    def test_staleness_floor_beats_exploit(self):
        # Both sampled past the floor; IMPROVE absent from the last SIX sittings, so
        # the staleness floor must beat EXPAND's better rate.
        st = arms(WARMUP + (("EXPAND",), ("ROTATE",)) * 3,
                  EXPAND=(6, 5), IMPROVE=(2, 0), ROTATE=(6, 1))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "IMPROVE")
        self.assertIn("staleness", reason)

    def test_exploit_picks_best_smoothed_rate(self):
        st = arms(WARMUP + (("EXPAND",), ("IMPROVE",),
                            ("ROTATE",), ("EXPAND",), ("IMPROVE",)),
                  EXPAND=(6, 5), IMPROVE=(6, 1), ROTATE=(6, 2))
        lane, reason = sp.draw_lane(st, ALL_FULL)
        self.assertEqual(lane, "EXPAND")  # (5+1)/(6+2) = 0.75, the max
        self.assertIn("exploit", reason)

    def test_exploit_tie_breaks_by_lane_order(self):
        st = arms(WARMUP + (("ROTATE",), ("IMPROVE",),
                            ("EXPAND",), ("ROTATE",)),
                  EXPAND=(6, 3), IMPROVE=(6, 3), ROTATE=(6, 3))
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
        # One huge sitting cannot age a lane out of the window on its own.
        base = dict(EXPAND=(2, 2), IMPROVE=(2, 2), ROTATE=(2, 2))
        # A twenty-iteration EXPAND sitting is ONE sitting, so IMPROVE is still inside
        # a two-sitting window. Under the old observation-counting it was long gone.
        st = arms(WARMUP + (("IMPROVE",), ("EXPAND",) * 20), **base)
        lane, _ = sp.draw_lane(st, ALL_FULL, stale_after=2)
        self.assertNotEqual(lane, "IMPROVE")
        # Three more sittings and it has genuinely aged out. (stale_after=3 so that
        # IMPROVE is the ONLY stale lane; with a 2-window EXPAND is stale too and wins
        # on lane order, which would prove nothing about the unit under test.)
        st = arms(WARMUP + (("IMPROVE",), ("EXPAND",), ("ROTATE",), ("EXPAND",)), **base)
        lane, reason = sp.draw_lane(st, ALL_FULL, stale_after=3)
        self.assertEqual(lane, "IMPROVE")
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
                          for ln in ("EXPAND", "IMPROVE", "ROTATE")] * 3}
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
                       "IMPROVE", "miss", session=124, today="2026-07-31")
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

    def test_expand_carries_both_tiers(self):
        """** EXPAND draws 0-parent AND 1-parent rows ** (deferred 50, wired 07 AUG 2026;
        the operator's lane definition is "leaf nodes ... especially those for which we
        only have 0 OR 1 parents"). Until this landed a one-parent row was drawable by
        NOTHING -- not even by EXPAND, whose whole job is missing parents.

        The two data sources are STUBBED rather than written to a temp vault, on purpose:
        `extension_frontier.rows_with_bodies` reads `parse_narrative()` off a module-global
        vault resolved at import, so a temp-dir fixture here silently reads the REAL vault
        and every assertion passes or fails for the wrong reason. (That is not a defect
        introduced by this change -- it is why the fixture is stubbed.) The vault-reading
        half is pinned in `test_build_edges.py`, against the shared `half_wired_rows()`.

        What this pins is the COMPOSITION, which is the part written here: tier labels,
        SILENT ranking first, the declared rows excluded, and above all NO OVERLAP -- a
        duplicate id would let one person be drawn twice and counted twice against the
        lane floor.
        """
        import extension_frontier as ef
        import build_edges as be
        real_rows, real_hw = ef.rows_with_bodies, be.half_wired_rows
        try:
            ef.rows_with_bodies = lambda v: [
                {"id": "P-ZER001", "name": "Zero Parent", "gen": 6, "file": "F.md",
                 "declared": False, "tier": "strong_signal", "spouse": False},
                {"id": "P-ZER002", "name": "Zero Declared", "gen": 7, "file": "F.md",
                 "declared": True, "tier": "strong_signal", "spouse": False},
            ]
            be.half_wired_rows = lambda v: [
                {"id": "P-ONE001", "name": "One Parent", "gen": 6, "file": "F.md",
                 "declared": False, "deep": False},
                {"id": "P-ONE002", "name": "One Declared", "gen": 6, "file": "F.md",
                 "declared": True, "deep": False},
                {"id": "P-ONE003", "name": "One Deep", "gen": 30, "file": "F.md",
                 "declared": False, "deep": True},
                # already on the 0-parent frontier: must NOT appear twice
                {"id": "P-ZER001", "name": "Zero Parent", "gen": 6, "file": "F.md",
                 "declared": False, "deep": False},
            ]
            rows = sp.lane_expand("/nonexistent")
            by_id = {r["id"]: r for r in rows}
            ids = [r["id"] for r in rows]

            self.assertEqual(len(ids), len(set(ids)),
                             "no overlap -- a duplicate id is double-counted work")
            self.assertEqual(by_id["P-ZER001"]["tier"], "silent",
                             "a 0-parent row is the SILENT tier")
            self.assertEqual(by_id["P-ONE001"]["tier"], "half_wired",
                             "a 1-parent row is now DRAWN, in the half_wired tier")
            self.assertNotIn("P-ZER002", by_id,
                             "NEGATIVE CONTROL: a DECLARED frontier row is not offered")
            self.assertNotIn("P-ONE002", by_id,
                             "NEGATIVE CONTROL: a row declared `no-second-parent` is not offered")
            tiers = [r["tier"] for r in rows]
            first_hw = tiers.index("half_wired")
            self.assertTrue(all(t == "silent" for t in tiers[:first_hw]),
                            "SILENT ranks ahead of HALF_WIRED")
            self.assertIn("wire it", by_id["P-ONE003"]["why"],
                          "a DEEP row's hint says wire the named mother")
            self.assertIn("declare", by_id["P-ONE001"]["why"],
                          "a SHALLOW row's hint offers the declaration too")
        finally:
            ef.rows_with_bodies, be.half_wired_rows = real_rows, real_hw

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


class ImproveSplitTests(unittest.TestCase):
    """** deferred_decisions 34, option 1 (operator-directed 02 AUG 2026). **

    IMPROVE's two dispositions cost wildly differently and only one serves the
    biography goal, but they scored identically and nothing recorded which had
    happened -- so #128's all-FamilySearch draw read as a clean 17-of-21 while
    SINGLE_SOURCED went UP by 16 and MULTI_SOURCED did not move.

    The split is REPORTING ONLY. The negative control below is the load-bearing
    test: recording a split must leave the bandit arithmetic byte-identical, because
    the floor is "the same in every lane, counted in PEOPLE" and weighting it was
    rejected on sight.
    """

    def _st(self):
        return {"arms": {}, "history": [], "pending": None}

    def test_split_is_recorded_on_the_history_row(self):
        st = sp.record(self._st(), "IMPROVE", "hit", today="2026-08-02",
                       sourced=13, corroborated=8)
        self.assertEqual(st["history"][-1]["split"],
                         {"sourced": 13, "corroborated": 8, "verified": 0})

    def test_one_half_alone_is_enough_and_the_other_defaults_to_zero(self):
        st = sp.record(self._st(), "IMPROVE", "miss", today="2026-08-02", sourced=4)
        self.assertEqual(st["history"][-1]["split"],
                         {"sourced": 4, "corroborated": 0, "verified": 0})

    def test_zero_corroborated_is_RECORDED_not_dropped(self):
        """An explicit 0 is the #128 signal itself -- it must survive, not vanish
        into 'no split reported'."""
        st = sp.record(self._st(), "IMPROVE", "hit", today="2026-08-02",
                       sourced=17, corroborated=0)
        self.assertEqual(st["history"][-1]["split"]["corroborated"], 0)
        self.assertEqual(sp.last_improve_split(st)["corroborated"], 0)

    def test_no_split_leaves_no_key(self):
        st = sp.record(self._st(), "IMPROVE", "hit", today="2026-08-02")
        self.assertNotIn("split", st["history"][-1])

    def test_split_is_IMPROVE_ONLY(self):
        for lane in ("EXPAND", "VERIFY", "ROTATE"):
            with self.assertRaises(SystemExit, msg=lane):
                sp.record(self._st(), lane, "hit", sourced=1)

    def test_NEGATIVE_CONTROL_the_split_does_not_change_scoring(self):
        """Same two draws, one pair recorded with a split and one without: the arms
        must be identical. If this ever fails, the split has become a weight."""
        plain = self._st()
        plain = sp.record(plain, "IMPROVE", "hit", today="2026-08-02")
        plain = sp.record(plain, "IMPROVE", "miss", today="2026-08-02")
        split = self._st()
        split = sp.record(split, "IMPROVE", "hit", today="2026-08-02",
                          sourced=0, corroborated=21)
        split = sp.record(split, "IMPROVE", "miss", today="2026-08-02",
                          sourced=21, corroborated=0)
        self.assertEqual(plain["arms"], split["arms"])
        self.assertEqual(plain["arms"]["IMPROVE"], {"iterations": 2, "wins": 1})

    def test_last_improve_split_is_None_before_any_is_recorded(self):
        self.assertIsNone(sp.last_improve_split({"history": []}))
        self.assertIsNone(sp.last_improve_split({}))

    def test_last_improve_split_takes_the_NEWEST(self):
        st = self._st()
        st = sp.record(st, "IMPROVE", "hit", today="2026-08-01",
                       sourced=1, corroborated=1)
        st = sp.record(st, "IMPROVE", "hit", today="2026-08-02",
                       sourced=9, corroborated=12)
        self.assertEqual(sp.last_improve_split(st),
                         {"date": "2026-08-02", "sourced": 9, "corroborated": 12})

    def test_a_later_IMPROVE_row_WITHOUT_a_split_does_not_mask_the_last_one(self):
        """'not reported' and 'reported as none' are different facts; only the first
        is silent, so an unsplit row is skipped rather than read as zeroes."""
        st = self._st()
        st = sp.record(st, "IMPROVE", "hit", today="2026-08-01",
                       sourced=5, corroborated=6)
        st = sp.record(st, "IMPROVE", "hit", today="2026-08-02")
        self.assertEqual(sp.last_improve_split(st)["sourced"], 5)

    def test_other_lanes_never_supply_the_last_improve_split(self):
        st = self._st()
        st["history"] = [{"date": "2026-08-02", "lane": "VERIFY", "outcome": "hit",
                          "split": {"sourced": 99, "corroborated": 99}}]
        self.assertIsNone(sp.last_improve_split(st))


class LaneCollapseTests(unittest.TestCase):
    """** deferred 39 + 40 (operator-directed, 02 AUG 2026): VERIFY collapsed into
    IMPROVE, asymmetrically. **

    40 measured that the two lanes drew from mostly the same people (694 in both).
    39 measured that VERIFY's edge pool was keyed on a SELF-ASSIGNED mark covering
    3.2% of edges, and could not see ANY of the 8 children carrying an unexplained
    PARENT-GEN MISMATCH.

    The load-bearing part is the ASYMMETRY: PID liveness must not become a scoring
    unit, or the cheapest action in the system satisfies a floor that sourcing has
    never met.
    """

    def test_VERIFY_is_no_longer_a_lane(self):
        self.assertNotIn("VERIFY", sp.LANES)
        self.assertEqual(sp.LANES, ("EXPAND", "IMPROVE", "ROTATE"))

    def test_recording_VERIFY_is_REJECTED_not_silently_accepted(self):
        """A stale prompt or a habit must fail loudly, not write an orphan arm."""
        with self.assertRaises(SystemExit):
            sp.record({"arms": {}, "history": []}, "VERIFY", "hit",
                      today="2026-08-02")

    def test_verified_is_a_THIRD_split_slot_not_a_replacement(self):
        st = sp.record({"arms": {}, "history": [], "pending": None}, "IMPROVE",
                       "hit", today="2026-08-02",
                       sourced=3, corroborated=2, verified=6)
        self.assertEqual(st["history"][-1]["split"],
                         {"sourced": 3, "corroborated": 2, "verified": 6})

    def test_an_ALL_DEFECT_draw_is_recordable_and_visible(self):
        """A draw spent adjudicating edges must not read as 'achieved nothing'."""
        st = sp.record({"arms": {}, "history": [], "pending": None}, "IMPROVE",
                       "hit", today="2026-08-02", verified=21)
        sp_split = st["history"][-1]["split"]
        self.assertEqual(sp_split["verified"], 21)
        self.assertEqual((sp_split["sourced"], sp_split["corroborated"]), (0, 0))

    def test_the_split_still_does_NOT_change_the_arithmetic(self):
        """NEGATIVE CONTROL, inherited from deferred 34: reporting is not scoring.
        Adding `verified` must leave the bandit byte-identical."""
        a = sp.record({"arms": {}, "history": [], "pending": None}, "IMPROVE",
                      "hit", today="2026-08-02")
        b = sp.record({"arms": {}, "history": [], "pending": None}, "IMPROVE",
                      "hit", today="2026-08-02", sourced=1, corroborated=1,
                      verified=99)
        self.assertEqual(a["arms"], b["arms"])

    def test_verified_is_IMPROVE_only(self):
        with self.assertRaises(SystemExit):
            sp.record({"arms": {}, "history": [], "pending": None}, "EXPAND",
                      "hit", today="2026-08-02", verified=1)

    def test_pid_staleness_is_NOT_one_of_the_scoring_slots(self):
        """The asymmetry, pinned. There is deliberately no --probed/--pid slot: a
        PID confirmation is step 0 of prompt 25 and scores nothing at all."""
        st = sp.record({"arms": {}, "history": [], "pending": None}, "IMPROVE",
                       "hit", today="2026-08-02", verified=1)
        self.assertEqual(set(st["history"][-1]["split"]),
                         {"sourced", "corroborated", "verified"})

    def test_IMPROVE_unit_text_says_a_PID_CHECK_SCORES_NOTHING(self):
        """The prompt and the plan must state the same rule; this is the plan half."""
        unit = sp.LANE_UNITS["IMPROVE"]
        self.assertIn("SCORES NOTHING", unit.upper())
        self.assertIn("DEFECT", unit.upper())


if __name__ == "__main__":
    unittest.main()
