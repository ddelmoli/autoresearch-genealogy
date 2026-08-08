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
import pathlib
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
    # Far-end ids of `?`-marked edges on THIS record that have been WALKED AND
    # JUDGED, with the `?` retained deliberately (FS-GAP, scholarly hedge, or
    # privacy). See the `adjudicated` note in CLAUDE.method.md.
    #
    # ** WHY A SEPARATE KEY AND NOT A MARK ON THE TOKEN (deferred 32, 01 AUG 2026). **
    # The obvious design is a third token state, `P-XXXXXX?!`. It cannot work:
    # `build_edges.edge_value` REGENERATES every edge token as
    # `pid + ("" if verified else "?")`, so any suffix beyond the bare `?` is
    # silently destroyed by the next `build_edges --apply` — a data-loss path with
    # no error. `upsert_edges` splices parents:/spouse: "WITHOUT disturbing any
    # other field", so a sibling key survives by construction. Absent key = nothing
    # adjudicated, which is exactly the pre-existing behaviour.
    adjudicated: list = field(default_factory=list)
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
            frozenset(str(a) for a in (self.adjudicated or ())),
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
        adjudicated=list(fm.get("adjudicated") or []),
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
    "parents", "spouse", "flags", "adjudicated",
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
        "adjudicated": record.adjudicated,
    }
    old_vals = {
        "id": old_record.id, "name": old_record.name, "born": old_record.born,
        "died": old_record.died, "born_phrase": old_record.born_phrase,
        "died_phrase": old_record.died_phrase, "generation": old_record.generation,
        "evidence_tier": old_record.evidence_tier,
        "profile_status": old_record.profile_status,
        "life_status": old_record.life_status, "parents": old_record.parents,
        "spouse": old_record.spouse, "flags": old_record.flags,
        "adjudicated": old_record.adjudicated,
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
    for key in ("parents", "spouse", "flags", "adjudicated"):
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
# A `#`/`##`-level heading. Used ONLY as a barrier for the generation fallback:
# a Generation heading below one of these does not govern entries above it, and
# an entry below one does not inherit a Generation heading from above it.
_SECTION_HDR = re.compile(r"^#{1,2}\s+\S")


EXTERNAL_ID_SENTINELS = {"TBD", "NONE", "-", ""}


#: Hosts a banked parent-pair can have been read from. Same short ids as the
#: `hosts` registry; kept small deliberately -- this is a provenance note, not a
#: locator.
BANKED_HOSTS = ("fs", "wt", "anc")

# The closed vocabulary of `adjudicated_why`. The first four say why a `?` EDGE
# survives adjudication (deferred 38). `no-second-parent` says why an entry names
# only ONE parent (deferred 50, operator-directed 04 AUG 2026) — a different kind
# of statement, about an ABSENCE rather than about an edge.
ADJUDICATED_WHY = ("fs-gap", "hedge", "contradicted", "privacy", "no-second-parent")


def adjudicated_why_values(record_or_line):
    """Return `adjudicated_why` as a LIST of reasons (possibly empty).

    ** WHY A LIST, WHEN THE KEY SHIPPED AS A SCALAR (deferred 50, 04 AUG 2026). **
    `no-second-parent` had to share the key with the existing edge reasons, and on
    the reference vault **14 of the 109 half-wired rows already carried one**
    (`fs-gap`, `hedge`, `contradicted`) with a real `adjudicated` list beside it.
    A scalar could not hold both, and silently overwriting an `fs-gap` would have
    switched off that row's re-check (see `session_plan.lane_defects`).

    ⚠⚠ AND THE OBVIOUS FIX IS A TRAP THIS FUNCTION EXISTS TO CLOSE. Writing
    `adjudicated_why: fs-gap, no-second-parent` is invalid: the meta block is a YAML
    flow-mapping, so a value containing a comma MUST be single-quoted — and the
    reader that had consumed this key used `adjudicated_why:\\s*([a-z\\-]+)`, which a
    leading quote does not match AT ALL. The row would have parsed as having NO
    reason, silently disabling the `fs-gap` re-check while the entry advertised it.
    That is the same shape as the `?`-suffix data loss that made `adjudicated` a
    sibling key rather than a token suffix.

    So the accepted forms are, and a conforming reader takes BOTH:
      * bare scalar, the legacy form   — `adjudicated_why: fs-gap`
      * single-quoted flow list        — `adjudicated_why: '[fs-gap, no-second-parent]'`

    Existing entries are NOT migrated: the bare form stays valid and is what all 46
    current rows use. Only a row that genuinely needs two reasons takes the list.

    Unrecognised tokens are DROPPED rather than returned, so a typo cannot invent a
    reason — but note the asymmetry with `banked_parents`: there an unknown value
    means "absent", here it means one reason of several may be silently ignored.
    `ADJUDICATED_UNEXPLAINED` is what surfaces the resulting empty case.

    Accepts a PersonRecord (reads the meta line out of `raw`) or a raw meta line.
    """
    line = record_or_line
    if not isinstance(line, str):
        raw = getattr(record_or_line, "raw", None)
        if not isinstance(raw, dict):
            return []
        line = next((v for v in (raw.get("line"), raw.get("meta_line"))
                     if isinstance(v, str) and _META.match(v)), "")
    m = _META.match(line or "")
    if not m:
        return []
    body = m.group(1).strip()
    if not body.startswith("{"):
        return []
    for part in _flow_split(body):
        k, sep, v = part.partition(":")
        if sep and k.strip().lower() == "adjudicated_why":
            v = v.strip().strip("'\"").strip()
            v = v.lstrip("[").rstrip("]")
            vals = [t.strip().lower() for t in v.split(",") if t.strip()]
            return [t for t in vals if t in ADJUDICATED_WHY]
    return []


def banked_parents_host(record_or_line):
    """Return the host a BANKED-BUT-UNWIRED parent pair was read from, or None.

    ** THE MECHANISM (operator-directed, 04 AUG 2026). ** An EXPAND draw regularly
    finds that a frontier row's parents ARE named on FamilySearch, and the standing
    rule is not to wire them: an FS couple is a TREE ASSERTION, not a source, and
    wiring it would grow the vault on somebody else's conclusion. So the row is
    DECLARED with both parent PIDs banked in its prose and no edge minted.

    That was the right call and it created a hole. The row now counts as DECLARED,
    so `extension_frontier` reads it as closed and EXPAND never offers it again --
    while the work is real, located, and cheap to finish (find one record naming
    the parents, then wire with a `?`). Measured 04 AUG 2026: **11 rows, 7 from
    session #138 and 4 from #139, holding ~22 parent PIDs, none of those parents
    present in the vault.** It grew 7 -> 11 in two sittings with nothing drawing it
    -- the same shape as the FS write-back queue.

    ** WHY A META KEY AND NOT A PROSE MATCH. ** The obvious detector is a grep for
    the declaration wording. This vault has already ruled against exactly that: when
    rule 8 limb (g) was added, making the bullet NAME load-bearing in code was
    "considered and NOT taken -- it would make bullet TEXT a failure surface, where a
    typo silently starts counting". A prose detector also double-counts, because
    `route_digest` blockquotes entry text at the head of every lineage file -- the
    first count taken while designing this read 27 declarations where the true
    number was 11, the identical trap the `? edge` grep documents.

    ** WHY A SCALAR AND NOT A LIST OF PIDs. ** The lane needs to SELECT the row; the
    researcher needs the PIDs, and those are already in the entry prose where they
    are read. Storing them twice would create a second copy to drift. The value is
    the HOST, so the key generalises past FamilySearch without a grammar change.

    ** WHY IT IS SAFE AS AN UNMODELED KEY. ** `_record_to_meta` preserves "any
    UNMODELED keys the original block carried (so a write never silently drops a
    field the seam doesn't model)", the file backend's frontmatter write is likewise
    surgical, and `build_edges.upsert_edges` splices `parents:`/`spouse:` without
    disturbing sibling keys -- the same three guarantees that make `adjudicated`
    safe. So this needs no change to `PersonRecord`, and a `narrative <-> file`
    conversion round-trips it.

    Accepts a PersonRecord (reads the meta line out of `raw`) or a raw meta line.
    Returns one of BANKED_HOSTS, or None when the key is absent or malformed.

    ⚠ The narrative backend's `raw` carries `meta_line` as a line NUMBER and the
    TEXT as `line`; picking by name alone got an int here and raised. Take the
    first value that is actually a meta line, so neither key name is load-bearing.
    """
    line = record_or_line
    if not isinstance(line, str):
        raw = getattr(record_or_line, "raw", None)
        if not isinstance(raw, dict):
            return None
        line = next((v for v in (raw.get("line"), raw.get("meta_line"))
                     if isinstance(v, str) and _META.match(v)), "")
    m = _META.match(line or "")
    if not m:
        return None
    body = m.group(1).strip()
    if not body.startswith("{"):
        return None                       # legacy `;` form carries no fields
    for part in _flow_split(body):
        k, sep, v = part.partition(":")
        if sep and k.strip().lower() == "banked_parents":
            v = v.strip().strip("'\"").lower()
            return v if v in BANKED_HOSTS else None
    return None


_ENTRY_TEXT_CACHE = {}


def entry_text(record):
    """Return an entry's FULL text -- header line plus body -- or "" if unavailable.

    ** WHY THIS EXISTS (deferred_decisions 23, 07 AUG 2026). ** Consumers that need
    an entry's PROSE were reading `record.raw["header_text"]`, which is the header
    line alone. Measuring the `ABT`-vs-`EST` population that way reported **5**
    candidates where the real figure was ~83 -- a **16x undercount produced by the
    ACCESSOR, not the data**, and one that nothing would have flagged: 5 is a
    plausible-looking number.

    The narrative backend already computes each entry's body span (its body runs
    from the meta line to the NEXT entry's header, which is the entry-boundary rule
    in spec/entry-boundary). It was simply being discarded. Recording it here means
    no caller has to re-implement that boundary -- and a caller that does
    re-implement it is how entries get silently truncated.

    ⚠ Model-agnostic by design: on the `file` backend an entry IS its file, so the
    whole file below the frontmatter is returned.

    ⚠ The file is read once and cached by path. Callers iterating the whole vault
    would otherwise re-read each lineage file per person.
    """
    raw = getattr(record, "raw", None)
    if not isinstance(raw, dict):
        return ""
    path = raw.get("path")
    if not path:
        return ""
    try:
        lines = _ENTRY_TEXT_CACHE.get(path)
        if lines is None:
            lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
            _ENTRY_TEXT_CACHE[path] = lines
    except OSError:
        return ""
    hline = raw.get("header_line")
    bend = raw.get("body_end")
    if isinstance(hline, int) and isinstance(bend, int):
        return "\n".join(lines[hline:bend])
    return "\n".join(lines)          # file model: the entry is the file


ROUTE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROUTE_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


def fs_probed(record_or_line):
    """Return the ISO date FamilySearch was verified EMPTY for this person, or None.

    ** WHY A DATED NEGATIVE (operator-directed, 07 AUG 2026, Open_Questions Q157 +
    deferred_decisions 51). ** The vault could already say "searched, no profile"
    (`fs: none`) and "cannot ever be sourced here" (`structural_gap`). It could NOT
    say WHEN the check happened, and an undated negative is treated as expired on
    sight -- so the row is re-offered every rotation for ever.

    Measured 07 AUG 2026: the two structural ROTATE arms (BOOK_SOURCED 261,
    UNCITED 94) hit at **0.17 and 0.15** against 0.43-0.48 for every other arm,
    because the poll is an FS probe and these are people FamilySearch will never
    index. They are **26% of the rotation pool**. Two rows in one sitting were
    re-polled purely because their negative carried no date.

    ⚠ **This is NOT `fs: none`.** `fs: none` says no PROFILE exists. This says the
    profile (or its absence) was checked and carries **no attached sources** -- a
    positive read of an empty set at the `entityref` endpoint, which is a different
    and stronger statement than a failed render. A person may legitimately have a
    live PID and `fs_probed` on the same day.

    ⚠ **A date is not a licence to stop looking.** It records when the answer was
    true, so a consumer can decide whether to re-ask. Pair it with `route` to say
    where the evidence actually lives.
    """
    v = _meta_key_value(record_or_line, "fs_probed")
    return v if v and ROUTE_DATE_RE.match(v) else None


def banked_parents_settled(record) -> bool:
    """True when a `banked_parents` note has been OVERTAKEN and should be pruned.

    ** Q238, option 1 (operator, 08 AUG 2026): the exit test is COMPLETENESS, not
    PRESENCE. ** It was "has any `parents` edge", which made the key unusable on a
    HALF-WIRED row -- exactly the case where a second parent is located and not
    wired. Adding it to such a row fired `BANKED_STALE` immediately (verified on two
    rows, 08 AUG), so the find could only be recorded in prose, where no builder
    reads it. That is the failure `banked_parents` exists to prevent, reappearing one
    case to the left.

    A row is settled when it has **TWO** parents, or when it declares
    `no-second-parent` -- which is precisely the "one parent is CORRECT" terminal
    state, so it belongs in this test rather than fighting it.

    ⚠ Measured before the change: **all 27 rows then carrying `banked_parents` had
    ZERO parents**, so this regressed nothing, and it unlocked **95 still-open
    half-wired rows**.

    ONE PREDICATE, TWO READERS -- `build_edges --validate` (the BANKED_STALE gate) and
    `session_plan.lane_banked` (the worklist) both call it, so the gate and the lane
    cannot disagree about which rows are done. Same discipline as `gen_mismatches`
    and `half_wired_rows`.
    """
    # Accepts a PersonRecord or a raw `- meta:` LINE, because the gate
    # (`build_edges --validate`) works from parsed meta and the lane from records.
    # One predicate must serve both or they drift -- that is the whole point of it.
    if isinstance(record, str):
        parents = _meta_key_value(record, "parents") or ""
        toks = [t for t in re.split(r"[\[\],\s]+", parents) if t]
    else:
        toks = [str(x).strip() for x in (getattr(record, "parents", None) or [])
                if str(x).strip()]
    if len(toks) >= 2:
        return True
    return "no-second-parent" in (adjudicated_why_values(record) or [])


def fs_absent(record_or_line):
    """Return the ISO date it was verified that NO FamilySearch profile exists, or None.

    ** deferred_decisions 56, option 2 (operator, 08 AUG 2026). ** `fs: none` means
    "searched, nothing is there", and it CANNOT CARRY A DATE. The EXISTENCE_PROBE arm
    treats an undated negative as expired on sight, so every such row returned every
    cycle, for ever. One entry had the diagnosis written on it by an earlier session
    that could not fix it, because the grammar had nowhere to put the date.

    ⚠⚠ **THIS IS NOT `fs_probed`, AND THE TWO ARE EASY TO CONFUSE. They answer
    different questions:**

        fs_probed   a profile (or its absence) was checked and carries NO RECORDS.
                    A person may hold a LIVE PID and `fs_probed` on the same day.
        fs_absent   NO PROFILE EXISTS AT ALL. Pairs with `fs: none`.

    A row can legitimately carry both, and they are not redundant: one is about the
    attached-source set, the other about the profile's existence.

    ⚠ **IT DOES NOT SUPPRESS IN IMPROVE, deliberately, and that asymmetry with
    `fs_probed` is a decision rather than an oversight.** `fs_probed` suppresses a
    SOURCE_GAP row (deferred 58) because it says the sources were READ and are empty.
    `fs_absent` says only that FamilySearch has no profile -- which is silent about
    whether records exist in an archive, a register or a book. Those rows already
    route to non-FS in the IMPROVE worklist, and suppressing them there would hide
    real work behind a fact about the wrong repository.

    ⚠ **A date is not a licence to stop looking**, and ⛔ **do not write one for a
    probe you did not perform** -- an invented date silences a real worklist row,
    which is strictly worse than no date at all. Measured 08 AUG 2026: **13 entries
    carry `fs: none` (NOT the 44 an earlier prose-grep reported), and 9 of the 13 are
    ANSWERABLE** through a relative's family panel.
    """
    v = _meta_key_value(record_or_line, "fs_absent")
    return v if v and ROUTE_DATE_RE.match(v) else None


def route(record_or_line):
    """Return the slug naming WHERE this person's records actually are, or None.

    ** THE MISSING PRIMITIVE (operator-directed, 07 AUG 2026). ** The vault could
    express "this person cannot be sourced" (`structural_gap`) but not "this person
    CAN be sourced, just not on FamilySearch" -- so Open_Questions Q157's remainder
    (six people, four of whom died AFTER civil registration began and one of whom
    lived 1876-1937) had nowhere to go except an opaque `pids` enumeration in
    `structural_gap` rule 3. That is the enumeration pattern the operator ruled
    against on 05 AUG 2026 in favour of stating the CRITERION.

    The value is a short slug -- a registered host id where one fits (`metryki`,
    `jri`, `agad`, `antenati`, `anc`), or an archive slug where the route is
    in-person (`como-diocesan`, `aquila-diocesan`, `as-sondrio`).

    ⚠ **UNRECOGNISED SLUGS ARE RETURNED, NOT DROPPED**, which is the opposite of
    `adjudicated_why_values`. That vocabulary is tiny and closed, so dropping a typo
    is safe. Routes are open-ended -- every archive in the world is a potential
    value -- so dropping an unknown would make a declaration silently fail, which is
    exactly the failure mode this key exists to remove. A validator may WARN on a
    slug outside the known set; the reader must not swallow it.

    ⚠ Shape only is enforced (lowercase slug, 2-40 chars), so a stray sentence or a
    quoted phrase does not become a route.
    """
    v = _meta_key_value(record_or_line, "route")
    return v if v and ROUTE_SLUG_RE.match(v) else None


def _meta_key_value(record_or_line, key):
    """Read one scalar key out of a `- meta:` flow mapping. Shared by the readers
    above so the parsing lives in ONE place, per the two-readers-one-entry rule."""
    line = record_or_line
    if not isinstance(line, str):
        raw = getattr(record_or_line, "raw", None)
        if not isinstance(raw, dict):
            return None
        line = next((v for v in (raw.get("line"), raw.get("meta_line"))
                     if isinstance(v, str) and _META.match(v)), "")
    m = _META.match(line or "")
    if not m:
        return None
    body = m.group(1).strip()
    if not body.startswith("{"):
        return None
    for part in _flow_split(body):
        k, sep, v = part.partition(":")
        if sep and k.strip().lower() == key:
            return v.strip().strip("'\"").lower() or None
    return None


def external_id_state(value):
    """Classify an external-id field (`fs`, `wt`, `anc`) into ONE of four states.

    ** deferred_decisions 41 (02 AUG 2026), option 2. ** `fs: none` was carrying
    two situations with OPPOSITE consequences:

      ABSENT   -- searched, nothing is there. Creating the person on that
                  platform is the CORRECT next action.
      REJECTED -- something IS there and the vault declined it (a conflicting
                  profile, an unreliable structure, the wrong man). Creating is
                  exactly WRONG: it would push a duplicate onto a shared tree.

    Nothing in the data separated them. The distinction survived only in prose,
    in a header bullet, in two entries out of the whole vault -- and a
    create-and-attach write-back was proposed on the strength of the bare
    `none` and withdrawn only because someone happened to read the entry.

    A REJECTED profile is now written as the PID with a `~` prefix
    (`fs: ~XXXX-XXX`), reusing the convention `~locator` already established for
    sources: **a thing you have deliberately declined is RECORDED, not erased.**
    The PID is what makes the rejection re-checkable; a rejection with no
    identifier decays into an unfalsifiable claim.

    Returns "live" | "rejected" | "unknown" | "absent".
      live      a real PID a harvest/walk can be run against
      rejected  a real PID that was examined and declined -- NOT harvestable,
                NOT re-checkable, and NOT a reason to create anything
      unknown   `TBD` -- not yet searched
      absent    `none` / empty -- searched, genuinely nothing there
    """
    v = ("" if value is None else str(value)).strip()
    if v.startswith("~"):
        return "rejected" if v[1:].strip() else "absent"
    return "unknown" if v.upper() == "TBD" else (
        "absent" if v.upper() in EXTERNAL_ID_SENTINELS else "live")


def live_external_id(value):
    """The PID string only when it is LIVE; otherwise None.

    Use this anywhere a PID is about to be fetched, harvested or walked. A
    `~`-prefixed (rejected) PID deliberately returns None -- it is recorded so a
    human can re-check it, never so a tool can act on it.
    """
    v = ("" if value is None else str(value)).strip()
    return v if external_id_state(v) == "live" else None


def rejected_external_id(value):
    """The bare PID of a REJECTED profile (no `~`), else None.

    For the reader that genuinely wants the declined id -- a report, a
    re-check worklist, a duplicate audit.
    """
    v = ("" if value is None else str(value)).strip()
    return v[1:].strip() if external_id_state(v) == "rejected" else None


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


def set_meta_key(line, key, value):
    """Set `key` on a `- meta:` line, REPLACING it in place if already present.

    ** THE WRITER-SIDE HALF OF deferred 25 (02 AUG 2026). ** The gate
    (`gen_person_index.duplicate_meta_keys`) DETECTS a duplicated key after the
    fact; this stops one being written. A meta block is valid YAML flow mapping
    and LAST WINS, so prepending `fs: <pid>` to a line that already carries
    `fs: TBD` silently discards the new value and leaves every gate green — which
    is exactly what happened once, and was caught only because two lanes
    contradicted each other.

    Anything banking an external id (`fs`, `wt`, `anc`) into a meta block should
    go through here rather than splicing text. Returns the new line; the input is
    not mutated. A non-meta line, or the legacy `;` form, is returned UNCHANGED —
    this deliberately does not invent a flow mapping where none exists.

    New keys are inserted before `flags:` when present (kept last by convention),
    else before the closing brace, matching `build_edges.upsert_edges`.
    """
    m = _META.match(line)
    if not m:
        return line
    raw = m.group(1).strip()
    if not raw.startswith("{"):
        return line                       # legacy `;` form: not ours to rewrite
    val = _flow_quote("" if value is None else str(value))
    items = _flow_split(raw)
    out, replaced = [], False
    for part in items:
        k, sep, _ = part.partition(":")
        if sep and k.strip().lower() == key.lower():
            if replaced:
                continue                  # collapse a PRE-EXISTING duplicate
            out.append(f"{k.strip()}: {val}")
            replaced = True
        else:
            out.append(part.strip())
    if not replaced:
        idx = next((i for i, p in enumerate(out)
                    if p.split(":", 1)[0].strip().lower() == "flags"), len(out))
        out.insert(idx, f"{key}: {val}")
    return line[:m.start(1)] + "{" + ", ".join(out) + "}" + \
        line[m.start(1) + len(m.group(1)):]


def _flow_quote(v):
    """Single-quote a flow-mapping value when the vault's convention wants it.

    ** ADDED 03 AUG 2026 (deferred 23). ** `set_meta_key` wrote the value RAW, so
    banking `EST 1795` produced `born: EST 1795` where every hand-written date in
    the corpus reads `born: 'EST 1795'`. Both parse -- a plain scalar with a space
    is legal YAML -- so no gate could see it, and 51 rows were written that way
    before a `grep` for the quoted form came back with 4 instead of 51.

    Quote when the value contains a SPACE, a comma or a bracket. A bare token
    (`TBD`, `none`, a PID, an integer) stays unquoted, which is how the corpus
    writes those. Already-quoted input is passed through untouched so callers that
    quote for themselves are not double-wrapped.
    """
    if not v:
        return v
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        return v
    return f"'{v}'" if re.search(r"[\s,\[\]{}]", v) else v


def _flow_split(s):
    """Top-level comma split of a flow mapping body (quote- and bracket-aware)."""
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
    return [p for p in out if p.strip()]


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
    # The MARKED dialect is the only one read. The old marker-less fallback
    # (_terse_vitals) was retired 23 JUL 2026 once the Spec 04 migration brought
    # every terse header to a `b.`/`d.` form and the last 4 records that depended
    # on it gained a meta date key. Its removal was measured on the whole corpus:
    # 0 records changed born/died/phrase/generation. A header with no marker now
    # simply yields no vitals — which is correct, because a marker-less
    # parenthetical is exactly the shape that wrote 25 wrong values by guessing.
    clean = lambda s: re.sub(r"[*\[\]`]", "", s).strip(" ,")
    return clean(born), clean(died)


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


def _record_from_meta(meta, name, rest, gens, header_line, path, vault, meta_line,
                      barriers=()):
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
        # Fall back to the nearest preceding `### Generation N` heading -- but NEVER
        # across a `##`-level section boundary (deferred_decisions 10, fixed 31 JUL
        # 2026). A `## Collateral stub entries` section carries no Generation
        # headings of its own, so the nearest preceding one could sit ~180 lines and
        # three unrelated sections above: an entry that deliberately omitted
        # `generation` was silently relabelled 28 -> 30 and duly reported as a Gen-30
        # frontier row. No gate objected, because NEEDS_META is satisfied by a
        # generation being FOUND, not by its being right -- and the vault's own "the
        # meta block is the source of truth, not the heading" rule was quietly
        # inverted. Stopping at the boundary yields generation None instead, which is
        # honest: it says "undetermined", and NEEDS_META reports it.
        for go, gn in gens:
            if go > header_line:
                break
            if any(go < b <= header_line for b in (barriers or ())):
                continue        # a section boundary sits between that heading and us
            gen = gn
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
        adjudicated=_listify(meta.get("adjudicated")),
        sources=[],  # narrative sources live in a body bullet; populated in Spec 04c
        source_file=(os.path.relpath(path, vault) if path else None),
        raw={"path": path, "meta_line": meta_line, "header_line": header_line,
             # Backend artifacts for Spec 03/06. `header_vitals` is what the header
             # parenthetical says (the DATE_DRIFT comparison target); `read_dates`
             # is what this record was READ as, which is how write_person tells a
             # deliberate change from a value that merely fell back to the header.
             "header_vitals": (hborn or None, hdied or None),
             "header_paren": _vitals_paren(name, rest),
             # the WHOLE header line. Attestation asks "does the header say this
             # year anywhere?", which must not be narrowed to the one parenthetical
             # the vitals parser happened to pick: an entry may carry an editorial
             # aside first and its vitals in a later paren.
             "header_text": f"{name} {rest or ''}",
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
    def _iter_entries(vault):
        """Yield (record, path, header_line_index, block_lines) per entry.

        The single narrative scan. `iter_people` drops everything but the record;
        `iter_entry_blocks` keeps the block, which is what a consumer needs when it
        must read an entry's BODY rather than its fields — e.g. the source-coverage
        census counting the records cited inside each entry.
        """
        for path in sorted(glob.glob(os.path.join(vault, "Family_Tree*.md"))):
            lines = _read(path).splitlines()
            gens = [(i, int(mm.group(1))) for i, ln in enumerate(lines)
                    for mm in [_GEN_HDR.match(ln)] if mm]
            # Section boundaries the generation fallback must not reach across: any
            # heading at `#`/`##` level that is not itself a Generation heading.
            # See _record_from_meta and deferred_decisions 10.
            barriers = [i for i, ln in enumerate(lines)
                        if _SECTION_HDR.match(ln) and not _GEN_HDR.match(ln)]
            # Pass 1: locate each entry (its bold header line + its `- meta:` line).
            # Detection is META-ANCHORED: a bold line is a header only when a
            # `- meta:` line follows it, which is why no shape heuristic is needed
            # and why bold PROSE can never be mistaken for an entry.
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
                rec = _record_from_meta(meta, name, rest, gens, hline, path, vault, mline,
                                        barriers=barriers)
                rec.sources = _extract_sources(lines[mline + 1:body_end])
                rec.raw["line"] = lines[mline]   # raw meta line (consumers re-parse it as `block`)
                # The body span is computed here anyway and was being thrown away by
                # `iter_people`, which yields only the record. Recording it is what lets
                # `entry_text()` read an entry's PROSE without every caller re-implementing
                # the entry-boundary rule -- see deferred_decisions 23, where reading only
                # `header_text` produced a 16x undercount.
                rec.raw["body_start"] = mline + 1
                rec.raw["body_end"] = body_end
                yield rec, path, hline, lines[hline:body_end]

    @staticmethod
    def iter_people(vault):
        for rec, _path, _hline, _block in NarrativeBackend._iter_entries(vault):
            yield rec

    @staticmethod
    def iter_entry_blocks(vault):
        for rec, path, hline, block in NarrativeBackend._iter_entries(vault):
            yield rec, path, hline, "\n".join(block)

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
                     "parents", "spouse", "flags", "adjudicated")
_META_LIST_KEYS = ("parents", "spouse", "flags", "adjudicated")
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
    if record.adjudicated:
        d["adjudicated"] = list(record.adjudicated)
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


def iter_entry_blocks(vault):
    """Yield (record, path, header_line_index, block_text) per person entry.

    `iter_people` gives a consumer the FIELDS; this gives it the entry's raw
    Markdown BLOCK as well, for the consumers that must read what is written inside
    an entry — the source-coverage census counts the record locators cited there.
    Model-agnostic like the rest of the seam: on the file model each person IS a
    file, so the block is that file's text.
    """
    backend = _backend(vault)
    if hasattr(backend, "iter_entry_blocks"):
        return backend.iter_entry_blocks(vault)
    return ((r, r.raw.get("path", ""), 0, r.raw.get("text", ""))
            for r in backend.iter_people(vault))


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
