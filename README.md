# autoresearch-genealogy

Structured prompts, vault templates, and research workflows for AI-assisted genealogy research. Built for Claude Code, adaptable to any AI tool or manual workflow.

This project extracts and generalizes methods developed during a real genealogy research effort that produced 105 files spanning 9 generations across 6 family lines, using Claude Code's autonomous research capabilities.

## Who This Is For

- **Genealogy researchers** who want to use AI to accelerate their family history work without sacrificing source rigor
- **AI/tech enthusiasts** who want a concrete example of autonomous research loops applied to a humanities domain
- **Anyone** who has a box of old photos, a DNA test, and unanswered questions about their family

## Quick Start

If you are new to AI-assisted genealogy, start with [START_HERE.md](START_HERE.md). It routes you by what you already have: names, documents, DNA results, an existing tree, or a finding you need to verify.

1. If you do not use Git, follow [Download And Start](guides/download-and-start.md).
2. Copy the [vault-template](vault-template/) folder into your Obsidian vault or any markdown editor.
3. Fill in `Family_Tree.md` with what you already know. Mark living or possibly living people clearly and avoid exact birth dates for them.
4. Use [Privacy Mode](guides/privacy-mode.md) and [First Week Checklist](checklists/first-week-checklist.md).
5. Use [Prompt Picker](guides/prompt-picker.md) to choose a verification or source-inventory prompt before expansion.
6. Run [02 Cross-Reference Audit](prompts/02-cross-reference-audit.md) or [05 Source Citation Audit](prompts/05-source-citation-audit.md) before [01 Source-Backed Tree Expansion](prompts/01-tree-expansion.md).

See [Getting Started](workflows/getting-started.md) for the full walkthrough.

## What's Included

### Beginner Guides (`guides/`)

Start with [Download And Start](guides/download-and-start.md) if you do not use Git. Use [Prompt Picker](guides/prompt-picker.md) when you do not know what to run. The bundle guides package prompts into safer workflows:

- [Beginner Pack](guides/bundles/beginner-pack.md)
- [Document Pack](guides/bundles/document-pack.md)
- [DNA Pack](guides/bundles/dna-pack.md)
- [Verification Pack](guides/bundles/verification-pack.md)
- [Advanced Pack](guides/bundles/advanced-pack.md)

Printable checklists cover [first-week setup](checklists/first-week-checklist.md), [scanning documents](checklists/scan-your-documents.md), [interviewing relatives](checklists/interview-a-relative.md), [verifying AI findings](checklists/verify-an-ai-finding.md), [adding ancestors](checklists/before-you-add-an-ancestor.md), and [sharing safely](checklists/share-safely.md).

For a privacy-safe dry run, use the [First Run Walkthrough](walkthroughs/first-run.md) with the synthetic fixture.

Plain-language reference pages explain [source grades](guides/plain-language/source-grades.md), [evidence versus clues](guides/plain-language/evidence-vs-clues.md), [why AI can be wrong](guides/plain-language/why-ai-can-be-wrong.md), and [what counts as proof](guides/plain-language/what-counts-as-proof.md).

If you do not use Obsidian, follow [No-Obsidian Setup](guides/no-obsidian-setup.md). The template works as a normal folder of markdown files.

Before using public AI tools or sharing exports, follow [Privacy Mode](guides/privacy-mode.md).

### Prompts (`prompts/`)

13 autoresearch prompts designed for Claude Code's `/autoresearch` command. Each defines inputs to replace, a Goal, Metric, Direction, Verify condition, Guard rails, Iterations, and Protocol. They run autonomously: searching the web, browsing image archives, updating your vault, and verifying their own work.

| Prompt | Purpose |
|---|---|
| 01-tree-expansion | Review source-backed candidate relationships for deceased ancestors |
| 02-cross-reference-audit | Find and fix discrepancies between your tree and source documents |
| 03-findagrave-sweep | Locate Find a Grave memorials for every deceased ancestor |
| 04-gedcom-completeness | Ensure your GEDCOM file matches your vault data |
| 05-source-citation-audit | Verify every person file cites at least two independent sources |
| 06-unresolved-persons | Identify and resolve unnamed people mentioned in your documents |
| 07-timeline-gap-analysis | Find life events where records should exist but have not been found |
| 08-open-question-resolution | Systematically attack every open research question |
| 09-bygdebok-extraction | Extract data from digitized local history books (any country) |
| 10-colonial-records-search | Search for colonial American ancestors in pre-1800 records |
| 11-immigration-search | Locate passenger manifests and naturalization records |
| 12-dna-chromosome-analysis | Analyze per-chromosome ancestry data to map genetic segments |
| 13-image-archive-deep-dive | Browse image-only archives, read entries, and save cropped evidence images |

### Vault Template (`vault-template/`)

19 files: a complete Obsidian vault starter kit with YAML frontmatter, plain markdown, readable anywhere.

- **Core files**: Family tree, research log, open questions, data inventory, timeline, genetic profile, chromosome painting, witness network, unresolved persons, research strategy
- **Templates**: Person, transcription, certificate, postcard, region, surname, hypothesis, draft letter

### Archive Guides (`archives/`)

24 country and region-specific guides covering where to find records, what is free vs paid, and what AI tools can access directly vs what requires a browser.

**Europe**: Ireland, England/Wales, Scotland, France, Italy, Spain/Portugal, Germany, Netherlands, Austria, Hungary, Norway, Sweden, Poland, Russia/Ukraine

**Americas**: USA (colonial, immigration, census, vital records), African American, Canada, Mexico/Latin America

**Oceania**: Australia/New Zealand

**Cross-national**: Jewish genealogy

### Reference Guides (`reference/`)

11 methodology documents: confidence tiers, source hierarchy, vault file manifest, DNA interpretation guardrails, naming conventions (patronymics, farm names, przydomki), GEDCOM format guide, common pitfalls, glossary, AI capabilities assessment, GitHub triage lane, and the case for autoresearch in genealogy.

### Workflows (`workflows/`)

10 step-by-step guides: getting started, OCR pipeline, image archive navigation, new ancestor intake, document triage, oral history protocol, discrepancy resolution, phase planning, source citation trace, onomastic origins.

### Examples (`examples/`)

5 anonymized worked examples showing autoresearch in action: tree expansion session, cross-reference audit, DNA-to-genealogy mapping, name resolution, colonial deep dive.

## Philosophy

**Structured autonomous research with mechanical verification, not AI guessing.**

Genealogy is different from most AI tasks. There is no compiler. Sources disagree with each other. Confidence is probabilistic, not binary. A name that appears as "Sakkarias" in one record and "Zacharias" in another might both be correct. A date listed as 1820 in one source and 1925 in another is almost certainly wrong somewhere.

The autoresearch approach adapts to this by:

- **Defining measurable metrics** (count of sourced claims, count of resolved questions, count of remaining discrepancies)
- **Requiring verification after every iteration** (cross-reference audit, not just accumulation)
- **Logging negative results** (what you searched for and did not find is as important as what you found)
- **Maintaining confidence tiers** (Strong Signal / Moderate Signal / Speculative) rather than treating all claims as equal
- **Protecting living-person privacy** (autonomous prompts skip living people and redact exact private details)

This is inspired by Andrej Karpathy's autoresearch concept: autonomous goal-directed loops where the AI modifies, verifies, keeps or discards, and repeats. Applied to genealogy, the "compiler" is replaced by cross-referencing independent sources.

## License

MIT. See `LICENSE`.

## Contributing

Contributions welcome. If you have prompts, workflows, or archive guides that worked for your research, open a PR. Please ensure all examples use placeholder names (no real family data).
