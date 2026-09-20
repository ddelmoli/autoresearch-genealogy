#!/usr/bin/env python3
"""
test_rotate_floor_pool.py — pins the PER-LANE POOL behind a lane target (20 SEP 2026).

A lane floor is `rate% of a pool`. Both numbers were shared on purpose: the
17 SEP 2026 per-lane ruling gave ROTATE 1.5% *because* that is
`profile_review.sample_percent`, so the floor would track the profile-review
slice ("ROTATE keeps 1.5% because its unit is the profile-review slice").

The POOL was never shared, and that is where they came apart. ROTATE's unit is
one entry POLLED by `profile_review.py`, which refuses to draw living/unknown
people at all; `session_plan` was sizing the floor off EVERY person record. The
two rounded the same way until the vault crossed 1,700 records, and then:

    1.5% of 1,709 records    = 25.635 -> floor 26
    1.5% of 1,694 slice pool = 25.41  -> slice 25

Session #209's slice polled all 25 people it could reach and still stood one
short of its own floor. It scored a hit only because the lane RAN DRY, which is
a different clause of the rule — the lane could not have met the floor by
working, in any sitting, at any effort.

THE TEST THAT MATTERS IS THE NEGATIVE CONTROL (`test_old_behaviour_*`): sizing
ROTATE off the record pool is not obviously wrong — it is wrong only on the
pools that straddle a rounding boundary, which is why it survived three days and
would have recurred unpredictably as the vault grew.
"""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_plan as sp          # noqa: E402
import profile_review as pr        # noqa: E402

CFG = {"lane_target_percent": {"EXPAND": 0.5, "IMPROVE": 1.0, "ROTATE": 1.5, "default": 1.0}}

# ⚠ resolve_lane_target reads the vault's .maintenance.json for
# `profile_review.sample_percent` in the SAME try block that parses the per-lane
# mapping, so a vault path that does not open makes it fall back to the built-in
# rate for every lane. The tests therefore use a real directory holding the real
# config shape, not a fake path.
VAULT = None


def setUpModule():
    global VAULT
    VAULT = tempfile.mkdtemp(prefix="rotate-floor-")
    with open(os.path.join(VAULT, ".maintenance.json"), "w", encoding="utf-8") as f:
        json.dump({"session_plan": CFG, "profile_review": {"sample_percent": 1.5}}, f)


def tearDownModule():
    shutil.rmtree(VAULT, ignore_errors=True)

# The pools measured at the #209 close, the sitting that exposed the split.
RECORDS = 1709      # every person record
SLICE_POOL = 1694   # what profile_review will actually draw (RECORDS minus 15 living/unknown)


class FakePools:
    """Stand in for both pool sources, so the test needs no vault CONTENT.

    (It still needs the temp vault above for the config file; what is faked here
    is only how many people each of the two pools holds.)"""

    def __init__(self, records=RECORDS, slice_pool=SLICE_POOL, break_profile_review=False):
        self.records, self.slice_pool = records, slice_pool
        self.break_profile_review = break_profile_review
        self._saved = {}

    def __enter__(self):
        gpi = types.ModuleType("gen_person_index")
        gpi.parse_narrative = lambda *a, **k: [object()] * self.records
        pr_mod = types.ModuleType("profile_review")
        if self.break_profile_review:
            def boom(*a, **k):
                raise RuntimeError("builder unavailable")
            pr_mod.build_candidates = boom
        else:
            pr_mod.build_candidates = lambda *a, **k: [object()] * self.slice_pool
        for name, mod in (("gen_person_index", gpi), ("profile_review", pr_mod)):
            self._saved[name] = sys.modules.get(name)
            sys.modules[name] = mod
        return self

    def __exit__(self, *exc):
        for name, mod in self._saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        return False


def floor(lane, **kw):
    with FakePools(**kw):
        return sp.resolve_lane_target(VAULT, CFG, None, lane)[0]


class TestRotateTracksTheSlice(unittest.TestCase):
    def test_rotate_floor_equals_the_slice_ceiling(self):
        # THE INVARIANT: what ROTATE is scored against is what the slice can draw.
        ceiling = pr.resolve_cadence({}, SLICE_POOL, 1.5)[2]
        self.assertEqual(floor("ROTATE"), ceiling)
        self.assertEqual(floor("ROTATE"), 25)

    def test_rotate_uses_the_slice_pool_not_the_record_pool(self):
        self.assertEqual(sp.SLICE_SIZED_LANES, ("ROTATE",))
        with FakePools():
            self.assertEqual(sp.lane_pool_size(VAULT, "ROTATE"), SLICE_POOL)

    def test_the_two_stay_equal_across_a_range_of_vault_sizes(self):
        # The defect was not one bad number, it was a drift that recurs whenever
        # 1.5% of the two pools falls either side of a half. Sweep the boundary.
        for records in range(1650, 1780, 7):
            for living in (0, 1, 15, 40):
                slice_pool = records - living
                with FakePools(records=records, slice_pool=slice_pool):
                    got = sp.resolve_lane_target(VAULT, CFG, None, "ROTATE")[0]
                want = pr.resolve_cadence({}, slice_pool, 1.5)[2]
                self.assertEqual(got, want, f"records={records} living={living}")


class TestOtherLanesUnchanged(unittest.TestCase):
    def test_expand_and_improve_still_use_every_record(self):
        # Either lane may draw anyone, including people the rotation will not poll,
        # so their floors are a share of the WHOLE vault. Changing ROTATE's pool
        # must not move them: 0.5% of 1,709 = 9, 1.0% of 1,709 = 17.
        self.assertEqual(floor("EXPAND"), 9)
        self.assertEqual(floor("IMPROVE"), 17)
        with FakePools():
            self.assertEqual(sp.lane_pool_size(VAULT, "EXPAND"), RECORDS)
            self.assertEqual(sp.lane_pool_size(VAULT, None), RECORDS)


class TestOldBehaviourWasReallyWrong(unittest.TestCase):
    """Negative controls: pin the defect, not just the fix."""

    def test_old_behaviour_set_a_floor_the_slice_could_not_meet(self):
        old_floor = max(1, round(RECORDS * 1.5 / 100.0))
        slice_ceiling = pr.resolve_cadence({}, SLICE_POOL, 1.5)[2]
        self.assertEqual(old_floor, 26)
        self.assertEqual(slice_ceiling, 25)
        self.assertGreater(old_floor, slice_ceiling)   # unmeetable by working
        self.assertLessEqual(floor("ROTATE"), slice_ceiling)

    def test_old_behaviour_looked_correct_on_most_vault_sizes(self):
        # Why it survived: on most pools the record count and the slice pool round
        # to the SAME floor, so the bug is invisible until a boundary crossing.
        agree = sum(1 for r in range(1600, 1800)
                    if max(1, round(r * 0.015)) == max(1, round((r - 15) * 0.015)))
        self.assertGreater(agree, 150)                  # mostly indistinguishable
        self.assertLess(agree, 200)                     # but not always


class TestFallback(unittest.TestCase):
    def test_broken_builder_falls_back_to_the_record_pool(self):
        # A too-high floor is a bad day; no plan at all is a lost sitting.
        self.assertEqual(floor("ROTATE", break_profile_review=True),
                         max(1, round(RECORDS * 1.5 / 100.0)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
