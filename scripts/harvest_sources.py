#!/usr/bin/env python3
"""
Coverage audit for FS source ARKs in vault narrative entries.

Recipe-S (source harvesting) extracts FS-attached primary-source ARKs from each
FS profile's Sources tab and appends them to the corresponding vault narrative
entry. This script audits which narrative entries are well-sourced vs which
need a Recipe-S harvest pass.

Strategy:
1. Read the canonical roster from the NARRATIVES via
   gen_person_index.parse_narrative() — VAULT-ID -> (name, gen, tier, file, pid) —
   for EVERY entry (Person_Index.md was retired; see memory
   project_person_index_retirement).

   ** KEYED ON THE VAULT `id`, NOT THE FS PID (26 JUL 2026). ** This step used to
   read "entries with no FS PID are skipped (no FS profile to harvest)". True for
   HARVESTING, false for CENSUSING, and one function served both: 210 of 1,320
   entries — 16% of the reference vault — reached no category at all, 60 of them
   carrying a Sources bullet and 12 carrying real locators. `fs: none` is the
   sharpest case: it MEANS "searched FS, confirmed absent", a proper finding, and
   it erased the person from the vault's own coverage numbers. The `id` is unique,
   never reused, and BLOCKING in `gen_person_index --integrity`, so keying on it
   cannot drop anyone. `pid` rides along and still drives all FS-facing work.

   NO_NARRATIVE is vacuous by construction ONCE the roster and
   this module agree on what an entry is — which they now do, both reading through
   the meta-anchored `person_store` seam. It was NOT vacuous while this module
   detected entries by bold-name shape: 52 entries the roster could see were
   invisible here and silently inherited a neighbouring entry's records, which is
   exactly why the category read 0 and looked vacuous. See spec/entry-boundary
   Spec 05.
2. Read each entry's BLOCK from the same seam (`entry_blocks_by_file`), truncated at
   the next structural break, and count the source records cited inside it.
3. Count ARK references in each entry's body:
   - Long-form  `ark:/61903/(1:1:[A-Z0-9-]+)`
   - Short-form `1:1:[A-Z0-9-]{6,}` standalone tokens
4. Classify EVERY entry by record count (PID-bearing or not):
   - SOURCE_GAP (0 ARKs) — highest priority Recipe-S target
   - BOOK_SOURCED / UNCITED (0 ARKs, but structurally unsourceable) — a 0-ARK entry
     that can essentially NEVER acquire an indexed-record ARK, so it must not inflate
     the actionable SOURCE_GAP to-do count. Two classes qualify: (a) deep medieval /
     early-modern ancestors (Gen >= STRUCTURAL_GEN) documented by peerage books,
     heraldic visitations, and GMB volumes rather than indexed vital records;
     (b) pre-civil-registration lines whose parish registers are not digitized
     online (in-person only), declared per-vault in .autoresearch.json.

     These two categories REPLACE the former single STRUCTURAL_GAP (split 23 JUL
     2026), because that one bucket answered the wrong question. It said "cannot be
     harvested", which conflated finished work with untouched work:
       BOOK_SOURCED  cites scholarly apparatus — Cawley/Medlands, Richardson,
                     Complete Peerage, ODNB, the Henry Project, MGH/chronicles,
                     Great Migration. DOCUMENTED. Not a gap, and no amount of
                     Recipe-S will ever change its ARK count. Do not chase these.
       UNCITED       cites NOTHING — no record ARK and no book either. Genuinely
                     unresearched, and previously invisible because it hid inside
                     the same bucket as Charlemagne.
     UNCITED is the actionable one, and its route is a LIBRARY/archive pass, not an
     FS harvest. Measured at the split: 186 structural entries were 101 BOOK_SOURCED
     and 85 UNCITED — i.e. nearly half of what the census had been reporting as
     "unsourceable, cited in prose" was not cited anywhere at all.
   - LOW_COVERAGE (1-3 ARKs) — partial coverage
   - WELL_SOURCED (4+ ARKs) — done
   SOURCE_GAP therefore reads as "work remaining" (read-only Recipe-S harvest or an
   operator-gated Source-Linker attach can move it), not "depth of tree."
5. Report by generation + region to prioritize next harvest rounds.

Does NOT edit any files. Outputs categorized lists + summary tables.

Filtering:
  --gen N        Only show ancestors at Generation N
  --gen-range    e.g. --gen-range 3-5
  --confidence X Only Strong/Moderate/etc (S/M/Sp/U)
  --limit N      Cap per-category report length
  --csv          Output a single CSV instead of categorized report
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import shard_manifest
import gen_person_index as G
import privacy_gate
import vault_config
# NOTE: `tree_locator` and `meta_presence_audit` are no longer imported. They supplied
# the person-name heuristic that decided whether a bold string was a header; entry
# detection is meta-anchored now, so nothing here has to guess at names.

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
PID_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{3})\b")
# Source-citation formats counted toward coverage. Per the source-harvest policy
# (CLAUDE.md invariant #8, adopted 02 JUN 2026): count INDEPENDENT PRIMARY records
# only — FS-indexed record ARKs AND external archive image links (Antenati, metryki,
# szukajwarchiwach). Do NOT count published-book citations or user-tree citations
# (RootsFinder, copied Ancestry/WikiTree trees) — books belong as prose citations and
# trees are not independent evidence.
#
# FS-indexed ARK formats observed in vault narratives:
#   ark:/61903/1:1:XXXX-XXX
#   1:1:XXXX-XXX
#   FamilySearch ARK ark:/61903/1:1:XXXX-XXX  (long form)
#   FamilySearch ARK XXXX-XXX                 (bare-PID-as-ARK form)
#   FamilySearch ARK XXXX-YYYY                (bare-PID-as-ARK form, 4-4)
# FS image / browse-record ARKs (the 3:1: namespace). These are the actual register
# IMAGE links ("Web Page (Link to the Record)" → View the original document), the
# primary source for browse-only collections — e.g. some browse-only civil-registration
# (Stato Civile / Tribunale) registers attach as 3:1: image ARKs, NOT 1:1: indexed records:
#   ark:/61903/3:1:XXXX-YYYY-ZZZZ
#   3:1:XXXX-YYYY-ZZZZ-N   (multi-segment image ID)
# External-archive primary-source formats (Italian/Polish lines especially):
#   ark:/12657/an_...                         (Antenati / Portale Antenati)
#   https://metryki.genealodzy.pl/...         (APW-held Polish register scans)
#   https://www.szukajwarchiwach.gov.pl/...   (Polish State Archives)
#   agadd2.home.net.pl/.../PL_1_300_<syg>_<img>.jpg  (AGAD Fond 300 Galician register
#       scans. Keyed on the PL_<archive>_<fond>_<syg>_<img>.jpg scan FILENAME, not
#       the domain, because vault bullets cite later acts in a set as
#       ".../<syg>/PL_1_300_<syg>_<img>.jpg" shorthand; the filename appears in every
#       citation form and dedupes per act.)
# Match all then dedupe by source-record-ID / URL:
ARK_PATTERNS = [
    re.compile(r"\b1:1:([A-Z0-9]{3,}-[A-Z0-9]{3,})\b"),
    re.compile(r"\bark:/61903/1:1:([A-Z0-9]{3,}-[A-Z0-9]{3,})", re.IGNORECASE),
    # FS image/browse ARKs (3:1: namespace; IDs are multi-segment, 2-4 hyphen groups)
    re.compile(r"\b(?:ark:/61903/)?3:1:([A-Z0-9]{3,}(?:-[A-Z0-9]+){1,4})", re.IGNORECASE),
    # Bare PID following an explicit "ARK" keyword (not "ARK ark:/...")
    re.compile(r"\b(?:Family[Ss]earch\s+)?ARK\s+([A-Z0-9]{3,}-[A-Z0-9]{3,})\b"),
    # External archive primary sources (Antenati ARK + Polish register URLs)
    re.compile(r"\bark:/12657/([\w.\-]+)", re.IGNORECASE),
    re.compile(r"\b(metryki\.genealodzy\.pl/[^\s)\]]+)", re.IGNORECASE),
    re.compile(r"\b(szukajwarchiwach\.(?:gov\.pl|pl)/[^\s)\]]+)", re.IGNORECASE),
    # AGAD scan filenames (agadd2.home.net.pl direct-URL images, incl. ".../<syg>/..." shorthand)
    re.compile(r"\b(PL(?:_\d+){3,4}\.jpg)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------- negated locators
# A locator prefixed with `~` is DELIBERATELY NOT EVIDENCE and is not counted.
#
# Why this exists (deferred_decisions 28, added 01 AUG 2026). Recording WHY a source
# was excluded requires naming it, and until now naming it in any documented form made
# this census COUNT it: a "NOT COUNTED - Find a Grave, policy (e)" bullet citing
# `1:1:694C-W9N2` moved that person from SOURCE_GAP to LOW_COVERAGE, crediting her with
# the two sources the bullet existed to exclude. The vault had one syntax for "this
# locator is evidence for this person" and none for "this locator exists and is
# deliberately NOT evidence", so every exclusion was either undocumented or silently
# counted -- which is also why the Find a Grave population (item 18) could not be
# measured.
#
# The form is `~` immediately before the locator, host prefix included if present:
#     ~fs:1:1:694C-W9N2      ~1:1:694C-W9N2      ~ark:/61903/1:1:694C-W9N2
# It suppresses that ONE locator; an unmarked locator on the same line still counts.
# Suppression is implemented by blanking the negated span BEFORE any pattern runs, so
# every counter inherits it and none can drift.
# The SHORT host ids the migration emits as `host:` prefixes. Detection keys on
# these (not full words like "FamilySearch") so a prose "FamilySearch: the site"
# is never mistaken for a locator line. Includes hosts with no legacy pattern
# (anc/wt/etc.) whose locators only ever appear host-prefixed.
#
# ** DERIVED FROM THE VAULT'S `hosts` REGISTRY SINCE 02 AUG 2026 (session #130). **
# This was a hard-coded literal while `vault_config.DEFAULTS["hosts"]` was a separate
# registry, so the two disagreed in both directions: `anc`/`wt` were counted but not
# registered, and registering a host did NOTHING because nothing read the registry.
# "Register the host" (the deferred-17 remedy) was therefore a no-op for counting.
# The registry is now the single source of truth, and a vault adds a host by adding
# it to `.autoresearch.json` `hosts` -- no code change.
#
# `familysearch` is the one registry key whose emitted prefix differs (`fs`), so a
# host may declare `short`. Everything else emits under its own key.
#
# ⚠ SORTED LONGEST-FIRST. These are joined into a regex alternation, and Python's `|`
# is first-match-wins: with `agad` before `agadd2` the longer id could never match.
_FALLBACK_HOST_IDS = ["fs", "anc", "wt", "antenati", "metryki", "szukajwarchiwach",
                      "agad", "tna"]


def _emitted_host_ids():
    """Short host ids from the vault registry; the literal above if unavailable.

    Import-time config reads must never be fatal: `resolve_vault()` is strict by
    design and raises when no vault is selected, and a module that cannot be imported
    without a vault would break every `--help` and every unit test."""
    try:
        import vault_config
        hosts = vault_config.get_hosts(vault_config.resolve_vault())
        ids = {(spec or {}).get("short") or key for key, spec in (hosts or {}).items()}
        ids.discard("familysearch")          # emitted as its `short`, "fs"
        if ids:
            return sorted(ids, key=lambda s: (-len(s), s))
    except BaseException:
        # ⚠ BaseException, not Exception: `resolve_vault()` signals "no vault" with
        # SystemExit, which does NOT inherit from Exception. An `except Exception`
        # here let it escape and made importing this module fatal whenever
        # AUTORESEARCH_VAULT was unset -- caught by test_host_registry.
        pass
    return sorted(_FALLBACK_HOST_IDS, key=lambda s: (-len(s), s))


EMITTED_HOST_IDS = _emitted_host_ids()


#
# ** THE FIRST ALTERNATIVE IS A GENERIC `~<registered-host>:<token>` FORM, ADDED
# 02 AUG 2026 (session #130), AND WITHOUT IT NEGATION SILENTLY DID NOT WORK FOR
# HALF THE HOSTS. ** The list below enumerates locator SHAPES (ark paths, `1:1:`
# ids, archive URLs). Those cover FamilySearch, Antenati, metryki and
# szukajwarchiwach — but an `id`-kind host has no distinctive shape, so
# `~anc:2704:14165620` and `~tna:C1/548/65` matched NOTHING and kept counting.
# Measured when found: every one of the 69 `~fs:` exclusions in the corpus worked,
# and the single `~anc:` one did not. That is deferred_decisions 28's own failure
# mode ("documenting an exclusion used to create one") surviving for the hosts it
# was never tested against, and it would have hit all four hosts registered today.
# Built from EMITTED_HOST_IDS so a newly registered host is negatable immediately.
NEGATED_LOCATOR_RE = re.compile(
    r"~\s*(?:"
    r"(?:" + "|".join(EMITTED_HOST_IDS) + r"):[^\s,;)\]]+"
    r"|(?:[A-Za-z]{2,8}:)?(?:"
    r"ark:/\d+/[\w.:\-]+"
    r"|[13]:1:[A-Z0-9][A-Z0-9\-]*"
    r"|(?:Family[Ss]earch\s+)?ARK\s+[A-Z0-9]{3,}-[A-Z0-9]{3,}"
    r"|metryki\.genealodzy\.pl/[^\s)\]]+"
    r"|szukajwarchiwach\.(?:gov\.pl|pl)/[^\s)\]]+"
    r"|PL(?:_\d+){3,4}\.jpg"
    r")"
    r")",
    re.IGNORECASE,
)


def strip_negated_locators(text: str) -> str:
    """Blank every `~`-prefixed locator so no counter can see it."""
    return NEGATED_LOCATOR_RE.sub(" ", text or "")


# ** THE MEMORIAL CLASSES, IN ONE PLACE (deferred_decisions 33, option 1;
# operator-directed 02 AUG 2026). **
#
# Policy (e) excludes contributor-built memorial and headstone indexes from the
# record census. `CLAUDE.method.md` carries a standing warning that this "IS A
# POLICY, NOT YET A COUNTER", and that is exactly right about a locator ALREADY IN
# THE VAULT: a bare `fs:1:1:QVKJ-YZTW` does not say which collection it belongs to,
# so no text analysis can tell a Find a Grave ARK from a parish register.
#
# ** It is exactly WRONG about the moment of harvest. ** With Detail View on, each
# source row renders its full citation, COLLECTION TITLE INCLUDED. Session #128 used
# that to identify and negate 12 memorial locators mechanically, in the same pass
# that read the records. So the retrospective backlog still needs a resolve-against-FS
# pass (item 33 option 3, deferred), but a conformant harvest can never add a NEW one.
#
# This list exists so the classification has ONE home. It was previously restated in
# prose in prompts 19 and 25 and in CLAUDE.method.md, which is three places to drift
# — and the vault's own rule is "do NOT restate the rule inline where it can drift".
#
# ⚠ MATCHED ON THE COLLECTION TITLE, NEVER ON THE ARK. There is deliberately no
# locator-shaped test here, because there cannot be one.
MEMORIAL_COLLECTION_MARKERS = (
    "find a grave",
    "findagrave",
    "billiongraves",
    "billion graves",
    "cemetery memorial index",
    "headstone index",
    "grave index",
)

# Titles that CONTAIN a memorial marker but are NOT the excluded class. JOWBR is the
# worked case and the reason this list exists: it is itself a contributor-built burial
# index, this vault cites it throughout, and the operator's 01 AUG 2026 ruling turned
# on the point that banning one brand while trusting another of the same class was not
# a principled line. Burial evidence is credited to the BIOGRAPHY (a `- **Burial
# evidence**` bullet + the bio_completeness `burial` facet), not to the ARK census.
MEMORIAL_ALLOWLIST_MARKERS = (
    "jowbr",
    "jewish online worldwide burial",
)


def is_memorial_collection(title: str) -> bool:
    """Does this FS collection title name a policy-(e) memorial/headstone index?

    Call it at HARVEST time with the collection title Detail View renders, and negate
    a positive with the `~` prefix so the locator is documented without being counted.

    ⚠ ** THIS DECIDES THE CLASS, NOT THE TIER. ** The 01 AUG 2026 ruling is that the
    test is the ARTIFACT: a PHOTOGRAPHED STONE you have actually looked at is real
    evidence of a death date and a burial, and belongs in a `- **Burial evidence**`
    bullet; an image-less memorial page is a contributor's assertion worth nothing;
    a modern monument for a pre-1750 person is memorialisation. Telling those apart
    requires OPENING the memorial, so no function can do it — this only answers
    "is this collection the excluded class", which is the part a harvest can automate.
    """
    t = (title or "").casefold()
    if any(m in t for m in MEMORIAL_ALLOWLIST_MARKERS):
        return False
    return any(m in t for m in MEMORIAL_COLLECTION_MARKERS)


# ── policy (c): PUBLISHED BOOKS, JOURNALS AND COMPILED INDEXES ──────────────────
#
# ⚠ THE LIMB LETTERS HERE WERE OFF BY ONE UNTIL 05 AUG 2026. This block and the
# `is_book_collection` docstring called books "policy (d)" while CLAUDE.method.md
# rule 8 — the authority — has always had (c) books, (d) user trees, (e) memorials,
# and even points AT this function as "limb (c)". Nothing computed changed; the
# labels did. It surfaced while implementing Q182, whose whole ruling is expressed
# as "(c) or (d)?", which is unreadable against a file that disagrees about which
# is which. Comments naming a rule are part of the rule.
#
# ⚠ WHY THIS EXISTS AT ALL. Limb (e) has had `is_memorial_collection` since 02 AUG
# 2026 and it demonstrably works. Limb (c) — "published-book / journal citations …
# real but bibliographic" — had NOTHING: no function, no list, no test. And both
# hosts serve books with RECORD-SHAPED LOCATORS, so nothing about the locator
# betrays them:
#   * Ancestry sells `Colonial Families of the USA`, `Mayflower Births and Deaths`,
#     `The Great Migration`, `Millennium File`, `A book of Strattons` as
#     "collections" with `anc:<collection>:<record>` ids.
#   * ⭐ FamilySearch serves DIGITISED BOOKS as `3:1:` IMAGE ARKs — the same form
#     rule 8 limb (a2) describes as the "View the original document" REGISTER image
#     and counts unconditionally. Two of Anne Plummer's three "record ARKs" were a
#     compiled marriage abstract (Torrey's) and a printed town genealogy.
#
# Measured on ONE 21-row ROTATE slice, 03 AUG 2026: twelve entries were credited
# with records that are not records, including two classified WELL_SOURCED on zero
# and one own-life record, and a Magna Carta surety dead in 1219 carried on a Find
# a Grave. Raised and settled as deferred_decisions 48.
#
# ⚠ MATCHED ON THE COLLECTION TITLE, NEVER ON THE LOCATOR — same rule as (e), same
# reason: there cannot be a locator-shaped test.
#
# ⚠⚠ THIS LIST IS A FLOOR, NEVER A TOTAL. It cannot enumerate every compiled work,
# and it is not meant to: the CAUSE of the twelve bad entries was that every one of
# them was a BARE LOCATOR LIST with no record description, which is the thing rule 8
# already requires and that ran at 4% adoption. Name the record; this is the net for
# what slips through.
BOOK_COLLECTION_MARKERS = (
    # compiled genealogies, lineage-society and reference works served as "records"
    "great migration",
    "mayflower births and deaths",
    "mayflower increasings",
    "colonial families",
    "family histories",
    "genealogical history",
    "millennium file",
    "family group record",
    "american genealogical-biographical index",
    "american genealogical biographical index",
    "royal descents",
    "the complete peerage",
    "new england marriages prior to",   # Torrey's — an abstract INDEX, not the register
    "u.s. and international marriage records",
    "sons of the american revolution",
    "daughters of the american revolution",
    # aggregated user trees sold as collections (limb (d), same treatment)
    "family trees",
    "community trees",
    "geneanet",
    "myheritage",
    "rootsfinder",
    "onegreatfamily",
)

# Titles that CONTAIN a book marker but ARE a record collection. Kept for the same
# reason as the memorial allowlist: a brand ban that catches the wrong thing is worse
# than no test. `Town and Vital Records` and the like are transcribed REGISTERS.
BOOK_ALLOWLIST_MARKERS = (
    "town and vital records",
    "town clerk, vital and town records",
    "vital records to 1850",
    "parish registers",
    "church records",
    "extracted church of england",
)


def is_book_collection(title: str) -> bool:
    """Does this collection title name a policy-(c) BOOK / journal / compiled index?

    Call it at HARVEST time with the collection title, exactly as for
    `is_memorial_collection`, and negate a positive with the `~` prefix so the
    locator is documented without being counted. A `- **Sources**` sub-bullet whose
    description names the work is what makes this checkable at all.

    ⚠ Returns the CLASS, not a verdict on worth. A book can be excellent evidence and
    still not be a RECORD: rule 8 limb (b) deliberately credits scholarly apparatus
    to `profile_status`, and deliberately keeps it OFF the ARK coverage metric so
    coverage cannot inflate on bibliography. Cite Cawley, the Complete Peerage or a
    TAG article in prose with page refs — just not as a record locator.
    """
    t = (title or "").casefold()
    if any(m in t for m in BOOK_ALLOWLIST_MARKERS):
        return False
    return any(m in t for m in BOOK_COLLECTION_MARKERS)


# ── policy (c)/(d) SPLIT: ENCYCLOPEDIAS, WIKIS AND REFERENCE WEBSITES ───────────
#
# ⚠ WHY A THIRD CLASSIFIER AND NOT A LONGER BOOK LIST. Rule 8 enumerates (c)
# published books/journals and (d) user-tree citations. FamilySearch attaches a
# third thing that is NEITHER: Wikipedia, Quora, Encyclopaedia Britannica,
# BritRoyals, the International Genealogical Index and the "Directory of Royal
# Genealogical Data". They match no book keyword and no tree keyword, so a title
# classifier files them in the RECORD bucket — which is exactly what happened in
# session #144: **"27 records" was reported for HENRY I, a man dead in 1135**,
# before the titles were read. Measured that sitting, on two English royal/baronial
# rows: 48 attachments of which ~10 were this class and **0** were records; and
# 28 / 3 / **0**.
#
# ⭐ OPERATOR RULING 05 AUG 2026 (Open_Questions Q182): the class SPLITS, because
# its members are not alike.
#   * limb (d) — WIKIPEDIA, QUORA, BRITROYALS and the like: tertiary, USER-EDITABLE
#     and with no fixed citation. Worth what a copied tree is worth: nothing.
#     Negate with `~`, and **a deep entry must never reach `profile_status:
#     complete` on Wikipedia**.
#   * limb (c) — BRITANNICA, the IGI, named encyclopaedias: edited and citable,
#     so bibliographic rather than worthless — off the ARK metric, and may stand
#     beside real apparatus the way a book does.
# The ARK census treats both identically (neither is a record). The limb decides
# what the citation may SUPPORT, which is a write-time judgement.
#
# ⚠ MATCHED ON THE COLLECTION TITLE, NEVER ON THE LOCATOR — same rule as (c) and
# (e), same reason: there cannot be a locator-shaped test.
#
# ⚠⚠ NO BARE "IGI". `igi` is a substring of `original`, `digital` and `digitized`,
# which appear in a large share of legitimate record-collection titles. The marker
# is the spelled-out name, and `test_reference_works.py` pins the negative control.
REFERENCE_WORK_LIMB_D_MARKERS = (      # tertiary + user-editable: worth nothing
    "wikipedia",
    "wikimedia",
    "quora",
    "britroyals",
    "brit royals",
    "directory of royal genealogical data",
    "royal genealogical data",
)

REFERENCE_WORK_LIMB_C_MARKERS = (      # edited + citable: bibliographic, off-metric
    "britannica",
    "encyclopedia",
    "encyclopaedia",
    "international genealogical index",
)


def reference_work_limb(title: str):
    """Which rule-8 limb does this reference-work title fall under — 'c', 'd' or None.

    `None` means "not this class"; it does NOT mean "this is a record" — screen a
    title with `is_memorial_collection` and `is_book_collection` too.

    Limb (d) is checked FIRST and deliberately: a page titled "Wikipedia:
    Encyclopedia of ..." is user-editable whatever else it calls itself, and the
    stricter reading is the safe one for a class that must never support
    `profile_status: complete`.
    """
    t = (title or "").casefold()
    if any(m in t for m in REFERENCE_WORK_LIMB_D_MARKERS):
        return "d"
    if any(m in t for m in REFERENCE_WORK_LIMB_C_MARKERS):
        return "c"
    return None


def is_reference_work(title: str) -> bool:
    """Is this an encyclopedia / wiki / reference-website citation at all?

    True for BOTH limbs, because the ARK census excludes both. Use
    `reference_work_limb` when you need to know which one — that is the part the
    operator's Q182 ruling turns on.
    """
    return reference_work_limb(title) is not None


def extract_arks(text: str) -> set:
    """Extract all source-record-IDs from vault narrative text, normalized.

    Backward-compat anchor: this is the LEGACY locator-token counter and is left
    UNCHANGED apart from honouring `~` negation. `count_records` falls back to it for
    un-migrated bullets, so an all-legacy vault reports exactly as before Spec 03
    (record_count == old ark_count)."""
    text = strip_negated_locators(text)
    ids = set()
    for pat in ARK_PATTERNS:
        for m in pat.finditer(text):
            sid = m.group(1)
            # Skip if it's actually the person's profile PID (XXXX-XXX format,
            # 4 chars / 3 chars). Profile PIDs are 8-char total. Source ARKs are
            # typically longer (e.g., XXXX-YYYY is 4-4, XXXX-YYY is 4-3 but rare).
            # Many source IDs are 4-4 or longer.
            # Don't try to filter — just collect everything matching the pattern.
            ids.add(sid)
    return ids


# --- Spec 03 (multi-anchor-multi-repo): record / host:locator model -----------
# A *record* is one primary source; a *locator* is a host:id pointer to where it
# is hosted. The migration (migrate_sources.py) rewrites legacy flat ARK lists
# under `**FS-attached sources**` into `**Sources**` sub-bullets, one record per
# line, each locator host-prefixed (`fs:1:1:...`, `anc:dbid=...`). This module
# counts RECORDS (not locator tokens) and reports a per-host locator breakdown.
#
# Host-tagged mirror of ARK_PATTERNS: (pattern, host_id, kind). Used only for the
# per-host breakdown and host derivation; extract_arks stays the counting anchor.
HOST_LOCATOR_PATTERNS = [
    (re.compile(r"\b1:1:([A-Z0-9]{3,}-[A-Z0-9]{3,})\b"), "familysearch", "indexed"),
    (re.compile(r"\bark:/61903/1:1:([A-Z0-9]{3,}-[A-Z0-9]{3,})", re.IGNORECASE), "familysearch", "indexed"),
    (re.compile(r"\b(?:ark:/61903/)?3:1:([A-Z0-9]{3,}(?:-[A-Z0-9]+){1,4})", re.IGNORECASE), "familysearch", "image"),
    (re.compile(r"\b(?:Family[Ss]earch\s+)?ARK\s+([A-Z0-9]{3,}-[A-Z0-9]{3,})\b"), "familysearch", "indexed"),
    (re.compile(r"\bark:/12657/([\w.\-]+)", re.IGNORECASE), "antenati", "image"),
    (re.compile(r"\b(metryki\.genealodzy\.pl/[^\s)\]]+)", re.IGNORECASE), "metryki", "image"),
    (re.compile(r"\b(szukajwarchiwach\.(?:gov\.pl|pl)/[^\s)\]]+)", re.IGNORECASE), "szukajwarchiwach", "image"),
    (re.compile(r"\b(PL(?:_\d+){3,4}\.jpg)\b", re.IGNORECASE), "agad", "image"),
]

# A host-prefixed locator token: a short host id, a colon, then a non-space run.
# PREFIX detector only — it says "a locator starts here", not "this cites a record".
# The census must not count on it alone (a prose `fs:1:1:` matches); use
# `record_locators` / `is_record_locator` below. Retained for migrate_sources.py,
# which uses it to spot already-migrated lines, where a false positive is harmless.
HOST_LOC_RE = re.compile(
    r"\b(" + "|".join(EMITTED_HOST_IDS) + r"):(?=[0-9A-Za-z/])", re.IGNORECASE)
# The FULL host:locator token (for record identity / dedup): host id + ':' + the
# locator up to a delimiter. A record's identity is its SET of these tokens, so an
# ARK cited on two record lines (pre-existing prose duplication that the legacy
# set-based count already deduped) does not inflate the record count.
FULL_HOST_LOC_RE = re.compile(
    r"\b(?:" + "|".join(EMITTED_HOST_IDS) + r"):[^\s,;)\]]+", re.IGNORECASE)
# Legacy patterns already match the FS/antenati/etc. id INSIDE a `fs:1:1:...`
# prefix (the `1:1:`/`ark:` substring is still present), so extract_arks and the
# per-host tally both see host-prefixed locators without extra work.

# A locator token must actually POINT AT A RECORD (spec/entry-boundary, 23 JUL 2026).
#
# The mirror image of the phantom-header bug: that one destroyed coverage, this one
# INVENTS it. Writing a locator PREFIX literally in prose — naming the class of thing
# rather than citing one, "these register images attach as fs:3:1: image ARKs" —
# matched the host-prefix detector, so the sentence was counted as a RECORD and the
# person gained a source that does not exist. Same silence, opposite sign.
#
# Two conditions separate a citation from a mention, and both are about the TAIL:
#   * a real id has a substantial final segment (>= 3 alphanumerics somewhere after
#     the host prefix) — `fs:1:1:` names a namespace, `fs:1:1:XXXX-XXX` cites a record;
#   * a real id does not end on a separator — `anc:dbid=` is a field waiting for a
#     value, and "hosted on fs:" is a sentence.
_LOC_ALNUM_RUN = re.compile(r"[0-9A-Za-z]{3,}")


def is_record_locator(token: str) -> bool:
    """True if `token` (a `host:...` match) cites a record rather than naming a
    locator class in prose."""
    if ":" not in token:
        return False
    tail = token.split(":", 1)[1]
    if not tail or tail[-1] in ":=/-_.":
        return False
    return bool(_LOC_ALNUM_RUN.search(tail))


def record_locators(text: str) -> "List[str]":
    """Every host-prefixed token in `text` that really cites a record.

    Honours `~` negation (deferred_decisions 28): a negated locator is not a citation."""
    text = strip_negated_locators(text)
    return [m.group(0) for m in FULL_HOST_LOC_RE.finditer(text)
            if is_record_locator(m.group(0))]


def per_host_locators(text: str) -> "Dict[str, int]":
    """Return host_id -> count of DISTINCT locators of that host in `text`
    (across both legacy bare tokens and host-prefixed ones)."""
    text = strip_negated_locators(text)
    counts: Dict[str, int] = defaultdict(int)
    seen = set()
    # Pass 1: the legacy bare-token patterns. Record the SPANS they consume, not
    # just the hosts they belong to — see the note on pass 2.
    consumed: "list[tuple[int, int]]" = []
    for pat, host, _kind in HOST_LOCATOR_PATTERNS:
        for m in pat.finditer(text):
            consumed.append(m.span())
            key = (host, m.group(1))
            if key not in seen:
                seen.add(key)
                counts[host] += 1
    # Pass 2: host-PREFIXED locators (`anc:1234:56`, `agad:300/872/31-1865`, `wt:…`).
    #
    # ⚠ THIS USED TO SKIP BY HOST — `if host in legacy_hosts: continue` — on the
    # assumption that a host owning a legacy pattern had already been tallied in
    # pass 1. That is only true when the legacy pattern ACTUALLY MATCHED THIS
    # TOKEN. `agad`'s legacy pattern matches only the scan-filename form
    # (`PL_1_300_875_0066.jpg`), so an AGAD locator written as an ARCHIVAL
    # REFERENCE (`agad:300/872/31-1865`) matched neither pass and was attributed
    # to NO host at all — while still counting as a record, so nothing looked
    # wrong. The record count stayed right and the HOST silently vanished, which
    # matters because SINGLE_SOURCED / MULTI_SOURCED are computed from hosts.
    # AGAD's own `locator_kind` in the registry is `id`, so the archival form is
    # arguably the intended one. Found 03 AUG 2026 (deferred_decisions 47).
    #
    # The fix skips on SPAN OVERLAP instead: a prefixed token is dropped only if a
    # legacy pattern really did consume it (e.g. `fs:1:1:X` contains `1:1:X`;
    # `antenati:ark:/12657/…` contains `ark:/12657/…`). This fixes the CLASS, so
    # the trap is not left armed for the next host that gains a legacy pattern.
    for m in re.finditer(
            r"\b(" + "|".join(EMITTED_HOST_IDS) + r"):([0-9A-Za-z][^\s,;)\]]*)",
            text, re.IGNORECASE):
        if not is_record_locator(m.group(0)):
            continue  # a locator CLASS named in prose ("attach as anc: ids"), not a citation
        s, e = m.span()
        if any(cs < e and s < ce for cs, ce in consumed):
            continue  # a legacy pattern already tallied THIS token
        host = m.group(1).lower()
        host = {"fs": "familysearch"}.get(host, host)
        key = (host, m.group(2))
        if key not in seen:
            seen.add(key)
            counts[host] += 1
    return dict(counts)


SOURCES_BULLET_RE = re.compile(r"^\s*-\s+\*\*(Sources|FS-attached sources)", re.I)


def sources_bullet_text(body: str) -> str:
    """Just the `- **Sources**` / `- **FS-attached sources**` bullet(s) of an entry
    body, including their indented sub-bullets.

    ** WHY A STRUCTURAL SPLIT AND NOT A KEYWORD ONE (deferred_decisions 19,
    settled 30 JUL 2026). ** The census credited a locator cited as a research
    ROUTE exactly as it credited one cited as EVIDENCE, so a `FRONTIER
    DECLARATION` naming the images somebody should go and read made the
    unresolved person look well sourced. The obvious fix — skip lines carrying a
    route marker — was measured and REJECTED: it wrongly zeroed an entry whose
    line contained the word "unread" (about a register image) *and* cited the
    real marriage record that documents him. A line can hold a citation and a
    caveat at once, so exclusion must key on WHERE a citation sits, not on what
    words surround it. Same position-over-guesswork principle as the
    entry-boundary gate.

    Measured on the reference vault the day it was written: strict counting drops
    339 of 7,868 records (4.3%) and takes 44 entries to zero — and roughly half of
    those are legitimate prose citations that need MIGRATING into a Sources
    bullet, not deleting. Hence the staged rollout: this function exists and is
    reported, but `--strict-sources` is opt-in until that migration is done."""
    out, inside = [], False
    for ln in body.splitlines():
        if SOURCES_BULLET_RE.search(ln):
            inside = True
            out.append(ln)
            continue
        if inside:
            if ln.strip() == "" or re.match(r"^\s{2,}", ln):
                out.append(ln)
                continue
            inside = False
    return "\n".join(out)


def count_records_strict(body: str) -> int:
    """count_records restricted to what a Sources bullet actually asserts."""
    return count_records(sources_bullet_text(body))


def count_records(body: str) -> int:
    """Number of distinct source RECORDS cited in an entry body.

    Migrated entries (new `Sources` grammar) put one record per line, each with
    one or more host-prefixed locators. Count those lines, PLUS any legacy bare
    locator not yet moved onto a record line (transitional, so nothing is lost).
    A fully un-migrated body has no host-prefixed lines, so this returns exactly
    len(extract_arks(body)) — identical to the pre-Spec-03 count."""
    # A line is a record line only if it carries a locator that POINTS AT a record —
    # not one that merely names the locator form in prose (see is_record_locator).
    record_lines = [ln for ln in body.splitlines() if record_locators(ln)]
    legacy_ids = extract_arks(body)
    if not record_lines:
        return len(legacy_ids)
    # A record's identity is its SET of host:locator tokens. Dedupe records with an
    # identical locator set (the same source cited on two lines) so pre-existing
    # duplication does not inflate the count — matching the legacy set-based dedup.
    seen_records = set()
    covered = set()
    for ln in record_lines:
        toks = frozenset(t.lower() for t in record_locators(ln))
        if toks:
            seen_records.add(toks)
        covered |= extract_arks(ln)
    stray = legacy_ids - covered
    return len(seen_records) + len(stray)

# ENTRY DETECTION LIVES IN `person_store`, NOT HERE (spec/entry-boundary Spec 05).
#
# This module used to carry its own bold-name header patterns (`ENTRY_HDR_A`/`B`), a
# prose filter, and an `extract_entries` that turned every match into a body boundary.
# All of it is deleted. The census reads entries through `entry_blocks_by_file()` below,
# which asks the model-agnostic seam, where a person is detected by the `- meta:` block
# the vault documents as the identity anchor.
#
# What the shape-based reader cost, before it went:
#   * it could not tell a person from an institution ("Archivio di Stato di Sondrio"
#     has the same shape as "Richard de Clare"), so a bolded archive name in mid-prose
#     truncated the entry it sat in and orphaned that entry's `Sources` bullet;
#   * it could not match a name carrying quotes, parentheses or a slash alias, so 52
#     real entries had no block and silently inherited a neighbour's record count; and
#   * it needed an ever-growing filter to reject bold prose bullets, which is a losing
#     game: a filter that must recognise every non-person string will meet a new one.
# None of those are fixable at the shape layer, and none of them arise at the meta
# layer, where a bold line without a meta block under it is simply not an entry.

# Person_Index row pattern.
# NEW layout: | Name | Gen | Born | Died | FS PID | Notes |
# (PID is now group 5; Gen is group 2; the File column was removed.)
PI_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([A-Z0-9]{4}-[A-Z0-9]{3})\s*\|\s*([^|]*?)\s*\|\s*$"
)

# Section headers are now file names (e.g. "## Family_Tree_<Region>").
# Region is derived from the current section header. The Appendix block must be
# skipped (historical prose, not data rows).
SECTION_HDR_RE = re.compile(r"^##\s+(\S.*?)\s*$")
APPENDIX_RE = re.compile(r"^##\s+Appendix")


def parse_person_index() -> Dict[str, dict]:
    """Return vault-id -> {name, gen, confidence, file_col, region, pid} for EVERY
    person entry.

    Person_Index.md was RETIRED (memory project_person_index_retirement); the
    canonical roster now comes from the narratives via
    gen_person_index.parse_narrative() — each entry's bold-name header + `- meta:`
    block (id / FS / tier / gen).

    ** KEYED ON THE VAULT `id`, NOT THE FS PID (26 JUL 2026 — the census blind
    spot). ** This function used to open with `if not pid: continue`, on the
    reasoning quoted in its old docstring: "an entry without one has no FS profile
    whose Sources tab could be harvested." That is TRUE FOR HARVESTING and FALSE
    FOR CENSUSING, and this one function fed both jobs.

    The cost, measured on the reference vault the day it was fixed: **210 of 1,320
    entries — 16% of the vault — never reached the census at all.** Not
    SOURCE_GAP, not UNCITED, not any category: absent. 60 of them carried a
    `- **Sources**` bullet and 12 carried real locators. The sharpest case is
    `fs: none`, which MEANS "searched FamilySearch, confirmed no profile" — a
    finding, recorded properly, and it erased the person from the vault's own
    statistics. `fs: TBD` (not yet searched) did the same to 162 more.

    So the roster now keys on the meta `id`: unique, never reused, and BLOCKING in
    `gen_person_index --integrity`, so no entry can lack one. `pid` rides along as
    an attribute and stays the key for FS-facing work (`--csv`, the harvest target
    list, the structural-gap PID allowlists). Region is classified from the
    narrative's file name via the optional shard manifest (shard_manifest.region_for
    expects the basename WITHOUT `.md`)."""
    manifest = shard_manifest.load_shard_manifest(VAULT)
    out: Dict[str, dict] = {}
    for e in G.parse_narrative():
        key = e["id"]
        if not key:
            # Defensive only: MISSING_ID is a HARD integrity violation that blocks
            # the commit, so this cannot happen in a gated vault. Skipping here
            # would reintroduce the very silence this change removes, so say so.
            sys.stderr.write(
                f"harvest_sources: entry {e.get('name','?')!r} in {e.get('file','?')} "
                "has no meta id and is EXCLUDED from the census "
                "(run gen_person_index.py --integrity)\n")
            continue
        pid = e["pid"]          # None for TBD / none / malformed — no longer fatal
        file_col = e["file"][:-3] if e["file"].endswith(".md") else e["file"]
        region = shard_manifest.region_for(file_col, manifest)
        tier = e["tier"] or "U"
        # ids are unique by the integrity gate, so the old "same PID on >1 entry,
        # keep the first" dedup is no longer needed to avoid collisions.
        if key not in out:
            out[key] = {
                "pid": pid,
                "name": e["name"].strip("* "),
                "gen": e["gen"],
                "confidence": tier,
                "confidence_raw": tier,
                "file_col": file_col.strip(),
                "region": region,
                # Carried so gather_records can apply the RESEARCH gate. Absent =>
                # the gate fails closed, which is the intended reading of a person
                # whose life status nobody has recorded.
                "life_status": e.get("life_status"),
                # Carried for the `before_year` structural criterion (Q157). Empty
                # when the entry has no dated vitals, which that criterion treats
                # as "not structural" rather than as a vacuous pass.
                "years": vital_years(e.get("born"), e.get("died")),
            }
    return out


# ** THE ONE DEFINITION OF A STRUCTURAL BREAK (02 AUG 2026). **
# `entry_boundary_audit` used to keep its own copy of this pattern with a comment
# saying "the same structural breaks the census honours" -- and the moment the census
# gained `### Generation N`, the two disagreed and the HARD entry-boundary gate went
# from 0 to 80 findings. Two readers, one entry: the gate now IMPORTS this.
BREAK_LINE = re.compile(r"^(?:---\s*|##\s.*|#{1,4}\s+Generation\s+\d+.*)$", re.I)


def truncate_at_break(body: str) -> str:
    """Cut an entry body at the first structural break (`---` rule or `## ` heading)
    after its header line.

    An entry ends at the next entry OR at a section boundary, whichever comes first.
    Without this the last entry before a boundary swallows the following section
    prose, and any PID named in that prose inherits the entry's records — a
    false-credit bug fixed 02 JUL 2026 and preserved here across the move to
    meta-anchored detection.

    ** `### Generation N` JOINED THE BREAK SET 02 AUG 2026 (deferred 36, measured). **
    A Generation heading is a STRUCTURAL boundary — the last entry of one generation
    was absorbing the start of the next. Measured effect: exactly 2 entries, 3
    records, both verified true by reading: one entry was absorbing a titled
    `### Generation 8: <Line>` heading, another a bare `### Generation 29` whose record
    sits after the heading and belongs to the next section. The old `##\\s` alternative
    could not match it, because `###` puts a third `#` where that pattern wants space.

    ⚠ **AND NOTHING ELSE WAS ADDED, WHICH IS THE POINT.** Two other candidate signals
    were measured and REJECTED, both because they delete real evidence:
      - a line-start **bold** header — 3 entries change and ONE IS A FALSE POSITIVE:
        one entry's block is cut by `**Read the prior work before researching him
        again** — …`, which is bold PROSE, and its only record sits below it. A regex
        cannot tell a bold section header from a sentence opening with a bold phrase.
      - a GENERIC `###` sub-heading — same false positive, because an entry legitimately
        contains narrative sub-headings (`### What the 02 AUG 2026 sweep actually added`).
    A genuine non-entry section that is NOT introduced by a Generation heading is closed
    by writing an explicit `---` above it, which this function already honours.
    """
    lines = body.splitlines()
    for i, ln in enumerate(lines[1:], start=1):
        if BREAK_LINE.match(ln):
            return "\n".join(lines[:i])
    return body


def entry_blocks_by_file(vault: "Optional[str]" = None) -> "Dict[str, List[Tuple[str, int, str]]]":
    """path -> [(display_name, header_line_index, body_text)] for every person entry.

    META-ANCHORED (23 JUL 2026, spec/entry-boundary Spec 05): entries come from the
    model-agnostic `person_store` seam, which detects a person by the `- meta:` block
    the vault documents as the identity anchor, and takes the bold line above it as
    the display header.

    This RETIRES the shape heuristics for census purposes. Reading entries by name
    shape was the root of this whole lane: it could not tell a person from an
    institution, it silently missed every name carrying quotes, parentheses or a
    slash alias (52 entries, which then inherited a neighbour's records), and it
    needed a growing filter to reject bold prose. None of that arises here — a bold
    line without a meta block under it is simply not an entry.

    The entry-boundary gate re-derives ownership independently, by its own top-down
    line scan, and fails a commit on any disagreement with what this returns.
    """
    import person_store as PS
    out: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
    for rec, path, hline, block in PS.iter_entry_blocks(vault or VAULT):
        out[path].append((rec.name, hline, truncate_at_break(block)))
    return dict(out)


def entry_blocks_with_ids(vault: "Optional[str]" = None):
    """path -> [(vault_id, display_name, header_line_index, body_text)].

    Same seam as `entry_blocks_by_file`, but carries the record's `id` straight
    from `person_store` instead of re-parsing it out of the body text.

    ** WHY NOT A REGEX (26 JUL 2026). ** The first cut of the id-keyed census
    scraped the id from the `- meta:` line with a pattern built from the
    DOCUMENTED grammar — `P-` + 6 Crockford base32 chars, no I/L/O/U
    (CLAUDE.method). 15 entries promptly fell out and landed in NO_NARRATIVE,
    because the live vault contains ids the documented grammar forbids: twelve
    using `L` or `O` (mnemonic ids built from initials, e.g. `P-ABC258`) and one
    only five characters long. The integrity gate enforces DUP_ID and
    MISSING_ID — it does NOT validate the id's SHAPE — so those ids are legal in
    practice.

    The lesson is the recurring one in this module: **encode what the data is,
    not what the spec says it should be.** An id is an opaque primary key here;
    validating its charset is the integrity gate's job, and duplicating that
    judgement in a consumer just invents a second, stricter, silent filter — which
    is precisely the failure this whole change exists to remove.

    `entry_blocks_by_file` keeps its 3-tuple shape because `entry_boundary_audit`
    and its test unpack it."""
    import person_store as PS
    out = defaultdict(list)
    for rec, path, hline, block in PS.iter_entry_blocks(vault or VAULT):
        out[path].append((rec.id, rec.name, hline, truncate_at_break(block)))
    return dict(out)


def _attributed_region_indices(lines: "List[str]", i: int) -> "set":
    """The LINE INDICES of the region at `i`: that line plus its more-indented
    continuation lines (a bullet and its sub-bullets).

    Indices rather than text because `own_region` has to SUBTRACT regions and
    therefore needs to know which lines they occupy. Both crediting paths derive
    their region from this one function, so the entry's own text and a foreign
    pid's attributed text can never disagree about where a region ends.
    """
    def indent(s: str) -> int:
        return len(s) - len(s.lstrip())
    base = indent(lines[i])
    out = {i}
    for j in range(i + 1, len(lines)):
        if not lines[j].strip() or indent(lines[j]) <= base:
            break
        out.add(j)
    return out


def _attributed_region(lines: "List[str]", i: int) -> str:
    """The line at `i` plus its more-indented continuation lines (a bullet and its
    sub-bullets). The unit a citation is attributed to."""
    return "\n".join(lines[j] for j in sorted(_attributed_region_indices(lines, i)))


_META_LINE_RE = re.compile(r"^\s*-\s*meta:\s*\{")
_META_FS_RE = re.compile(r"\bfs:\s*([A-Z0-9]{4}-[A-Z0-9]{3})\b")
_META_ID_RE = re.compile(r"\bid:\s*(P-[0-9A-HJKMNP-TV-Z]{6})\b")


def own_ids(body: str) -> "set":
    """The vault `id`(s) this entry is ABOUT — the `id:` value on its `- meta:` line.

    The id is the vault's PRIMARY KEY (CLAUDE.method "the meta block is the identity
    and detection anchor"), it is unique and non-reusable, and `gen_person_index
    --integrity` BLOCKS a commit unless every entry has one. So it is the only
    identifier the census can key on without silently dropping people — which is
    exactly what keying on the FS PID did. See `parse_person_index`.
    """
    own = set()
    for ln in body.splitlines():
        if _META_LINE_RE.match(ln):
            own |= set(_META_ID_RE.findall(ln))
    return own


def own_pids(body: str) -> "set":
    """The PID(s) this entry is ABOUT — the `fs:` value on its `- meta:` line(s).

    This is the meta-anchored identity the roster keys on (`gen_person_index`
    reads the same `fs`). A PID that appears only in the bold-name HEADER — a
    spouse in a couple header "**A** (…) + **B** (…, FS PID …)", or a relative
    named in a prose header — is a CROSS-REFERENCE, not the entry's own person.
    """
    own = set()
    for ln in body.splitlines():
        if _META_LINE_RE.match(ln):
            own |= set(_META_FS_RE.findall(ln))
    return own


def may_credit(body: str, pid: str) -> bool:
    """May this entry's record count be credited to `pid`?

    THE PROBLEM THIS SOLVES. `gather_records` credits a PID with max(records)
    across every block that MENTIONS it. Two very different things get mentioned
    in a person's entry:

      (a) a relative whose sources are documented INLINE, here, on purpose —
          "- **FS-attached sources for wife <Name>** (<PID>, inline collateral;
          Recipe-S 30 MAY 2026): 1:1:..., 1:1:..." — a convention the vault uses
          deliberately and which must keep working; and
      (b) a relative merely NAMED in a cross-reference — "- Siblings (3, with FS
          PIDs): ...", "- Children of X + Y: ...", "- Parents: ..." — a pointer,
          not documentation.

    Case (b) was inheriting the whole block's record count. Measured on the
    reference vault: 112 people were credited ONLY that way, including a child who
    died in infancy reading as WELL_SOURCED off his adult brother's 11 records, and
    three entries whose own text says in so many words that no record ARK exists.
    Integrity rule 6 already bans a foreign PID from a HEADER for the same reason;
    this is the body-level counterpart for the census.

    The discriminator is LOCATORS, not keywords: a mention that documents someone
    carries citations on that bullet; a cross-reference carries none. So a PID is
    creditable from this entry when EITHER
      * it is the entry's OWN pid — the `fs:` on its `- meta:` line (`own_pids`); OR
      * some line mentioning it, together with that line's sub-bullets, carries at
        least one record locator (the inline-collateral convention).
    A mention that is only a name in a list credits nothing.

    THE HEADER VECTOR (24 JUL 2026). The own-person test was `pid in lines[:2]`
    (header + meta), which trusts the bold-name HEADER to name only the entry's
    own person. A couple header names the SPOUSE too ("**A** (…) + **B** (…, FS
    PID …)"), and a prose header can name a relative's PID, so a 0-record stub
    inherited a rich relative's whole record count AND its scholarly citation —
    the residual half of the #99 cross-reference-inheritance defect. Spec 05
    closed the body-LIST vector (the locator test below); anchoring the own-person
    test on the `- meta:` line, which carries ONLY the entry's own `fs`, closes the
    header vector. Measured: 18 stubs dropped LOW/WELL → SOURCE_GAP, 0 the other way.
    """
    if pid in own_pids(body):                # the entry's own person (meta-anchored)
        return True
    return count_records(attributed_region_for_pid(body, pid)) > 0


def attributed_region_for_pid(body: str, pid: str) -> str:
    """The text within this entry that documents a FOREIGN `pid`: every line naming
    it, plus that line's sub-bullets, concatenated.

    ** THE MAGNITUDE HALF OF SPEC 05 (deferred_decisions 29, 01 AUG 2026). **
    `may_credit` decided WHETHER a foreign pid was creditable with a per-LINE test,
    and then `scan_family_tree_files` credited it the record count of the WHOLE
    ENTRY — the attributed region was computed here and thrown away. So a relative
    named on any one line that happened to carry a locator inherited every record in
    the entry.

    Measured on the reference vault the day it was found: 68 entries carried a wrong
    record count, 1,474 phantom records were in the census, and 17 entries read as
    WELL_SOURCED when they belonged in LOW_COVERAGE. The worst case read as 95
    records against an actual 3. The shape that surfaced it: a wife named once, in
    her husband's marriage narrative, on a line citing the ONE atto that documents
    the marriage — and credited all 32 of his records.

    SOURCE_GAP did NOT move and no entry became newly actionable: the gain here is
    coverage honesty, not extra worklist. (An early projection that this would add
    ~33 SOURCE_GAP entries was wrong — it used the entry's OWN count as the
    counterfactual, where the correct credit is the attributed-region count, which
    is normally non-zero.)

    This over-credited even the convention it exists to protect: an inline-collateral
    wife bullet should credit the locators on THAT bullet, not the husband's entry.

    Overlapping regions are safe — a pid named on both a parent bullet and its
    sub-bullet yields overlapping text, and `count_records` dedupes by locator set.
    """
    lines = body.splitlines()
    return "\n".join(_attributed_region(lines, i)
                     for i, line in enumerate(lines) if pid in line)


# A DEDICATED relative-sources bullet: a TOP-LEVEL bullet whose head NAMES A TARGET
# — "sources" immediately followed by `for` / `of` / a dash. Matches the documented
# forms —
#   - **FS-attached sources for wife <Name>** (<PID>, inline collateral; …): …
#   - **FS-attached sources — <Name> <PID>** (Recipe-S harvest …): …
#   - **Ancestry sources for <Name>** …
#
# and deliberately NOT:
#   * a narrative line citing a shared act — "- Married **X** (FS <PID>) … marriage
#     atto — <ARK>" — which documents the entry's own person too; and
#   * ⚠ THE ENTRY'S OWN `- **Sources**` BULLET, even when its parenthetical mentions
#     a relative's PID. That is not hypothetical: one entry's own bullet reads
#     "- **Sources** (Recipe-S harvest …; many co-attach with husband <Name> <PID>)",
#     and a rule keyed on the bare word "sources" deleted her whole Sources block,
#     taking her from 26 records to 0. Requiring a for/of/dash TARGET after the word
#     is what separates "sources FOR someone else" from "this entry's Sources".
#
# Anchored at indent 0, so a SUB-bullet inside the entry's own Sources block can
# never itself trigger a subtraction.
_SOURCES_BULLET_RE = re.compile(
    r"^-\s+.{0,120}?\bsources\b\s*(?:for\b|of\b|[—–]|-\s)", re.IGNORECASE)


def own_region(body: str, owners: "set", pid_to_id: "Dict[str, str]") -> str:
    """The text of this entry that documents the entry's OWN person: the body MINUS
    every region attributed to a documented FOREIGN pid.

    ** THE OTHER HALF OF DEFERRED 29 (deferred_decisions 49, 04 AUG 2026). **
    `attributed_region_for_pid` scoped the credit of a FOREIGN pid to the region
    that documents it. The entry's OWN person kept being credited
    `count_records(body)` — the whole body — so the sanctioned inline-collateral
    convention inflated its HOST. The code comment stating the principle ("neither
    does a documented one inherit the whole entry") sat directly above the line
    that violated it, on the other path.

    Measured on the reference vault the day it was found: 66 entries, 1,151 records
    credited where 834 were genuinely the owner's, i.e. 317 phantom records. The
    worked case: an entry carrying
    `- **FS-attached sources for son <Name>** (<PID>, inline collateral): <21 locators>`
    read as 26 records against 6 FS attachments. The independent confirmation
    needed no tooling — the worst row's own `- **Sources**` bullet SAYS "13 record
    ARKs" while the census credited it 95.

    ** THE DISCRIMINATOR IS `pid_to_id`, AND THAT IS LOAD-BEARING, NOT INCIDENTAL. **
    A region is excluded only when the foreign pid RESOLVES to an entry in the
    roster. `PID_RE` matches the 4-3/4-4 shape, which is also the shape of an ARK
    SUFFIX, so a bare `- fs:1:1:WWWW-111` sub-bullet scans as a line "naming a pid".
    Requiring the roster lookup defeats that collision by construction — an ARK
    suffix owns no entry — and it is the same test step (2) already applies.

    ⚠ A first measurement of this defect, written WITHOUT the roster test, reported
    545 entries and 5,096 records. It was reading entries' own bare-locator Sources
    bullets as foreign-attributed and deleting them: one entry's own 24 locators
    became "24 foreign pids" and it reported as having 0 records of its own. The
    5,096 figure measured the measuring script. `test_own_region_ark_suffix_collision`
    is the negative control that pins this.

    ** AND IT SUBTRACTS ONLY A DEDICATED RELATIVE-SOURCES BULLET, WHICH IS NARROWER
    THAN "ANY LINE NAMING A RELATIVE". ** The first implementation subtracted every
    region naming a documented foreign pid, and `test_foreign_credit_magnitude`
    caught it: its MARRIAGE_NARRATIVE fixture is

        - Married **Poor Wife** (FS <PID>), m. 17 JAN 1883 — marriage atto no 2 — <ARK>

    A marriage act documents BOTH spouses, so subtracting it from the husband is
    simply wrong. The shape is live in this vault, not hypothetical: one entry's
    numbered wife-list cites his own 1883 marriage atto on the line naming the
    wife, and the over-eager rule took 27 records off him.

    So the discriminator is the convention Spec 05 actually defines — *"put them on
    that relative's OWN bullet"* — detected as a top-level bullet whose head line
    carries the word "sources" together with a resolvable foreign pid.

    ⚠ THIS MAKES BULLET TEXT LOAD-BEARING, WHICH rule 8 limb (g) DELIBERATELY
    DECLINED, so the difference is worth stating. There, text would have decided
    whether to START counting, and a typo would silently inflate. Here text decides
    whether to STOP counting, so a typo silently leaves the pre-existing
    over-credit — it **fails open, to the status quo**, never toward destroying a
    real record. Given that the alternative demonstrably deletes genuine
    shared-event records, that is the correct direction to fail in.

    Overlapping regions are safe: lines are collected into a set of indices.
    """
    lines = body.splitlines()
    drop: "set" = set()
    for i, line in enumerate(lines):
        if not _SOURCES_BULLET_RE.match(line):
            continue                     # not a dedicated relative-sources bullet
        region_idx = _attributed_region_indices(lines, i)
        region = "\n".join(lines[j] for j in sorted(region_idx))
        # The pid is looked for across the WHOLE REGION, not just the head line:
        # a real bullet reads "- **FS-attached sources for the 3 emigrant sons**
        # (Recipe-S harvest …):" and carries the sons' pids in its SUB-bullets.
        # A head-only test missed it and left that entry credited 95 where its own
        # bullet says 13. Safe to widen because the HEAD test has already
        # established this is a sources-for-someone-else bullet — which is what
        # keeps an entry's own `- **Sources**` block out, wherever its pids sit.
        foreign = [p for p in PID_RE.findall(region)
                   if p not in owners and p in pid_to_id]
        if foreign and count_records(region):
            drop |= region_idx
    return "\n".join(l for i, l in enumerate(lines) if i not in drop)


def scan_family_tree_files(pid_to_id: "Optional[Dict[str, str]]" = None) -> Dict[str, List[Tuple[str, str, int, int, dict]]]:
    """Return vault-id -> list of (filename, name, record_count, body_length, per_host, scholarly).

    For each narrative entry, count the number of source RECORDS in its body
    (Spec 03). For un-migrated entries this equals the legacy ARK-token count;
    migrated entries count `Sources` record lines. `per_host` is host_id ->
    distinct-locator count for the entry.

    ** KEYED ON THE VAULT `id` (26 JUL 2026). ** Two crediting paths, and keeping
    them separate is the whole point:

      (1) THE ENTRY'S OWN PERSON is credited via the meta `id` — no PID required.
          This is the fix: an entry with `fs: TBD` / `fs: none` / no `fs` at all
          used to fall out here and reach no category at all.
      (2) A FOREIGN PID in the body still credits ONLY under the inline-collateral
          convention (`may_credit`: the PID must appear on a line that carries its
          own locators). Those records are attributed to the id of the entry that
          OWNS that PID, via `pid_to_id`. This preserves Spec 05 exactly — a name
          in a `- Siblings` / `- Children of` / `- Parents:` list still credits
          nothing, because it documents nothing.

    Path (2) is why the PID machinery stays: dropping it would silently un-credit
    every inline-collateral relative, which is the mirror-image defect of the one
    being fixed."""
    out: Dict[str, List[Tuple[str, str, int, int, dict]]] = defaultdict(list)
    pid_to_id = pid_to_id or {}

    for path, entries in entry_blocks_with_ids().items():
        fname = os.path.basename(path)

        for rec_id, name, start, body in entries:
            # The id comes from the person_store seam, NOT a regex over the body —
            # see entry_blocks_with_ids for the 15 entries that taught us why.
            entry_ids = {rec_id} if rec_id else set()
            pids_in_entry = set(PID_RE.findall(body))
            if not entry_ids and not pids_in_entry:
                continue
            # Count RECORDS (Spec 03). For an un-migrated body this is exactly
            # len(extract_arks(body)) — the legacy locator-token count — so the
            # metric is unchanged until a file is migrated. Source-ARK IDs share
            # the 4-3/4-4 shape with profile PIDs but appear in a `1:1:`/"ARK"
            # context the patterns require, so they do not overlap the profile
            # PID; don't subtract pids_in_entry (that once zeroed genuine IDs).
            owners = own_pids(body)

            # (1) THE ENTRY'S OWN PERSON, keyed on the meta id. No PID needed —
            # this is the path that used to not exist.
            #
            # ** SCOPED TO THE ENTRY'S OWN TEXT (deferred 49, 04 AUG 2026). ** This
            # was `count_records(body)` — the WHOLE body — so a sanctioned
            # inline-collateral bullet ("- **FS-attached sources for son <Name>**
            # (<PID>, inline collateral): <locators>") credited its records to the
            # HOST as well as to the son. That is the exact mirror of the defect
            # step (2) exists to prevent, and it survived deferred 29 because that
            # fix only ever touched the foreign path. See `own_region`.
            own = own_region(body, owners, pid_to_id)
            record_count = count_records(own)
            per_host = per_host_locators(own)
            # Scholarly likewise: a Cawley/Richardson cite inside a relative's
            # inline bullet documents the RELATIVE. Scoping it keeps the
            # BOOK_SOURCED / UNCITED split honest for the same reason the record
            # count is scoped, and matches what step (2) already asserts.
            scholarly = has_scholarly_citation(own)
            for eid in entry_ids:
                out[eid].append((fname, name, record_count, len(own), per_host, scholarly))

            # (2) INLINE COLLATERAL: a FOREIGN pid credited only under the Spec 05
            # locator test, attributed to the entry that owns that pid.
            for pid in pids_in_entry:
                if pid in owners:
                    continue            # own person — already credited by id above
                # A PID merely cross-referenced here (a name in a siblings /
                # children / parents list, or a spouse in a couple header) does
                # NOT inherit this entry's records.
                #
                # ** AND NEITHER DOES A DOCUMENTED ONE INHERIT THE WHOLE ENTRY. **
                # The credit is the records of the region that documents THIS pid,
                # not `record_count` — see attributed_region_for_pid for the 88
                # entries that taught us the difference (deferred 29).
                region = attributed_region_for_pid(body, pid)
                foreign_count = count_records(region)
                if not foreign_count:
                    continue
                target = pid_to_id.get(pid)
                if not target:
                    continue            # no entry in the roster owns this PID
                # NOT the entry's scholarly citation: an entry's Cawley/Richardson
                # cite documents the entry's OWN person, not a relative named in
                # it. An inline-collateral relative is credited via the locator
                # test, so foreign_count > 0 and this flag never decides its
                # BOOK/UNCITED split. Same header-vector fix as may_credit.
                # per_host is likewise scoped to the region, not the entry.
                out[target].append((fname, name, foreign_count, len(region),
                                    per_host_locators(region), False))

    return out


# Structurally unsourceable: a 0-ARK entry that can essentially NEVER acquire an
# indexed-record ARK, so it should not inflate the actionable SOURCE_GAP to-do count.
#   (a) Gen >= STRUCTURAL_GEN — deep medieval / early-modern ancestors documented by
#       peerage books, heraldic visitations, GMB volumes, not indexed vital records.
#   (b) Pre-civil-registration lines whose parish registers are not digitized online,
#       identified by an explicit PID-prefix allowlist scoped to their region (e.g. a
#       pre-1866 civil-registration Italian pedigree whose registers are in-person only).
#   (c) Off-FS parish-resident lines whose primary records live only at a regional archive
#       (not FamilySearch), identified by an explicit FS-PID allowlist scoped to their region
#       (e.g. a parish cluster whose records are held at a diocesan/state archive and whose
#       real route is a non-FS harvest such as metryki.genealodzy.pl). Emigrant descendants
#       of such a line who DO have indexed ARKs are correctly excluded from the allowlist.
# Use --include-structural to fold these back into SOURCE_GAP (e.g. to audit prose
# book-citation coverage of the deep tree).
#
# The threshold + the region-scoped PID allowlists are per-vault constants read
# from vault/.autoresearch.json ("structural_gap") via vault_config. A config-less
# vault gets threshold 16 and NO allowlist rules (nothing exempted). Each rule is
# {label, region?, pid_prefixes?, pids?}: a 0-ARK entry is structural if its region
# contains `region` AND its PID starts with one of `pid_prefixes` or is in `pids`.
STRUCTURAL_GEN, _STRUCTURAL_RULES = (
    vault_config.structural_gap(VAULT) if VAULT
    else (vault_config.DEFAULTS["structural_gap"]["deep_gen_threshold"], []))

# A structurally-unsourceable entry is NOT automatically an undocumented one, and
# until 23 JUL 2026 the census could not tell the difference — STRUCTURAL_GAP lumped
# "impeccably cited to Cawley and Richardson" together with "nothing at all".
# Measured on the live vault that day: of 119 zero-ARK Gen>=16 entries, 62 carried a
# scholarly citation and 57 carried NONE. That 57 is a real, previously hidden
# worklist; the 62 are finished work that merely cannot earn an ARK.
#
# So the two are now separate categories. This does NOT touch SOURCE_GAP: both remain
# outside the actionable ARK to-do count, exactly as STRUCTURAL_GAP was.
#
# The list is scholarly APPARATUS, deliberately NOT user trees. Geni/Ancestry/
# RootsFinder stay excluded under the invariant-8 independence rule (they copy each
# other and often copy this vault).
#
# WIKITREE IS NOT ON THIS LIST (removed 24 JUL 2026). A bare WikiTree ID in a header
# ("WikiTree Surname-NN") is a POINTER used exactly like an FS PID — an assertion, not
# apparatus — and integrity rule 8 is explicit that "corroboration comes from what
# WikiTree CITES, never its bare assertion." Counting the token let 16 entries whose
# only citation was a bare WT id read as BOOK_SOURCED ("finished work") when they cite
# nothing. WikiTree's cited sources remain a separate corroboration layer, captured in
# a `- **WikiTree corroboration**` bullet, which is off this ARK/BOOK metric entirely.
SCHOLARLY_CITATION_RE = re.compile(
    r"Cawley|Medlands|\bFMG\b|fmg\.ac"                     # Foundation for Medieval Genealogy
    r"|Richardson|Magna Carta Ancestry|Royal Ancestry"      # Richardson
    r"|Complete Peerage|ODNB|Oxford DNB|doi:10\.1093/ref:odnb"
    r"|Henry Project|fasg\.org"
    r"|\bWeis\b|Ancestral Roots"
    r"|Flodoard|Regino|Monumenta Germaniae|\bMGH\b|Primary Chronicle"
    r"|Great Migration|NEHGR|NEHGS|\bTAG\b|Silver Book"
    r"|Visitation of|Chamberlain|Savage.{0,20}Genealogical Dictionary",
    re.I,
)


def has_scholarly_citation(body: str) -> bool:
    """True if the entry cites scholarly apparatus rather than only a record ARK."""
    return bool(SCHOLARLY_CITATION_RE.search(body or ""))


def classify(ark_count: int) -> str:
    if ark_count == 0:
        return "SOURCE_GAP"
    if ark_count <= 3:
        return "LOW_COVERAGE"
    return "WELL_SOURCED"


def is_single_sourced(rec) -> bool:
    """Documented, but by exactly ONE host — a corroboration gap, not a coverage gap.

    ** DELIBERATELY CROSS-CUTTING, NOT A CATEGORY. ** The coverage categories sum to
    the whole vault, and a person who silently vanishes from a census is the exact
    failure the 26 JUL 2026 id-keying fix removed. Single-sourcing is ORTHOGONAL to
    how many records someone has: a WELL_SOURCED person with 30 ARKs from one
    aggregator is the case this is meant to surface, and folding it into the category
    ladder would both break the sum and hide it behind "done".

    LIVING_EXCLUDED is never single-sourced for this purpose: those people are not
    web-researched at all, so a corroboration caption cannot apply to them (same
    reasoning as the research gate in gather_records).
    """
    if rec.get("category") == "LIVING_EXCLUDED":
        return False
    return (rec.get("ark_count") or 0) > 0 and (rec.get("hosts") or 0) <= 1


_VITAL_YEAR_RE = re.compile(r"\b(\d{3,4})\b")


def vital_years(born: Optional[str], died: Optional[str]) -> tuple:
    """Every 4-digit year appearing in a person's `born`/`died` DateValues.

    Deliberately takes EVERY year rather than "the" year: a GEDCOM 7 DateValue may
    be a range or a span (`BET 1816 AND 1823`, `BEF JAN 1866`), and the criterion
    below asks whether the person's whole life sits before a cutoff — so the LATEST
    year mentioned is the one that decides it, not a parsed single value.
    """
    out = []
    for v in (born, died):
        if v:
            out += [int(y) for y in _VITAL_YEAR_RE.findall(str(v))]
    return tuple(out)


def is_structural(pid: Optional[str], gen: Optional[int], region: Optional[str],
                  years: tuple = ()) -> bool:
    """A 0-ARK entry that can essentially never acquire an indexed-record ARK.

    `pid` may be None since the census stopped requiring one (26 JUL 2026). The
    deep-generation test is PID-free and still applies; the enumerated allowlists
    are keyed on FS PIDs, so a PID-less entry simply cannot match them — correctly,
    since those rules exist to name specific FS-profiled clusters.

    ⭐ `before_year` IS THE CRITERION; `pids`/`pid_prefixes` ARE ENUMERATIONS
    (operator ruling 05 AUG 2026, Open_Questions Q157/Q144). A rule may carry a
    `before_year` with a `region`, meaning: *all this person's dated vitals fall
    before the year that region's civil registration begins, in a parish whose
    registers are not online*. That is what the enumerated rules always MEANT, and
    stating it as a criterion is what stops the drift — the reference vault's rule keyed
    on the FS-PID prefixes `P6K`/`P97`, which carry no meaning at all, and by the
    time the drift was measured it was missing 16 entries of the very cluster it
    describes while two of its own members no longer qualified.

    ⚠⚠ AN UNDATED ENTRY IS NOT STRUCTURAL, AND THIS GUARD IS LOAD-BEARING.
    "All dated vitals before 1866" is VACUOUSLY TRUE of a person with no dates at
    all — measured on the reference vault, 22 undated entries in that one region would have
    been retired from the worklist by a naive reading, including one at Gen 13 whom
    nobody has dated. So a `before_year` rule requires at least ONE dated vital.
    An undated person is unevidenced, which is a reason to research them, not to
    declare them unresearchable.

    ⚠ It answers "were they alive before the registers start", NOT "is anything
    findable". A person who dies in 1869 has a Stato Civile death record whatever
    their birth year, so the LATEST year decides — see `vital_years`.
    """
    if gen is not None and gen >= STRUCTURAL_GEN:
        return True
    if not region:
        return False
    for rule in _STRUCTURAL_RULES:
        rregion = rule.get("region")
        if rregion and rregion not in region:
            continue
        before = rule.get("before_year")
        if before and years and max(years) < int(before):
            return True
        if not pid:
            continue
        prefixes = tuple(rule.get("pid_prefixes", []))
        if prefixes and pid.startswith(prefixes):
            return True
        if pid in rule.get("pids", []):
            return True
    return False


def fold_matches(matches):
    """Fold a person's crediting blocks into ONE (fname, name, records, len, per_host, scholarly).

    ** deferred 35 (operator, 03 AUG 2026, option 1): RECORDS take the MAX over
    blocks, HOSTS take the UNION. They answer different questions. **

    MAX is right for "how many records": the same record cited in two blocks must
    not double-count, which is what Spec 05 settled and is unchanged here. But
    taking the winning block's `per_host` WHOLESALE also discarded every host cited
    in the OTHER blocks -- so a person genuinely documented by two repositories
    could read `hosts 1, SINGLE_SOURCED` with no error anywhere. The split across
    blocks is the SANCTIONED inline-collateral convention (Spec 05), not a defect
    in the data, so the population is not one entry.

    This bites exactly the metric the 01 AUG biography ruling is about: a session
    can corroborate correctly and watch MULTI_SOURCED refuse to move. Measured when
    raised, only ONE person was affected -- so it is a TRAP rather than a live
    distortion, and it scales with the goal, since every future corroboration of
    someone whose records sit inline in a relative's entry lands in it silently.

    Per-host COUNTS take the max per host, not the sum, for the same
    anti-double-counting reason. Only the KEY COUNT feeds SINGLE_SOURCED /
    MULTI_SOURCED (`"hosts": len(per_host)` in gather_records).

    ONE home for the rule so the census and its test cannot drift apart.
    """
    best = max(matches, key=lambda m: m[2])
    if len(matches) == 1:
        return best
    fname, narr_name, ark_count, body_len, _per_host, scholarly = best
    unioned = {}
    for m in matches:
        for host, n in (m[4] or {}).items():
            unioned[host] = max(unioned.get(host, 0), n)
    return (fname, narr_name, ark_count, body_len, unioned, scholarly)


def gather_records(gen_lo=None, gen_hi=None, confidence=None, region=None, include_structural=False):
    """Build the per-PID coverage records (shared by the report and the heartbeat)."""
    pi = parse_person_index()
    # pid -> id, so inline-collateral records found under a FOREIGN pid can be
    # attributed to the entry that owns it (scan_family_tree_files path 2).
    pid_to_id = {info["pid"]: key for key, info in pi.items() if info.get("pid")}
    narrative_index = scan_family_tree_files(pid_to_id)
    records = []
    for key, info in pi.items():
        pid = info.get("pid")
        if gen_lo is not None and (info["gen"] is None or info["gen"] < gen_lo or info["gen"] > gen_hi):
            continue
        if confidence and info["confidence"] != confidence:
            continue
        if region and (info["region"] is None or region.lower() not in info["region"].lower()):
            continue
        matches = narrative_index.get(key, [])
        if not matches:
            category, ark_count, per_host, fname, narr_name = "NO_NARRATIVE", 0, {}, "", ""
        else:
            fname, narr_name, ark_count, body_len, per_host, scholarly = fold_matches(matches)
            category = classify(ark_count)
            if (category == "SOURCE_GAP" and not include_structural
                    and is_structural(pid, info["gen"], info["region"],
                                      info.get("years", ()))):
                # Split (23 JUL 2026): documented-but-unharvestable vs genuinely
                # unresearched. Both stay out of the actionable SOURCE_GAP count.
                category = "BOOK_SOURCED" if scholarly else "UNCITED"

        # THE RESEARCH GATE, applied LAST so it overrides every other category
        # (28 JUL 2026, session #111 — deferred_decisions item 11). A living or
        # unknown person is not a coverage GAP: they are someone this vault
        # forbids web-searching at all, so a coverage caption cannot apply to
        # them. Before this, 15 of them sat in the census and 9 of them in
        # SOURCE_GAP, which integrity rule 8 calls "the highest-priority Recipe-S
        # harvest target" — and Recipe-S is a web-research workflow.
        #
        # They are RE-CATEGORIZED, not dropped, deliberately: the categories sum
        # to the whole vault, and a person who silently vanishes from a census is
        # the exact failure the 26 JUL id-keying fix existed to remove. The rule
        # itself lives in privacy_gate.may_research — one place, called by every
        # research target-set builder, never restated inline where it can drift.
        # --include-structural does NOT fold these back; nothing does.
        researchable, _why = privacy_gate.may_research(info.get("life_status"))
        if not researchable:
            category = "LIVING_EXCLUDED"

        records.append({
            "id": key,
            "pid": pid,
            "name": info["name"],
            "gen": info["gen"],
            "confidence": info["confidence"],
            "region": info["region"],
            "life_status": info.get("life_status"),
            "category": category,
            "ark_count": ark_count,
            "per_host": per_host,
            # ** SOURCE BREADTH (operator-directed, 01 AUG 2026). ** How many DISTINCT
            # hosts document this person. The coverage categories count RECORDS and
            # say nothing about INDEPENDENCE: thirty FamilySearch ARKs and nothing
            # else scores WELL_SOURCED while resting entirely on one aggregator that
            # itself copies. Measured when this was added: of 1,392 people, 665 cited
            # exactly ONE host and only 26 cited two or more, and 660 of the 691 who
            # cited anything cited FamilySearch. The operator's standing goal is a
            # complete biography per person built from as many resources as possible,
            # with FS as a SYNC POINT rather than the evidence base -- so breadth
            # needs to be a number the banner reports, not an intention.
            "hosts": len(per_host or {}),
            "narr_file": fname,
            "narr_name": narr_name,
        })
    return records


def heartbeat():
    """One-line coverage + cadence status for the SessionStart audit suite.

    Reads the OPTIONAL vault/.maintenance.json "harvest" section:
        {"last_round": "YYYY-MM-DD", "interval_days": N, "source_gap_ceiling": M}
    DUE when days-since-last-round >= interval_days OR SOURCE_GAP >= ceiling.
    Silent-safe: no config => prints the counts with no cadence verdict.
    """
    import json
    from datetime import date

    counts = defaultdict(int)
    sg_pid = 0
    single = multi = 0
    for r in gather_records():
        counts[r["category"]] += 1
        if r["category"] == "SOURCE_GAP" and r.get("pid"):
            sg_pid += 1
        if is_single_sourced(r):
            single += 1
        elif (r.get("hosts") or 0) >= 2:
            multi += 1
    sg, low, well = counts["SOURCE_GAP"], counts["LOW_COVERAGE"], counts["WELL_SOURCED"]
    base = (f"RECIPE-S: SOURCE_GAP {sg} (harvestable {sg_pid}), LOW_COVERAGE {low}, "
            f"WELL_SOURCED {well}, LIVING_EXCLUDED {counts['LIVING_EXCLUDED']}")
    # Source BREADTH, reported every session so "do not rely on one repository"
    # is a standing number rather than an intention that drifts back.
    base += (f"; SINGLE_SOURCED {single} (documented by ONE host only), "
             f"MULTI_SOURCED {multi}")

    # deferred_decisions 19: the strict/loose gap, reported every session so the
    # staged migration cannot quietly stall. Drops to 0 when the flip is safe.
    loose_t = strict_t = 0
    for _path, _rows in entry_blocks_with_ids().items():
        for _id, _name, _ln, _body in _rows:
            _b = truncate_at_break(_body)
            loose_t += count_records(_b)
            strict_t += count_records_strict(_b)
    if loose_t - strict_t:
        base += (f"; SOURCES-BULLET GAP {loose_t - strict_t} records cited outside a "
                 f"Sources bullet [migrate: --sources-conformance]")

    cfg = {}
    try:
        with open(os.path.join(VAULT, ".maintenance.json"), encoding="utf-8") as f:
            cfg = json.load(f).get("harvest", {}) or {}
    except (FileNotFoundError, ValueError):
        cfg = {}
    if not cfg:
        print(base + "; no harvest cadence configured (.maintenance.json `harvest`) — "
                     "run scripts/harvest_sources.py for the SOURCE_GAP worklist.")
        return 0

    interval = cfg.get("interval_days")
    ceiling = cfg.get("source_gap_ceiling")
    last = cfg.get("last_round")
    days = None
    reasons = []
    if last:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(last))
        if m:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            days = (date.today() - d).days
            if interval and days >= interval:
                reasons.append(f"{days}d since last round >= {interval}d cadence")
    # THE CEILING WATCHES THE HARVESTABLE SUBSET, NOT THE WHOLE BUCKET (28 JUL
    # 2026, #111 — the second half of deferred_decisions item 11). SOURCE_GAP
    # mixes populations a Recipe-S round cannot touch: entries with NO FS PID have
    # no /tree/person/sources/{PID} to visit, so their route is a library/archive
    # pass. Comparing the whole bucket to a harvest ceiling fired a DUE alarm on a
    # number that was not the worklist, and the response was to raise the ceiling
    # — twice. The honest worklist is the PID-bearing subset; watch that.
    if ceiling is not None and sg_pid >= ceiling:
        reasons.append(f"harvestable SOURCE_GAP {sg_pid} >= ceiling {ceiling}")

    cad = f"; last round {last}" + (f" ({days}d ago)" if days is not None else "") if last else ""
    if reasons:
        print(base + cad + "; status DUE — " + "; ".join(reasons)
              + ". Run a Recipe-S pass (prompts/19-fs-source-harvest.md) over the SOURCE_GAP "
                "worklist, then reset harvest.last_round in vault/.maintenance.json.")
    else:
        nxt = f" (next due in {interval - days}d)" if (interval and days is not None) else ""
        print(base + cad + f"; status OK{nxt}.")
    return 0


def main():
    vault_config.require_vault(VAULT)
    parser = argparse.ArgumentParser(description="Coverage audit for FS source ARKs in vault narratives.")
    parser.add_argument("--gen", type=int, default=None, help="Filter to a single generation.")
    parser.add_argument("--gen-range", type=str, default=None, help='e.g. "3-5".')
    parser.add_argument("--confidence", type=str, default=None, help="Filter by tier (S/M/Sp/U).")
    parser.add_argument("--limit", type=int, default=20, help="Cap per-category report length.")
    parser.add_argument("--csv", action="store_true", help="Output a single CSV instead of categorized report.")
    parser.add_argument("--region", type=str, default=None, help="Filter by region substring (e.g. Italian, Polish, British).")
    parser.add_argument("--include-structural", action="store_true",
                        help="Fold STRUCTURAL_GAP entries (deep medieval / pre-register lines that can never get an indexed-record ARK) back into SOURCE_GAP.")
    parser.add_argument("--sources-conformance", action="store_true",
                        help="Report the deferred_decisions-19 migration worklist: entries whose "
                             "records are cited OUTSIDE a `- **Sources**` bullet, and would stop "
                             "counting when strict crediting is switched on.")
    parser.add_argument("--heartbeat", action="store_true",
                        help="Print a one-line coverage + cadence status for the SessionStart audit suite (reads .maintenance.json `harvest`).")
    args = parser.parse_args()

    if args.sources_conformance:
        loose = strict = 0
        zero, partial = [], 0
        for path, rows in entry_blocks_with_ids().items():
            for _id, name, _ln, body in rows:
                body = truncate_at_break(body)
                w = count_records(body)
                if not w:
                    continue
                st = count_records_strict(body)
                loose += w
                strict += st
                if st == 0:
                    zero.append((w, name, os.path.basename(path)))
                elif st < w:
                    partial += 1
        print("=== SOURCES-BULLET CONFORMANCE (deferred_decisions 19) ===")
        print(f"  records credited today                : {loose}")
        print(f"  records inside a `- **Sources**` bullet: {strict}")
        print(f"  would stop counting on the flip       : {loose - strict} "
              f"({100.0 * (loose - strict) / loose:.1f}%)" if loose else "")
        print(f"  entries dropping to ZERO              : {len(zero)}   <- MIGRATE THESE FIRST")
        print(f"  entries losing SOME records           : {partial}")
        print()
        print("  Migration = move the entry's real record citations into a `- **Sources**`")
        print("  bullet. A locator that is a research ROUTE is meant to stop counting; a")
        print("  locator that documents the person is meant to move. That call is per-entry.")
        print()
        for w, name, f in sorted(zero, reverse=True):
            print(f"    {w:>3} records  {name[:46]:<46} {f}")
        return 0

    if args.heartbeat:
        return heartbeat()

    gen_lo = gen_hi = None
    if args.gen is not None:
        gen_lo = gen_hi = args.gen
    if args.gen_range:
        a, b = args.gen_range.split("-")
        gen_lo, gen_hi = int(a), int(b)

    records = gather_records(gen_lo, gen_hi, args.confidence, args.region, args.include_structural)

    if args.csv:
        import csv
        w = csv.writer(sys.stdout)
        w.writerow(["pid", "name", "gen", "confidence", "region", "category", "ark_count", "narr_file", "narr_name", "id", "life_status"])
        # `id` is APPENDED, never inserted: two consumers (keystone_report,
        # migrate_profile_status) parsed this CSV BY COLUMN POSITION, and putting id
        # first silently shifted ark_count from index 6 to 7 -> both read the category
        # string as the count, skipped every row, and returned an EMPTY census.
        # keystone_report then lost its THIN veto and over-flagged (79 -> 85 rows).
        # Both now read by header name; the append keeps any unknown consumer safe.
        for r in sorted(records, key=lambda r: (r["gen"] or 999, r["category"], -r["ark_count"])):
            w.writerow([r["pid"] or "", r["name"], r["gen"], r["confidence"], r["region"], r["category"], r["ark_count"], r["narr_file"], r["narr_name"], r.get("id",""), r.get("life_status") or ""])
        return

    # Categorized report
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)

    total = len(records)
    print(f"=== RECIPE-S COVERAGE AUDIT ===")
    print(f"Vault PIDs with narrative-entry analysis: {total}")
    if args.gen is not None:
        print(f"Filter: Generation {args.gen}")
    if args.gen_range:
        print(f"Filter: Generations {args.gen_range}")
    if args.confidence:
        print(f"Filter: confidence tier '{args.confidence}'")
    if args.region:
        print(f"Filter: region substring '{args.region}'")
    print()

    # Order categories by priority
    cat_order = [
        ("SOURCE_GAP",     "[1] SOURCE_GAP — 0 ARKs cited, ACTIONABLE (highest-priority Recipe-S / Source-Linker targets)"),
        ("NO_NARRATIVE",   "[2] NO_NARRATIVE — the roster has this PID but NO entry this parser can credit. Not 'no write-up': the roster comes FROM the narratives, so an entry exists. It means the census's shape-based header patterns cannot see that entry — typically a name carrying quotes, parentheses or a slash alias, which the name token classes cannot express. Until 23 JUL 2026 these people silently inherited the PRECEDING entry's record count, so the category read 0 and looked vacuous. See spec/entry-boundary Spec 05"),
        ("LOW_COVERAGE",   "[3] LOW_COVERAGE — 1-3 ARKs cited"),
        ("WELL_SOURCED",   "[4] WELL_SOURCED — 4+ ARKs cited"),
        ("UNCITED",        "[5] UNCITED — 0 ARKs, structurally unsourceable, AND no scholarly citation either. The hidden worklist: not harvestable, but not yet documented from the books either (deep medieval Gen>=%d / pre-register / off-FS lines per .autoresearch.json)" % STRUCTURAL_GEN),
        ("BOOK_SOURCED",   "[6] BOOK_SOURCED — 0 ARKs and structurally unsourceable, but DOCUMENTED: cites Cawley/Medlands, Richardson, ODNB, Complete Peerage, the Henry Project, MGH/chronicles or Great Migration. Finished work that can never earn a record ARK — not a gap"),
        ("LIVING_EXCLUDED", "[7] LIVING_EXCLUDED — life_status living/unknown (or unrecorded, which fails closed). NEVER a target: this vault forbids web-searching these people, so no coverage caption applies to them. Listed so the count stays VISIBLE rather than silently dropped; --include-structural does not fold these back"),
    ]
    for cat, label in cat_order:
        items = sorted(by_cat[cat], key=lambda r: (r["gen"] or 999, -r["ark_count"], r["name"]))
        print(f"{label}: {len(items)} entries")
        if cat == "LIVING_EXCLUDED":
            # The COUNT is the finding; the roster is not. These are living family
            # members and this report is a worklist, so it names none of them —
            # the vault's living-person privacy rule applies to its own tooling.
            print("  (rows suppressed by design — living people are not a worklist)")
            print()
            continue
        for r in items[: args.limit]:
            gen_str = f"Gen {r['gen']:>2}" if r["gen"] is not None else "Gen ??"
            ark_str = f"{r['ark_count']:>2} ARKs" if cat in ("LOW_COVERAGE", "WELL_SOURCED") else ""
            # PID may be absent (fs: TBD / none / unset) now that the census keys
            # on the vault id. Show the id instead, prefixed, so the row is still
            # actionable AND it is obvious at a glance that there is no FS profile
            # to harvest — these are the entries that used to be invisible here.
            ident = r["pid"] or ("=" + (r.get("id") or "?"))
            print(f"  {gen_str} {r['confidence']:<2} {ident:<10} {r['name'][:55]:<55} {ark_str:<9} [{r['region']}, {r['narr_file']}]")
        if len(items) > args.limit:
            print(f"  ... and {len(items) - args.limit} more")
        print()

    print("=== SUMMARY ===")
    print(f"  Total PIDs analyzed:     {total}")
    for cat, _ in cat_order:
        print(f"  {cat:<16} {len(by_cat[cat])}")

    # Per-host locator breakdown (Spec 03): where the cited records are hosted.
    # Counts distinct locators per host across the best-cited entry of each PID.
    host_totals: Dict[str, int] = defaultdict(int)
    for r in records:
        for host, n in (r.get("per_host") or {}).items():
            host_totals[host] += n
    if host_totals:
        print()
        print("  By host (distinct locators):")
        for host, n in sorted(host_totals.items(), key=lambda kv: -kv[1]):
            print(f"    {host:<18} {n}")

    print()
    print("Recommended next-action ARK count if SOURCE_GAP entries were harvested (assuming average yield):")
    sg_count = len(by_cat["SOURCE_GAP"])
    # Estimate yield by region pattern (per round-3 observations)
    avg_yield = 10  # rough
    print(f"  {sg_count} SOURCE_GAP entries × ~{avg_yield} ARKs/anchor = ~{sg_count * avg_yield} ARK harvest potential")


if __name__ == "__main__":
    main()
