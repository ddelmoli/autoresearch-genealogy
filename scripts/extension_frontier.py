#!/usr/bin/env python3
"""extension_frontier.py — who is the tree NOT extended above, and is that on purpose?

WHY IT EXISTS. Line-extension work in this vault has always been organised by
CHAIN: pick a named line (Capetian, Rurikid, Carolingian, Dunkeld/Alpin, Leinster),
walk it up until it hits a documented terminus, stop. That is a good way to extend a
line and a bad way to notice a line you never started. A person added as a
completeness leaf — most often a WIFE added by a "wives pass" — is never the head of
a chain, so no later pass ever treats them as a frontier.

The concrete failure this was written for (22 JUL 2026): **Hedwig of Saxony** sat at
Gen 37 as the mother of Hugh Capet with NO parents edge, and the omission survived
several extension passes. Her parentage was neither unknown nor contested — Cawley
gives it, FamilySearch carries it, and the operator found it in one click on
Wikipedia. The vault simply had no report that asked "who has no parents?".

WHAT IT REPORTS. Every person with NO `parents` edge, split by whether the entry
says WHY:

  DECLARED   the prose gives a reason — terminus, unknown parentage, legendary,
             ceiling, explicitly speculative. Not work; a recorded decision.
  SILENT     no parents edge and no stated reason. THIS IS THE WORKLIST. Each one
             is either a real extension opportunity or a missing terminus note, and
             you cannot tell which without looking — which is the point.

A SILENT row is not an accusation that the parents are known. It says the vault has
not recorded either the parents or a reason there are none. Both outcomes are
progress: extend the line, or write the terminus down so it stops appearing here.

Rows are ranked by generation ascending (shallower = closer to the subject = cheaper
to verify and more likely to matter), then by evidence tier.

USAGE
  python3 scripts/extension_frontier.py                  # SILENT rows, all gens
  python3 scripts/extension_frontier.py --gen-min 29     # deep medieval only
  python3 scripts/extension_frontier.py --all            # DECLARED rows too
  python3 scripts/extension_frontier.py --csv
  python3 scripts/extension_frontier.py --summary        # counts only
  python3 scripts/extension_frontier.py --heartbeat      # one line, SessionStart banner

THE STANDING GOAL: DRIVE SILENT TO ZERO. Not "give everyone parents" — that is not
in anyone's power — but leave no parentless person whose entry is SILENT about why.
Every row exits one of two ways: it gains PARENTS, or it gains a written REASON. The
target is reported in the SessionStart banner every session so it stays a standing
objective rather than something each session has to rediscover.

⚠ THE CHEAP WIN TO REFUSE: closing rows by writing "parentage unknown" without
consulting anything. That zeroes the metric and destroys its meaning in one pass. A
declaration must say what was checked and, where possible, name the onward route.
`--heartbeat` therefore also counts DECLARED rows whose entry cites NO source and NO
route, and flags them for review — an advisory proxy, since no regex can judge
whether the reasoning was any good, only whether any was offered.

Advisory. Never blocks a commit: a silent frontier is a research to-do, not a defect.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_person_index as g  # noqa: E402
import vault_config  # noqa: E402

PARENTS_RE = re.compile(r"parents:\s*'\[")
SPOUSE_RE = re.compile(r"spouse:\s*'\[")
TIER_RE = re.compile(r"evidence_tier:\s*(\w+)")
LIVING_RE = re.compile(r"life_status:\s*(living|unknown)")

# A reason to have no parents.
#
# ** THERE ARE NO "EFFORT" STOPS (operator ruling, 07 AUG 2026). **
# A DECLARED row means the ANCESTRY stops here on some authority. It does NOT mean
# nobody has got round to it. Those are opposite states and the vault had been
# recording them in the same field:
#   - a TERMINUS is about ANCESTRY -- no cited authority carries the line further;
#   - a STOP is about EFFORT -- the work is simply undone.
# The second is a research to-do, which is precisely what SILENT is for. So the
# alternation that used to match "NOT WORKED", "not yet worked", "deliberate stop",
# "NOT EXTENDED" and "do NOT adopt/extend/wire" was REMOVED. Measured at the ruling:
# 39 of 327 declared rows rested on that language ALONE and became SILENT.
#
# This also reverses the note that used to sit here, which reasoned that "a false
# DECLARED is cheaper than a false SILENT". It is not. A false SILENT nags; a false
# DECLARED **removes a real row from the EXPAND pool permanently and silently**, and
# nothing ever re-examines it. Two were minted by accident in one sitting (see
# `deferred_decisions` 55) -- one of them by a bullet reading "Bank, do not wire
# from the tree", a statement about METHOD that closed a frontier row.
# ⭐⭐ **FREE-TEXT MATCHING WAS RETIRED 08 AUG 2026 (operator ruling, deferred 55
# option 1). THE EXPLICIT MARKER IS NOW THE ONLY THING THAT DECLARES A FRONTIER ROW.**
#
# The alternation that used to live here matched ancestry phrases -- `terminus`,
# `parentage unknown`, `no parents recorded`, `legendary`, `fabricat`, `origin
# unknown`, `reliability ceiling`. Measured before the change: of 264 declared rows,
# **195 (74%) already carried the explicit marker and only 69 rested on free text.**
# Of those 69, **26 hit an unambiguous ancestry phrase and were STAMPED with the
# marker** (their reasons preserved verbatim in-entry), and **44 rested only on the
# genuinely ambiguous phrases and correctly fell back to SILENT.**
#
# WHY THE PHRASES HAD TO GO, and it is not the ambiguity everyone expected:
#   (a) The known problem -- "her parentage is unknown" is written both about a
#       CLOSED question and an OPEN one, and no regex separates them. The 44
#       fallbacks are dominated by "No parents recorded in FamilySearch", which is a
#       statement about ONE HOST, not about the ancestry. Under the no-effort-stops
#       ruling those are research to-dos, i.e. exactly what SILENT is for.
#   (b) ⚡ The decisive one, found the same day: **the detector could not tell an
#       ASSERTION from a DENIAL.** A session wrote "a documented negative on FS is
#       not a <the marker>" onto six entries -- spelling the phrase out IN ORDER TO
#       SAY THE ROW WAS NOT ONE -- and minted **five accidental closures**
#       (SILENT 301 -> 296). No wording rule could have prevented that: the sentence
#       was already unambiguous to any human reader.
#
# ⚠ A false DECLARED is the EXPENSIVE error -- it removes a real row from the EXPAND
# pool permanently and silently, and nothing re-examines it. A false SILENT merely
# nags. That asymmetry is why this check is now deliberately hard to satisfy.
#
# ⚠ TO DECLARE A ROW, WRITE THE MARKER. There is no longer any other way, by design.
# ⚠ CASE-INSENSITIVE, deliberately. The reader must be tolerant of what is already
# written -- the same rule the FS write-back grammar states in CLAUDE.method.md
# ("match case-insensitively ... count on the words, never on the decoration").
# A declaration must not fail because someone typed it in sentence case.
DECLARED_RE = re.compile(r"FRONTIER DECLARATION", re.I)


# A declaration is only worth the SILENT row it closes if it says WHY on some
# authority. "Parentage unknown" written after looking at Cawley is a research
# result; the same words written after looking at nothing are a way to make the
# worklist shorter without doing any work — and the vault has learned repeatedly
# that a number moving in the flattering direction deserves the most scrutiny.
# BACKED_RE is the cheap mechanical proxy: does the DECLARATION name a source, an
# authority, or an explicit onward route? It is advisory and deliberately broad —
# it cannot judge whether the reasoning is good, only whether any was offered.
#
# ⚠⚠ **IT IS MATCHED AGAINST THE DECLARING BULLET, NOT THE WHOLE ENTRY** (fixed
# 07 AUG 2026). It used to scan the entire body, which asks a different question —
# "does this entry mention any source anywhere?" — and on a long entry the answer is
# always yes. Measured at the fix: **entry-scope reported 0 unbacked declarations;
# bullet-scope reports 21.** The advisory was printing all-clear over 21 declarations
# that name nothing, which is the exact "flattering direction" the note above warns
# about — in its own implementation.
#
# ⚠ `not yet worked` / `NOT WORKED` remain here deliberately, even though they no
# longer DECLARE (the "no effort stops" ruling): if such a phrase still appears beside
# a real ancestry claim, it is evidence that *something* was offered, and this regex
# only ever asks whether a reason was given.
BACKED_RE = re.compile(
    r"Cawley|Medlands|\bFMG\b|Richardson|Complete Peerage|ODNB|Henry Project|\bWeis\b"
    r"|Visitation|Muskett|History of Parliament|\bVCH\b|British History Online"
    r"|Macnamara|Clutterbuck|\bIPM\b|inquisition|charter|register|probate|\bwill\b"
    r"|FamilySearch|\bFS\b|WikiTree|Primary Chronicle|annal|NEHGR|Savage|Torrey"
    # ⚠ The list above was ANGLO-MEDIEVAL and did not know the authorities this vault
    # actually leans on outside that world (added 08 AUG 2026, working the 21 unbacked
    # rows). Eight declarations named a real work and still read as "cites no source":
    # Copinger's *Manors of Suffolk* (3 rows), Otis's *Barnstable Families*, *History of
    # North Bridgewater*, a Cagnano **tavola alfabetica**, and a **Geneteka** index row.
    # A backing check that only recognises Cawley will always report the non-medieval
    # half of a vault as unbacked, which is a defect in the CHECK, not in the entries.
    r"|Copinger|Otis|Barnstable Families|North Bridgewater|Davy MSS"
    r"|Geneteka|Antenati|metryki|ScotlandsPeople|tavola alfabetica|town records"
    r"|Vital Records"
    # `route` in ANY form: the vault's own word for "here is where to look next", which
    # is exactly the third thing this check accepts. `[Rr]oute:` only matched the colon
    # form and missed "⏭ **Routes**:" and "the route is ...".
    r"|\broutes?\b|not yet worked|NOT WORKED|re-read|read directly",
    re.I,
)


def declaring_lines(body):
    """The bullet(s) that actually carry the declaration.

    Scoping `backed` to these is the difference between asking "does this DECLARATION
    say why" and "does this ENTRY mention a source anywhere". Blockquoted lines are
    excluded: `route_digest` mirrors entry text at the head of every lineage file, so
    counting them would credit a declaration to every person in the shard.
    """
    return [l for l in body.split("\n")
            if not l.lstrip().startswith(">") and DECLARED_RE.search(l)]


def rows_with_bodies(vault):
    """Person records joined to their FULL narrative block (not just the meta line).

    parse_narrative()'s `block` is the meta line; the reason a person has no parents
    is written in the surrounding prose, so the body comes from the model-agnostic
    `person_store` seam (24 JUL 2026 — this replaced a shape-based chunker keyed on
    `line.startswith("**")`. Canonical entries written as `- **Name**` BULLETS, the
    dominant style in the deep-royal shards, never start a chunk under that rule, so
    their prose — including an existing terminus declaration — was invisible and only
    the first meta id per chunk got a body at all. Measured on the reference vault:
    Crínán of Dunkeld carried a full TERMINUS bullet, recorded the previous day, and
    still reported SILENT. Same parser-drift family the census retired in
    spec/entry-boundary Spec 05; the seam is the one reader that knows what an entry
    is.)
    """
    import person_store as PS
    bodies = {}
    for rec, _path, _hline, block in PS.iter_entry_blocks(vault):
        if rec.id:
            text = block if isinstance(block, str) else "\n".join(block)
            # Same PID/id can appear on >1 block only pathologically; keep the longest.
            if rec.id not in bodies or len(text) > len(bodies[rec.id]):
                bodies[rec.id] = text
    out = []
    for p in g.parse_narrative():
        pid = p.get("id")
        body = bodies.get(pid, p.get("block") or "")
        meta = p.get("block") or ""
        if PARENTS_RE.search(meta):
            continue
        if LIVING_RE.search(meta):
            continue  # living/unknown are privacy-excluded from research anyway
        tier = TIER_RE.search(meta)
        out.append({
            "id": pid,
            "name": p.get("name") or "?",
            "gen": p.get("gen"),
            "file": p.get("file") or "?",
            "tier": tier.group(1) if tier else "",
            "spouse": bool(SPOUSE_RE.search(meta)),
            "declared": bool(DECLARED_RE.search(body)),
            # scoped to the declaring bullet, not the whole body -- see BACKED_RE
            "backed": any(BACKED_RE.search(l) for l in declaring_lines(body)),
        })
    return out


TIER_ORDER = {"strong_signal": 0, "moderate_signal": 1, "speculative": 2, "": 3}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--gen-min", type=int)
    ap.add_argument("--gen-max", type=int)
    ap.add_argument("--all", action="store_true", help="include DECLARED rows")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--heartbeat", action="store_true",
                    help="one-line SILENT/DECLARED status for the SessionStart audit suite")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    rows = rows_with_bodies(vault)
    if a.gen_min is not None:
        rows = [r for r in rows if r["gen"] is not None and r["gen"] >= a.gen_min]
    if a.gen_max is not None:
        rows = [r for r in rows if r["gen"] is not None and r["gen"] <= a.gen_max]

    silent = [r for r in rows if not r["declared"]]
    declared = [r for r in rows if r["declared"]]

    if a.heartbeat:
        # STANDING GOAL: drive SILENT to 0 — every parentless person either gains
        # parents or gains a written reason. Reported every session so the goal is
        # standing rather than remembered. `backed` guards the cheap win: closing a
        # row by asserting "parentage unknown" without consulting anything.
        n_s, n_d = len(silent), len(declared)
        tot = n_s + n_d
        pct = (100 * n_d // tot) if tot else 100
        unbacked = sum(1 for r in declared if not r["backed"])
        line = (f"FRONTIER: SILENT {n_s}, DECLARED {n_d} ({pct}% closed; target SILENT 0)")
        if unbacked:
            line += f", {unbacked} DECLARED cite no source/route [review]"
        print(line)
        return 0

    if a.summary:
        print(f"EXTENSION FRONTIER: SILENT {len(silent)} (no parents, no stated reason); "
              f"DECLARED {len(declared)}; total parentless {len(rows)}")
        return 0

    show = rows if a.all else silent
    show.sort(key=lambda r: (r["gen"] is None, r["gen"] or 0, TIER_ORDER.get(r["tier"], 3)))

    if a.csv:
        print("id,name,gen,tier,spouse_linked,status,file")
        for r in show:
            nm = '"%s"' % r["name"].replace('"', "'")
            print(f"{r['id']},{nm},{r['gen']},{r['tier']},{int(r['spouse'])},"
                  f"{'DECLARED' if r['declared'] else 'SILENT'},{r['file']}")
        return 0

    print("=" * 78)
    print("EXTENSION FRONTIER — people with no `parents` edge (advisory)")
    print("=" * 78)
    print("  SILENT = no parents recorded AND no reason given. Either extend the line,")
    print("  or write the terminus into the entry so it stops appearing here.")
    print("  `sp` marks an entry that has a spouse edge — the completeness-leaf class")
    print("  that chain-by-chain passes cannot see (this is how Hedwig was missed).\n")
    for r in show:
        gen = f"Gen {r['gen']:>2}" if r["gen"] is not None else "Gen  ?"
        tag = "sp" if r["spouse"] else "  "
        st = "DECLARED" if r["declared"] else "SILENT  "
        print(f"  {st} {gen} {tag} {r['name'][:46]:48} {r['tier'][:8]:9} [{r['file']}]")
    print(f"\n  SILENT {len(silent)}   DECLARED {len(declared)}   total parentless {len(rows)}")
    print("  Advisory only — a silent frontier is a research to-do, not a defect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
