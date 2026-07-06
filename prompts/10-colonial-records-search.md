# Colonial Records Search

Search for colonial American ancestors in pre-1800 records.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[ANCESTOR]`: target colonial ancestor's full name
- `[COUNTY]`: colonial county or equivalent jurisdiction
- `[COLONY]`: colony or state name for pre-1800 research
- `[YEAR RANGE]`: relevant date range
- `[WAR/ERA]`: military conflict or colonial period
- `[HUSBAND]`: husband name when a woman appears only through spouse records

## Autoresearch Configuration

**Goal**: For every ancestor in the colonial-era Family Tree shards (the `Colonial`-region files in the `Family_Tree.md` File Index) who lived in colonial America (pre-1800), search for records that would extend the line further back or fill biographical details, prioritizing obtaining details on existing ancestors before extending the line.

**Metric**: Number of colonial-era ancestors with at least two primary source citations other than GEDCOM

**Direction**: Maximize

**Verify**: Count persons across all colonial Family Tree files with dates before 1800 who have entries in their Document Sources section.

**Guard**:
- Colonial records are fragmentary. Many have been lost to fire, war, or neglect.
- Do not confuse similarly named individuals. Colonial naming conventions often reused names across generations within a family.
- Be cautious with compiled genealogies and lineage society applications; they sometimes contain errors that have been perpetuated for decades.

**Iterations**: 5

**Protocol**:

1. **Identify colonial ancestors**: Read all colonial-era Family Tree shards (the `Colonial`-region files per the File Index in `Family_Tree.md`) and list every person with dates before 1800. For each, note:
   - Name, dates, location (colony/county)
   - What records already exist in the vault
   - What records might exist (see Record Types below)
   - **Before searching**: grep `vault/logs/` and `vault/Open_Questions.md` for the ancestor's name to check what has already been tried. Do not repeat searches that returned negative results in prior sessions unless you have a new source, spelling variant, or search strategy not previously attempted.

2. **Search by record type** (see [archives/usa-colonial.md](../archives/usa-colonial.md) for what each record type contains and where it survives best):

   **Land records**: Colonial land patents, grants, and surveys are among the best-preserved colonial records.
   - Search: `[ANCESTOR] land [COUNTY] [COLONY] colonial`
   - Check county deed books (many digitized by FamilySearch)

   **Probate records**: Wills, inventories, and administrations name family members.
   - Search: `[ANCESTOR] will probate [COUNTY] [YEAR RANGE]`
   - Often the best source for identifying a wife, children, and extended family

   **Military records**: Militia rolls, muster lists, oaths of allegiance.
   - Search: `[ANCESTOR] militia [COUNTY] [WAR/ERA]`
   - Revolutionary War records: check the DAR Patriot Index

   **Church records**: Baptism, marriage, and burial registers.
   - Search by parish and denomination
   - Many colonial churches have published their registers

   **Tax records**: Tithable lists, tax assessments.
   - Show who lived in a county and approximately when

   **Court records**: Civil suits, criminal proceedings, guardianships.
   - Often reveal family relationships not found elsewhere


3. **Source evaluation**: Colonial records require extra care — see [archives/usa-colonial.md](../archives/usa-colonial.md) § "Colonial Research Challenges" (inconsistent spelling; Old/New Style calendar dating; "Junior/Senior" = relative age, not father/son; women recorded only as "wife of [HUSBAND]").

4. **Update vault**: For each record found, create a transcription note, update the person's narrative entry (each person carries a `- meta:` block — `scripts/mint_ids.py --apply` mints ids for new ones), and log the search. Review and update the relevant colonial Family_Tree files, `vault/Open_Questions.md`, and `vault/Hereditary_Society_Lineages.md`. When complete, create a session log at `vault/logs/YYYY-MM-DD-colonial-records.md` (use today's date). Then add a one-line summary entry to the session index in `vault/Research_Log.md`.

## Colonial Record Sources

See [archives/usa-colonial.md](../archives/usa-colonial.md) for the full source list (FamilySearch, Fold3, Archive.org/Google Books + Open Library, DAR, USGenWeb, state archives), the record-types-by-survival-rate table, and lineage-society aids (GSMD Silver Books, DAR GRS, WikiTree Mayflower project).

## Tips

- **Name changes at immigration**: Many immigrants changed or simplified their names. Search both the original and Americanized versions.
- **Negative results matter**: If you search for an ancestor and find nothing, log it. This prevents duplicate searches later.
- **Sibling research**: Sometimes the easiest way to find an ancestor's parents is to find their siblings first. Siblings often appear in more records.
- **FamilySearch** : Use the signed-in FamilySearch capability via Claude in Chrome and your FamilySearch group tree available at [SUBJECT_PID]
- **Internet Archive** : Internet Archive and "The Open Library" has digitized books which may be useful for Colonial Records. This source is available via https://archive.org/ and has a signed-in account which can be used via Claude in Chrome.
- **Mayflower Resources**: To assist in answering the question about Mayflower ancestors, leverage https://www.wikitree.com/wiki/Space:The_Mayflower