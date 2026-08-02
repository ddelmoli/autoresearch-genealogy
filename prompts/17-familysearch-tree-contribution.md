# FamilySearch Tree Contribution

Push every vault-confirmed person and relationship that is missing from the live FamilySearch tree (the subject, FS PID **[SUBJECT_PID]**, https://www.familysearch.org/en/tree/pedigree/landscape/[SUBJECT_PID]) up into FamilySearch, attaching at least one strong primary source per addition (more when available — see Guard's tiered source-minimum rule), then record the new FS PID back in the vault **and harvest that profile's FS-attached source ARKs back into the vault narrative entry** (Recipe-S, CLAUDE.md Rule 8). The objective is bidirectional: minimize the count of persons in `vault/Family_Tree*.md` who lack an FS PID, while only contributing additions that are source-backed and verifiable by other FamilySearch users — and, in the same visit, close the reverse gap by pulling each profile's existing source coverage down into the vault so `harvest_sources.py` SOURCE_GAP shrinks alongside the PID metric.

**Every PID recorded in the vault this prompt — whether duplicate-found (the common case) or newly created — gets a same-session Recipe-S source harvest (step 8.5).** This is the lesson of the 29 MAY 2026 runs: two back-to-back runs recorded 31 + 19 PIDs as PID-only write-backs, then separate manual follow-ups had to harvest several hundred source ARKs after the fact. Folding the harvest into step 8.5 makes the source review automatic rather than a deferred chore.

## Expected outcome distribution (read before running)

FamilySearch is a mature shared tree. **The dominant outcome of any iteration is "duplicate found — record the PID in vault."** A meta block with `fs: TBD` does NOT mean the person isn't on FS — it usually means the vault hasn't yet searched / recorded the PID. Across the first three Tier-2 setup-pass candidates, all three turned out to be already on FS, surfacing several vault PID drifts.

That's fine — it's what the protocol is for. The workflow's principal value is:

1. **Vault-PID gap-fill**: for each `fs: TBD` meta block, run step 4's duplicate check. When a match is found (the common case), apply the step-8 write-back to the vault. Zero FS-side mutations.
1a. **FS write-back queue drain (the other inbound worklist)**: entries carrying a `- **FS write-back QUEUED <date>** (<PID>; <action>): …` bullet, put there by `23-session-review` when a research session found something FS has wrong, missing or unattached and was not allowed to fix it. These are already-researched, already-evidenced actions waiting only on the operator, so they are usually the cheapest work in the run — and unlike `fs: TBD`, each one is a genuine FS-side MUTATION and therefore gated (step 7). A drained item's bullet is rewritten to its DONE form in step 8d, which is what removes it from the queue: the ledger is the grep, so a performed action that leaves its QUEUED bullet standing will be re-presented forever.
2. **Source-harvest-back (every PID, automatic)**: immediately after any PID write-back, run step 8.5 — read the profile's Sources tab, extract its FS-attached record ARKs, and write the vault's "FS-attached sources" bullet (Rule 8). Read-only on the FS side, so autonomous (no operator gate), exactly like the step-8 vault write-back. This is what moves the person out of `harvest_sources.py` SOURCE_GAP.
3. **Source-attach gap-fill (opportunistic, the other direction)**: if the existing FS profile is missing sources from the *vault* dossier, attach them to FS (after operator confirmation per the Guard rule below). Note the asymmetry: step 8.5 pulls FS→vault (read-only, automatic); step 7 ATTACH pushes vault→FS (mutation, operator-gated).
4. **New person creation (rare)**: only for candidates that genuinely don't exist on FS (Valerio-style: vault narrative explicitly says "FS: no PID known despite searching"). Most sessions will see zero of these. A freshly-created profile still gets a step-8.5 harvest — it will usually show just the 1 source you attached, confirming the round-trip.

The metric still drops on every iteration — whether via duplicate-found write-back or via genuine creation — so the autoresearch loop is still convergent.

## Tooling prerequisite (read first)

FamilySearch tree edits (add person, add relationship, attach source) cannot be performed via WebFetch or WebSearch. They require an interactive logged-in session. To run this prompt productively, use:

- **Claude in Chrome** at https://www.familysearch.org/ with the operator's FS account already signed in. Your working group tree lives at [FS_GROUP_TREE] and the subject pedigree at https://www.familysearch.org/en/tree/pedigree/landscape/[SUBJECT_PID].
- The vault's existing image-zoom workflow (see [[feedback_image_reading_workflow]]) when a source requires reading an Antenati / FS film register page to confirm a citation before attaching.

A run that uses ONLY WebSearch / WebFetch will produce a candidate list and a per-person source dossier, but it cannot execute the contribution itself. That partial run is still useful as a setup pass for a follow-up Chrome session.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[SUBJECT_PID]`: the starting person's FamilySearch PID (configure in your local project instructions). A vault anchored on a married couple has one per anchor
- `[FS_GROUP_TREE]`: URL of your FamilySearch group/family tree, if you use one (configure in your local project instructions)
- `[WORKLIST]` (optional, default `both`): which candidates this run drains — `tbd` (the `fs: TBD` gap-fill), `queue` (the FS write-back queue: entries carrying a `- **FS write-back QUEUED …**` bullet), or `both`. The queue is produced by `23-session-review`, which is forbidden to perform outward mutations; this prompt is where they get performed, with the operator present

Note: `<PID>` and `<PARENT_PID>` in the Protocol's write-up template are OUTPUT
fields, filled with the PID a contribution creates or anchors to, not inputs to
replace before a run.

## Autoresearch Configuration

**Goal**: For every person and direct-relationship edge present in `vault/Family_Tree*.md` but missing from the FamilySearch tree connected to subject `[SUBJECT_PID]`, when the tiered source-minimum holds for that person, (a) create the person on FamilySearch, (b) attach the sources, (c) wire the relationship to the appropriate existing FS profile, (d) write the FS PID back into the vault entry's `- meta:` block (`fs:` field) + header, and (e) harvest the profile's FS-attached record ARKs back into the vault "FS-attached sources" bullet (step 8.5, Recipe-S / Rule 8). When step 4 finds the person already on FS (the common case), skip (a)-(c) and still do (d)+(e). Log every contribution, every harvest, and every rejection.

**Metric**: Two terms, both minimized, reported separately (never summed — they measure different work): (a) person entries across `vault/Family_Tree*.md` whose `- meta:` block has `fs: TBD` (FamilySearch not yet searched / PID not yet recorded); (b) entries carrying an open `- **FS write-back QUEUED …**` bullet (an evidenced, operator-gated FS mutation waiting to be performed). Term (b) is the only metric in the toolkit that ONLY this prompt can move, because every other prompt is forbidden to mutate FamilySearch.

**Direction**: Minimize

**Verify**: `grep -rho 'fs: TBD' vault/Family_Tree*.md | wc -l` before and after each iteration. Log the delta. (Sentinels: `fs: TBD` = not yet searched = the worklist; `fs: none` = searched, no FS profile = done; a real `fs: XXXX-XXX` = done. The ~21 entries with no `fs` key at all are collaterals never scoped for FS — out of the worklist unless you promote one to `fs: TBD`.) Also report `grep -rohc 'fs: [A-Z0-9-]\{8\}' vault/Family_Tree*.md` totals as a cross-check. For term (b): `grep -ric "FS write-back QUEUED" vault/Family_Tree*.md` before and after (the emergent queue ledger — there is no queue file), with the DONE/DROPPED count rising by the same amount you drained: `grep -rihoE "FS write-?back (DONE|DROPPED)" vault/Family_Tree*.md | wc -l`. Match case-insensitively — the corpus carries historical spellings, and a case-sensitive count undercounted DONE by four the day the grammar was written. The SessionStart banner's `writeback ->` line reports all of this.

**Guard**:
- **Operator confirmation required for every FS mutation.** This prompt is human-in-the-loop. Add Person, Save Vitals, Attach Source, Complete Tags, Add Life Sketch, Add Note, Add Relationship — every one of these is a stop-and-ask gate. The autonomous portion of the workflow ends at step 7's "Stage the action plan in chat." Mutations are executed only after explicit operator approval ("yes", "proceed", or equivalent) for that specific action plan. Vault-side write-back (step 8) remains autonomous since it touches only local files and runs under the pre-commit hook (CLAUDE.md Rule 9). **The Recipe-S source harvest (step 8.5) is likewise autonomous: it only READS the FS Sources tab and writes local files — it attaches nothing to FS, so it is not a mutation and needs no operator gate.** (Contrast with step 7 ATTACH, which pushes sources vault→FS and IS gated.)
- **A QUEUED item is a CANDIDATE, and its evidence is re-checked before it is performed.** The queuing session did the research; it did not get to test the action against the live profile, which may have changed since. Re-open the profile, re-read the identifiers, and honour any prior not-a-match decision. If the queued action no longer applies, rewrite the bullet to say so (with the date and why) rather than deleting it silently — a queue item that evaporates without explanation is indistinguishable from one that was done.
- **The DONE bullet REPLACES the QUEUED bullet; they never both stand**, per CLAUDE.method.md rule 8. An entry states current state.
- **A queued item still passes every gate below.** The privacy gate especially: `23-session-review` is required to mark each item's `life_status`, but the mark is not the authority — `scripts/privacy_gate.py` is, and a public target denies `living` and `unknown` no matter what the bullet says.
- **Per-iteration cap**: up to **5 new persons or relationships** and up to **10 sources attached**. Stop the iteration at whichever limit hits first. This is a hard ceiling, not a target.
- **Source minimum (tiered by candidate strength)** — relaxed 26 MAY 2026 from prior flat 2-source rule after 6-of-6 Tier-2/Tier-3 iteration data showed the 2-source bar was indefinitely blocking primary-source-attested candidates from sparse-curation regions while FS itself routinely accepts 0-1 source profiles (FS routinely hosts profiles created from a single source, and 0-source placeholder profiles are common):
  - **Strong-Signal CREATE** (1 strong primary source suffices): a vault-Strong-Signal candidate may be CREATE'd with **1 strong primary source** when ALL of these hold: (a) the source is a primary record (Italian Stato Civile atto with ARK, FS-indexed record, FreeREG/Antenati permalink, parish-register transcription, or comparable verifiable primary attestation); (b) the source names the candidate, gives a date + place, and ideally names parents or spouse; (c) at least one parent OR spouse already has an FS PID (the anchor needed to wire the relationship); (d) step 4 duplicate-check returns no match (so this is a genuinely-not-on-FS candidate, not a duplicate-creation risk); (e) step 6 independence test still applies — if 2nd source is available, attach it; the relaxation lifts the BLOCK on 1-source candidates, not the preference for 2+ sources when feasible.
  - **Moderate-Signal CREATE** (2-source minimum still required): a vault-Moderate-Signal candidate retains the 2-source minimum, since the Moderate-tier identity-distinctness margin needs the cross-attestation to avoid duplicate-creation risk.
  - **Speculative-Signal**: blocked regardless of source count (per Confidence floor below).
  - **Vault-Strong, FS-Strong-curation regions**: prefer 2+ sources when available even for Strong-Signal candidates — densely-curated regions (e.g. well-covered Anglo-American areas) make 2nd-source acquisition cheap. The 1-source relaxation primarily unlocks sparse-curation regions where the 2nd source is months-to-years behind paid archive access.
- **No fabrication**: every claim in the FS person record (name, dates, places, parents) must trace to a source being attached. Do not transcribe vault facts that have no underlying citation. If the vault entry is uncited, fix the vault first or skip the person.
- **No duplicate creation**: before adding, search FS aggressively for the person under all known spelling variants. If a candidate FS profile already exists, do NOT create a second one; instead record the existing PID in the vault and (optionally, with operator confirmation) attach the missing sources to the existing profile. Duplicate-merging is out of scope for this prompt — flag duplicates in `vault/Open_Questions.md` for human review.
- **No edits to existing FS persons** beyond source attachment and relationship-add. Do not change names, dates, places, parent links, or vital events on profiles created by other contributors. If a vault fact contradicts an existing FS profile, log the conflict and skip.
- **Direct-line + close collateral only**: prioritize direct ancestors and their spouses/siblings/children. Do not contribute deep collateral pedigrees (in-law walk-ups, AAD enlistee clusters, ghost-surname collateral) in this prompt.
- **Confidence floor**: contribute only persons whose meta `evidence_tier` is `strong_signal` or `moderate_signal`. Skip `evidence_tier: speculative`, anything marked `(unverified)`, and entries with NO `evidence_tier` (unassessed = `profile_status: stub`). Promote candidates only after sources upgrade them.
- **Living persons (per-target gate, Spec 04)**: the write target is resolved from `.autoresearch.json` `repositories` (default: FamilySearch, a PUBLIC shared tree). This prompt targets FamilySearch, a **public** target, so it skips any person whose meta is `life_status: living` or `life_status: unknown` — only `life_status: deceased` persons are eligible, never a living or possibly-living person (110-year presumption seeds these; FS also enforces its own living-person policy). The rule is enforced in one place: `scripts/privacy_gate.py` `gate(vault, "fs", life_status)` returns DENY for living/unknown on a public target. (A **private** personal-tree target would allow living people, but this prompt does not target one; do not relax the skip here.)
- **Group-tree scope**: contributions should be visible from the your family group tree ([FS_GROUP_TREE]). Avoid adding persons under a branch that is not actually reachable from `[SUBJECT_PID]`.

**Iterations**: 10

**Protocol**:

1. **Baseline**: Compute BOTH metric terms across `vault/Family_Tree*.md` using the Verify commands — the `fs: TBD` count and the open `FS write-back QUEUED` count. Record the baseline plus per-generation breakdown (from each entry's meta `generation`) in `vault/logs/YYYY-MM-DD-fs-tree-contribution.md` (today's date).

2. **Build the candidate list**: Across every `vault/Family_Tree*.md` file, identify (a) person entries whose meta block has `fs: TBD`, and (b) unless `[WORKLIST]` says otherwise, entries carrying an open `- **FS write-back QUEUED …**` bullet. **Work (b) FIRST**: those items arrive pre-researched and pre-evidenced from `23-session-review`, they are the only work in the vault that nothing else can perform, and they are the reason the queue does not rot. For a (b) candidate, read the bullet's action, evidence locator and `life_status` mark, then go to step 4's duplicate check only if the action is a CREATE; an attach, a merge-review or a correction goes straight to the step-7 staging gate with the evidence the bullet names. The rest of this step describes (a). (These are produced upstream by the discovery prompts — `01-tree-expansion` adds the persons; `02-cross-reference-audit` + `05-source-citation-audit` verify and source them. This prompt is the downstream contribution stage — it does not discover net-new persons, it reconciles existing vault persons against the live FS tree.) For each candidate, capture:
   - Name with all variants documented in the vault (Italian/Polish/anglicized forms, maiden names, patronymics)
   - Birth date + place, death date + place, marriage date + place where known
   - Parents and spouse (with their FS PIDs if already on FS — these are the anchor points)
   - Vault confidence tier
   - Source citations already in the vault entry (count them; mark each as "FS-attachable" or "narrative-only")
   - Vault file path + line, for the post-contribution PID write-back

3. **Triage**: For each candidate, classify into:
   - **READY (Strong-tier 1-source path)**: vault confidence = **Strong (S)**, AND at least 1 strong primary-source FS-attachable citation in vault, AND at least one parent or spouse FS-anchored, AND step 4 returns no duplicate. Step 6 independence test relaxed to 1-source minimum per Guard rule. (Relaxed 26 MAY 2026.)
   - **READY (Moderate-tier 2-source path)**: vault confidence = **Moderate (M)**, AND 2+ FS-attachable sources cited in vault, AND at least one parent or spouse FS-anchored. Moderate-tier retains the 2-source minimum to manage duplicate-creation risk.
   - **NEEDS_ANCHOR**: source bar met but neither parent nor spouse has an FS PID yet. Defer until the anchor is contributed in an earlier iteration.
   - **NEEDS_SOURCES**: vault confidence = Moderate but fewer than 2 FS-attachable sources cited (Strong-tier should be READY at 1 source). Do not contribute; flag for the source-citation audit (prompt 05).
   - **BLOCKED**: confidence below Moderate, or vault entry contradicts an existing FS profile, or person is living. Skip and document why.
   Prioritize READY candidates by generation depth (lower generation number first — closest to subject) so each iteration's contributions become anchors for the next.

4. **Pre-add duplicate check (per candidate)**: Before creating a person on FamilySearch:
   a. From an anchor profile (parent or spouse), open the Family tab and scan for an existing child/sibling/spouse matching the candidate.
   b. Use FamilySearch Find (https://www.familysearch.org/search/tree/find) with name + birth year ± 2 + birthplace. Try every documented spelling variant.
   c. Use FamilySearch Full-Text Search (https://www.familysearch.org/search/full-text) with unquoted multi-keyword queries spanning name variants (per [[feedback_fs_fulltext_search]]).
   d. If a candidate FS profile is found and matches on ≥3 fields (name, birth ±2, birthplace, parent name, spouse name), STOP — do not add. Instead: record the discovered PID in the vault entry's meta block (`fs:` field) per step 8, then if missing sources can still be attached, proceed to step 7 against the existing profile. Note the reuse in the log.

5. **Source-attachment dossier (per candidate)**: For each candidate cleared by step 4, assemble the source dossier before any FS edit. Each source must be one of:
   - **Indexed FS record** (preferred): FS ARK URL of the form `ark:/61903/1:1:XXXX-XXXX` (index entry) or `ark:/61903/3:1:3Q9M-...` (image). Use the FS "Attach to Family Tree" flow.
   - **External record with a stable URL**: Find a Grave memorial ID, Antenati ARK, Geneteka entry, FreeBMD GRO citation, archive.org page-anchored link, etc. Attach via the "Memories" or "Sources" tab using the "Web Page" source-create flow with full citation text.
   - **Published genealogy / vital record book**: attach as a Source with title, author, publisher, year, page number, and a stable URL when one exists (Internet Archive identifier preferred).
   Reject any "source" that is a user-submitted tree (other FamilySearch trees, Ancestry / Geni / WikiTree profiles) without an underlying primary record. Two trees citing each other do not count as two sources.

6. **Independence test**: When counting toward the tiered source-minimum rule (Guard), two citations are independent only if they derive from different original records or different recording events. Two transcriptions of the same census household are ONE source. A baptism record + a death record + a census household = three sources. A FamilySearch indexed entry + the underlying register image of the same event = ONE source (record image attachment is preferred over the index-only entry when both exist). For the Strong-tier 1-source path, the single source must by itself be a strong primary record (not a transcription-of-transcription chain).

6.5. **Pre-attach source dedup check (per candidate)**: Before attaching any source from the dossier — whether the person was just created in step 7 or already exists per step 4 — open the candidate's Sources tab on FS and enumerate what is already attached. For each dossier source, check:
   - **Same FS ARK already attached**: skip the attach step entirely (it's a duplicate).
   - **Same external URL already attached as a Web Page source**: skip the attach step.
   - **Same published-genealogy title + page already attached**: skip the attach step.
   - **Partial-attachment (ARK is attached but event tags are incomplete)**: do NOT re-attach, but DO complete the tags in step 7e — add the missing event tags (Birth / Death / Marriage / Residence / etc.) that the source actually supports per the dossier.
   - **Different ARK for the same underlying record** (e.g., FS attached the index-entry ARK; dossier has the higher-quality image ARK): defer to human judgment. Note in the log; do not auto-replace. Image-ARK attachment is generally preferred but replacing an existing attach risks losing other contributors' work.
   Update the dossier in place: each source is now marked ATTACH (new), SKIP_DUPLICATE (already there), or COMPLETE_TAGS (already there but partial). The iteration's source-attachment cap (10/iter) counts only ATTACH actions, not SKIP_DUPLICATE.

7. **Stage the action plan, then execute per operator approval** (Claude in Chrome session, per candidate):

   Every FS mutation is a stop-and-ask gate per the Guard rule. The autonomous part of this step is preparation only.

   a. **Prepare** the planned FS actions in one of three modes:

      - **Mode CREATE** (rare: step 4 returned no duplicate). From the anchor profile (parent or spouse), identify the appropriate "Add" action (Add Child / Add Spouse / Add Parent / Add Sibling). State the exact Vitals to enter: name with diacritics, sex, birth date + place, death date + place, marriage date + place. Confirm the place-name picker will produce a standardized place ID. List the dossier sources to be attached after Save + their planned event tags.

      - **Mode ATTACH** (common: step 4 returned a duplicate). Per step 6.5, the dossier sources are classified ATTACH / SKIP_DUPLICATE / COMPLETE_TAGS. State which ARKs will be attached (with target event tags) and which tag-completions will be applied. Skip the SKIP_DUPLICATE list entirely. If 0 ATTACH and 0 COMPLETE_TAGS, this candidate is fully covered on FS — skip to step 8 (vault write-back) directly, no operator gate needed for source work.

      - **Mode METADATA** (optional, with either mode above). Plan any Life Sketch (1-3 sentences summarizing vault facts without speculation) and provenance Note ("Added/updated by your family project group tree [FS_GROUP_TREE] from vault entry [Family_Tree_Xxx.md], YYYY-MM-DD").

   b. **Present the action plan in chat** for operator review. Format:

      ```
      PROPOSED FS ACTIONS for [Name] (vault row Lxxx)
      Profile: [existing PID or "new — anchor to <PARENT_PID> via Add <Action>"]
      Mode: CREATE | ATTACH | CREATE+METADATA | ATTACH+METADATA
      Mutations planned (N total):
        1. [Action] — [exact field values / ARK URL / tag set]
        ...
      Awaiting confirmation. Reply "yes" to execute all, or "yes 1,3" for partial, or "no" / details to revise.
      ```

   c. **Wait for explicit operator approval in chat.** "yes", "proceed", "confirmed", or a partial-selection variant counts as approval. "no", "skip", a request for modification, or any non-approval response means do NOT execute. If approval is partial (e.g., "yes 1,3,5"), execute only the approved mutations.

   d. **Execute approved mutations one at a time**, in the order stated. After each, log the action + outcome (e.g., `Added person LLLL-LLL from anchor MMMM-MMM via Add Child; saved 14:23 UTC` or `Attached ARK 1:1:XXXX-XXX to NNNN-NNN with Birth tag`). If the operator approved in batch (a single "yes"), no further confirmation is needed for that batch; if any unexpected FS response occurs (validation error, system warning, indexing conflict), STOP the batch and report.

   e. **For ATTACH actions**:
      - FS-indexed records: use "Attach from Search Results" or paste the ARK and use "Attach a Source from FamilySearch".
      - External records: "Create a New Source", paste the URL, fill Citation, Title, Notes (transcription excerpt when relevant), and Where the Source is Found.

   f. **For tag-application** (both new ATTACH and COMPLETE_TAGS): click "Tag" and select the events the source supports. For COMPLETE_TAGS sources, only ADD the missing tags from the dossier; do not remove existing tags.

   g. **For Life Sketch / Note** (if planned): enter the prepared text and Save.

8. **Vault write-back** (immediately after each successful FS save):
   a. In the candidate's `- meta:` block, set the `fs:` field to the new PID (replacing `fs: TBD`). This is the machine-authoritative write — it is what drops the metric. The meta block is the single source of truth; there is no separate lookup index to update.
   b. Also place the PID in the bold-name header's parenthetical for human display, using the vault convention (`FS PID LLLL-LLL` or `FS: LLLL-LLL`) — the entry's OWN PID only, never a cross-reference PID (CLAUDE.md Rule 6; `header_xref_audit.py`).
   c. Stage these changes for the iteration's single commit. Do NOT commit per-candidate; commit per-iteration so the FS adds and vault updates land together. (This vault has no per-person files — everyone lives in the `Family_Tree*.md` narratives.)
   d. **If this candidate came from the FS write-back queue, REWRITE its bullet now**, in the canonical three-state grammar of `CLAUDE.method.md` rule 8 — replace `- **FS write-back QUEUED <date>** (…)` with either `- **FS write-back DONE <today>** (<PID>; <note>): <what was actually written>` or, when the action turned out not to apply (superseded, operator declined, already fixed by a contributor), `- **FS write-back DROPPED <today>** (<PID>): <why>`. This is what drains the queue: the ledger is a grep over those words, so a performed action whose QUEUED bullet survives is re-presented at every session start, and a deleted bullet vanishes from the count entirely. Never leave one looking pending; never delete one without a trace.

8.5. **Recipe-S source harvest** (immediately after step 8, for every PID recorded this iteration — duplicate-found OR newly created):

   This step is **read-only on the FamilySearch side** (it only reads the Sources tab; it attaches nothing), so like step 8 it is **autonomous — no operator gate**. It populates the vault's "FS-attached sources" bullet per CLAUDE.md Rule 8, which is what moves the person out of `harvest_sources.py` SOURCE_GAP. Skip it only when the profile is brand-new with exactly the sources you just attached in step 7 (those are already documented in the dossier write-up).

   a. **Navigate** (Claude in Chrome) to `https://www.familysearch.org/en/tree/person/sources/{PID}`.

   b. **Enable Detail View, then extract record locators FROM `href` ATTRIBUTES.** The record ARKs are NOT in the DOM until Detail View is on. ⚠ **Never regex `innerText` for locators** — a source's citation string embeds ARKs that belong to no attached source, so a text scrape returns GHOST locators (prompt 19 measured 3 in the text against 2 in the hrefs, 1 ghost). Walk each source row and read its links. Use a self-polling snippet, since the SPA renders the list after navigation:

      ```js
      (()=>{const s=ms=>new Promise(r=>setTimeout(r,ms));
        // Classify a link into (host, locator). Add hosts here as lines reach new archives.
        const CLASSIFY=u=>{let m;
          if((m=u.match(/ark:\/61903\/((?:1:1|3:1):[A-Z0-9-]+)/i)))   return ['fs',m[1]];
          if((m=u.match(/ark:\/12657\/([^\s"'<>?#]+)/i)))             return ['antenati','ark:/12657/'+m[1]];
          if((m=u.match(/ancestry\.[a-z.]+\/collections\/(\d+)\/records\/(\d+)/i)))
                                                                      return ['anc',m[1]+':'+m[2]];
          if((m=u.match(/discoveryui-content\/view\/(\d+):(\d+)/i))) return ['anc',m[2]+':'+m[1]];
          if((m=u.match(/[?&]dbid=(\d+)[\s\S]*?[?&]h=(\d+)/i)))      return ['anc',m[1]+':'+m[2]];
          if(/metryki\.genealodzy\.pl/i.test(u))                      return ['metryki',u];
          if(/szukajwarchiwach/i.test(u))                              return ['szukajwarchiwach',u];
          if(/agad\./i.test(u))                                       return ['agad',u];
          if(/discovery\.nationalarchives/i.test(u))                   return ['tna',u];
          return [null,u];};
        return(async()=>{
          let cb=null;for(let i=0;i<25;i++){cb=document.querySelector('input[name=detailView]');if(cb)break;await s(250);}
          if(cb&&!cb.checked)cb.click();await s(1200);
          const rows=[...document.querySelectorAll('div[class*=cssSourceBody]')];
          const hits={},skipped={};let noLink=0;
          for(const b of rows){const o=b.parentElement.parentElement;
            const hrefs=[...o.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(h=>h&&/^https?:/i.test(h));
            if(!hrefs.length){noLink++;continue;}
            let matched=false;
            for(const h of hrefs){const[host,loc]=CLASSIFY(h);
              if(host){(hits[host]=hits[host]||new Set()).add(loc);matched=true;}}
            if(!matched)for(const h of hrefs){try{const d=new URL(h,location.origin).hostname.replace(/^www\./,'');
              skipped[d]=(skipped[d]||0)+1;}catch(e){}}}
          const c=(document.body.innerText.match(/Sources\s*\((\d+)\)/)||[])[1]||'?';
          const loc={};for(const k in hits)loc[k]=[...hits[k]];
          return JSON.stringify({pid:location.pathname.split('/').pop(),sourceCount:c,
            sourceRows:rows.length, rowsWithNoLink:noLink,
            byHost:Object.fromEntries(Object.entries(loc).map(([k,v])=>[k,v.length])),
            locators:loc, UNRECOGNISED_HOSTS:skipped});})();})()
      ```

      - Batch up to ~5 profiles per `browser_batch` as `[navigate, js]` pairs; the self-poller tolerates the per-profile render delay. Do NOT fire navigations faster than the poller can keep up (a too-fast batch returns `sourceCount:"?"`/0 — re-run those).
      - **BOTH `1:1:` (indexed) and `3:1:` (image/browse) FS ARKs count** for Rule 8, and so do the non-FS hosts above. ⚠ **A previous version of this note claimed `3:1:` was NOT counted by `harvest_sources.py`. That was wrong** — the script has counted image ARKs since 02 JUN 2026, and a profile whose only locator is a `3:1:` is classified with 1 record, not 0 (verified on a live entry 01 AUG 2026). Do not skip them.
      - ⭐ **`UNRECOGNISED_HOSTS` IS THE POINT OF THE SHAPE, NOT A DEBUG FIELD.** It names every domain that appeared as a source link and matched no known host, with a count. Before this, a profile that was 60% Ancestry-attached harvested as a thin FS-only result **with no sign anything had been missed** — the silence was the defect (deferred_decisions 30). **If `UNRECOGNISED_HOSTS` is non-empty, say so in the bullet or the log**, and add the host to `CLASSIFY` if it is a real record host.
      - `rowsWithNoLink` counts sources carrying no link at all — book, journal and tree citations. A high number there is the honest signal that a profile is bibliographically rich and record-poor, which is exactly what `BOOK_SOURCED` describes.
      - **A record on two hosts is ONE record with TWO locators**, never two records — cite it on one sub-bullet (`… — fs:1:1:AAAA-AAA, anc:1234:56789`).
      - **VERIFIED LIVE 01 AUG 2026** against the very profile that raised deferred_decisions 30. It returns `sourceRows 10, rowsWithNoLink 1, byHost {fs:4}, UNRECOGNISED_HOSTS {search.ancestry.com:4, legacy.com:1}` — reconciling exactly with that item's hand count of *"10 attached sources, of which only 4 are FS ARKs"*. The Ancestry form in the wild is `search.ancestry.com/collections/<collection>/records/<record>`, which maps onto the vault's existing `anc:<collection>:<record>`. ⚠ Do NOT match "ancestry" loosely: FamilySearch serves a partner-access interstitial at `familysearch.org/en/access/ancestry/` that is not a record.
      - ⏭ **`legacy.com` is an OPEN host question, deliberately left unclassified.** Obituaries COUNT as records (policy (f), operator ruling 01 AUG 2026), but no `legacy` host id is registered, and inventing one here would put an uncoordinated host into the census. It surfaces in `UNRECOGNISED_HOSTS`, which is the correct behaviour — visible rather than silently dropped.

   c. **Write the "Sources" bullet** into the person's narrative entry (Rule 8 / Spec 03 record-locator format): one sub-bullet per RECORD, each with `host:locator` pairs (`fs:1:1:…` indexed, `fs:3:1:…` image; `anc:`/`wt:`/`antenati:` for other hosts). A record cited on several hosts lists several locators on one line.
      ```
      - **Sources** (Recipe-S harvest YYYY-MM-DD, N records):
        - 1910 US Census, Manhattan — fs:1:1:AAAA-AAA
        - 1847 birth atto — antenati:ark:/12657/an_…, fs:3:1:BBBB-CCCC-DDDD
      ```
      (The legacy flat `- **FS-attached sources**: 1:1:…` form is still parsed during the transition; `scripts/migrate_sources.py` converts it. Write new bullets in the `**Sources**` form.)
      - **Cap dense profiles**: if M is large (>~30, common for dense 19th-c profiles), list ~24 representative ARKs and note the true total: `… / 140 record ARKs total — densely covered by MA vital + census + town records; 24 representative listed): …`.
      - **Zero-record profiles**: `… , N FS sources / 0 indexed 1:1 record ARKs — attached sources are Web Page / book / society citations without FS record links`. (Common for Mayflower passengers, pre-1600 English gentry, and Italian profiles whose only attachments are Antenati image links.)

   d. **Placement**:
      - **Standalone bold-name entry** (the person has their own `**Name** (…, FS …)` header): add the bullet directly under the header.
      - **Inline collateral sub-mention** (the PID appears only inside a parent's children-list, with no standalone entry): add a labelled sub-bullet within the parent entry block, e.g. `- **FS-attached sources for a son** (their PID, inline collateral): …`. `harvest_sources.py` will attribute those ARKs to the parent block, which is acceptable; do NOT manufacture a new bold-name entry just to host the bullet (that is Task-D / NO_NARRATIVE territory).

   e. **Stage** the bullet edits into the same per-iteration commit as step 8. After the iteration, run `python3 scripts/harvest_sources.py` and record the SOURCE_GAP → WELL_SOURCED/LOW_COVERAGE delta in the log.

   f. **Session-drop caveat**: a long Chrome run can drop to the FS sign-in wall (`ident.familysearch.org/…/login`); the harvest then returns empty (`sourceCount:"?"`, 0 ARKs) on every profile. If that happens, STOP, tell the operator to re-authenticate in the browser, and resume after they confirm. Never attempt to sign in on the operator's behalf.

9. **Verify cross-references** (per iteration, before commit):
   - `grep -rc "<new PID>" vault/Family_Tree*.md` — confirm the PID appears in the expected file (both the `- meta:` `fs:` field and the header parenthetical).
   - `grep -E "fs: <new PID>|FS PID <new PID>|FS: <new PID>" vault/Family_Tree*.md` — confirm meta + header format consistency.
   - Re-run the Verify command and record the delta. The iteration's contribution count must equal the metric drop minus any duplicates discovered in step 4 (which also drop the metric without an FS add).

10. **Log the session**: Append to `vault/logs/YYYY-MM-DD-fs-tree-contribution.md`:
    - Per-iteration: baseline metric, persons added, PIDs assigned, sources attached (count + per-person breakdown), existing duplicates reused, candidates deferred (with reason: NEEDS_ANCHOR / NEEDS_SOURCES / BLOCKED).
    - **Source dispositions per person**: how many dossier sources were ATTACH (newly added), SKIP_DUPLICATE (already on profile), COMPLETE_TAGS (already attached but tag set extended). SKIP_DUPLICATE counts are evidence that the profile was well-curated before; COMPLETE_TAGS counts are easy wins.
    - **Recipe-S harvest tally (step 8.5)**: per PID, the FS source count and record-ARK count harvested into the vault (note any capped at 24 with the true total, and any 0-record profiles). End-of-iteration `harvest_sources.py` SOURCE_GAP → WELL_SOURCED/LOW_COVERAGE delta.
    - Source-attachment tally: indexed FS sources vs external sources vs published-genealogy sources.
    - Relationship edges added (parent-child, spouse, sibling).
    - Conflicts discovered (vault fact contradicts existing FS profile, candidate duplicate that needs merge review).
    - Any FS profile edits that hit the operator's contribution limit or triggered a system warning.
    - End with the post-iteration metric and one-line entry appended to `vault/Research_Log.md`.

11. **Handoff to the next iteration**: Promote NEEDS_ANCHOR candidates whose anchor was just contributed to READY. Re-triage. Stop the loop when one of:
    - The Verify metric stops decreasing for two consecutive iterations (READY queue is exhausted at current source coverage).
    - 10 iterations completed.
    - Operator stop.

## Tips

- **Duplicate-found is the expected outcome**: across the Tier-2 setup-pass , the first candidates all turned out to be already on FS. Most `fs: TBD` entries are case B (vault drift), not case A (genuinely not on FS). Treat step 4 as the primary value-creation step, not as a gate that "fails" when a duplicate is found.
- **Watch for the "PID loose in prose, not in the meta block / parenthetical" failure mode**: a vault narrative entry may already mention a PID (e.g., "REVISED from prior vault <PID>") only in body prose. When step 4's duplicate-check surfaces such a PID, the step 8 write-back must put it in the authoritative `fs:` meta field AND the bold-name parenthetical — the entry's own PID only (CLAUDE.md Rule 6; `header_xref_audit.py`).
- **Stage-and-confirm cadence**: keep the chat-side action plan compact (≤ 12 lines per candidate) so the operator can review at a glance. Group SKIP_DUPLICATE counts into a single line rather than listing each; itemize only ATTACH + COMPLETE_TAGS + CREATE actions.
- **Anchor outward from [SUBJECT_PID]**: every contribution should be reachable from the subject's pedigree within a small number of edges. The your family group tree ([FS_GROUP_TREE]) is the operational scope, not the entire FS tree.
- **Generation depth ordering matters**: contributing a Gen 7 ancestor with no Gen 8 parents on FS is fine, but contributing Gen 8 first with no Gen 7 anchor leaves orphaned profiles. Work shallowest-first.
- **Italian / Polish ancestors**: spelling-variant duplicate hunting is critical. Italian profiles may exist under anglicized name variants; Polish ones under phonetic variants. Run a Recipe-A-style multi-variant Full-Text Search before adding.
- **Source provenance over source count**: two strong primary-source attachments (a baptism atto image + a death certificate image) are vastly more valuable than five derivative index hits. Prefer image attachments when available.
- **Place-name standardization**: use FS's place-name picker so the standardized place ID attaches; otherwise the profile appears as "unstandardized" and is harder for other users to find. For non-English places, use the picker's standardized form (e.g. "Town, Province, Region, Country") — confirm against the relevant Family Tree shard before saving.
- **Living-person policy**: FS hides any person born within the last 110 years without a death record. The system will block direct linking to a "living" profile created by another user. If a vault person fits this window, contribute the death citation first or defer.
- **Relationship edges count toward the metric too**: adding an existing-on-FS sibling as a child of a vault-known parent (when the parent-child edge is missing) is a valid contribution. Count edges separately from new persons in the iteration log.
- **Stop short if Chrome MCP is unavailable**: a setup-only run that produces the READY candidate list + per-person source dossier is still valuable. Save it as `vault/logs/YYYY-MM-DD-fs-tree-contribution-setup.md` and hand off to a follow-up Chrome session.
- **Reverse-Recipe-0 opportunity**: the Polish Extension Plan flagged a "P0.5" task — attach vault's existing primary-source ARKs prior vault primary-source reads) to the corresponding FS profiles. That work falls naturally inside this prompt's step 7d when those profiles come up.
- **Coordinate with Open_Questions**: when step 4 finds a duplicate FS profile or step 7 reveals a vault-FS contradiction, file it in `vault/Open_Questions.md` rather than silently resolving. Merging duplicates and reconciling conflicts are separate prompts.
- **Harvest while you're already on the profile (step 8.5)**: you opened the profile in step 4 to check for a duplicate; harvest its sources in the same visit rather than queuing a separate Recipe-S round later. The 29 MAY 2026 data showed yields vary wildly by region — 19th-c MA residents 30-140 record ARKs, colonial-era MA 7-35, sparse-curation regions 0-13, Mayflower passengers / English gentry often source-rich but 0-few *indexed* records (book/society citations). Expect-and-document the zeros; a "0 indexed records" bullet is a valid harvest result, not a failure.
- **Don't dump 100+ ARKs into the vault**: cap inline lists at ~24 representative record ARKs for very dense profiles and state the true total. The full list lives on the FS profile; the vault bullet documents coverage and moves the person to WELL_SOURCED, it is not a mirror of FS.
