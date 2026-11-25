#!/usr/bin/env python3
"""Pins for export_gedcom7.py's pure helpers (placeholder names only)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_gedcom7 as ex  # noqa: E402


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
