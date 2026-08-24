#!/usr/bin/env python3
"""persona_dup_audit.py — one RECORD cited twice because FS minted two personas.

The census counts one RECORD per `- **Sources**` sub-bullet, and FamilySearch
mints **one persona per named party**. So a marriage indexed for bride and groom,
or a christening indexed for child, father and mother, arrives from a harvest as
several ARKs of ONE record — and if they land as several sub-bullets, the entry is
credited several times for one document.

** THE ROW THAT PROVED IT (24 AUG 2026, session #181; the entry itself is vault
data and is named only in that vault's own log). ** An entry cited one 1911
marriage twice. Resolved at the two record pages: one ark is the GROOM's persona
and the other the BRIDE's, of a single record — and the proof was mechanical
rather than inferential, because **FamilySearch's own *Cite This Record* block on
the bride's persona page gives the GROOM's ark as the record URL.** Same event
date, same place, same indexing timestamp. Merging them moved that entry from
WELL_SOURCED/10 to WELL_SOURCED/9.

⭐ **That trick generalises and is the cheapest way to settle a row:** open both
personas and compare the ark each page CITES for itself. Two personas of one
record name the same ark; two genuinely different records do not.

WHAT THIS SCREEN DOES: inside one Sources bullet, it groups sub-bullets by their
record DESCRIPTOR (the text before the last em-dash) and reports any descriptor
used more than once with surviving locators. It is free, needs no network, and its
whole value is that it names the ARKs worth opening.

⛔⛔ ** IT EMITS CANDIDATES. IT NEVER EMITS A VERDICT, AND THE BASELINE IS NOT 0. **
A repeated descriptor has innocent readings, and the reference vault contains at
least three of them: several children christened on ONE day, an event indexed
twice by two collections, and a genuine OS/NS dual date. Only opening each ARK and
reading its PRINCIPAL settles a row. ⚠ And the correction is not always "merge":
where the principal turns out to be a CHILD, the whole row is rule 8 limb (g) and
credits the entry NOTHING rather than merely crediting it twice — a bigger
correction in the same direction.
⚠ ** Never negate on the count mismatch itself ** (the standing Q316 rule): a
mismatch is not evidence that any given locator is wrong, and negating on one
destroys real citations.

** WHY THERE IS NO DEFAULT MODE. ** `--id` audits the row a lane just drew;
`--survey` walks the vault. Neither is the default, for the same reason
`entry_attribution_audit` refuses one: deferred 42 says **do not sweep these as a
campaign — audit each when a lane draws it**, so the whole-vault count is a
worklist to read, never a number to drive to zero.

⚠⚠ ** NEGATION IS RESOLVED OVER THE WHOLE ENTRY BEFORE THE BODY IS NARROWED, and
this script must keep that order. ** It is the ordering `count_records_strict`
documents: the `~` almost never lives inside the Sources bullet — it is written
where the rejection is explained — so narrowing first discards the negation and
keeps the token. Getting it backwards re-credited 27 records across 10 entries in
session #159.

⚠⚠ ** THE CONTROLS ARE NOT DECORATION; THE RUN REFUSES WITHOUT THEM. ** The first,
throwaway version of this screen returned a clean **0** across the whole vault and
was believed for several minutes. It was reading a `body` field that
`person_store` does not expose, so every record scored empty, the loop skipped all
of them, and nothing errored. It was caught only by re-running it against
`git HEAD`, where a just-merged duplicate HAD to appear. Hence, following
`ark_404_sweep`: two synthetic controls run FIRST — one that must flag, one that
must stay clean — and the run ABORTS if either misbehaves. And every report prints
its DENOMINATOR, because "0 candidates" means nothing without the number of
sub-bullets actually examined.
"""
import argparse
import os
import re
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as HS
import vault_config

# A sub-bullet inside a Sources bullet: indented, dash-led. The Sources bullet
# itself is found structurally by harvest_sources.sources_bullet_text.
SUB_BULLET_RE = re.compile(r"^\s{2,}-\s+(?P<text>\S.*)$")

# The descriptor is everything before the LAST em-dash; the locators follow it.
EMDASH = "—"


def _descriptor(sub_bullet_text: str) -> str:
    """The record's description — the part that says WHAT, not where.

    ⚠ Split on the LAST em-dash, not the first: descriptions legitimately contain
    one (`1847 birth atto — Antenati`), and the locator run is always last."""
    head = sub_bullet_text.rsplit(EMDASH, 1)[0] if EMDASH in sub_bullet_text else sub_bullet_text
    head = re.sub(r"[\s*_`]+$", "", head.strip())
    return re.sub(r"\s+", " ", head).lower()


def is_event_dated(descriptor: str) -> bool:
    """Does this descriptor name an EVENT, or only the collection it came from?

    ⚠⚠ THE TWO ARE DIFFERENT FINDINGS AND MUST NOT BE REPORTED TOGETHER. A
    descriptor repeated WITH an event date (*"6 January 1859 …"*) says the same
    event twice — the persona-duplicate candidate. A descriptor repeated with only
    a collection name (*"Testland State Vital Records, 1638-1927"*, *"FamilySearch
    indexed record (… census or military)"*) says nothing about events at all:
    those sub-bullets are very likely DIFFERENT records that were never named, and
    calling them duplicates would be a false over-credit claim. Measured on the
    reference vault the day this was written: 31 raw repeats split 11 dated and 20
    unnamed, and the largest single row — twelve sub-bullets under one label — was
    entirely the second kind.

    The test has to strip the COLLECTION's own year range first, or every
    collection name looks dated: *"Testland State Vitals, 1638-1927"* carries two
    years that describe the collection's coverage, not an event. Both regexes are
    harvest_sources' own, deliberately — the obituary screen already needed this
    exact distinction, and a second copy of it here would be a second reader."""
    stripped = HS._COLLECTION_RANGE_RE.sub(" ", descriptor)
    return bool(HS._LINE_YEAR_RE.search(stripped))


def groups_for_body(body: str):
    """[(descriptor, [locators…])] for every repeated descriptor in this entry.

    Order is load-bearing: negation body-wide FIRST, then narrow to the Sources
    bullet. See the module docstring."""
    text = HS.sources_bullet_text(HS.strip_negated_locators(body))
    by_desc = defaultdict(list)
    examined = 0
    for line in text.splitlines():
        m = SUB_BULLET_RE.match(line)
        if not m:
            continue
        locs = HS.record_locators(line)
        if not locs:
            continue          # a header line, or a row whose locators were negated
        examined += 1
        by_desc[_descriptor(m.group("text"))].append(locs)
    out = []
    for desc, rows in by_desc.items():
        if len(rows) > 1:
            kind = "DUP" if is_event_dated(desc) else "UNNAMED"
            out.append((desc, [tok for row in rows for tok in row], len(rows), kind))
    out.sort(key=lambda r: (r[3] != "DUP", -r[2]))
    return out, examined


# ---------------------------------------------------------------- the controls

_MUST_FLAG = """
- **Sources**
  - 1911 Placeholt Marriage Records 1637-1947 — fs:1:1:AAAA-AAA
  - 1911 Placeholt Marriage Records 1637-1947 — fs:1:1:BBBB-BBB
"""

# Three shapes that must STAY QUIET, and each is a real reading of a repeat:
#   * two genuinely different records (different descriptors);
#   * a repeat whose locators are all `~`-negated, so neither is credited;
#   * a repeat where the negation is written OUTSIDE the Sources bullet, which is
#     where it usually lives — this is the ordering pin.
_MUST_NOT_FLAG = """
- **Sources**
  - 1900 Testland Census — fs:1:1:AAAA-AAA
  - 1910 Testland Census — fs:1:1:BBBB-BBB
  - Find a Grave Index entry — NOT COUNTED, policy (e) — ~fs:1:1:CCCC-CCC
  - Find a Grave Index entry — NOT COUNTED, policy (e) — ~fs:1:1:DDDD-DDD
- **Named-in** (off the coverage metric): son's 1946 death — ~fs:1:1:EEEE-EEE
"""

_ORDERING_PIN = """
- **Sources**
  - 1899 Testland Deeds — fs:1:1:FFFF-FFF
  - 1899 Testland Deeds — fs:1:1:GGGG-GGG
- **FS write-back QUEUED 01 JAN 2026** (detach): both spellings refuted — ~fs:1:1:FFFF-FFF, ~fs:1:1:GGGG-GGG
"""


def self_check(verbose=False):
    """Run the detector over known inputs; return a list of failures.

    A screen that cannot be seen failing will report zeros forever."""
    bad = []
    flagged, seen = groups_for_body(_MUST_FLAG)
    if not flagged:
        bad.append("CONTROL FAILED: the known duplicate was not flagged")
    if seen != 2:
        bad.append(f"CONTROL FAILED: expected 2 sub-bullets examined, saw {seen}")
    clean, seen2 = groups_for_body(_MUST_NOT_FLAG)
    if clean:
        bad.append(f"CONTROL FAILED: clean body flagged {clean!r}")
    if seen2 != 2:
        bad.append(f"CONTROL FAILED: expected 2 credited sub-bullets in the clean "
                   f"body (the two negated ones must not count), saw {seen2}")
    pinned, _ = groups_for_body(_ORDERING_PIN)
    if pinned:
        bad.append("CONTROL FAILED: a duplicate negated OUTSIDE the Sources bullet "
                   "was still flagged — negation must be resolved body-wide FIRST")
    if verbose and not bad:
        print("  controls ok (flags a known duplicate, stays quiet on three "
              "innocent shapes, honours body-wide negation)")
    return bad


# ------------------------------------------------------------------ the report

def collect(vault, only_id=None):
    rows, entries, sub_bullets = [], 0, 0
    for path, blocks in HS.entry_blocks_with_ids(vault).items():
        for pid, name, _idx, body in blocks:
            if only_id and pid != only_id:
                continue
            entries += 1
            found, seen = groups_for_body(body)
            sub_bullets += seen
            for desc, locs, n, kind in found:
                rows.append((pid, name, os.path.basename(path), desc, locs, n, kind))
    rows.sort(key=lambda r: (r[6] != "DUP", -r[5]))
    return rows, entries, sub_bullets


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--id", help="audit ONE entry — the row a lane just drew "
                                 "(the deferred-42 mode)")
    ap.add_argument("--survey", action="store_true",
                    help="walk the whole vault. A worklist to READ, never a "
                         "number to drive to 0.")
    ap.add_argument("--self-check", action="store_true",
                    help="run the controls and exit")
    a = ap.parse_args()

    bad = self_check(verbose=a.self_check)
    if bad:
        print("PERSONA_DUP: REFUSING TO RUN — the detector's own controls failed:")
        for b in bad:
            print("   ", b)
        return 2
    if a.self_check:
        return 0

    if bool(a.id) == bool(a.survey):
        ap.error("choose --id <P-XXXXXX> (the drawn row) or --survey (the whole "
                 "vault). There is deliberately no default: deferred 42 says audit "
                 "each row when a lane draws it, not as a campaign.")

    vault = vault_config.resolve_vault(a.vault)
    rows, entries, sub_bullets = collect(vault, only_id=a.id)

    print("=== PERSONA_DUP — one record cited twice under two personas "
          "(advisory; CANDIDATES) ===\n")
    if a.id and entries == 0:
        print(f"  no entry with id {a.id} in this vault.")
        return 1
    dup = [r for r in rows if r[6] == "DUP"]
    unnamed = [r for r in rows if r[6] == "UNNAMED"]
    for label, group, gloss in (
            ("PERSONA_DUP", dup,
             "repeated descriptor that names an EVENT — candidate one record, "
             "several personas"),
            ("UNNAMED_RECORD", unnamed,
             "repeated descriptor naming only a COLLECTION — these are probably "
             "DIFFERENT records nobody named; NOT an over-credit claim")):
        if not group:
            continue
        print(f"--- {label}: {gloss} ---")
        for pid, name, f, desc, locs, n, _k in group:
            print(f"  {pid}  {name[:34]:34} x{n}  ({f})")
            print(f"      {desc[:100]}")
            print(f"      {', '.join(locs)}")
        print()
    print(f"PERSONA_DUP: {len(dup)} dated repeat(s) across "
          f"{len({r[0] for r in dup})} entr(ies)  [advisory; baseline is NOT 0]")
    print(f"UNNAMED_RECORD: {len(unnamed)} undated repeat(s) across "
          f"{len({r[0] for r in unnamed})} entr(ies)  [advisory; a NAMING defect, "
          f"rule 8: name the record in the sub-bullet]")
    # ⚠ THE DENOMINATOR IS THE POINT: a zero over zero sub-bullets is a BROKEN RUN,
    # not a clean vault. That distinction is the whole reason this line exists.
    print(f"           examined {sub_bullets} credited sub-bullet(s) "
          f"across {entries} entr(ies)")
    if entries and not sub_bullets:
        print("  ⛔ ZERO SUB-BULLETS EXAMINED across a non-empty vault — this run "
              "read nothing. Do NOT report it as clean.")
        return 2
    if dup:
        print("\n  NEXT (PERSONA_DUP): open each ARK, read its PRINCIPAL, group by EVENT.\n"
              "    one record  -> ONE sub-bullet carrying every locator\n"
              "    a CHILD as principal -> the row is limb (g): move it to a "
              "`Named-in` bullet, `~`-negated\n"
              "  ⛔ Never negate on the count mismatch itself (Q316).\n"
              "  ⏭ deferred 42: audit a row when a lane DRAWS it, not as a campaign.")
    return 0


def main_for_test():
    """`main` with no argv — the pin that a blind detector REFUSES rather than
    reporting a clean zero. Kept tiny and next to main so the two cannot drift."""
    saved = sys.argv
    try:
        sys.argv = ["persona_dup_audit.py", "--survey"]
        return main()
    finally:
        sys.argv = saved


if __name__ == "__main__":
    sys.exit(main())
