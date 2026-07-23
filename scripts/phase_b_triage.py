#!/usr/bin/env python3
"""phase_b_triage.py — Spec 03 Phase B, category 1 helper.

The Phase-A migration left a `- note (pre-migration, Phase B: ...)` line under
some `**Sources**` bullets, preserving the original freeform text. Category 1 is
consuming those notes: re-attach per-record descriptors, remove locators the prose
rejects, then drop the note.

This helper CLASSIFIES each note so the judgment cases get human attention and the
purely-redundant ones can be cleared safely. For each note it computes:
  - record_arks : the ARK ids already on the block's record sub-bullets
  - note_arks   : the ARK ids in the note
  - orphans     : note_arks - record_arks  (would be LOST if the note were deleted —
                  never auto-delete a note with orphans)
  - has_reject  : the note flags a do-not-attach / different-family locator
  - has_prose   : the note carries descriptors or context beyond a bare ARK list

Classification:
  REDUNDANT  : no orphans, no reject, no prose  -> safe to delete the note (its ARKs
               are all already records and it says nothing else)
  MANUAL     : everything else (descriptors to attach, rejects to remove, or orphan
               ARKs to preserve) -> a human edits it

Modes:
  (default)         report the classification per note
  --delete-redundant [--apply]   drop ONLY the REDUNDANT notes (dry-run without --apply)
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config
import harvest_sources as H

NOTE_RE = re.compile(r"^\s*-\s+note \(pre-migration", re.IGNORECASE)
SOURCES_HDR_RE = re.compile(r"^\s*-\s+\*\*(?:Sources?|FS[- ]attached sources?)\*\*", re.IGNORECASE)
LIST_ITEM_RE = re.compile(r"^\s*-\s+")
REJECT_RE = re.compile(r"⛔|do NOT attach|DIFFERENT|false positive|not ours|no match", re.IGNORECASE)

# Tokens to strip when deciding whether a note is a BARE ark list (no prose).
_STRIP = [
    re.compile(r"note \(pre-migration[^:]*:", re.IGNORECASE),
    re.compile(r"ark:/\d+/[\w./-]+", re.IGNORECASE),
    re.compile(r"https?://[^\s,;)\]]+", re.IGNORECASE),
    re.compile(r"\b\d:1:[A-Z0-9-]+", re.IGNORECASE),
    re.compile(r"\bPL(?:_\d+){3,4}\.jpg", re.IGNORECASE),
    re.compile(r"\b(?:fs|anc|wt|antenati|metryki|szukajwarchiwach|agad):", re.IGNORECASE),
    re.compile(r"\bext\b|\bincl\.?\b", re.IGNORECASE),
]


NOTE_PREFIX_RE = re.compile(r"^(?P<indent>\s*)-\s+note \(pre-migration[^)]*\):\s*(?P<body>.*)$")


def locator_spans(text):
    spans = []
    for pat, _host, _kind in H.HOST_LOCATOR_PATTERNS:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end()))
    return spans


def split_note(note_line):
    """Return (indent, ark_portion, trailing_prose) or None if not a note.
    ark_portion = text up to the last locator token; trailing_prose = the rest."""
    m = NOTE_PREFIX_RE.match(note_line)
    if not m:
        return None
    body = m.group("body")
    spans = locator_spans(body)
    if not spans:
        return (m.group("indent"), "", body.strip())
    last_end = max(e for _s, e in spans)
    ark_portion = body[:last_end]
    trailing = body[last_end:].strip(" \t.,;:")
    return (m.group("indent"), ark_portion, trailing)


def is_flat_context(note_line):
    """FLAT: the ark-list portion carries NO inline descriptor (no '(' and no
    '**'), so the note is a bare locator list plus an optional trailing sentence.
    Such notes fold safely to a Coverage note (their ARKs are already records)."""
    sp = split_note(note_line)
    if sp is None:
        return False
    _indent, ark_portion, _trailing = sp
    return ("(" not in ark_portion) and ("**" not in ark_portion)


def fold_to_coverage(note_line):
    """Rewrite a FLAT note as a Coverage-note bullet (or None to delete it if it
    carries no trailing prose)."""
    indent, _ark, trailing = split_note(note_line)
    # keep a trailing parenthetical caveat too, e.g. "(+ ~63 more ... not transcribed)"
    if trailing and re.search(r"[A-Za-zÀ-ÿ]{3,}", trailing):
        # tidy a leading connector
        trailing = re.sub(r"^(and|but|\.)\s+", "", trailing).strip()
        return f"{indent}- Coverage note: {trailing}"
    return None


def strip_to_coverage(note_line):
    """For a DESCRIPTOR note whose ARKs are all already record lines, remove the
    inline locator tokens and keep the descriptive prose as a 'record breakdown'
    Coverage note. Safe only when the note has no orphan ARKs (caller checks)."""
    indent = re.match(r"^(\s*)", note_line).group(1)
    body = NOTE_PREFIX_RE.match(note_line).group("body")
    for pat, _h, _k in H.HOST_LOCATOR_PATTERNS:
        body = pat.sub("", body)
    # tidy artifacts left by token removal
    body = re.sub(r"\(\s*(?:already )?cited(?: above)?\s*\)", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\(\s*\)", "", body)          # empty parens
    body = re.sub(r"\(\s*[,;+]\s*", "(", body)
    body = re.sub(r"\bARK list:\s*", "", body, flags=re.IGNORECASE)  # dangling "ARK list:"
    body = re.sub(r":\s*(?=[.;,])", "", body)    # "word:." / "word:;" -> "word." / "word;"
    body = re.sub(r"\s*[,;]\s*(?=[,;.)])", "", body)  # doubled delimiters
    body = re.sub(r"\s*\+\s*(?=[,;.)]|$)", "", body)  # dangling +
    body = re.sub(r"\s{2,}", " ", body)
    body = re.sub(r"\s+([,;.])", r"\1", body)
    body = re.sub(r"[\s:;,]+$", ".", body)       # tidy trailing punctuation
    body = re.sub(r"\.\s*\.+", ".", body)         # collapse ". ." -> "."
    body = re.sub(r"^[\s,;:+.\-—]+", "", body).strip()
    return f"{indent}- Coverage note: record breakdown — {body}"


def note_has_prose(note_line):
    """True if, after removing every locator/URL token and delimiters, meaningful
    word characters remain (a descriptor or a context sentence)."""
    s = note_line
    for pat in _STRIP:
        s = pat.sub(" ", s)
    s = re.sub(r"[\s,;:.\-()\[\]/\"']+", " ", s).strip()
    # ignore short leftover fragments like stray 'the', 'a' — require a real word run
    return bool(re.search(r"[A-Za-zÀ-ÿ]{3,}", s))


def find_blocks(lines):
    """Yield (note_idx, sources_hdr_idx, record_line_idxs) for each note."""
    for i, ln in enumerate(lines):
        if not NOTE_RE.match(ln):
            continue
        # walk back to the Sources header, collecting record list-items in between
        hdr = None
        recs = []
        j = i - 1
        while j >= 0:
            if SOURCES_HDR_RE.match(lines[j]):
                hdr = j
                break
            if LIST_ITEM_RE.match(lines[j]):
                recs.append(j)
            else:
                break  # left the block
            j -= 1
        yield i, hdr, list(reversed(recs))


def classify(lines, note_idx, rec_idxs):
    note = lines[note_idx]
    note_arks = H.extract_arks(note)
    rec_arks = set()
    for r in rec_idxs:
        rec_arks |= H.extract_arks(lines[r])
    orphans = note_arks - rec_arks
    has_reject = bool(REJECT_RE.search(note))
    has_prose = note_has_prose(note)
    if not orphans and not has_reject and not has_prose:
        return "REDUNDANT", orphans, has_reject, has_prose
    return "MANUAL", orphans, has_reject, has_prose


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None)
    ap.add_argument("--fold-context", action="store_true",
                    help="Fold FLAT notes (bare ARK list + trailing sentence) into a Coverage-note bullet.")
    ap.add_argument("--strip-descriptor", action="store_true",
                    help="For DESCRIPTOR notes (no orphans), strip inline ARKs, keep the prose as a record-breakdown Coverage note.")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    vault = vault_config.resolve_vault(args.vault)

    totals = {"FLAT": 0, "DESCRIPTOR": 0, "SKIP": 0}
    descriptor_detail = []
    for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        changed = False
        # process bottom-up so line replacement doesn't shift earlier indices
        for note_idx, hdr, rec_idxs in sorted(find_blocks(lines), key=lambda t: -t[0]):
            note = lines[note_idx]
            note_arks = H.extract_arks(note)
            rec_arks = set()
            for r in rec_idxs:
                rec_arks |= H.extract_arks(lines[r])
            orphans = note_arks - rec_arks
            has_reject = bool(REJECT_RE.search(note))
            if orphans or has_reject:
                totals["SKIP"] += 1
                descriptor_detail.append((os.path.basename(path), note_idx + 1,
                                          f"SKIP orphans={len(orphans)} reject={has_reject}"))
                continue
            if is_flat_context(note):
                totals["FLAT"] += 1
                repl = fold_to_coverage(note)
                if args.fold_context:
                    print(f"{'APPLY' if args.apply else 'DRY  '} {os.path.basename(path)}:{note_idx+1}")
                    print(f"    -> {repl if repl else '(delete note)'}")
                    if args.apply:
                        if repl is None:
                            lines.pop(note_idx)
                        else:
                            lines[note_idx] = repl
                        changed = True
            else:
                totals["DESCRIPTOR"] += 1
                if args.strip_descriptor:
                    repl = strip_to_coverage(note)
                    print(f"{'APPLY' if args.apply else 'DRY  '} {os.path.basename(path)}:{note_idx+1}")
                    print(f"    -> {repl}")
                    if args.apply:
                        lines[note_idx] = repl
                        changed = True
                else:
                    descriptor_detail.append((os.path.basename(path), note_idx + 1, "DESCRIPTOR (manual)"))
        if args.apply and changed:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

    print(f"\n=== {totals['FLAT']} FLAT (fold-safe), {totals['DESCRIPTOR']} DESCRIPTOR (manual), {totals['SKIP']} SKIP ===")
    if not args.fold_context:
        for fn, lineno, tags in sorted(descriptor_detail):
            print(f"  {fn}:{lineno}  [{tags}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
