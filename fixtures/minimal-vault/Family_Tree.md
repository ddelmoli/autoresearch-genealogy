---
type: reference
created: 2026-05-19
updated: 2026-05-19
tags: [genealogy, fixture, fictional]
---

# Fictional Family Tree Fixture

This fixture is synthetic. Names, places, and source references are invented for testing prompt behavior.

## Direct Line

```
Jordan Example (Living)
└── Parent: Alex Example (Living)
    └── Grandparent: Eleanor Reed (1932-2014)
        ├── Father: Samuel Reed (1904-1978)
        └── Mother: Clara Whitfield (1908-1995)
```

## Reed Family

**Eleanor Reed** (b. 1932, Lake County, Example State; d. 2014, Harbor Town, Example State)
- Married Daniel Mercer in 1954 at Harbor Town, Example State
- Child: Alex Example (Living)
- Sources: [[Sources/Eleanor_Reed_Obituary]], family oral history

**Samuel Reed** (b. 1904 or 1905, Hill Parish, Example Country; d. 1978, Harbor Town, Example State)
- Married Clara Whitfield in 1929
- Parents: unknown
- Sources: [[Sources/Samuel_Reed_Obituary]]

**Clara Whitfield** (b. 1908, Meadow County, Example State; d. 1995, Harbor Town, Example State)
- Parents: unknown
- Sources: [[Sources/Clara_Whitfield_Death_Index]]

## Parser Boundary Fixture

Regression fixture for `spec/entry-boundary`, exercised by
`scripts/test_entry_boundary.py`. The source-census parser once treated ANY bold
`Words (parenthetical)` span as a person-entry header, including one written
mid-sentence, so the span became a body boundary and the `Sources` bullet below it
was credited to a phantom entry instead of to the person.

The entry below contains both populations that trigger it: an institution name with
toponymic particles (indistinguishable from a personal name by shape) and a relative
named in passing. Both are followed by the `Sources` bullet they used to steal, so a
parser that mis-attributes fails visibly here.

**Marta Example** (b. 1868, Example Village; d. 1931, Harbor Town, Example State; FS PID XXXX-XXX)
- meta: {id: P-3XAMP2, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 5, fs: XXXX-XXX, born: '1868', died: '1931'}
- Her birth atto sits in the **Archivio di Stato di Example (Stato Civile)** series, filmed but not indexed.
- Her brother **Paolo Example (1871-1940)** is written up in the collateral file.
- **Sources**
  - 1868 birth atto, Example Village — fs:3:1:YYYY-YYY
  - 1900 census, Harbor Town — fs:1:1:ZZZZ-ZZZ
  - 1931 death certificate, Harbor Town — fs:1:1:WWWW-WWW

## Data Discrepancies

| Person | Field | Source A | Source B | Resolution |
|---|---|---|---|---|
| Samuel Reed | birth_year | 1905 (family tree note) | 1904 (obituary) | UNRESOLVED, needs primary record |

## Privacy Notes

- Jordan Example and Alex Example are living. Autonomous web-search prompts must skip them.
- Exact dates and contact details for living people are intentionally omitted.
