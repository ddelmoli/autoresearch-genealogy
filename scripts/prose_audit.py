#!/usr/bin/env python3
"""
Prose-vs-canonical drift detector.

Canonical truth comes from the vault/Family_Tree*.md narratives — each person's
bold-name header (name + vitals parenthetical) plus its `- meta:` block (id / FS /
tier / gen). Person_Index.md was RETIRED (see memory project_person_index_retirement);
the canonical fact map is now built from the narratives via
gen_person_index.parse_narrative(), NOT from a parallel index table.

Prose summaries (intros, "Lineage interconnections" sections, hereditary-society
walks, mayflower-line write-ups, etc.) paraphrase these canonical facts. When
canonical entries change OR when prose is written from memory rather than
canonical, drift happens.

This script checks two kinds of drift:

  CLAIM 1 — Inline person fact:
    "Name (b. YEAR PLACE; d. YEAR PLACE)"  or  "Name (YEAR-YEAR)"
    Compare extracted years/places to the canonical narrative Born/Died.

  CLAIM 2 — Relationship-with-name:
    "paternal grandmother Maria Rossi", "great-grandfather John Smith"
    Verify the named person ACTUALLY has that relationship to the subject
    according to the canonical family tree.

  CLAIM 3 — Death-unknown placeholder:
    "Name (... d. ?)" or "Name (... d. unknown)" when canonical has a death date.

Does NOT edit any files.
"""
import re, glob, os, sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import gen_person_index as G
import gdate
import vault_config
VAULT = vault_config.resolve_vault()

PID_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{3})\b")
# TWO year scanners, and the split is deliberate (spec/structured-dates Spec 05).
#
#   CANONICAL side -> gdate.resolve_year, which reads the record's `born`/`died`
#   FIELD first. The old shared regex matched years 1500-2029 and nothing else, a
#   1500 floor that meant no pre-1500 person could be year-drift-checked at all.
#
#   PROSE side -> PROSE_YEAR_RE below. This one scans FREE TEXT, a different job
#   with different hazards: narrative sentences are full of page numbers, atto
#   numbers, regnal years and citation numbers. It must NOT simply be widened to
#   match the canonical path; widening a year scanner over prose was measured on
#   22 JUL 2026 in an adjacent context and read `534` as a death year. Any change
#   here needs its own measurement (see the Spec 05 notes for the one that was run).
PROSE_YEAR_RE = re.compile(r"\b(1\d{3}|20[0-2]\d)\b")

# ============================================================
# Build canonical fact map
# ============================================================

def parse_person_index():
    """Canonical person facts, sourced from the NARRATIVES (Person_Index retired).

    Delegates to gen_person_index.parse_narrative() — which reads each entry's
    bold-name header (name + vitals paren) and `- meta:` block — and reshapes the
    rows to the {name, born, died, pid, gen, lineno, born_year, died_year} dicts
    the rest of this auditor expects. `lineno` is the narrative meta line for a
    stable, if cosmetic, anchor."""
    rows = []
    for e in G.parse_narrative():
        # TWO STORES, ONE FACT (spec/structured-dates Spec 06, decision (a)):
        #   the FIELD is authoritative for the YEAR — it is a real DateValue;
        #   the HEADER is authoritative for the PLACE — a date field holds no
        #   place by design, so deriving one from it is a category error. That
        #   mistake produced a live false positive: a canonical born of
        #   'BET 1625 AND 1627' was compared against a prose place.
        header_born = _clean_vital(e.get("header_born") or "")
        header_died = _clean_vital(e.get("header_died") or "")
        born = header_born or _clean_vital(e["born"])
        died = header_died or _clean_vital(e["died"])
        rows.append({
            "name": e["name"],
            "born": born,
            "died": died,
            "field_born": e["born"],
            "field_died": e["died"],
            "header_born": header_born,
            "header_died": header_died,
            "pid": e["pid"],
            "gen": e["gen"],
            "file": e.get("file"),
            "meta_date_keys": e.get("meta_date_keys") or (),
            "lineno": 0,
            # canonical side: the FIELD when the entry has one, else the header —
            # all inside gdate.resolve_year, one path for every gate.
            "born_year": gdate.resolve_year(e["born"]) or gdate.resolve_year(header_born),
            "died_year": gdate.resolve_year(e["died"]) or gdate.resolve_year(header_died),
        })
    return rows


def _clean_vital(s):
    """Narrative vitals parentheticals are freeform ('3 SEP 1780 (FS XXXX-XXX +
    a cited 1969 genealogy p.61)', 'baptized 3 OCT 1598') — far messier than
    the retired index's tidy Born/Died columns. Drop parenthetical asides and any
    'FS …'/PID provenance tail so the year stays and the place-segment extractor
    doesn't misread provenance text as a place. Year-only and clean 'DATE, PLACE'
    cells pass through unchanged."""
    if not s:
        return s
    s = re.sub(r"\([^)]*\)", "", s)                 # drop "(FS …)" asides
    s = re.sub(r"\bFS\b.*$", "", s, flags=re.I)     # drop "FS XXXX-XXX + …" tails
    s = re.sub(r"\b[A-Z0-9]{4}-[A-Z0-9]{3}\b.*$", "", s)  # drop a bare PID + tail
    return re.sub(r"\s+", " ", s).strip(" ,;")

def extract_year(s):
    """PROSE-side year scan. Not the canonical path — see the note at PROSE_YEAR_RE."""
    m = PROSE_YEAR_RE.search(s or "")
    return int(m.group(1)) if m else None

# Tokens that look alphabetic but do NOT name a place: date qualifiers and
# month abbreviations. A comma-segment of a Born/Died cell counts as a "place"
# only if, after removing these and any digits, an actual word remains.
_NON_PLACE_WORDS = {
    "abt", "bef", "aft", "est", "ca", "circa", "bapt", "baptized", "baptised",
    "christened", "chr", "bp", "bur", "buried", "born", "died",
    "unknown", "unk", "deceased", "living", "alive", "and", "the", "of", "age",
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
    # occupations / civil-status descriptors that occasionally land in the
    # comma-segment the place regex grabs (e.g. "b. 1750, Mariner, Boston")
    "mariner", "yeoman", "gentleman", "gent", "esq", "esquire", "widow",
    "widower", "spinster", "laborer", "labourer", "husbandman", "contadino",
    "infant", "twin",
}

def _norm_place(s):
    """Lowercase + canonicalize a place string for comparison: expand the
    "Co." abbreviation to "county" (so "Co. Fermanagh" == "County Fermanagh")
    and drop trailing punctuation / wikilink-and-aside tails."""
    s = (s or "").lower().strip()
    s = re.sub(r"\s+[—–-]\s+.*$", "", s)         # drop " — aside" / " - see ..." tails
    s = re.sub(r"[.,;:]", " ", s)                # punctuation → space
    s = re.sub(r"\bco\b", "county", s)           # Co. / Co → county
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _segment_names_place(seg):
    """True if a comma-segment of a date cell actually names a place, i.e. it
    contains at least one alphabetic word that is not a date qualifier or month
    abbreviation. "Salem" → True; "DEC 1651" → False; "ABT 1640" → False;
    "bef. 9 OCT 1774" → False; "" → False."""
    words = [w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{2,}", seg or "")]
    return any(w not in _NON_PLACE_WORDS for w in words)

# Old-Style / New-Style double-date pattern for English colonial dates prior
# to 1752 (e.g., "1603/04", "1620/21", "1672/73", or single-digit-suffix
# forms "1717/8", "1696/7"). Under Old Style the year began March 25, so
# January-March events crossed the calendar boundary. Modern citation
# convention writes either year; vault canonical generally uses "OS/NS"
# form, prose may write either OS or NS.
DOUBLE_DATE_RE = re.compile(r"\b(1[5-7]\d{2})/(\d{1,2})\b")

# Full-year approximate ranges: "1896-1897", "1841/1842", "ABT 1826-1828",
# "b. 1853-1855". Both endpoints are full 4-digit years. These appear when a
# vital is known only to within a few years (declarant-age estimates, FS-vs-
# primary-source disagreement, sibling-cluster inference). A prose year that
# falls anywhere INSIDE the canonical range — or a canonical year inside a
# prose range — is not drift. Span is capped (<=12) so a birth-death lifespan
# like "1633-1693" is NOT collapsed into a single fuzzy range.
# Same widening as PROSE_YEAR_RE, and measured the same way: these two range
# scanners carried the identical 1500 floor, so a medieval "985-990" span was
# never recognised as a range at all.
_Y4 = r"(?:1\d{3}|20[0-2]\d)"
FULL_RANGE_RE = re.compile(rf"\b({_Y4})\s*[-/]\s*({_Y4})\b")
RANGE_SPAN_CAP = 12

def canonical_year_alts(raw_date_str, primary_year):
    """Return the set of valid years for matching, including the NS year of
    an OS/NS double-date and every year inside a full-year approximate range.
    Examples: "1603/04" → {1603, 1604}; "1717/8" → {1717, 1718};
    "1699/00" → {1699, 1700} (century rollover); "ABT 1826-1828" →
    {1826, 1827, 1828}; "1841/1842" → {1841, 1842}. For plain dates returns
    just {primary_year}."""
    alts = {primary_year} if primary_year else set()
    for m in DOUBLE_DATE_RE.finditer(raw_date_str or ""):
        os_year = int(m.group(1))
        suffix_str = m.group(2)
        # Reconstruct NS year by replacing the trailing len(suffix) digits
        # of os_year with the suffix. "1717" + "8" → keep "171", append "8"
        # → 1718. "1603" + "04" → keep "16", append "04" → 1604.
        keep = str(os_year)[: 4 - len(suffix_str)]
        ns_year = int(keep + suffix_str.zfill(len(suffix_str)))
        if ns_year <= os_year:
            ns_year += 10 ** len(suffix_str)  # century / decade rollover
        alts.add(os_year)
        alts.add(ns_year)
    for m in FULL_RANGE_RE.finditer(raw_date_str or ""):
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo <= hi <= lo + RANGE_SPAN_CAP:
            alts.update(range(lo, hi + 1))
    return alts

# ============================================================
# DATE_DRIFT — header vs field (spec/structured-dates Spec 06)
# ============================================================
# Before this lane a person's dates lived in ONE place, the header parenthetical.
# They now live in two: the `- meta:` FIELD (authoritative for machines — gates,
# sorting, matching, exports) and the header (authoritative for humans, and the
# only one that can carry "near Weymouth, MA", "killed in the war", "christened
# 3 SEP 1676"). That is exactly the drift integrity rule 7 exists to police, so it
# is gated rather than trusted.
#
# Compare YEARS, not strings. `3 SEP 1780` and `b. 3 SEP 1780, Boston` must agree;
# `ABT 1750` and `~1750` must agree. Only a genuine disagreement — both sides
# present and different — is drift. One side absent is COVERAGE, counted separately,
# because a missing field is a migration gap and a missing header is a display gap;
# neither is a contradiction.
DATE_DRIFT_COVERAGE = {"field_missing": 0, "header_missing": 0, "both_missing": 0}


def date_drift(rows):
    """Header-vs-field year disagreements. Returns prose_audit-shaped issue tuples."""
    for k in DATE_DRIFT_COVERAGE:
        DATE_DRIFT_COVERAGE[k] = 0
    out = []
    for r in rows:
        for slot in ("born", "died"):
            # `field_*` falls back to the header when the meta has no date key, so
            # ask the meta block itself whether the FIELD exists. Otherwise coverage
            # reports 0 gaps on a vault that has not been migrated at all.
            has_field = slot in (r.get("meta_date_keys") or ())
            field = r.get(f"field_{slot}") if has_field else None
            header = r.get(f"header_{slot}")
            fy = gdate.resolve_year(field) if field else None
            hy = gdate.resolve_year(header) if header else None
            if fy is None and hy is None:
                DATE_DRIFT_COVERAGE["both_missing"] += 1
            elif fy is None:
                DATE_DRIFT_COVERAGE["field_missing"] += 1
            elif hy is None:
                DATE_DRIFT_COVERAGE["header_missing"] += 1
            elif fy != hy:
                # An OS/NS dual header legitimately reads either year, so accept
                # both before calling it drift.
                if fy in canonical_year_alts(header, hy):
                    continue
                out.append((r.get("file") or "?", 0, "WARN", "DATE_DRIFT",
                            f"'{r['name']}' {slot} field says {fy}; header says {hy}"))
    return out


def normalize_name(name):
    n = re.sub(r"~~.*?~~", "", name)
    n = re.sub(r"\s*\([^)]*\)\s*", " ", n)
    n = re.sub(r"\*+", "", n)
    n = re.sub(r"\s+", " ", n).strip().lower()
    return n

def name_tokens(name):
    return {t for t in re.findall(r"\w{2,}", normalize_name(name))}

def build_canonical_map(rows):
    """
    Map: normalized-name -> list of rows (could be multiple for same-name people).
    For lookup, we'll match by token-set with year-proximity disambiguation.
    """
    m = defaultdict(list)
    for r in rows:
        m[normalize_name(r["name"])].append(r)
    return m

def build_pid_map(rows):
    """Map: FS PID -> row. Used to disambiguate when prose carries the PID
    explicitly (defeats name-regex boundary edge-cases like '**Giovanni Andrea
    Bianchi**' where the leading '**' blocks the lookbehind and the regex
    only matches the trailing 'Andrea Bianchi' substring)."""
    m = {}
    for r in rows:
        pid = r.get("pid")
        if pid and pid not in ("—", "(pending FS)", ""):
            m[pid] = r
    return m

# ============================================================
# Build relation map from Family_Tree.md tree diagram
# ============================================================

def build_relation_map():
    """
    Parse Family_Tree.md's ASCII tree diagram (lines 41-55) to determine
    each person's relationship to the subject.
    Returns: {normalized_name: relation_string} like "paternal grandmother"
    """
    path = os.path.join(VAULT, "Family_Tree.md")
    with open(path) as f:
        lines = f.readlines()

    # Find the tree-diagram block (between ``` and ```)
    in_block = False
    block_lines = []
    for line in lines:
        if line.strip() == "```":
            if in_block:
                break
            in_block = True
            continue
        if in_block:
            block_lines.append(line)

    # Parse tree by indent level
    # Each line has structure: [pipes-and-chars] Name (b. ..., d. ...)
    # The depth = number of branch chars (├ │ └ ─) before the name
    relations = {}
    # depth 0 = subject
    # depth 1 = parent (mother/father)
    # depth 2 = grandparent
    # depth 3 = great-grandparent
    # depth 4 = gg-grandparent
    relation_words = [
        "subject",
        "parent",
        "grandparent",
        "great-grandparent",
        "great-great-grandparent",
        "great-great-great-grandparent",
    ]

    # Track current parent at each depth to determine paternal/maternal
    # parent_side[1] = "father" or "mother" of subject
    # At depth >=2, the side is inherited from the depth-1 parent
    side_at_depth = {}

    for line in block_lines:
        # Count leading branch chars + spaces
        # Pattern: starts with some combination of │, ├, └, ─, spaces
        m = re.match(r"^([│├└─\s]*)(.+?)(?:\s*\(|\s*$)", line)
        if not m:
            continue
        prefix = m.group(1)
        name = m.group(2).strip()
        if not name or name.startswith("```"):
            continue
        # Skip empty / non-person lines
        if not re.match(r"^[A-ZÀ-Ý]", name):
            continue
        # Depth ≈ count of pipe-like chars including spaces, divided by 4
        # (each indent level adds 4 chars: "│   " or "    ")
        depth = len(prefix) // 4
        normalized = normalize_name(name)
        if depth == 0:
            # Subject (Gen 1)
            relations[normalized] = "subject"
            side_at_depth[0] = None
            continue
        # Determine side
        if depth == 1:
            # Parent
            # First-encountered Gen 2 = father by convention (father listed first)
            # Actually parse "father side" by tracking the first vs second Gen 2 entry
            if "father" not in side_at_depth.values():
                side = "paternal"
                side_at_depth[1] = "paternal"
            else:
                side = "maternal"
                side_at_depth[1] = "maternal"
            relations[normalized] = f"{side[:-2]}al parent" if False else (
                "father" if side == "paternal" else "mother"
            )
            # Reset side tracking for sub-tree
            current_side = side
        else:
            # Use last side_at_depth[1] context — but we need to track which
            # subtree we're in. Simpler: re-determine from the most recent
            # depth-1 ancestor by scanning back through lines.
            # For now, use a stack approach.
            pass
    # Re-parse with stack approach for proper side tracking.
    # Couple-safe (spec/multi-anchor-multi-repo Spec 02): the diagram may have TWO
    # depth-0 roots (an anchor couple, each with their own ancestry subtree). Father/
    # mother detection is tracked PER ROOT via root_parents, reset at each depth-0
    # line, so the second anchor's first parent is not mislabeled "mother" by a
    # global count. A single-root diagram behaves exactly as before.
    relations = {}
    stack = []  # list of (depth, name, side_to_pass_down)
    root_parents = 0  # depth-1 parents seen under the CURRENT depth-0 anchor
    for line in block_lines:
        m = re.match(r"^([│├└─\s]*)(.+?)(?:\s*\(|\s*$)", line)
        if not m:
            continue
        prefix = m.group(1)
        name = m.group(2).strip()
        if not name or name.startswith("```"):
            continue
        if not re.match(r"^[A-ZÀ-Ý]", name):
            continue
        depth = len(prefix) // 4
        normalized = normalize_name(name)
        # Pop stack to current depth
        while stack and stack[-1][0] >= depth:
            stack.pop()
        # Determine side
        if depth == 0:
            side = None
            rel = "subject"
            root_parents = 0  # new anchor root: restart father/mother tracking
        elif depth == 1:
            # First depth-1 child under THIS anchor = father; second = mother
            # (children listed father-first). Tracked per-root so a couple's two
            # subtrees do not cross-contaminate.
            if root_parents == 0:
                side = "paternal"
                rel = "father"
            else:
                side = "maternal"
                rel = "mother"
            root_parents += 1
        else:
            # Inherit side from parent (top of stack at depth-1)
            parent_side = None
            for d, _, s in reversed(stack):
                if d == depth - 1 and s:
                    parent_side = s
                    break
            side = parent_side
            # Determine relation by depth from subject
            if depth == 2:
                # Grandparent: first child = grandfather, second = grandmother
                # We need to know if we're processing the first or second child
                # of this parent. Use the prefix to tell: ├── = not-last child, └── = last child
                # The first ├── is a grandfather; the └── is grandmother
                if "├" in prefix:
                    rel = f"{side} grandfather"
                else:
                    rel = f"{side} grandmother"
            elif depth == 3:
                if "├" in prefix:
                    rel = f"{side} great-grandfather"
                else:
                    rel = f"{side} great-grandmother"
            elif depth == 4:
                if "├" in prefix:
                    rel = f"{side} great-great-grandfather"
                else:
                    rel = f"{side} great-great-grandmother"
            else:
                rel = f"{side} ancestor (depth {depth})"
        relations[normalized] = rel
        stack.append((depth, normalized, side))
    return relations

# ============================================================
# Extract claims from prose
# ============================================================

# Pattern A: inline person fact in parens
# Match: "Name (b. ..., d. ...)" or "Name (YYYY-YYYY)" or "Name (b. YEAR PLACE)"
# We require Name be 2+ capitalized tokens to avoid noise.
# The paren must contain a year OR "Deceased" OR "?" OR "unknown".
NAME_PAREN_RE = re.compile(
    r"(?<![*\w])"                                # left boundary, no preceding word/asterisk
    r"([A-ZÀ-Ý][\w\.\-'À-ÿ]+(?:\s+[\w\.\-'À-ÿ]+){1,7})"  # 2-8 word tokens, capitalized start
    r"\s*\(([^)]{1,300})\)"                      # paren content up to 300 chars
)

# Pattern B: "[relation] [Name]"
RELATION_WORDS = [
    "paternal grandmother", "paternal grandfather",
    "maternal grandmother", "maternal grandfather",
    "paternal great-grandmother", "paternal great-grandfather",
    "maternal great-grandmother", "maternal great-grandfather",
    "paternal great-great-grandmother", "paternal great-great-grandfather",
    "maternal great-great-grandmother", "maternal great-great-grandfather",
]
# Case-insensitive on the relation word but strict on the name (case-sensitive
# capital-letter start) — without IGNORECASE on [A-Z] we'd miss "Paternal Grandmother"
# at sentence start. Use explicit lower+title alternation for the relation word.
_rel_alt = "|".join(re.escape(w) for w in RELATION_WORDS) + "|" + \
           "|".join(re.escape(w.title()) for w in RELATION_WORDS)
RELATION_RE = re.compile(
    r"\b(" + _rel_alt + r")\s+"
    r"(?!of\s|to\s|for\s|in\s|via\s|as\s|with\s|from\s|by\s|on\s|line\b|side\b|cluster\b|pattern\b)"
    r"([A-ZÀ-Ý][\w\.\-'À-ÿ]+(?:\s+[\w\.\-'À-ÿ]+){1,5})",
)

# Pattern C: Generation N (her X generation) — also handle plural+apostrophe-s
GEN_RELATION_RE = re.compile(
    r"Generation\s+(\d+)\s*\(\s*(his|her|their|the)\s+([\w\-'’]+(?:\s+[\w\-'’]+){0,4})\s+generation\s*[\)—]",
    re.IGNORECASE,
)

# Pattern D: death-unknown placeholder
DEATH_UNKNOWN_RE = re.compile(
    r"([A-ZÀ-Ý][\w\.\-'À-ÿ]+(?:\s+[\w\.\-'À-ÿ]+){1,7})"
    r"\s*\([^)]*?\bd\.\s*(\?|unknown|tbd|todo|unk)\b[^)]*\)",
    re.IGNORECASE,
)

# Generation relation-word mapping (in terms of generations above subject)
GEN_FROM_RELATION = {
    "parent": 1, "father": 1, "mother": 1,
    "grandparent": 2, "grandfather": 2, "grandmother": 2,
    "great-grandparent": 3, "great-grandfather": 3, "great-grandmother": 3,
    "great-great-grandparent": 4, "great-great-grandfather": 4, "great-great-grandmother": 4,
    "great-great-great-grandparent": 5,
}
# Mapping to vault Gen number from the subject's perspective
# Subject = Gen 1, parents = Gen 2, etc.

def gen_for_relation(rel_word, subject_gen=1):
    """Convert a relationship descriptor to absolute generation number."""
    n = GEN_FROM_RELATION.get(rel_word.lower())
    return subject_gen + n if n else None

# ============================================================
# Main check loop
# ============================================================

def main(argv=None):
    # DATE_DRIFT was advisory at first landing (spec/structured-dates Spec 06) and
    # is BLOCKING as of 22 JUL 2026, the promotion the spec called for once the
    # baseline was 0 and the Spec 04 residue was triaged. It is the only blocking
    # metric in this script: prose ERROR/WARN stay advisory, because they judge
    # PROSE, which a human writes and may legitimately phrase loosely. A DATE_DRIFT
    # finding is different in kind — two machine-readable copies of one fact
    # disagreeing on the year, where one of them is simply wrong.
    strict_dates = "--no-strict-dates" not in (argv if argv is not None else sys.argv[1:])
    rows = parse_person_index()
    canon = build_canonical_map(rows)
    pid_map = build_pid_map(rows)
    relations = build_relation_map()
    # Also build a name -> generation lookup for non-direct relatives
    name_to_gen = {}
    for r in rows:
        n = normalize_name(r["name"])
        if n not in name_to_gen and r["gen"]:
            name_to_gen[n] = r["gen"]

    print(f"Canonical narrative entries:    {len(rows)}", file=sys.stderr)
    print(f"Family-tree direct relations:   {len(relations)}", file=sys.stderr)

    issues = []  # list of (file, lineno, severity, kind, message)

    for path in sorted(glob.glob(os.path.join(VAULT, "**/*.md"), recursive=True)):
        fname = os.path.relpath(path, VAULT)
        # Skip session logs (historical research notes — by design they record
        # what was known at that time and shouldn't be updated when canonical
        # facts evolve).
        if fname.startswith("logs/"):
            continue
        # Skip *_Archive/ snapshot dirs (Open_Questions_Archive, Handoff_Archive,
        # Research_Log_Archive). These are write-once timestamped snapshots produced by
        # scripts/archive_sections.py; same rationale as logs/ — they record the file's
        # state at archive time and must not be rewritten when canonical facts evolve.
        # Without this, every snapshot duplicates the live file's drift findings.
        if "_Archive/" in fname:
            continue
        # Skip templates
        if fname.startswith("templates/"):
            continue
        # Research_Log.md is a write-once dated research journal (a table of
        # "what was searched/found on date X"), same rationale as logs/: its
        # rows record the working estimates of their day and must not be
        # rewritten when canonical facts later evolve. Excluded from prose
        # drift checks.
        if fname == "Research_Log.md":
            continue
        # findagrave_audit.md is a write-once tracking TABLE (one row per person,
        # recording the value found on the source side — e.g. a Find a Grave
        # headstone year that intentionally differs from the canonical estimate,
        # which is the whole point of recording it). Same rationale as logs/ and
        # Research_Log.md; also, person-name strings in this table carry
        # parenthetical disambiguators (e.g. "wife of Jan b.1893") that the year
        # regex mis-attributes. Excluded from prose drift checks.
        if fname == "findagrave_audit.md":
            continue
        with open(path) as f:
            content = f.read()

        # ---------- CLAIM 3: relation-claim drift ----------
        STOP_WORDS = {"was", "is", "who", "the", "and", "or", "but", "a", "an",
                      "her", "his", "their", "of", "to", "for", "in", "on", "at",
                      "ancestral", "cluster", "line", "side", "branch", "lineage",
                      "daughter", "son", "wife", "husband", "mother", "father",
                      "had", "has", "have", "were", "being", "been",
                      "via", "by", "as", "with", "from"}
        for m in RELATION_RE.finditer(content):
            rel_word = m.group(1).strip().lower()
            raw_name = m.group(2).strip()
            # Truncate at first stop-word; strip apostrophe-s but keep the token
            name_tokens_list = []
            for tok in raw_name.split():
                base_tok = tok.lower().rstrip(".,;:")
                if base_tok in STOP_WORDS:
                    break
                # Strip possessive '-s' but keep the token as part of the name
                cleaned = re.sub(r"[’']s$", "", tok)
                name_tokens_list.append(cleaned)
                if tok.endswith("'s") or tok.endswith("’s"):
                    # Apostrophe-s usually marks end of a name (X's daughter, X's line)
                    break
            if len(name_tokens_list) < 2:
                continue
            claimed_name = " ".join(name_tokens_list)
            claimed_norm = normalize_name(claimed_name)
            lineno = content[:m.start()].count("\n") + 1
            # Check if there's a possessive prefix within ~50 chars before the
            # relation word — if yes, this is a relation-to-someone-else claim
            # (e.g., "Cecily's paternal grandmother Isabel of Cambridge")
            pre_ctx = content[max(0, m.start() - 60):m.start()]
            has_possessive_subject = bool(re.search(r"\b\w+(?:’s|'s)\s*$", pre_ctx))
            if has_possessive_subject:
                continue
            # Check if the claimed name matches a canonical person whose relation
            # to subject MATCHES the relation word
            actual_rel = relations.get(claimed_norm)
            if actual_rel is None:
                # Person not in direct-line tree
                if claimed_norm not in canon:
                    issues.append((fname, lineno, "WARN", "unknown-person-in-relation-claim",
                                   f"'{rel_word} {claimed_name}' — no canonical entry for this name"))
                else:
                    # Person IS in canonical but isn't a direct-line ancestor in
                    # any relation — yet prose claims they're [rel_word] (with no
                    # possessive subject before). This is the misattributed-relation bug.
                    issues.append((fname, lineno, "ERROR", "wrong-direct-line-relation",
                                   f"'{rel_word} {claimed_name}' — claimed as the subject's direct-line {rel_word}, but person is not in canonical direct tree"))
                continue
            # Compare claimed relation to actual
            if actual_rel.lower() != rel_word.lower():
                issues.append((fname, lineno, "ERROR", "wrong-relation",
                               f"'{rel_word} {claimed_name}' — actual relation to subject is '{actual_rel}'"))

        # ---------- CLAIM 4: generation-relation mismatch ----------
        for m in GEN_RELATION_RE.finditer(content):
            n = int(m.group(1))
            possessive = m.group(2).lower()
            rel_desc = m.group(3).strip().lower()
            lineno = content[:m.start()].count("\n") + 1
            # Compute what Gen N should mean for the possessive subject
            # If possessive = "her", subject is implied (e.g., Jane Smith => Gen 2)
            # Default to the subject (Gen 1) unless we can determine otherwise.
            # Strip "great-" prefixes + plural/apostrophe to find base relation word
            base = rel_desc.replace("'s", "").replace("’s", "").strip()
            base = re.sub(r"s\b", "", base).strip()  # plural → singular
            expected_n = GEN_FROM_RELATION.get(base)
            if expected_n is None:
                continue
            # Check several possible implied subjects: the subject (Gen 1), a
            # Gen-2 parent (so "<parent>'s grandparents" = Gen 4), or a Gen-3 anchor.
            possible = []
            for subj_gen, subj_name in [(1, "subject"), (2, "subject's parents"), (3, "Gen 3 anc")]:
                if n == subj_gen + expected_n:
                    possible.append(subj_name)
            if not possible:
                # Mismatch
                inferred_gen = f"subject Gen 1: Gen {1+expected_n} | subject Gen 2: Gen {2+expected_n}"
                issues.append((fname, lineno, "WARN", "generation-relation-mismatch",
                               f"'Generation {n} ({possessive} {rel_desc} generation)' — for that descriptor, expected: {inferred_gen}"))

        # ---------- CLAIM 1+2: inline person fact / death-unknown ----------
        # Only scan prose contexts (skip lines that look like canonical bold-name entries
        # in Family_Tree files, since those ARE the canonical source for those files)
        is_family_tree_file = re.match(r"Family_Tree(_.*)?\.md$", os.path.basename(path))
        for m in NAME_PAREN_RE.finditer(content):
            name = m.group(1).strip()
            paren = m.group(2).strip()
            lineno = content[:m.start()].count("\n") + 1
            # If we're in a Family_Tree file and this looks like a bold-name entry
            # header (line starts with ** or - **), skip it
            line_start = content.rfind("\n", 0, m.start()) + 1
            line_text = content[line_start:m.start()]
            if is_family_tree_file and ("**" in line_text and line_text.rstrip().endswith("**")):
                continue
            # Skip if no year in paren (probably not a person-fact claim)
            paren_year = extract_year(paren)
            if not paren_year:
                continue
            # PID disambiguation: if the paren carries an FS PID, that is the
            # authoritative identifier. This defeats name-regex boundary
            # artifacts (e.g., '**Giovanni Andrea Bianchi**' where the
            # leading '**' blocks lookbehind and the regex only captures
            # the trailing 'Andrea Bianchi' substring — which would
            # otherwise match a different canonical row of the same trailing
            # name).
            matched = None
            paren_pid_m = PID_RE.search(paren)
            paren_pid = paren_pid_m.group(1) if paren_pid_m else None
            if paren_pid:
                matched = pid_map.get(paren_pid)
            if matched is None:
                # No PID, or PID not in canonical. Fall back to name lookup.
                norm = normalize_name(name)
                if norm not in canon:
                    continue  # not a known person; skip
                candidates = canon[norm]
                # Pick BEST match by smallest year diff (not first-within-tolerance).
                # Needed when multiple canonical rows share a normalized name AND
                # have years within tolerance — e.g., the infant Domenico
                # Rossi b.1883 vs cousin b.1886; prose year-range 1883-1885
                # should match the infant (diff=0) not the cousin (diff=3).
                best_diff = None
                for c in candidates:
                    cy = c["born_year"] or c["died_year"]
                    if cy is None:
                        continue
                    d = abs(cy - paren_year)
                    if d <= 5 and (best_diff is None or d < best_diff):
                        matched = c
                        best_diff = d
                if not matched:
                    # Multi-candidate same-name case: don't flag drift; this is
                    # likely a different person sharing a name (Robert Morgan Sr.
                    # vs Robert Morgan (immigrant), Thomas Bill Sr. vs Thomas Bill Jr.)
                    continue
                # Homonym-collision guard: the prose parenthetical carries an
                # explicit FS PID that is NOT in the canonical index, and it
                # differs from the PID of the row we matched by name. That means
                # the parenthetical describes a DIFFERENT person (one not yet
                # promoted to Person_Index) who happens to share a name with a
                # canonical entry — e.g. adult Filippo Rossi AAAA-AAA matched to
                # infant Filippo BBBB-BBB, or the 2nd-namesake Martino Verdi
                # CCCC-CCC matched to the 3rd-namesake direct ancestor DDDD-DDD.
                # Comparing their years would be a false positive.
                if paren_pid and matched.get("pid") and paren_pid != matched["pid"]:
                    continue
            # Compare born year
            paren_born = None
            paren_died = None
            born_m = re.search(r"\bb\.\s*([^,;)]+)", paren)
            died_m = re.search(r"\bd\.\s*([^,;)]+)", paren)
            if born_m:
                paren_born = extract_year(born_m.group(1))
            if died_m:
                paren_died = extract_year(died_m.group(1))
            # If paren is just "(YYYY-YYYY)" parse that
            if not paren_born and not paren_died:
                range_m = re.match(rf"^\s*({_Y4})\s*[-–]\s*({_Y4})\s*$", paren)
                if range_m:
                    paren_born = int(range_m.group(1))
                    paren_died = int(range_m.group(2))
            canon_born_alts = canonical_year_alts(matched.get("born"), matched["born_year"])
            canon_died_alts = canonical_year_alts(matched.get("died"), matched["died_year"])
            # Also expand prose-side double-dates (e.g., prose says
            # "b. 2 JAN 1589/90" → accept either 1589 or 1590 against canonical)
            prose_born_alts = canonical_year_alts(born_m.group(1) if born_m else "", paren_born) if paren_born else set()
            prose_died_alts = canonical_year_alts(died_m.group(1) if died_m else "", paren_died) if paren_died else set()
            # No drift if prose's accepted years and canonical's accepted years
            # overlap; only flag when they're disjoint.
            if paren_born and matched["born_year"] and not (prose_born_alts & canon_born_alts):
                issues.append((fname, lineno, "ERROR", "born-year-drift",
                               f"'{name}' prose says b.{paren_born}; canonical narrative says b.{matched['born_year']}"))
            if paren_died and matched["died_year"] and not (prose_died_alts & canon_died_alts):
                issues.append((fname, lineno, "ERROR", "died-year-drift",
                               f"'{name}' prose says d.{paren_died}; canonical says d.{matched['died_year']}"))
            # Check for place mismatch — extract place from "b. YEAR, PLACE" pattern
            born_place_m = re.search(r"\bb\.\s*[\d\s\.\?A-Za-z]+,\s*([A-Z][^,;)]+)", paren)
            if born_place_m and matched["born"]:
                claimed_place = born_place_m.group(1).strip()
                # Reduce to first non-place token (e.g., "Springfield" vs "Springfield, MA")
                claimed_short = claimed_place.split(",")[0].strip()
                # Extract the canonical PLACE. Canonical Born is formatted
                # "DATE, PLACE, STATE" (e.g. "DEC 1651, Salem, MA"), so the place
                # is NOT split(",")[0] (that's the date) — it's the first
                # comma-segment that actually names a place. Many canonical Born
                # cells carry ONLY a date ("ABT 1640", "bef. 9 OCT 1774") with no
                # place at all; in that case there is nothing to compare and we
                # must not flag (this was the source of ~all born-place-drift
                # false positives).
                canon_place = None
                for seg in matched["born"].split(","):
                    if _segment_names_place(seg):
                        canon_place = seg.strip()
                        break
                # Skip artifacts: prose "place" that is actually (or contains) an
                # FS PID captured by the regex — bare "XXXX-XXX", or the common
                # "FS XXXX-XXX" / "FS PID XXXX-XXX" / "FS: XXXX-XXX" forms where
                # the parenthetical gave the PID in place of (or before) a place.
                claimed_is_pid = (bool(PID_RE.search(claimed_short))
                                  or bool(re.match(r"(?i)\s*FS\b", claimed_short)))
                claimed_norm = _norm_place(claimed_short)
                canon_norm = _norm_place(canon_place)
                # Consistency guard: if the canonical place name appears ANYWHERE
                # in the prose parenthetical, the prose is consistent (it either
                # names the same place, or is MORE specific — "Hamlet,
                # Sample Town" — or the place-regex simply grabbed an
                # adjacent region token: "b. 1844 Newtown, Sampleshire" where
                # the town "Newtown" matches but the regex captured the trailing
                # "Sampleshire"). Only a genuinely different place omits the
                # canonical name entirely.
                paren_has_canon = bool(canon_norm) and canon_norm in _norm_place(paren)
                if (canon_place and claimed_short and not claimed_is_pid
                        and not paren_has_canon
                        and _segment_names_place(claimed_short)
                        and claimed_norm != canon_norm):
                    # Only flag if neither is a substring of the other (avoid false positives)
                    if claimed_norm not in canon_norm and canon_norm not in claimed_norm:
                        issues.append((fname, lineno, "WARN", "born-place-drift",
                                       f"'{name}' prose b. place: '{claimed_short}'; canonical: '{canon_place}'"))

        # ---------- CLAIM 5: death-unknown when canonical has a date ----------
        for m in DEATH_UNKNOWN_RE.finditer(content):
            name = m.group(1).strip()
            lineno = content[:m.start()].count("\n") + 1
            norm = normalize_name(name)
            if norm not in canon:
                continue
            for c in canon[norm]:
                if c["died_year"]:
                    issues.append((fname, lineno, "ERROR", "stale-death-unknown",
                                   f"'{name}' prose says d. unknown/? but canonical has d.{c['died_year']}"))
                    break

    # (The former CLAIM 5 — Person_Index Notes-column-bloat — was removed when
    # Person_Index.md was retired; there is no Notes column to police.)

    # DATE_DRIFT (spec/structured-dates Spec 06) — the gate for the two-store
    # model this lane introduced. Advisory, and appended after the prose checks so
    # it shares their report.
    issues.extend(date_drift(rows))

    # Report
    by_severity = defaultdict(list)
    for i in issues:
        by_severity[i[2]].append(i)

    print(f"\n=== SUMMARY ===")
    print(f"  ERROR issues:  {len(by_severity['ERROR'])}")
    print(f"  WARN issues:   {len(by_severity['WARN'])}")
    dd = [i for i in issues if i[3] == "DATE_DRIFT"]
    cov = DATE_DRIFT_COVERAGE
    print(f"  DATE_DRIFT:    {len(dd)}   "
          f"[{'BLOCKING' if strict_dates else 'advisory (--no-strict-dates)'}]"
          f"  (coverage: field missing {cov['field_missing']}, "
          f"header missing {cov['header_missing']}, neither {cov['both_missing']})")

    for sev in ("ERROR", "WARN"):
        if not by_severity[sev]:
            continue
        print(f"\n=== {sev} ({len(by_severity[sev])}) ===")
        for fname, lineno, _, kind, msg in by_severity[sev]:
            print(f"  {fname}:{lineno} [{kind}] {msg}")

    if dd and strict_dates:
        print(f"\nDATE_DRIFT is BLOCKING: {len(dd)} header/field date disagreement(s).",
              file=sys.stderr)
        print("Fix the wrong side (the meta FIELD is authoritative for machines, the "
              "header for humans), and update any prose that paraphrases it in the same "
              "commit — integrity rule 7. Override for one run with --no-strict-dates.",
              file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
