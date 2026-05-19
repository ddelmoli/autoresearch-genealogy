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

## Data Discrepancies

| Person | Field | Source A | Source B | Resolution |
|---|---|---|---|---|
| Samuel Reed | birth_year | 1905 (family tree note) | 1904 (obituary) | UNRESOLVED, needs primary record |

## Privacy Notes

- Jordan Example and Alex Example are living. Autonomous web-search prompts must skip them.
- Exact dates and contact details for living people are intentionally omitted.
