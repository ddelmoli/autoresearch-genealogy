#!/usr/bin/env python3
"""`### Generation N` is an entry boundary — deferred 36, measured 02 AUG 2026.

An entry was absorbing the start of the NEXT generation's section, because the break
set matched `## ` (two hashes + space) and a `### Generation 8` heading puts a third
`#` exactly where that pattern wants whitespace.

** THE NEGATIVE CONTROLS ARE THE POINT OF THIS FILE. ** Two other boundary signals
were measured against the live corpus and REJECTED, both because they delete real
evidence, and both failing on the SAME entry. They are pinned here so nobody
"improves" the break set into deleting a record again.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest_sources as hs


class GenerationBreakTests(unittest.TestCase):

    def test_a_generation_heading_CLOSES_the_entry(self):
        body = ("**Sarah Example** (b. 1700)\n"
                "- meta: {id: P-1XAMP1, generation: 8}\n"
                "- **Sources**\n"
                "  - 1720 marriage — fs:1:1:AAAA-BBB\n"
                "### Generation 9: Somewhere Line\n"
                "**Someone Else** (b. 1670)\n"
                "  - 1690 deed — fs:1:1:CCCC-DDD\n")
        cut = hs.truncate_at_break(body)
        self.assertIn("AAAA-BBB", cut, "the entry keeps its own record")
        self.assertNotIn("CCCC-DDD", cut, "and stops absorbing the next generation")
        self.assertEqual(hs.count_records(cut), 1)

    def test_the_bare_heading_form_also_closes(self):
        """`### Generation 29` with no trailing title is the form one live entry
        was absorbing."""
        body = ("**A** (b. 1200)\n- meta: {id: P-2XAMP2, generation: 28}\n"
                "  - fs:1:1:AAAA-BBB\n### Generation 29\n  - fs:1:1:CCCC-DDD\n")
        self.assertEqual(hs.count_records(hs.truncate_at_break(body)), 1)

    # ---- the two rejected signals, pinned as NEGATIVE CONTROLS ----

    def test_NEGATIVE_CONTROL_bold_PROSE_must_not_close_an_entry(self):
        """The live false-positive case. That block is preceded by
        `**Read the prior work before researching him again** — …`, which is a
        SENTENCE opening with a bold phrase, not a header — and that entry's only
        record sits below it. Truncating on a line-start bold would delete it."""
        body = ("**John Example** (d. 1716)\n"
                "- meta: {id: P-3XAMP3, generation: 12}\n"
                "**Read the prior work before researching him again** — three logs\n"
                "  - 1685 probate — fs:1:1:AAAA-BBB\n")
        cut = hs.truncate_at_break(body)
        self.assertIn("AAAA-BBB", cut,
                      "a bold sentence is not a boundary; the record must survive")
        self.assertEqual(hs.count_records(cut), 1)

    def test_NEGATIVE_CONTROL_a_generic_h3_subheading_must_not_close_an_entry(self):
        """Same entry, other failing signal: an entry legitimately contains
        narrative sub-headings (`### What the sweep added`)."""
        body = ("**John Example** (d. 1716)\n"
                "- meta: {id: P-4XAMP4, generation: 12}\n"
                "### What the 02 AUG 2026 sweep actually added\n"
                "  - 1685 probate — fs:1:1:AAAA-BBB\n")
        cut = hs.truncate_at_break(body)
        self.assertIn("AAAA-BBB", cut,
                      "a narrative sub-heading is not a boundary")
        self.assertEqual(hs.count_records(cut), 1)

    def test_a_generation_subheading_is_matched_case_insensitively(self):
        body = ("**A** (b. 1)\n- meta: {id: P-5XAMP5, generation: 3}\n"
                "  - fs:1:1:AAAA-BBB\n### generation 4\n  - fs:1:1:CCCC-DDD\n")
        self.assertEqual(hs.count_records(hs.truncate_at_break(body)), 1)

    # ---- the pre-existing break set must be untouched ----

    def test_the_EXISTING_breaks_still_work(self):
        for brk in ("---", "## Some Section"):
            body = (f"**A** (b. 1)\n- meta: {{id: P-6XAMP6, generation: 3}}\n"
                    f"  - fs:1:1:AAAA-BBB\n{brk}\n  - fs:1:1:CCCC-DDD\n")
            self.assertEqual(hs.count_records(hs.truncate_at_break(body)), 1, brk)

    def test_an_entry_with_NO_break_is_returned_whole(self):
        body = ("**A** (b. 1)\n- meta: {id: P-7XAMP7, generation: 3}\n"
                "  - fs:1:1:AAAA-BBB\n  - fs:1:1:CCCC-DDD\n")
        self.assertEqual(hs.truncate_at_break(body), body)
        self.assertEqual(hs.count_records(body), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
