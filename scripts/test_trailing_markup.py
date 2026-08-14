"""A closing markdown backtick must not become part of the locator token.

[[Open_Questions]] Q274, operator-directed 14 AUG 2026 (the code fix).

** THE DEFECT. ** A locator token is a NON-SPACE run and a backtick is not in the stop set,
so a locator written inside markdown code formatting produced a token that was a DIFFERENT
STRING from the same locator written plainly. An entry citing a record properly AND
mentioning it in backticked prose was credited with TWO records for one document.
Measured across the vault: 21 entries, 34 excess records, and exactly ONE category change.

** THE FAIL DIRECTION IS ASYMMETRIC AND THE CONTROLS BELOW MATTER MORE THAN THE FIX. **
Over-stripping DESTROYS a real citation: locators legitimately contain `:` and `/`
INTERNALLY (`antenati:ark:/12657/an_ua…`, `tna:C1/548/65`, `fs:3:1:3QS7-…`), and a strip
that reached inside a token would silently unmake evidence. So every real host form in the
registry is asserted to survive untouched.

** AND ONE LIVE DEFECT WAS UNMASKED BY THE FIX, WHICH IS WORTH KNOWING. ** A citation of
E. A. Freeman's *History of the Norman Conquest* carried a sentence-final full stop. The
malformed token had been failing `is_record_locator` and so, by accident, was not being
counted — the fix normalised it and promoted a **book** into a record (rule 8 limb (c)),
turning one row 0 -> 1. **The malformed tokens were MASKING real mis-citations**; a
per-row census diff is what caught it, and the data was fixed rather than the reader.
`test_no_row_gains_records` encodes the rule that came out of that.
"""
import unittest

import harvest_sources as H


class TestStrip(unittest.TestCase):
    def test_backtick_is_stripped(self):
        self.assertEqual(H.strip_trailing_markup("fs:1:1:ABCD-123`"), "fs:1:1:ABCD-123")

    def test_bold_and_backtick_combo(self):
        self.assertEqual(H.strip_trailing_markup("fs:1:1:ABCD-123`**"), "fs:1:1:ABCD-123")

    def test_sentence_full_stop(self):
        self.assertEqual(H.strip_trailing_markup("ia:somebook00auth."), "ia:somebook00auth")

    def test_clean_token_untouched(self):
        for tok in ("fs:1:1:ABCD-123", "fs:3:1:3QS7-99WG-KKPY", "anc:4732"):
            with self.subTest(tok=tok):
                self.assertEqual(H.strip_trailing_markup(tok), tok)


class TestNegativeControls(unittest.TestCase):
    """⚠ Over-stripping destroys evidence. Every real host form must survive."""

    def test_internal_punctuation_survives(self):
        for tok in (
            "antenati:ark:/12657/an_ua19358017",
            "antenati:ark:/12657/an_ua37834763/wj6aDjm",
            "tna:C1/548/65",
            "agad:300/872/31-1865",
            "sp:644/1/272/11",
            "hq:2469:p559",
            "ia:copyoldrecordst00masgoog:p47",
            "nycdoris:D-B-1921-0002748",
        ):
            with self.subTest(tok=tok):
                self.assertEqual(H.strip_trailing_markup(tok), tok)

    def test_a_real_locator_still_counts(self):
        body = "- 1910 US Census, Manhattan — fs:1:1:ABCD-123"
        self.assertIn("fs:1:1:ABCD-123", H.record_locators(body))

    def test_backticked_and_plain_collapse_to_one_record(self):
        # The defect, end to end: one record cited once and discussed once.
        body = ("- his 1873 death registration — fs:1:1:ABCD-123\n"
                "- note: confirmed against `fs:1:1:ABCD-123` in the index\n")
        self.assertEqual(len(set(H.record_locators(body))), 1)


class TestFormNotCited(unittest.TestCase):
    """Q200: cite a locator, never the locator FORM."""

    def test_bare_prefix_is_not_a_record(self):
        # A trailing colon is stripped, leaving something is_record_locator rejects.
        self.assertNotIn("fs:1:1", H.record_locators("browse-only registers attach as `fs:1:1:`"))


class TestNegationStillReaches(unittest.TestCase):
    """A `~`-negated token must still suppress, backtick or not."""

    def test_negated_backticked_token_does_not_count(self):
        body = "- ⚠ not evidence — ~fs:1:1:ABCD-123`"
        self.assertEqual(H.record_locators(body), [])

    def test_negated_plain_token_does_not_count(self):
        self.assertEqual(H.record_locators("- ~fs:1:1:ABCD-123"), [])


class TestNoRowGainsRecords(unittest.TestCase):
    """⚠⚠ THE RULE THAT CAME OUT OF THE FREEMAN ROW.

    Normalising a token can only ever MERGE two spellings of one record. It must never
    turn something uncounted into a credit — if it does, the entry is mis-citing a
    non-record (a book, a memorial, a tree) and the DATA is wrong, not the reader.
    Re-run the per-row census diff after any change here and assert nobody gains.
    """

    def test_merging_cannot_increase_a_count(self):
        body = ("- record A — fs:1:1:AAAA-111\n"
                "- discussed as `fs:1:1:AAAA-111` above\n")
        self.assertEqual(len(set(H.record_locators(body))), 1)

    def test_a_book_with_a_full_stop_is_still_the_entrys_problem(self):
        # After stripping, this IS a well-formed ia: locator. Whether it should count is
        # a POLICY question (rule 8 limb (c)) answered by negating it in the entry, not
        # by leaving the token malformed.
        body = "- Freeman, *Norman Conquest* — read 12 AUG 2026, ia:historyofnorman02free."
        self.assertEqual(len(H.record_locators(body)), 1)
        neg = "- Freeman, *Norman Conquest* — read 12 AUG 2026, ~ia:historyofnorman02free."
        self.assertEqual(H.record_locators(neg), [])


if __name__ == "__main__":
    unittest.main()
