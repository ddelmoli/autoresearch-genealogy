#!/usr/bin/env python3
"""Typing-friendly guard for the vault's Handoff.md.

Handoff.md is standardized so its section markers (`Start here`, `WATCHLIST
AGING REMINDER`, ...) stay easy to reference, and so it carries no decorative
glyphs you can't type. The rule is about CHARACTER KIND, not codepoint range:

  ALLOWED (preserved, never flagged):
    - printable ASCII (0x20-0x7E) + tab/newline
    - any Latin-script LETTER, with or without diacritics
      (so Solotwina/Soltwina-with-barred-L, Borszczow-with-acute, Szutzer-with-
       umlaut, Melnytsya, etc. are fine -- they are real names, not noise)
  FLAGGED (and fixed by --fix):
    - Symbol-category glyphs: emoji / pictographs / arrows / stars / check &
      cross marks / warning signs (the real target of this guard)
    - typographic punctuation that has a plain-ASCII equivalent
      (em/en dash, curly quotes, ellipsis, non-breaking space)
    - any non-Latin script (Cyrillic/Hebrew/CJK) -- Handoff is English notes

Other vault files keep their diacritics untouched; this guard is Handoff-only.

  python3 scripts/ascii_handoff.py            # check: list flagged chars, exit 1 if any
  python3 scripts/ascii_handoff.py --fix      # normalize punctuation, drop symbols
  python3 scripts/ascii_handoff.py --count    # print just the flagged-char count

Usage from another file: import ascii_handoff; n = ascii_handoff.count()
"""
import sys, os, re, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import vault_config
VAULT = vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
PATH = os.path.join(VAULT, "Handoff.md") if VAULT else None

# Typographic punctuation -> plain ASCII. These are flagged AND auto-normalized;
# they are NOT letters, so keeping them out keeps the file plain-typeable.
PUNCT = {
    "→": "->",  "←": "<-",       # arrows (category Sm, but map don't drop)
    "…": "...",                         # ellipsis
    "—": "-",   "–": "-",         # em / en dash
    "‘": "'",   "’": "'",         # curly single quotes
    "“": '"',   "”": '"',         # curly double quotes
    " ": " ",                          # non-breaking space
}

def is_letter(c: str) -> bool:
    """A Latin-script letter (with or without diacritics): allowed + preserved."""
    return (unicodedata.category(c).startswith("L")
            and unicodedata.name(c, "").startswith("LATIN"))

def is_allowed(c: str) -> bool:
    return ord(c) <= 0x7E or c in "\t\n" or is_letter(c)

def _nfc(t: str) -> str:
    # Precompose so "o" + U+0301 becomes a single LATIN letter (allowed), not a
    # bare combining mark (which would be flagged/dropped).
    return unicodedata.normalize("NFC", t)

def find(t: str):
    t = _nfc(t)
    return [(i + 1, c) for i, ln in enumerate(t.split("\n"))
            for c in ln if not is_allowed(c)]

def count() -> int:
    if not os.path.exists(PATH):
        return 0
    return len(find(open(PATH, encoding="utf-8").read()))

def transliterate(t: str) -> str:
    t = _nfc(t)
    for k, v in PUNCT.items():
        t = t.replace(k, v)
    # Whatever is still not allowed is a symbol/emoji/non-Latin glyph: drop it,
    # plus one trailing space so leading markers ("<star> Surname") vanish cleanly.
    for c in {c for ln in t.split("\n") for c in ln if not is_allowed(c)}:
        t = t.replace(c + " ", "").replace(c, "")
    # tidy doubled spaces left by a dropped mid-line glyph (not leading indentation)
    t = "\n".join(re.sub(r"(?<=\S)  +", " ", ln) for ln in t.split("\n"))
    return t

def main():
    vault_config.require_vault(VAULT)
    if not os.path.exists(PATH):
        print("Handoff.md missing"); return 0
    t = open(PATH, encoding="utf-8").read()
    if "--count" in sys.argv:
        print(count()); return 0
    if "--fix" in sys.argv:
        new = transliterate(t)
        open(PATH, "w", encoding="utf-8").write(new)
        residual = find(new)
        print(f"[ascii_handoff] fixed; {'0' if not residual else len(residual)} flagged chars remain")
        for ln, c in residual:
            print(f"  UNMAPPED line {ln}: {c!r} (U+{ord(c):04X}) -- add to PUNCT if it has an ASCII form")
        return 1 if residual else 0
    bad = find(t)
    if not bad:
        print("ASCII OK"); return 0
    print(f"FLAGGED: {len(bad)} non-typeable char(s) in Handoff.md (emoji/symbols/typographic punctuation) -- run: python3 scripts/ascii_handoff.py --fix")
    for ln, c in bad[:20]:
        print(f"  line {ln}: {c!r} (U+{ord(c):04X})")
    return 1

if __name__ == "__main__":
    sys.exit(main())
