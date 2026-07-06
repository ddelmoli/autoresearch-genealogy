# Immigration Search

Search for immigration, naturalization, emigration, and passenger records for immigrant ancestors.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[ANCESTOR NAME]`: immigrant ancestor's full name and known variants
- `[YEAR RANGE]`: approximate immigration or naturalization date range
- `[STATE]`: state where naturalization may have occurred
- `[CITY/COUNTY]`: city or county where naturalization may have occurred

## Autoresearch Configuration

**Goal**: For every immigrant ancestor in the regional family-tree files (`[VAULT_PATH]/Family_Tree.md` and the shard files in its File Index), locate their immigration record (passenger manifest), emigration record (departure-side index), and/or naturalization record.

**Metric**: Number of immigrant ancestors without an immigration, emigration, or naturalization record

**Direction**: Minimize (lower is better)

**Verify**: Count immigrant ancestors (born outside the US, with "emigrated"/"immigrated" notation) across the family-tree files who lack a citation to a passenger list, departure-side index, or naturalization document.

**Guard**:
- Name spelling on passenger manifests can be extremely different from what the family used in America. Search all plausible variants, including the **original-language / European spelling** (see techniques below).
- Not all immigrants were naturalized. Some remained resident aliens their entire lives.
- Pre-1820 US passenger lists are sparse to nonexistent. Pre-1892 NY arrivals are Castle Garden, not Ellis Island.
- **A US arrival manifest line can be garbled or never-indexed** (no name/soundex/ship/first-name search reaches it). Confirm the identity from an independent source (departure-side index, naturalization, headstone) FIRST, then go to the manifest IMAGE knowing what to look for.
- **Spouses frequently emigrated separately.** A wife often arrived under her maiden name on a different voyage. Search both surnames and don't assume a couple travelled together.
- **Common immigrant names need disambiguation, not just a name match.** A common immigrant name returns many same-name men. Distinguish by birthplace, census ward / household composition, spouse + children's names, and age→birth-year BEFORE attaching a record, adopting a PID, or merging a profile. (a same-name man with a different birthplace, spouse, or census ward is NOT a merge — post an FS Alert Note instead of merging.)
- **Couples who married in Europe leave no US marriage record** naming their parents. If the index shows no shared certificate number between a groom's certs and a bride's certs, they married pre-immigration — the parents (Gen +1) are then only on European records or a US death/naturalization image.
- **Distinguish free (Claude-drivable) work from operator-gated work** and label each finding accordingly. Index/database SEARCHES are free; downloading record IMAGES, captcha-gated archive searches, and ordering certificates are operator steps. Do not re-propose an operator-gated item as a free next-action.
- **CREATE/edit actions on FamilySearch are operator-gated.** This prompt is discovery + writing findings back to your own tree; pushing anything up to FamilySearch is a separate, human-approved step.

**Iterations**: 10

**Protocol**:

1. **Identify immigrant ancestors**: From each family-tree file, list every person born outside the US (or with "emigrated"/"immigrated" notation). Before searching, **check your research logs and open-questions notes for the name** to see what has already been tried (do not repeat prior negative searches unless using a new source or strategy). For each immigrant, note:
   - Name (all known variants, including original-language and Hebrew/Yiddish spelling)
   - Approximate arrival year or range; approximate emigration year
   - Country/region of origin (as specific as possible: country, region, province, town/shtetl)
   - Port of departure and port of entry (if known); ship name (if known)
   - Final destination in the US; who they were joining

2. **Search arrival (US) passenger manifests** (NY = Ellis Island 1892+; Castle Garden / Barge Office pre-1892):
   a. **Steve Morse One-Step** (stevemorse.org) — the best free front-end. The **Gold Form (1892–1924)** searches the JewishGen Enhanced Ellis Island DB (a logged-in JewishGen session carries via cookies) with Daitch-Mokotoff phonetic surname + arrival-year-range + age-range + gender + town + companion filters. **Driving gotcha:** the form is GET with `target=_blank` (a synthetic submit just opens a blocked popup → nothing happens); instead serialize the form fields to a query string and navigate to `action?query` in-tab (then mutate `LNM`/`SYR`/etc. on the URL for follow-up searches). The **White Form** covers 1820–1957. (`ellisgold.html` 404s — reach the live forms from the stevemorse.org homepage.)
   b. **FamilySearch** passenger collections: pre-1892 NY = collection **`1849782`** ("New York Passenger Lists, 1820-1891" — the successor to the now-**DEFUNCT** castlegarden.org), Ellis 1892+ = a separate FS collection. Search by name variant + birth-year + birthplace (the FS arrival-date URL params error — filter on birth year/place instead). FS Soundex over-matches (a Soundex search pulls unrelated like-sounding surnames).
   c. **Internet Archive — free NARA microfilm page images** (Allen County upload, collection `vesselpassengercrewnewyork`): the entire **M237 (NY 1820-1897)** + **T715 (NY 1897-1957)** films, one IA item per reel, FREE + Claude-readable — **no operator/FS image download needed**. IA reel № = NARA roll №; the item `description` gives the reel's date range. Pull a page: `curl ".../download/{id}/page/n{LEAF}.jpg?scale=4"` then downsize/crop (`sips`/`magick`). ⚠ Same microfilm = same physical fold/tear/"cut-off" damage as FS (a retake-target card marks damaged frames).
   d. **NARA Castle Garden / Balch bulk Data Files** (catalog.archives.gov NaId 4719476 → e.g. **229630481** `PAS_RS.txt`, 88 MB, pipe-delimited, **greppable locally**): rich origin-town / ship / arrival-date / birthplace fields; country codes (46=Romania, 6=Austria, 34=Galicia, 44=Russia); `ALLHDRS.txt` joins each MID → ship + arrival date. ⚠ THIN subset (Russia/Austria-Hungary-weighted; sparse Romania + post-1897) — good for bulk-grep, not comprehensive.
   e. CEMLA (search.cemla.com) for **Buenos Aires arrivals 1882–1960** — for Italian/Spanish lines whose emigrants went to Argentina, not the US (operator types the captcha)
   f. Try name variants: original spelling, phonetic, abbreviated, **maiden name (for women)**, Hebrew/Yiddish given name. If name + phonetic + town searches all fail across BOTH the departure and arrival indexes, the line is genuinely **un-indexed** (a whole voyage / inspection-group can be) → escalate to the manifest IMAGE by ship + date (free on IA, above), not more index searches.

3. **Search departure (emigration) indexes** — these are often far cleaner than the garbled US arrival index:
   a. **Stadsarchief Rotterdam HAL passenger database** (stadsarchief.rotterdam.nl/passagierslijsten) — Rotterdam DEPARTURE side for Holland America Line ships, May 1900+; free, name-indexed. Gives ship + departure date + Yiddish/European given name, but NOT the origin town.
   b. Other national emigration archives by origin: Hamburg (Auswanderer), Bremen, Antwerp (Red Star Line), Digitalarkivet (Norway), Emihamn (Sweden)
   c. Use the departure index to recover the **European given name**, then re-search the US arrival manifest with that spelling.

4. **Search naturalization records**:
   a. FamilySearch "[STATE] naturalization" collections; for NYC, the SDNY/EDNY District & Circuit Court records (NARA M1972, RG 21)
   b. `"[ANCESTOR NAME]" naturalization [CITY/COUNTY] [YEAR RANGE]`
   c. Post-1906 naturalization records are richest (exact birthplace town, birth date, arrival date, ship, occupation, physical description, witnesses)
   d. **Caveat:** the FS naturalization INDEX often exposes only "Event Place: Manhattan / New York" — the birthplace TOWN and arrival fields are on the IMAGE only (operator-gated). Pre-1906 declarations frequently give only the country/province, not the town.
   e. USCIS Genealogy Program — C-files / certificate files, $65/request (operator-order)

5. **Jewish / Eastern-European line techniques**:
   - **Landsmanshaft burial = town of origin.** NYC Jewish cemetery plots are owned by hometown societies. Search the **Mount Hebron interment DB** (mounthebroncemetery.com/interments/) and read the **Society column** — a society named for a town (e.g. "1st [Townname]er") points to that town of origin in the old country. Plot adjacency reveals spouses + disambiguates same-name dead. ⚠ A **married woman lies in her husband's** society plot, so it indicates the *household's* (his) town, not necessarily her own birthplace.
   - **Hebrew headstone = the father's name (a free generation).** "X bar/bat Y" gives the patronymic. e.g. "Eliezer bar Yosef" yields the father's name (a free generation), often corroborated by a firstborn-namesake.
   - **JewishGen** (free account): Unified Search → JRI-Poland (Galician/Polish vital records), Bessarabia/Romania DBs, JOWBR (burials w/ Hebrew names + parents), JGFF (researcher/cousin matches by surname+town), Communities/Gazetteer (town IDs). Search the **original European spelling** (US forms over-match on Soundex). Gesher Galicia's **All-Galicia DB** (gesher-galicia.org) is separate, for pre-1916 Galician births.
   - **Yad Vashem Shoah Names DB** (collections.yadvashem.org/en/names) — Pages of Testimony name parents/spouse/birthplace; use the field-specific Place-of-Birth advanced URL. Only bridges a generation if a relative survived to submit; verify the record's actual town (synonyms mis-resolve).
   - **Check whether the European vital records even survive** before chasing them: some pre-1919 Galician Jewish registers are lost (check the Gesher Galicia district inventory) — a "town identified, records gone" result is a valid, loggable endpoint.

6. **NYC certificate images** (the source that breaks maiden-name + parents + birth-town walls): **NYC Historical Vital Records / DORIS** (a860-historicalvitalrecords.nyc.gov) — actual birth/death/marriage CERTIFICATE IMAGES, all five boroughs, births→~1909 / marriages→~1949 / deaths→~1948. A death cert names the deceased's PARENTS + often a **birth town** where the FS index of the same cert gives only the country; a birth cert names the MOTHER'S MAIDEN NAME. Look up the cert # from the FS index, then pull the image here. Browser-only; download the image, then read it with your AI tool.
   - **The FS-indexed version of a NYC death cert carries structured parent personas** (father/mother). Those personas let you CREATE both parents (Gen +1) on FamilySearch as a coupled, source-attached pair in one flow (an operator-gated CREATE step). ⚠ Source Linker gotcha: clicking "Add New Person" for a second parent can re-fire the first parent's still-active "Create New Person" form, producing a duplicate with the wrong name and sex. Confirm each created person's name and sex before the final Attach.

7. **Data extraction**: When a record is found:
   - Passenger manifest: full name, age, occupation, last residence (= origin town), destination, ship, departure/arrival port + date, traveling companions, who joining, literacy, physical description, money
   - Naturalization: full name, birth date, birthplace (town + country), arrival date/port/ship, occupation, address, witnesses
   - Departure index: European given name, ship, departure date, fare register reference
   - Cemetery/headstone: society (= town), plot, Hebrew patronymic, dates

8. **Cross-reference**: Compare against existing vault files. Does the birth date match? Does the birthplace narrow a region/town? Are traveling companions or witnesses family members? Does a society/headstone corroborate a manifest origin?

9. **Update your records**: Create transcription notes for found record IMAGES; update the person's entry in your tree with the new facts and citations. **Log negative results** ("searched X under spellings A/B/C, no clean match" is valuable). Label each finding **free** vs **operator-gated**. Record the session's searches and outcomes in your research log.

## Key Immigration / Emigration Databases

| Database | Coverage | Access |
|---|---|---|
| Steve Morse One-Step (stevemorse.org) | NY arrivals — Gold Form 1892–1924 (JewishGen EIDB), White Form 1820–1957; phonetic/missing-manifest tools | Free (GET-serialize to drive) |
| ~~Castle Garden (castlegarden.org)~~ — **DEFUNCT** → FamilySearch collection **1849782** | NY arrivals 1820–1891 (pre-Ellis) | Free |
| **Internet Archive NARA microfilm reels** (`vesselpassengercrewnewyork`) | Full M237 (1820-1897) + T715 (1897-1957) NY manifest IMAGES, one item/reel | Free (Claude-readable; reel№=roll№) |
| **NARA Castle Garden/Balch bulk Data Files** (catalog.archives.gov NaId 4719476) | Greppable passenger dataset; rich origin-town/ship fields; THIN subset | Free (download + grep) |
| **Stadsarchief Rotterdam HAL** (stadsarchief.rotterdam.nl/passagierslijsten) | Rotterdam DEPARTURE index, HAL ships 1900+ | Free (drive in Chrome) |
| **CEMLA** (search.cemla.com) | Buenos Aires arrivals 1882–1960 | Free (operator captcha) |
| FamilySearch | Multiple ports/countries; manifest + naturalization images | Free |
| **NYC DORIS Historical Vital Records** (a860-historicalvitalrecords.nyc.gov) | NYC birth/death/marriage CERTIFICATE IMAGES | Free (browser; operator downloads) |
| **Mount Hebron interment DB** (mounthebroncemetery.com/interments/) | NYC Jewish burials; Society = hometown | Free |
| **JewishGen** (jewishgen.org/databases/all/) | JRI-Poland, Bessarabia, JOWBR, JGFF, Gazetteer | Free account |
| **Gesher Galicia All-Galicia DB** (gesher-galicia.org) | Galician vital/cadastral records | Free / member |
| **Yad Vashem Shoah Names** (collections.yadvashem.org/en/names) | Holocaust victims; parents/spouse/birthplace | Free |
| Ancestry.com | Largest indexed manifest/naturalization collection | Subscription (operator) |
| USCIS Genealogy Program | Naturalization C-files, 1906–1956 | $65/request (operator) |

## Name Variation Strategies

When searching for an immigrant ancestor, try:
- Original-language spelling (search the European form, not the Americanized one)
- Phonetic variants (try every plausible transliteration of the surname)
- Hebrew/Yiddish given name (the secular name often differs from the religious given name)
- Shortened forms (Chas. for Charles, Wm. for William)
- Maiden name for married women (spouses often arrived separately under it)
- Patronymic / farm name (Scandinavian: Antonsen; Rasmusen)
- Both "old country" and Americanized versions

## Recording worked-line status

When a line has been worked end-to-end, record its post-work status in your research log — confirmed records, current walls, and untried free avenues — so future runs do not re-run exhausted negatives. Keep that per-line research status in your logs, not in this prompt.
