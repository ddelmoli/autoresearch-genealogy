# Prompts

Autoresearch prompts for AI-assisted genealogy research. Designed for Claude Code's `/autoresearch` command but adaptable to any AI tool that supports autonomous iteration.

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

**Starting from scratch?**
Start with `01-tree-expansion`. It will search the web for every ancestor you've listed and try to extend every branch.

**Already have a populated tree?**
Run `02-cross-reference-audit` to find and fix discrepancies between your tree file and your source documents.

**Have deceased ancestors without memorial links?**
Run `03-findagrave-sweep` to locate Find a Grave memorials and extract data from them.

**Want to export your tree?**
Run `04-gedcom-completeness` to build or verify a GEDCOM file that matches your vault.

## Prerequisites

| Prompt | Requires |
|---|---|
| 01-tree-expansion | A `Family_Tree.md` file with at least your known ancestors listed |
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

Each prompt also lists any prompt-specific placeholders such as `[DEATH YEAR]`, `[COUNTY]`, `[STATE]`, `[YEAR RANGE]`, or `[SOURCE_URL_OR_PATH]` in its `Inputs To Replace` section.

## Privacy

Autonomous prompts should not search living people. Mark living and possibly living people in your vault before running tree expansion, and redact exact dates or contact details for anyone living or possibly living.
