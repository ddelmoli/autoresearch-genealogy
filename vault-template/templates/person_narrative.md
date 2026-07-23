---
type: template
created: YYYY-MM-DD
tags: [genealogy, person, narrative, template]
---

# Person entry template — narrative + meta block (`person_model: narrative`)

Use this when the vault's `.autoresearch.json` sets `person_model: narrative`:
people are recorded as **bold-name entries inside `Family_Tree*.md`** (grouped by
lineage / generation) rather than one file per person. This is a *snippet* to
paste into the right Family_Tree shard, not a standalone file.

The other model, `person_model: file` (the default), gives each person their own
page — see `person.md`. Both encode the same record fields and convert either way
with `scripts/convert_person_model.py`; see
[workflows/switch-person-model.md](../../workflows/switch-person-model.md).

Each entry's FIRST body bullet is a machine-readable `- meta:` block — a valid
YAML flow-mapping. The authoritative grammar and the field-map to the `person.md`
frontmatter live in **`CLAUDE.method.md` → "Person entry meta block"**; this file
is the copy-paste shape.

## Full entry (direct ancestor / sourced person)

```
**[Full Name]** (b. [DateValue], [place]; d. [DateValue], [place]; FS PID [XXXX-XXX])
- meta: {id: P-XXXXXX, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: [N], fs: [XXXX-XXX], born: '3 SEP 1780', died: 'BET 1816 AND 13 FEB 1823'}
- [sourced biographical detail — cite inline, source-first]
- **Sources** (harvested YYYY-MM-DD, N records):
  - [record descriptor, e.g. 1910 US Census, Manhattan] — fs:1:1:AAAA-AAA
  - [record descriptor] — fs:3:1:BBBB-CCCC-DDDD, anc:dbid=NNNN   (one record, several hosts)
```

**Sources grammar:** one sub-bullet per RECORD (the primary source), each carrying
one or more `host:locator` pairs. `host` is a short id from `.autoresearch.json`
`hosts` (`fs`, `antenati`, `metryki`, `szukajwarchiwach`, `agad`, `anc`, `wt`, …);
the locator keeps its namespace (`1:1:` indexed, `3:1:` image, `ark:/12657/…`).
Prefer an ARK where the host mints one. The coverage metric counts RECORDS, not
locators, so a census cited on two sites is ONE record with two locators. The
legacy flat form `- **FS-attached sources**: 1:1:…, 1:1:…` is still accepted on
read (run `scripts/migrate_sources.py` to convert), but write new entries in the
`**Sources**` form.

## Collateral stub (thin kin: a sibling/aunt/cousin worth only a one-line note)

Goes in the file's `## Collateral stub entries` section, gen-sorted:

```
**[Full Name]** (b. ABT [year]; [one-line relationship to a vault anchor])
- meta: {id: P-XXXXXX, profile_status: stub, life_status: deceased, generation: [N]}
```

**Mark the date even here.** A bare year with no `b.` is the terse positional
dialect the header grammar forbids. A stub is still a header.

## Header grammar

The bold-name header has a grammar too, checked at commit time for any header a
commit writes or edits (`scripts/header_audit.py --changed-only`). The rule is
narrow on purpose: **it constrains the DATE SLOT, not the sentence.**

```
**[Name]** (<field>; <field>; …)   [free prose after the paren]
```

- A field opening with **`b.` / `bapt.` / `chr.` / `d.`** (or `born` / `died`)
  MUST carry a valid GEDCOM 7 `DateValue`, or the literal `unknown`. `ABT 1750`,
  not `~1750` or `c.1750`. `BET 1810 AND 1830`, not `1810-1830`.
- A **place goes after the date, behind a comma** — `b. 1810, Villagio` — with
  jurisdictions smallest to largest. Never inside the date slot.
- **Every other field is free prose and stays that way.** `Gen 35`, `a weaver`,
  `alive 1852`, an editorial aside — all legal, INCLUDING when they contain a
  year, because a conforming reader never looks outside a date slot. That is the
  whole point: dates live in declared slots, so nothing else has to be guessed at.
- **No parenthesis inside the DATE SLOT.** Put it after the place
  (`b. 3 SEP 1780, Villagio (parish copy)`), in its own `;` field, or after the
  closing `)`. A paren elsewhere is fine: `Gloucester (Barton St Mary)` is a place
  name, not a dialect.
- Only THIS person's external id belongs in the header.

If the meta block has no `born`/`died`, no vital field is required — the grammar
never asks you to invent a date.

## Meta fields

| field | values | notes |
|---|---|---|
| `id` | `P-` + 6 Crockford base32 (no I/L/O/U) | REQUIRED, unique, never reused. Mint with `python3 scripts/mint_ids.py --apply` |
| `evidence_tier` | `strong_signal` \| `moderate_signal` \| `speculative` | OPTIONAL — omit when unassessed (pairs with `profile_status: stub`) |
| `profile_status` | `stub` \| `partial` \| `complete` | completeness, orthogonal to evidence_tier |
| `life_status` | `living` \| `deceased` \| `unknown` | privacy gate — autonomous web research SKIPS `living` and `unknown` |
| `generation` | integer from the anchor (Gen 1) | REQUIRED for the roster; matches the `### Generation N` heading |
| `fs` | external id, or `TBD` (not searched) / `none` (searched, no profile) | optionally `wt` (WikiTree), `anc` (Ancestry) |
| `born` / `died` | a GEDCOM 7 `DateValue` (or ISO `YYYY-MM-DD`), single-quoted | OPTIONAL — omit if unknown. The MACHINE value; the header parenthetical stays the human display |
| `born_phrase` / `died_phrase` | free text, single-quoted | the GEDCOM 7 PHRASE escape hatch, for what the grammar cannot express |

## Dates

The date lives in **two places with different jobs**: the meta field is the
machine value (gates, sorting, matching, exports) and is AUTHORITATIVE; the header
parenthetical is the human display and keeps what a structured field cannot carry
(`near Weymouth, MA`, `christened 3 SEP 1676`). The `DATE_DRIFT` check compares
the YEARS of the two, so they may differ in wording but not in fact.

```
ABT 1750              near x, exact unknown          (~1750, c.985)
EST 1832              near x, and x is CALCULATED    <- declarant-age estimates go here
CAL 1780              x calculated from other data   (age-at-death arithmetic)
BEF 1866 / AFT 1672   no later / no earlier than x
BET 1816 AND 13 FEB 1823     between two bounds
FROM 1650 TO 1672     lasted across a span           (floruit approximations)
JULIAN 30 JAN 1649    non-Gregorian calendar
954                   a year is a year — no 1500 floor, medieval dates are first-class
```

Rules: **omit the key when the date is unknown** (absence = unknown, never
`unknown` or `?` as a value). **Places stay OUT of the date value** — they belong
in the header. Use `EST` rather than `ABT` for a year derived from a declarant's
stated age, which puts "estimates, not facts" in the data instead of a prose
caveat. Old Style / New Style dual dates use both keys, and the DATE takes the
NEW STYLE (later) year, per GEDCOM 7 Appendix A §6.2:

```
- meta: {id: P-XXXXXX, ..., born: 'JULIAN 30 JAN 1649', born_phrase: '30 January 1648/49'}
```

Check one value with `python3 scripts/gdate.py '~1750'`. Bulk-convert legacy prose
dates with `python3 scripts/migrate_dates.py` (dry-run by default). Full runbook:
[workflows/structured-dates.md](../../workflows/structured-dates.md).

Rules of thumb: every new person needs at minimum `id` + `generation`. Keep the
bold name human-readable (the machine keys on `id`, not the name). Cross-reference
ids (parent/spouse/child) go in a body bullet, never the header. The gen-sorted
roster regenerates on demand:
`python3 scripts/gen_person_index.py --write /tmp/roster.md`.
