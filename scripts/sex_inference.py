#!/usr/bin/env python3
"""sex_inference.py -- a best GUESS at each person's sex, for display wording only.

The narrative person model has no sex field, so the session visualizer had to say
"aunt or uncle". This module guesses, in layers, and says which layer decided:

  1. gedcom   the vault's GEDCOM `SEX` tag, matched on the FS PID (`_FSFTID`).
  2. pronoun  the entry's own biography (text before `- **Sources**`) uses he/his/him
              or she/her at least twice as often as the other, plus two.
  3. name     a given name the vault itself votes on (3+ people already sexed by
              layers 1-2, 90%+ one way). A STRONG name vote (5+, 95%+) also
              overrules a pronoun guess: pronoun counts misfire on entries that are
              mostly about a spouse.
  4. spouse   the opposite of a sexed spouse, when every sexed spouse agrees.

MEASURED (24 NOV 2026, against the 381 people whose GEDCOM sex is known, with the
GEDCOM held out of the learning): pronoun 143 right / 2 wrong, spouse 50 / 1,
name 113 / 0; the three misses were all fixed by the strong-name override. With the
GEDCOM as seed it sexes about 92% of the vault.

⛔ A GUESS FOR WORDING, NOT A FACT. Nothing here is written to the vault, nothing is
a record, and no gate or census may read it. If the vault ever gains a sex field,
that field wins and this module becomes a fallback.
"""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OPPOSITE = {"M": "F", "F": "M"}
TITLES = re.compile(r"^(?:(?:Sir|Lady|Dame|Captain|Capt\.|Deacon|Rev\.|Dr\.|Lieut\.|Lt\.|Ens\.|"
                    r"Ensign|Major|Mr\.|Mrs\.|Saint|St\.|Elder|Goodman|Goodwife)\s+)+")


def _ids(tokens):
    return [str(t).rstrip("?") for t in (tokens or [])]


def given_name(name):
    n = TITLES.sub("", (name or "").split(" [", 1)[0].strip())
    t = re.findall(r"[A-Za-zÀ-ÿ']+", n)
    return t[0].lower() if t else None


def pronoun_guess(text):
    bio = (text or "").split("**Sources**", 1)[0]
    he = len(re.findall(r"\b(?:he|his|him|himself)\b", bio, re.I))
    she = len(re.findall(r"\b(?:she|her|hers|herself)\b", bio, re.I))
    if he >= 2 * she + 2:
        return "M"
    if she >= 2 * he + 2:
        return "F"
    return None


def gedcom_sex(gedcom_path):
    """{FS PID: 'M'|'F'} from a GEDCOM file's INDI records."""
    out, cur = {}, {}
    try:
        lines = open(gedcom_path, encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in lines:
        if line.startswith("0 "):
            cur = {}
        elif line.startswith("1 SEX "):
            cur["sex"] = line.split()[2] if len(line.split()) > 2 else ""
        elif line.startswith("1 _FSFTID "):
            cur["fs"] = line.split()[2]
        if cur.get("fs") and cur.get("sex") in ("M", "F"):
            out[cur["fs"]] = cur["sex"]
    return out


def _lexicon(people, sex, min_n, purity):
    votes = collections.defaultdict(collections.Counter)
    for i, s in sex.items():
        g = given_name(people[i].name)
        if g:
            votes[g][s] += 1
    lex = {}
    for g, c in votes.items():
        s, n = c.most_common(1)[0]
        if sum(c.values()) >= min_n and n / sum(c.values()) >= purity:
            lex[g] = s
    return lex


def infer(people, bodies, seed=None):
    """people {id: PersonRecord}, bodies {id: entry text}, seed {id: 'M'|'F'}.
    Returns ({id: 'M'|'F'}, {id: layer})."""
    sex, src = dict(seed or {}), {i: "gedcom" for i in (seed or {})}
    for i in people:
        if i not in sex:
            g = pronoun_guess(bodies.get(i))
            if g:
                sex[i], src[i] = g, "pronoun"
    strong = _lexicon(people, sex, 5, 0.95)
    for i in list(sex):
        g = strong.get(given_name(people[i].name))
        if src[i] == "pronoun" and g and g != sex[i]:
            sex[i], src[i] = g, "name"
    lex = _lexicon(people, sex, 3, 0.9)
    for i, r in people.items():
        if i not in sex and given_name(r.name) in lex:
            sex[i], src[i] = lex[given_name(r.name)], "name"
    for _ in range(4):
        changed = False
        for i, r in people.items():
            if i in sex:
                continue
            got = {OPPOSITE[sex[s]] for s in _ids(r.spouse) if s in sex}
            if len(got) == 1:
                sex[i], src[i], changed = got.pop(), "spouse", True
        if not changed:
            break
    return sex, src


def vault_sexes(vault, people=None):
    """infer() over a vault: GEDCOM seed, entry bodies through the sanctioned reader."""
    import harvest_sources as hs
    import person_store as ps
    import vault_config as vc
    if people is None:
        people = {r.id: r for r in ps.iter_people(vault)}
    bodies = {}
    for rows in hs.entry_blocks_with_ids(str(vault)).values():
        for pid, _name, _idx, text in rows:
            bodies[pid] = text
    seed = {}
    try:
        ged = vc.gedcom_path(vault)
    except Exception:
        ged = None
    if ged:
        by_fs = gedcom_sex(ged)
        for i, r in people.items():
            fs = str((r.external_ids or {}).get("fs", ""))
            if fs in by_fs:
                seed[i] = by_fs[fs]
    return infer(people, bodies, seed)


if __name__ == "__main__":
    import vault_config as vc
    sex, src = vault_sexes(vc.resolve_vault(None))
    print(f"sexed {len(sex)} people:", dict(collections.Counter(src.values())))
