#!/usr/bin/env python3
"""disconnected_audit.py — who is in the vault but attached to NOTHING, and
which of them name a relative the vault already holds?

WHY IT EXISTS (15 AUG 2026, session #172, operator-directed).

The frontier report answers "who has no PARENTS?". Nothing answered "who is
connected to the tree AT ALL?" — no parents, no spouse, and no other entry
pointing at them. Those people are not invisible to the lanes: measured when
this was written, **79 such entries existed, 64 of them already in the SILENT
frontier and 67 already in SOURCE_GAP**. EXPAND draws them and IMPROVE draws
them.

** SO THIS IS NOT A COVERAGE GAP. IT IS A LABELLING ONE, AND THAT IS THE WHOLE
POINT OF THE TOOL. ** When such a row comes up, the plan says "no parents edge,
no declared reason", which points the session at the EXPENSIVE question. The
archetype is **Joan Example**: her own entry says in terms *"Mother of Thomas
Example the Husbandman"*, corroborated against WikiTree Surname-48 — and Thomas's
meta block carries no `parents:` key at all. Drawn as a frontier row she reads
as "go find Joan's parents in England, husband unknown", which is hard and may
be impossible. Read as an unwired edge she is a two-minute fix whose evidence
was written down months ago. Same row, same lane, completely different job, and
nothing in the vault distinguished them.

WHAT IT REPORTS

  DISCONNECTED   0 parents, 0 spouse, and 0 inbound edge references. A person
                 floating free of every lineage. Not automatically a defect —
                 a collateral stub legitimately looks like this, and so does a
                 deliberately detached non-ancestor (Emma Example is the
                 vault's worked example).

  UNWIRED_KIN    the actionable subset: a DISCONNECTED entry whose OWN PROSE
                 names a relationship to a person the vault already holds, with
                 no edge between them. These are candidate wirings with the
                 evidence already in the entry.

⚠⚠ THIS TOOL MATCHES ON NAMES, WHICH THIS VAULT HAS BEEN BURNED BY REPEATEDLY.
`log_backlinks.py` deliberately matches on IDENTIFIERS and never on names, for
good reason: four men of one name lived in a single parish at once, and one
session alone met two same-named fathers and two same-named sons. So:

  - Every finding is a **CANDIDATE, not a verdict**. Nothing here is ever wired
    automatically, and there is no `--apply`. Read the entry, confirm the
    identifiers, then wire by hand with a `?` like any other hand-authored edge.
  - A name claimed by **two or more** entries is DROPPED and counted, never
    guessed between — the same rule `log_backlinks` applies to tokens.
  - A single-token name ("Mary", "Jane") is never matched at all.
  - A relationship named in a **refuting** context is suppressed, not proposed.

⚠⚠ AND IT SHIPPED A CONFIDENTLY WRONG EDGE TWICE BEFORE IT SHIPPED AT ALL —
both caught only by reading the output, neither by any gate:

  1. It proposed re-wiring **Emma Example to Hugh Example**, the edge a
     session had disproved and deliberately detached on a standard printed
     peerage. A denial names the relationship in full in order to deny it.
  2. Fixing the by-name handling then matched **Joan Example to Thomas Example
     Jr.** — the wrong man — because the tail-trimmer cut "Thomas Example the
     Husbandman" back to "Thomas Example".

Each regression made the output look MORE useful, which is the flattering
direction this vault treats as a warning. Behaviours are pinned in
`scripts/test_disconnected_audit.py`; run it after touching any regex here.

Usage:
    python3 scripts/disconnected_audit.py [--vault PATH] [--limit N]
    python3 scripts/disconnected_audit.py --heartbeat     # one line, for the banner
    python3 scripts/disconnected_audit.py --candidates    # UNWIRED_KIN only
"""

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

META_RE = re.compile(r"- meta: \{id: (P-[0-9A-Z]{6})(.*)")
ID_RE = re.compile(r"P-[0-9A-Z]{6}")
BOLD_RE = re.compile(r"^\*\*(.+?)\*\*")
# ⚠ NAME capture accepts the BULLET entry form too (`- **Name** (...)`), while
# entry TERMINATION deliberately still keys on the line-start form only. Widening
# both would let a body bullet like `- **Sources**` end the entry and truncate the
# prose this tool reads. Discovered 15 AUG 2026: a line-start-only name reader
# attached the PREVIOUS entry's name to two bullet-form entries, which read as two
# mis-attached FS PIDs until the entries were opened.
BOLD_ANY_RE = re.compile(r"^\s*(?:[-*]\s*)?\*\*(.+?)\*\*")

# Relationship phrasings actually used in this vault's entries. Each captures the
# text that should hold the RELATIVE's name. Deliberately narrow: a missed
# candidate costs nothing (the row stays on the worklist), while a bad match
# invites exactly the same-name error the tool warns about.
REL_RE = [
    (re.compile(r"\b(?:mother|father|parent)\s+of\s+([^,;.()\[\]]+)", re.I), "child"),
    (re.compile(r"\b(?:son|daughter|child)\s+of\s+([^,;.()\[\]]+)", re.I), "parent"),
    (re.compile(r"\b(?:wife|husband|widow)\s+of\s+([^,;.()\[\]]+)", re.I), "spouse"),
    (re.compile(r"\bmarried\s+((?:[A-Z][\w'’-]+\s+){1,3}[A-Z][\w'’-]+)"), "spouse"),
]

# ⛔ Refutation context. A bullet that DENIES a relationship names it in full in
# order to deny it, so the relationship regexes match a disproof exactly as they
# match an assertion. Deliberately broad: a missed candidate costs nothing, while
# re-proposing a detached edge destroys the work that detached it.
NEGATION_RE = re.compile(
    r"⛔|⚠⚠|\bnot\b|\bno\b|\bnever\b|disprov|refut|unsupported|unproven|unverified"
    r"|must not|do not|does not|cannot|rejected|withdrawn|retracted|removed|detach"
    r"|conflat|mis-?attribut|error|wrong|false|tradition|claim(?:ed|s)? to be"
    r"|NOT ADOPTED|not adopted|lead only|candidate|hypothes|speculat|possib|probab"
    r"|alleged|purport|if\b|whether\b",
    re.I,
)


# Honorifics, suffixes and editorial furniture stripped before comparing names.
NOISE_RE = re.compile(
    r"\b(?:Capt\.?|Captain|Lt\.?|Lieut\.?|Lieutenant|Sir|Rev\.?|Deacon|Dea\.?|Dr\.?|"
    r"Mrs\.?|Mr\.?|Major|Maj\.?|Col\.?|Ensign|Jr\.?|Sr\.?|I{1,3})\b",
    re.I,
)
# ⛔⛔ `the` IS NOT A STOP WORD HERE, AND REMOVING IT WAS A REAL BUG CAUGHT IN
# TESTING (15 AUG 2026). While `the` truncated the tail, "Thomas Example the
# Husbandman" was cut back to "Thomas Example" — which then resolved UNIQUELY
# and CONFIDENTLY to **Thomas Example Jr., the wrong man**. The by-name is the
# discriminator; cutting at `the` throws it away and converts a safe ambiguous
# DROP into a wrong answer. That is strictly worse than reporting nothing, and
# it is the same-name failure this whole tool exists to avoid, reproduced inside
# the tool itself in the space of one edit.
STOP_TAIL_RE = re.compile(
    r"\b(?:and|his|her|their|who|which|in|at|by|gen|generation|bapt|"
    r"above|below|this|that|our|ancestor|entry|file)\b.*$", re.I)


def norm_name(s):
    """A comparable key for a display name. Empty string = do not match on it."""
    # ⭐ Bracketed BY-NAMES are kept, not stripped. "Thomas Example [the
    # Husbandman]" and "Thomas Example Jr." both reduced to "thomas example"
    # while the brackets were being discarded, so the pair read as AMBIGUOUS and
    # the tool dropped its own archetype (Joan Example, whose prose names the
    # Husbandman explicitly). The compiler's by-name is the DISCRIMINATOR that
    # tells four contemporary men of that name apart — throwing it away destroyed
    # the only thing that could separate them.
    s = re.sub(r"[\[\]]", " ", s or "")
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.replace("’", "'")
    s = NOISE_RE.sub(" ", s)
    s = re.sub(r"[^\w\s']", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    # A bare forename is not a usable key — see the docstring.
    return s if len(s.split()) >= 2 else ""


def load(vault):
    """-> (records, inbound counter). One pass, no backend import needed: the
    meta line is the identity anchor and the bold name directly above it is the
    display name, which is exactly the contract CLAUDE.method.md states."""
    records = {}
    inbound = collections.Counter()
    for fn in sorted(os.listdir(vault)):
        if not (fn.startswith("Family_Tree") and fn.endswith(".md")):
            continue
        path = os.path.join(vault, fn)
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        name, cur = None, None
        for line in lines:
            if BOLD_RE.match(line):
                name, cur = BOLD_RE.match(line).group(1), None
            elif BOLD_ANY_RE.match(line) and not line.lstrip().startswith(">"):
                name = BOLD_ANY_RE.match(line).group(1)   # name only; entry continues
            m = META_RE.match(line)
            if m:
                pid, rest = m.group(1), m.group(2)
                cur = pid
                records[pid] = {
                    "id": pid, "name": name, "file": fn, "body": [],
                    "gen": (int(g.group(1)) if (g := re.search(r"generation: (\d+)", rest)) else None),
                    "has_parents": "parents:" in rest,
                    "has_spouse": "spouse:" in rest,
                    "living": bool(re.search(r"life_status: (living|unknown)", rest)),
                    "edges": set(ID_RE.findall(rest)) - {pid},
                }
                for ref in records[pid]["edges"]:
                    inbound[ref] += 1
            elif cur and not line.lstrip().startswith(">"):
                records[cur]["body"].append(line)
    return records, inbound


def find_candidates(records, by_name, ambiguous):
    """UNWIRED_KIN: prose names a vault person, and no edge joins the two.

    ⛔⛔ SCANNED LINE BY LINE, AND A LINE IN A REFUTING CONTEXT IS SKIPPED. The
    first run of this tool proposed re-wiring **Emma Example to Hugh le
    Despenser** — precisely the edge a session had DISPROVED and deliberately
    detached, on a standard printed peerage. The prose names the
    relationship *in order to deny it*, and a bare regex reads a denial exactly
    like an assertion. That is the vault's own "writing about a marker = having
    it" hazard in a new costume, and it is the most dangerous thing this tool
    could do: silently re-attaching a refuted edge destroys the finding that
    detached it, and no gate would object.

    ⚠ That same candidate was wrong TWICE — it also matched the wrong Hugh (the
    husband, not the Justiciar the sentence is about). Both failures are why the
    output is advisory and why there is no --apply.
    """
    out, dropped, refuted = [], 0, 0
    for rec in records.values():
        seen = set()
        for line in rec["body"]:
            negated = bool(NEGATION_RE.search(line))
            for rx, kind in REL_RE:
                for raw in rx.findall(line):
                    cand = STOP_TAIL_RE.sub("", raw).strip()
                    key = norm_name(cand)
                    if not key or key in seen:
                        continue
                    if key in ambiguous:
                        dropped += 1
                        seen.add(key)
                        continue
                    other = by_name.get(key)
                    if not other or other == rec["id"]:
                        continue
                    # Already joined in either direction? Wired, not a finding.
                    if other in rec["edges"] or rec["id"] in records[other]["edges"]:
                        seen.add(key)
                        continue
                    if negated:
                        refuted += 1
                        seen.add(key)
                        continue
                    seen.add(key)
                    out.append((rec, kind, records[other]))
    return out, dropped, refuted


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--candidates", action="store_true")
    a = ap.parse_args()
    vault = vault_config.resolve_vault(a.vault)

    records, inbound = load(vault)

    # Name index, built once. A key claimed by 2+ entries is unusable by design.
    owners = collections.defaultdict(list)
    for pid, r in records.items():
        k = norm_name(r["name"])
        if k:
            owners[k].append(pid)
    by_name = {k: v[0] for k, v in owners.items() if len(v) == 1}
    ambiguous = {k for k, v in owners.items() if len(v) > 1}

    disconnected = [r for r in records.values()
                    if not r["has_parents"] and not r["has_spouse"]
                    and inbound[r["id"]] == 0]
    cands, dropped, refuted = find_candidates(records, by_name, ambiguous)
    disc_ids = {r["id"] for r in disconnected}
    unwired = [c for c in cands if c[0]["id"] in disc_ids]

    if a.heartbeat:
        print(f"DISCONNECTED {len(disconnected)} (0 edges, 0 inbound); "
              f"UNWIRED_KIN {len(unwired)} of them name a vault person in prose "
              f"[advisory; CANDIDATES — name-matched, read before wiring]")
        return 0

    if not a.candidates:
        print(f"=== DISCONNECTED: {len(disconnected)} entr(ies) with no parents, "
              f"no spouse and nothing pointing at them ===")
        print("  Not automatically a defect: collateral stubs and deliberately")
        print("  detached non-ancestors look like this too. Read before acting.\n")
        for r in sorted(disconnected, key=lambda r: -(r["gen"] or 0))[:a.limit]:
            print(f"  Gen {str(r['gen']):>3}  {r['id']}  {(r['name'] or '')[:42]:42} {r['file']}")
        if len(disconnected) > a.limit:
            print(f"  ... and {len(disconnected) - a.limit} more (--limit N)")
        print()

    print(f"=== UNWIRED_KIN: {len(unwired)} candidate wiring(s) ===")
    print("  A DISCONNECTED entry whose own prose names a person the vault already")
    print("  holds, with no edge between them. ⚠ NAME-MATCHED: each is a CANDIDATE.")
    print("  Confirm identifiers, then wire by hand with a `?`. There is no --apply.\n")
    for rec, kind, other in sorted(unwired, key=lambda c: -(c[0]["gen"] or 0))[:a.limit]:
        print(f"  {rec['id']}  {(rec['name'] or '')[:34]:34} "
              f"--{kind:>6}--> {other['id']}  {(other['name'] or '')[:30]:30}")
        print(f"      {rec['file']}  |  far end in {other['file']}")
    if len(unwired) > a.limit:
        print(f"  ... and {len(unwired) - a.limit} more (--limit N)")
    if dropped:
        print(f"\n  ⚠ {dropped} prose name(s) DROPPED as ambiguous (claimed by 2+ entries).")
        print("    Never guessed between — the same rule log_backlinks applies to tokens.")
    if refuted:
        print(f"  ⛔ {refuted} match(es) SUPPRESSED as refutation context — the prose names")
        print("    the relationship in order to DENY it. Re-proposing a deliberately")
        print("    detached edge would destroy the finding that detached it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
