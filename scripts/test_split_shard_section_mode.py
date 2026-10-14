#!/usr/bin/env python3
"""Pins split_shard.py's SECTION mode (added 14 OCT 2026).

WHAT IS BEING DEFENDED.
  A collateral shard organised by FAMILY sections (`## Sibling Collateral — ...`,
  `## Generation 6 Collateral by Marriage: ...`) could not be carved by either
  existing mode: block mode only sees `### Generation N` blocks, and surname mode
  splits a family from its in-laws (a wife whose header carries the surname leaves,
  her husband and his parents stay). `--section REGEX` moves whole `## ` sections,
  verbatim, with their `### ` subsections and intro prose.

  1. A matching section travels WITH its `### ` subsections, up to the next `## `.
  2. A non-matching section (and the file head) stays, byte for byte.
  3. Generations for the label are read from the moved entries' meta lines.

Placeholder names only.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_shard as ss  # noqa: E402

FIXTURE = """---
type: reference
---

# Family Tree: example collateral

## Sibling Collateral — Jane Example's sister Ann

Intro prose about Ann's family.

**Ann Example** (b. ABT 1800)
- meta: {id: P-AAAAAA, generation: 6}

## Generation 6 Collateral by Marriage: Mary Sample + John Other

**John Other** (b. ABT 1798)
- meta: {id: P-BBBBBB, generation: 6}

### Generation 7 in-law (John Other's parents)

**Peter Other** (b. ABT 1770)
- meta: {id: P-CCCCCC, generation: 7}

## Collateral stub entries (migrated from Person_Index)

**Stub Example** (b. 1901)
- meta: {id: P-DDDDDD, generation: 4}
"""


class SectionMode(unittest.TestCase):
    def test_section_moves_with_its_subsections(self):
        lines, drop, first, chunks, gens = ss.carve_sections(FIXTURE, r"Mary Sample")
        self.assertEqual(len(chunks), 1)
        self.assertIn("P-BBBBBB", chunks[0])
        self.assertIn("P-CCCCCC", chunks[0])          # the ### in-law block travels
        self.assertNotIn("P-DDDDDD", chunks[0])       # stops at the next ##
        self.assertEqual(sorted(gens), [6, 7])

    def test_unmatched_sections_stay_verbatim(self):
        lines, drop, first, chunks, gens = ss.carve_sections(FIXTURE, r"Mary Sample")
        kept = "".join(ln for i, ln in enumerate(lines) if i not in drop)
        self.assertIn("Intro prose about Ann's family.\n", kept)
        self.assertIn("P-AAAAAA", kept)
        self.assertIn("P-DDDDDD", kept)
        self.assertTrue(kept.startswith("---\ntype: reference\n---\n"))
        moved_ids = sorted(ss.meta_ids("".join(chunks)) + ss.meta_ids(kept))
        self.assertEqual(moved_ids, sorted(ss.meta_ids(FIXTURE)))

    def test_alternation_matches_several_sections(self):
        _, _, first, chunks, _ = ss.carve_sections(FIXTURE, r"sister Ann|Mary Sample")
        self.assertEqual(len(chunks), 2)
        self.assertEqual(first, FIXTURE.splitlines().index(
            "## Sibling Collateral — Jane Example's sister Ann"))

    def test_no_match(self):
        self.assertEqual(ss.carve_sections(FIXTURE, r"Nobody"), (None, None, []))


if __name__ == "__main__":
    unittest.main()
