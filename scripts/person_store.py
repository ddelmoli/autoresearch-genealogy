#!/usr/bin/env python3
"""person_store.py — a model-agnostic seam over person records.

Two on-disk encodings ("person models", selected by vault_config.get_person_model):
  - "file"      : one `type: person` Markdown file per person (the upstream/legacy
                  model). This is the default.
  - "narrative" : many people per lineage file, each a bold-name entry with an
                  inline `- meta:` block.

Callers use iter_people / get_person / write_person over a common PersonRecord and
never parse files directly, so one script written against this seam serves both
models. This is the linchpin that lets the record-consuming toolkit
(gen_person_index, mint_ids, harvest_sources, prose_audit, ...) become
model-agnostic without a rewrite (spec/optional-person-model, Spec 05).

Staging (spec/optional-person-model):
  - Spec 03 (this file): wire FileBackend (the default) + PersonRecord; leave
    NarrativeBackend a stub. Prove the seam is a no-op for the file model.
  - Spec 04: implement NarrativeBackend + the narrative<->file converter + a
    narrative-aware validity/privacy check.

Zero hard dependencies: uses PyYAML for frontmatter when present, else a small
flat-frontmatter fallback (person frontmatter is shallow: scalars + short lists).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import glob
import os
import re

import gdate
import vault_config

# The four Spec 03 date keys, and which of them must satisfy the grammar.
# `*_phrase` is free text by definition (that is what a PHRASE is FOR), so it is
# never grammar-checked — but it IS privacy-screened, exactly like the date keys.
DATE_KEYS = ("born", "born_phrase", "died", "died_phrase")
_GRAMMAR_KEYS = ("born", "died")


class InvalidDateValue(ValueError):
    """A write tried to store a value that is not a GEDCOM 7 DateValue.

    Raised rather than dropped: a silently discarded date is the failure mode this
    whole lane exists to remove. Read paths stay lenient — a bad value already on
    disk is REPORTED by the gates, not made to crash every tool that opens the
    vault."""


def _validate_date_write(key, value, who=""):
    """Grammar-check a date value that a write is about to INTRODUCE or CHANGE.

    Deliberately not applied to values passing through untouched: a pre-existing
    hand-edited value stays byte-preserved and is surfaced by the gates instead,
    so one bad entry cannot block an unrelated `mint_ids --apply` run."""
    if key not in _GRAMMAR_KEYS or value is None or str(value).strip() == "":
        return
    if not gdate.is_valid(value):
        raise InvalidDateValue(
            f"{who}{key}={value!r} is not a valid GEDCOM 7 DateValue. "
            f"Use gdate.normalise() to convert legacy prose, put anything the "
            f"grammar cannot express in {key}_phrase, or omit the key entirely "
            f"(absence = unknown).")


try:
    import yaml
    _HAVE_YAML = True
except ImportError:  # pragma: no cover - yaml is normally present
    _HAVE_YAML = False


# --------------------------------------------------------------------------- #
# The common record
# --------------------------------------------------------------------------- #
@dataclass(eq=False)
class PersonRecord:
    """One person, independent of on-disk encoding. Fields are the shared
    vocabulary (the CLAUDE.method.md field-map / the Spec-01 file keys).

    `source_file` and `raw` are BACKEND ARTIFACTS, not part of the record's
    identity: source_file differs by model by design (a person's own file vs the
    lineage file), and raw is the handle write_person uses to update in place.
    Both are excluded from equality.
    """
    id: str | None = None
    name: str | None = None
    # born/died: a GEDCOM 7 DateValue when the record carries one as a FIELD
    # (spec/structured-dates Spec 03), else the header/frontmatter value kept
    # VERBATIM. The field is authoritative when present — Spec 06 decision (a),
    # meta authoritative + advisory DATE_DRIFT — and for the narrative model the
    # header-parsed pair stays available in `raw['header_vitals']` so that gate
    # can compare the two without re-reading the file.
    born: str | None = None
    died: str | None = None
    # The GEDCOM 7 PHRASE escape hatch: free text for what the grammar cannot
    # express (`30 January 1648/49`). Permitted alongside its date key, or alone
    # when the date is genuinely unstructurable.
    born_phrase: str | None = None
    died_phrase: str | None = None
    generation: int | None = None
    evidence_tier: str | None = None
    profile_status: str | None = None
    life_status: str | None = None
    external_ids: dict = field(default_factory=dict)   # {fs, wt, anc, ...}
    parents: list = field(default_factory=list)        # ids; a trailing '?' = unverified
    spouse: list = field(default_factory=list)         # ids; a trailing '?' = unverified
    flags: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    source_file: str | None = None   # backend artifact (which file holds the record)
    raw: object = None               # backend handle for in-place write

    # Equality over the field VOCABULARY only (see class docstring). Multi-valued
    # fields compare as SETS (order-independent) while PRESERVING the '?'
    # unverified-edge marker; born/died compare VERBATIM.
    def _eqkey(self):
        return (
            self.id, self.name, self.born, self.died,
            self.born_phrase, self.died_phrase, self.generation,
            self.evidence_tier, self.profile_status, self.life_status,
            tuple(sorted((self.external_ids or {}).items())),
            frozenset(str(p) for p in (self.parents or ())),
            frozenset(str(s) for s in (self.spouse or ())),
            frozenset(str(f) for f in (self.flags or ())),
            frozenset(_norm_source(s) for s in (self.sources or ())),
        )

    def __eq__(self, other):
        return isinstance(other, PersonRecord) and self._eqkey() == other._eqkey()

    def __hash__(self):
        return hash(self._eqkey())


def _norm_source(s):
    """Canonicalize a source entry for set comparison. File-model sources are
    plain strings; narrative sources may be structured. Compare on a stripped
    string form so equivalent citations across encodings match."""
    if isinstance(s, dict):
        return tuple(sorted((k, str(v)) for k, v in s.items()))
    return str(s).strip()


# --------------------------------------------------------------------------- #
# Frontmatter parsing (verbatim scalars: dates must NOT be coerced to date objects)
# --------------------------------------------------------------------------- #
def _split_frontmatter(text):
    """Return (frontmatter_dict, body_text). Non-frontmatter files -> ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    parts = re.split(r"(?m)^---[ \t]*$", text, maxsplit=2)
    if len(parts) < 3:
        return {}, text
    return _parse_frontmatter(parts[1]), parts[2]


def _parse_frontmatter(block):
    """Parse a YAML frontmatter block, keeping every scalar as a STRING so
    genealogical dates (`1840-03-01`, `ABT 1832`) survive verbatim rather than
    being coerced to date objects. Uses yaml.BaseLoader when available (which does
    exactly that), else a small flat fallback."""
    if _HAVE_YAML:
        data = yaml.load(block, Loader=yaml.BaseLoader) or {}
        return data if isinstance(data, dict) else {}
    return _flat_frontmatter(block)


def _flat_frontmatter(block):
    """Minimal dependency-free fallback for shallow person frontmatter:
    `key: scalar`, `key: [a, b]` inline lists, and `key:` + `  - item` blocks."""
    out, cur_key = {}, None
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if cur_key and re.match(r"^\s+-\s+", line):
            if not isinstance(out.get(cur_key), list):
                out[cur_key] = []
            out[cur_key].append(_unquote(line.split("-", 1)[1].strip()))
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            out[key], cur_key = "", key      # empty for now; a following `- item` promotes it to a list
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            out[key] = [_unquote(x.strip()) for x in inner.split(",")] if inner else []
            cur_key = None
        else:
            out[key], cur_key = _unquote(val), None
    return out


def _unquote(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        inner = s[1:-1]
        if s[0] == '"':                       # double-quoted: resolve \" and \\ escapes
            out, i = [], 0
            while i < len(inner):
                if inner[i] == "\\" and i + 1 < len(inner):
                    out.append(inner[i + 1]); i += 2
                else:
                    out.append(inner[i]); i += 1
            return "".join(out)
        return inner.replace("''", "'")       # single-quoted: '' -> '
    return s


# --------------------------------------------------------------------------- #
# FileBackend — one `type: person` Markdown file per person (the default)
# --------------------------------------------------------------------------- #
_EXTERNAL_ID_KEYS = ("fs", "wt", "anc", "wikitree", "ancestry")


def _iter_person_files(vault):
    """Every `*.md` under the vault EXCEPT template scaffolding (`templates/`)."""
    for path in sorted(glob.glob(os.path.join(vault, "**", "*.md"), recursive=True)):
        rel_parts = os.path.relpath(path, vault).split(os.sep)
        if "templates" in rel_parts:
            continue
        yield path


def _int_or_none(v):
    s = str(v).strip()
    return int(s) if s.lstrip("-").isdigit() else None


def _clean_str(v):
    """None or empty/whitespace -> None; else the string. So an empty `died:` reads
    the same whether parsed by yaml.BaseLoader (None) or the flat fallback ("")."""
    if v is None:
        return None
    s = str(v)
    return s if s.strip() != "" else None


def _record_from_frontmatter(fm, path, text, vault):
    ext = {k: fm[k] for k in _EXTERNAL_ID_KEYS if fm.get(k)}
    return PersonRecord(
        id=fm.get("id"),
        name=fm.get("name"),
        born=_clean_str(fm.get("born")),
        died=_clean_str(fm.get("died")),
        born_phrase=_clean_str(fm.get("born_phrase")),
        died_phrase=_clean_str(fm.get("died_phrase")),
        generation=(None if fm.get("generation") is None else _int_or_none(fm["generation"])),
        evidence_tier=fm.get("evidence_tier"),
        profile_status=fm.get("profile_status"),
        life_status=fm.get("life_status"),
        external_ids=ext,
        parents=list(fm.get("parents") or []),
        spouse=list(fm.get("spouse") or []),
        flags=list(fm.get("flags") or []),
        sources=list(fm.get("sources") or []),
        source_file=(os.path.relpath(path, vault) if path else None),
        raw={"path": path, "text": text},
    )


class FileBackend:
    """One `type: person` Markdown file per person."""

    name = "file"

    @staticmethod
    def iter_people(vault):
        for path in _iter_person_files(vault):
            text = _read(path)
            fm, _body = _split_frontmatter(text)
            if not fm or fm.get("type") != "person":
                continue
            yield _record_from_frontmatter(fm, path, text, vault)

    @staticmethod
    def write_person(vault, record, promote_dates=False):
        """Upsert a person file. `promote_dates` is accepted for seam parity and
        is a no-op here: a file record's dates come from frontmatter, so there is
        no header prose to promote. For an existing record (record.raw carries the
        original text), rewrite ONLY the frontmatter keys whose value changed, so a
        no-op write is byte-identical and the body + comments are preserved. For a
        new record, create `<vault>/<Name>.md` from a minimal frontmatter."""
        if record.raw and record.raw.get("path"):
            path = record.raw["path"]
            original = record.raw.get("text", _read(path))
            new_text = _apply_frontmatter_changes(original, record)
            if new_text != original:
                _write(path, new_text)
            return path
        # New person: derive a filename from the name.
        base = re.sub(r"\s+", "_", (record.name or record.id or "Unknown").strip())
        path = os.path.join(vault, base + ".md")
        _write(path, _render_new_person(record))
        return path


# --------------------------------------------------------------------------- #
# Frontmatter surgical write (change only what differs; preserve everything else)
# --------------------------------------------------------------------------- #
_WRITE_KEYS = (
    "id", "name", "born", "born_phrase", "died", "died_phrase", "generation",
    "evidence_tier", "profile_status", "life_status",
    "parents", "spouse", "flags",
)


def _yaml_dq(s):
    """Double-quote a scalar with escaping, for YAML-safe block-list values
    (source strings carry commas, colons, em-dashes)."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _yaml_flow_scalar(v):
    """Quote a flow-list element if it isn't a bare word/id, so a value like a
    parent id with a trailing '?' (an unverified-edge marker — a YAML metacharacter)
    stays valid YAML that a real parser and the Ruby validator can read."""
    v = str(v)
    return v if re.fullmatch(r"[\w\-.]+", v) else '"' + v.replace('"', '\\"') + '"'


def _serialize_value(key, value):
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_flow_scalar(v) for v in value) + "]"
    return "" if value is None else str(value)


def _apply_frontmatter_changes(text, record):
    """Return `text` with the frontmatter updated to match `record`, editing only
    changed scalar/inline-list keys (leaves the body and untouched keys verbatim)."""
    parts = re.split(r"(?m)^---[ \t]*$", text, maxsplit=2)
    if len(parts) < 3:
        return text  # not frontmatter; refuse to guess
    lead, fm_block, body = parts[0], parts[1], parts[2]
    old_fm = _parse_frontmatter(fm_block)
    old_record = _record_from_frontmatter(old_fm, "", text, "")

    desired = {
        "id": record.id, "name": record.name, "born": record.born,
        "died": record.died, "born_phrase": record.born_phrase,
        "died_phrase": record.died_phrase, "generation": record.generation,
        "evidence_tier": record.evidence_tier, "profile_status": record.profile_status,
        "life_status": record.life_status, "parents": record.parents,
        "spouse": record.spouse, "flags": record.flags,
    }
    old_vals = {
        "id": old_record.id, "name": old_record.name, "born": old_record.born,
        "died": old_record.died, "born_phrase": old_record.born_phrase,
        "died_phrase": old_record.died_phrase, "generation": old_record.generation,
        "evidence_tier": old_record.evidence_tier,
        "profile_status": old_record.profile_status,
        "life_status": old_record.life_status, "parents": old_record.parents,
        "spouse": old_record.spouse, "flags": old_record.flags,
    }

    lines = fm_block.split("\n")
    for key in _WRITE_KEYS:
        if _norm_field(desired[key]) == _norm_field(old_vals[key]):
            continue  # unchanged -> leave the original line byte-identical
        _validate_date_write(key, desired[key], who=f"{record.id or record.name}: ")
        new_line = f"{key}: {_serialize_value(key, desired[key])}"
        replaced = False
        for i, ln in enumerate(lines):
            if re.match(rf"^{re.escape(key)}:\s*", ln):
                lines[i] = new_line
                replaced = True
                break
        if not replaced and desired[key] not in (None, [], ""):
            # insert a new key just before the closing of the frontmatter block
            insert_at = len(lines) - 1 if lines and lines[-1] == "" else len(lines)
            lines.insert(insert_at, new_line)
    return lead + "---" + "\n".join(lines) + "---" + body


def _norm_field(v):
    if isinstance(v, list):
        return [str(x) for x in v]
    return None if v is None else str(v)


def _render_new_person(record):
    fm = ["---", "type: person"]
    if record.name is not None:
        fm.append(f'name: "{record.name}"')
    for key in ("born", "born_phrase", "died", "died_phrase", "life_status",
                "evidence_tier", "profile_status", "id", "generation"):
        val = getattr(record, key)
        if val is not None:
            fm.append(f"{key}: {_serialize_value(key, val)}")
    for k in _EXTERNAL_ID_KEYS:               # fs/wt/anc — needed for lossless conversion
        if (record.external_ids or {}).get(k):
            fm.append(f"{k}: {record.external_ids[k]}")
    for key in ("parents", "spouse", "flags"):
        val = getattr(record, key)
        if val:
            fm.append(f"{key}: {_serialize_value(key, val)}")
    if record.sources:
        fm.append("sources:")
        fm.extend("  - " + _yaml_dq(s) for s in record.sources)
    fm.append("tags: [genealogy, person]")
    fm.append("---")
    fm.append("")
    fm.append(f"# {record.name or ''}".rstrip())
    fm.append("")
    return "\n".join(fm)


# --------------------------------------------------------------------------- #
# NarrativeBackend — many people per lineage file, each a `- meta:` entry
# --------------------------------------------------------------------------- #
# The parsing primitives below are lifted verbatim from gen_person_index (today's
# narrative parser) so the meta-anchored detection stays identical. Spec 05
# consolidates: gen_person_index will consume this seam and its duplicate copies
# are removed, making person_store the single narrative parser.
_BOLD = re.compile(r"^\s*[-*]*\s*\*\*(.+?)\*\*(.*)$")
_META = re.compile(r"^\s*-\s*meta:\s*(.+)$", re.I)
_GEN_HDR = re.compile(r"^#{1,4}\s+Generation\s+(\d+)", re.I)


def _parse_meta_block(line):
    """Parse a `- meta:` line's mapping. Handles the v3 YAML flow-mapping
    `{k: v, ...}` and the legacy `;`-delimited form."""
    m = _META.match(line)
    if not m:
        return {}
    raw = m.group(1).strip()
    if raw.startswith("{"):
        if _HAVE_YAML:
            data = yaml.safe_load(raw) or {}
            return {str(k).lower(): v for k, v in data.items()} if isinstance(data, dict) else {}
        return _flow_mapping_fallback(raw)
    out = {}
    for part in raw.split(";"):
        k, _, v = part.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k and v:
            out[k] = v
    return out


def _flow_mapping_fallback(s):
    """Dependency-free `{k: v, ...}` parser (comma-split respecting quotes/brackets)."""
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out, buf, depth, inq = [], "", 0, None
    for ch in s:
        if inq:
            buf += ch
            if ch == inq:
                inq = None
        elif ch in "'\"":
            inq = ch; buf += ch
        elif ch in "[{":
            depth += 1; buf += ch
        elif ch in "]}":
            depth -= 1; buf += ch
        elif ch == "," and depth == 0:
            out.append(buf); buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    d = {}
    for part in out:
        k, _, v = part.partition(":")
        k, v = k.strip().lower(), v.strip()
        if len(v) >= 2 and v[0] in "'\"" and v[-1] == v[0]:
            v = v[1:-1]
        elif re.fullmatch(r"-?\d+", v):
            v = int(v)
        if k and v != "":
            d[k] = v
    return d


def _parse_vitals(paren):
    """Pull (born, died) display strings from a header parenthetical (verbatim)."""
    born = died = ""
    # `\)` is a TERMINATOR, not merely an excluded character. `[^;)]` already
    # refuses to cross a ')', so without ')' in the lookahead the born match FAILS
    # outright on any parenthetical containing one — e.g.
    # "b. 5 FEB 1871, Gloucester (Barton St Mary), ... d. 25 MAY 1934". Measured:
    # adding it alone changes nothing, but it is what makes the balanced-paren
    # capture in _vitals_paren safe (14 losses -> 0). Keep the two together.
    bm = re.search(r"(?:\bb\.|\bborn\b|\bbapt|\bchr\.)\s*([^;)]*?)(?=;|\)|\bd\.|\bdied\b|$)", paren, re.I)
    dm = re.search(r"(?:\bd\.|\bdied\b)\s*([^;)]*)", paren, re.I)
    if bm:
        born = bm.group(1).strip(" ,")
    if dm:
        died = dm.group(1).strip(" ,")
    if not born and not died:
        born, died = _terse_vitals(paren)
    clean = lambda s: re.sub(r"[*\[\]`]", "", s).strip(" ,")
    return clean(born), clean(died)


# The TERSE DIALECT: a header with no b./d. marker whose parenthetical states the
# vitals positionally — "(c.966; 23 APR 1016; FS PID …)", "(c.975–1045; Gen 35)",
# "(1116–1183; WikiTree …)".
#
# ⚠ THE RULE THAT MAKES THIS SAFE: the parenthetical must OPEN with a date.
#
# Without it, this fallback guessed positionally over any numbers it could find,
# and wrote 25 wrong values into a live vault (found by audit, 23 JUL 2026):
#
#   "of Horsley; father of Susanna bp. 8 FEB 1718/19; ? m. … 3 FEB 1701/2"
#        -> born 1718, died 1701 — a daughter's baptism and a marriage, and born
#           AFTER died, which is impossible.
#   "alive 1852 Cagnano, profession Lavoratore"  -> born 1852. A floruit. x15
#   "deceased before 1898 Cagnano"               -> born 1898. A death bound.
#   "vault name '…' 4 APR – 10 JUN 2026, a paleo misread" -> born 2026.
#
# None of those OPEN with a date, so none of them reach the positional read now.
#
# The other half of the bug was the 4-digit floor: in "(c.966; 23 APR 1016; …)"
# the birth year 966 was invisible, so the only year found was the DEATH year and
# it landed in `born`, losing the birth entirely on 7 medieval entries. Years here
# are 3-or-4 digit. The old objection to 3-digit years — atto and page numbers
# like "534" being read as death years — is answered by the opens-with-a-date rule
# instead of by a floor: a page number never starts a vitals parenthetical.
#
# A wrong date is far worse than a missing one, so this refuses rather than
# guesses, the same contract gdate.normalise holds.
_ABSENT_FIELD = re.compile(r"\A(?:unknown|unk|n/?a|\?+|—|-)\b", re.I)
_FLORUIT = re.compile(r"\balive\b|\bdeceased\s+before\b|\bfl\.", re.I)
_PIDISH = re.compile(r"\b[A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+\b")
# A leading approximation OR bound is part of the date: this dialect writes
# "bef.1294–24 SEP 1313" and "c.966" as freely as a bare year.
_DATE_TOKEN = re.compile(
    r"(?:c\.|ca\.|~|abt\.?|bef\.?|aft\.?|before|after|about)?\s*"
    r"(?:\d{1,2}\s+)?(?:[A-Za-z]{3,9}\.?\s+)?\d{3,4}\b", re.I)


def _terse_vitals(paren):
    """(born, died) from a marker-less vitals parenthetical, or ("", "")."""
    s = _PIDISH.sub(" ", paren).strip()
    if not s or _FLORUIT.search(s):
        return "", ""
    # Semicolons delimit the dialect's fields, and a field routinely carries a
    # PLACE after its date — "1940, MA; 1946 [infant death]; FS PID …". So the
    # death is the next SEGMENT that starts with a date, not the next token.
    segs = [x.strip() for x in s.split(";") if x.strip()]
    if not segs:
        return "", ""
    # "(unknown, Cagnano; 6 APR 1820, Cagnano; FS PID TBD)" is this same dialect
    # with the BIRTH field absent, so the date that follows is the DEATH. The old
    # positional scan stored it as `born` — the identical bug, wearing a different
    # hat: an absence marker where a birth date should be.
    if _ABSENT_FIELD.match(segs[0]):
        for seg in segs[1:]:
            nxt = _DATE_TOKEN.match(seg)
            if nxt:
                return "", nxt.group(0).strip()
        return "", ""
    head = _DATE_TOKEN.match(segs[0])
    if not head:
        return "", ""                    # does not open with a date -> not vitals
    first = head.group(0).strip()
    tail0 = segs[0][head.end():]
    dash = re.match(r"\s*[–—-]\s*(.+)", tail0)
    dash_date = _DATE_TOKEN.match(dash.group(1).strip()) if dash else None

    # A LATER field carrying a date is the death. Check for it FIRST, because it
    # disambiguates the dash in field 0: with a death elsewhere, that dash is a
    # birth RANGE, not birth–death.
    #   "~1760-1790 [estimate], Cagnano; 7 FEB 1820, Cagnano; FS PID TBD"
    #        -> born ~1760-1790 (a range), died 7 FEB 1820.  Reading the dash as
    #           birth–death gave this man a death of 1790 and lost the real one —
    #           DATE_DRIFT caught it once the header parsed correctly.
    #   "c.975–1045; Gen 35; FS PID …"  (no later date) -> the dash IS birth–death.
    for seg in segs[1:]:
        nxt = _DATE_TOKEN.match(seg)
        if nxt:
            if dash_date:
                first = (head.group(0) + tail0[:dash.end()]).strip()   # keep the range
            return first, nxt.group(0).strip()
    if dash_date:
        return first, dash_date.group(0).strip()
    return first, ""


def _vitals_paren(name, rest):
    """The vitals parenthetical: first BALANCED (...) after the bold name, else in
    the name.

    ⚠ The FIRST balanced parenthetical, deliberately. Preferring "the first paren
    that contains a b./d. marker" was tried 23 JUL 2026 to rescue a header whose
    vitals sit in a SECOND paren after an editorial aside — and measured far worse
    than the bug it fixed: on 14 entries it jumped to a LATER parenthetical
    belonging to a RELATIVE named in the narrative, so an earl inherited his
    wife's dates and a father inherited his son's death. A header whose vitals are
    not in the first paren is a header to fix, not a parser to loosen.

    Balanced, not "up to the first ')'": vault headers routinely nest a
    parenthetical inside the vitals — "(b. 3 SEP 1780 (FS XXXX-XXX + …), … d.
    between 1816 and 13 FEB 1823, likely at sea …)". A first-')' scan truncates at
    the INNER close, so everything after it — usually the whole death date — was
    invisible to every consumer of the record.

    Measured over the live vault (22 JUL 2026), balanced capture plus the ')'
    terminator in _parse_vitals: **gained 16, changed 0, lost 0**. All 16 are real
    death dates that no gate could previously see, including a colonial mariner
    whose `d. between 1816 and 13 FEB 1823` sat behind a nested citation paren —
    one of Spec 04's own spot-check cases, and unmigratable without this fix.

    The two changes are a PAIR. Balanced capture alone loses 14 born values (the
    born regex cannot cross the now-included ')'), and it also invents a junk
    `died: '2026'` by pushing an entry into the year-fallback. Neither is true with
    the terminator in place. Do not adopt one without the other."""
    for src in (rest or "", name or ""):
        i = src.find("(")
        if i < 0:
            continue
        depth = 0
        for j in range(i, len(src)):
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
                if depth == 0:
                    return src[i + 1:j]
        return src[i + 1:]          # unterminated paren: take the rest of the line
    return ""


def _listify(v):
    """A meta parents/spouse/flags value -> list of str. The v3 grammar quotes flow
    lists (`parents: '[P-A, P-B?]'`), so the value may arrive as a bracketed string
    or an already-parsed list; the '?' unverified marker is preserved."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    return [x.strip() for x in s.split(",") if x.strip()]


def _record_from_meta(meta, name, rest, gens, header_line, path, vault, meta_line):
    # Spec 03 + Spec 06 decision (a): the META FIELD is authoritative when present;
    # the header parenthetical is the human display and the fallback. Both are kept
    # — the header pair goes into raw['header_vitals'] so the DATE_DRIFT gate can
    # compare them without re-reading the file.
    hborn, hdied = _parse_vitals(_vitals_paren(name, rest))
    born = _clean_str(meta["born"]) if "born" in meta else (hborn or None)
    died = _clean_str(meta["died"]) if "died" in meta else (hdied or None)
    born_phrase = _clean_str(meta.get("born_phrase"))
    died_phrase = _clean_str(meta.get("died_phrase"))
    gv = meta.get("generation", meta.get("gen"))
    gen = int(str(gv)) if gv is not None and str(gv).lstrip("-").isdigit() else None
    if gen is None:
        for go, gn in gens:
            if go <= header_line:
                gen = gn
            else:
                break
    ext = {k: meta[k] for k in _EXTERNAL_ID_KEYS if meta.get(k) not in (None, "")}
    return PersonRecord(
        id=meta.get("id"),
        name=name,
        born=born or None,
        died=died or None,
        born_phrase=born_phrase,
        died_phrase=died_phrase,
        generation=gen,
        evidence_tier=meta.get("evidence_tier"),
        profile_status=meta.get("profile_status"),
        life_status=meta.get("life_status"),
        external_ids=ext,
        parents=_listify(meta.get("parents")),
        spouse=_listify(meta.get("spouse")),
        flags=_listify(meta.get("flags")),
        sources=[],  # narrative sources live in a body bullet; populated in Spec 04c
        source_file=(os.path.relpath(path, vault) if path else None),
        raw={"path": path, "meta_line": meta_line, "header_line": header_line,
             # Backend artifacts for Spec 03/06. `header_vitals` is what the header
             # parenthetical says (the DATE_DRIFT comparison target); `read_dates`
             # is what this record was READ as, which is how write_person tells a
             # deliberate change from a value that merely fell back to the header.
             "header_vitals": (hborn or None, hdied or None),
             "read_dates": {"born": born or None, "died": died or None,
                            "born_phrase": born_phrase, "died_phrase": died_phrase},
             "meta_date_keys": tuple(k for k in DATE_KEYS if k in meta)},
    )


_SOURCES_HDR = re.compile(r"^(\s*)-\s*\*\*(?:Sources|FS-attached sources)\*\*\s*(:?)(.*)$", re.I)


def _extract_sources(body_lines):
    """Extract an entry's source RECORDS (as strings) from its body. Handles both
    grammars (Spec 03 / CLAUDE.method.md rule 8):
      structured:  `- **Sources**` then indented `  - <record> — host:locator` sub-bullets
      legacy flat: `- **FS-attached sources**: 1:1:X, 3:1:Y, ext: ark:/...`
    Returns the record strings verbatim (round-trip fidelity; identity is the set)."""
    out = []
    i, n = 0, len(body_lines)
    while i < n:
        m = _SOURCES_HDR.match(body_lines[i])
        if not m:
            i += 1
            continue
        hdr_indent, trailing = len(m.group(1)), m.group(3).strip()
        if trailing:                       # flat form: comma-separated after the colon
            out.extend(s.strip() for s in trailing.split(",") if s.strip())
            i += 1
            continue
        j = i + 1                          # structured: capture more-indented `- ` sub-bullets
        while j < n:
            sub = body_lines[j]
            if not sub.strip():
                j += 1
                continue
            subm = re.match(r"^(\s*)-\s+(.*)$", sub)
            if subm and len(subm.group(1)) > hdr_indent:
                out.append(subm.group(2).strip())
                j += 1
            else:
                break
        i = j
    return out


class NarrativeBackend:
    """Many people per `Family_Tree*.md` lineage file; each person is a bold-name
    entry whose FIRST body bullet is a `- meta:` flow-mapping. Entries are detected
    by the meta line (identity = meta `id`), not the bold name."""

    name = "narrative"

    @staticmethod
    def iter_people(vault):
        for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
            lines = _read(path).splitlines()
            gens = [(i, int(mm.group(1))) for i, ln in enumerate(lines)
                    for mm in [_GEN_HDR.match(ln)] if mm]
            # Pass 1: locate each entry (its bold header line + its `- meta:` line).
            entries = []
            last_name = last_rest = None
            last_line = -1
            for i, line in enumerate(lines):
                hm = _BOLD.match(line)
                if hm:
                    last_name, last_rest, last_line = hm.group(1).strip(), hm.group(2), i
                if _META.match(line) and last_name is not None:
                    entries.append((last_line, last_name, last_rest, i, _parse_meta_block(line)))
            # Pass 2: an entry's body runs from its meta line to the NEXT entry's
            # header; capture that entry's `**Sources**` records from the body.
            for idx, (hline, name, rest, mline, meta) in enumerate(entries):
                body_end = entries[idx + 1][0] if idx + 1 < len(entries) else len(lines)
                rec = _record_from_meta(meta, name, rest, gens, hline, path, vault, mline)
                rec.sources = _extract_sources(lines[mline + 1:body_end])
                rec.raw["line"] = lines[mline]   # raw meta line (consumers re-parse it as `block`)
                yield rec

    @staticmethod
    def write_person(vault, record, promote_dates=False):
        """Upsert a person's `- meta:` block. For an existing entry (record.raw
        carries the file + meta-line index) this surgically rewrites ONLY the meta
        line, preserving the bold-name header, the body bullets, and everything
        else; a no-op write (meta content unchanged) is byte-identical. Creating a
        brand-new narrative entry (header + block, gen-sorted, routed to a lineage
        file) is Spec 04c's converter concern; here a record with no location
        raises so a miswired caller fails loudly rather than dropping data.

        NOTE: this is a LOCAL vault write. The living-person rule is enforced at
        rest by the 4d narrative validator (like the file model's Ruby validator),
        not here; privacy_gate governs EXTERNAL write-back (Spec 05), not local
        storage — gating a local write would wrongly refuse to store living anchors.
        """
        raw = record.raw or {}
        path, meta_i = raw.get("path"), raw.get("meta_line")
        if not path or meta_i is None:
            raise NotImplementedError(
                "NarrativeBackend.write_person for a NEW entry (no location) is "
                "Spec 04c (converter routes + inserts gen-sorted). An existing "
                "record must carry raw['path'] + raw['meta_line'].")
        text = _read(path)
        lines = text.split("\n")
        orig_line = lines[meta_i]
        orig_meta = _parse_meta_block(orig_line)
        new_meta = _record_to_meta(record, orig_meta, promote_dates=promote_dates)
        # No-op guard on PARSED content (not the emitted string), so legacy-formatted
        # blocks stay byte-identical unless a field actually changed.
        if _meta_record(new_meta) == _meta_record(orig_meta):
            return path
        lines[meta_i] = _apply_meta_changes(orig_line, orig_meta, new_meta)
        _write(path, "\n".join(lines))
        return path


# --- meta-block serialization (v3 flow-mapping grammar) --------------------- #
_META_FIELD_ORDER = ("id", "evidence_tier", "profile_status", "life_status",
                     "generation", "fs", "wt", "anc",
                     "born", "born_phrase", "died", "died_phrase",
                     "parents", "spouse", "flags")
_META_LIST_KEYS = ("parents", "spouse", "flags")
# Date values are always single-quoted on emit. The v3 grammar REQUIRES quoting for
# any value containing a comma or bracket, and a phrase can carry either; quoting
# all four unconditionally keeps one rule instead of a per-value judgement call.
_META_QUOTED_KEYS = DATE_KEYS


def _date_keys_to_write(record, promote=False):
    """Which of the four date keys this write should put in the meta block.

    `promote=True` is the Spec 04 MIGRATION path and the one exception to the rule
    below: the caller is deliberately turning header-derived display prose into a
    field, so a value identical to what was read still gets written. Nothing else
    should pass it — that is the whole point of the default.

    A key qualifies when EITHER:
      * the entry's meta block already carried it (it is a real field, so keep it
        up to date), or
      * the caller CHANGED the value away from what the record was read as (a
        deliberate set, e.g. the Spec 04 migration or a hand edit).

    A value that merely fell back to the header parenthetical, unchanged, is NOT
    written — that is display prose, not a field, and promoting it silently would
    be a whole-vault migration disguised as a no-op write.

    A record with no narrative read provenance — built from scratch, or arriving
    from the FILE backend via `convert_person_model` — has no header it could have
    fallen back to, so the test becomes the value itself: only a FIELD-GRADE value
    (one the grammar accepts) is promoted into the meta block. That keeps a
    `file -> narrative` conversion from turning legacy prose like
    `1969, Somewhereton, MA` into a meta date key; such a value stays in the header
    parenthetical, which is where display prose belongs, exactly as it does today.
    Converting it into a field is the Spec 04 migration's job, with review."""
    raw = record.raw if isinstance(record.raw, dict) else {}
    had = set(raw.get("meta_date_keys") or ())
    read = raw.get("read_dates")
    out = {}
    for k in DATE_KEYS:
        v = getattr(record, k, None)
        if v is None or str(v).strip() == "":
            continue
        if promote:
            out[k] = v
        elif read is None:
            if k in _GRAMMAR_KEYS and not gdate.is_valid(v):
                continue
            out[k] = v
        elif k in had or str(v) != str(read.get(k) or ""):
            out[k] = v
    return out


def _record_to_meta(record, original_meta=None, promote_dates=False):
    """Build a meta dict from a record, preserving any UNMODELED keys the original
    block carried (so a write never silently drops a field the seam doesn't model)."""
    d = {}
    if record.id:
        d["id"] = record.id
    if record.evidence_tier:
        d["evidence_tier"] = record.evidence_tier
    if record.profile_status:
        d["profile_status"] = record.profile_status
    if record.life_status:
        d["life_status"] = record.life_status
    if record.generation is not None:
        d["generation"] = record.generation
    for k in _EXTERNAL_ID_KEYS:
        if (record.external_ids or {}).get(k):
            d[k] = record.external_ids[k]
    if record.parents:
        d["parents"] = list(record.parents)
    if record.spouse:
        d["spouse"] = list(record.spouse)
    if record.flags:
        d["flags"] = list(record.flags)
    # Date keys are written only when they BELONG in the meta block — see
    # _date_keys_to_write. Without that rule, `record.born` (which falls back to
    # the header parenthetical when the meta has no date key) would be written
    # back as a meta key by ANY unrelated write, so a single `mint_ids --apply`
    # would silently migrate the whole vault to values scraped out of prose. That
    # migration is Spec 04's job, done deliberately and with review, not a side
    # effect of minting an id.
    for k, v in _date_keys_to_write(record, promote=promote_dates).items():
        _validate_date_write(k, v, who=f"{record.id or record.name}: ")
        d[k] = v
    modeled = set(_META_FIELD_ORDER) | {"gen", "tier", "wikitree", "ancestry"}
    for k, v in (original_meta or {}).items():
        if k not in d and k not in modeled:
            d[k] = v
    return d


def _emit_meta_line(meta):
    """Serialize a meta dict to a `- meta: {…}` line in the conventional field
    order; list values are single-quoted flow-lists per the v3 grammar."""
    parts = []
    for k in _META_FIELD_ORDER:
        if k not in meta:
            continue
        parts.append(f"{k}: {_meta_val_str(k, meta[k])}")
    for k, v in meta.items():          # any unmodeled leftover keys, stable at end
        if k not in _META_FIELD_ORDER:
            parts.append(f"{k}: {v}")
    return "- meta: {" + ", ".join(parts) + "}"


def _meta_record(meta):
    """A neutral PersonRecord carrying only meta-derived fields (name/vitals blank),
    for comparing two meta blocks by content via PersonRecord equality."""
    return _record_from_meta(meta, "", "", [], -1, "", "", 0)


def _meta_val_str(key, value):
    """Serialize a single meta value: list keys as a single-quoted flow-list,
    date keys as a single-quoted scalar."""
    if key in _META_LIST_KEYS:
        return "'[" + ", ".join(str(x) for x in _listify(value)) + "]'"
    if key in _META_QUOTED_KEYS:
        return "'" + str(value).replace("'", "''") + "'"
    return str(value)


def _split_flow_items(inner):
    """Split a flow-mapping body `k: v, k: v` on TOP-LEVEL commas (respecting
    quotes/brackets). Returns [(key_lower, raw_item_str)] preserving each item's text."""
    items, buf, depth, inq = [], "", 0, None
    for ch in inner:
        if inq:
            buf += ch
            if ch == inq:
                inq = None
        elif ch in "'\"":
            inq = ch; buf += ch
        elif ch in "[{":
            depth += 1; buf += ch
        elif ch in "]}":
            depth -= 1; buf += ch
        elif ch == "," and depth == 0:
            items.append(buf); buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf)
    return [(raw.split(":", 1)[0].strip().lower(), raw) for raw in items]


def _norm_meta_val(v):
    if isinstance(v, list):
        return [str(x) for x in v]
    s = str(v) if v is not None else None
    return _listify(s) if (s and s.startswith("[") and s.endswith("]")) else s


def _apply_meta_changes(orig_line, orig_meta, new_meta):
    """Surgically rewrite a `- meta: {...}` line: replace changed values and insert
    new keys at their canonical slot, while PRESERVING the order and text of every
    untouched key (no reformat — e.g. a spouse-before-parents block stays that way).
    Falls back to a canonical re-emit only for a non-flow (legacy `;`) shape."""
    m = re.match(r"^(\s*-\s*meta:\s*)\{(.*)\}(\s*)$", orig_line)
    if not m:
        indent = re.match(r"^(\s*)", orig_line).group(1)
        return indent + _emit_meta_line(new_meta)
    prefix, inner, suffix = m.group(1), m.group(2), m.group(3)
    items = _split_flow_items(inner)
    present = {k for k, _ in items}

    rebuilt = []
    for k, raw in items:
        if k not in new_meta:
            continue  # key removed
        if _norm_meta_val(new_meta[k]) != _norm_meta_val(orig_meta.get(k)):
            lead = raw[:len(raw) - len(raw.lstrip())]
            rebuilt.append(f"{lead}{k}: {_meta_val_str(k, new_meta[k])}")
        else:
            rebuilt.append(raw)  # unchanged -> byte-preserved

    rank = {kk: i for i, kk in enumerate(_META_FIELD_ORDER)}
    for k in new_meta:
        if k in present:
            continue
        item = f"{k}: {_meta_val_str(k, new_meta[k])}"
        pos = len(rebuilt)
        for idx, it in enumerate(rebuilt):
            if rank.get(it.split(":", 1)[0].strip().lower(), 999) > rank.get(k, 999):
                pos = idx
                break
        rebuilt.insert(pos, item)
    return f"{prefix}{{{', '.join(s.strip() for s in rebuilt)}}}{suffix}"


# --------------------------------------------------------------------------- #
# Public seam
# --------------------------------------------------------------------------- #
_BACKENDS = {"file": FileBackend, "narrative": NarrativeBackend}


def _backend(vault):
    return _BACKENDS[vault_config.get_person_model(vault)]


def backend_name(vault):
    return vault_config.get_person_model(vault)


def iter_people(vault):
    return _backend(vault).iter_people(vault)


def get_person(vault, id):
    for r in iter_people(vault):
        if r.id == id:
            return r
    return None


def write_person(vault, record, promote_dates=False):
    return _backend(vault).write_person(vault, record, promote_dates=promote_dates)


# --------------------------------------------------------------------------- #
def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


if __name__ == "__main__":
    import sys
    _vault = vault_config.resolve_vault(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"backend: {backend_name(_vault)}")
    for r in iter_people(_vault):
        print(f"  {r.id or '(no id)':10} gen={r.generation} {r.name}")
