---
type: workflow
created: 2026-07-23
tags: [genealogy, workflow, headers, gedcom]
---

# Header grammar: writing, checking, and migrating a bold-name header

What a person entry's bold-name header may contain, how the gate reads it, and
what to do when a header will not conform.

Spec: `spec/header-grammar/`. Grammar reference:
[FamilySearch GEDCOM 7.0](https://gedcom.io/specifications/FamilySearchGEDCOMv7.html).

## The rule in one line

**The grammar constrains the DATE SLOT, not the sentence.**

A field that opens with `b.` / `bapt.` / `chr.` / `d.` (or `born` / `died`) must
carry a valid GEDCOM 7 `DateValue`, or the literal `unknown`. Everything else in
the header is free prose and stays that way — *including when it contains a year*,
because a conforming reader never looks outside a date slot.

```
**[Name]** (<field>; <field>; …)   [free prose after the paren]
```

That last point is the whole design. `Gen 35`, `a weaver`, `alive 1852` (a
floruit), `atto 534` are all legal and all unread. Those exact values are what the
old positional guessing turned into birth dates — 25 of them — and the fix was to
stop scavenging, not to ban the prose.

## Writing a header by hand

```
**Jane Example Ancestor** (b. 3 SEP 1780, Somewhereton; d. 1873; FS PID XXXX-XXX)
**Jane Example Ancestor** (b. ABT 1750; d. unknown; a weaver; FS PID XXXX-XXX)
**Jane Example Ancestor** (b. EST 1832, Villagio) — declarant age 47 in 1879
**Jane Example Ancestor** (d. BET 1816 AND 13 FEB 1823, likely at sea)
**Jane Example Ancestor** (b. ABT 975; d. 1045; Gen 35; FS PID XXXX-XXX)
```

Five things to get right, each of which exists because breaking it caused a defect:

1. **Mark the vitals.** `b.` / `d.`, never positional. `(c.966; 23 APR 1016)` is the
   dialect that caused the damage: nothing tells a reader which number is which.
2. **The date slot is a `DateValue`.** `ABT 1750`, not `~1750` or `c.1750`.
   `BET 1810 AND 1830`, not `1810-1830`. `BEF 1866`, not `bef. 1866`. Same grammar
   as the meta field — check one with `python3 scripts/gdate.py '<value>'`.
3. **The place follows a comma**, jurisdictions smallest to largest:
   `b. 1810, Villagio, Provincia, Italy`. Never inside the date slot. Depth is not
   mandated — a bare `Villagio` is fine.
4. **No parenthesis inside the date slot.** Put it after the place, in its own `;`
   field, or after the closing `)`. A paren elsewhere is fine: `Gloucester (Barton
   St Mary)` is a place name.
5. **Absence is spelled `unknown`**, not `Deceased`, `?` or `—`.

If the meta block carries no `born`/`died`, **no vital field is required.** The
grammar never asks you to invent a date.

Copy-paste shape: `vault/templates/person_narrative.md`.

## The gate

`header_audit.py --changed-only` runs in the vault pre-commit hook and **BLOCKS**
any header this commit writes or edits. It is scoped to changed header LINES, so:

- editing a body bullet in a file full of legacy violations passes;
- touching a legacy header for any reason opts it in — burn down what you touch.

It reads the **index**, not the working tree, so unstaged edits cannot shift the
lines it grades.

```bash
python3 scripts/header_audit.py                      # whole vault, advisory
python3 scripts/header_audit.py --rule R4 --limit 20 # one rule
python3 scripts/header_audit.py --changed-only       # what the hook runs
```

The failure message states the FIX, not just the diagnosis. If you genuinely need
one commit through, `--no-strict-headers`, but prefer fixing the header.

## The rules and their codes

| code | rule | typical fix |
|---|---|---|
| R2 | no paren inside a **date slot** | move it after the place or into a `;` field |
| R3 | a marked field's date slot must be a `DateValue` | `~1750` -> `ABT 1750` |
| R4 | a record with dates must expose a marked vital field | add `b. ` / `d. ` |

R1 (the vitals paren is the first balanced one), R5 (years in prose are not dates),
R6's ordering half and R7 (own id only, policed by `header_xref_audit`) are not
separately checkable here. Full text: `spec/header-grammar/01_grammar.md`.

## Migrating legacy headers

```bash
python3 scripts/migrate_headers.py                       # dry run, R3 date slots
python3 scripts/migrate_headers.py --file <file> --apply
python3 scripts/migrate_headers.py --phase b             # R4 vital tags
python3 scripts/migrate_headers.py --refusals            # the worklist
```

**The invariant: no date value changes, and no non-date content is lost.** Both
halves are checked per entry, never sampled, and both have caught real defects —
the second one caught proposals that would have deleted a place, a civil-record
reference and a name variant while every date stayed identical.

Two sanctioned exceptions, both gated on the meta field:

- an **Old Style/New Style dual** moving to its New Style year (`1696` -> `1697`),
  because the field already holds the NS year and the header is coming into
  agreement with it;
- a **year gained** where the header had none (`c.693/709` -> `BET 693 AND 709`).

A year **lost** is always a hard failure.

The migrator is **all-or-nothing per header**: if any field on a line is refused,
the others are left alone. A half-migrated header is worse than an untouched one
because it looks done.

Standing discipline for any apply: read the whole diff, confirm insertions equal
deletions, and confirm a word-level comparison of the non-date content shows zero
differences — **against the git diff itself, not the tool's own report.**

## Triaging the residue

`vault/Header_Grammar_Residue.md` holds every field the migrator refused, grouped
by reason. The tool will not invent, drop, or reinterpret a date, so these are
human calls. The recurring shapes:

| shape | what to do |
|---|---|
| `1843 [GRO Q3]`, `9 SEP 1764 "Mary Wix," Horsley` | move the note or alias out of the date slot, then the date normalises |
| `fl. c.960`, `alive 1852` | a **floruit is not a vital**. Leave it as a note field; if the record has no dates, nothing is required |
| `21 or 22 MAR 1837` | pick one and record the doubt in prose, or `BET 21 MAR 1837 AND 22 MAR 1837` |
| `~1650s`, `early 1621` | a vague phrase. `BET 1650 AND 1659` if you mean the decade, else leave it |
| `2 APR c.747/748` | April cannot be an OS/NS dual, so it is a span: `BET 747 AND 748` |
| `947 per the king-list` | move the attribution out; the date is `947` |

## Two traps worth knowing

**`YYYY/YYYY` is two different things.** `6 JAN 1743/4` is an Old Style/New Style
dual year and resolves to **1744** (GEDCOM 7 Appendix A §6.2 — the DATE takes the
NEW STYLE year). `944/945` is a medieval "one year or the other" span and becomes
`BET 944 AND 945`. They are told apart by the CALENDAR, not the arithmetic: a dual
can only arise between 1 January and 24 March, so it needs a day and a Jan/Feb/Mar
month. `944/945` is consecutive and would fool a naive check.

**A `\b` after punctuation does not match at end of string.** `\?+\b` never matches
a bare `?`. This mis-fired three separate times in this lane. If a pattern ending in
punctuation silently matches nothing, check this first.

## Related

- `workflows/structured-dates.md` — the meta `born`/`died` fields and `DATE_DRIFT`
- `spec/header-grammar/` — the grammar, the validator, the migration and their
  measurements
- `CLAUDE.method.md` — the authoring convention, stated where entries are written
