#!/usr/bin/env python3
"""sex_inference.py -- a best GUESS at each person's sex, for display wording only.

The narrative person model has no sex field, so the session visualizer had to say
"aunt or uncle". This module guesses, in layers, and says which layer decided:

  0. field    the entry's own `sex` meta key (person_store.sex), when recorded. It
              always wins; a recorded `U` (looked, unknown) stops any guess.
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

⛔ A GUESS FOR WORDING, NOT A FACT. Layers 2-4 are never written to the vault, are
not records, and no gate or census may read them. Since 24 NOV 2026 the vault has
a `sex` field (seeded once from the GEDCOM, then written on touch from records);
this module is the fallback for people whose field is still absent.
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


def infer(people, bodies, seed=None, recorded=None):
    """people {id: PersonRecord}, bodies {id: entry text}, seed {id: 'M'|'F'} (GEDCOM),
    recorded {id: 'M'|'F'|'X'|'U'} (the vault field, which wins).
    Returns ({id: 'M'|'F'}, {id: layer})."""
    recorded = recorded or {}
    sex = {i: s for i, s in (seed or {}).items() if i not in recorded}
    src = {i: "gedcom" for i in sex}
    for i, s in recorded.items():
        if s in ("M", "F"):
            sex[i], src[i] = s, "field"
    settled = set(recorded)                  # X and U are recorded answers too: never guess over them
    for i in people:
        if i not in sex and i not in settled:
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
        if i not in sex and i not in settled and given_name(r.name) in lex:
            sex[i], src[i] = lex[given_name(r.name)], "name"
    for _ in range(4):
        changed = False
        for i, r in people.items():
            if i in sex or i in settled:
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
    recorded = {i: ps.sex(r) for i, r in people.items() if ps.sex(r)}
    return infer(people, bodies, seed, recorded)


def seed_from_gedcom(vault, apply=False):
    """Write `sex` from the GEDCOM's SEX tag onto every entry whose FS PID matches and
    that has no `sex` yet. One-time seed (operator, 24 NOV 2026); after it, the key is
    written ON TOUCH from records. Never overwrites a recorded value; writes only
    through person_store.set_meta_key on the record's own meta line."""
    import person_store as ps
    import vault_config as vc
    by_fs = gedcom_sex(vc.gedcom_path(vault)) if vc.gedcom_path(vault) else {}
    plan = collections.defaultdict(list)            # path -> [(meta_line_index, new_line)]
    skipped = collections.Counter()
    for r in ps.iter_people(vault):
        fs = str((r.external_ids or {}).get("fs", ""))
        if fs not in by_fs:
            continue
        if ps.sex(r) or ps.raw_sex_value(r):
            skipped["already recorded"] += 1
            continue
        raw = r.raw if isinstance(r.raw, dict) else {}
        if raw.get("meta_line") is None or not raw.get("path"):
            skipped["no meta line"] += 1
            continue
        new = ps.set_meta_key(raw["line"], "sex", by_fs[fs])
        if new == raw["line"]:
            skipped["unwritable meta"] += 1
            continue
        plan[raw["path"]].append((raw["meta_line"], raw["line"], new))
    n = 0
    for path, edits in plan.items():
        lines = Path(path).read_text(encoding="utf-8").split("\n")
        for idx, old, new in edits:
            if lines[idx] != old:
                raise SystemExit(f"refusing: {path}:{idx + 1} is not the meta line read")
            lines[idx] = new
            n += 1
        if apply:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
    verb = "wrote" if apply else "would write"
    print(f"seed-gedcom: {verb} sex on {n} entries in {len(plan)} file(s); skipped {dict(skipped)}"
          + ("" if apply else "  [dry-run; --apply to write]"))
    return n


if __name__ == "__main__":
    import argparse
    import vault_config as vc
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault")
    ap.add_argument("--seed-gedcom", action="store_true",
                    help="write the GEDCOM SEX tag as a `sex` meta key where none is recorded")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    vault = vc.resolve_vault(a.vault)
    if a.seed_gedcom:
        seed_from_gedcom(vault, a.apply)
    else:
        sex, src = vault_sexes(vault)
        print(f"sexed {len(sex)} people:", dict(collections.Counter(src.values())))
