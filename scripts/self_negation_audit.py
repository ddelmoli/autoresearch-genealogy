#!/usr/bin/env python3
"""Gate: SELF_NEGATION -- an entry whose own `~` cancels its own citation.

`~` negation is scoped to the ENTRY, not to the line it is written on. So a locator
quoted with a `~` in an audit note, a retraction bullet, or an exclusion list will
suppress the SAME token where the entry cites it properly, several bullets away. The
prose and the census then say opposite things, and the census wins.

    - **Sources** ...
      - her birth, 18 MAR 1691 -- fs:1:1:AAAA-BBB      <- the citation
    - AUDITED ...: her birth is indexed twice -- ~fs:1:1:AAAA-BBB   <- kills it

⭐ WHAT IT IS FOR, measured on the reference vault (Open_Questions Q305, 20 AUG 2026).
The first run returned SEVEN entries. One read SOURCE_GAP / 0 ARKs while citing a birth
AND a marriage; another had its subject's own death-register entry -- the record naming
his parents -- filed into a bullet listing "children's DEATHS, all POSTDATING his own
death", where one misfiled line suppressed the best record on the entry.

⛔⛔ FINDINGS RESOLVE IN BOTH DIRECTIONS. NEVER FIX THESE IN BULK. Of those seven, TWO were
suppressed real records (the `~` was wrong, and the fix is to remove the locator from the
prose that mentions it) and FIVE were latent over-credits (the `~` was RIGHT and a stale
duplicate `- **Sources**` bullet was re-citing an excluded memorial, obituary, or
limb-(g) record). A mechanical pass in either direction would have made half the batch
worse. Read the entry; decide per row.

   the `~` is WRONG  -> MIGRATE the prose mention: drop the locator from the discussion,
                        which never needed it, and leave the citation standing.
   the `~` is RIGHT  -> the Sources copy is the error: remove the duplicate claim.
   ⛔ never          -> negate the Sources copy. That destroys the citation, which is
                        the ordinary outcome when an entry quotes its own best record.

⚠ ALWAYS DIFF THE CENSUS BY ROW AFTER A FIX (`census_diff.py`). Negation is
non-monotonic: removing a `~` can move a count either way, and no other gate sees any of
this. Every instance found so far was invisible to integrity, prose_audit,
entry_boundary, bare_ark and entry_attribution alike.

⛔ KNOWN BLIND SPOT, STATED SO A ZERO HERE IS NOT MISREAD. This finds a CLASH -- a token
negated somewhere and cited un-negated in a `- **Sources**` bullet. Where the analysis was
never written and only the stale bullet survives, there is no clash and the entry looks
clean while being wrong. Two such rows were found by READING in the same sitting: both
spouses credited for a cluster of death acts that postdate them. A clean run here is not
a statement that an entry's citations are correct.

⛔ "ONE `- **Sources**` BULLET PER ENTRY" IS NOT THE INVARIANT, and was measured and
rejected as one: of 44 entries carrying more than one bullet, only 3 shared any locator
between them. Two disjoint Sources bullets are usually legitimate (an apparatus bullet
beside a records bullet, most often on medieval entries). The signal is duplicated
LOCATORS, not duplicated bullets.

WHY THERE IS NO `--changed-only` MODE, deliberately, unlike header_audit/bare_ark_audit.
Those gates judge LINES, and a line is either added by this commit or it is not. This
defect is a relationship BETWEEN two lines that are usually far apart and usually not
touched together: a commit that adds one `~` on line 5 breaks a citation on line 90 it
never edited. A changed-only view would grade the new line, find it well-formed, and miss
the interaction the gate exists to catch. The whole-entry scan is the only sound scope.

    python3 scripts/self_negation_audit.py            # advisory report
    python3 scripts/self_negation_audit.py --strict   # exit 1 on any finding
"""
import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as H
import vault_config


def findings(vault=None):
    """[(file, vault_id, display_name, [(token, tier)])] -- one row per entry.

    The comparison uses ONLY documented public helpers, because a hand-rolled locator
    regex is the recurring way this module gets re-broken: `record_locators` already
    honours `~`, strips trailing markdown (Q274), and rejects a bare locator FORM. It
    also resolves negation across SPELLINGS, which a naive `~fs:` regex cannot see and
    which is how the first hand-rolled version of this check returned a false zero:
    `~fs:1:1:X`, `~1:1:X` and `~ark:/61903/1:1:X` all cancel a cited `fs:1:1:X`.

    ⚠ ONE SPELLING DOES NOT, AND IT IS THE ONE THAT LOOKS LIKE IT SHOULD. A bare
    `~AAAA-BBB` -- a PID with no namespace at all -- does NOT cancel `fs:1:1:AAAA-BBB`;
    the `~` attaches to the token AS WRITTEN, which is the same asymmetry `bare_ark_audit`
    exists for. Pinned in `test_self_negation.py` so nobody "fixes" it into a claim the
    counter does not make.

      survives   -- tokens still citing after negation is resolved over the WHOLE body,
                    which is the scope `~` actually has and the number the census uses.
      claimed    -- tokens the `- **Sources**` bullet(s) assert, with negation resolved
                    over that bullet text ALONE.

    A token in `claimed` but not in `survives` is asserted as a citation and cancelled by
    a `~` written somewhere else in the same entry.

    ⭐⭐ TWO TIERS, BECAUSE THE CENSUS COUNTS RECORDS AND NOT TOKENS. A sub-bullet may
    legitimately carry several locators for ONE record -- an index ARK beside its register
    image, or the same document on two hosts -- and negating one of them to stop the
    record being counted twice is CORRECT, deliberate de-duplication. Nothing is lost so
    long as a sibling locator on that same sub-bullet still cites.

      LOST   no surviving locator on the token's own sub-bullet -> a citation really is
             destroyed, and this is the tier that matters.
      DEDUP  a sibling on the same sub-bullet survives -> one record, one count, no loss.

    Reported separately rather than filtered away: DEDUP rows are the population where a
    later edit to the surviving sibling would silently turn the whole record into a LOST
    row, and a reader should be able to see them.
    """
    out = []
    for path, entries in H.entry_blocks_with_ids(vault).items():
        for vid, name, _hline, body in entries:
            src = H.sources_bullet_text(body)
            claimed = set(H.record_locators(src))
            if not claimed:
                continue
            survives = set(H.record_locators(body))
            cancelled = claimed - survives
            if not cancelled:
                continue
            # A sub-bullet is one RECORD (Spec 03 grammar), so judge loss per line.
            rows = []
            for tok in sorted(cancelled):
                tier = "LOST"
                for ln in src.splitlines():
                    if tok not in ln:
                        continue
                    # ⚠ The sibling must SURVIVE, not merely be present. The first cut
                    # tested presence and reported DEDUP for a sub-bullet whose locators
                    # were ALL cancelled -- i.e. it called a wholly destroyed record
                    # "no loss", which is the exact failure this gate exists to prevent.
                    if any(sib != tok and sib in survives for sib in H.record_locators(ln)):
                        tier = "DEDUP"
                    break
                rows.append((tok, tier))
            out.append((os.path.basename(path), vid, name, rows))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", help="vault path (default: resolved as usual)")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any LOST citation (baseline is 0)")
    ap.add_argument("--all", action="store_true",
                    help="list DEDUP rows too, not just LOST ones")
    a = ap.parse_args()

    vault = vault_config.resolve_vault(a.vault)
    rows = findings(vault)

    lost_rows = [r for r in rows if any(t == "LOST" for _, t in r[3])]
    n_lost = sum(1 for r in rows for _, t in r[3] if t == "LOST")
    n_dedup = sum(1 for r in rows for _, t in r[3] if t == "DEDUP")

    print("=== SELF_NEGATION — an entry's own `~` cancels its own citation ===")
    for fn, vid, name, cancelled in sorted(rows):
        if not a.all and not any(t == "LOST" for _, t in cancelled):
            continue
        print(f"  {fn}  {vid}  {name[:44]}")
        for tok, tier in cancelled:
            print(f"      [{tier:<5}] {tok}")
    print()
    print(f"SELF_NEGATION: {n_lost} LOST citation(s) across {len(lost_rows)} entr(ies)  "
          f"[{'BLOCKING' if a.strict else 'advisory'}; baseline 0]")
    print(f"               {n_dedup} DEDUP token(s) — a sibling locator on the same "
          f"sub-bullet still cites, so the RECORD is counted and nothing is lost"
          f"{'' if a.all else '  (--all to list)'}")
    if lost_rows:
        print("  ⚠ CANDIDATES, NOT FINDINGS — these resolve in BOTH directions. Read each entry:")
        print("      the `~` is WRONG -> migrate the prose mention, keep the citation.")
        print("      the `~` is RIGHT -> the Sources copy is a stale duplicate; remove the claim.")
        print("    ⛔ Never negate the Sources copy. ⚠ Diff the census BY ROW after every fix:")
        print("      python3 scripts/census_diff.py --since HEAD")
    return 1 if (n_lost and a.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
