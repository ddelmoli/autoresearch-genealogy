#!/usr/bin/env python3
"""migrate_dates.py — populate the structured date keys from the header prose.

spec/structured-dates Spec 04. House converter conventions (`migrate_sources.py`,
`mint_ids.py`): **dry-run by default**, `--apply` to write, idempotent, `--vault`
resolved through `vault_config.resolve_vault`.

WHAT IT DOES. For each narrative person entry it reads the header parenthetical's
vitals, runs them through `gdate.normalise`, and writes `born` / `died` into the
`- meta:` block **only when a valid GEDCOM 7 DateValue comes out**. Everything else
is REPORTED, never guessed at.

WHAT IT REFUSES TO DO, and why each rule exists:

  * **Never writes a `*_phrase` automatically.** A phrase is an editorial act: it
    says "here is what the record actually reads, which the grammar cannot hold".
    Machine-generating that would put words in the record's mouth. The one
    mechanical exception is the Old Style / New Style dual year, where the phrase
    is a verbatim copy of the original notation and the conversion is provably
    lossless (GEDCOM 7 Appendix A §6.2) — and even that is OPT-IN, behind
    `--dual-year`, so the default run cannot write a phrase at all.
  * **Never touches a header.** The header is this migration's SOURCE. Rewriting it
    was tried on 22 JUL 2026 and rejected on measurement, and Spec 06 owns the
    header/meta sync question. `--verify-headers` proves the run did not.
  * **Skips `living` and `unknown` by default.** Both Gen-1 anchors of the vault
    this was built for are living. With `--include-living` the Spec 01
    day-precision screen still applies per value, so a living person can gain
    `ABT 1980` but never `3 SEP 1980`.
  * **Never overwrites an existing date key.** An entry already carrying `born:` is
    skipped, which is what makes a second `--apply` a no-op.

Usage:
    python3 scripts/migrate_dates.py                          # dry run, whole vault
    python3 scripts/migrate_dates.py --file Family_Tree_British_Magna_Carta.md
    python3 scripts/migrate_dates.py --apply --file ...       # one file at a time
    python3 scripts/migrate_dates.py --residue "$AUTORESEARCH_VAULT/Structured_Dates_Residue.md"

⚠ Write the residue worklist INTO THE VAULT, not into the framework repo. It names
every person whose date needs a human call, and a real vault's worklist tripped 39
terms of the framework's anonymization denylist. The vault is local-only; the
framework repo is a public fork. `privacy-audit-repo` is the backstop, but the rule
is: worklists about real people live with the real people.
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_narrative_privacy as cnp   # the Spec 01 day-precision predicate
import gdate
import person_store as ps
import vault_config

_PRIVATE_LS = frozenset({"living", "unknown"})


# --------------------------------------------------------------------------- #
# Residue classification
# --------------------------------------------------------------------------- #
# NOTE the two alternation groups: `\?+` and the dashes must NOT be followed by
# `\b`. After a '?' the next character is end-of-string or a space — non-word to
# non-word — so `\b` never matches there, and a single-group version silently
# classified the bare `?` (8 live values) as a place-leak instead of an absence
# marker. The same trap is documented in check_narrative_privacy's _VITAL_MARKER.
_ABSENCE = re.compile(
    r"\A\s*(?:(?:unknown|unk|deceased|dead|none|n/?a|tbd|young)\b|\?+|[-–—]+)", re.I)
_MODIFIER_WORD = re.compile(r"\A\s*(?:before|after|about|circa|abt|say|probably|likely|"
                            r"possibly|early|mid|late|by|between)\b", re.I)
_HAS_YEAR = re.compile(r"\b\d{3,4}\b")


def classify(value):
    """Bucket a value that produced no date, for the triage worklist.

    The buckets are the ones Spec 04 named, plus `dual-year`, which the corpus run
    turned up as a distinct MECHANICAL class rather than a judgement call."""
    v = (value or "").strip()
    if not v:
        return "empty"
    if _ABSENCE.match(v):
        return "absence"
    if gdate.split_dual_year(v):
        return "dual-year"
    if not _HAS_YEAR.search(v):
        return "place-leak"          # a date slot holding only a place name
    if _MODIFIER_WORD.match(v):
        return "unstructurable"      # a qualifier the grammar has no keyword for
    return "unstructurable"


CLASS_NOTE = {
    "absence": "Omit the key. Absence = unknown; never store `unknown`/`?` as a value. "
               "`young` is here too: it is not a date, and one live case is a parser "
               "artifact where `died` matched inside a prose aside about a DIFFERENT "
               "person, so nothing may be attached to that entry at all.",
    "place-leak": "A PLACE has leaked into the date slot. Content fix on the header; "
                  "flagged, never auto-edited.",
    "dual-year": "Old Style / New Style dual year. Mechanical and lossless via "
                 "GEDCOM 7 App. A §6.2 (DATE + PHRASE) — apply with --dual-year.",
    "unstructurable": "Needs a human call: either a date the grammar cannot express "
                      "(-> *_phrase) or a qualifier to resolve.",
    "empty": "Nothing in the date slot.",
}


# --------------------------------------------------------------------------- #
# The migration
# --------------------------------------------------------------------------- #
class Plan:
    def __init__(self):
        self.converted = []      # (rec, key, old, new)
        self.dual = []           # (rec, key, old, value, phrase)
        self.residue = []        # (rec, key, value, klass)
        self.skipped_private = []
        self.skipped_existing = 0
        self.blocked_private = []  # would have been day-precise for a living person


def build_plan(vault, only_file=None, include_living=False, dual_year=False):
    plan = Plan()
    for rec in ps.NarrativeBackend.iter_people(vault):
        if only_file and os.path.basename(rec.source_file or "") != only_file:
            continue
        ls = (rec.life_status or "").strip().lower()
        private = ls in _PRIVATE_LS
        if private and not include_living:
            plan.skipped_private.append(rec)
            continue
        raw = rec.raw or {}
        header = dict(zip(("born", "died"), raw.get("header_vitals") or (None, None)))
        had = set(raw.get("meta_date_keys") or ())
        for key in ("born", "died"):
            # A `<key>_phrase` with no date key is a DECISION, not a gap: it is the
            # recorded disposition for a value the grammar cannot express ("early
            # 1621"). Without this the worklist keeps listing settled entries as
            # outstanding work, which is how a residue list loses its meaning.
            if key in had or f"{key}_phrase" in had:
                plan.skipped_existing += 1      # already migrated -> idempotent
                continue
            source = header.get(key)
            if not source or not source.strip():
                continue
            value, _residue = gdate.normalise(source)
            if value is None:
                dual = gdate.split_dual_year(source) if dual_year else None
                # A dual-year pair is only safe to apply automatically when what
                # is left over is a PLACE. `c.877/878 or c.910/920` passes the
                # consecutive-year test on its first pair and would have been
                # written as `ABT 877` + phrase `c.877/878`, silently discarding
                # the second candidate range entirely. If the residue still holds
                # a year, this is a human call, not a batch.
                if dual and _HAS_YEAR.search(dual[2] or ""):
                    plan.residue.append((rec, key, source, "unstructurable"))
                    continue
                if dual:
                    v, phrase, _r = dual
                    if private and cnp.has_exact_date(v):
                        plan.blocked_private.append((rec, key, v))
                        continue
                    plan.dual.append((rec, key, source, v, phrase))
                else:
                    plan.residue.append((rec, key, source, classify(source)))
                continue
            # Spec 01 screen, applied per VALUE even under --include-living.
            if private and cnp.has_exact_date(value):
                plan.blocked_private.append((rec, key, value))
                continue
            plan.converted.append((rec, key, source, value))
    return plan


def apply_plan(vault, plan):
    """Group by record so an entry with both born and died is written once.

    ⚠ The clearing step below is load-bearing, and its absence was caught by the
    Spec 03 write-time gate on the first live run rather than by review.
    `promote_dates=True` promotes EVERY date field set on the record — and
    `record.born` falls back to the header, so an entry whose born is residue
    (Eudes of Vermandois, header `c.985/990`) but whose died converted cleanly
    would carry that residue straight into the meta block. It raised
    InvalidDateValue mid-run, after 51 entries had already been written.

    So before writing, every date field that this plan did NOT convert is cleared
    — EXCEPT one the meta block already carried, since clearing that would DELETE
    an existing key (`_apply_meta_changes` drops keys absent from the new mapping).
    """
    pending = collections.OrderedDict()
    planned = collections.defaultdict(set)
    for rec, key, _old, new in plan.converted:
        pending.setdefault(id(rec), rec)
        planned[id(rec)].add(key)
        setattr(rec, key, new)
    for rec, key, _old, value, phrase in plan.dual:
        pending.setdefault(id(rec), rec)
        planned[id(rec)].update({key, key + "_phrase"})
        setattr(rec, key, value)
        setattr(rec, key + "_phrase", phrase)
    written = 0
    for rid, rec in pending.items():
        keep = planned[rid] | set((rec.raw or {}).get("meta_date_keys") or ())
        for k in ps.DATE_KEYS:
            if k not in keep:
                setattr(rec, k, None)
        ps.NarrativeBackend.write_person(vault, rec, promote_dates=True)
        written += 1
    return written


def header_lines(vault, only_file=None):
    """Every bold-name header line in the vault, for the no-header-touched proof."""
    out = {}
    import glob
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        if only_file and os.path.basename(path) != only_file:
            continue
        rel = os.path.relpath(path, vault)
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if ps._BOLD.match(line):
                    out[(rel, i)] = line
    return out


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def write_residue_report(path, plan, vault, total):
    lines = [
        "# Structured dates: residue worklist",
        "",
        "Generated by `scripts/migrate_dates.py`. Every value here produced NO valid",
        "GEDCOM 7 `DateValue`, so the migration left it alone rather than guess.",
        "Resolve each by hand: give the entry a `born`/`died` the grammar accepts, put",
        "the original notation in `born_phrase`/`died_phrase`, or leave the key absent",
        "(absence = unknown, which is a legitimate final answer for most of these).",
        "",
        f"- Entries scanned: **{total}**",
        f"- Values converted mechanically: **{len(plan.converted)}**",
        f"- Dual-year pairs available via `--dual-year`: **{len(plan.dual)}**",
        f"- Values needing a human call: **{len(plan.residue)}**",
        f"- Skipped, already carrying the key: **{plan.skipped_existing}**",
        f"- Skipped, `living`/`unknown` (default-safe): **{len(plan.skipped_private)}** entries",
        "",
    ]
    by_class = collections.defaultdict(list)
    for rec, key, value, klass in plan.residue:
        by_class[klass].append((rec, key, value))
    for klass in ("absence", "place-leak", "dual-year", "unstructurable", "empty"):
        rows = by_class.get(klass)
        if not rows:
            continue
        lines += [f"## {klass} ({len(rows)})", "", CLASS_NOTE[klass], "",
                  "| file | id | name | key | value |", "|---|---|---|---|---|"]
        for rec, key, value in sorted(rows, key=lambda r: (r[0].source_file or "", r[0].id or "")):
            safe = str(value).replace("|", "\\|")
            lines.append(f"| {rec.source_file} | {rec.id} | {rec.name} | {key} | `{safe}` |")
        lines.append("")
    if plan.dual:
        lines += [f"## dual-year, mechanical ({len(plan.dual)})", "",
                  CLASS_NOTE["dual-year"], "",
                  "| file | id | name | key | original | proposed value | proposed phrase |",
                  "|---|---|---|---|---|---|---|"]
        for rec, key, src, value, phrase in sorted(plan.dual, key=lambda r: (r[0].source_file or "", r[0].id or "")):
            lines.append(f"| {rec.source_file} | {rec.id} | {rec.name} | {key} | "
                         f"`{src}` | `{value}` | `{phrase}` |")
        lines.append("")
    if plan.blocked_private:
        lines += [f"## blocked by the privacy screen ({len(plan.blocked_private)})", "",
                  "A `living`/`unknown` person whose value is DAY-PRECISE. The Spec 01 "
                  "rule applies per value even under `--include-living`; the date value "
                  "is deliberately NOT echoed here.", "",
                  "| file | id | key |", "|---|---|---|"]
        for rec, key, _v in plan.blocked_private:
            lines.append(f"| {rec.source_file} | {rec.id} | {key} |")
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Populate born/died from header prose (Spec 04).")
    ap.add_argument("--vault", help="Vault dir (default: $AUTORESEARCH_VAULT).")
    ap.add_argument("--apply", action="store_true", help="Write (default is dry run).")
    ap.add_argument("--file", help="Restrict to one Family_Tree file (batch-safe).")
    ap.add_argument("--include-living", action="store_true",
                    help="Also migrate living/unknown entries. The Spec 01 day-precision "
                         "screen still applies per value.")
    ap.add_argument("--dual-year", action="store_true",
                    help="Also apply the Old Style / New Style class, writing "
                         "born/born_phrase as a lossless pair (GEDCOM 7 App. A 6.2).")
    ap.add_argument("--residue", help="Write the triage worklist to this path.")
    ap.add_argument("--verify-headers", action="store_true",
                    help="With --apply: assert no bold-name header line changed.")
    ap.add_argument("--limit", type=int, help="Show at most N sample rows per section.")
    args = ap.parse_args()

    vault = vault_config.resolve_vault(args.vault)
    total = sum(1 for _ in ps.NarrativeBackend.iter_people(vault))
    plan = build_plan(vault, args.file, args.include_living, args.dual_year)

    n = args.limit or 12
    print(f"migrate_dates: {'APPLY' if args.apply else 'dry run'} on {vault}"
          + (f"  [{args.file}]" if args.file else ""))
    print(f"  entries scanned              : {total}")
    print(f"  values convertible           : {len(plan.converted)}")
    print(f"  dual-year pairs {'(applying)' if args.dual_year else '(use --dual-year)'} : {len(plan.dual)}")
    print(f"  residue (needs a human)      : {len(plan.residue)}")
    print(f"  skipped, key already present : {plan.skipped_existing}")
    print(f"  skipped, living/unknown      : {len(plan.skipped_private)} entries")
    if plan.blocked_private:
        print(f"  BLOCKED by the privacy screen: {len(plan.blocked_private)}")
    if plan.converted:
        print("\n  sample conversions:")
        for rec, key, old, new in plan.converted[:n]:
            print(f"    {rec.id} {key}: {old!r} -> {new!r}")
    if plan.residue:
        counts = collections.Counter(k for _, _, _, k in plan.residue)
        print("\n  residue by class: " + ", ".join(f"{k}={v}" for k, v in counts.most_common()))

    if args.residue:
        write_residue_report(args.residue, plan, vault, total)
        print(f"\n  residue worklist -> {args.residue}")

    if not args.apply:
        print("\n  (dry run — nothing written; re-run with --apply)")
        return 0

    before = header_lines(vault, args.file) if args.verify_headers else None
    written = apply_plan(vault, plan)
    print(f"\n  entries written: {written}")
    if before is not None:
        after = header_lines(vault, args.file)
        changed = [k for k in before if before[k] != after.get(k)]
        if changed or len(before) != len(after):
            print(f"  HEADER CHANGED ({len(changed)}) — this must never happen", file=sys.stderr)
            for k in changed[:10]:
                print(f"    {k[0]}:{k[1]}", file=sys.stderr)
            return 1
        print(f"  headers verified untouched: {len(before)} header lines byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
