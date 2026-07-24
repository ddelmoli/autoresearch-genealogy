#!/usr/bin/env python3
"""
Harvest FS PIDs from Family_Tree*.md narrative files for Person_Index candidates.

Strategy (rewritten v2):
1. Scan each narrative file and build a list of "person entries":
   - Each entry starts at a line where a bullet or paragraph begins with **Name**
   - Capture the bolded name and the entry's body (until the next entry start
     or a clear paragraph break)
2. Within each entry's body, extract any FS PID
3. Build a dictionary: normalized-name -> [(pid, file, line, snippet), ...]
4. For each Person_Index candidate (PID = — or pending FS), look up its
   normalized name in the dictionary; report matches with confidence:
   - UNAMBIGUOUS: exactly one PID matches across all narrative entries
   - AMBIGUOUS: multiple distinct PIDs map to the same name
   - NO_MATCH: name not present in any narrative entry header

Does NOT edit any files.
"""

import re, glob, os, sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises

PID_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{3})\b")
# An "entry header" line: optional bullet marker + **BoldName** + opening paren
# Capture the parenthetical content too, so we can search the PID only inside it
# Examples:
#   "**John Smith** (b. 26 MAR 1864, ... FS PID **XXXX-XXX**)"
#   "**George Edwin Doe (1840-1873, FS PID YYYY-YYY)**"   <-- bold-wraps-everything
# Require at least 2 word tokens (filters out **.**, **Strong Signal**)
# Pattern A: **Name** ( ... )
ENTRY_HDR_A = re.compile(
    r"^[\-\*\s]*\*\*([A-ZÀ-Ý][\w\.\-'À-ÿ]+(?:\s+[\w\.\-'À-ÿ]+){1,8})\*\*\s*\(([^)]{0,800})\)",
    re.MULTILINE,
)
# Pattern B: **Name ( ... )**  (bold wraps the whole thing including PID)
# ANCHORED to line start, like pattern A (23 JUL 2026, spec/entry-boundary): a real
# entry header always begins its line, and an unanchored match treats a bold span in
# mid-sentence prose as an entry. Here the damage was bounded (a PID must appear in
# the parenthetical), but it is the same defect this module's descendant
# harvest_sources.py was corrupting its census with, so the dialect is anchored
# everywhere it is recognized.
ENTRY_HDR_B = re.compile(
    r"^[\-\*\s]*\*\*([A-ZÀ-Ý][\w\.\-'À-ÿ]+(?:\s+[\w\.\-'À-ÿ]+){1,8})\s*\(([^)]{0,800})\)\*\*",
    re.MULTILINE,
)

# Sub-entries within a paragraph (used only as a content-skip signal, no longer
# used for body boundary computation since we now scope PID to the parenthetical)

def normalize_name(name):
    """Lowercase, strip diacritics-ish, strip parens, strip strikethrough."""
    n = re.sub(r"~~.*?~~", "", name)
    n = re.sub(r"\s*\([^)]*\)\s*", " ", n)
    n = re.sub(r"\*+", "", n)
    n = re.sub(r"\s+", " ", n).strip().lower()
    return n

def token_set(name):
    """Tokenize a normalized name into a set of word-chars-only tokens of length >= 2."""
    return {t for t in re.findall(r"\w{2,}", name)}

SUFFIX_RE = re.compile(r"\b(sr|jr|i{1,3}|iv|v|esq|esquire|gent|gentleman)\b\.?", re.IGNORECASE)

def extract_suffix(name):
    """Return canonical suffix (sr/jr/iii/etc) or None."""
    m = SUFFIX_RE.search(normalize_name(name))
    if m:
        return m.group(1).lower()
    return None

DESCRIPTIVE_TOKENS = {
    "siblings", "children", "family", "ancestors", "descendants", "cluster",
    "branch", "lineage", "household", "vault", "vaults", "candidates",
    "spouses", "relatives",
}

def names_match(narr_name, cand_name):
    """
    Strict matching:
    - Narrative name must NOT contain descriptive tokens (siblings/children/etc.)
    - Both names must have >= 2 tokens of length >= 2
    - Token sets must be equal, OR cand_tokens is subset of narr_tokens (narr has extra middle names),
      OR narr_tokens is subset of cand_tokens (Person_Index has extra qualifiers)
    - Suffix (Sr./Jr./III/etc.) must match exactly when present on either side
    Returns the match kind, or None.
    """
    # Reject narrative names that look like section headers, not persons
    narr_tokens_raw = set(re.findall(r"\w+", normalize_name(narr_name)))
    if narr_tokens_raw & DESCRIPTIVE_TOKENS:
        return None
    # Suffix gate: if either side has a suffix, both must have the SAME suffix
    n_suf = extract_suffix(narr_name)
    c_suf = extract_suffix(cand_name)
    if n_suf != c_suf:
        return None
    n_tok = token_set(normalize_name(narr_name))
    c_tok = token_set(normalize_name(cand_name))
    if len(n_tok) < 2 or len(c_tok) < 2:
        return None
    if n_tok == c_tok:
        return "exact"
    # Identify "discriminating" tokens (anything > 2 chars to filter out "de", "di", "fu", "jr", "sr")
    n_disc = {t for t in n_tok if len(t) >= 3}
    c_disc = {t for t in c_tok if len(t) >= 3}
    if len(n_disc) < 2 or len(c_disc) < 2:
        return None
    if n_disc <= c_disc or c_disc <= n_disc:
        # at least 2 discriminating tokens shared
        shared = n_disc & c_disc
        if len(shared) >= 2:
            return "subset"
    return None

# YEAR_RE is GONE (spec/structured-dates Spec 05). It matched years 1500-2029 and
# nothing else — a **1500 floor** that made every medieval person
# yearless, and so invisible to dup_name_audit: with no year that check neither
# flags a pair NOR clears it. Year resolution now goes through the one shared path
# in gdate, which reads a real DateValue field first and only then falls back.
import gdate


def extract_year(s):
    """First comparable year from a record's date value. See gdate.resolve_year."""
    return gdate.resolve_year(s)

def extract_died_year(s):
    """Extract the last 4-digit year-like token (typically the death year in
    parenthetical ranges like '(1883-1885)' or 'd. 1962'). Returns int or
    None. Useful for cross-checking against a candidate's death year when
    same-name siblings/cousins fall within the birth-year tolerance window."""
    lo, hi = gdate.resolve_year_range(s)
    if lo is not None and hi is not None and hi != lo:
        return hi
    # Single year — only return if a 'd.' marker precedes it
    m = re.search(r"\bd\.\s*[^,;)]*?(\d{4})", s or "")
    if m:
        return int(m.group(1))
    return None

def extract_entries(filename, body):
    """
    Find all bold-name entries in a file. PID must appear inside the FIRST
    parenthetical attached to the bold name. Also capture the birth year from
    the paren content if present (for disambiguation across same-named people).
    Returns list of dicts: {name, file, line, pid, year, snippet, pattern}
    """
    out = []
    seen_starts = set()
    for pat, label in [(ENTRY_HDR_A, "A"), (ENTRY_HDR_B, "B")]:
        for m in pat.finditer(body):
            start = m.start()
            if start in seen_starts:
                continue
            seen_starts.add(start)
            name = m.group(1).strip()
            paren_content = m.group(2)
            pid_match = PID_RE.search(paren_content)
            if not pid_match:
                continue
            pid = pid_match.group(1)
            year = extract_year(paren_content)
            died_year = extract_died_year(paren_content)
            line = body[:start].count("\n") + 1
            snippet = m.group(0)[:200].replace("\n", " ")
            out.append({
                "name": name,
                "file": filename,
                "line": line,
                "pid": pid,
                "year": year,
                "died_year": died_year,
                "snippet": snippet,
                "pattern": label,
            })
    return out

def parse_person_index():
    """Return list of candidate rows (PID = — / pending FS).

    NEW Person_Index layout: | Name | Gen | Born | Died | FS PID | Notes |
    Generation now comes from the Gen column (cells[1]), not from
    `## Generation N` section headers (which no longer exist).

    Person_Index.md was RETIRED (memory project_person_index_retirement). This
    module now survives only as a name-matching HELPER LIBRARY (normalize_name,
    token_set, names_match, extract_year — imported by gen_person_index and the
    seeder/migration tools). Its standalone PID-harvest CLI has no candidate
    source once the index is gone, so this returns []."""
    path = os.path.join(VAULT, "Person_Index.md")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            # Stop at the Appendix block (historical prose, not data rows)
            if line.startswith("## Appendix"):
                break
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) < 6:
                continue
            name, gen_str, born, died, pid, conf = cells[:6]
            gennum = int(gen_str) if re.match(r"^\d+$", gen_str) else None
            if pid in ("—", "(pending FS)"):
                rows.append({
                    "gen": gennum, "name": name, "born": born, "died": died,
                    "pid_current": pid, "conf": conf, "file": "", "lineno": lineno,
                })
    return rows

def main():
    vault_config.require_vault(VAULT)
    candidates = parse_person_index()
    print(f"Loaded {len(candidates)} candidates", file=sys.stderr)

    # Build narrative entry dictionary
    all_entries = []
    for path in sorted(glob.glob(os.path.join(VAULT, "Family_Tree*.md"))):
        with open(path) as f:
            body = f.read()
        entries = extract_entries(os.path.basename(path), body)
        all_entries.extend(entries)
    print(f"Extracted {len(all_entries)} bold-name entries from narrative", file=sys.stderr)

    # Pre-compute how many candidates share each normalized name
    # (used to flag "ambiguous candidate" cases where we have multiple
    # Sir Walter Ashbys or multiple John Smiths in Person_Index)
    from collections import Counter
    cand_name_counts = Counter(normalize_name(c["name"]) for c in candidates)

    # Match candidates to entries
    unambiguous = []
    ambiguous = []
    no_match = []
    for cand in candidates:
        cand_year = extract_year(cand["born"]) or extract_year(cand["died"])
        cand_died_year = extract_year(cand["died"])
        cand_norm = normalize_name(cand["name"])
        cand_name_is_dup = cand_name_counts[cand_norm] > 1
        # Find all narrative entries whose name matches this candidate
        matches = []
        for ent in all_entries:
            kind = names_match(ent["name"], cand["name"])
            if not kind:
                continue
            # Year-proximity check: if both have years, require within 4
            if cand_year and ent["year"]:
                if abs(cand_year - ent["year"]) > 4:
                    continue
            # Death-year cross-check: when both sides have a death year, require
            # those to be within tolerance too. Catches the infant-vs-adult and
            # cousin-vs-namesake collisions where birth years happen to fall in
            # the window but death years are decades apart (e.g., infant Domenico
            # Rossi d.1885 vs cousin Domenico d.1962 — birth diff 3 but
            # death diff 77).
            if cand_died_year and ent.get("died_year"):
                if abs(cand_died_year - ent["died_year"]) > 4:
                    continue
            # If candidate has no year and the name is a duplicate in Person_Index,
            # require the narrative entry to also have no year (otherwise we can't
            # tell which person this PID belongs to)
            if not cand_year and cand_name_is_dup and ent["year"]:
                continue
            # When the candidate name is MORE specific than the narrative name
            # (Person_Index has an extra discriminator like a patronymic or middle name
            # that's missing from the narrative bold name), require a year match to
            # confirm. Without a year on at least one side, we can't tell whether the
            # narrative entry is the same person or a different relative.
            if kind == "subset":
                c_disc = {t for t in token_set(normalize_name(cand["name"])) if len(t) >= 3}
                n_disc = {t for t in token_set(normalize_name(ent["name"])) if len(t) >= 3}
                if n_disc < c_disc and not (cand_year and ent["year"]):
                    # narrative is strictly smaller token set + no year confirmation
                    continue
            matches.append((kind, ent))
        if not matches:
            no_match.append(cand)
            continue
        # Dedup by PID
        unique_pids = {}
        for kind, ent in matches:
            unique_pids.setdefault(ent["pid"], []).append((kind, ent))
        # Resolution: if only 1 unique PID, unambiguous
        if len(unique_pids) == 1:
            pid = list(unique_pids.keys())[0]
            unambiguous.append((cand, pid, unique_pids[pid]))
        else:
            # Try to break ambiguity: if exactly one PID has an "exact" name match
            # and all others are "subset", prefer the exact
            exact_pids = {pid for pid, m_list in unique_pids.items()
                          if any(k == "exact" for k, _ in m_list)}
            if len(exact_pids) == 1:
                pid = list(exact_pids)[0]
                unambiguous.append((cand, pid, unique_pids[pid]))
            else:
                ambiguous.append((cand, matches))

    # Report
    print("\n=== UNAMBIGUOUS HARVESTABLE (safe to apply) ===")
    print("gen\tname\tcurrent\tproposed_pid\tnarr_file\tnarr_name")
    for cand, pid, ents in sorted(unambiguous, key=lambda x: (x[0]["gen"] or 0, x[0]["name"])):
        ent = ents[0][1]  # first matching entry
        print(f"{cand['gen']}\t{cand['name']}\t{cand['pid_current']}\t{pid}\t{ent['file']}\t{ent['name']}")
    print(f"\n  Total UNAMBIGUOUS: {len(unambiguous)}")

    print("\n=== AMBIGUOUS (multiple distinct PIDs, needs human review) ===")
    for cand, matches in ambiguous:
        print(f"\n  Gen {cand['gen']} | {cand['name']}  (Person_Index points to {cand['file']})")
        seen_pids = set()
        for kind, ent in matches:
            if ent["pid"] in seen_pids:
                continue
            seen_pids.add(ent["pid"])
            print(f"    {ent['pid']} via '{ent['name']}' in {ent['file']}:{ent['line']} [{kind}]")
            print(f"      snippet: {ent['snippet'][:150]}")
    print(f"\n  Total AMBIGUOUS: {len(ambiguous)}")

    print(f"\n=== NO_MATCH ({len(no_match)} candidates with no narrative bold-name entry) ===")
    # Print first 20 only
    for cand in no_match[:20]:
        print(f"  Gen {cand['gen']} | {cand['name']} [{cand['file']}]")
    if len(no_match) > 20:
        print(f"  ... and {len(no_match) - 20} more")

    print(f"\n=== SUMMARY ===")
    print(f"  Total candidates:      {len(candidates)}")
    print(f"  Unambiguous matches:   {len(unambiguous)}  <-- ready to apply")
    print(f"  Ambiguous matches:     {len(ambiguous)}  <-- needs human review")
    print(f"  No narrative entry:    {len(no_match)}  <-- true new contributions OR vault staleness")

if __name__ == "__main__":
    main()
