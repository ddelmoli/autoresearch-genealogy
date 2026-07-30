# NARA AAD Military Service Sweep

Add primary-source military service citations from NARA's Access to Archival Databases (AAD, https://aad.archives.gov/aad/) to every US-resident person in the vault who was of military age during a covered conflict.

## Tooling prerequisite (read first)

AAD blocks anonymous WebFetch (HTTP 403) and AAD record-detail pages are not crawled by Google's index, so this prompt **cannot be executed end-to-end via WebSearch/WebFetch alone**. Verified 9 MAY 2026; see `vault/logs/2026-05-09-aad-military-sweep.md`. To run this prompt productively, use one of:

- **Claude in Chrome** — open https://aad.archives.gov/aad/series-list.jsp?cat=GP24 in a logged-in browser, run searches manually, and paste results / let Claude read the page via the Chrome MCP tools.
- **Manual sweep + CSV import** — the vault owner runs each query at https://aad.archives.gov/aad/ (the Fielded Search interface for series 3360 is the WWII enlistment file), downloads results as CSV (up to 1,000 rows per query), saves to `vault/aad_imports/[surname]_[state].csv`, and asks Claude to parse and match.
- **FamilySearch authenticated session** — the WWII Army Enlistment Records collection 2028680 mirrors the AAD data and is searchable while logged in.

A run that uses ONLY WebSearch and WebFetch will produce a baseline eligibility list and audit file, but every row will end up `NEEDS_AAD`. That is still a valid first iteration — it tells the human exactly which queries to run.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[AUDIT_FILE]`: the per-person service-status file this prompt maintains (default `aad_military_audit.md`)
- `[SCOPE]` (optional): a subset of shard files, a lineage, or a single conflict window (WWII / Korea / Vietnam / DCAS / AIMS) to focus on; leave unset to sweep the whole vault

Note: the bracketed tokens inside the Protocol's citation template — `[SERIAL]`,
`[STATE]`, `[COUNTY]`, `[DATE]`, `[UNIT/BRANCH]`, `[URL]` — are OUTPUT fields to be
filled from the AAD record being cited, not inputs to replace before a run.

## Autoresearch Configuration

**Goal**: For every person in the vault (`vault/Family_Tree*.md` narrative entries) with a US residence and a birth year that places them within military age (~17-50) during any AAD-covered conflict (WWII 1938-1946, Korean War 1950-1957, Vietnam War 1957-1975, peacetime 1975-2006, Gulf War, War on Terror), search the relevant AAD database, evaluate matches, and add a Document Source citation to the person's file when a confident match is found. Log every search (positive and negative).

**Metric**: Number of US-eligible persons without a checked AAD status (`NEEDS_AAD` or unchecked) in `vault/[AUDIT_FILE]`

**Direction**: Minimize

**Verify**: `grep -c "NEEDS_AAD\|NO_MATCH" vault/[AUDIT_FILE]` after each iteration; report the delta.

**Guard**:
- Do not claim an AAD match without agreement on at least three of: surname, given name, state of residence, year of birth (±2), county of residence. A name-only match is NOT sufficient — many common names (e.g. "John Smith", "Joseph Brown") return dozens of hits.
- Do not fabricate service numbers, units, or dates. Every field added to the vault must be present in the AAD record being cited.
- If multiple AAD records match equally well, list all candidates in the audit file as `AMBIGUOUS` and flag for human review. Do not pick one.
- The WWI Army service records were largely destroyed in the 1973 St. Louis fire and are NOT in AAD. Do not search AAD for WWI service. Note "WWI: not in AAD" in the audit when relevant.
- Confederate / Union Civil War service is also NOT in AAD; redirect those searches to Fold3 / NPS Soldiers and Sailors Database (note this in the audit; do not attempt in this prompt).
- Most pre-1900-born ancestors will not match. Do not force matches.
- **Living-person privacy gate**: skip any person whose meta block is `life_status: living` or `life_status: unknown` (the post-2006/peacetime and recent-conflict buckets will include people who are still living). Do not web-search living or possibly-living people during an autonomous run. Only `life_status: deceased` people are in scope.

**Iterations**: 8

**Protocol**:

1. **Build the eligibility list**: Read every `vault/Family_Tree*.md` file (each person is a bold-name entry with a `- meta:` block; for a flat roster run `python3 scripts/gen_person_index.py --write /tmp/roster.md` and read that). For each person, classify into one of these AAD eligibility buckets based on US residence and birth year:
   - **WWII (Army Enlistment)**: born 1888-1928, US-resident 1938-1946. Most populated database.
   - **WWII POW**: same age window, captured by Axis powers.
   - **Korean War**: born 1905-1935, US-resident 1950-1957.
   - **Vietnam War**: born 1917-1955, US-resident 1957-1975.
   - **DCAS Public Use (peacetime/Gulf/WOT)**: born 1925-1985, US-resident 1975-2006.
   - **AIMS Awards (1925-2004)**: any US-resident in service during this window.
   - **NOT IN AAD**: pre-1888 birth (skip with reason "pre-WWII"); never lived in US (skip with reason "non-US"); WWI-only window with no later eligibility (skip with reason "WWI: not in AAD").

2. **Create the audit file**: `vault/[AUDIT_FILE]` with these columns:
   - Person name (with all known spelling variants)
   - Birth year, death year
   - US residence state(s) and county(ies) at the relevant date
   - Eligibility buckets (which databases to check)
   - AAD status (`NEEDS_AAD`, `MATCH`, `NO_MATCH`, `AMBIGUOUS`, `NOT_IN_AAD`)
   - Database(s) searched
   - Match details (serial number, unit, dates) if found
   - File where citation was added

3. **Database priority order** (work the most-populated databases first):
   a. **WWII Army Enlistment Records** ("Electronic Army Serial Number Merged File, ca. 1938-1946", National Archives Identifier 1263923, Record Group 64) — searchable by name, state of residence, year of birth, county, race, civilian occupation, education, marital status. Most likely to yield matches for any US ancestor born 1888-1928.
   b. **DCAS Korean War Extract** and related Korean War casualty/POW files
   c. **DCAS Vietnam War Extract** and related Vietnam casualty/POW/awards/unit files
   d. **DCAS Public Use Files (1950-2006)** for peacetime/Gulf/War-on-Terror deaths
   e. **AIMS Awards Information Management System (1925-2004)** for award recipients
   f. **WWII POW Records (1942-1947)** if WWII enlistment found and POW status suspected

4. **Search strategy per person** (per database):
   a. Free-text search by surname + first name on https://aad.archives.gov/aad/ (use the Fielded Search page for the relevant series — start from https://www.archives.gov/research/military/veterans/aad.html which links each series).
   b. Filter by state of residence (WWII enlistment file) or by branch of service (DCAS files).
   c. If zero hits, try the spelling variants documented in the vault for that surname. Anticipate the drift the WWII enlistment file introduces (it uppercases everything and is ASCII-only): an English surname gaining/losing a letter (`-ley` / `-ly` / `-y`); an Italian surname with or without the space/article (`DelX` / `Del X` / `De X`); a Polish surname phonetically respelled in the county where the family settled.
   d. If still zero hits, drop the first name and search surname-only with state filter; review for plausible matches by year of birth.
   e. If using the WWII enlistment file, the "Year of Birth" field is a 2-digit year (`24` = 1924). The "Term of Enlistment" and "Source of Army Personnel" fields are coded; click any field title to access "Detailed Field Information" for code meanings.

5. **Evaluating a hit**:
   - Compute a match score across: surname (exact or known variant), given name (exact, abbreviation, or middle-name swap), state of residence (exact), county of residence (exact or adjacent), year of birth (±2 years).
   - **Strong Signal**: surname + given name + state + year of birth ALL match. Single record returned.
   - **Moderate Signal**: 4 of 5 fields match. Multiple records possible; pick only if other candidates can be eliminated by exclusionary data (different county, wildly different occupation).
   - **Speculative**: 3 of 5 match, or surname + given name only. Log as candidate; do NOT add citation.
   - **Ambiguous**: two or more records score equally high. Log all candidates in the audit; do NOT pick one.

6. **When a match is confirmed (Strong or Moderate Signal)**:
   - Add a Document Source entry to the person's file in `vault/[Person_File].md` (or to the relevant Family_Tree file's entry if no person file exists yet) using this citation template:

     ```
     - National Archives, Access to Archival Databases (AAD), [SERIES TITLE]
       (National Archives Identifier [N], Record Group [N]). [PERSON NAME], serial number
       [SERIAL], [STATE] [COUNTY], enlisted [DATE], [UNIT/BRANCH]. AAD record URL: [URL].
       Strong Signal / Moderate Signal.
     ```

     Concrete example for the WWII Army enlistment series:

     ```
     - National Archives, Access to Archival Databases (AAD), "Electronic Army Serial
       Number Merged File, ca. 1938-1946" (National Archives Identifier 1263923,
       Record Group 64). SMITH, JOSEPH J., serial number 31234567, Massachusetts,
       Anytown County, enlisted 14 OCT 1942, Branch: Infantry. AAD record URL:
       https://aad.archives.gov/aad/record-detail.jsp?... Strong Signal.
     ```

   - Also extract the following fields if present (WWII enlistment): serial number, year of birth, place of birth, race, citizenship, civilian occupation, education, marital status, term of enlistment, branch immaterial / branch alternative, height/weight (some records). Add to the person file's body as a "Military Service" section.
   - If the record reveals new relationships (e.g. next-of-kin field naming a parent or spouse), cross-check against existing vault data and flag any discrepancies in `vault/Open_Questions.md`.

7. **When NO match is found after exhausting variants**:
   - Audit row marked `NO_MATCH`, listing every database searched and every variant tried.
   - This is a valid negative result; it tells future sessions not to repeat these searches without a new strategy.

8. **Log the session**: Create `vault/logs/YYYY-MM-DD-aad-military-sweep.md` with:
   - Baseline count of `NEEDS_AAD` rows
   - Per-iteration: persons checked, databases searched, matches found, ambiguous candidates flagged
   - New citations added (with person + database + serial number)
   - Brick walls / persons with plausible service but no AAD match (suggest follow-up: paid Fold3 search, NARA OMPF letter request to NPRC St. Louis)
   - Append a one-line entry to the table in `vault/Research_Log.md`

9. **Update the count**: After each iteration, recount `NEEDS_AAD` rows. Report the delta.

## Tips

- **The WWII Army Enlistment file is by far the largest** (~9 million records) and the most likely to yield matches. Run it first for every WWII-eligible person before touching any other database.
- **Year of Birth is a 2-digit field** in the WWII enlistment file. A 1922 birth is encoded as `22`. Be careful with persons born 1900-1909 (encoded `00`-`09`) — they sometimes get conflated with persons born 2000-2009 in poorly designed search interfaces.
- **State of residence is the single most-discriminating field** in the WWII enlistment file. If the person was in Massachusetts, the surname pool drops by 50x compared to a national search. Always filter by state when known.
- **Common surnames need extra scrutiny**: "John Smith", "William Jones", "Joseph Brown" will return dozens of hits even with state filtering. Use county and year of birth aggressively to narrow.
- **Italian and Polish surnames may be heavily anglicized in 1940s records**: an Italian surname might appear ASCII-uppercased with the article split off; a Polish surname might be phonetically respelled. The WWII enlistment file uppercases everything and uses ASCII only (no diacritics).
- **AAD does not include service medical or pension records**. For those, the audit should flag follow-up via NARA Standard Form 180 to NPRC St. Louis (https://www.archives.gov/veterans/military-service-records).
- **Civil War, Spanish-American War, and WWI service are NOT in AAD.** For Civil War, redirect to NPS Soldiers and Sailors Database (https://www.nps.gov/civilwar/soldiers-and-sailors-database.htm) and Fold3. For WWI, redirect to state archives (most US WWI Army records were destroyed in the 1973 NPRC fire; state-level draft registration cards 1917-1918 survive on FamilySearch and Ancestry).
- **AAD download limit**: 1,000 records per query. If a surname-only search returns more than 1,000 hits, narrow by state before downloading.
