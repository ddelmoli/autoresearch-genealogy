# FamilySearch Source Harvest (Recipe-S)

Harvest the independent primary-source citations already attached to each ancestor's FamilySearch profile down into that person's vault entry, raising source-coverage on entries that carry an FS PID but cite few or no records. This is the read-only, FS→vault direction of "Recipe-S" — the same harvest that `17-familysearch-tree-contribution` folds in as its step 8.5, extracted here as a standalone pass so a coverage round can run on its own over the whole backlog without any tree-contribution work.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[FS_GROUP_TREE]`: URL of the logged-in FamilySearch tree/group the ancestors live in (for navigation context)
- `[SCOPE]` (optional): a subset to focus the pass — a shard file, Region, generation range, or confidence tier (e.g. `Family_Tree_<Region>.md`, `Gen 3-5`, a region name). Omit to sweep every FS-PID-bearing entry.

## Tooling prerequisite (read first)

The harvest reads each profile's **Sources tab with Detail View ON**. The record ARKs and the external "Web Page (Link to the Record)" links only enter the page DOM when Detail View is toggled on, and the single-page app usually needs a second render call after navigation — so this cannot be done with WebFetch/WebSearch. Use **Claude in Chrome** with the operator's FamilySearch account already signed in (tree at `[FS_GROUP_TREE]`). The harvest itself is READ-ONLY on FamilySearch (it attaches nothing), so it is autonomous — no operator gate — exactly like the vault write-back. (Pushing a vault source UP onto an FS profile is the opposite direction and IS operator-gated; that lives in prompt 17, not here.)

## Autoresearch Configuration

**Goal**: For every person entry across the family-tree files (`[VAULT_PATH]/Family_Tree.md` and the shard files in its File Index) whose `- meta:` block carries a FamilySearch PID, ensure the entry's `**FS-attached sources**` bullet lists the independent primary-source records (ARKs) attached to that profile's FamilySearch Sources tab.

**Metric**: Number of FS-PID-bearing person entries that cite zero FS-attached primary-source ARKs (the SOURCE_GAP backlog).

**Direction**: Minimize (lower is better)

**Verify**: Count FS-PID-bearing entries across the family-tree files whose entry has no `**FS-attached sources**` bullet citing at least one record ARK. If your vault provides a coverage-audit helper (this vault: `scripts/harvest_sources.py` — categories SOURCE_GAP / LOW_COVERAGE / WELL_SOURCED, with `--gen` / `--gen-range` / `--region` / `--confidence` / `--csv` filters), use its SOURCE_GAP count as the authoritative metric and its ranked SOURCE_GAP list as the worklist. Otherwise grep the family-tree files for `- meta:` lines bearing a real `fs: XXXX-XXX` PID and check each for a following FS-attached-sources bullet. Log the before/after delta each iteration.

**Guard**:
- **⚠ THE SOURCES TAB IS HALF THE PROFILE. Read the Research Help surface too** (added 30 JUL 2026). Attached sources cannot tell you what is left to find; **unattached record hints, possible duplicates, data problems and prior not-a-match decisions** live on the Research Help card, which **never renders under automation** — the driven tab is backgrounded (`document.hidden === true`) so FamilySearch does not mount it, and the page shows empty slots with no error. Fetch its endpoints directly instead (same-origin, credentialed); they are specified in `CLAUDE.method.md` under the source-coverage rule. A harvest that reports "N ARKs" from the Sources tab alone has measured **citation agreement**, not coverage. Two constraints carry over: a hint is a **candidate** to be judged on identifiers, not a record; and **attaching one on FS is operator-gated** (prompt 17), while reading is free.
- **Detail View MUST be ON before extracting.** Harvesting with it off yields a FALSE "0 ARKs / book-citations-only" read (the record hrefs are not in the DOM). After a fresh navigate, re-issue the render/extract call once so the SPA has populated the source list. A pre-existing "0 ARK" bullet from an earlier run may be a stale Detail-View-off read — re-check rather than trust it.
- **Harvest independent PRIMARY records only.** INCLUDE: (a) FS indexed-record ARKs (`ark:/61903/1:1:...`); (b) FS image/browse-record ARKs (`ark:/61903/3:1:...`) — the "View the original document" register-image links, which are the primary source for browse-only collections and attach as `3:1:` not `1:1:`; (c) external archive image links in a source's "**Web Page (Link to the Record)**" field that point to a primary register (Antenati `ark:/12657/...`, metryki, szukajwarchiwach, and equivalents for your lines). EXCLUDE: (d) published-book / journal citations (lineage society books, Great Migration, NEHGR, TAG, archive.org / Google Books) — real but bibliographic: cite the important ones in narrative **prose** with page numbers and note their count in the bullet (e.g. "+ 2 book/journal citations, no record ARK"); do NOT fabricate an ARK for them; (e) user-submitted trees (copied Ancestry/WikiTree/Geni trees, RootsFinder) — NOT independent evidence (trees copy each other and often copy this vault), excluded from the coverage metric.
- **⚠⚠ EXTRACT ARKs FROM `href` ATTRIBUTES, NEVER FROM THE PAGE TEXT — A CITATION STRING CONTAINS ARKs THAT ARE NOT LOCATORS** (verified against a live profile 01 AUG 2026; deferred_decisions 27(d)). Each attached source renders its locator as a link under **"Web Page (Link to the Record)"**, and *separately* prints a full citation such as `"United States, Obituary Records, 2014-2023", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:61XC-KGR5 : Tue Nov 05 ...)`. **The ARK inside that citation string is frequently a DIFFERENT id from the link's.** A regex over `innerText` therefore returns GHOST ARKs — locators that belong to no attached source. Measured on one profile: **3 ARKs in the text, 2 in the hrefs, 1 ghost.** Scrape `a[href*="ark:/61903/"]`; the useful anchor for scoping is the surrounding `[data-testid="view-edit-url-or-image"]`.
- **`UNFINISHED ATTACHMENTS` IS A PER-SOURCE BUTTON, NOT A SECTION, AND IT DOES NOT MEAN "NOT ATTACHED"** (`data-testid="source.unfinished.link"`). It appears on a source that IS attached to this person but has **not been attached to every person named in the record**, and it is a call to action, not a warning about validity. **Do not skip or discount a source because it carries this badge.** Recorded because a session on 31 JUL 2026 read it as a heading over a list of drafts, concluded the harvest was scraping unattached material, and stopped an IMPROVE draw on that basis — the diagnosis was wrong and cost a lane draw. The lesson generalises: **an FS affordance whose meaning you have inferred from its label is not evidence** — check what the control actually is before writing a rule around it.
- **Never fabricate or guess an ARK.** Only record an ARK string actually present on the page. A record with no extractable ARK is logged as such, not invented.
- **⚠ CAPTURE THE RECORD DESCRIPTION WITH THE LOCATOR, IN THE SAME PASS. A BARE ARK IS UNAUDITABLE.** Spec 03 already requires `- <what the record is> — <host:locator>`, and vault-wide adoption is ~4%. That gap is not cosmetic: it is exactly why the contamination above is invisible after the fact, why the Find a Grave exclusion (e) cannot be counted, and why a wrongly-harvested ARK looks identical to a good one forever. Take each source's **title** and **"Where The Record Is Found (Citation)"** line along with its ARK; a locator you cannot describe is one you have not actually read.
- **Scope external-link capture to known archive domains.** A whole-page href scan picks up FS footer junk (YouTube/Facebook/help links). Match only the archive domains that hold primary registers for your lines.
- **Read-only on FamilySearch.** This prompt does not attach, merge, edit, or create anything on FS. If a profile is clearly missing a source the vault holds, note it as a prompt-17 ATTACH candidate (operator-gated) — do not act on it here.
- **Living-person privacy.** Skip any entry whose `life_status` is `living` or `unknown`. Do not harvest, web-search, or publish records for living or possibly-living people.
- **WikiTree corroboration is a separate qualitative layer, off this ARK metric.** A WikiTree profile's *cited primary sources* and analytical notes can be valuable for contested lines, but capture them as a distinct corroboration bullet, never as a count toward this ARK coverage metric (a bare tree assertion is not independent evidence).

**Iterations**: 6

**Protocol**:

1. **Build the worklist**: produce the ranked list of FS-PID-bearing entries that lack source coverage (SOURCE_GAP first, then LOW_COVERAGE). Use the coverage-audit helper if present (`scripts/harvest_sources.py`, optionally filtered to `[SCOPE]`); otherwise grep the family-tree files as in **Verify**. Prioritize by generation (closest to the subject first) and confidence tier. Before harvesting a given person, **grep `[VAULT_PATH]/logs/` for their name** to see whether a prior round already read their Sources tab (do not re-harvest an entry already marked WELL_SOURCED unless a new source has since been attached).

2. **Open the profile's Sources tab**: navigate to `/tree/person/sources/{PID}` for the target PID. Wait for the SPA to render, then **toggle the Detail View checkbox ON** and re-issue the extract call so each source's record ARK + "Web Page (Link to the Record)" external link are in the DOM.

3. **Extract**: collect every `ark:/61903/1:1:` and `ark:/61903/3:1:` href, plus the domain-scoped external archive links from the "Web Page (Link to the Record)" fields (per Guard). Note each source's record category (census, vital, immigration, naturalization, parish/register image, etc.).

4. **Filter** per the Guard's include/exclude policy: drop published-book/journal citations and user-tree citations from the ARK list; keep them only as a prose note + a count, never as a fabricated ARK.

5. **Write back to the vault** (autonomous — local files only): add or update the entry's `- **Sources**` bullet in the Spec 03 record-locator grammar — one sub-bullet per RECORD with a brief descriptor and its `host:locator` pairs (`fs:1:1:…` indexed, `fs:3:1:…` image, `antenati:ark:/12657/…` and other hosts). A record cited on more than one host lists its locators together on one line (the metric counts records, not locators). The legacy flat `- **FS-attached sources**: 1:1:…, 3:1:…` form is still parsed during the transition (`scripts/migrate_sources.py` converts it), but write new bullets in the `**Sources**` form. Keep the `- meta:` block lean (fixed grammar only); harvest provenance + the locator list live in the body bullet. Update `profile_status`/`evidence_tier` if the new coverage warrants (e.g. an entry that now has a primary record can move toward `complete`).

6. **Re-verify**: re-run the metric (or re-grep) to confirm the entry left SOURCE_GAP. **Log negative results**: an entry whose Sources tab genuinely holds only book/journal or user-tree citations is a valid endpoint — record "harvested, 0 independent primary ARKs (book-citations-only)" so a future round does not re-read it expecting a different answer.

7. **Record the round**: create a session log at `[VAULT_PATH]/logs/YYYY-MM-DD-fs-source-harvest.md` (anchors read, ARKs added, negatives), and add a one-line summary to the session index in `[VAULT_PATH]/Handoff.md` (or `Research_Log.md`, per your vault's convention). If your vault tracks harvest cadence, reset its "last round" marker.

## Yield expectations by region (calibration, not a target)

Coverage varies by where a line's records live, so a low ARK count is not always an incomplete harvest:
- **Dense Anglo-American / UK lines** (multiple census + vital + parish collections): typically 20-35 ARKs per anchor.
- **Browse-only register lines** (e.g. Italian civil/Tribunale registers that attach as `3:1:` image ARKs, not `1:1:` indexed records): a handful of register-image ARKs — make sure the `3:1:` links are captured, since a `1:1:`-only read misreads these as "0 ARKs".
- **Lines whose primary records are NOT yet on FamilySearch** (parish registers held only at a regional archive; emigrant lines documented mainly on the departure side): few or zero FS ARKs even after a complete harvest. Cite what exists, log the gap, and treat the off-FS primary research as a separate (often operator-gated) task — do not keep re-reading the Sources tab expecting more.

## Recording worked-anchor status

When an anchor has been harvested end-to-end, its coverage state lives in the entry's `**FS-attached sources**` bullet (the ARK list) and in `[VAULT_PATH]/logs/` (round notes + negatives), not in this prompt. That is what lets a future round skip already-WELL_SOURCED anchors and re-target only the gaps.
