#!/usr/bin/env python3
"""Pins for export_gedcom7.py's pure helpers (placeholder names only)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_gedcom7 as ex  # noqa: E402
import vault_config  # noqa: E402


class NameTests(unittest.TestCase):
    def test_surname_is_last_plain_word(self):
        self.assertEqual(ex.gedcom_name("Jane Example Ancestor"), "Jane Example /Ancestor/")

    def test_bracketed_qualifier_is_not_a_surname(self):
        self.assertEqual(ex.gedcom_name("John Sample [of Somewhereton]"), "John /Sample/")

    def test_single_name_has_no_surname(self):
        self.assertEqual(ex.gedcom_name("Halfdan"), "Halfdan")


class PlaceTests(unittest.TestCase):
    def test_place_follows_date(self):
        self.assertEqual(ex.place_of("3 SEP 1780, Somewhereton, Shire"), "Somewhereton, Shire")

    def test_research_annotation_is_cut(self):
        self.assertEqual(ex.place_of("1840, Somewhereton — CONFIRMED by register"), "Somewhereton")

    def test_no_place(self):
        self.assertEqual(ex.place_of("1840"), "")


class EventTests(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual(ex.event_lines("BIRT", "3 SEP 1780", None, "Somewhereton"),
                         ["1 BIRT", "2 DATE 3 SEP 1780", "2 PLAC Somewhereton"])

    def test_unknown_is_absent(self):
        self.assertEqual(ex.event_lines("DEAT", "unknown", None, ""), [])
        self.assertEqual(ex.event_lines("DEAT", "unknown, Shire", None, "Shire"),
                         ["1 DEAT", "2 PLAC Shire"])

    def test_header_date_with_place_normalises_without_phrase(self):
        self.assertEqual(ex.event_lines("BIRT", "BEF 1670, Somewhereton", None, "Somewhereton"),
                         ["1 BIRT", "2 DATE BEF 1670", "2 PLAC Somewhereton"])

    def test_prose_date_becomes_phrase(self):
        out = ex.event_lines("DEAT", "died young", None, "")
        self.assertEqual(out, ["1 DEAT", "2 DATE", "3 PHRASE died young"])

    def test_dual_year_keeps_phrase(self):
        out = ex.event_lines("BIRT", "JULIAN 30 JAN 1649", "30 January 1648/49", "")
        self.assertEqual(out, ["1 BIRT", "2 DATE JULIAN 30 JAN 1649", "3 PHRASE 30 January 1648/49"])


# --------------------------------------------------------------------------- #
# SOURCES (rule 8). Every case here is the POLICY decision the exporter must not
# make for itself: an include-limb locator becomes a SOUR, apparatus does not, a
# `~`-negated locator does not, and a living person's locators never leave the
# vault at all. Placeholder names and invented locators only.
# --------------------------------------------------------------------------- #

CITED = """**Jane Example Ancestor** (1880-1950)
- meta: {id: P-AAAAAA, generation: 4}
- **Sources** (harvest 01 JAN 2026, 2 records):
  - 1910 US Census, Somewhereton, in her father's household - fs:1:1:AAAA-BBB
  - her 1880 birth act - antenati:ark:/12657/an_EXAMPLE1, fs:3:1:XXXX-YYYY-ZZZZ
"""

# ⚠ Both apparatus locators cite a host the DEFAULT registry registers (`anc`).
# An unregistered host would make this case pass for the wrong reason, which is
# what CONTROL is here to prove: the same two lines, described as the records they
# are not, do yield both locators.
APPARATUS = """**John Sample** (1700-1770)
- meta: {id: P-BBBBBB, generation: 9}
- **Sources** (no record ARKs; scholarly apparatus only):
  - Example, History of the Town of Somewhereton (1893), vol. II, p. 464 - anc:9998:2222222
  - Wikipedia article on the Sample family of Somewhereton - anc:9999:1111111
"""

APPARATUS_CONTROL = APPARATUS.replace(
    "Example, History of the Town of Somewhereton (1893), vol. II, p. 464",
    "his 1735 marriage, Somewhereton").replace(
    "Wikipedia article on the Sample family of Somewhereton",
    "the 1750 Somewhereton tax list")

NEGATED = """**Mary Placeholder** (1840-1910)
- meta: {id: P-CCCCCC, generation: 6}
- **Sources** (harvest 01 JAN 2026, 1 record):
  - her 1865 marriage, Somewhereton - fs:1:1:CCCC-DDD
  - an image-less Find a Grave memorial, a contributor's assertion - ~fs:1:1:EEEE-FFF
"""


class SourceDescriptionTests(unittest.TestCase):
    def test_description_is_the_half_before_the_locators(self):
        self.assertEqual(
            ex.record_description("  - 1910 US Census, Somewhereton \u2014 fs:1:1:AAAA-BBB"),
            "1910 US Census, Somewhereton")

    def test_a_bare_locator_describes_nothing(self):
        self.assertEqual(ex.record_description("  - fs:1:1:AAAA-BBB"), "")

    def test_emphasis_glyph_and_open_parenthesis_are_cleaned(self):
        self.assertEqual(
            ex.record_description("  - \u2b50 his death, 1865 (Somewhereton \u2014 fs:1:1:AAAA-BBB"),
            "his death, 1865")


class PersonSourceTests(unittest.TestCase):
    def test_include_limb_locators_are_cited_with_their_record_name(self):
        got = ex.person_sources(CITED)
        self.assertEqual(got, [
            ("fs:1:1:AAAA-BBB", "1910 US Census, Somewhereton, in her father's household"),
            ("antenati:ark:/12657/an_EXAMPLE1", "her 1880 birth act"),
            ("fs:3:1:XXXX-YYYY-ZZZZ", "her 1880 birth act"),
        ])

    def test_apparatus_is_not_a_source(self):
        """Limb (c) books and limb (d) reference sites wear record-shaped
        locators; the title screens are what keep them off the metric, so they
        must keep them out of the file too."""
        self.assertEqual(ex.person_sources(APPARATUS), [])

    def test_apparatus_control_yields_both_locators(self):
        """The negative control: the same two lines, renamed as records, count.
        Without this the case above would also pass on an unparsed locator."""
        self.assertEqual([tok for tok, _d in ex.person_sources(APPARATUS_CONTROL)],
                         ["anc:9998:2222222", "anc:9999:1111111"])

    def test_a_negated_locator_is_not_a_citation(self):
        got = ex.person_sources(NEGATED)
        self.assertEqual([tok for tok, _d in got], ["fs:1:1:CCCC-DDD"])

    def test_negation_control_counts_the_same_locator_unmarked(self):
        self.assertEqual([tok for tok, _d in ex.person_sources(NEGATED.replace("~fs:", "fs:"))],
                         ["fs:1:1:CCCC-DDD", "fs:1:1:EEEE-FFF"])

    def test_negation_written_outside_the_sources_bullet_still_bites(self):
        """⚠ The ordering `count_records_strict` documents: the `~` is usually
        written where the rejection is EXPLAINED, not inside the Sources bullet,
        so negation has to be resolved over the whole body BEFORE it is narrowed."""
        body = CITED + "- Detached 01 FEB 2026: wrong man, ~fs:1:1:AAAA-BBB.\n"
        self.assertEqual([tok for tok, _d in ex.person_sources(body)],
                         ["antenati:ark:/12657/an_EXAMPLE1", "fs:3:1:XXXX-YYYY-ZZZZ"])

    def test_no_sources_bullet_means_no_sources(self):
        self.assertEqual(ex.person_sources("**Nobody Example** (1900-1980)\n- meta: {id: P-DDDDDD}\n"), [])


PRIVACY_TREE = """---
type: lineage
created: 2026-01-01
tags: [test]
---

# Test Lineage

### Generation 1

**Living Example** (b. 1980)
- meta: {id: P-LLLLLL, generation: 1, life_status: living}
- **Sources** (harvest 01 JAN 2026, 1 record):
  - his 1980 birth record - fs:1:1:LLLL-MMM

### Generation 2

**Dead Example** (1900-1980)
- meta: {id: P-DEADED, generation: 2, life_status: deceased}
- **Sources** (harvest 01 JAN 2026, 1 record):
  - his 1900 birth record - fs:1:1:DDDD-EEE
"""


def _privacy_vault(tmp):
    with open(os.path.join(tmp, ".autoresearch.json"), "w", encoding="utf-8") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(tmp, "Family_Tree_Test.md"), "w", encoding="utf-8") as fh:
        fh.write(PRIVACY_TREE)
    vault_config.load_config.cache_clear()
    return tmp


class PrivacyTests(unittest.TestCase):
    """A locator is a record identifier for a named person, so it is withheld with
    the dates, not published beside `RESN PRIVACY`."""

    @staticmethod
    def _indi(lines, xref):
        out, inside = [], False
        for ln in lines:
            if ln.startswith("0 "):
                inside = ln == "0 %s INDI" % xref
                continue
            if inside:
                out.append(ln)
        return out

    def test_a_living_persons_locators_never_reach_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines, stats = ex.build(_privacy_vault(tmp))
        text = "\n".join(lines)
        self.assertIn("1 RESN PRIVACY", text)
        self.assertNotIn("fs:1:1:LLLL-MMM", text)
        self.assertNotIn("1980 birth record", text)
        self.assertIn("fs:1:1:DDDD-EEE", text)
        self.assertEqual(self._indi(lines, ex.xref("I", "P-LLLLLL")).count("1 SOUR @S1@"), 0)
        self.assertEqual(stats["sourced"], 1)
        self.assertEqual(ex.check(lines), [])

    def test_include_living_details_releases_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines, stats = ex.build(_privacy_vault(tmp), include_living_details=True)
        self.assertIn("fs:1:1:LLLL-MMM", "\n".join(lines))
        self.assertEqual(stats["sourced"], 2)


class CheckTests(unittest.TestCase):
    def test_dangling_pointer_is_an_error(self):
        lines = ["0 HEAD", "1 GEDC", "2 VERS 7.0", "0 @F1@ FAM", "1 HUSB @IX@", "0 TRLR"]
        self.assertTrue(any("does not resolve" in e for e in ex.check(lines)))

    def test_level_jump_is_an_error(self):
        lines = ["0 HEAD", "2 VERS 7.0", "0 TRLR"]
        self.assertTrue(any("level jumps" in e for e in ex.check(lines)))

    def test_clean_file(self):
        lines = ["0 HEAD", "1 GEDC", "2 VERS 7.0", "0 @I1@ INDI", "1 FAMS @F1@",
                 "0 @F1@ FAM", "1 HUSB @I1@", "0 TRLR"]
        self.assertEqual(ex.check(lines), [])


if __name__ == "__main__":
    unittest.main()
