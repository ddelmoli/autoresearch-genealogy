# Creative Whole-Vault Enhancement & Extension Review

Apply a rotating battery of *interpretive* analytical lenses across the whole vault to surface non-obvious ways to **enhance** existing records (deepen a person, correct a fact, add a source) and **extend** the tree (recover a new ancestor, collateral, or origin) that brute-force record scans miss. This is the "read the pattern, not the record" prompt: patronymics, naming chains, toponymy, migration clusters, and kinship networks each carry information that a single-record search never queries.

> **Sharded trees (optional):** if your `Family_Tree.md` has been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as covering all shard files: read them all, and route any new person to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[SURNAME]`: a family surname to run a lens against (e.g., the surname whose patronymic or toponymic pattern you are analyzing)
- `[ANCESTOR]`: a specific ancestor's full name, when a lens targets one person
- `[LOCATION]`: a place name (town, parish, region, or country of origin) relevant to the lens
- `[CEMETERY]`: a cemetery or burial ground relevant to the burial-cluster lens
- `[DATE]`: a date or year relevant to a chronological-lens inference
- `[LENS]`: which analytical lens this iteration runs (onomastic / toponymic / migration-chain / kinship-network / chronological / convergence / occupational)

## Autoresearch Configuration

**Goal**: For every direct-line ancestor and every significant collateral in `Family_Tree.md`, run the person (and their family cluster) through the battery of creative analytical lenses in the Protocol. For each lens hit, log an **enhancement** or **extension** lead — a concrete, verifiable next action with a confidence tier — into `[VAULT_PATH]/creative_review_leads.md`. The deliverable is the ranked lead log; the point is to convert *patterns already latent in the vault* into actionable research.

**Metric**: Number of direct-line + significant-collateral person entries **not yet passed through the full lens battery** (the review backlog).

**Direction**: Minimize (toward full lens coverage of the vault). Secondary (report, do not optimize): count of OPEN actionable leads generated.

**Verify**: `grep -c "REVIEWED:" [VAULT_PATH]/creative_review_leads.md` against the direct-line + significant-collateral roster size (from `scripts/gen_person_index.py --write` if available, else a manual count). Also report the count of leads by tier: `grep -cE "Confidence: (Strong|Moderate)" [VAULT_PATH]/creative_review_leads.md`.

**Guard**:
- **Every logged lead MUST carry a concrete, verifiable NEXT ACTION** (a specific record to pull, a specific search to run, a specific person/date to confirm) — not a vague "investigate further." A lead with no next action does not count and is not logged.
- **Tier every lead** Strong Signal / Moderate Signal / Speculative. **Speculative leads are logged but flagged and never acted on autonomously** — they are queued for human review. Do not inflate the count with speculation; a lens hit with no plausible action is a negative result (log it as "lens run, no lead").
- **This prompt GENERATES leads; it does not adopt facts.** Do not write a derived name/date/place into a person entry from a lens inference alone. A lens says "a record probably exists / a person probably existed" — the *record* must still be found and cited before any vault person-entry changes (that is a downstream prompt: 01-tree-expansion, 05-source-citation-audit, etc.).
- **Living-person privacy**: do not run lenses that would surface or publish private data (exact DOB, address, contact details) for living or possibly-living people; skip `life_status: living`/`unknown` for any web-facing action.
- **Confidence floor for extension**: propose a NEW ancestor/collateral only from a Strong or Moderate lens inference with a named next-record to confirm. A surname/place coincidence alone is Speculative.
- Respect the vault's existing negative-results log: before proposing a lead, grep `[VAULT_PATH]/logs/` and `Open_Questions.md` so you do not re-propose a documented dead-end.

**Iterations**: 10

**Protocol**:

Work the vault **one family cluster at a time** (a direct ancestor + their spouse, parents, and children). For each cluster, run every lens below that applies, then mark the cluster `REVIEWED:` in the lead log. Rotate `[LENS]` focus across iterations so the whole battery gets exercised.

1. **Onomastic / naming-pattern lens** — the vault's proven highest-yield creative lens.
   - **Patronymics**: parse patronymic constructions in names/records (e.g., Italian "*[given] in [father's-given]*" or "*fu [father]*"; Hebrew "*[given] bar/ben [father]*"; Slavic "*-owicz/-ewicz*"; Scandinavian "*-son/-dotter*"; Welsh "*ap/verch*"). A patronymic **names the previous generation for free** → an EXTEND lead (a candidate father's given name to confirm against a register).
   - **Namesake chains**: a child named for a grandparent (common in many cultures on a fixed rotation — e.g., first son = paternal grandfather) **recovers the grandparent's given name** → EXTEND. A child suddenly named after a same-family adult often means that adult **just died** (naming-after-death) → a death-date ENHANCE lead. A "second son of the name" implies the **first died in infancy** → a missing-infant EXTEND lead.
   - **Given-name recurrence & disappearance**: track the family's given-name pool; a name that recurs every generation then vanishes flags a line change or a break to investigate.
   - Worked shape: "`[ANCESTOR]`'s declarant name renders '`[given] in [father]`' → father's given name = `[X]`; NEXT: search `[LOCATION]` `[DATE-window]` register for a `[given=X] [SURNAME]` whose child is `[ANCESTOR]`. Confidence: Moderate."

2. **Toponymic / regional-history lens.**
   - **Surname etymology → origin place**: toponymic and locative surnames encode a place of origin; occupational/descriptive surnames encode social context. Derive a candidate origin `[LOCATION]` and name the archive that holds its registers.
   - **Community/society anchors**: landsmanshaftn, mutual-aid societies, parish/guild affiliations named in records **pin an origin town** even when no birth record survives → EXTEND the origin + name the town's archive/diaspora database. (When the affiliation is named on a *grave or in a cemetery/interment record*, work it under the Cemetery / burial-cluster lens below — that is where the physical source lives.)
   - **Regional record-availability map**: for each origin region, state which record classes exist, are digitized, are archive-only, or are destroyed — so downstream prompts target the *reachable* record, not a lost one. This converts "origin = country" into "origin = town + a named next repository."

3. **Migration-chain lens.**
   - Cluster immigrants of the same surname/town by arrival window and "joining-relative" links (manifest "nearest relative," naturalization witnesses, shared US addresses). A chain reveals **siblings/cousins who emigrated together** → EXTEND collateral, and the *first* arrival often names the old-country family left behind.
   - Ship/port/date patterns across a surname flag an undiscovered family member on the same or adjacent voyage.

4. **Kinship-network / witness lens.**
   - Witnesses, sponsors, godparents, declarants, and bondsmen at an ancestor's events are **disproportionately kin**. Extract the recurring names around a family; a witness who appears at several of one family's events is a candidate close relative → EXTEND lead (identify the relationship).
   - Census/tax neighbor-clusters and shared households flag extended-family co-residence to map.

5. **Chronological / demographic lens.**
   - **Age-gap anomalies**: a >3-year gap between successive children implies a **missing (often infant-death) child** → EXTEND lead to search the gap year. A first child born suspiciously long after a marriage flags a missing earlier marriage or lost children.
   - **Remarriage inference**: a wife's name that changes between children, or a large second-cluster of children, implies a **prior spouse who died** → ENHANCE (a death) + EXTEND (a first-marriage record).
   - **Declarant-age arithmetic**: reconcile ages stated across records to bound birth years and flag the outliers that a single record hid.

6. **Cross-lineage convergence lens.**
   - Scan for the **same surname or origin place appearing in two different branches** of the vault. Endogamy and cousin-marriage were common in small communities → a convergence is a candidate **shared ancestor** that ties two lines together (a high-value EXTEND). Shared witnesses across two families is the same signal.

7. **Occupational / social-status lens.**
   - Occupation and social class predict **which record classes exist** (a landowner → deeds/probate; a guild member → guild rolls; a soldier → muster/pension; a merchant → port/business records). Convert a known occupation into a targeted record-type lead for a person who currently lacks sources.

8. **Cemetery / burial-cluster lens** — a grave is a dense, under-read record; the stone AND its neighbors AND the interment record each carry a different signal.
   - **Society / affiliation on the stone or interment record**: a burial society, landsmanshaft, congregation, lodge, or guild named at the grave **pins the origin town / community** even when no birth record survives → EXTEND the origin + name the town's archive or diaspora database.
   - **Plot-adjacency → kinship**: who lies *next to* the ancestor is disproportionately family. A same-surname adult in the adjacent plot is a candidate sibling/parent; a same-plot spouse confirms a couple; a grave filled **out of chronological sequence** (a later death in an earlier-numbered plot) signals a **reserved family allotment** → EXTEND collateral (identify the relationship, then confirm with a record).
   - **Inscription → prior generation**: a Hebrew *matzeva* names the deceased's **father** ("*[given] ben/bat [father]*") = a **patronymic that recovers the previous generation's given name** + often the exact town; other traditions' stones carry maiden names, "wife of", "native of [place]", or a birthplace → EXTEND / origin.
   - **Stone vitals → ENHANCE / correct**: the carved name, age, and dates refine or CORRECT a vault vital (a cemetery age that conflicts with census-derived age flags a same-name mix-up to resolve, not an error to average).
   - **The negative is a result**: if **independent gravestone-photo indexes** (Find a Grave, BillionGraves, Gravestone Photographic Resource, plus the cemetery office) all show **no surviving stone**, log it — the family used perishable markers or the stones are lost; stop re-scanning and pivot to register/probate/vital records instead.
   - **Cross-check multiple databases**: a person may be indexed in one gravestone DB and not another; the cemetery-office record (or a paid photo) may list the father's / Hebrew name that the public thumbnail omits → a queued lead, not a fact.
   - Worked shape: "`[ANCESTOR]` interred `[CEMETERY]`, society '`[society]`' → origin `[LOCATION]`; grave adjacent to a same-surname `[X]` filled out-of-sequence → probable sibling; NEXT: read the matzeva / order the cemetery-office record for the father's given name (Gen-back). Confidence: Moderate."

9. **Log every result.** For each cluster + lens, append to `[VAULT_PATH]/creative_review_leads.md`:
   - `REVIEWED: [cluster] — [lenses run]`
   - Per lead: **Type** (ENHANCE / EXTEND) · **Lens** · **Target** (person/place/date) · **Inference** (the pattern you read) · **NEXT ACTION** (the specific record/search) · **Confidence** (Strong/Moderate/Speculative) · **Downstream prompt** (which numbered prompt would execute it).
   - A lens that fires no lead: log `— [lens]: run, no lead` (a valuable negative — it means the pattern was checked).

10. **Rank & hand off.** At the end of each iteration, sort new leads by (Confidence tier) then (payoff: extends a direct line > deepens a direct ancestor > collateral). Promote the top Strong/Moderate leads into `Open_Questions.md` or the relevant `*_Extension_Plan.md` so a downstream research prompt can execute them. Speculative leads stay in the review log for human review.

11. **Coverage & stop.** Update the metric (un-reviewed entries remaining). Stop when: the whole direct-line + significant-collateral roster has been through the battery, or 10 iterations complete, or the operator stops. Re-running later with a fresh record base (new sources arrived) is expected — a lens that fired "no lead" before may fire once new data lands.

## Tips

- **The vault's own history is the proof of concept**: the highest-yield past finds came from exactly these lenses — a patronymic rendering recovered a father's given name; a burial-society name pinned an origin town no birth record could; a namesake child dated a death; a declarant/witness turned out to be a sibling. This prompt systematizes that instinct across the *whole* vault instead of one lucky entry.
- **Lenses compound**: a patronymic (onomastic) + a society name (toponymic) + a manifest relative (migration) pointing at the same person is a Strong lead even when each alone is Moderate. Note when lenses corroborate.
- **Culture-specific defaults matter**: naming rotations, patronymic grammar, and record survival differ by region — apply the convention of the ancestor's *own* culture, not a generic one. (An Italian first-son-named-for-paternal-grandfather rule ≠ an Ashkenazi name-for-the-recently-deceased rule.)
- **A grave is three records at once** — the stone (vitals + inscription + affiliation), its neighbors (kinship via plot-adjacency and reserved allotments), and the interment-office record (often the father's/Hebrew name the public photo omits). Read all three before calling a cemetery "checked," and cross the independent photo databases; a "no stone found" across all of them is itself a filed result that redirects the search to registers.
- **A negative lens result is data**, not a failure — logging "checked the naming pattern, nothing" prevents a future session from re-deriving the same dead-end and tells you the pattern is genuinely silent.
- **Keep the lead log skimmable**: one line per lead with the six fields; the prose reasoning lives in the linked person entry or Open_Question, not the log.
- This prompt **feeds** the doing-prompts (01-tree-expansion, 05-source-citation-audit, 08-open-question-resolution, 10/11 record searches, 17 FS contribution); it is the *ideation* front-end that decides *what is worth searching for next*.
