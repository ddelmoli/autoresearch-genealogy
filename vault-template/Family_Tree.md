---
type: reference
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [genealogy, family-tree]
---

# Family Tree

Complete merged family tree. All dates sourced; unsourced dates marked with `(unverified)`. Living or possibly living people should be marked as `Living` and should not include exact birth dates or contact details.

## Direct Line

```
YOU (Living)
├── [PARENT-1] (b. YYYY, d. YYYY)
│   ├── [GRANDPARENT-1] (b. YYYY, d. YYYY)
│   │   ├── [GREAT-GRANDPARENT-1] (b. YYYY, d. YYYY)
│   │   └── [GREAT-GRANDPARENT-2] (b. YYYY, d. YYYY)
│   └── [GRANDPARENT-2] (b. YYYY, d. YYYY)
│       ├── [GREAT-GRANDPARENT-3] (b. YYYY, d. YYYY)
│       └── [GREAT-GRANDPARENT-4] (b. YYYY, d. YYYY)
└── [PARENT-2] (b. YYYY, d. YYYY)
    ├── [GRANDPARENT-3] (b. YYYY, d. YYYY)
    └── [GRANDPARENT-4] (b. YYYY, d. YYYY)
```

## Sharding & File Index

A single `Family_Tree.md` is fine for a few hundred people. As a tree grows, keep this file to the recent core (e.g. Generations 1–N, plus this index) and split older or branch lineages into `Family_Tree_<Region>_<Branch>.md` shard files — one contiguous generation range per shard, grouped by geography or lineage. Delete this section if your tree is small enough to live in one file.

The table below is both human navigation ("which file holds this branch?") and a machine-readable manifest. The **Region** column lets tooling group people by lineage: `scripts/shard_manifest.py` reads it, and `scripts/tree_locator.py` uses it to answer "which file is person X in?" by scanning the shards directly — no hand-maintained index required. A shard is matched to the longest `File` entry that is a prefix of its name, so a master row (`Family_Tree_Maternal`) automatically covers its children (`Family_Tree_Maternal_Highland`), while a more specific row overrides a broader one. Files not listed here fall back to a generic label.

| File | Region | Content |
|---|---|---|
| [[Family_Tree_Paternal_Coastal]] | Coastal | [SURNAME-1], [SURNAME-2] ([place]; Gen 6–9) |
| [[Family_Tree_Maternal_Highland]] | Highland | [SURNAME-3] ([place]; Gen 6–10) |
| [[Family_Tree_Colonial_North]] | Colonial | [SURNAME-4], [SURNAME-5] ([place]; Gen 8–14) |

## [Paternal/Maternal] Line

### [SURNAME-1] Family

**[ANCESTOR-1]** (b. [DATE], [LOCATION]; d. [DATE], [LOCATION])
- Married [SPOUSE] on [DATE] at [LOCATION]
- Children: [CHILD-1] (YYYY), [CHILD-2] (YYYY)
- Occupation: [occupation]
- Sources: [[Surname/Person_File]], Find a Grave #[memorial_number]

### [SURNAME-2] Family

**[ANCESTOR-2]** (b. [DATE], [LOCATION]; d. [DATE], [LOCATION])
- Parents: [FATHER] and [MOTHER]
- Emigrated from [COUNTRY] to [DESTINATION] in [YEAR]
- Sources: [[transcription_file]], [[person_file]]

## Data Discrepancies

| Person | Field | Source A | Source B | Resolution |
|---|---|---|---|---|
| [ANCESTOR] | birth_date | YYYY (Family tree screenshot) | MM/DD/YYYY (Birth certificate) | Birth certificate is authoritative |

## Geographic Origins

| Region | Family Lines | Time Period |
|---|---|---|
| [Country/Region] | [SURNAME-1], [SURNAME-2] | 1800s to 1900s |
