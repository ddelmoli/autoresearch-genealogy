# Review Card: Person Research Sweep

Prompt: [25 Person Research Sweep](../prompts/25-person-research-sweep.md)

## Good Output

- The entry reads as a BIOGRAPHY — birth, marriage(s), children, occupation, residences and moves, migration, death, burial, probate — not a list of locators with a name on top.
- Every claim traces to the record that carries it, and the `- **Sources**` bullet NAMES each record before its locators (`- 1910 US Census, Manhattan — fs:1:1:XXXX-XXX`).
- Sources come from MORE THAN ONE repository wherever more than one holds them; a record held by two hosts is cited as ONE record with two locators.
- All three FamilySearch surfaces were read, not just the first: Sources with Detail View ON, Research Help (hints, duplicates, data problems, prior not-a-match decisions), and the discussions/notes tab.
- The region's own archive was actually tried, and the attempt is logged with its coverage bound ("Antenati holds this comune only from 1930").
- Discussion content (WikiTree G2G, FS notes, member-tree comments) was read for identity arguments, and what it CITES was followed.
- Every resource touched is logged INCLUDING the empty ones, each negative scoped: what was searched, under which spellings, and what that search structurally cannot contain.
- Index hits were followed to the IMAGE and read at the source.
- Outward mutations are queued as `FS write-back QUEUED` bullets with evidence and `life_status`, never performed.

## Red Flags

- The sweep stopped at FamilySearch and the entry now cites one host. FS is the SYNC point, not the evidence base.
- A claim is written from a search-result snippet or a structured data panel rather than the record itself — panels state guesses as confidently as facts.
- An FS hint is cited as a record without an identifier check; a matching date is treated as evidence of identity.
- A user tree is cited as a record (policy (d)) rather than negated with `~` or used only as a pointer.
- A memorial is cited as evidence WITHOUT its photograph having been opened, or a headstone age is used as a birth date, or a modern monument for a pre-1750 person is treated as contemporary (policy (e)'s three tiers).
- "Not on FamilySearch" is written as "no records exist", or a single-spelling zero is written as absence.
- The Sources bullet grew but the prose did not: a record count is not a biography.
- Negatives are not logged, so the next session re-runs the same spent route.
- A living or possibly-living person was web-searched.

## Verify Manually

- Run `python3 scripts/harvest_sources.py --heartbeat` and confirm the person moved out of `SINGLE_SOURCED` if a second repository holds anything on them.
- Run `python3 scripts/bio_completeness.py --worklist` and confirm the person's core facets improved.
- Open two or three cited records and confirm each says what the entry claims.
- Confirm each negative names its scope (source, spelling, date), not just "nothing found".
- Confirm `python3 scripts/prose_audit.py` is at ERROR 0 — a new date in prose that disagrees with the meta field is the common regression here.

## Reject The Result When

- The entry cites only FamilySearch and no other repository was even attempted or logged as unavailable.
- Locators were added with no record descriptions, leaving a census that cannot say what it counts.
- A hint or a same-name match was adopted as identity without discriminators.
- The biography asserts facts no cited record carries.

## Next Prompt

Queue outward corrections for [17 FamilySearch Tree Contribution](../prompts/17-familysearch-tree-contribution.md). If the sweep surfaced a parent, continue with [01 Tree Expansion](../prompts/01-tree-expansion.md); if it surfaced an unresolved conflict, [08 Open Question Resolution](../prompts/08-open-question-resolution.md).
