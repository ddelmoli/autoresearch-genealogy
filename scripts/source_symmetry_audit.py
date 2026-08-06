#!/usr/bin/env python3
"""Two ADVISORY checks for sources the vault owns but has not applied.

Both come out of a sweep run on 06 AUG 2026 after three findings in one sitting
shared a shape: the answer was already inside something the vault had cited and
never opened. Three shapes turned out to be involved, and only these two are
mechanically detectable. The third (an entry asserting that a cited source does
NOT contain something, where the assertion is simply false) was measured and has
no detector: 138 raw matches, and reading them showed ordinary careful prose
about sources. It is recorded here so nobody rebuilds it.

    SPOUSE_ASYMMETRY       a marriage locator cited on one spouse and absent
                           from the other, so a shared event documents only half
                           the couple.
    DESCRIBED_NOT_NEGATED  a locator the entry's own prose calls non-evidence,
                           left without the `~` that would stop the census
                           counting it.

BOTH EMIT CANDIDATES, NEVER VERDICTS. Advisory, exit 0 always. Open every row
before acting on it; on the reference vault SPOUSE_ASYMMETRY ran roughly half
legitimate-opportunity rather than defect, and DESCRIBED_NOT_NEGATED ran 2
genuine out of 7.

** WHY PROSE MAY DRIVE DESCRIBED_NOT_NEGATED WHEN RULE 8 LIMB (g) REFUSED IT. **
Limb (g) considered making a bullet NAME load-bearing and did not take it,
because "it would make bullet TEXT a failure surface, where a typo silently
starts counting". That objection is about COUNTING: there, prose would have
decided the census, so a typo would move a number with nothing to catch it. Here
prose only RAISES A CANDIDATE for a human to read, and moves no count at all. A
typo in this module's markers loses a candidate; it can never credit or discredit
a record. Same posture as `dup_name_audit`, which is advisory for the same
reason.

** AND EVERY LOCATOR JUDGEMENT DELEGATES TO `harvest_sources`. ** The throwaway
script this module replaces used its own regex and promptly over-matched on
backticked tokens, reporting a defect on an entry the census reads as zero. That
is the standing two-readers-one-entry hazard: a screen that disagrees with the
tool it is screening for measures its own over-reach. `record_locators` honours
`~` negation and the is-this-really-a-locator test, so this module never decides
what a locator is. Delegating cut SPOUSE_ASYMMETRY from 53 rows to 33 on the
reference vault; the 20 that vanished were the screen's own over-reach.

** THE LIMIT OF DESCRIBED_NOT_NEGATED, MEASURED AND NOT DESIGNED AROUND. ** It
cannot tell "the non-evidence wording refers to THIS locator" from "this line
carries a caveat AND a real citation". Both remaining rows on the reference vault
are the second kind: one line rejects a user tree while citing a genuine census,
another negates a memorial while naming four real records as "hers". This repo
has already settled the general form of that problem in
`harvest_sources.sources_bullet_text`, where keying exclusion on words was
measured and REJECTED because "a line can hold a citation and a caveat at once".
The same is true here, which is exactly why this check is advisory and emits
candidates: it narrows a 7,000-locator corpus to a handful worth reading, and a
human decides. A non-zero reading is NOT a regression.
"""
import os
import re
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources  # noqa: E402
import person_store  # noqa: E402
import vault_config  # noqa: E402

VAULT = vault_config.resolve_vault_optional()

# A line is a MARRIAGE line for ranking purposes only. This never decides
# whether a locator counts; it decides whether a row is worth a human's time.
MARRIAGE_RE = re.compile(r"\bmarriage\b|\bmarried\b|\bm\.\s|\bwed\b|\bintention\b", re.I)

# Prose that says, in effect, "this locator is not evidence". Deliberately a
# small, literal list: a marker that fires too widely buries the real rows.
NON_EVIDENCE_RE = re.compile(
    r"earns? nothing"
    r"|not counted"
    r"|does not count"
    r"|is NOT a record"
    r"|are not records"
    r"|not independent evidence"
    r"|bibliographic"
    r"|compiled index"
    r"|off the ARK coverage metric",
    re.I,
)


def _locators(text):
    """Every real, non-negated record locator in `text`, per the census reader."""
    return set(harvest_sources.record_locators(text))


def collect(vault=None):
    """Return (blocks, spouses) keyed by vault id.

    blocks: id -> (display name, file, body text)
    spouses: id -> [spouse ids, '?' stripped]
    """
    vault = vault or VAULT
    blocks, spouses = {}, {}
    for rec, path, _hline, block in person_store.iter_entry_blocks(vault):
        if not rec.id:
            continue
        body = harvest_sources.truncate_at_break(block)
        blocks[rec.id] = (rec.name or "", os.path.basename(path), body)
        spouses[rec.id] = [str(s).strip().rstrip("?") for s in (rec.spouse or []) if s]
    return blocks, spouses


def spouse_asymmetry(blocks, spouses):
    """Marriage locators CITED by one spouse and not the other.

    ** SCOPED TO THE `Sources` BULLET, AND THAT IS A POSITION RULE, NOT A KEYWORD
    ONE (narrowed 06 AUG 2026 after the first 33 rows were worked). ** The first
    cut read every line of an entry, and 8 of the 15 rows it still reported were
    firing on NARRATIVE prose that merely contained a marriage word beside an
    unrelated locator: a baptism, a christening, an 1891 census, a write-back
    DETACH bullet, and a third party's certificate quoted as corroboration. None
    was a citation, so none could be propagated, and every one had to be declined
    by hand.

    Restricting to `sources_bullet_text` is the same fix `harvest_sources` itself
    adopted for deferred_decisions 19: "a line can hold a citation and a caveat at
    once, so exclusion must key on WHERE a citation sits, not on what words
    surround it." Measured: it removes all 8 prose rows and, against a control of
    the 11 propagations made that day, loses NONE.

    ** WHAT WAS CONSIDERED AND REJECTED, both on measurement. ** (1) Suppressing a
    pair once the lacking spouse holds ANY marriage locator, to kill the
    twice-married case: it dropped 0 rows, because those spouses hold no marriage
    record at all. (2) Suppressing when the record description names a DIFFERENT
    spouse: it dropped 13 of 15, but it is name matching, which this vault has
    already rejected for log backlinks, and it would have suppressed a true
    positive found the same day where the description read "his marriage to Ann
    Right" and the wife's entry is "Anna Wright".

    ** AND NO SUPPRESSION KEY WAS ADDED. ** An `adjudicated`-style marker was the
    obvious move and is wrong here: after this narrowing, most of what remains is
    either a real data defect (a third party's record cited as the holder's, which
    also over-credits the census) or a genuinely correct asymmetry on a
    twice-married person. A key would have memorialised check noise as settled
    work, and a declaration inherits the correctness of its reason."""
    marriage_locs = {}
    for pid, (_name, _fn, body) in blocks.items():
        found = set()
        for ln in harvest_sources.sources_bullet_text(body).splitlines():
            if MARRIAGE_RE.search(ln):
                found |= _locators(ln)
        marriage_locs[pid] = found

    out, seen = [], set()
    for pid, sps in spouses.items():
        for sp in sps:
            # A trailing `?` marks an edge as not yet FS-confirmed; it is still an
            # edge. Stripped here as well as in collect() so a caller passing raw
            # meta values gets the same answer as one passing collected ones.
            sp = str(sp).strip().rstrip("?")
            if sp not in blocks:
                continue
            key = tuple(sorted((pid, sp)))
            if key in seen:
                continue
            seen.add(key)
            a, b = marriage_locs.get(pid, set()), marriage_locs.get(sp, set())
            if a and not b:
                out.append((sp, pid, sorted(a)))
            elif b and not a:
                out.append((pid, sp, sorted(b)))
    return out


def described_not_negated(blocks):
    """Locators sitting on a line whose own prose calls them non-evidence."""
    out = []
    for pid, (_name, fn, body) in blocks.items():
        for i, ln in enumerate(body.splitlines(), 1):
            if not NON_EVIDENCE_RE.search(ln):
                continue
            bare = _locators(ln)
            if bare:
                out.append((pid, fn, i, sorted(bare), ln.strip()[:150]))
    return out


def main():
    argv = sys.argv[1:]
    vault = None
    if "--vault" in argv:
        vault = argv[argv.index("--vault") + 1]
    vault = vault_config.resolve_vault(vault) if vault else VAULT
    vault_config.require_vault(vault)

    blocks, spouses = collect(vault)
    asym = spouse_asymmetry(blocks, spouses)
    desc = described_not_negated(blocks)

    print(f"SPOUSE_ASYMMETRY: {len(asym)}  "
          f"(a marriage locator on one spouse, absent on the other)  [advisory; CANDIDATES]")
    by_file = defaultdict(int)
    for missing, holder, locs in asym:
        by_file[blocks[missing][1]] += 1
    for fn, c in sorted(by_file.items(), key=lambda kv: -kv[1]):
        print(f"  {c:>3}  {fn}")
    for missing, holder, locs in asym:
        mn, mf, _ = blocks[missing]
        hn = blocks[holder][0]
        print(f"    - {missing} {mn[:28]:30} lacks what {hn[:28]:30} cites: {', '.join(locs[:2])}")
    if asym:
        print("    NOTE: a marriage documents BOTH parties, so most of these are an "
              "uncited opportunity rather than an error. Cite it on both, or say why not.")

    print(f"\nDESCRIBED_NOT_NEGATED: {len(desc)}  "
          f"(prose calls the locator non-evidence; it is NOT `~`-negated, so the census counts it)"
          f"  [advisory; CANDIDATES]")
    for pid, fn, i, locs, text in desc:
        print(f"    - {pid} {blocks[pid][0][:26]:28} {fn}:{i}  {', '.join(locs[:2])}")
        print(f"        {text}")
    if desc:
        print("    FIX (only once you have READ the line): prefix the locator with `~`. "
              "An unmarked locator on the same line still counts, which is the point.")

    return 0  # advisory, always


if __name__ == "__main__":
    sys.exit(main())
