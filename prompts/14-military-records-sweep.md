# Military Service Records Sweep (NARA AAD)

Add primary-source US military service citations from the National Archives' Access to Archival Databases (AAD, https://aad.archives.gov/aad/) to every US-resident ancestor who was of military age during a covered conflict.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[AUDIT_FILE]`: name of the military-service audit file to create and maintain (e.g. `Military_Service_Audit.md`)
- `[SURNAME]` (optional): limit a run to one surname instead of the whole vault
- `[STATE]` (optional): the US state of residence to filter by, when known

## Tooling prerequisite (read first)

AAD blocks anonymous web fetches (HTTP 403) and its record-detail pages are not in Google's index, so this prompt **cannot be executed end-to-end with web search/fetch alone**. To run it productively, use one of:

- **A logged-in browser session** — open the relevant series (for the WWII enlistment file, start from the AAD series list) in a browser the AI tool can drive or read, run the searches, and read the result pages.
- **Manual sweep + CSV import** — the vault owner runs each query at https://aad.archives.gov/aad/, downloads the results as CSV (up to 1,000 rows per query), saves them under `[VAULT_PATH]/`, and asks the AI to parse and match.
- **FamilySearch authenticated session** — the WWII Army Enlistment Records collection mirrors the AAD enlistment data and is searchable while logged in.

A run that uses only web search/fetch will still produce a valid first iteration: a baseline eligibility list and audit file in which every row is marked `NEEDS_AAD`. That tells the human exactly which queries to run by hand.

## Autoresearch Configuration

**Goal**: For every person in `[VAULT_PATH]/Family_Tree.md` with a US residence and a birth year that places them within military age (about 17 to 50) during any AAD-covered conflict — WWII (1938-1946), Korea (1950-1957), Vietnam (1957-1975), peacetime/Gulf/War-on-Terror (1975-2006) — search the relevant AAD database, evaluate matches, and add a source citation to the person's entry when a confident match is found. Log every search, positive and negative.

**Metric**: Number of US-eligible persons with no checked AAD status (`NEEDS_AAD` or unchecked) in `[AUDIT_FILE]`

**Direction**: Minimize (lower is better)

**Verify**: `grep -c "NEEDS_AAD\|NO_MATCH" [VAULT_PATH]/[AUDIT_FILE]` after each iteration; report the delta.

**Guard**:
- Do not claim an AAD match without agreement on at least three of: surname, given name, state of residence, year of birth (±2), county of residence. A name-only match is NOT sufficient — common names return dozens of hits.
- Do not fabricate service numbers, units, or dates. Every field added to the vault must be present in the AAD record being cited.
- If multiple AAD records match equally well, list all candidates in the audit file as `AMBIGUOUS` and flag for human review. Do not pick one.
- WWI Army service records were largely destroyed in the 1973 St. Louis fire and are NOT in AAD. Do not search AAD for WWI service; note "WWI: not in AAD" in the audit when relevant.
- Civil War service (Union or Confederate) is also NOT in AAD; redirect those to Fold3 / the NPS Soldiers and Sailors Database and note it in the audit, rather than attempting it here.
- Most pre-1900-born ancestors will not match. Do not force matches.
- **Living-person privacy gate**: skip anyone marked living or possibly living in your vault — the peacetime and recent-conflict buckets include people who may still be alive. Do not web-search living or possibly-living people during an autonomous run. Only deceased people are in scope.

**Iterations**: 8

**Protocol**:

1. **Build the eligibility list**: Read `Family_Tree.md` (and any shard files). For each person, classify into one AAD eligibility bucket based on US residence and birth year:
   - **WWII (Army Enlistment)**: born 1888-1928, US-resident 1938-1946. The most populated database.
   - **WWII POW**: same age window, captured by Axis powers.
   - **Korean War**: born 1905-1935, US-resident 1950-1957.
   - **Vietnam War**: born 1917-1955, US-resident 1957-1975.
   - **DCAS Public Use (peacetime/Gulf/War-on-Terror)**: born 1925-1985, US-resident 1975-2006.
   - **AIMS Awards (1925-2004)**: any US-resident in service during this window.
   - **NOT IN AAD**: pre-1888 birth (skip, reason "pre-WWII"); never lived in the US (skip, reason "non-US"); a WWI-only window with no later eligibility (skip, reason "WWI: not in AAD").

2. **Create the audit file** `[AUDIT_FILE]` with these columns:
   - Person name (with all known spelling variants)
   - Birth year, death year
   - US residence state(s) and county(ies) at the relevant date
   - Eligibility buckets (which databases to check)
   - AAD status (`NEEDS_AAD`, `MATCH`, `NO_MATCH`, `AMBIGUOUS`, `NOT_IN_AAD`)
   - Database(s) searched
   - Match details (serial number, unit, dates) if found
   - The file where the citation was added

3. **Database priority order** (work the most-populated databases first):
   a. **WWII Army Enlistment Records** ("Electronic Army Serial Number Merged File, ca. 1938-1946", National Archives Identifier 1263923) — searchable by name, state of residence, year of birth, county, race, civilian occupation, education, and marital status. Most likely to yield a match for any US ancestor born 1888-1928.
   b. **DCAS Korean War Extract** and related Korean War casualty/POW files.
   c. **DCAS Vietnam War Extract** and related Vietnam casualty/POW/awards/unit files.
   d. **DCAS Public Use Files (1950-2006)** for peacetime/Gulf/War-on-Terror deaths.
   e. **AIMS Awards Information Management System (1925-2004)** for award recipients.
   f. **WWII POW Records (1942-1947)** if a WWII enlistment is found and POW status is suspected.

4. **Search strategy per person** (per database):
   a. Search by surname + first name on https://aad.archives.gov/aad/ (use the Fielded Search page for the relevant series; https://www.archives.gov/research/military/veterans/aad.html links each series).
   b. Filter by state of residence (WWII enlistment file) or by branch of service (DCAS files).
   c. If zero hits, try the spelling variants documented in your vault for that surname. Anticipate the drift the WWII enlistment file introduces — it uppercases everything and is ASCII-only: an English surname gaining or losing a letter (`-ley` / `-ly` / `-y`); an Italian surname with or without the space or article (`DelX` / `Del X` / `De X`); a Polish surname phonetically respelled in the county where the family settled.
   d. If still zero hits, drop the first name and search surname-only with the state filter; review plausible matches by year of birth.
   e. In the WWII enlistment file, "Year of Birth" is a 2-digit field (`24` = 1924), and "Term of Enlistment" and "Source of Army Personnel" are coded — click any field title for "Detailed Field Information" to decode them.

5. **Evaluating a hit**:
   - Score the match across: surname (exact or known variant), given name (exact, abbreviation, or middle-name swap), state of residence (exact), county of residence (exact or adjacent), year of birth (±2 years).
   - **Strong Signal**: surname + given name + state + year of birth ALL match, single record returned.
   - **Moderate Signal**: 4 of 5 fields match. Multiple records possible; pick only if the others can be eliminated by exclusionary data (different county, wildly different occupation).
   - **Speculative**: 3 of 5 match, or surname + given name only. Log as a candidate; do NOT add a citation.
   - **Ambiguous**: two or more records score equally high. Log all candidates; do NOT pick one.

6. **When a match is confirmed (Strong or Moderate Signal)**:
   - Add a source citation to the person's entry in `Family_Tree.md` (or their person file, if one exists) using this template:

     ```
     - National Archives, Access to Archival Databases (AAD), [SERIES TITLE]
       (National Archives Identifier [N]). [PERSON NAME], serial number [SERIAL],
       [STATE] [COUNTY], enlisted [DATE], [UNIT/BRANCH]. AAD record URL: [URL].
       Strong Signal / Moderate Signal.
     ```

     Example for the WWII Army enlistment series (placeholder data):

     ```
     - National Archives, Access to Archival Databases (AAD), "Electronic Army Serial
       Number Merged File, ca. 1938-1946" (National Archives Identifier 1263923).
       SMITH, JOSEPH J., serial number 31234567, Massachusetts, Berkshire County,
       enlisted 14 OCT 1942, Branch: Infantry. AAD record URL:
       https://aad.archives.gov/aad/record-detail.jsp?... Strong Signal.
     ```

   - Extract the other available fields (WWII enlistment): serial number, year of birth, place of birth, race, citizenship, civilian occupation, education, marital status, term of enlistment, branch, and (in some records) height/weight. Add them to the person's entry as a "Military Service" note.
   - If the record reveals a new relationship (a next-of-kin field naming a parent or spouse), cross-check it against existing vault data and flag any discrepancy in `Open_Questions.md`.

7. **When NO match is found after exhausting variants**:
   - Mark the audit row `NO_MATCH`, listing every database searched and every variant tried.
   - This is a valid negative result; it tells future sessions not to repeat the same searches without a new strategy.

8. **Log the session**: append a one-line entry to `Research_Log.md` recording the baseline `NEEDS_AAD` count, persons checked, databases searched, matches and ambiguous candidates, and any brick walls worth a paid follow-up (Fold3, or a NARA Standard Form 180 request to the NPRC in St. Louis).

9. **Update the count**: after each iteration, recount the `NEEDS_AAD` rows and report the delta.

## Tips

- **The WWII Army Enlistment file is by far the largest** (about 9 million records) and the most likely to yield a match. Run it first for every WWII-eligible person before touching any other database.
- **Year of Birth is a 2-digit field** in the WWII enlistment file (a 1922 birth is `22`). Be careful with births of 1900-1909 (`00`-`09`), which a poorly designed search interface can conflate with 2000-2009.
- **State of residence is the single most-discriminating field** in the WWII enlistment file — filtering by state can cut the surname pool by 50x versus a national search. Always filter by state when known.
- **Common surnames need extra scrutiny** — "John Smith", "William Jones", "Joseph Brown" return dozens of hits even with a state filter. Use county and year of birth aggressively to narrow.
- **Italian and Polish surnames may be heavily anglicized in 1940s records** — the WWII enlistment file uppercases everything and uses ASCII only (no diacritics); an Italian surname may appear with the article split off, a Polish surname phonetically respelled.
- **AAD does not include service medical or pension records.** For those, flag a follow-up via NARA Standard Form 180 to the NPRC in St. Louis (https://www.archives.gov/veterans/military-service-records).
- **Civil War, Spanish-American War, and WWI service are NOT in AAD.** For the Civil War, redirect to the NPS Soldiers and Sailors Database (https://www.nps.gov/civilwar/soldiers-and-sailors-database.htm) and Fold3. For WWI, redirect to state archives — most US WWI Army records were destroyed in the 1973 NPRC fire, but the 1917-1918 draft registration cards survive on FamilySearch and Ancestry.
- **AAD download limit**: 1,000 records per query. If a surname-only search returns more than 1,000 hits, narrow by state before downloading.
