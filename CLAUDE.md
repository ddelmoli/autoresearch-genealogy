# CLAUDE.md

Project instructions for autoresearch-genealogy.

## Project Structure

- `prompts/` — Autoresearch prompts for Claude Code. Each prompt is a self-contained research task.
- `vault-template/` — Obsidian vault starter kit. Copy into your vault to begin.
- `reference/` — Methodology guides. Not meant to be modified per-project.
- `workflows/` — Step-by-step procedures for common tasks.

## Prompt Format

Every prompt in `prompts/` follows this structure:

- **Goal**: What the prompt is trying to accomplish
- **Metric**: A measurable quantity that indicates progress
- **Direction**: Whether to maximize or minimize the metric
- **Verify**: A command or check that measures current state
- **Guard**: Safety rails (what the prompt should NOT do)
- **Iterations**: How many autonomous loops to run
- **Protocol**: Step-by-step instructions for each iteration

Each numbered prompt must include an `Inputs To Replace` section before `## Autoresearch Configuration`.

## Vault Template Conventions

- All vault files use YAML frontmatter with at minimum: `type`, `created`, `tags`
- Person files add: `name`, `born`, `died`, `life_status`, `family`, `evidence_tier`, `profile_status`, `sources`
- Transcription files add: `source`, `document_type`, `person`, `date`, `ocr_method`, `ocr_quality`
- Region and surname files add: `evidence_tier`
- Wikilinks (`[[File_Name]]`) connect files within the vault
- File names use underscores, not spaces: `John_Smith.md`, not `John Smith.md`
- Canonical core vault file names are listed in `reference/vault-file-manifest.md`. Prompts should use those exact names.

## Style

- No hyphens as punctuation. Use commas, periods, colons, semicolons, or parentheses.
- No emojis.
- Source-first: every claim should cite its source. Unsourced claims should be flagged.
- Log negative results. "Searched X, found nothing" is valuable data.
- Use confidence tiers (Strong Signal / Moderate Signal / Speculative) for all claims.
- Treat living-person data as private. Do not web-search living people during autonomous runs, and do not publish exact birth dates, addresses, phone numbers, or contact details for living or possibly living people.

## When Contributing

- All examples must use placeholder names. Zero real family names.
- Every prompt must include all 7 fields (Goal, Metric, Direction, Verify, Guard, Iterations, Protocol).
- Vault templates must have valid YAML frontmatter.
- Run `scripts/validate-repo` before submitting.
- Test prompts end-to-end when behavior changes.
