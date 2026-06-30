# Onomastic Origins (surname → toponym → which archive holds the records)

A repeatable method for building an **"Origins and Toponymy"** section for a surname lineage once the *primary-record* seam is exhausted and the remaining free leads are published history, onomastics, surname-distribution tooling, and archive-provenance lookups. It produces contextual analysis graded Strong / Moderate / Speculative **and**, as a side effect, tells you *which archive actually holds the named records* — so you stop chasing dead-end foreign archives and either find a digitized finding aid or draft a precise consultation request.

## When to run this workflow

Run it for a place/surname lineage when:

1. **The free primary-record seam is worked.** Parish and civil registers for the wall era are exhausted, paid, or available in person only (deep walls often bottom out at pre-civil-registration parish books, in-person tax rolls, or diocesan archives).
2. **You already hold a documented surname cluster** in one place, so etymology and distribution have an anchor to corroborate against.
3. **You want either** (a) defensible contextual depth (etymology, regional history, the local naming system), **or** (b) to locate the archive that holds the named records and decide between a free finding aid and a paid or in-person request.

Skip when the primary seam still has free, un-worked records (run those first), or when an Origins section already exists for that line (extend it, don't duplicate).

## The five steps

### Step 1 — Surname etymology and toponym
Establish what the surname *means* and whether it encodes a place. Classify the naming **system**: toponymic, patronymic, occupational, nickname (soprannome / byname), gentry/territorial, or co-surname. Cross-check your own cluster: do the collateral surnames map to the same village's quarters and hamlets (toponymic), or to patronymics and nicknames? Tools: regional etymology dictionaries; the hamlet/contrada/townland list of the home place; published local history.

### Step 2 — Regional and political history → which sovereign actually held the records
Trace which state governed the place across the relevant centuries, because **that decides which archive holds the records** and prevents chasing dead-end foreign archives. Watch for the common trap where a territory was politically subject to one power but kept its records with the local or original administration — in that situation the records stay where they were created, and the records of the controlling power are a dead end. Output: a sovereign-by-era timeline ending in "→ records held at [archive]".

### Step 3 — Surname-distribution mapping, with the spelling-split check
Map the surname's modern geographic distribution to confirm a single localized origin, or to reveal multiple unrelated stocks of the same name. **Always map the native spelling separately from the emigrant spelling** — they routinely split (a space added or dropped, a consonant simplified, a diacritic lost on emigration), and a native and an anglicized form can resolve to entirely different regions. Tools:
- **cognomix.it** — Italy, region and comune level (distribution data is in the page text; read it in a browser, not a plain fetch)
- **nazwiska-polskie.pl** — Poland, locality level (JavaScript-rendered; needs a browser)
- **forebears.io** — global and Great Britain
- **GB1881 surname atlas** and UCL's **FaNUK** (Family Names of the United Kingdom) — British lines

### Step 4 — Archive-provenance check → which archive holds the NAMED records, and its digitization status
Find the specific archive, fonds, and unit that holds the records, and whether a finding aid or images are online. Tools:
- **Italy**: Lombardia Beni Culturali (search the *complesso archivistico* and *conservatore/sede* fields), SIUSA (the unified archival-superintendency information system), and provincial state-archive finding aids
- **Poland**: szukajwarchiwach, the AGAD/regional state-archive inventories, and metryki.genealodzy.pl
- **United Kingdom**: TNA Discovery, county record-office catalogues, and family-history-society parish-register guides

Output: archive + fonds + unit numbers + "free finding aid online? / images online? / in-person only?".

### Step 5 — Draft a consultation request (only if documents are in-person or paid)
If Step 4 lands on in-person or paid-reproduction documents, draft a concise consultation message naming the exact fonds and unit and the specific question (which named holders, which date span). Record the full text and the on-reply next steps. Sending it is a manual step for the researcher, not an autonomous action.

## Confidence and scope discipline

- Label every claim Strong / Moderate / Speculative, exactly as for primary-record work. Onomastic reasoning is corroboration, **not** a primary-source substitute — it can establish *that a surname is toponymic and indigenous to a place*, never *that person X descends from holder Y* without a record.
- Place the result in the line's main family-tree file as a `## Origins and Toponymy: ...` section, with a "Researched [date] (web and regional-history pass; no new primary record)" disclaimer and a Sources list at the end.
- Do **not** add person entries or identifiers from onomastic analysis — no individuals are identified by it. If you do name a specific dated individual in an Origins section, it must match that person's canonical entry elsewhere in the vault.

## Tool notes

- Some historical-gazetteer sites (for example, scanned 19th-century geographical dictionaries) return intermittent HTTP 500s — retry; they often carry per-village notes on noble, civil, and church status that bear directly on a gentry-vs-commoner question.
- Surname-distribution sites are frequently JavaScript-rendered (cognomix.it serves its data as page text; nazwiska-polskie.pl renders client-side) — read them in a real or scriptable browser, not a plain HTTP fetch.
- A plain fetch is fine for static history pages (encyclopedias, county-history sites) but fails on JavaScript-gated distribution sites and on some government and archive viewers (HTTP 403) — fall back to a browser for those.

## Applying the method to Anglo lines

The method works the same for British and colonial American surnames, which have unusually rich *free* tooling: forebears.io, the GB1881 surname atlas, UCL's FaNUK, the Guild of One-Name Studies, and the English Place-Name Society. For Scottish names, George F. Black's *The Surnames of Scotland* is the standard reference and resolves many multi-origin names that the lighter secondary sources leave open. As with the continental lines, treat the result as contextual corroboration and keep it clearly separated from primary-record claims.
