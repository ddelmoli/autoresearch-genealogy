#!/usr/bin/env python3
"""test_log_session_replace.py — pins `log_session.py --replace` and the re-close that uses it.

** WHY THIS EXISTS (20 SEP 2026). ** A long sitting is often closed, extended, then closed
again. The first close writes the sitting's Research_Log index row; the extension makes it
wrong; and the file is append-only, so there was no sanctioned way to fix it.
`session_close.py` answered a re-close's `--log` with "correct the existing row in place
with a targeted replacement" while offering no tool to do it — and the Edit tool is
forbidden on that file. Measured on one sitting: its row made four claims that were all
false by the re-close.

What is pinned:
  1. --replace rewrites THIS sitting's row in place and adds no second row;
  2. it matches on the LOG-LINK cell only — a row whose SUMMARY merely mentions the same
     log is never touched;
  3. neighbouring rows, the header and the separator survive byte-for-byte;
  4. the ORIGINAL date is kept (a next-day cleanup must not re-date the sitting), and an
     explicit --date still wins;
  5. 0 matches REFUSES (nothing to correct) and 2+ matches REFUSES (a duplicate needs a
     human), and neither writes;
  6. plain append is unchanged;
  7. end to end: a RE-CLOSE with --log/--summary replaces the row, while a re-close with
     --lane/--outcome is still refused (that one would double-count the bandit).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

LOG = "logs/2099-01-02-session-900-example"
LINK = f"[[{LOG}]]"

RESEARCH_LOG = f"""# Research Log

## Session Index

| Date | Log | Summary |
|------|-----|---------|
| 2099-01-01 | [[logs/2099-01-01-session-899-earlier]] | An earlier sitting that cites {LINK} in its summary. |
| 2099-01-02 | {LINK} | FIRST-CLOSE summary: census flat throughout. |
| 2099-01-03 | [[logs/2099-01-03-session-901-later]] | A later sitting. |

## Trailing section
Not part of the table.
"""

VAULT_TREE = """# Family Tree

**Alpha Placeholder** (b. 1800)
- meta: {id: P-AAA111, generation: 1, life_status: deceased}
"""


class ReplaceTests(unittest.TestCase):
    def setUp(self):
        self.vault = tempfile.mkdtemp(prefix="autoresearch-logreplace-test-")
        os.makedirs(os.path.join(self.vault, "logs"), exist_ok=True)
        self.rl = os.path.join(self.vault, "Research_Log.md")
        with open(self.rl, "w", encoding="utf-8") as f:
            f.write(RESEARCH_LOG)
        with open(os.path.join(self.vault, "Family_Tree.md"), "w", encoding="utf-8") as f:
            f.write(VAULT_TREE)
        with open(os.path.join(self.vault, ".autoresearch.json"), "w", encoding="utf-8") as f:
            json.dump({"person_model": "narrative"}, f)

    def tearDown(self):
        shutil.rmtree(self.vault, ignore_errors=True)

    def run_script(self, name, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, name), *args],
                              capture_output=True, text=True, timeout=600,
                              env={**os.environ, "AUTORESEARCH_VAULT": self.vault})

    def text(self):
        with open(self.rl, encoding="utf-8") as f:
            return f.read()

    def rows_for(self, link):
        return [ln for ln in self.text().splitlines()
                if ln.startswith("|") and ln.split("|")[2].strip() == link]

    # ---------------------------------------------------------------- log_session
    def test_replace_rewrites_in_place_and_adds_no_row(self):
        before = self.text().count("\n| ")
        r = self.run_script("log_session.py", "--log", LOG,
                            "--summary", "CORRECTED: census moved 47 -> 45.", "--replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.text().count("\n| "), before, "no second row may be added")
        rows = self.rows_for(LINK)
        self.assertEqual(len(rows), 1)
        self.assertIn("CORRECTED: census moved", rows[0])
        self.assertNotIn("FIRST-CLOSE summary", self.text())

    def test_replace_matches_on_the_link_cell_only(self):
        self.run_script("log_session.py", "--log", LOG, "--summary", "new text", "--replace")
        self.assertIn(f"An earlier sitting that cites {LINK} in its summary.", self.text(),
                      "a row that merely MENTIONS the log in its summary must be untouched")

    def test_neighbours_and_structure_survive(self):
        before = self.text().splitlines()
        self.run_script("log_session.py", "--log", LOG, "--summary", "new text", "--replace")
        after = self.text().splitlines()
        self.assertEqual(len(before), len(after))
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(len(changed), 1, "exactly one line may change")
        self.assertIn("## Trailing section", after)

    def test_original_date_kept_unless_overridden(self):
        self.run_script("log_session.py", "--log", LOG, "--summary", "x", "--replace")
        self.assertTrue(self.rows_for(LINK)[0].startswith("| 2099-01-02 |"),
                        "a re-close must not re-date the sitting")
        self.run_script("log_session.py", "--log", LOG, "--summary", "y", "--replace",
                        "--date", "2099-01-09")
        self.assertTrue(self.rows_for(LINK)[0].startswith("| 2099-01-09 |"),
                        "an explicit --date still wins")

    def test_zero_matches_refuses_and_writes_nothing(self):
        before = self.text()
        r = self.run_script("log_session.py", "--log", "logs/2099-12-31-nope",
                            "--summary", "x", "--replace")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NO existing row", r.stdout)
        self.assertEqual(self.text(), before)

    def test_duplicate_matches_refuse_and_write_nothing(self):
        dup = self.text().replace(
            "| 2099-01-03 |", f"| 2099-01-02 | {LINK} | an accidental duplicate. |\n| 2099-01-03 |", 1)
        with open(self.rl, "w", encoding="utf-8") as f:
            f.write(dup)
        r = self.run_script("log_session.py", "--log", LOG, "--summary", "x", "--replace")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("duplicate", r.stdout)
        self.assertEqual(self.text(), dup, "an ambiguous match must not be guessed")

    def test_plain_append_is_unchanged(self):
        r = self.run_script("log_session.py", "--log", "logs/2099-01-04-session-902-new",
                            "--summary", "appended row")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = self.text().splitlines()
        idx = next(i for i, ln in enumerate(lines) if "appended row" in ln)
        self.assertIn("2099-01-03", lines[idx - 1], "append lands after the last table row")
        self.assertEqual(len(self.rows_for(LINK)), 1)

    # ---------------------------------------------------------------- session_close
    def test_reclose_log_replaces_the_row(self):
        self.run_script("session_close.py", "--session", "900")          # first close
        r = self.run_script("session_close.py", "--session", "900",
                            "--log", LOG, "--summary", "RE-CLOSE summary: census moved.")
        self.assertIn("RE-CLOSE", r.stdout)
        rows = self.rows_for(LINK)
        self.assertEqual(len(rows), 1, "the re-close must not add a second row")
        self.assertIn("RE-CLOSE summary", rows[0])
        self.assertNotIn("\n  log          BLOCK", r.stdout)

    def test_reclose_still_refuses_a_second_observation(self):
        self.run_script("session_close.py", "--session", "900")
        r = self.run_script("session_close.py", "--session", "900",
                            "--lane", "EXPAND", "--outcome", "hit")
        self.assertNotEqual(r.returncode, 0, "a double-record must still FAIL")
        self.assertIn("already closed", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
