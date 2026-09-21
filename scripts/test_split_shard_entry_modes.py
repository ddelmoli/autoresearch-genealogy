#!/usr/bin/env python3
"""Pins split_shard.py's ENTRY-LEVEL modes (added 21 SEP 2026).

WHAT IS BEING DEFENDED.
  1. `--by-meta-gen`: a shard whose entries all sit under ONE section (a gen-sorted
     `## Collateral stub entries` appendix, no `### Generation N` headings) could not
     be carved by generation at all -- the block mode found nothing. The new mode
     routes each person entry by the `generation` in its OWN meta line, never by a
     heading or by prose that merely mentions a generation.
  2. The dropped-prose abort. Entry mode rebuilds a section from its entries, so a
     free prose line BETWEEN entries has nothing to travel with; it used to vanish
     silently while the id-conservation check (which counts ids, not prose) passed.
     Now it is returned and the caller refuses to write.

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

---

## Collateral stub entries (migrated from Person_Index)

**Jane Example** (b. ABT 1200)
- meta: {id: P-AAAAAA, generation: 30}
- Gen 30; her son was Gen 31 per the chronicle.

**John Example** (b. ABT 1170)
- meta: {id: P-BBBBBB, generation: 31}

**Joan Example** (b. ABT 1140)
- meta: {id: P-CCCCCC, generation: 32}

**No Gen Example**
- meta: {id: P-DDDDDD}
"""


class ByMetaGen(unittest.TestCase):
    def split(self, text, lo, hi):
        return ss.cluster_split(text, ss.meta_gen_matcher(lo, hi), "S.md", "D.md", "2026-01-01-000000")

    def test_routes_by_meta_field_not_prose(self):
        src, dst, moved, kept, dropped = self.split(FIXTURE, 31, 32)
        self.assertEqual(moved, ["John Example", "Joan Example"])
        # Jane's BODY says "Gen 31"; her meta says 30, and the meta wins.
        self.assertIn("Jane Example", kept)
        self.assertIn("P-AAAAAA", src)
        self.assertNotIn("P-AAAAAA", dst)
        self.assertEqual(dropped, [])

    def test_entry_without_generation_stays(self):
        src, dst, moved, kept, _ = self.split(FIXTURE, 0, 999)
        self.assertIn("No Gen Example", kept)
        self.assertIn("P-DDDDDD", src)

    def test_ids_conserved(self):
        src, dst, *_ = self.split(FIXTURE, 31, 32)
        self.assertEqual(sorted(ss.meta_ids(FIXTURE)), sorted(ss.meta_ids(src) + ss.meta_ids(dst)))

    def test_section_heading_reconstructed_in_dest(self):
        _, dst, *_ = self.split(FIXTURE, 31, 32)
        self.assertIn("## Collateral stub entries", dst)


class ProseIsNeverLost(unittest.TestCase):
    INTRO = "*(Scope note: these stubs are gen-sorted.)*"

    def test_section_intro_stays_with_source_heading(self):
        # The live case that motivated the guard: a scope note directly under the
        # section heading, before any entry. It used to vanish.
        text = FIXTURE.replace("(migrated from Person_Index)\n", "(migrated from Person_Index)\n\n" + self.INTRO + "\n")
        src, dst, _, _, dropped = ss.cluster_split(text, ss.meta_gen_matcher(31, 32), "S.md", "D.md", "t")
        self.assertEqual(dropped, [])
        self.assertIn(self.INTRO, src)
        self.assertNotIn(self.INTRO, dst)
        self.assertLess(src.index("## Collateral stub entries"), src.index(self.INTRO))

    def test_intro_kept_even_when_every_entry_moves(self):
        text = FIXTURE.replace("(migrated from Person_Index)\n", "(migrated from Person_Index)\n\n" + self.INTRO + "\n")
        src, _, _, _, dropped = ss.cluster_split(text, ss.meta_gen_matcher(0, 999), "S.md", "D.md", "t")
        self.assertEqual(dropped, [])
        self.assertIn(self.INTRO, src)

    def test_prose_after_an_entry_travels_with_it(self):
        note = "> A note about the Gen 31 band."
        text = FIXTURE.replace("**Joan Example**", note + "\n\n**Joan Example**")
        src, dst, _, _, dropped = ss.cluster_split(text, ss.meta_gen_matcher(31, 32), "S.md", "D.md", "t")
        self.assertEqual(dropped, [])
        self.assertIn(note, dst)  # it follows John (Gen 31), so it moves with him

    def test_blank_lines_and_rules_are_not_reported(self):
        text = FIXTURE.replace("**John Example**", "---\n\n**John Example**")
        _, _, _, _, dropped = ss.cluster_split(text, ss.meta_gen_matcher(31, 32), "S.md", "D.md", "t")
        self.assertEqual(dropped, [])


class SurnameModeUnchanged(unittest.TestCase):
    def test_list_calling_form_still_works(self):
        _, _, moved, kept, _ = ss.cluster_split(FIXTURE, ["Joan"], "S.md", "D.md", "t")
        self.assertEqual(moved, ["Joan Example"])
        self.assertEqual(len(kept), 3)


if __name__ == "__main__":
    unittest.main()
