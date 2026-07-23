#!/usr/bin/env python3
"""
Coverage audit for FS source ARKs in vault narrative entries.

Recipe-S (source harvesting) extracts FS-attached primary-source ARKs from each
FS profile's Sources tab and appends them to the corresponding vault narrative
entry. This script audits which narrative entries are well-sourced vs which
need a Recipe-S harvest pass.

Strategy:
1. Read the canonical roster from the NARRATIVES via
   gen_person_index.parse_narrative() — PID -> (name, gen, tier, file) — for every
   entry that carries an FS PID (Person_Index.md was retired; see memory
   project_person_index_retirement). Entries with no FS PID are skipped (no FS
   profile to harvest). The old NO_NARRATIVE category is now vacuous by
   construction (every PID comes FROM a narrative entry).
2. Scan each Family_Tree*.md narrative file for bold-name entries that
   reference an FS PID. Group the body content following each entry header.
3. Count ARK references in each entry's body:
   - Long-form  `ark:/61903/(1:1:[A-Z0-9-]+)`
   - Short-form `1:1:[A-Z0-9-]{6,}` standalone tokens
4. Classify each PID-bearing entry by ARK count:
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
import vault_config
import tree_locator as T
import meta_presence_audit as MPA

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


def extract_arks(text: str) -> set:
    """Extract all source-record-IDs from vault narrative text, normalized.

    Backward-compat anchor: this is the LEGACY locator-token counter and is left
    UNCHANGED. `count_records` falls back to it for un-migrated bullets, so an
    all-legacy vault reports exactly as before Spec 03 (record_count == old
    ark_count)."""
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

# The SHORT host ids the migration emits as `host:` prefixes. Detection keys on
# these (not full words like "FamilySearch") so a prose "FamilySearch: the site"
# is never mistaken for a locator line. Includes hosts with no legacy pattern
# (anc/wt/etc.) whose locators only ever appear host-prefixed.
EMITTED_HOST_IDS = ["fs", "anc", "wt", "antenati", "metryki", "szukajwarchiwach", "agad"]
# A host-prefixed locator token: a short host id, a colon, then a non-space run.
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


def per_host_locators(text: str) -> "Dict[str, int]":
    """Return host_id -> count of DISTINCT locators of that host in `text`
    (across both legacy bare tokens and host-prefixed ones)."""
    counts: Dict[str, int] = defaultdict(int)
    seen = set()
    for pat, host, _kind in HOST_LOCATOR_PATTERNS:
        for m in pat.finditer(text):
            key = (host, m.group(1))
            if key not in seen:
                seen.add(key)
                counts[host] += 1
    # Host-prefixed locators whose host has NO legacy pattern (anc:dbid=..., wt:...).
    legacy_hosts = {h for _p, h, _k in HOST_LOCATOR_PATTERNS}
    for m in re.finditer(
            r"\b(" + "|".join(EMITTED_HOST_IDS) + r"):([0-9A-Za-z][^\s,;)\]]*)",
            text, re.IGNORECASE):
        host = m.group(1).lower()
        host = {"fs": "familysearch"}.get(host, host)
        if host in legacy_hosts:
            continue  # already tallied via its legacy pattern
        key = (host, m.group(2))
        if key not in seen:
            seen.add(key)
            counts[host] += 1
    return dict(counts)


def count_records(body: str) -> int:
    """Number of distinct source RECORDS cited in an entry body.

    Migrated entries (new `Sources` grammar) put one record per line, each with
    one or more host-prefixed locators. Count those lines, PLUS any legacy bare
    locator not yet moved onto a record line (transitional, so nothing is lost).
    A fully un-migrated body has no host-prefixed lines, so this returns exactly
    len(extract_arks(body)) — identical to the pre-Spec-03 count."""
    record_lines = [ln for ln in body.splitlines() if HOST_LOC_RE.search(ln)]
    legacy_ids = extract_arks(body)
    if not record_lines:
        return len(legacy_ids)
    # A record's identity is its SET of host:locator tokens. Dedupe records with an
    # identical locator set (the same source cited on two lines) so pre-existing
    # duplication does not inflate the count — matching the legacy set-based dedup.
    seen_records = set()
    covered = set()
    for ln in record_lines:
        toks = frozenset(m.group(0).lower() for m in FULL_HOST_LOC_RE.finditer(ln))
        if toks:
            seen_records.add(toks)
        covered |= extract_arks(ln)
    stray = legacy_ids - covered
    return len(seen_records) + len(stray)

# Match a bold-name narrative entry header. We re-use patterns from harvest_pids.py.
# Require the first name-token to look like a proper-noun: Cap + at least one
# lowercase letter (excludes all-caps acronyms like "FS-attached", "SECOND
# MARRIAGE", "NUMIDENT", "WWII", "AAD", "FS PID", etc.) Subsequent tokens may
# be initials, suffixes, or proper nouns.
NAME_TOKEN_FIRST = r"[A-ZÀ-Ý][a-zà-ÿ][\w\.\-'À-ÿ]*"
NAME_TOKEN_REST = r"[\w\.\-'À-ÿ]+"
# A name token may also be a bracketed qualifier ("[maiden surname unknown]",
# "[maiden unknown]") — without this, headers like
# "**Jane Doe [maiden surname unknown]** (b. ?, ...)" are not recognized as
# entry starts, so the PREVIOUS entry's body bleeds through them and any PID
# mentioned below inherits that entry's ARK count (a real bracketed-name entry
# once picked up the prior entry's AGAD acts this way).
NAME_TOKEN_ANY = rf"(?:{NAME_TOKEN_REST}|\[[^\]\n]{{1,40}}\])"
ENTRY_HDR_A = re.compile(
    rf"^[\-\*\s]*\*\*({NAME_TOKEN_FIRST}(?:\s+{NAME_TOKEN_ANY}){{1,8}})\*\*\s*\(([^)]{{0,1500}})\)",
    re.MULTILINE,
)
ENTRY_HDR_B = re.compile(
    rf"\*\*({NAME_TOKEN_FIRST}(?:\s+{NAME_TOKEN_ANY}){{1,8}})\s*\(([^)]{{0,1500}})\)\*\*",
)

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
    """Return PID -> {name, gen, confidence, file_col, region} for every
    PID-bearing person entry.

    Person_Index.md was RETIRED (memory project_person_index_retirement); the
    canonical roster now comes from the narratives via
    gen_person_index.parse_narrative() — each entry's bold-name header + `- meta:`
    block (id / FS / tier / gen). Only entries with an FS PID are returned (an
    entry without one has no FS profile whose Sources tab could be harvested).
    Region is classified from the narrative's file name via the optional shard
    manifest (shard_manifest.region_for expects the basename WITHOUT `.md`)."""
    manifest = shard_manifest.load_shard_manifest(VAULT)
    out: Dict[str, dict] = {}
    for e in G.parse_narrative():
        pid = e["pid"]
        if not pid:
            continue
        file_col = e["file"][:-3] if e["file"].endswith(".md") else e["file"]
        region = shard_manifest.region_for(file_col, manifest)
        tier = e["tier"] or "U"
        # Same PID can legitimately appear on >1 entry (FS conflation / a
        # duplicate-candidate flag); keep the first, matching prior behavior.
        if pid not in out:
            out[pid] = {
                "name": e["name"].strip("* "),
                "gen": e["gen"],
                "confidence": tier,
                "confidence_raw": tier,
                "file_col": file_col.strip(),
                "region": region,
            }
    return out


def _is_entry_header(name: str) -> bool:
    """True if this bold text is a person-entry header rather than bold prose.

    Combines the two heuristics the suite already owns, so there is one shared
    notion of "this bold text is a name":
      * meta_presence_audit._prose_reason — leading glyph (✅/⚠/⛔), trailing
        colon, ALL-CAPS run, or an uppercase month token ("20 JUL 2026"); and
      * tree_locator.looks_like_person_header — every lowercase token must be a
        toponymic connector or a patronymic particle, with bracketed titles
        stripped first.
    """
    return not MPA._prose_reason(name) and T.looks_like_person_header(name)


def extract_entries(text: str) -> List[Tuple[str, int, str]]:
    """Return list of (bold_name, start_offset, body_text) for each narrative
    entry in the text. body_text spans from the entry header to the next entry
    or to the next blank-line-separated paragraph."""
    entries = []
    seen_starts: set = set()

    # Find all entry-header matches
    matches = []
    for m in ENTRY_HDR_A.finditer(text):
        matches.append((m.start(), m.end(), m.group(1), m.group(2)))
    for m in ENTRY_HDR_B.finditer(text):
        # Don't double-record overlapping pattern-B matches
        if not any(abs(m.start() - s) < 10 for s, _, _, _ in matches):
            matches.append((m.start(), m.end(), m.group(1), m.group(2)))

    matches.sort()

    # Reject BOLD PROSE headers before any body span is computed (22 JUL 2026).
    #
    # The header regexes are shape-based and permissive (NAME_TOKEN_REST matches
    # any word), so bold prose bullets — "Death record", "Two marriages",
    # "Status update 11 MAY 2026", "Corroborated by ..." — were being treated as
    # narrative entries. Each such phantom entry captured the body of source
    # citations beneath it, and because gather_records() credits a PID with
    # max(ARKs) across EVERY block mentioning it, the phantom's ARK count was
    # handed to every PID named inside — inflating the coverage census.
    #
    # Filtering here (rather than after the loop) is what makes this safe: a
    # rejected header stops being a body boundary, so its text MERGES into the
    # preceding real entry, which is where those citations belonged all along.
    # Filtering afterwards would instead DISCARD the block and under-credit the
    # very people it documents — measured at 23 spurious downgrades when tried.
    #
    # Measured effect of this filter on the reference vault: 4 category changes,
    # ALL upgrades, 0 downgrades, SOURCE_GAP unchanged, no NO_NARRATIVE created.
    # Deliberately preserved: the convention of recording one person's sources
    # inline in a relative's entry (e.g. a wife's ARKs recorded inside her
    # husband's entry) — her credit is unchanged, because the entry they sit
    # under is itself a real person header.
    matches = [m for m in matches if _is_entry_header(m[2].strip())]

    # Structural breaks (a "---" rule or a "## " section heading) also terminate
    # an entry body. Without this, the last entry before a section boundary
    # swallows the following section prose until the NEXT recognized bold-name
    # header, and any PID mentioned in that prose inherits the entry's ARK count
    # (a false-credit bug fixed 02 JUL 2026).
    BREAK_RE = re.compile(r"^(?:---\s*|##\s.*)$", re.MULTILINE)
    break_offsets = [m.start() for m in BREAK_RE.finditer(text)]

    for i, (start, end, name, paren) in enumerate(matches):
        if start in seen_starts:
            continue
        seen_starts.add(start)
        # Body spans from this header to the next header's start OR the next
        # structural break, whichever comes first. Compare breaks against the
        # header match's END, not its start — ENTRY_HDR_A's leading [\-\*\s]*
        # can swallow a PRECEDING "---" line into the match, and truncating at
        # that break would leave a 1-char body (the truncated-entry-body bug).
        body_end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        for boff in break_offsets:
            if end <= boff < body_end:
                body_end = boff
                break
        body = text[start:body_end]
        entries.append((name.strip(), start, body))

    return entries


def scan_family_tree_files() -> Dict[str, List[Tuple[str, str, int, int, dict]]]:
    """Return PID -> list of (filename, name, record_count, body_length, per_host).

    For each narrative entry that references a PID, count the number of source
    RECORDS in the entry's body (Spec 03). For un-migrated entries this equals
    the legacy ARK-token count; migrated entries count `Sources` record lines.
    `per_host` is host_id -> distinct-locator count for the entry."""
    out: Dict[str, List[Tuple[str, str, int, int, dict]]] = defaultdict(list)

    pattern = os.path.join(VAULT, "Family_Tree*.md")
    import glob
    files = glob.glob(pattern)

    for path in files:
        fname = os.path.basename(path)
        with open(path) as f:
            text = f.read()

        entries = extract_entries(text)

        for name, start, body in entries:
            pids_in_entry = set(PID_RE.findall(body))
            if not pids_in_entry:
                continue
            # Count RECORDS (Spec 03). For an un-migrated body this is exactly
            # len(extract_arks(body)) — the legacy locator-token count — so the
            # metric is unchanged until a file is migrated. Source-ARK IDs share
            # the 4-3/4-4 shape with profile PIDs but appear in a `1:1:`/"ARK"
            # context the patterns require, so they do not overlap the profile
            # PID; don't subtract pids_in_entry (that once zeroed genuine IDs).
            record_count = count_records(body)
            per_host = per_host_locators(body)
            scholarly = has_scholarly_citation(body)
            for pid in pids_in_entry:
                out[pid].append((fname, name, record_count, len(body), per_host, scholarly))

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
# other and often copy this vault); WikiTree counts only because this vault already
# treats its CITED sources as a distinct corroboration layer.
SCHOLARLY_CITATION_RE = re.compile(
    r"Cawley|Medlands|\bFMG\b|fmg\.ac"                     # Foundation for Medieval Genealogy
    r"|Richardson|Magna Carta Ancestry|Royal Ancestry"      # Richardson
    r"|Complete Peerage|ODNB|Oxford DNB|doi:10\.1093/ref:odnb"
    r"|Henry Project|fasg\.org"
    r"|\bWeis\b|Ancestral Roots"
    r"|Flodoard|Regino|Monumenta Germaniae|\bMGH\b|Primary Chronicle"
    r"|Great Migration|NEHGR|NEHGS|\bTAG\b|Silver Book"
    r"|Visitation of|Chamberlain|Savage.{0,20}Genealogical Dictionary"
    r"|WikiTree",
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


def is_structural(pid: str, gen: Optional[int], region: Optional[str]) -> bool:
    """A 0-ARK entry that can essentially never acquire an indexed-record ARK."""
    if gen is not None and gen >= STRUCTURAL_GEN:
        return True
    if not region:
        return False
    for rule in _STRUCTURAL_RULES:
        rregion = rule.get("region")
        if rregion and rregion not in region:
            continue
        prefixes = tuple(rule.get("pid_prefixes", []))
        if prefixes and pid.startswith(prefixes):
            return True
        if pid in rule.get("pids", []):
            return True
    return False


def gather_records(gen_lo=None, gen_hi=None, confidence=None, region=None, include_structural=False):
    """Build the per-PID coverage records (shared by the report and the heartbeat)."""
    pi = parse_person_index()
    narrative_index = scan_family_tree_files()
    records = []
    for pid, info in pi.items():
        if gen_lo is not None and (info["gen"] is None or info["gen"] < gen_lo or info["gen"] > gen_hi):
            continue
        if confidence and info["confidence"] != confidence:
            continue
        if region and (info["region"] is None or region.lower() not in info["region"].lower()):
            continue
        matches = narrative_index.get(pid, [])
        if not matches:
            records.append({
                "pid": pid,
                "name": info["name"],
                "gen": info["gen"],
                "confidence": info["confidence"],
                "region": info["region"],
                "category": "NO_NARRATIVE",
                "ark_count": 0,
                "per_host": {},
                "narr_file": "",
                "narr_name": "",
            })
        else:
            # Use the match with the most records (best-cited entry).
            best = max(matches, key=lambda m: m[2])
            fname, narr_name, ark_count, body_len, per_host, scholarly = best
            category = classify(ark_count)
            if (category == "SOURCE_GAP" and not include_structural
                    and is_structural(pid, info["gen"], info["region"])):
                # Split (23 JUL 2026): documented-but-unharvestable vs genuinely
                # unresearched. Both stay out of the actionable SOURCE_GAP count.
                category = "BOOK_SOURCED" if scholarly else "UNCITED"
            records.append({
                "pid": pid,
                "name": info["name"],
                "gen": info["gen"],
                "confidence": info["confidence"],
                "region": info["region"],
                "category": category,
                "ark_count": ark_count,
                "per_host": per_host,
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
    for r in gather_records():
        counts[r["category"]] += 1
    sg, low, well = counts["SOURCE_GAP"], counts["LOW_COVERAGE"], counts["WELL_SOURCED"]
    base = f"RECIPE-S: SOURCE_GAP {sg}, LOW_COVERAGE {low}, WELL_SOURCED {well}"

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
    if ceiling is not None and sg >= ceiling:
        reasons.append(f"SOURCE_GAP {sg} >= ceiling {ceiling}")

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
    parser.add_argument("--heartbeat", action="store_true",
                        help="Print a one-line coverage + cadence status for the SessionStart audit suite (reads .maintenance.json `harvest`).")
    args = parser.parse_args()

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
        w.writerow(["pid", "name", "gen", "confidence", "region", "category", "ark_count", "narr_file", "narr_name"])
        for r in sorted(records, key=lambda r: (r["gen"] or 999, r["category"], -r["ark_count"])):
            w.writerow([r["pid"], r["name"], r["gen"], r["confidence"], r["region"], r["category"], r["ark_count"], r["narr_file"], r["narr_name"]])
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
        ("NO_NARRATIVE",   "[2] NO_NARRATIVE — PID in Person_Index but no bold-name narrative entry"),
        ("LOW_COVERAGE",   "[3] LOW_COVERAGE — 1-3 ARKs cited"),
        ("WELL_SOURCED",   "[4] WELL_SOURCED — 4+ ARKs cited"),
        ("UNCITED",        "[5] UNCITED — 0 ARKs, structurally unsourceable, AND no scholarly citation either. The hidden worklist: not harvestable, but not yet documented from the books either (deep medieval Gen>=%d / pre-register / off-FS lines per .autoresearch.json)" % STRUCTURAL_GEN),
        ("BOOK_SOURCED",   "[6] BOOK_SOURCED — 0 ARKs and structurally unsourceable, but DOCUMENTED: cites Cawley/Medlands, Richardson, ODNB, Complete Peerage, the Henry Project, MGH/chronicles or Great Migration. Finished work that can never earn a record ARK — not a gap"),
    ]
    for cat, label in cat_order:
        items = sorted(by_cat[cat], key=lambda r: (r["gen"] or 999, -r["ark_count"], r["name"]))
        print(f"{label}: {len(items)} entries")
        for r in items[: args.limit]:
            gen_str = f"Gen {r['gen']:>2}" if r["gen"] is not None else "Gen ??"
            ark_str = f"{r['ark_count']:>2} ARKs" if cat in ("LOW_COVERAGE", "WELL_SOURCED") else ""
            print(f"  {gen_str} {r['confidence']:<2} {r['pid']:<10} {r['name'][:55]:<55} {ark_str:<9} [{r['region']}, {r['narr_file']}]")
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
