#!/usr/bin/env python3
"""Pin the close ORDER: record the outcome FIRST, register the next draw AFTER.

THE DEFECT THIS PINS (found 31 JUL 2026). `session_plan.py --record` sets
`pending: null`, and the close prompt used to say "run session_plan.py for
OPEN / NEXT" BEFORE running the close command. So the plan registered a pending
draw and the close immediately wiped it: a Handoff announced "a pending draw is
waiting: EXPAND" over a state file holding no pending draw at all, and the next
session's plan drew a different lane. Nothing failed, no gate moved, and the two
disagreed silently for days.

`session_close.py --next-plan` runs the plan LAST so the ordering cannot be got
wrong by hand. These tests run the real command against a throwaway vault.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

VAULT_TREE = """---
type: tree
created: 2026-07-31
tags: [tree]
---
### Generation 1: Test

**Alpha Placeholder** (b. 1900; d. 1980)
- meta: {id: P-AAA111, generation: 1, life_status: deceased}
- Body.

**Beta Placeholder** (b. 1870; d. 1940)
- meta: {id: P-BBB222, generation: 2, life_status: deceased, parents: '[P-CCC333?]'}
- Body.

**Gamma Placeholder** (b. 1840)
- meta: {id: P-CCC333, generation: 3, life_status: deceased}
- Body.
"""


class CloseOrderTests(unittest.TestCase):
    def setUp(self):
        self.vault = tempfile.mkdtemp(prefix="autoresearch-close-test-")
        os.makedirs(os.path.join(self.vault, "logs"), exist_ok=True)
        with open(os.path.join(self.vault, "Family_Tree.md"), "w", encoding="utf-8") as f:
            f.write(VAULT_TREE)
        with open(os.path.join(self.vault, ".autoresearch.json"), "w", encoding="utf-8") as f:
            json.dump({"person_model": "narrative"}, f)

    def tearDown(self):
        shutil.rmtree(self.vault, ignore_errors=True)

    def close(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "session_close.py"), *args],
                              capture_output=True, text=True, timeout=600,
                              env={**os.environ, "AUTORESEARCH_VAULT": self.vault})

    def state(self):
        with open(os.path.join(self.vault, "session_plan_snapshots.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_next_plan_survives_the_record(self):
        """The whole point: a draw registered by --next-plan is still pending after."""
        r = self.close("--lane", "EXPAND", "--outcome", "hit", "--next-plan")
        self.assertIn("next", r.stdout)
        s = self.state()
        self.assertEqual(len(s["history"]), 1, "the outcome should be recorded exactly once")
        self.assertIsNotNone(s["pending"],
                             "--next-plan must run AFTER --record, or the draw is wiped")

    def test_plan_before_close_is_the_bug_being_prevented(self):
        """Negative control: the OLD ordering (plan, then close) loses the draw."""
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "session_plan.py")],
                       capture_output=True, text=True, timeout=600,
                       env={**os.environ, "AUTORESEARCH_VAULT": self.vault})
        self.assertIsNotNone(self.state()["pending"], "the plan should register a draw")
        self.close("--lane", "EXPAND", "--outcome", "hit")
        self.assertIsNone(self.state()["pending"],
                          "this is the defect: --record clears a draw registered before it")

    def test_close_without_lane_records_nothing(self):
        """The four-phase default: iterations record themselves in phase 2."""
        self.close("--next-plan")
        self.assertEqual(self.state().get("history", []), [],
                         "a close with no --lane/--outcome must not touch the bandit")

    def test_next_plan_absent_reports_due_not_silence(self):
        r = self.close()
        line = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("next")]
        self.assertTrue(line, "the `next` step must always be reported")
        self.assertIn("DUE", line[0])
        self.assertIn("AFTER this command", line[0])


class RecloseTests(unittest.TestCase):
    """** A RE-CLOSE IS DERIVED FROM STATE, NOT REMEMBERED (31 JUL 2026). **

    A long sitting is often closed, extended, then closed again. The old close prompt
    asked the agent to know which case it was in; a resumed agent cannot, and the state
    file carried nothing to tell it -- `history` rows hold only a date and a lane, and
    two sittings in one day is normal on this vault."""

    def setUp(self):
        CloseOrderTests.setUp(self)

    def tearDown(self):
        CloseOrderTests.tearDown(self)

    close = CloseOrderTests.close
    state = CloseOrderTests.state

    def test_first_close_stamps_the_session(self):
        r = self.close("--session", "123", "--next-plan")
        self.assertIn("first close", r.stdout)
        self.assertEqual(self.state()["last_close"]["session"], 123)

    def test_second_close_of_the_same_session_is_detected(self):
        self.close("--session", "123", "--next-plan")
        r = self.close("--session", "123")
        self.assertIn("RE-CLOSE", r.stdout)

    def test_reclose_refuses_to_double_record(self):
        self.close("--session", "123")
        r = self.close("--session", "123", "--lane", "EXPAND", "--outcome", "hit")
        self.assertNotEqual(r.returncode, 0, "a double-record must FAIL the checklist")
        self.assertIn("already closed", r.stdout)
        self.assertEqual(self.state().get("history", []), [],
                         "and it must not reach the bandit")

    def test_a_different_session_number_is_a_first_close(self):
        self.close("--session", "123")
        r = self.close("--session", "124")
        self.assertIn("first close", r.stdout)

    def test_recorded_observation_carries_the_sitting(self):
        self.close("--session", "125", "--lane", "IMPROVE", "--outcome", "miss")
        self.assertEqual(self.state()["history"][-1]["session"], 125)


if __name__ == "__main__":
    unittest.main()
