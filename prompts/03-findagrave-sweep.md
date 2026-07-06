# Find a Grave Sweep

Locate a Find a Grave memorial for every deceased person in your family tree.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[FULL NAME]`: deceased person's full name and known variants
- `[DEATH YEAR]`: known or approximate death year
- `[LOCATION]`: expected burial or death location

## Autoresearch Configuration

**Goal**: For every deceased person in the vault (`[VAULT_PATH]/Family_Tree*.md` entries with `life_status: deceased`), search Find a Grave for their memorial. Extract all available data and update the vault.

**Metric**: Number of deceased persons WITHOUT a Find a Grave memorial link

**Direction**: Minimize (lower is better)

**Verify**: `grep -c "NO_MEMORIAL_FOUND\|NEEDS_FINDAGRAVE" [VAULT_PATH]/findagrave_audit.md`

**Guard**:
- Do not assume a Find a Grave result is the correct person without verifying name, dates, AND location.
- If multiple memorials match, document all candidates and flag for human review.
- Do not create Find a Grave memorials; only search for existing ones.

**Iterations**: 15

**Protocol**:

1. **Build the deceased list**: Read the vault's `[VAULT_PATH]/Family_Tree*.md` entries (or the on-demand roster: `python3 scripts/gen_person_index.py --write /tmp/roster.md`). List every person with `life_status: deceased` (or a death date). For each, note:
   - Full name (all known variants)
   - Birth and death dates (even approximate)
   - Expected burial location (city, state, or cemetery if known)
   - Whether a Find a Grave memorial is already linked in the vault

2. **Create the audit file**: `[VAULT_PATH]/findagrave_audit.md` with columns:
   - Person name, dates, expected burial location, Find a Grave status, memorial number, new data extracted

3. **Search priority order**:
   - Most recent deaths first (more likely to have memorials)
   - Then work backward chronologically
   - Skip anyone already linked to a memorial (add to audit as KNOWN)

4. **Search strategy per person**:
   a. `"Find a Grave" "[FULL NAME]" [DEATH YEAR]`
   b. `site:findagrave.com "[FULL NAME]" [LOCATION]`
   c. Try name variations: maiden name, married name, nickname, abbreviated first name
   d. If no results, try searching by cemetery name + surname only

5. **When a memorial IS found**:
   - Verify: do name, dates, and location all match?
   - Extract: full name as listed, birth/death dates, burial location (cemetery name and city/state), spouse(s), parents, children, linked records (Ancestry, FamilySearch)
   - Compare against vault data. Note any discrepancies.
   - Update the person file with the memorial link and any new data
   - Update the appropriate Family Tree shard (per the File Index in `Family_Tree.md`) if the memorial reveals new relationships

6. **When a memorial is NOT found**:
   - Log as NO_MEMORIAL_FOUND with all search terms tried
   - Note whether the cemetery itself has coverage on Find a Grave (some cemeteries are not yet transcribed)

7. **After each batch of 3 to 4 searches**, update the audit file with current counts.

## Find a Grave Data Value

Find a Grave memorials often contain data not available elsewhere:
- Exact cemetery and plot location
- Photos of headstones (which may show dates not in other records)
- Family links (spouse, parents, children buried nearby)
- Linked Ancestry and FamilySearch records
- User-contributed biographical information (treat as secondary source)
