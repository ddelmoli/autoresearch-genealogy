#!/usr/bin/env python3
"""manifest_audit.py — does a generation heading still hold the people it names?

WHY IT EXISTS (Q340, raised 26 AUG 2026). The File Index table in `Family_Tree.md`
is the vault's map of which shard holds what, and NOTHING checked a row against its
own file. Two rows were found by hand, in one lineage, in one sitting, describing
families that had either left or never arrived.

⭐ THE MECHANISM, AND WHY THIS CHECK IS AIMED WHERE IT IS. A File Index row is
written from the file's SECTION HEADINGS, and **a split updates the row it creates,
never the row it empties**. Each split correctly appended its own "Gen 15-16 split
to X" note while the front half of the sentence went on naming families that had
gone. Four splits later the row was mostly false and every individual edit had been
correct. So the EMPTY HEADING is the upstream cause: it is what the stale row was
written from, and catching it catches the row before it is ever written.

WHAT COUNTS
  MANIFEST_EMPTY_HEADING   a `### Generation N` heading whose section holds no
                           person entry AND no wikilink pointer. Advisory.
  MANIFEST_GEN_RANGE       a File Index row whose every `Gen X-Y` claim disagrees
                           with the actual min/max `generation` of that file's
                           entries. Advisory, baseline 17.
  MANIFEST_SURNAME_ABSENT  a File Index row naming a family that IS a surname in
                           this vault but has no entry in the file the row
                           describes. Advisory, baseline 14. READ THE ROWS.

⭐ THE POINTER IS THE DISCRIMINATOR, AND IT IS STRUCTURAL. An emptied heading kept
deliberately as a signpost carries a pointer naming where the people went; a
`[[wikilink]]` in the section body IS that pointer, and testing for one separates
the two populations exactly. ⛔ Do NOT test for the word "moved" instead: the
vault writes the pointer at least four ways ("— MOVED" in the heading, "**Moved
<date>** to [[X]]", "EMPTY SINCE AN EARLIER SPLIT, kept as a pointer", "split to
[[X]]"), and a word match scored 17 pointered sections three different ways while
the wikilink test scored all 17 the same way. The wikilink tests what the
remediation actually requires — a destination a reader can follow — rather than the
sentence someone happened to write around it.

⚠ A FINDING IS NOT AUTOMATICALLY A DELETION, and the two kinds need OPPOSITE fixes:
  - **emptied by a split** -> add a pointer naming where the people went;
  - **a reservation for work never done** -> must NOT get a pointer, because
    "moved to X" would be false; either delete the heading or say what it reserves.
The discriminator between THOSE two is whether a person entry of that surname
exists anywhere in the vault, which is a judgement call this check does not make.
Read the rows.

⛔ WHAT IT CANNOT DO, SAID PLAINLY. It checks headings, not prose. The most
misleading clause found in the incident that raised Q340 was a row's claim to be
"the vault's single home" for a whole class of ancestry, which was false and is
unreachable by this check or any of Q340's other two. A green reading is NOT
"the File Index is true".

⭐⭐ CHECK 2 (`MANIFEST_GEN_RANGE`) HAS TWO RULES, AND BOTH WERE MEASURED BEFORE
BEING BELIEVED. Together they are the difference between 26 findings and 17, and
17 is the defensible number.

  1. **ACCEPT ANY CLAIMED RANGE THAT MATCHES, NOT THE FIRST ONE.** A row
     legitimately carries several ranges: its own, plus what it split away. Taking
     only the first claim reports **26**; requiring that NO claim matches reports
     **17**. The nine-row difference is entirely rows that state their current range
     after a historical one, and every one of those rows is correct.
  2. **ONLY A `Gen X-Y` RANGE IS A CLAIM.** A bare `Gen 8` in prose is a remark
     about a cluster's depth, not an assertion about the file's span. Treating a
     single mention as the range `8-8` adds **4** false rows (21 instead of 17) —
     it reads a claim into text that makes none.

⚠ The wikilink strip in `_range_claims` is DEFENSIVE, not load-bearing: measured
26 AUG 2026, the vault's shard filenames spell their spans `Gen15_16` with an
underscore, which the range pattern does not match anyway. It is kept because a
piped display form (`[[Family_Tree_X|Gen 15-16]]`) would otherwise inject another
file's span as a claim about this row — a file NAME is not a claim.

⚠ A row with NO range claim, or naming a file with no generation-bearing entries,
is SKIPPED rather than flagged; the report prints how many, because a check that
silently drops a third of its rows reads as coverage it does not have.

⭐⭐ CHECK 3 (`MANIFEST_SURNAME_ABSENT`) IS A LADDER, AND THE LADDER IS THE REPORT.
A bare "capitalised token absent from this file" rule yields **465** hits, almost all
places and structural vocabulary — an advisory nobody would read. Four filters cut it
to **14**, and `--ladder` prints every rung, because a single number here would hide
which rule is doing the work:

    465  absent from this file          (raw capitalised tokens)
     95  and is a surname in this vault
     44  and is not in a file this row LINKS to
     23  and is not a place in this vault
     14  and is not in the row's own file name

⚠ Each rung answers a false-positive source this question's spec NAMED, and each is
DATA-DRIVEN rather than a hand-tuned word list — that distinction is what keeps this
from being the "widen until it reads 0" trap. ⛔ Do NOT add a fifth rung: the residue
is known (below) and shrinking it further would mean encoding judgement as vocabulary.

⚠⚠ THE SPEC'S "SINGLE HIGHEST-VALUE RULE" DOES NOT HOLD FOR THIS VAULT. It expected
excluding tokens INSIDE `[[wikilinks]]` to remove most false positives on its own.
Measured: the dominant pointer dialect writes the family OUTSIDE the link — `Ashgrove
to [[Family_Tree_Region]]` — so that exclusion removes almost nothing. What
works is the SEMANTIC version: **if the surname is present in a file this row links
to, the row is correctly saying where the family went.** That is rung 2, and it is
worth 51 of the 95.

⚠ THE KNOWN RESIDUE, so nobody re-derives it: the medieval rows contribute a cluster
of DYNASTY and HOUSE labels (a kingdom or a house used as a lineage name, where the
entries themselves carry regnal names and no surname at all), and a bare-word
provenance clause ("split from X", with no wikilink) reads as a family claim. Both are
legitimate prose. ⛔ They are NOT to be filtered away — a house name in a row is
exactly the kind of claim a reader may want to check.

⭐ CHECKS 1 AND 3 CORROBORATE EACH OTHER, and did on their first run: the two empty
headings check 1 flags in one deep file are for the very families check 3 finds that
row naming. Two independent routes to one defect is the strongest signal here.

TIER 2, OFF BY DEFAULT (`--absent-everywhere`): tokens that are not a surname
ANYWHERE in the vault — the class covering "the row names a family the vault does not
hold", which is half of the incident that raised this question. **370 tokens, 144
distinct, overwhelmingly places and structural words.** It is a one-off review list,
NOT a gate, and it is deliberately excluded from the baseline.

SCOPE. Section extent follows the markdown nesting rule: a heading's section runs
to the next heading at the SAME OR SHALLOWER level, so a Generation heading whose
entries live under `####` subheadings is correctly seen as populated.

USAGE
  python3 scripts/manifest_audit.py               # full report
  python3 scripts/manifest_audit.py --pointered    # also list the resolved sections
  python3 scripts/manifest_audit.py --skipped      # rows check 2 could not judge
  python3 scripts/manifest_audit.py --ladder       # check 3's filter rungs
  python3 scripts/manifest_audit.py --absent-everywhere   # check 3 tier 2 (noisy)
  python3 scripts/manifest_audit.py --heartbeat    # one line for the banner
"""
from __future__ import annotations

import argparse
import glob as _glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import person_store  # noqa: E402
import shard_manifest  # noqa: E402
import vault_config  # noqa: E402

# Heading grammar: kept compatible with person_store's own `_GEN_HDR`, which is
# what decides a person's generation fallback. One grammar, one meaning.
GEN_HEADING_RE = re.compile(r"^(#{1,6})\s+Generation\s+(\d+)", re.I)
ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
# A RANGE claim only. `Gen 13-14`, `Generations 0 through 3`, `Gen 20 to 25`.
# ⛔ Deliberately does NOT match a bare `Gen 8` — see rule 2 in the module docstring.
NAME_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019-]+")
# A surname-shaped token in row prose: capitalised, 3+ letters. Deliberately broad —
# the narrowing is the LADDER in scan_surname_absent, not this pattern.
ROW_TOKEN_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
# The place half of a header vitals parenthetical: everything after a comma.
HEADER_PLACE_RE = re.compile(r",\s*([A-Z][a-zA-Z'\u2019-]+(?:\s+[A-Z][a-zA-Z'\u2019-]+)*)")
WIKILINK_TARGET_RE = re.compile(r"\[\[([^\]|]+)")
GEN_RANGE_RE = re.compile(
    r"\bGen(?:eration)?s?\s*\.?\s*(\d{1,2})\s*(?:-|\u2013|\u2014|\bto\b|\bthrough\b)\s*(\d{1,2})\b",
    re.I)


def scan(vault):
    """Yield one dict per Generation heading that holds no person entry.

    Entry positions come from `person_store.iter_entry_blocks` — the sanctioned
    reader. ⛔ Never re-derive them from a bold-name pattern here: a sanctioned
    body bullet (`- **Sources**`, `- **Prior work**`) is indistinguishable from an
    entry header under a naive rule, and a hand-rolled chunker does not fail
    quietly, it MISFILES.
    """
    entry_lines = defaultdict(list)
    for _rec, path, hline, _block in person_store.iter_entry_blocks(vault):
        entry_lines[path].append(hline)

    rows = []
    for path in sorted(_glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        headings = [(i, len(m.group(1)))
                    for i, ln in enumerate(lines)
                    for m in [ANY_HEADING_RE.match(ln)] if m]
        here = entry_lines.get(path, [])
        for idx, (i, level) in enumerate(headings):
            if not GEN_HEADING_RE.match(lines[i]):
                continue
            # Section runs to the next heading at the same or a shallower level.
            end = len(lines)
            for j, other_level in headings[idx + 1:]:
                if other_level <= level:
                    end = j
                    break
            if any(i < e < end for e in here):
                continue
            body = "\n".join(lines[i + 1:end])
            rows.append({
                "file": os.path.basename(path),
                "line": i + 1,
                "heading": lines[i].strip(),
                "pointered": bool(WIKILINK_RE.search(body)),
            })
    return rows


def _range_claims(row_text):
    """Every `Gen X-Y` range asserted in a File Index row, in order of appearance."""
    return [(int(a), int(b))
            for a, b in GEN_RANGE_RE.findall(WIKILINK_RE.sub(" ", row_text))]


def actual_spans(vault):
    """{basename.md: (min_generation, max_generation)} from the person records.

    ⛔ Never a text scrape of the `### Generation N` headings: `generation` is the
    per-person source of truth and a heading is only its display. Reading the
    headings here would compare the File Index against the very layer check 1 exists
    because it drifts.
    """
    gens = defaultdict(list)
    for rec in person_store.iter_people(vault):
        if rec.generation is not None and rec.source_file:
            gens[os.path.basename(rec.source_file)].append(rec.generation)
    return {f: (min(g), max(g)) for f, g in gens.items()}


def scan_gen_range(vault):
    """Yield one dict per File Index row: its claims, the file's real span, verdict.

    Verdicts: 'ok' (some claim matches), 'mismatch' (claims exist, none matches),
    'no_claim' / 'no_entries' (not judgeable — counted, never flagged).
    """
    spans = actual_spans(vault)
    path = os.path.join(vault, "Family_Tree.md")
    if not os.path.exists(path):
        return []
    rows = []
    for line in open(path, encoding="utf-8"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        # Reuse the manifest loader's own File-cell normaliser: wikilinks, backticks,
        # markdown links and a trailing `.md` all reduce to a bare shard basename.
        name = shard_manifest._normalize_file(cells[0])
        if not name.startswith(shard_manifest.TREE_PREFIX):
            continue
        actual = spans.get(name + ".md")
        claims = _range_claims(line)
        if actual is None:
            verdict = "no_entries"
        elif not claims:
            verdict = "no_claim"
        elif any(c == actual for c in claims):
            verdict = "ok"
        else:
            verdict = "mismatch"
        rows.append({"file": name, "claims": claims, "actual": actual,
                     "verdict": verdict})
    return rows


def _name_index(vault):
    """Three vocabularies, all read from the person records themselves.

    Returns (per_file, surnames, places):
      per_file  {basename.md: {every name token, lowercased}}
      surnames  {the LAST name token of every entry}  — "is this a family here?"
      places    {tokens from the place half of header vitals} — the collision set,
                because a toponymic surname and a place look identical in prose
                (this vault's medieval lines are full of both).

    ⛔ Never a text grep of the shard: a prose MENTION is not presence, the same
    self-crediting trap as a bare ARK counting itself. Presence means an ENTRY.
    """
    per_file = defaultdict(set)
    surnames, places = set(), set()
    for rec in person_store.iter_people(vault):
        if not rec.name or not rec.source_file:
            continue
        toks = NAME_TOKEN_RE.findall(rec.name)
        if not toks:
            continue
        per_file[os.path.basename(rec.source_file)].update(w.lower() for w in toks)
        surnames.add(toks[-1].lower())
        for chunk in HEADER_PLACE_RE.findall((rec.raw or {}).get("header_paren") or ""):
            places.update(w.lower() for w in NAME_TOKEN_RE.findall(chunk))
    return per_file, surnames, places


def scan_surname_absent(vault, tier2=False):
    """Yield findings plus the ladder tally. Returns (rows, ladder).

    Each rung is a false-positive source this question's spec named; see the module
    docstring for why the ladder is printed rather than just its last rung.
    """
    per_file, surnames, places = _name_index(vault)
    path = os.path.join(vault, "Family_Tree.md")
    ladder = defaultdict(int)
    out = []
    if not os.path.exists(path):
        return out, ladder
    for line in open(path, encoding="utf-8"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = shard_manifest._normalize_file(cells[0])
        if not name.startswith(shard_manifest.TREE_PREFIX):
            continue
        here = per_file.get(name + ".md")
        if not here:
            continue
        content = "|".join(cells[2:])
        linked = [shard_manifest._normalize_file(x) + ".md"
                  for x in WIKILINK_TARGET_RE.findall(content)]
        own = {w.lower() for w in re.findall(r"[A-Za-z]+", name)}
        for tok in sorted(set(ROW_TOKEN_RE.findall(WIKILINK_RE.sub(" ", content)))):
            low = tok.lower()
            if low in here:
                continue
            ladder["1 absent from this file"] += 1
            is_surname = low in surnames
            if tier2 and not is_surname:
                out.append({"file": name, "token": tok, "tier": 2})
            if not is_surname:
                continue
            ladder["2 is a surname in this vault"] += 1
            # The row LINKS to a file that holds them: it is correctly saying where
            # the family went. This is the pointer rule that actually works here.
            if any(low in per_file.get(dest, set()) for dest in linked):
                continue
            ladder["3 not in a file this row links to"] += 1
            if low in places:
                continue
            ladder["4 not a place in this vault"] += 1
            if low in own:
                continue
            ladder["5 not in the row's own file name"] += 1
            out.append({"file": name, "token": tok, "tier": 1})
    return out, ladder


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--skipped", action="store_true",
                    help="list the File Index rows check 2 could NOT judge (no range "
                         "claim, or a file with no generation-bearing entries)")
    ap.add_argument("--ladder", action="store_true",
                    help="print check 3's filter rungs — which rule removed what")
    ap.add_argument("--absent-everywhere", action="store_true",
                    help="check 3 TIER 2: tokens that are not a surname anywhere in "
                         "the vault. A review list, not a gate; mostly places.")
    ap.add_argument("--pointered", action="store_true",
                    help="also list the sections that ARE pointered — the resolved "
                         "population, shown so a reader can check the discrimination "
                         "rather than take the count on trust")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    rows = scan(vault)
    findings = [r for r in rows if not r["pointered"]]
    pointered = [r for r in rows if r["pointered"]]

    if a.heartbeat:
        nfiles = len({r["file"] for r in findings})
        extra = (f" across {nfiles} file(s); {len(pointered)} more are empty but "
                 f"POINTERED (resolved)" if findings else "")
        gr = scan_gen_range(vault)
        bad = sum(1 for r in gr if r["verdict"] == "mismatch")
        unjudged = sum(1 for r in gr if r["verdict"] in ("no_claim", "no_entries"))
        sa, _ladder = scan_surname_absent(vault)
        print(f"MANIFEST_EMPTY_HEADING: {len(findings)}  [advisory]{extra}; "
              f"MANIFEST_GEN_RANGE: {bad}  [advisory; baseline 17] "
              f"({unjudged} of {len(gr)} row(s) not judgeable); "
              f"MANIFEST_SURNAME_ABSENT: {len(sa)}  [advisory; baseline 14; READ THE ROWS]")
        return 0

    print("=== MANIFEST_EMPTY_HEADING — a generation heading with no entries "
          "and no pointer (advisory) ===")
    print("  A finding is NOT automatically a deletion: an emptied-by-a-split")
    print("  heading wants a pointer; a reservation for work never done must NOT")
    print("  get one. Read the row before fixing it.\n")
    for r in findings:
        print(f"  {r['file']}:{r['line']}")
        print(f"      {r['heading'][:96]}")
    if a.pointered:
        print(f"\n  --- empty but POINTERED ({len(pointered)}), not findings ---")
        for r in pointered:
            print(f"  {r['file']}:{r['line']}  {r['heading'][:80]}")
    print(f"\nMANIFEST_EMPTY_HEADING: {len(findings)}  [advisory]"
          f"   (+{len(pointered)} empty but pointered)")

    gr = scan_gen_range(vault)
    bad = [r for r in gr if r["verdict"] == "mismatch"]
    unjudged = [r for r in gr if r["verdict"] in ("no_claim", "no_entries")]
    print("\n=== MANIFEST_GEN_RANGE — a File Index row whose every Gen claim "
          "disagrees with its file (advisory) ===")
    print("  A row may state several ranges (its own, plus what it split away);")
    print("  ANY match clears it. Only a `Gen X-Y` RANGE counts as a claim.\n")
    for r in bad:
        claims = ", ".join(f"{x}-{y}" for x, y in r["claims"])
        print(f"  {r['file']}")
        print(f"      file holds Gen {r['actual'][0]}-{r['actual'][1]}; row claims {claims}")
    if not bad:
        print("  (none)")
    if a.skipped:
        print(f"\n  --- not judgeable ({len(unjudged)}) ---")
        for r in unjudged:
            why = "no Gen X-Y range claim" if r["verdict"] == "no_claim" \
                else "file has no generation-bearing entries"
            print(f"  {r['file']:56} {why}")
    print(f"\nMANIFEST_GEN_RANGE: {len(bad)}  [advisory; baseline 17]"
          f"   ({len(unjudged)} of {len(gr)} row(s) not judgeable"
          + ("" if a.skipped else "; --skipped to list them") + ")")

    sa, ladder = scan_surname_absent(vault, tier2=a.absent_everywhere)
    t1 = [r for r in sa if r["tier"] == 1]
    t2 = [r for r in sa if r["tier"] == 2]
    print("\n=== MANIFEST_SURNAME_ABSENT — a row names a family with no entry in "
          "that file (advisory) ===")
    print("  CANDIDATES, NOT VERDICTS. A house or dynasty label and a bare-word")
    print("  provenance clause both read as a family claim and are legitimate prose.\n")
    for r in t1:
        print(f"  {r['file']:52} {r['token']}")
    if not t1:
        print("  (none)")
    if a.ladder:
        print("\n  --- the ladder (each rung is a named false-positive source) ---")
        for rung in sorted(ladder):
            print(f"      {ladder[rung]:5}  {rung}")
    if a.absent_everywhere:
        print(f"\n  --- TIER 2 ({len(t2)}): not a surname anywhere in the vault. A")
        print("      review list, NOT a gate, and not in the baseline. Mostly places ---")
        seen = defaultdict(list)
        for r in t2:
            seen[r["token"]].append(r["file"])
        for tok in sorted(seen):
            print(f"      {tok:24} x{len(seen[tok])}")
    print(f"\nMANIFEST_SURNAME_ABSENT: {len(t1)}  [advisory; baseline 14]"
          + ("" if a.ladder else "   (--ladder for the filter rungs)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
