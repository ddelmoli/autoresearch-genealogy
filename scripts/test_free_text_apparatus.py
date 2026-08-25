"""Free-text scholarly apparatus must screen as BOOK *and* register as CITED.

[[Open_Questions]] Q269, operator-directed 13 AUG 2026.

** THE DEFECT. ** `is_book_collection` was built for COLLECTION titles and deep
profiles are mostly FREE-TEXT CITATIONS. Measured on one profile (Henry of Scotland,
26 attachments): 18 free-text scholarly citations, **0 of 18 screened by anything**,
so a session screening that profile mechanically would have been told that Fordun's
Chronicle and the Complete Peerage are not books. The sharpest instance was a single
missing word -- the marker read `the complete peerage`, so:

    "The Complete Peerage, Vol 6"                 -> True
    "Cokayne's Complete Peerage, Vol 6, pg. 641-2" -> False

and both of that profile's citations used the second form. The article is now gone
from the marker, which catches every prefix form at once.

** WHAT THIS TEST PINS, and it is the DEPENDENCY rather than the list. ** Per
deferred 64, a work moved into the book class and NOT recognised as apparatus lands
its entry in **UNCITED** -- "nobody has cited anything" -- about a person cited to
the best evidence that exists. `test_printed_record_series.py` pins that rule for the
printed-record class; this pins it for free-text apparatus. The important assertion
is `test_every_new_book_marker_is_also_scholarly`: it walks the markers themselves,
so a future widening that forgets `SCHOLARLY_CITATION_RE` fails here rather than
silently emptying somebody's citations.

** NEGATIVE CONTROLS ARE THE OTHER HALF. ** The fail direction for a book marker is
DESTRUCTIVE -- a false positive REMOVES a real record -- so real record-collection
titles are asserted False, and the allowlist that protects transcribed registers is
re-checked here.
"""
import unittest

import harvest_sources as H


# Markers added 13 AUG 2026 that MUST also be recognised as scholarly apparatus.
# `wikitree` is deliberately excluded: it is limb (d), earns nothing, and must NOT
# be treated as apparatus.
PAIRED_MARKERS = (
    "complete peerage",
    "cracroft",
    "baronage of england",
    "scots peerage",
    "dormant and abeyant",
    "anglia sacra",
    "early sources of scottish history",
    "scottish annals from english",
    "john of fordun",
    "dictionary of national biography",
    "magna charta barons",
    "pedigrees of charlemagne",
    "genealogical memoir",
)


class TestPossessiveForms(unittest.TestCase):
    """The one-word miss that raised Q269, pinned in both directions."""

    def test_the_complete_peerage_still_screens(self):
        self.assertTrue(H.is_book_collection("The Complete Peerage, Vol 6"))

    def test_cokaynes_complete_peerage_now_screens(self):
        # This is the regression. It returned False before 13 AUG 2026.
        self.assertTrue(
            H.is_book_collection("Cokayne's Complete Peerage, Vol 6, pg. 641-2"))

    def test_other_possessive_forms(self):
        for title in (
            "Cracroft's Peerage",
            "Dugdale's Baronage of England",
            "G.E.C.'s Complete Peerage",
        ):
            with self.subTest(title=title):
                self.assertTrue(H.is_book_collection(title))


class TestMeasuredApparatus(unittest.TestCase):
    """The works actually found on the profile that raised the question."""

    def test_free_text_apparatus_screens_as_book(self):
        for title in (
            "John of Fordun's Chronicle of the Scottish Nation",
            "Anglia sacra (Wharton)",
            "The Scots Peerage",
            "Early Sources of Scottish History",
            "Scottish Annals from English Chroniclers",
            "Burke's Dormant and Abeyant Peerages",
            "Dictionary of National Biography",
            "The Magna Charta Barons",
            "Pedigrees of Charlemagne's Descendants",
            "A Genealogical Memoir of the Huntington Family",
        ):
            with self.subTest(title=title):
                self.assertTrue(H.is_book_collection(title))


class TestPairingWithScholarly(unittest.TestCase):
    """⚠⚠ The load-bearing one: deferred 64's dependency, walked mechanically."""

    def test_every_new_book_marker_is_also_scholarly(self):
        for marker in PAIRED_MARKERS:
            with self.subTest(marker=marker):
                self.assertTrue(
                    H.has_scholarly_citation(f"cited to {marker}, p. 12"),
                    f"{marker!r} screens as a BOOK but is not recognised as "
                    f"apparatus -- an entry citing only this work would fall into "
                    f"UNCITED. Widen SCHOLARLY_CITATION_RE in the SAME commit "
                    f"(deferred 64).",
                )

    def test_wikitree_is_a_tree_and_NOT_apparatus(self):
        # limb (d): screens as the excluded class, earns nothing, and must never
        # count as a scholarly citation.
        self.assertTrue(H.is_book_collection("wikitree"))
        self.assertFalse(H.has_scholarly_citation("wikitree"))


class TestIrishApparatus(unittest.TestCase):
    """The Ban-shenchus, added 24 AUG 2026 (session #182).

    ⚠⚠ FOUND BY WRITING, NOT BY AUDITING. Six entries were minted from Dobbs's
    edition in one iteration and the census called every one UNCITED -- "nobody
    has cited anything" -- about people cited to a named medieval tract at exact
    page numbers, verified at the page image. Measured the same minute: 8 rows in
    total moved UNCITED -> BOOK_SOURCED once the detector could see it, and TWO of
    them (Donnchad mac Briain, Orlaith ingen Meic Braenáin) predated the sitting.
    They had been sitting on "the real worklist, whose route is a library pass"
    while the library pass was already done and cited.

    ⛔ NOT the flattering-direction widening the baseline warns about. The test is
    whether the citation is REAL, and the rule already admits "MGH and named
    chronicles" -- this is a named 12th-c. tract in its scholarly edition. The
    direction a widening moves a count is not what makes it right or wrong.
    """

    IRISH = (
        "Ban-shenchus, ed. Dobbs, Revue Celtique XLVIII (1931), p. 189",
        "Banshenchus",
        "the metrical Ban-shenchus at Revue Celtique XLVII, p. 314",
        "Revue Celtique XLIX (1932), the edition's index",
    )

    def test_irish_apparatus_is_recognised(self):
        for cite in self.IRISH:
            with self.subTest(cite=cite):
                self.assertTrue(H.has_scholarly_citation(cite))

    def test_it_is_apparatus_only_and_NOT_a_book_collection(self):
        # ⚠ The pairing rule runs ONE WAY. BOOK_COLLECTION_MARKERS screens FS
        # COLLECTION TITLES; the Ban-shenchus is never one, so adding it there
        # would screen nothing and risks catching a real record title later.
        # Apparatus-only is the correct asymmetry -- it can only move a row toward
        # "somebody cited something", never destroy a record.
        for cite in self.IRISH:
            with self.subTest(cite=cite):
                self.assertFalse(H.is_book_collection(cite))

    def test_negative_controls(self):
        # A Celtic-sounding sentence is not a citation.
        for cite in ("an Irish genealogy website",
                     "a celtic revival poem",
                     "some notes on Irish kings"):
            with self.subTest(cite=cite):
                self.assertFalse(H.has_scholarly_citation(cite))


class TestRouteSlugIsNotACitation(unittest.TestCase):
    """Q328 (operator ruling 25 AUG 2026): the `- meta:` line is excluded.

    ** A `route:` slug is a lowercase word that collides with the apparatus regex **
    — `medlands`, `richardson`, `odnb`, `nehgs`, `weis`, `flodoard`, `regino`, `mgh`,
    `chamberlain`. Before this, declaring WHERE the evidence would be found counted
    as HAVING FOUND IT, and four `profile_status: stub` rows citing nothing at all
    were classed BOOK_SOURCED: *"finished work that can never earn a record ARK, not
    a gap"*.

    ⚠⚠ AND THE FIRST MEASUREMENT OF THIS SAID 195, NOT 4. It came from an ad-hoc
    chunker that treated any line starting `- **` as a new entry, so every entry was
    truncated at its own `- **Sources**` bullet and its citation went unseen. The
    number was wrong by ~49x and was put in front of the operator before being
    re-measured through `entry_blocks_with_ids` + `own_region`. **The mechanism was
    real; the scale was an artefact of not using the seam.** That is why the positive
    case below is a body citation living BELOW a bold body bullet — the exact shape
    the bad chunker could not see.
    """

    META = ("**Someone** (d. 1000)\n"
            "- meta: {id: P-AAAAAA, generation: 5, route: medlands}\n"
            "- prose that cites nothing")

    def test_route_slug_alone_is_NOT_apparatus(self):
        self.assertFalse(H.has_scholarly_citation(self.META))

    def test_every_colliding_route_slug_is_excluded(self):
        for slug in ("medlands", "richardson", "odnb", "nehgs", "weis",
                     "flodoard", "regino", "mgh", "chamberlain"):
            with self.subTest(slug=slug):
                body = "**X** (d. 1000)\n- meta: {id: P-AAAAAA, route: %s}\n- no citation" % slug
                self.assertFalse(H.has_scholarly_citation(body),
                                 f"route: {slug} must not credit the entry")

    def test_a_REAL_citation_below_a_bold_body_bullet_still_counts(self):
        # ⭐ The positive control the bad measurement lacked.
        body = (self.META + "\n- **Sources** (scholarly apparatus, limb (b))\n"
                "  - FMG Medlands, ANJOU MAINE (Cawley) — read directly 24 AUG 2026")
        self.assertTrue(H.has_scholarly_citation(body))

    def test_the_meta_line_does_not_mask_a_citation_on_the_same_entry(self):
        # Stripping the meta line must remove ONLY that line.
        body = "- meta: {id: P-AAAAAA, route: medlands}\ncited to the Complete Peerage, vol. 6"
        self.assertTrue(H.has_scholarly_citation(body))

    def test_bare_strings_are_unaffected(self):
        # Every other caller passes prose with no meta line at all.
        self.assertTrue(H.has_scholarly_citation("cited to Richardson, Royal Ancestry"))
        self.assertFalse(H.has_scholarly_citation("an Ancestry user tree"))


class TestNegativeControls(unittest.TestCase):
    """The fail direction is DESTRUCTIVE, so real records must stay records."""

    def test_record_collections_are_not_books(self):
        for title in (
            "Massachusetts State Vital Records, 1638-1927",
            "England and Wales Census, 1881",
            "Scotland Births and Baptisms, 1564-1950",
            "New York, New York City Births, 1846-1909",
            "Italy, Sondrio, Civil Registration, 1866-1937",
        ):
            with self.subTest(title=title):
                self.assertFalse(H.is_book_collection(title))

    def test_transcribed_registers_stay_allowlisted(self):
        # deferred 64: a printed TRANSCRIPTION of a register is a RECORD.
        for title in (
            "Massachusetts Town and Vital Records, 1620-1988",
            "Vital Records to 1850",
            "England, Church Records",
        ):
            with self.subTest(title=title):
                self.assertFalse(H.is_book_collection(title))

    def test_a_peerage_record_series_is_not_swallowed(self):
        # `scots peerage` must not catch an ordinary Scottish record collection.
        self.assertFalse(
            H.is_book_collection("Scotland, Statutory Registers, Deaths"))


if __name__ == "__main__":
    unittest.main()
