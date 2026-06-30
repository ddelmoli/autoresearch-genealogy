# GEDCOM Completeness

Ensure your GEDCOM matches your vault while protecting living and possibly living people.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[GEDCOM_PATH]`: path to the GEDCOM file to audit or create
- `[ANCESTOR]`: example ancestor name used in the sample audit row
- `[ANCESTOR-2]`: second example ancestor name used in the sample audit row
- `[N]`: next available GEDCOM record number
- `[Given]`: given names for a GEDCOM `NAME` value
- `[Surname]`: surname for a GEDCOM `NAME` value
- `[DD MMM YYYY]`: GEDCOM-formatted date, for example `10 MAY 1866`
- `[Place]`: GEDCOM place string, ordered smallest to largest jurisdiction

## Autoresearch Configuration

**Goal**: Every publishable deceased person in `[VAULT_PATH]/Family_Tree.md` should exist in `[GEDCOM_PATH]` with correct names, dates, places, and relationships. Living or possibly living people must be omitted, privatized, or reduced to non-identifying placeholders before sharing.

**Metric**: Number of persons in Family_Tree.md who are missing from or incomplete in the GEDCOM

**Direction**: Minimize (lower is better)

**Verify**: `grep -c "MISSING\|INCOMPLETE" [VAULT_PATH]/gedcom_audit.md`

**Guard**:
- Use GEDCOM 5.5.1 format (the most widely supported version)
- Do not include living or possibly living people's names, exact dates, places, notes, media paths, source details, or relationship structure in any GEDCOM intended for sharing.
- For a private local GEDCOM, preserve living details only if the file stays local and the user explicitly asks for a private export.
- For a shared GEDCOM, use privacy placeholders such as `Living Person` and remove links that identify parents, spouses, children, residences, schools, workplaces, DNA matches, or private notes.
- Preserve existing GEDCOM data; do not overwrite entries that already exist unless they are demonstrably wrong

**Iterations**: 10

**Protocol**:

1. **Build the master list**: Read `[VAULT_PATH]/Family_Tree.md`. Split people into publishable deceased, living, and possibly living before extracting details. For publishable deceased people, extract:
   - Full name
   - Birth date and place
   - Death date and place
   - Marriage(s) with date, place, and spouse
   - Parents
   - Children
   For living or possibly living people, extract only the minimum needed to audit privacy status.

2. **Read the GEDCOM** (or create one if it does not exist): Parse `[GEDCOM_PATH]` and build a parallel list of all INDI (individual) and FAM (family) records.

3. **Compare**: For each person in the master list:
   - Does an INDI record exist? If not, mark as MISSING.
   - Are all known facts present? If not, mark as INCOMPLETE and list missing fields.
   - Are relationships correct? Check FAM records for spouse links, FAMC/FAMS references.

4. **Create the audit file**: `[VAULT_PATH]/gedcom_audit.md` with:
   ```
   | Person | Status | Missing Fields | Notes |
   |---|---|---|---|
   | [ANCESTOR] | MISSING | all | Not in GEDCOM |
   | [ANCESTOR-2] | INCOMPLETE | death_date, burial | Has INDI but missing data |
   ```
   Include a separate privacy section listing living or possibly living people whose names, exact dates, places, notes, media, or relationship links must be removed before sharing.

5. **Fix missing publishable persons**: For each MISSING publishable deceased person, add a new INDI record:
   ```
   0 @I[N]@ INDI
   1 NAME [Given] /[Surname]/
   1 BIRT
   2 DATE [DD MMM YYYY]
   2 PLAC [Place]
   1 DEAT
   2 DATE [DD MMM YYYY]
   2 PLAC [Place]
   ```

6. **Fix incomplete publishable persons**: For each INCOMPLETE publishable deceased person, add the missing fields to the existing INDI record.

7. **Fix publishable relationships**: Ensure publishable deceased relationships have FAM records linking husband, wife, and children. Remove or privatize any FAM record that exposes living or possibly living relationship structure in a shared export:
   ```
   0 @F[N]@ FAM
   1 HUSB @I[husband]@
   1 WIFE @I[wife]@
   1 CHIL @I[child1]@
   1 MARR
   2 DATE [DD MMM YYYY]
   2 PLAC [Place]
   ```

8. **Validate**: After all changes, verify:
   - Every INDI has at least a NAME
   - Every FAM has at least HUSB or WIFE
   - No orphaned CHIL references (child ID exists as INDI)
   - No duplicate INDI records for the same person
   - No living-person names, exact dates, places, notes, media paths, or relationship links in a shared GEDCOM
   - The file ends with `0 TRLR`

## GEDCOM 5.5.1 Quick Reference

```
0 HEAD
1 SOUR autoresearch-genealogy
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Given /Surname/
1 SEX M
1 BIRT
2 DATE 10 MAY 1866
2 PLAC Example County, Example State, USA
1 DEAT
2 DATE 12 DEC 1950
2 PLAC Example Town, Example State, USA
1 FAMS @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
1 MARR
2 DATE 15 JUN 1911
2 PLAC Example Town, Example State, USA
0 TRLR
```
