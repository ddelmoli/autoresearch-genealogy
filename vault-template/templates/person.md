---
type: person
name: "[Full Name]"
born: YYYY-MM-DD
died: YYYY-MM-DD
life_status: living | deceased | unknown
family: "[Surname]"
evidence_tier: strong_signal | moderate_signal | speculative
profile_status: complete | partial | stub
id: P-XXXXXX              # vault-owned stable key: "P-" + 6 Crockford base32 (no I/L/O/U)
generation: N             # integer, counted from the anchor/subject
parents: []               # list of parent ids, e.g. [P-AAAAAA, P-BBBBBB]
spouse: []                # list of spouse ids
flags: []                 # e.g. [Q12, dup]
sources:
  - "[Source 1]"
  - "[Source 2]"
created: YYYY-MM-DD
tags: [genealogy, surname, person]
---

# [Full Name]

## Vital Information

| Field | Value | Source |
|---|---|---|
| Full Name | [name] | [source] |
| Born | [date] | [source] |
| Birthplace | [place] | [source] |
| Died | [date] | [source] |
| Burial | [cemetery, city, state] | [source] |
| Father | [[Father_Name]] | [source] |
| Mother | [[Mother_Name]] | [source] |
| Spouse | [[Spouse_Name]] (m. [date], [place]) | [source] |
| Children | [[Child_1]], [[Child_2]] | [source] |

## Biography

[Narrative biography drawn from sources. Cite inline.]

## Document Sources

| Document | Type | Vault Note |
|---|---|---|
| [Document description] | [certificate / newspaper / transcription] | [[link_to_note]] |

## Data Discrepancies

| Field | Source A | Source B | Resolution |
|---|---|---|---|
| [field] | [value] ([source]) | [value] ([source]) | [which is correct and why] |
