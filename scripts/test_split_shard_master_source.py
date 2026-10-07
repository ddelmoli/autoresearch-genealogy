#!/usr/bin/env python3
"""Pins split_shard.py when the SOURCE is the master `Family_Tree.md` itself (fixed 07 OCT 2026).

WHAT IS BEING DEFENDED.
  The File Index row is added to the master's text, and the master is written
  after the source. When the two are one file, the master text used to be read
  from disk, i.e. the PRE-split file: its write then restored every moved entry,
  so each moved id ended up in both the source and the new shard. The
  conservation check could not see it (it compares the texts the tool built, not
  what reached disk). `_master_base` now hands back the carved source text.

Placeholder names only.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_shard as ss  # noqa: E402


class MasterIsSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.master = self.vault / "Family_Tree.md"
        self.master.write_text("# Family Tree\n\nORIGINAL\n", encoding="utf-8")
        self._saved = ss.MASTER
        ss.MASTER = self.master

    def tearDown(self):
        ss.MASTER = self._saved
        self.tmp.cleanup()

    def test_master_source_uses_carved_text(self):
        self.assertEqual(ss._master_base(self.master, "CARVED"), "CARVED")

    def test_other_source_reads_master_from_disk(self):
        other = self.vault / "Family_Tree_Example.md"
        other.write_text("x", encoding="utf-8")
        self.assertIn("ORIGINAL", ss._master_base(other, "CARVED"))

    def test_no_master_gives_empty(self):
        ss.MASTER = self.vault / "absent.md"
        self.assertEqual(ss._master_base(self.master, "CARVED"), "")


if __name__ == "__main__":
    unittest.main()
