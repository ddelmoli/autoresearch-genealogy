#!/usr/bin/env python3
"""
migrate_meta_v3.py — one-shot migration of every `- meta:` block from the legacy
`;`-delimited grammar to the v3 YAML flow-mapping with upstream-aligned vocabulary.

  legacy:  - meta: id: P-7K3QM2; FS: XXXX-XXX; tier: S; gen: 6
  v3:      - meta: {id: P-7K3QM2, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 6, fs: XXXX-XXX}

Field mapping (operator decisions 24 JUN 2026):
  id        -> id                       (unchanged; primary key)
  tier S/M/Sp -> evidence_tier strong_signal / moderate_signal / speculative
  tier U      -> (no evidence_tier)     + profile_status: stub  (U conflated
                 completeness with quality; v3 splits them, per upstream)
  gen N     -> generation: N
  FS pid    -> fs: pid                  (lowercase key; TBD/none preserved)
  (new) profile_status: complete | partial | stub
        complete = entry body has an "FS-attached sources" bullet
        partial  = has an evidence_tier (S/M/Sp) but no sources bullet
        stub     = otherwise (was tier U / thin collateral)
  (new) life_status: living | deceased | unknown   (110-year presumption)
        living   = header carries a delimited "living" status token
        deceased = header has a death date OR born > 110 yr ago (< 1916)
        unknown  = otherwise

The format is VALID YAML (yaml.safe_load reads it); current field values are
simple tokens needing no quoting. Idempotent: lines already in `{...}` form are
skipped. Dry-run by default; --apply writes a per-file .bak.
"""
import re, glob, os, sys, argparse
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import gen_person_index as G
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
META_LINE = re.compile(r"^(\s*-\s*meta:\s*)(.+?)\s*$", re.I)
BOLD = re.compile(r"^\s*[-*]*\s*\*\*(.+?)\*\*(.*)$")
HEADING = re.compile(r"^#{1,6}\s")
YEAR = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")
# A living-status token in the header: the word "living" (incl. **living**, or
# "possibly/probably/still living"), but NOT a residence mention ("living 1851
# at Kingsholm", "living in Boston"). Privacy-first: when in doubt, prefer living.
LIVING_WORD = re.compile(r"\bliving\b", re.I)
LIVING_NOT = re.compile(r"\s+(?:\d|at\b|in\b|with\b|near\b|until\b)", re.I)
TIER_FULL = {"S": "strong_signal", "M": "moderate_signal", "Sp": "speculative"}
LIVENESS_CUTOFF = 1916   # 2026 - 110


def parse_legacy(raw):
    out = {}
    for part in raw.split(";"):
        k, _, v = part.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k and v:
            out[k] = v
    return out


def body_has_sources(lines, i):
    """True if the entry whose meta is at line i has an FS-attached-sources bullet
    before the next entry boundary (next meta line or next heading)."""
    for j in range(i + 1, min(i + 60, len(lines))):
        l = lines[j]
        if META_LINE.match(l) or HEADING.match(l):
            break
        if "FS-attached sources" in l:
            return True
    return False


def life_status(header):
    # The life-status token lives in the FIRST vitals parenthetical, e.g.
    # "(1952, MA; living; FS …)" — NOT the trailing prose (where "living parents"
    # / "living at X" would false-positive). Restrict the scan to that paren.
    paren = G._vitals_paren("", header)
    p = paren.replace("*", "")           # so **living** is seen
    m = LIVING_WORD.search(p)
    if m and not LIVING_NOT.match(p[m.end():]):
        return "living"                  # explicit / possibly living -> privacy-safe
    born, died = G.parse_vitals(paren)
    if died.strip():
        return "deceased"
    yrs = [int(y) for y in YEAR.findall(born)]
    if yrs and min(yrs) < LIVENESS_CUTOFF:
        return "deceased"
    return "unknown"


def build_v3(meta, header, has_sources):
    fields = []
    fields.append(("id", meta.get("id")))
    tier = meta.get("tier")
    etier = TIER_FULL.get(tier)            # U / absent -> None
    if etier:
        fields.append(("evidence_tier", etier))
    # profile_status
    if has_sources:
        prof = "complete"
    elif etier:
        prof = "partial"
    else:
        prof = "stub"
    fields.append(("profile_status", prof))
    fields.append(("life_status", life_status(header)))
    gen = meta.get("gen")
    if gen and gen.lstrip("-").isdigit():
        fields.append(("generation", int(gen)))
    fs = meta.get("fs")
    if fs:
        fields.append(("fs", fs))
    inner = ", ".join(f"{k}: {v}" for k, v in fields if v is not None)
    return "{" + inner + "}", prof, life_status(header), etier


def migrate_file(path, apply):
    lines = open(path).read().split("\n")
    last_header = ""
    changed = 0
    counts = Counter()
    for i, line in enumerate(lines):
        bm = BOLD.match(line)
        if bm and not META_LINE.match(line):
            last_header = bm.group(1) + bm.group(2)
        m = META_LINE.match(line)
        if not m:
            continue
        raw = m.group(2).strip()
        if raw.startswith("{"):            # already v3
            counts["already_v3"] += 1
            continue
        meta = parse_legacy(raw)
        v3, prof, life, etier = build_v3(meta, last_header, body_has_sources(lines, i))
        lines[i] = m.group(1) + v3
        changed += 1
        counts[f"profile:{prof}"] += 1
        counts[f"life:{life}"] += 1
        counts[f"tier:{etier or 'none'}"] += 1
    if apply and changed:
        import shutil
        shutil.copy2(path, path + ".bak")
        open(path, "w").write("\n".join(lines))
    return changed, counts


def main():
    vault_config.require_vault(VAULT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--file", help="limit to one file (basename)")
    args = ap.parse_args()
    total = 0
    agg = Counter()
    files = sorted(glob.glob(os.path.join(VAULT, "Family_Tree*.md")))
    if args.file:
        files = [f for f in files if os.path.basename(f) == args.file]
    for path in files:
        changed, counts = migrate_file(path, args.apply)
        total += changed
        agg.update(counts)
        if changed:
            print(f"{'APPLIED' if args.apply else 'would change'} {changed:>4}  {os.path.basename(path)}")
    print(f"\n{'APPLIED' if args.apply else 'DRY-RUN'} total: {total} meta blocks")
    print("  profile_status:", {k.split(':')[1]: v for k, v in sorted(agg.items()) if k.startswith('profile:')})
    print("  life_status:   ", {k.split(':')[1]: v for k, v in sorted(agg.items()) if k.startswith('life:')})
    print("  evidence_tier: ", {k.split(':')[1]: v for k, v in sorted(agg.items()) if k.startswith('tier:')})
    if agg.get("already_v3"):
        print(f"  already v3 (skipped): {agg['already_v3']}")


if __name__ == "__main__":
    main()
