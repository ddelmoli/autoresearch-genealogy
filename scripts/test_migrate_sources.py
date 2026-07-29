#!/usr/bin/env python3
"""Regression fixtures for migrate_sources.py.

Runnable with no test framework and no vault: `python3 scripts/test_migrate_sources.py`
(exit 0 = pass). Every fixture is inline text.

** WHY THIS FILE EXISTS. ** A trial `--apply` on a THROWAWAY COPY of four vault files
(28 JUL 2026) reported "86 bullets" migrated and would have written 59 damaged lines
while migrating ZERO locators and ZERO records. Two defects, both in the no-locator
branch, both invisible in the dry-run summary because the summary counts BULLETS
MATCHED rather than content changed:

  1. CORRUPTION. The annotation pattern `\\([^)\\n]*\\)` cannot nest, so an annotation
     like "(scholarly apparatus, rule 8 limb (b))" truncated at the INNER ')' and the
     rebuild spliced ": " into the middle of it.
  2. STRAY COLON. The rebuild appended ':' whenever the payload was non-empty, whether
     or not the original had one, turning "- **Sources** - cited with pages:" into
     "- **Sources**: - cited with pages:".

The fix is that a bullet with NO LOCATORS is never re-emitted from parsed groups: an
already-`Sources` bullet is returned byte-identical, and a legacy label gets a surgical
in-place swap. **The invariant these fixtures pin: if migrate_bullet extracts no
locators, it must not change anything except the label.**

Placeholder identifiers only; this repo is public.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import migrate_sources as M

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def one(line):
    """Run migrate_bullet on a single line -> (new_lines, records, locators, reason)."""
    res = M.migrate_bullet(line)
    if res is None:
        return None
    (new_lines, nrec, nloc, _flagged, reason), = res
    return new_lines, nrec, nloc, reason


# --------------------------------------------------------------------------- #
def test_no_locator_bullets_are_byte_identical():
    """The regression that cost 59 lines on a trial run."""
    print("\n-- a Sources bullet with NO locators must come back byte-identical --")
    cases = [
        # (1) the CORRUPTION case: a nested paren inside the annotation.
        "- **Sources** (scholarly apparatus, rule 8 limb (b)):",
        "- **Sources** (scholarly apparatus per rule 8 limb (b); this line will never earn a record ARK):",
        # (2) the STRAY COLON case: payload leads with a dash, no colon after the label.
        "- **Sources** - cited with pages:",
        "- **Sources** - no record ARK is claimed for him; he is documented through his son:",
        # ordinary prose payloads
        "- **Sources** (Recipe-S harvest 2026-06-21): 1 FS source / 0 record ARKs (book only).",
        "- **Sources**: Cawley, Medlands, ROYAL ANCESTRY chapter, pp. 12-14.",
        "  - **Sources** (indented, nested under another bullet):",
    ]
    for line in cases:
        got = one(line)
        check(got is not None, f"recognised as a source bullet: {line[:46]}...")
        if got is None:
            continue
        new_lines, nrec, nloc, reason = got
        check(new_lines == [line],
              f"unchanged ({reason}): {line[:46]}...")
        check((nrec, nloc) == (0, 0), "and reports 0 records / 0 locators")


def test_legacy_label_relabels_surgically():
    print("\n-- a LEGACY label with no locators is relabelled and nothing else --")
    line = "- **FS-attached sources** (scholarly apparatus, rule 8 limb (b)): none yet."
    new_lines, nrec, nloc, reason = one(line)
    check(new_lines == ["- **Sources** (scholarly apparatus, rule 8 limb (b)): none yet."],
          "label swapped in place, nested paren and payload preserved exactly")
    check(reason == "no-locators-relabel", "reported as a relabel, not a migration")
    check((nrec, nloc) == (0, 0), "still 0 records / 0 locators")


def test_real_migration_still_works():
    """The negative control: the fix must not have turned the migrator into a no-op."""
    print("\n-- NEGATIVE CONTROL: a bullet WITH locators still migrates --")
    line = "- **FS-attached sources** (Recipe-S 30 MAY 2026): 1:1:XXXX-XXX, 1:1:YYYY-YYY"
    new_lines, nrec, nloc, reason = one(line)
    check(len(new_lines) == 3, "expands into a header plus one sub-bullet per record")
    check(new_lines[0].startswith("- **Sources**"), "relabelled to Sources")
    check(nloc == 2 and nrec == 2, "2 locators -> 2 records")
    check(all("fs:1:1:" in l for l in new_lines[1:]), "locators are host-prefixed")
    check(new_lines != [line], "and the line genuinely changed, so this test can fail")


def test_untouched_bullets_are_not_counted_as_work():
    print("\n-- a run that migrates nothing must not REPORT bullets --")
    text = ("**Someone Placeholder** (b. 1600)\n"
            "- meta: {id: P-AAAAAA, generation: 9}\n"
            "- **Sources** (scholarly apparatus, rule 8 limb (b)):\n"
            "  - Cawley, Medlands, chapter and page.\n")
    new_text, stats = M.migrate_text(text)
    check(new_text == text, "the text is returned byte-identical")
    check(stats["bullets"] == 0, "0 bullets reported as migrated")
    check(stats["untouched"] == 1, "the no-op bullet is counted separately")
    check(stats["records"] == 0 and stats["locators"] == 0, "0 records / 0 locators")


def test_idempotent_on_already_migrated():
    print("\n-- already-migrated bullets stay untouched across repeated runs --")
    text = ("- **Sources** (harvest):\n"
            "  - 1910 census - fs:1:1:XXXX-XXX\n"
            "  - 1920 census - fs:1:1:YYYY-YYY\n")
    once, _ = M.migrate_text(text)
    twice, _ = M.migrate_text(once)
    check(once == text, "first run is a no-op")
    check(twice == once, "second run is a no-op too")


def main():
    test_no_locator_bullets_are_byte_identical()
    test_legacy_label_relabels_surgically()
    test_real_migration_still_works()
    test_untouched_bullets_are_not_counted_as_work()
    test_idempotent_on_already_migrated()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
