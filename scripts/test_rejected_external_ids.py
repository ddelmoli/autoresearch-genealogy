#!/usr/bin/env python3
"""
test_rejected_external_ids.py — pins deferred_decisions 41 (option 2).

`fs: none` used to mean BOTH "searched, nothing there" and "a profile exists and
I declined it". Those give OPPOSITE instructions to a write-back: the first says
CREATE the person on FamilySearch, the second says a create would push a
DUPLICATE onto a shared public tree. Nothing in the data separated them.

A rejected profile is now recorded as `fs: ~PID`, reusing the `~locator`
convention: a thing deliberately declined is RECORDED, not erased.

The tests that matter are the NEGATIVE CONTROLS: a `~`-prefixed PID is a real,
well-formed PID, so every consumer that screened with a literal
`not in ("TBD", "none")` would have called it LIVE and acted on it.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import person_store as PS
import session_plan as SP


class TestExternalIdState(unittest.TestCase):
    def test_live(self):
        for v in ("XXXX-XXX", "YYYY-YYY", "  ZZZZ-ZZZ  "):
            self.assertEqual(PS.external_id_state(v), "live", v)
            self.assertEqual(PS.live_external_id(v), v.strip())
            self.assertIsNone(PS.rejected_external_id(v))

    def test_absent(self):
        for v in ("none", "None", "NONE", "-", "", "   ", None):
            self.assertEqual(PS.external_id_state(v), "absent", repr(v))
            self.assertIsNone(PS.live_external_id(v))

    def test_unknown_is_distinct_from_absent(self):
        # TBD means NOT YET SEARCHED. It must not read as "searched, nothing
        # there" -- that is the difference between owed work and finished work.
        for v in ("TBD", "tbd", " Tbd "):
            self.assertEqual(PS.external_id_state(v), "unknown", v)
            self.assertIsNone(PS.live_external_id(v))

    def test_rejected(self):
        self.assertEqual(PS.external_id_state("~XXXX-XXX"), "rejected")
        self.assertEqual(PS.rejected_external_id("~XXXX-XXX"), "XXXX-XXX")
        self.assertEqual(PS.rejected_external_id("~ XXXX-XXX "), "XXXX-XXX")

    def test_a_bare_tilde_is_not_a_rejection(self):
        # `~` with no PID records nothing re-checkable, so it is an absence.
        # The whole point of option 2 is that the IDENTIFIER is what makes a
        # rejection auditable.
        self.assertEqual(PS.external_id_state("~"), "absent")
        self.assertEqual(PS.external_id_state("~   "), "absent")
        self.assertIsNone(PS.rejected_external_id("~"))


class TestRejectedIsNeverActedOn(unittest.TestCase):
    """NEGATIVE CONTROLS — the reason this file exists."""

    def test_rejected_pid_is_not_harvestable(self):
        self.assertFalse(SP.harvestable_pid("~XXXX-XXX"))

    def test_rejected_pid_is_not_live(self):
        self.assertIsNone(PS.live_external_id("~XXXX-XXX"))

    def test_the_same_pid_unnegated_IS_harvestable(self):
        # Proves the tests above are testing the `~`, not a broken PID.
        self.assertTrue(SP.harvestable_pid("XXXX-XXX"))
        self.assertEqual(PS.live_external_id("XXXX-XXX"), "XXXX-XXX")

    def test_old_literal_screen_would_have_passed_it(self):
        # Documents the bug being fixed: the pre-41 test was
        #   p.upper() not in ("TBD", "NONE", "-")
        # which a `~`-prefixed PID sails straight through.
        old = lambda p: bool(p) and p.upper() not in ("TBD", "NONE", "-")
        self.assertTrue(old("~XXXX-XXX"))          # the defect
        self.assertFalse(SP.harvestable_pid("~XXXX-XXX"))  # the fix

    def test_sentinels_still_screened(self):
        for v in ("TBD", "none", "-", ""):
            self.assertFalse(SP.harvestable_pid(v), v)


if __name__ == "__main__":
    unittest.main()
