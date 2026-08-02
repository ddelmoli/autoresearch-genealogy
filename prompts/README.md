# Prompts

Autoresearch prompts for AI-assisted genealogy research. Designed for Claude Code's `/autoresearch` command but adaptable to any AI tool that supports autonomous iteration.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in these prompts as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## How to Use

1. Open Claude Code in your genealogy vault directory
2. Type `/autoresearch` and paste the contents of a prompt file
3. Replace all `[PLACEHOLDER]` values with your actual data
4. The AI will run autonomously for the specified number of iterations

## Prompt Anatomy

Every numbered prompt begins with `Inputs To Replace`, then contains these autoresearch fields:

| Field | Purpose |
|---|---|
| **Inputs To Replace** | The placeholders a user must fill before running |
| **Goal** | What the prompt is trying to accomplish |
| **Metric** | A measurable quantity that tracks progress |
| **Direction** | Whether to maximize or minimize the metric |
| **Verify** | A command or check that measures current state |
| **Guard** | What the prompt should NOT do (safety rails) |
| **Iterations** | How many autonomous loops to run |
| **Protocol** | Step-by-step instructions for each iteration |

## Which Prompt to Use When

If you are unsure, use [Prompt Picker](../guides/prompt-picker.md). It routes you through setup, privacy, verification, and bundle choices before you run a numbered prompt.

**Starting from scratch?**
Do not start with tree expansion. Use [Download And Start](../guides/download-and-start.md), [First Week Checklist](../checklists/first-week-checklist.md), and [Prompt Picker](../guides/prompt-picker.md). Run verification or citation review before expansion.

**Already have a populated tree?**
Run `02-cross-reference-audit` to find and fix discrepancies between your tree file and your source documents.

**Have deceased ancestors without memorial links?**
Run `03-findagrave-sweep` to locate Find a Grave memorials and extract data from them.

**Want to export your tree?**
Run `04-gedcom-completeness` to build or verify a GEDCOM file that matches your vault.

**Want to focus tree expansion on a subset of lines?**
Run `01-tree-expansion` with its optional `[SCOPE]` input set to the shard files / Region you want to focus on (e.g. one branch), rather than the whole tree.

**Want to add primary-source military service citations?**
Run `16-aad-military-sweep` to check NARA's Access to Archival Databases (https://aad.archives.gov/aad/) for every US-resident ancestor of military age during WWII, Korea, Vietnam, or later conflicts.

**Want to push vault-confirmed people up into the FamilySearch tree?**
Run `17-familysearch-tree-contribution` to contribute new persons and relationships from `Family_Tree*.md` into FamilySearch (anchored at subject [SUBJECT_PID]), attaching primary sources per the tiered source-minimum and writing the new FS PID back to the vault's `- meta:` block. Capped at 5 persons / 10 sources per iteration. Requires a logged-in Claude in Chrome FamilySearch session.

**Want to pull the sources already on your ancestors' FamilySearch profiles down into the vault?**
Run `19-fs-source-harvest` to harvest each FS-PID-bearing entry's FS-attached primary-source ARKs (census, vital, immigration, register images, external archive links) into its `**FS-attached sources**` bullet, raising independent-source coverage on entries that cite few or no records. Read-only on FamilySearch (no operator gate); the FS→vault direction of "Recipe-S". Requires a logged-in Claude in Chrome FamilySearch session. This is the standalone coverage pass; prompt 17 folds the same harvest in as its step 8.5 when contributing.

**Want to reconcile your tree's relationships against FamilySearch?**
Run `18-edge-verification` to walk every unverified (`?`-marked) parent/spouse edge in `Family_Tree*.md` against the FS tree and resolve it — confirm, contradict, or record why it cannot be confirmed. Pairs with `scripts/build_edges.py` (seeds edges) and `scripts/verify_edges.py` (writes the result).

**Want a fresh look at a tree you think you have already worked?**
Run `25-person-research-sweep` to research ONE person across EVERY available resource -- FamilySearch (Sources, Research Help hints, and the discussions tab), Ancestry, WikiTree and what it CITES, the region's own archive, newspapers/obituaries and library surfaces -- then write the result into the entry as a cited BIOGRAPHY rather than a locator dump. This is the default unit of research work and what `22-research-iterations` dispatches to for IMPROVE; `19-fs-source-harvest` is now just its FamilySearch leg. FamilySearch is the place this vault SYNCS with, not its evidence base.

Run `20-creative-vault-review` to pass every direct-line ancestor and significant collateral through a rotating battery of interpretive lenses, logging each hit as an enhancement (deepen, correct, source) or an extension (a new person or line to chase).

**Running routine research sessions on a vault with the mechanized session loop?**
A session is FOUR phase prompts, run in order, and only phase 2 is a loop:

| Phase | Prompt | What it does | Loop? |
|---|---|---|---|
| 1. Initialize | `21-session-start` | banner + gate state vs baseline, vault confirmed, session number, Handoff read, housekeeping and deferred decisions surfaced, rename suggested | no |
| 2. Research | `22-research-iterations` | **`Iterations: N`** lane draws; each draws a lane, works it to the Lane target, and records its own outcome | **yes** |
| 3. Review | `23-session-review` | reconcile the sitting against the tools, re-measure every lane metric, gates vs baseline, assemble the FS write-back queue | no |
| 4. Close | `24-session-close` | `scripts/session_close.py` checklist -> Handoff close block -> next session's draw and starting command -> commit | no |

These are dispatchers, not campaigns: the numbered prompts above are what a lane dispatches TO (e.g. an IMPROVE defect row -> prompt 18, a harvest target -> prompt 25, whose FamilySearch leg is prompt 19).

## Overriding A Field For One Run

Every field in `## Autoresearch Configuration` is a default, not a fixed value.
To change one for a single run, **name the field and give it a value**:

```
run 19-fs-source-harvest with Iterations=12
run 01-tree-expansion with Iterations=5, Scope=Family_Tree_<Region>.md
```

`Field=value` is unambiguous, and a bare count ("run 19 with 12 iterations")
reads the same way. **`Iterations` always means the same thing: how many times to
run the prompt's main loop.** What one loop *is* differs by prompt:

| Prompt | One iteration = |
|---|---|
| 01-20 | one pass of the Protocol over the worklist |
| **22-research-iterations** | one **lane draw**: draw a lane -> work it -> record the outcome |
| 21, 23, 24 | nothing — these are session PHASES, not loops. Raising `Iterations` on one of them is meaningless (a session is initialized, reviewed and closed once); the dial you want is 22 |

**22 takes a second, independent dial, and it is a PERCENT OF THE VAULT, counted
in PEOPLE** — the same metric as the profile-review sample rate, so one number
describes a session's workload whatever lane is drawn. `Iterations` says how many
lanes you draw; the **Lane target** says how deep to go in each. They compose:

```
run 22-research-iterations with Iterations=10              # 10 draw/work/record cycles
run 22-research-iterations with Iterations=3, Lane pct=3   # 3 lanes, 3% of the vault deep each
```

`session_plan.py` prints the resolved number so you never do the arithmetic:
`LANE TARGET: 20 people this ITERATION — 1.5% of 1,352 (sample_percent)`, followed
by what one unit means in the drawn lane. It defaults to
`profile_review.sample_percent`; pin it separately as
`session_plan.lane_target_percent` once the two diverge in cost.

⚠ **Some things are per-SITTING, not per-iteration**, however large `Iterations`
is: the profile-review slice runs **once** (sized by `sample_percent`), and you
write **one** Research_Log row and **one** Handoff close block. Phase 2 records
each cycle with `session_plan.py --record`, so phase 4 runs `session_close.py`
*without* `--lane/--outcome`; passing them there would count one cycle twice.

## Human Review Cards

Every prompt has a matching review card. Read the card after the prompt finishes and before accepting changes.

| Prompt | Review card |
|---|---|
| 01 Tree Expansion | [review-cards/01-tree-expansion.md](../review-cards/01-tree-expansion.md) |
| 02 Cross-Reference Audit | [review-cards/02-cross-reference-audit.md](../review-cards/02-cross-reference-audit.md) |
| 03 Find a Grave Sweep | [review-cards/03-findagrave-sweep.md](../review-cards/03-findagrave-sweep.md) |
| 04 GEDCOM Completeness | [review-cards/04-gedcom-completeness.md](../review-cards/04-gedcom-completeness.md) |
| 05 Source Citation Audit | [review-cards/05-source-citation-audit.md](../review-cards/05-source-citation-audit.md) |
| 06 Unresolved Persons | [review-cards/06-unresolved-persons.md](../review-cards/06-unresolved-persons.md) |
| 07 Timeline Gap Analysis | [review-cards/07-timeline-gap-analysis.md](../review-cards/07-timeline-gap-analysis.md) |
| 08 Open Question Resolution | [review-cards/08-open-question-resolution.md](../review-cards/08-open-question-resolution.md) |
| 09 Local History Extraction | [review-cards/09-bygdebok-extraction.md](../review-cards/09-bygdebok-extraction.md) |
| 10 Colonial Records Search | [review-cards/10-colonial-records-search.md](../review-cards/10-colonial-records-search.md) |
| 11 Immigration Search | [review-cards/11-immigration-search.md](../review-cards/11-immigration-search.md) |
| 12 DNA Chromosome Analysis | [review-cards/12-dna-chromosome-analysis.md](../review-cards/12-dna-chromosome-analysis.md) |
| 13 Image Archive Deep Dive | [review-cards/13-image-archive-deep-dive.md](../review-cards/13-image-archive-deep-dive.md) |
| 16 AAD Military Sweep | [review-cards/16-aad-military-sweep.md](../review-cards/16-aad-military-sweep.md) |
| 17 FamilySearch Tree Contribution | [review-cards/17-familysearch-tree-contribution.md](../review-cards/17-familysearch-tree-contribution.md) |
| 18 Edge Verification | [review-cards/18-edge-verification.md](../review-cards/18-edge-verification.md) |
| 19 FS Source Harvest | [review-cards/19-fs-source-harvest.md](../review-cards/19-fs-source-harvest.md) |
| 20 Creative Vault Review | [review-cards/20-creative-vault-review.md](../review-cards/20-creative-vault-review.md) |
| 25 Person Research Sweep | [review-cards/25-person-research-sweep.md](../review-cards/25-person-research-sweep.md) |
| 21 Session Start | [review-cards/21-session-start.md](../review-cards/21-session-start.md) |
| 22 Research Iterations | [review-cards/22-research-iterations.md](../review-cards/22-research-iterations.md) |
| 23 Session Review | [review-cards/23-session-review.md](../review-cards/23-session-review.md) |
| 24 Session Close | [review-cards/24-session-close.md](../review-cards/24-session-close.md) |

## Prerequisites

| Prompt | Requires |
|---|---|
| 01-tree-expansion | A privacy-reviewed, source-labeled `Family_Tree.md` with deceased targets and review capacity |
| 02-cross-reference-audit | A populated `Family_Tree.md` plus person files or transcription notes |
| 03-findagrave-sweep | A `Family_Tree.md` with death dates or "deceased" notations |
| 04-gedcom-completeness | A `Family_Tree.md` and optionally an existing `.ged` file |
| 16-aad-military-sweep | Populated `Family_Tree*.md` with deceased US-resident persons born ~1888-1985 (entries carry `- meta:` blocks; `life_status: deceased` only) |
| 17-familysearch-tree-contribution | Populated `Family_Tree*.md` (entries with `fs: TBD` meta = the worklist); logged-in FamilySearch Chrome session (subject [SUBJECT_PID]); ≥1 attachable primary source per candidate |
| 19-fs-source-harvest | Populated `Family_Tree*.md` (entries carry `- meta:` blocks with `fs:` PIDs = the worklist); logged-in FamilySearch Chrome session; optional coverage-audit helper to rank SOURCE_GAP targets |
| 18-edge-verification | Populated `Family_Tree*.md` with `- meta:` edges carrying `?` marks (run `scripts/build_edges.py` first); logged-in FamilySearch Chrome session |
| 20-creative-vault-review | A populated `Family_Tree*.md` that has already had at least one expansion and one source pass — the lenses need material to work on |
| 21-session-start | A vault on the mechanized session loop (`scripts/session_plan.py` present; `AUTORESEARCH_VAULT` set); SessionStart audit hook installed |
| 22-research-iterations | A session initialized via 21-session-start (current gate values, session number, session-start metric values in hand) |
| 23-session-review | Iterations run and recorded via 22-research-iterations; the sitting's `logs/<date>-<slug>.md` |
| 24-session-close | A reviewed sitting (23-session-review's material); the vault's Operating_Protocol close-block template |

## Placeholders

Common placeholders include:

- `[SURNAME]` — A family surname (e.g., "Hansen")
- `[ANCESTOR]` — A specific ancestor's name (e.g., "Elias M. Hansen")
- `[ANCESTOR NAME]` — A specific ancestor's full name, often used inside search strings
- `[LOCATION]` — A geographic location (e.g., "Example Town, Example State")
- `[DATE]` — A date or date range (e.g., "1866" or "1880-1920")
- `[VAULT_PATH]` — The path to your vault (e.g., `~/Vaults/MyVault/Genealogy/`)
- `[GEDCOM_PATH]` — The path to your GEDCOM file

Each prompt also lists any prompt-specific placeholders such as `[DEATH YEAR]`, `[COUNTY]`, `[STATE]`, `[YEAR RANGE]`, `[SOURCE_URL_OR_PATH]`, `[ARCHIVE_URL]`, `[COLLECTION]`, `[IMAGE_ID_RANGE]`, or `[EVIDENCE_DIR]` in its `Inputs To Replace` section.

## Privacy

Autonomous prompts should not search living people. Mark living and possibly living people in your vault before running tree expansion, and redact exact dates or contact details for anyone living or possibly living.

Use [Privacy Mode](../guides/privacy-mode.md) before pasting family details into a public AI tool or sharing a GEDCOM.
