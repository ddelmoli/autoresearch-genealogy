#!/usr/bin/env python3
"""Pins for export_gedcom7.py's pure helpers (placeholder names only)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_gedcom7 as ex  # noqa: E402
import person_store as ps  # noqa: E402
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


# --------------------------------------------------------------------------- #
# BRACKETED ANNOTATION (vault header convention: the annotation sits in `[...]`
# inside the date/place slot). The brackets must come off the parenthetical BEFORE
# the born/died split, because an annotation containing a `;` otherwise truncates
# the slot and takes the real place tail with it. Placeholder names only.
# --------------------------------------------------------------------------- #

class StripBracketedTests(unittest.TestCase):
    def test_span_in_the_middle_leaves_the_tail(self):
        self.assertEqual(
            ps.strip_bracketed("b. 5 JUL 1760, **Sampleton** [his own 1832 declaration; "
                               "another work gives Othertown], MA"),
            "b. 5 JUL 1760, **Sampleton**, MA")

    def test_span_at_the_end(self):
        self.assertEqual(ps.strip_bracketed("d. 1880, Somewhereton [age 22, cert. no. 534]"),
                         "d. 1880, Somewhereton")

    def test_two_spans(self):
        self.assertEqual(ps.strip_bracketed("b. SEP 1843, Example district [incl. Othertown] [GRO Q3]"),
                         "b. SEP 1843, Example district")

    def test_nested_spans(self):
        """A non-greedy regex closes on the INNER bracket and leaves the rest of the
        outer one behind as prose; the vault really does nest them."""
        self.assertEqual(
            ps.strip_bracketed('b. 1885, Placeland [the former "Othertown [Strong]" was '
                               'downgraded; town TBD]; d. 1972, Somewhereton'),
            "b. 1885, Placeland; d. 1972, Somewhereton")

    def test_unclosed_span_takes_the_rest(self):
        self.assertEqual(ps.strip_bracketed("b. 1900, Somewhereton [note that runs off the end"),
                         "b. 1900, Somewhereton")


class HeaderVitalsUnannotatedTests(unittest.TestCase):
    @staticmethod
    def _rec(paren):
        return type("R", (), {"raw": {"header_paren": paren}})()

    def test_semicolon_inside_the_annotation_no_longer_eats_the_place(self):
        """The regression this exists for: `;` terminates the born match, so with
        the brackets left in, the `, MA` after the closing bracket is lost."""
        paren = ('b. 5 JUL 1760, **Sampleton** [his own 1832 declaration; another work '
                 'gives Othertown], MA; d. 12 JAN 1840, Othertown, Shire, MA')
        self.assertEqual(ps.header_vitals_unannotated(self._rec(paren)),
                         ("5 JUL 1760, Sampleton, MA", "12 JAN 1840, Othertown, Shire, MA"))
        # the control: verbatim parsing keeps the annotation and drops the tail
        self.assertEqual(ps._parse_vitals(paren)[0],
                         "5 JUL 1760, Sampleton his own 1832 declaration")

    def test_no_header_parenthetical(self):
        self.assertEqual(ps.header_vitals_unannotated(self._rec("")), (None, None))
        self.assertEqual(ps.header_vitals_unannotated(object()), (None, None))


class PlaceAnnotationTests(unittest.TestCase):
    """End to end on the three shapes, parenthetical in and PLAC out."""

    @staticmethod
    def _places(paren):
        rec = type("R", (), {"raw": {"header_paren": paren}})()
        hb, hd = ps.header_vitals_unannotated(rec)
        return ex.place_of(hb or ""), ex.place_of(hd or "")

    def test_annotation_with_a_tail_after_it(self):
        self.assertEqual(
            self._places('b. 5 JUL 1760, **Sampleton** [his own 1832 declaration; '
                         'another work gives Othertown], MA; d. 12 JAN 1840, Othertown, Shire, MA'),
            ("Sampleton, MA", "Othertown, Shire, MA"))

    def test_annotation_at_the_end_of_the_slot(self):
        self.assertEqual(self._places("b. 1858, Somewhereton; d. 1880, Othertown [age 22, cert. no. 534]"),
                         ("Somewhereton", "Othertown"))

    def test_cause_of_death_annotation_is_not_a_place(self):
        self.assertEqual(
            self._places("b. 1920, Shiretown, Example County [US-born per cert]; "
                         "d. 29 APR 1921, Example Hospital, Shiretown, Example County "
                         "[broncho-pneumonia, 2 days; single, male]"),
            ("Shiretown, Example County", "Example Hospital, Shiretown, Example County"))

    def test_a_stated_absence_is_not_a_place(self):
        self.assertEqual(ex.place_of("ABT 1756, origin unknown"), "")
        self.assertEqual(ex.place_of("1800, parish unknown"), "")
        self.assertEqual(ex.place_of("1800, Unknown, Shire"), "Unknown, Shire")  # a real name


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

**Living Example** (b. 1980, Hidden Town [a sensitive annotation])
- meta: {id: P-LLLLLL, generation: 1, life_status: living, born: '1980'}
- **Sources** (harvest 01 JAN 2026, 1 record):
  - his 1980 birth record - fs:1:1:LLLL-MMM

### Generation 2

**Dead Example** (b. 1900, Open Town [an annotation]; d. 1980, Open Town)
- meta: {id: P-DEADED, generation: 2, life_status: deceased, born: '1900', died: '1980'}
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

    def test_a_living_persons_place_annotation_is_withheld_with_the_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines, _ = ex.build(_privacy_vault(tmp))
        text = "\n".join(lines)
        self.assertNotIn("Hidden Town", text)
        self.assertNotIn("sensitive annotation", text)
        self.assertIn("Open Town", text)       # the deceased person's place still ships

    def test_include_living_details_releases_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines, stats = ex.build(_privacy_vault(tmp), include_living_details=True)
        self.assertIn("fs:1:1:LLLL-MMM", "\n".join(lines))
        self.assertEqual(stats["sourced"], 2)


# --------------------------------------------------------------------------- #
# PARTNER SLOTS. HUSB/WIFE is a slot, not a sex: GEDCOM 7 reads no sex from the
# tag, but the file has no third slot, so an order must be picked. A recorded
# `sex` decides; with none recorded the order is `sex_inference`'s guess, which
# is wording and NEVER a SEX tag. Ada is the alphabetically first id throughout,
# so the arbitrary fill would always put HER in HUSB.
# --------------------------------------------------------------------------- #

COUPLE_TREE = """---
type: lineage
created: 2026-01-01
tags: [test]
---

# Test Lineage

### Generation 3

**Ada Placeholder** (b. 1850; d. 1920)
- meta: {id: P-AAAAAA, generation: 3, life_status: deceased, spouse: [P-BBBBBB], born: '1850', died: '1920'}
- She kept the shop after her father died, and her daughters worked beside her.
- **Sources** (harvest 01 JAN 2026, 1 record):
  - her 1850 birth record - fs:1:1:AAAA-AAA

**Bruno Placeholder** (b. 1848; d. 1915)
- meta: {id: P-BBBBBB, generation: 3, life_status: deceased, spouse: [P-AAAAAA], born: '1848', died: '1915'}
- He carted stone for the quarry, and his brothers followed him into the trade.
- **Sources** (harvest 01 JAN 2026, 1 record):
  - his 1848 birth record - fs:1:1:BBBB-BBB

### Generation 1

**Cora Placeholder** (b. 1985)
- meta: {id: P-CCCCCC, generation: 1, life_status: living, spouse: [P-DDDDDD]}
- She teaches, and her own note says which school.
- **Sources** (harvest 01 JAN 2026, 1 record):
  - her birth record - fs:1:1:CCCC-CCC

**Dov Placeholder** (b. 1983)
- meta: {id: P-DDDDDD, generation: 1, life_status: living, spouse: [P-CCCCCC]}
- He works for the railway, and his own note says which line.
- **Sources** (harvest 01 JAN 2026, 1 record):
  - his birth record - fs:1:1:DDDD-DDD
"""


def _couple_vault(tmp):
    with open(os.path.join(tmp, ".autoresearch.json"), "w", encoding="utf-8") as fh:
        json.dump({"person_model": "narrative"}, fh)
    with open(os.path.join(tmp, "Family_Tree_Couples.md"), "w", encoding="utf-8") as fh:
        fh.write(COUPLE_TREE)
    vault_config.load_config.cache_clear()
    return tmp


class PartnerSlotTests(unittest.TestCase):
    PAIR = ["P-AAAAAA", "P-BBBBBB"]
    GUESS = {"P-AAAAAA": "F", "P-BBBBBB": "M"}

    def test_inference_orders_a_couple_the_fill_would_have_got_wrong(self):
        self.assertEqual(ex.partner_slots(self.PAIR, {}, self.GUESS),
                         (["P-BBBBBB"], ["P-AAAAAA"], [], "inference"))

    def test_a_recorded_sex_is_not_overridden_by_inference(self):
        # The vault says Ada is M. Only a record may say that, and it wins.
        self.assertEqual(
            ex.partner_slots(self.PAIR, {"P-AAAAAA": "M"}, self.GUESS),
            (["P-AAAAAA"], ["P-BBBBBB"], [], "recorded"))

    def test_one_recorded_partner_still_fills_the_other_slot(self):
        self.assertEqual(
            ex.partner_slots(self.PAIR, {"P-BBBBBB": "F"}, {}),
            (["P-AAAAAA"], ["P-BBBBBB"], [], "recorded"))

    def test_an_unresolved_couple_keeps_the_arbitrary_fill(self):
        self.assertEqual(ex.partner_slots(self.PAIR, {}, {"P-AAAAAA": "F"}),
                         (["P-AAAAAA"], ["P-BBBBBB"], [], "arbitrary"))

    def test_an_inferred_same_sex_couple_keeps_the_arbitrary_fill(self):
        self.assertEqual(
            ex.partner_slots(self.PAIR, {}, {"P-AAAAAA": "F", "P-BBBBBB": "F"}),
            (["P-AAAAAA"], ["P-BBBBBB"], [], "arbitrary"))

    def test_a_recorded_u_is_an_answer_and_not_a_slot(self):
        # `U` = looked, unknown. It takes no slot and invites no guess.
        self.assertEqual(ex.partner_slots(self.PAIR, {"P-AAAAAA": "U"}, {}),
                         (["P-AAAAAA"], ["P-BBBBBB"], [], "arbitrary"))

    def test_a_third_partner_is_never_reordered_only_noted(self):
        trio = self.PAIR + ["P-CCCCCC"]
        husb, wife, extra, how = ex.partner_slots(trio, {}, self.GUESS)
        self.assertEqual((husb, wife, extra), (["P-AAAAAA"], ["P-BBBBBB"], ["P-CCCCCC"]))
        self.assertEqual(how, "arbitrary")


class InferredSlotExportTests(unittest.TestCase):
    """The same rule through the whole exporter, over a vault with no recorded sex."""

    @staticmethod
    def _fam(lines, xref):
        out, inside = [], False
        for ln in lines:
            if ln.startswith("0 "):
                inside = ln == "0 %s FAM" % xref
                continue
            if inside:
                out.append(ln)
        return out

    def _build(self, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            return ex.build(_couple_vault(tmp), **kw)

    def test_the_inferred_male_goes_in_husb(self):
        lines, stats = self._build()
        fam = self._fam(lines, "@F1@")
        self.assertEqual(fam[:2], ["1 HUSB %s" % ex.xref("I", "P-BBBBBB"),
                                   "1 WIFE %s" % ex.xref("I", "P-AAAAAA")])
        self.assertEqual(stats["inferred_slots"], 2)       # both couples
        self.assertEqual(stats["slots_swapped"], 2)        # both wrong under the fill
        self.assertEqual(ex.check(lines), [])

    def test_no_sex_tag_is_emitted_for_an_inferred_person(self):
        lines, _ = self._build()
        self.assertEqual([ln for ln in lines if ln.startswith("1 SEX")], [])

    def test_a_private_couple_is_ordered_but_gains_no_field(self):
        lines, _ = self._build()
        fam = self._fam(lines, "@F2@")
        self.assertEqual(fam, ["1 HUSB %s" % ex.xref("I", "P-DDDDDD"),
                               "1 WIFE %s" % ex.xref("I", "P-CCCCCC")])
        text = "\n".join(lines)
        self.assertIn("1 RESN PRIVACY", text)
        self.assertNotIn("fs:1:1:CCCC-CCC", text)          # the guess reads the entry;
        self.assertNotIn("fs:1:1:DDDD-DDD", text)          # the file still gets none of it
        self.assertNotIn("railway", text)

    def test_a_lost_inference_costs_the_order_not_the_export(self):
        self.assertEqual(ex.inferred_sexes("/nonexistent-vault-path"), {})


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
