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

## Autoresearch Configuration

**Goal**: For each deceased, source-suitable ancestor currently in `[VAULT_PATH]/Family_Tree.md`, search for source-backed parent, sibling, spouse-family, or earlier-generation leads. Update the vault only when the evidence tier is clear. Keep speculative leads separate from confirmed relationships.

**Metric**: Number of source-backed candidate relationships reviewed and classified as `strong_signal`, `moderate_signal`, `speculative`, or rejected

**Direction**: Maximize reviewed, source-backed classifications. Do not maximize raw person count.

**Verify**: In `[VAULT_PATH]/Research_Log.md`, count this iteration's reviewed candidate relationships by tier: strong, moderate, speculative, rejected, and not searched because privacy blocked it.

**Guard**:
- Do not fabricate ancestors. Every addition must cite a source.
- Do not trust user-contributed trees (Geni, Ancestry hints) without corroboration from at least one independent source.
- Do not add a confirmed parent-child relationship from a user-contributed tree alone. Treat it as a lead.
- Do not modify existing dates or names during expansion; that is the cross-reference audit's job.
- Mark any unverified additions with `(speculative)` or `evidence_tier: speculative`.
- Prefer adding a lead to `Open_Questions.md` over adding a weak ancestor to `Family_Tree.md`.
- Do not run web searches on living people. Treat the starting person, their siblings, parents, and any person without a death date as living unless the vault clearly states otherwise.
- Do not publish exact birth dates, addresses, or contact details for living or possibly living people. Use birth year only, or mark as `Living`.

**Iterations**: 8

**Protocol**:

1. **Baseline**: Read `[VAULT_PATH]/Family_Tree.md` completely. Record the starting source posture in `[VAULT_PATH]/Research_Log.md`: known deceased targets, living or privacy-blocked people skipped, already sourced relationships, and known speculative relationships.

2. **Identify expansion targets**: For each leaf node (an ancestor with no listed parents), note:
   - Name, dates, and location
   - Which web sources might have their parents (Find a Grave, Geni, WikiTree, FamilySearch wiki, published county histories)

3. **Search strategy per ancestor**: For each target, run web searches in this order:
   a. `"Find a Grave" "[ANCESTOR NAME]" [DEATH YEAR] [BURIAL LOCATION]`
   b. `"[ANCESTOR NAME]" parents born [BIRTH YEAR RANGE] [LOCATION]`
   c. `site:geni.com "[ANCESTOR NAME]" [BIRTH YEAR]`
   d. `site:wikitree.com "[ANCESTOR NAME]"`
   e. `"[ANCESTOR NAME]" genealogy [LOCATION] [SURNAME]`

4. **Evaluate results**: For each search hit:
   - Does the person match on name, dates, AND location? All three must align.
   - Is the source a primary record (vital record, church register) or secondary (user tree, published genealogy)?
   - If secondary, does at least one other independent source corroborate?
   - Could another same-name person explain the record?
   - What evidence tier does the candidate relationship deserve?

5. **Update the vault**: For each reviewed candidate:
   - Add `strong_signal` or `moderate_signal` relationships to Family_Tree.md in the correct position with citations
   - Add weak or single-source relationships to `Open_Questions.md`, not as confirmed tree facts
   - If sufficient data exists, create a person file using the template at `[VAULT_PATH]/templates/person.md`
   - Note the source in the person file's Document Sources section

6. **Log the search**: In `[VAULT_PATH]/Research_Log.md`, record:
   - Date and search target
   - Queries used
   - Results (positive or negative)
   - Candidate relationships reviewed, accepted, rejected, or held as speculative
   - What remains unresolved

7. **Update the classification table**: After each iteration, report counts for strong, moderate, speculative, rejected, and privacy-blocked candidates. If the tree grew but source quality did not, treat the iteration as a failure.

8. **Repeat**: Move to the next set of expansion targets. Prioritize:
   - Lines with the fewest known generations (shallowest branches)
   - Ancestors with specific dates and locations (higher probability of finding records)
   - Lines with no person files yet (lowest current documentation)

## Tips

- **Patronymic names**: In Scandinavian genealogy, "Hansen" means "son of Hans." The same person may appear under different names in different records (farm name, patronymic, Americanized name). Search all variants.
- **Name changes at immigration**: Many immigrants changed or simplified their names. Search both the original and Americanized versions.
- **Negative results matter**: If you search for an ancestor and find nothing, log it. This prevents duplicate searches later.
- **Sibling research**: Sometimes the easiest way to find an ancestor's parents is to find their siblings first. Siblings often appear in more records.
