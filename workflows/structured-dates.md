---
type: workflow
created: 2026-07-22
tags: [genealogy, workflow, dates, gedcom]
---

# Structured dates: writing, migrating, and triaging

How a person's birth and death dates are stored, how to convert legacy prose into
that form, and how to read the gate that keeps the two copies honest.

Spec: `spec/structured-dates/`. Grammar reference:
[FamilySearch GEDCOM 7.0](https://gedcom.io/specifications/FamilySearchGEDCOMv7.html).

## The model in one line

The `- meta:` **field** is the machine value and is authoritative; the **header
parenthetical** is the human display; `DATE_DRIFT` compares their years.

The header keeps what a structured field cannot carry — `near Weymouth, MA`,
`killed King Philip's War`, `christened 3 SEP 1676`, a citation aside. The field
carries a date and nothing else. Neither is redundant.

## Writing a date by hand

Put the value in the meta block, single-quoted, after `fs`:

```
**Jane Example Ancestor** (b. 3 SEP 1780, Somewhereton; d. 1873)
- meta: {id: P-7K3QM2, evidence_tier: strong_signal, profile_status: complete,
         life_status: deceased, generation: 6, fs: XXXX-XXX,
         born: '3 SEP 1780', died: '1873'}
```

The grammar, and when to reach for each production:

| you know | write |
|---|---|
| a full date | `3 SEP 1780` |
| a month | `SEP 1780` |
| a year | `1780` — and `954` is just as valid; there is no floor |
| roughly, source unknown | `ABT 1750` |
| roughly, **because you calculated it** | `EST 1832` ← declarant-age estimates |
| calculated from other data | `CAL 1780` (age-at-death arithmetic) |
| a bound | `BEF 1866` / `AFT 1672` |
| two bounds | `BET 1816 AND 13 FEB 1823` |
| a span | `FROM 1650 TO 1672` (floruits) |
| a non-Gregorian date | `JULIAN 30 JAN 1649` |
| nothing | **omit the key** — never `unknown`, `?`, or `Deceased` |

Check a value before you commit to it:

```bash
python3 scripts/gdate.py '~1750' 'bef. 1866' '6 JAN 1743/4'
```

### `EST` vs `ABT` matters here

`CLAUDE.method.md` insists that declarant-age-derived years are **estimates, not
facts**, with a known ±2-12 year spread. `EST` says exactly that in the data;
`ABT` does not. Use `EST` whenever the year came out of an age field.

### Old Style / New Style

Under Old Style the year began 25 March, so a January-to-March event was written
with both years. Use both keys, and **the DATE takes the NEW STYLE (later) year**:

```
- meta: {…, born: 'JULIAN 30 JAN 1649', born_phrase: '30 January 1648/49'}
```

That is GEDCOM 7 Appendix A §6.2's own example. Taking the earlier year is the
intuitive choice and it is wrong — it backdates every Jan-to-March event by a year,
silently, and only for those months.

## Migrating legacy prose

`scripts/migrate_dates.py` reads each entry's header vitals, runs them through
`gdate.normalise`, and writes the field **only when a valid value comes out**.

```bash
python3 scripts/migrate_dates.py                                    # dry run, whole vault
python3 scripts/migrate_dates.py --file Family_Tree_British_Magna_Carta.md
python3 scripts/migrate_dates.py --apply --file <one file> --verify-headers
python3 scripts/migrate_dates.py --residue "$AUTORESEARCH_VAULT/Structured_Dates_Residue.md"
```

Work **one file at a time**, re-running the gates between files. Always pass
`--verify-headers`: it re-reads every bold-name line after the write and fails the
run if a single byte moved.

What it will not do, and why:

- **It never writes a `*_phrase`.** A phrase asserts what a record actually reads —
  an editorial act. The one exception is the OS/NS dual year, where the phrase is a
  verbatim copy, and even that is opt-in behind `--dual-year`.
- **It never touches a header.** The header is the migration's source.
- **It skips `living` / `unknown`** unless you pass `--include-living`, and even
  then the day-precision privacy screen applies per value: a living person can gain
  `ABT 1980`, never `3 SEP 1980`.
- **It never overwrites an existing date key**, which is what makes re-running it a
  no-op.

Write the residue worklist **into the vault**, never into the framework repo: it
names every person still needing a decision.

## Triaging the residue

Four classes, in the worklist:

| class | what to do |
|---|---|
| `absence` | leave the key absent. `unknown` / `Deceased` / `?` are not dates |
| `place-leak` | a place is sitting in the date slot — fix the header, then re-run |
| `dual-year` | apply with `--dual-year`, or hand-write the DATE + PHRASE pair |
| `unstructurable` | either a `*_phrase` with no date, or resolve the qualifier |

`unstructurable` covers things like `early 1621`, `probably 30 JUN 1842`, and GRO
quarter references. `gdate.normalise` deliberately refuses to guess these into
`ABT` — an approximation you invented is not the same claim as one the record makes.

## Reading DATE_DRIFT

`prose_audit.py` reports it; the SessionStart banner and the vault pre-commit hook
surface it. Baseline **0**, and **BLOCKING** since 22 JUL 2026: a commit whose
header and field disagree on a year fails the hook. It is the only blocking metric
in `prose_audit` — ERROR/WARN judge PROSE, which a human writes and may phrase
loosely, while a DATE_DRIFT finding is two machine-readable copies of one fact
contradicting each other. Override one run with `--no-strict-dates`.

```
DATE_DRIFT:    0   [BLOCKING]  (coverage: field missing 42, header missing 1, neither 483)
```

- **A drift finding** means a header and its field disagree on the YEAR. One of them
  is wrong; fix it, and per integrity rule 7 fix any prose that paraphrases it in
  the same commit.
- **Coverage is not drift.** `field missing` is a migration gap (that entry is on the
  residue worklist), `header missing` is a display gap. Neither is a contradiction,
  which is why they are counted separately.

Years are compared, not strings, so `3 SEP 1780` vs `b. 3 SEP 1780, Boston` agree,
`ABT 1750` vs `~1750` agree, and a dual-dated header reads either year.

## Related

- [workflows/switch-person-model.md](switch-person-model.md) — the same fields
  round-trip through both person models.
- `scripts/gdate.py` — the grammar, `resolve_year`, and the normaliser.
- `scripts/test_gdate.py`, `test_migrate_dates.py`, `test_date_drift.py`.
