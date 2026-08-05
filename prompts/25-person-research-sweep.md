# Person Research Sweep (the default unit of research work)

Research ONE person across EVERY resource available, and write the result into their
entry as a biography with its sources. This is the prompt `22-research-iterations`
dispatches to for IMPROVE work, and it REPLACES `19-fs-source-harvest` as the default:
prompt 19 is now just this prompt's **FamilySearch leg**.

**Why it exists (operator, 01 AUG 2026).** The standing goal is *"for every person in
the vault to have as complete a biographical entry as possible"*, built by visiting as
many resources as possible. The toolkit had drifted a long way from that: measured on
the reference vault, **660 of the 691 entries citing any source cited FamilySearch, and
only 26 people in the whole vault cited two or more hosts**. The IMPROVE lane was
literally *defined* as "SOURCE_GAP entries with a harvestable FS PID", so a person with
no FamilySearch profile could not enter the improvement lane at all. FamilySearch is
**the place this vault chooses to SYNC with. It is not the evidence base.**

**A record count is not a biography.** An entry with thirty census ARKs and no prose
about the person's life is not finished work. The deliverable is a written life, with
every claim carrying a citation.

Copy-paste prompt (fill the placeholders):

```text
Research [PERSON] as completely as the available resources allow. Vault:
AUTORESEARCH_VAULT="[VAULT_PATH]".

0a. CHECK BEFORE SEARCHING, PER SOURCE. grep vault/logs/ and Open_Questions.md for
   the name, and READ THE ENTRY. A prior negative is a fact about ONE source with
   ONE spelling on ONE date -- it does not close the person, and it does not close
   a different repository. Do not re-run a spent route; do note which routes the
   entry already says are closed.

0b. ⛔ CONFIRM THE FS PID RESOLVES, BEFORE ANY HARVESTING. If the person carries an
   `fs:` PID, load `/tree/person/family/{PID}` and check the profile is still THAT
   person: the name and dates match, and the URL did not redirect. A profile merged
   away or deleted still LOOKS like a person, reads on a walk as someone with no
   relatives, and silently poisons everything you harvest against it.
   - ⚠ POLL FOR A PID PATTERN INSIDE THE FAMILY PANEL. `document.title` resolves
     LONG before the panel mounts, so a title-gated read returns an empty panel that
     cannot be told from "no parents on FS". That produced three bad reads in one
     sitting on 02 AUG 2026, two of them flatly wrong.
   - Record it with `profile_review.py --record <id> --probed fs`.
   - ⛔ **THIS SCORES NOTHING.** It is a PRECONDITION of the sweep, not a
     disposition (deferred 40): you are opening the profile to harvest it anyway.
     Counting it would let the cheapest action in the system satisfy a lane floor
     that sourcing has never met. The plan marks rows needing it; the mark is a
     reminder, never a unit.

1. SWEEP THE RESOURCES. Work DOWN this list. Log every one you touch, including
   the empty ones -- a negative naming what was searched is the deliverable that
   stops the next session repeating it.

   a. FAMILYSEARCH, all THREE surfaces, not just the first:
      - Sources tab with **Detail View ON** (off = a false "0 ARKs" read).
        Detail View also renders each source's COLLECTION TITLE: capture it with
        every locator, because that one string both becomes the record description
        below AND decides the policy-(e) memorial exclusion
        (`harvest_sources.is_memorial_collection` -- negate a positive with `~`,
        never judge the brands by eye) AND the policy-(c)/(d) reference-work
        exclusion (`harvest_sources.reference_work_limb` -- Wikipedia, Quora and
        BritRoyals are limb (d), worth nothing; Britannica and the IGI are limb
        (c), bibliographic. On deep British rows this class is the MAJORITY of
        what FS attaches). Full rule in `19-fs-source-harvest` step 3.
      - **Research Help**: unattached record hints, possible duplicates, data
        problems, and prior not-a-match decisions. It does NOT render under
        automation (the driven tab is backgrounded), so fetch the four
        `/service/tree/tree-data/...` endpoints instead.
      - **The discussions / collaboration tab and any attached notes.** Other
        researchers argue identity there, and that argument is often the only
        place a conflation is named.
   b. ANCESTRY (operator subscription): record collections AND hints. Read what a
      member tree CITES; never the tree's bare assertion.
   c. WIKITREE: the profile, its Research Notes, and its G2G discussion threads.
      Corroboration comes from **what WikiTree cites**, never from WikiTree.
   d. THE REGION'S OWN ARCHIVE -- the plan prints a route hint per row:
      Italian -> Antenati (per-comune, coverage varies), the provincial state
        archive, the diocesan archive for pre-1866 parish registers;
      Polish -> Geneteka, metryki.genealodzy.pl, szukajwarchiwach, AGAD;
      British -> FreeREG, FreeBMD, GRO Online index, TNA Discovery, PRONI, the
        county record office;
      Colonial US -> published town Vital Records, probate and land, NEHGR;
      Jewish -> JewishGen Unified Search, JRI-Poland, Gesher Galicia, JOWBR,
        Yad Vashem.
   e. NEWSPAPERS AND OBITUARIES (obituaries COUNT as records, ruling of 01 AUG
      2026), city directories, and the operator's library surfaces: HeritageQuest,
      Fold3, Internet Archive, OpenAthens.
   f. FOLLOW EVERY LINK TO A PRIMARY SOURCE. An index entry is a pointer; the
      IMAGE is the record. A source's "Web Page (Link to the Record)" field often
      holds a direct archive ARK, and the surrounding fascicolo frequently answers
      a question nobody asked it.

2. READ WHAT YOU FIND, AT THE SOURCE. Do not write a claim from a search-result
   summary or a structured data panel: a panel states a guess as confidently as a
   fact, and the hedge lives in the prose. Open the image or the page.
   ! A HINT IS A CANDIDATE, NOT A RECORD. Evaluate it on IDENTIFIERS before citing
   it -- a matching date is never evidence of identity on its own.

3. WRITE THE BIOGRAPHY into the person's entry. Not a locator dump: what the
   records establish about this life -- birth, baptism, marriage(s), children,
   occupation, residences and moves, migration, military service, death, burial,
   probate -- each claim traceable to the record that carries it. Then the
   `- **Sources**` bullet, one sub-bullet per RECORD, **naming the record** before
   its locators (`- 1910 US Census, Manhattan — fs:1:1:XXXX-XXX`). A bare locator
   says where; only the description says what.
   ! AND OPEN AN Open_Questions ENTRY FOR ANYTHING STILL UNRESOLVED -- do not leave
   it in the narrative alone. A sweep routinely turns up a contradiction, a record
   located but unread, or a choice between candidates; the entry states CURRENT
   STATE, so those die there unless they also reach the register. Owed when
   resolving it needs work not yet done; NOT owed for what you settled, or for a
   closed negative with no route left (that is a declaration). Batch thin ones,
   cross-link both ways, and name what would settle it. Full rule in
   CLAUDE.method.md.
   ! CITE THE SECOND HOST WHEN YOU HAVE IT. One record held by two repositories is
   ONE record with two locators; recording both is what moves this person out of
   SINGLE_SOURCED.

4. RECORD THE NEGATIVES on the entry, with their SCOPE: what was searched, under
   which spellings, and what that search structurally cannot contain. "Not on FS"
   is not "does not exist"; "not under this spelling" is not "absent".

5. QUEUE, NEVER PERFORM, any outward mutation (FS attach/merge/edit/create) as an
   `FS write-back QUEUED` bullet with its evidence and the person's life_status.

6. Never web-search anyone whose life_status is living or unknown.
```

## Inputs To Replace

- **[PERSON]** — the person to research: a vault `id`, or a name plus their file.
- **[VAULT_PATH]** — absolute path to the vault working tree.

## Autoresearch Configuration

**Goal**: One person's entry moved as far toward a complete, fully-cited biography as
the available resources allow — with the sources drawn from as many independent
repositories as hold them, not from whichever one is easiest to scrape.

**Metric**: Per person worked: distinct source HOSTS cited (the `SINGLE_SOURCED` →
`MULTI_SOURCED` transition in `harvest_sources`), records cited, biographical facets
filled, and resources swept-and-logged including the empty ones.

**Direction**: Maximize hosts, records and facets; minimize entries documented by a
single repository.

**Verify**:
`python3 scripts/harvest_sources.py --heartbeat` (SOURCE_GAP / SINGLE_SOURCED /
MULTI_SOURCED); `python3 scripts/bio_completeness.py --summary` (facet coverage);
the entry's own `- **Sources**` bullet; `python3 scripts/prose_audit.py`.

**Guard**:
- **FamilySearch is the sync point, not the evidence base.** An entry sourced only to
  FS is not finished, however many ARKs it holds. If FS is the only host after the
  sweep, say which other repositories were tried and what they structurally cannot
  contain.
- **A record count is not a biography.** Thirty ARKs and no prose is not done.
- **Read the source, not the summary.** Search-result snippets and structured data
  panels state guesses as facts; open the image or the page.
- **A hint is a candidate.** Check identifiers before citing; a fitting date is not
  evidence.
- **User trees are never records** (policy (d)) — they may be *pointers*, and what
  they CITE may be real. Negate an excluded locator with `~` rather than omitting it.
- **A memorial/headstone index is judged on the ARTIFACT, not the brand** (policy (e)):
  a stone whose PHOTO you actually opened is evidence — record it in a
  `- **Burial evidence**` bullet (off the ARK metric), good for the death date,
  burial place, family grouping and inscriptions an index drops, but NEVER alone for
  a birth date. No image = a contributor's assertion, worth nothing, negate it. A
  modern monument for a pre-1750 person is memorialisation, not evidence.
- **Log the empty resources.** An unlogged negative gets re-run for ever.
- **Prior negatives are scoped, not final** — one source, one spelling, one date.
- Outward mutations are operator-gated: queue them.
- Living / unknown people are never web-searched.

**Iterations**: 1 per person — this prompt is the unit of work that
`22-research-iterations` calls repeatedly, once per drawn candidate.

**Protocol**:

1. Check the logs and the entry for what has already been tried, per source.
2. Confirm the FS PID still resolves to this person (step 0) -- it scores nothing,
   and a merged-away PID poisons every harvest run against it.
3. Sweep the resources in order, logging each including the empty ones.
4. Read every promising find at the source, checking identifiers before adopting.
5. Write the biography and the `- **Sources**` bullet, naming each record.
6. Record scoped negatives on the entry.
7. Queue outward mutations; never perform them.
