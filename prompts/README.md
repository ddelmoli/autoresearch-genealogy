# Prompts

Autoresearch prompts for AI-assisted genealogy research. Designed for Claude Code's `/autoresearch` command but adaptable to any AI tool that supports autonomous iteration.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

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
| 14 Military Service Records Sweep | [review-cards/14-military-records-sweep.md](../review-cards/14-military-records-sweep.md) |

## Prerequisites

| Prompt | Requires |
|---|---|
| 01-tree-expansion | A privacy-reviewed, source-labeled `Family_Tree.md` with deceased targets and review capacity |
| 02-cross-reference-audit | A populated `Family_Tree.md` plus person files or transcription notes |
| 03-findagrave-sweep | A `Family_Tree.md` with death dates or "deceased" notations |
| 04-gedcom-completeness | A `Family_Tree.md` and optionally an existing `.ged` file |

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
