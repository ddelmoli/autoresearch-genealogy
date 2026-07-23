#!/usr/bin/env python3
"""migrate_sources.py — Spec 03 (multi-anchor-multi-repo) source-bullet migration.

Rewrites legacy `- **FS-attached sources** (...): LOC1, LOC2, ...` bullets into the
record / host:locator grammar:

    - **Sources** (...):
      - <descriptor?> — fs:1:1:AAAA-AAA
      - <descriptor?> — antenati:ark:/12657/..., fs:3:1:BBBB-CCCC   (multi-host record)

Approach b (chosen): Phase A is mechanical and NON-DESTRUCTIVE.
  - Relabel `FS-attached sources` -> `Sources` (host-neutral).
  - Host-prefix every locator (host derived from the token form).
  - Default ONE record per locator, EXCEPT auto-merge high-confidence pairs:
      * persona/household: `persona <LOC>` + `household <LOC>` on the same census
        -> one record, two locators.
      * index/image: an explicit "index ... image ... (same act)" marker (conservative;
        anything less certain is left split + flagged, never silently merged).
  - STRUCTURED bullets (a comma/semicolon list of locators, each optionally trailed
    by a short `(descriptor)`) become clean record sub-bullets.
  - FREEFORM bullets (emoji, multiple sentences, prose) are migrated minimally: their
    locators become one-record-per-line sub-bullets and the ORIGINAL text is preserved
    verbatim as a `- note (pre-migration): ...` line, then the bullet is FLAGGED for a
    human Phase B pass to re-attach descriptors / confirm merges. No data is lost.

Modes:
  (default)   dry-run: per-file plan, the flagged list, and before/after record counts.
  --apply     write the changes.
  --file NAME limit to one Family_Tree file (basename).
Idempotent: a bullet already in `**Sources**` sub-bullet form is left untouched, so it
is safe to run repeatedly during the dual-label transition.

Coverage is never reduced: record_count(after) == distinct-locator-count(before) minus
only the confidently auto-merged pairs. harvest_sources.count_records verifies this.
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config
import harvest_sources as H

# A legacy source bullet (single line). Variants of the label are accepted; the
# payload is everything after the optional `(annotation)` and colon.
SOURCE_BULLET_RE = re.compile(
    r"^(?P<indent>[ \t]*)-[ \t]+\*\*(?P<label>FS[- ]attached sources?|FamilySearch sources?|Sources?)\*\*"
    r"(?P<ann>[ \t]*\([^)\n]*\))?[ \t]*:?[ \t]*(?P<payload>.*)$"
)

# Markers that make a bullet FREEFORM (unsafe to parse into clean descriptors).
FREEFORM_MARKERS = re.compile(r"[✅⛔🟢🔴⚠️]|(?:\.\s+[A-Z])|(?:\bindexed?\b.*\bimage\b)", re.IGNORECASE)

# Merge-hint keywords: a STRUCTURED bullet mentioning these MIGHT contain a
# same-record locator pair we did not auto-merge, so flag it for Phase B review.
# A plain flat list of distinct life-event ARKs (no such keyword) is correctly
# one-record-per-locator and is NOT flagged (avoids flagging most of the vault).
MERGE_HINT_RE = re.compile(r"\b(persona|household|index|image|same (?:act|record|atto|event)|duplicate)\b", re.IGNORECASE)

# persona/household high-confidence merge: capture the two locators.
PERSONA_HH_RE = re.compile(
    r"persona[^0-9A-Za-z]{0,4}(?P<p>(?:ark:/61903/)?1:1:[A-Z0-9-]+)[^)]*?household[^0-9A-Za-z]{0,4}(?P<h>(?:ark:/61903/)?1:1:[A-Z0-9-]+)",
    re.IGNORECASE)


def host_prefix(host_id: str) -> str:
    """Short host prefix the grammar emits for a given internal host id."""
    return {"familysearch": "fs"}.get(host_id, host_id)


def locator_token(host_id: str, loc: str) -> str:
    """Render a `host:locator` token, preserving the locator's namespace
    (`1:1:`/`3:1:`/`ark:/...`) so harvest_sources.extract_arks can still count it."""
    return f"{host_prefix(host_id)}:{loc}"


def find_locators(text: str):
    """Return [(start, end, host_id, loc)] for every legacy locator in text, in
    source order, non-overlapping. `loc` is the FULL canonical locator (with its
    `1:1:`/`3:1:`/`ark:/12657/` namespace), NOT just the id group, so the migrated
    `host:loc` token remains recountable by extract_arks."""
    hits = []
    for pidx, (pat, host, _kind) in enumerate(H.HOST_LOCATOR_PATTERNS):
        for m in pat.finditer(text):
            g1 = m.group(1)
            if pidx in (0, 1):
                loc = "1:1:" + g1                 # FS indexed record
            elif pidx == 2:
                loc = "3:1:" + g1                 # FS register image
            elif pidx == 3:
                loc = "1:1:" + g1                 # bare "FS ARK <pid>" -> assume indexed (rare legacy form)
            elif pidx == 4:
                loc = "ark:/12657/" + g1          # Antenati
            else:
                loc = g1                          # metryki / szukajwarchiwach / agad: full URL or filename
            hits.append((m.start(), m.end(), host, loc))
    hits.sort()
    out, last_end = [], -1
    for s, e, host, loc in hits:
        if s >= last_end:
            out.append((s, e, host, loc))
            last_end = e
    return out


def already_migrated(lines, idx):
    """True if the `**Sources**` bullet at lines[idx] is already followed by
    host-prefixed record sub-bullets (idempotency guard)."""
    for j in range(idx + 1, min(idx + 4, len(lines))):
        if H.HOST_LOC_RE.search(lines[j]):
            return True
        if lines[j].strip() and not lines[j].lstrip().startswith("-"):
            break
    return False


def migrate_bullet(line: str):
    """Migrate one legacy single-line source bullet.

    Returns (new_lines, n_records, n_locators, flagged, reason) or None if the
    line is not a source bullet. new_lines is a list of output lines."""
    m = SOURCE_BULLET_RE.match(line)
    if not m:
        return None
    indent = m.group("indent")
    ann = (m.group("ann") or "").strip()
    payload = m.group("payload")
    label_is_sources = m.group("label").lower().startswith("source")

    locs = find_locators(payload)
    if not locs:
        # A `**Sources**`/`**FS-attached sources**` bullet with no locators: just
        # relabel (nothing to restructure).
        head = f"{indent}- **Sources**" + (f" {ann}" if ann else "") + (":" if payload.strip() else "")
        tail = f" {payload.strip()}" if payload.strip() else ""
        return ([head + tail], 0, 0, False, "no-locators"),

    freeform = bool(FREEFORM_MARKERS.search(payload))
    n_locators = len(locs)

    # --- build records ---
    records = []  # each: (descriptor_or_None, [locator_token, ...])
    used = set()

    # Auto-merge persona/household pairs first (high confidence).
    merged_pairs = 0
    for pm in PERSONA_HH_RE.finditer(payload):
        p_id = re.sub(r"^ark:/61903/", "", pm.group("p"))
        h_id = re.sub(r"^ark:/61903/", "", pm.group("h"))
        toks = []
        for (s, e, host, loc) in locs:
            if loc in (p_id, h_id) and (s, e) not in used:
                toks.append(locator_token(host, loc))
                used.add((s, e))
        if len(toks) == 2:
            records.append(("census (persona + household)", toks))
            merged_pairs += 1

    if freeform:
        # Minimal, lossless: one record per remaining locator, no invented
        # descriptor; original prose preserved as a note, flagged for Phase B.
        for (s, e, host, loc) in locs:
            if (s, e) in used:
                continue
            records.append((None, [locator_token(host, loc)]))
        head = f"{indent}- **Sources**" + (f" {ann}" if ann else "") + ":"
        out = [head]
        for desc, toks in records:
            body = ", ".join(toks)
            out.append(f"{indent}  - " + (f"{desc} — {body}" if desc else body))
        out.append(f"{indent}  - note (pre-migration, Phase B: re-attach descriptors): {payload.strip()}")
        return (out, len(records), n_locators, True, "freeform"),

    # STRUCTURED: split payload on top-level commas/semicolons; each chunk is a
    # locator optionally trailed by a `(descriptor)` or a `**bold descriptor**`.
    for (s, e, host, loc) in locs:
        if (s, e) in used:
            continue
        # descriptor: a parenthetical or bold immediately AFTER this locator, up
        # to the next locator or delimiter.
        rest = payload[e:e + 120]
        dm = re.match(r"\s*\((?P<d>[^)]{1,80})\)", rest) or re.match(r"\s*\*\*(?P<d>[^*]{1,80})\*\*", rest)
        desc = dm.group("d").strip() if dm else None
        records.append((desc, [locator_token(host, loc)]))

    # order records by their first appearance in payload
    head = f"{indent}- **Sources**" + (f" {ann}" if ann else "") + ":"
    out = [head]
    for desc, toks in records:
        body = ", ".join(toks)
        out.append(f"{indent}  - " + (f"{desc} — {body}" if desc else body))
    # Flag ONLY structured bullets that mention a merge concept (persona/household,
    # index/image, same-act) yet auto-merged nothing — those may hide a same-record
    # pair for Phase B. Plain flat lists of distinct life-event ARKs are not flagged.
    soft_flag = bool(MERGE_HINT_RE.search(payload)) and merged_pairs == 0
    return (out, len(records), n_locators, soft_flag, "structured"),


def migrate_text(text: str):
    """Migrate all legacy source bullets in a file's text. Returns
    (new_text, stats) where stats has per-bullet outcomes."""
    lines = text.splitlines()
    out_lines = []
    stats = {"bullets": 0, "records": 0, "locators": 0, "merged_pairs": 0,
             "flagged": [], "relabeled": 0}
    i = 0
    while i < len(lines):
        line = lines[i]
        m = SOURCE_BULLET_RE.match(line)
        if m and m.group("label").lower().startswith("source") and already_migrated(lines, i):
            out_lines.append(line)  # idempotent: already-migrated Sources bullet
            i += 1
            continue
        res = migrate_bullet(line)
        if res is None:
            out_lines.append(line)
            i += 1
            continue
        (new_lines, nrec, nloc, flagged, reason), = res
        stats["bullets"] += 1
        stats["records"] += nrec
        stats["locators"] += nloc
        stats["relabeled"] += 1
        if reason == "freeform" or (flagged and reason == "structured"):
            stats["flagged"].append((i + 1, reason, line.strip()[:100]))
        out_lines.extend(new_lines)
        i += 1
    new_text = "\n".join(out_lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, stats


def main():
    ap = argparse.ArgumentParser(description="Spec 03 source-bullet migration (relabel + host:locator + approach-b grouping).")
    ap.add_argument("--vault", default=None, help="Vault dir (else AUTORESEARCH_VAULT / ../vault).")
    ap.add_argument("--file", default=None, help="Limit to one Family_Tree file (basename).")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run).")
    args = ap.parse_args()

    vault = vault_config.resolve_vault(args.vault)
    pattern = os.path.join(vault, args.file if args.file else "Family_Tree*.md")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"no files matched {pattern}", file=sys.stderr)
        return 1

    grand = {"bullets": 0, "records": 0, "locators": 0, "flagged": 0, "changed_files": 0}
    for path in files:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new_text, stats = migrate_text(text)
        if new_text == text:
            continue
        grand["changed_files"] += 1
        grand["bullets"] += stats["bullets"]
        grand["records"] += stats["records"]
        grand["locators"] += stats["locators"]
        grand["flagged"] += len(stats["flagged"])
        fname = os.path.basename(path)
        print(f"{'APPLY' if args.apply else 'DRY  '} {fname}: {stats['bullets']} bullets -> {stats['records']} records "
              f"({stats['locators']} locators); {len(stats['flagged'])} flagged")
        for lineno, reason, snippet in stats["flagged"]:
            print(f"    FLAG L{lineno} [{reason}]: {snippet}")
        if args.apply:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)

    print()
    verb = "applied" if args.apply else "would change"
    print(f"=== {verb}: {grand['changed_files']} files, {grand['bullets']} bullets, "
          f"{grand['locators']} locators -> {grand['records']} records, {grand['flagged']} flagged for Phase B ===")
    if not args.apply:
        print("(dry-run; re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
