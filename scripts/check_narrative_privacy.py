#!/usr/bin/env python3
"""check_narrative_privacy.py — narrative-model validator (spec/optional-person-model, Spec 04d).

Option B (user-confirmed): the Ruby `validate-genealogy-vault.rb` owns the FILE
model; this Python check owns the NARRATIVE model, run over the person_store seam.
For a `person_model: narrative` vault it enforces the SAME living-person privacy
invariant the Ruby validator enforces on `type: person` files —

    a living/unknown person must NOT expose an exact birth/death DATE
    (an approximate year like "1990" or "abt 1850" is fine; "1990-04-12",
     "12 Apr 1990", "Apr 12, 1990" is not)

— plus the narrative-model integrity basics (every entry has a unique `id` and a
`generation`, and a `life_status` so privacy can be evaluated at all).

TWO PASSES (the second added 21 JUL 2026 after a manual sweep found the first pass
was undercounting by 3x):

  Pass 1 (`check`)        — the person's OWN record: their parsed born/died vitals.
  Pass 2 (`check_mentions`) — the same living/unknown people MENTIONED ANYWHERE in
                            the vault's Markdown, not just in their own entry.

Pass 2 exists because pass 1 only ever sees a person's entry header. A living
person's exact birth date can equally sit in a derived file that holds no person
entries at all — a hereditary-society lineage walk, an ASCII pedigree block, an
audit table, a body bullet under someone else's entry. A real sweep found 20 such
lines (9 of them in one derived file) while pass 1 reported 7.

Pass 2 is deliberately SCOPED to names the roster already knows are living/unknown,
and does not try to guess liveness for people who have no entry: a blanket
"exact date with a recent year" rule over this vault matched ~1,470 lines, nearly
all of them deceased people whose death year is simply not on the same line, which
is unusable as a gate. The residual gap is therefore people who are living but have
no person entry at all — they are invisible here BY CONSTRUCTION, and the mitigation
is to give them an entry with `life_status: living`. This is documented rather than
silently papered over.

By default pass 2 skips write-once historical trees (`logs/`, `*_Archive/`), which
record what was known at the time; `--all` includes them.

`validate-repo` dispatches here when the vault's person_model is narrative (the
Ruby validator then finds no `type: person` files and harmlessly passes). Run
standalone: `python3 check_narrative_privacy.py [--vault V]`. Exit 1 on violations.

Violation messages name the `id` and lineage file but NEVER echo the offending
date value, so running the check does not itself surface private data.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config
import person_store as ps

_MONTHS = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
# THE day-precision rule for the narrative model — the Python twin of
# validate-genealogy-vault.rb's DAY_PRECISE. Both must stay in step; the Ruby
# file carries the full rationale. In short (spec/structured-dates Spec 01):
#
#   * DAY-PRECISION is the trigger, not the presence of a year. `1780`,
#     `ABT 1780`, `BEF 1780`, `BET 1779 AND 1781` remain permitted for a living
#     person — the vault publishes approximate years for the living by design.
#   * The GEDCOM 7 `DateValue` form `3 SEP 1780` is ALREADY caught here (the
#     month alternation is case-insensitive), which is why this side needed no
#     new branch when the grammar was adopted; the Ruby `exact_date?` did, since
#     it matched ISO only and would have silently stopped recognising an exact
#     date for a living person.
#   * It SEARCHES rather than anchors, so a day-precise bound inside a range
#     (`BET 3 SEP 1780 AND 1790`) trips it too — deliberate fail-closed
#     behaviour for a privacy gate.
#   * Years are `\d{4}` on purpose: this gate protects LIVING people, none of
#     whom have a 3-digit birth year. Wider year support belongs to gdate
#     (Spec 02); widening it here would only add false positives to pass 2.
_EXACT_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
    rf"|\b\d{{1,2}}\s+(?:{_MONTHS})[a-z]*\.?\s+\d{{4}}\b"
    rf"|\b(?:{_MONTHS})[a-z]*\s+\d{{1,2}},\s+\d{{4}}\b",
    re.I,
)
_PRIVATE_LS = frozenset({"living", "unknown"})
# Record fields screened against the rule above. The `*_phrase` keys are the
# GEDCOM 7 PHRASE escape hatch (Spec 03) — free text, so they get the SAME
# screen, not a weaker one. Read with getattr so this holds whether or not the
# Spec 03 fields exist yet on PersonRecord.
_PRIVATE_DATE_ATTRS = (("born", "BIRTH"), ("born_phrase", "BIRTH"),
                       ("died", "DEATH"), ("died_phrase", "DEATH"))


def has_exact_date(value):
    """True when `value` discloses a specific DAY, in ISO or GEDCOM 7 notation."""
    return bool(value and _EXACT_DATE.search(str(value)))


def check(vault):
    """Return a list of violation strings for the narrative entries in `vault`.
    Uses NarrativeBackend directly so it works regardless of the vault's configured
    model (the CLI gates on model; this function is the reusable core)."""
    violations = []
    seen = {}
    for r in ps.NarrativeBackend.iter_people(vault):
        loc = r.source_file or "?"
        if not r.id:
            violations.append(f"{loc}: entry {r.name!r} has no id")
            continue
        if r.id in seen:
            violations.append(f"{loc}: duplicate id {r.id} (first seen in {seen[r.id]})")
        seen[r.id] = loc
        if r.generation is None:
            violations.append(f"{loc}: {r.id} has no generation")
        ls = (r.life_status or "").strip().lower()
        if not ls:
            violations.append(f"{loc}: {r.id} has no life_status "
                              f"(cannot evaluate privacy — fail closed)")
            ls = "unknown"
        if ls in _PRIVATE_LS:
            for attr, label in _PRIVATE_DATE_ATTRS:
                if has_exact_date(getattr(r, attr, None)):
                    violations.append(
                        f"{loc}: {r.id} is {ls} but exposes an exact {label} date")
    return violations


# Pass 2 -------------------------------------------------------------------
# How far after a name an exact date may sit and still be taken as THAT person's.
# 60 chars comfortably spans "Jane Q Ancestor (b. 12 Apr 1950, Springfield)" while
# staying clear of the next person on a "Children: A (...); B (...)" line.
_MENTION_WINDOW = 60
_SKIP_DIRS = ("logs", "Handoff_Archive", "Open_Questions_Archive",
              "Research_Log_Archive", "Shard_Split_Archive")
# Pass 2 flags BIRTH/DEATH dates only. The invariant is about vitals; a living
# person's marriage date, or a "read 20 JUL 2026" provenance stamp, is not a
# violation, and matching every exact date made the pass too noisy to gate on.
#
# The marker may be separated from the date by a little connective tissue, so
# that "birth record (12 Apr 1950)" and "was born on 12 Apr 1950" both count --
# an earlier end-anchored version missed exactly those two shapes on the live
# vault. `(?<![-\w])` keeps "New York-born. **FS PID ADOPTED 20 JUN 2026**" out:
# there the marker is a compound-adjective tail and the date is provenance.
#
# NOTE the two alternation groups: `b.`/`d.` must NOT be followed by `\b`. After
# a literal "." the next character is a space, i.e. non-word to non-word, so `\b`
# never matches there -- an earlier single-group version silently disabled the
# commonest marker in the whole vault ("b. 12 Apr 1950") and was caught only by
# the regression test. Keep them separate.
_VITAL_MARKER = re.compile(
    r"(?<![-\w])(?:(?:b|d)\.|(?:born|died|birth|death)\b)"
    r"[\s:,(—-]*(?:record|records|date|dated|cert(?:ificate)?|about|abt|circa|c\.|ca\.|on|in)?"
    r"[\s:,(—-]*$",
    re.I)
# How much text before the date may carry that marker.
_MARKER_LOOKBACK = 30


def _living_names(vault):
    """{display name -> id} for roster people whose life_status is living/unknown.
    Only multi-token names of reasonable length are used, so a bare given name
    ('Hannah') cannot carpet-match unrelated prose."""
    out = {}
    for r in ps.NarrativeBackend.iter_people(vault):
        ls = (r.life_status or "").strip().lower()
        if ls not in _PRIVATE_LS or not r.id:
            continue
        name = (r.name or "").strip()
        if len(name) < 6 or " " not in name:
            continue
        parts = name.split()
        for variant in {name, f"{parts[0]} {parts[-1]}"}:
            out.setdefault(variant, r.id)
    return out


def _vault_markdown(vault, include_all=False):
    for root, dirs, files in os.walk(vault):
        if not include_all:
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        else:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(files):
            if fn.endswith(".md"):
                yield os.path.join(root, fn)


_META_LINE = re.compile(r"^\s*-\s*meta:\s*\{(.*)\}\s*$")
_HEADING = re.compile(r"^#{1,6}\s")
# Entry-BODY attribution needs two guards, because a living person's narrative
# legitimately quotes OTHER people's vitals -- sibling lists, "<Forename> d. 1951".
# Without them the rule fires on a deceased sibling line such as
# "- Jane Q Example (b. 6 Aug 1948 ... d. 2010)" sitting inside a living
# parent's entry, and reports it against the parent.
#   1. A death date is never the living owner's -- they are alive. Birth only.
#   2. A two-token capitalised name just before the marker means the date belongs
#      to that person, not to the entry owner. (One token is too weak a signal:
#      "<State> birth record (...)" must still be caught.)
_BIRTH_ONLY = re.compile(r"(?<![-\w])(?:b\.|(?:born|birth)\b)", re.I)
_OTHER_NAME = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b")
_NAME_LOOKBACK = 40


def _meta_owner(line, living_ids):
    """If `line` is a meta block, return (id, is_living). Else (None, False)."""
    m = _META_LINE.match(line)
    if not m:
        return None, False
    pid = re.search(r"\bid:\s*(P-[0-9A-Z]+)", m.group(1))
    if not pid:
        return None, False
    return pid.group(1), pid.group(1) in living_ids


def check_mentions(vault, include_all=False):
    """Pass 2: exact birth/death dates for known-living people ANYWHERE in the
    vault's Markdown. Two attribution routes, because a date can belong to a
    person without naming them:

      by ENTRY  — inside a living person's own narrative entry, a body bullet
                  never repeats their name ("- Massachusetts birth record
                  (12 Apr 1950): not indexed..."). Ownership carries from the
                  entry's `- meta:` line until the next entry or heading.
      by NAME   — in derived files that hold no entries at all (lineage walks,
                  audit tables), attribution is the nearest preceding name.

    Returns violation strings; never echoes the offending date."""
    names = _living_names(vault)
    living_ids = set(names.values())
    if not names:
        return []
    violations = []
    for path in _vault_markdown(vault, include_all):
        rel = os.path.relpath(path, vault)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        owner = None  # id of the living person whose entry we are inside
        for lineno, line in enumerate(lines, 1):
            pid, is_living = _meta_owner(line, living_ids)
            if pid is not None:
                owner = pid if is_living else None
            elif _HEADING.match(line):
                owner = None
            for m in _EXACT_DATE.finditer(line):
                lead = line[max(0, m.start() - _MARKER_LOOKBACK):m.start()]
                if not _VITAL_MARKER.search(lead):
                    continue  # not a birth/death date — out of scope
                best, best_gap = None, _MENTION_WINDOW + 1
                for name, npid in names.items():
                    idx = line.rfind(name, 0, m.start())
                    if idx < 0:
                        continue
                    gap = m.start() - idx
                    if gap < best_gap:
                        best, best_gap = npid, gap
                if best is not None:
                    violations.append(
                        f"{rel}:{lineno}: {best} is living/unknown but an exact DATE "
                        f"appears beside their name")
                    break
                if owner is not None:
                    if not _BIRTH_ONLY.search(lead):
                        continue  # a death date cannot be the living owner's
                    if _OTHER_NAME.search(line[max(0, m.start() - _NAME_LOOKBACK):m.start()]):
                        continue  # the date belongs to the person just named
                    violations.append(
                        f"{rel}:{lineno}: {owner} is living/unknown but an exact BIRTH "
                        f"date appears in their entry body")
                    break
    return violations


def main():
    ap = argparse.ArgumentParser(description="Narrative-model privacy/integrity validator (Spec 04d).")
    ap.add_argument("--vault", help="Vault dir (default: $AUTORESEARCH_VAULT, else ../vault).")
    ap.add_argument("--force", action="store_true",
                    help="Run even if person_model is not 'narrative'.")
    ap.add_argument("--all", action="store_true",
                    help="Pass 2: also scan write-once history (logs/, *_Archive/).")
    ap.add_argument("--no-mentions", action="store_true",
                    help="Skip pass 2 (own-record check only, pre-21-JUL-2026 behaviour).")
    args = ap.parse_args()
    vault = vault_config.resolve_vault(args.vault)
    model = vault_config.get_person_model(vault)
    if model != "narrative" and not args.force:
        print(f"check_narrative_privacy: person_model is {model!r}; the file model is "
              f"validated by validate-genealogy-vault.rb. Skipping (use --force to run anyway).")
        return 0
    violations = check(vault)
    if not args.no_mentions:
        violations += check_mentions(vault, include_all=args.all)
    if not violations:
        print("check_narrative_privacy: ok")
        return 0
    print(f"check_narrative_privacy: {len(violations)} violation(s)", file=sys.stderr)
    for m in violations:
        print(f"- {m}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
