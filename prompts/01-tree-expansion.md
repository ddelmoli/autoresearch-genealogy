# Source-Backed Tree Expansion

Find source-backed candidate relationships for deceased ancestors without treating tree growth as proof.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[ANCESTOR NAME]`: a target ancestor's full name
- `[DEATH YEAR]`: known or approximate death year
- `[BURIAL LOCATION]`: expected cemetery, city, county, or state
- `[BIRTH YEAR RANGE]`: known or approximate birth range
- `[LOCATION]`: relevant town, county, state, province, or country
- `[BIRTH YEAR]`: known or approximate birth year
- `[SURNAME]`: family surname or historical surname variant
- `[FS_GROUP_TREE]`: URL of your FamilySearch group/family tree, if you use one (configure in your local project instructions)
- `[SUBJECT_PID]`: the starting person's FamilySearch PID (configure in your local project instructions)
- `[SCOPE]` (optional): a subset of shard files / a Region to focus on; leave unset to expand the whole tree

## Autoresearch Configuration

**Goal**: For each deceased, source-suitable ancestor currently in the Family Tree files (`[VAULT_PATH]/Family_Tree.md` and the shard files listed in its File Index), search for source-backed parent, sibling, spouse-family, or earlier-generation leads. Update the vault only when the evidence tier is clear, and keep speculative leads separate from confirmed relationships. Keep iterating until no more ancestors can be found through free web sources or your FamilySearch group tree `[FS_GROUP_TREE]` (read-only via a logged-in browser session).

**Metric**: Number of new ancestors/individuals added across all Family Tree files, and the number of source-backed candidate relationships reviewed and classified as `strong_signal`, `moderate_signal`, `speculative`, or rejected

**Direction**: Maximize reviewed, source-backed classifications. Do not maximize raw person count.

**Verify**: Count the number of named individuals across all Family Tree files before and after each iteration and log the delta. In `[VAULT_PATH]/Research_Log.md`, also count this iteration's reviewed candidate relationships by tier: strong, moderate, speculative, rejected, and not searched because privacy blocked it.

**Guard**:
- **Scope (optional)**: to focus on a subset rather than the whole tree, set `[SCOPE]` to the shard files / Region you're targeting and limit every step to those; log incidental out-of-scope finds to `Open_Questions.md` for a future run.
- Do not fabricate ancestors. Every addition must cite a source.
- Do not trust user-contributed trees (Geni, Ancestry hints) without corroboration from at least one independent source.
- Do not add a confirmed parent-child relationship from a user-contributed tree alone. Treat it as a lead.
- Do not modify existing dates or names during expansion; that is the cross-reference audit's job (`02-cross-reference-audit`).
- Mark any unverified additions with `(speculative)` or `evidence_tier: speculative` in the tree.
- Prefer adding a lead to `Open_Questions.md` over adding a weak ancestor to a Family Tree file.
- Do not run web searches on living people. Treat the starting person, their siblings, parents, and any person without a death date as living unless the vault clearly states otherwise.
- Do not publish exact birth dates, addresses, or contact details for living or possibly living people. Use birth year only, or mark as `Living`.
- **Scope boundary — discovery only, no FS contribution.** Use the FamilySearch group tree **read-only** as a discovery source. Do NOT perform FamilySearch mutations (Add Person / Attach Source / Add Relationship) here — this prompt is read-only discovery. Pushing vault-confirmed persons UP into FamilySearch and recording their PIDs is a separate, operator-gated step; the persons this prompt adds to your tree (not yet linked to FamilySearch) become that step's candidate list.

**Iterations**: 15

**Protocol**:

1. **Baseline**: Read all Family Tree files completely. Count every named individual across all files, and record the starting source posture in your research log: the baseline count, known deceased targets, living or privacy-blocked people skipped, already sourced relationships, and known speculative relationships.

2. **Identify expansion targets**: For each leaf node (an ancestor with no listed parents), note:
   - Name, dates, and location
   - Which web sources might have their parents (Find a Grave, Geni, WikiTree, FamilySearch wiki, published county histories)
   - **Before searching**: check your research logs and `Open_Questions.md` for the ancestor's name to see what has already been tried. Do not repeat searches that returned negative results in prior sessions unless you have a new source, spelling variant, or search strategy not previously attempted.

3. **Search strategy per ancestor**: For each target, run web searches in this order:
   a. `"Find a Grave" "[ANCESTOR NAME]" [DEATH YEAR] [BURIAL LOCATION]`
   b. `"[ANCESTOR NAME]" parents born [BIRTH YEAR RANGE] [LOCATION]`
   c. `site:geni.com "[ANCESTOR NAME]" [BIRTH YEAR]`
   d. `site:wikitree.com "[ANCESTOR NAME]"`
   e. `"[ANCESTOR NAME]" genealogy [LOCATION] [SURNAME]`

4. **Additional search strategies**: For any line that originates outside your home country, consult the relevant archive guide in `archives/` for country-specific databases, access methods, and AI accessibility notes before searching that line.

   **Country-specific archive guides** (read the relevant guide before searching that country's records):
   a. **Italian ancestors**: Read `archives/italy.md` for a full list of Italian genealogical databases. Key resources: Antenati portal (https://antenati.cultura.gov.it/?lang=en) for civil registration; FamilySearch Italian collections (partially indexed, partially browse-only); diocesan archives for pre-1809 parish records. Note: Antenati coverage varies by province (some provinces have limited digitization).
   b. **Polish ancestors**: Read `archives/poland.md`. Key resources: Geneteka (https://geneteka.genealodzy.pl) for indexed vital record transcriptions; Szukaj w Archiwach (https://szukajwarchiwach.gov.pl) for digitized images; FamilySearch Polish collections. Note: many smaller rural parish records (especially outside the larger provincial towns) are not digitized online.
   c. **English/Welsh ancestors**: Read `archives/england-wales.md`. Key resources: FreeBMD (https://www.freebmd.org.uk) for civil registration indexes from 1837; FreeREG for parish register transcriptions; GENUKI (https://www.genuki.org.uk/big) for county-level guides; GRO certificates (~11 GBP each).
   d. **Scottish ancestors**: Read `archives/scotland.md`. Key resources: ScotlandsPeople (https://www.scotlandspeople.gov.uk) for OPR, civil registration, and census; NRS (National Records of Scotland).
   e. **Irish ancestors**: Read `archives/ireland.md`. Key resources: IrishGenealogy.ie for civil registration; NLI Catholic Parish Registers; Griffith's Valuation.
   f. **Colonial American ancestors**: Read `archives/usa-colonial.md` for pre-1800 records; `archives/usa-vital-records.md` for state vital records; `archives/usa-immigration.md` for immigration/naturalization. Key resources: FamilySearch, Internet Archive (digitized genealogies), DAR GRS.
   g. **USA Census records**: Read `archives/usa-census.md` for census research strategies across all decades.

   **Cross-cutting resources** (useful for all lines):
   h. FamilySearch signed-in access: use your group tree `[FS_GROUP_TREE]` via a logged-in browser session (read-only)
   i. Internet Archive / Open Library (https://archive.org, https://openlibrary.org): digitized genealogies, county histories, and GSMD Silver Books available for borrowing. Ask to log in to borrow books.
   j. Cyndi's List (https://www.cyndislist.com/categories/): comprehensive categorized genealogy link directory
   k. WikiTree (https://www.wikitree.com): collaborative genealogy with sourcing requirements; search by surname or use Space pages for Mayflower, DAR, etc.
   l. Find a Grave (https://www.findagrave.com): cemetery records with photographs; particularly useful for confirming death dates and family groupings

5. **Evaluate results**: For each search hit:
   - Does the person match on name, dates, AND location? All three must align.
   - Is the source a primary record (vital record, church register) or secondary (user tree, published genealogy)?
   - If secondary, does at least one other independent source corroborate?
   - Could another same-name person explain the record?
   - What evidence tier does the candidate relationship deserve?

6. **Update the vault**: For each reviewed candidate:
   - Add `strong_signal` or `moderate_signal` relationships to the appropriate Family Tree shard in the correct position, with citations — route each person to the shard whose Region/scope matches their line (see the File Index in `Family_Tree.md`).
   - Add weak or single-source relationships to `Open_Questions.md`, not as confirmed tree facts.
   - Record each new person in your tree following your project's conventions (a unique id, evidence tier, and generation), with a source citation for every fact.
   - Cite each new fact where you record it (source-first); include any FamilySearch record ARKs that support the person.

7. **Log the search**: Record the session in your research log:
   - Date and search target
   - Queries used
   - Results (positive or negative)
   - Candidate relationships reviewed, accepted, rejected, or held as speculative
   - What remains unresolved
   Then add a one-line summary entry to your research log's session index.

8. **Update the count and classification**: After each iteration, recount named individuals across all Family Tree files and report the delta. Also report counts for strong, moderate, speculative, rejected, and privacy-blocked candidates. If the tree grew but source quality did not, treat the iteration as a failure.

9. **Repeat**: Move to the next set of expansion targets. Prioritize:
   - Lines with the fewest known generations (shallowest branches)
   - Ancestors with specific dates and locations (higher probability of finding records)
   - Lines with no person files yet (lowest current documentation)

## Tips

- **Patronymic names**: In Scandinavian genealogy, "Hansen" means "son of Hans." The same person may appear under different names in different records (farm name, patronymic, Americanized name). Search all variants.
- **Name changes at immigration**: Many immigrants changed or simplified their names. Search both the original and Americanized versions.
- **Negative results matter**: If you search for an ancestor and find nothing, log it. This prevents duplicate searches later.
- **Sibling research**: Sometimes the easiest way to find an ancestor's parents is to find their siblings first. Siblings often appear in more records.
- **FamilySearch** : Use the signed-in FamilySearch capability and your group tree `[FS_GROUP_TREE]` (starting person `[SUBJECT_PID]`) **as a read-only discovery source** (browse it for ancestors/relationships to add to your tree). Contributing back to FS and recording PIDs is a separate, operator-gated step.