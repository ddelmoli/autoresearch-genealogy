# autoresearch-genealogy

Structured prompts, vault templates, and research workflows for AI-assisted genealogy research. Built for Claude Code, adaptable to any AI tool or manual workflow.

This project extracts and generalizes methods developed during a real genealogy research effort that produced 105 files spanning 9 generations across 6 family lines, using Claude Code's autonomous research capabilities.

## About This Fork

This is [**ddelmoli/autoresearch-genealogy**](https://github.com/ddelmoli/autoresearch-genealogy),
a fork of [mattprusak/autoresearch-genealogy](https://github.com/mattprusak/autoresearch-genealogy).
The prompts, guides, vault template, and workflows below are upstream's design and remain
compatible with it. Upstream has been quiet for some time; this fork has continued
independently and now differs from it in one substantial way.

**Upstream ships a method. This fork also ships the tooling that enforces it.**

Where upstream describes conventions a vault should follow, this fork adds programs that
check them, a record layer that both of the vault's storage models read through, and a test
suite over the whole thing. Concretely:

| addition | what it is |
|---|---|
| `scripts/person_store.py` | A model-agnostic seam over person records. A vault may store one Markdown file per person (upstream's model) **or** many people per lineage file, each a bold-name entry with an inline `- meta:` block. Every other script reads through this seam, so it serves both. |
| `scripts/gdate.py` | The [GEDCOM 7](https://gedcom.io/specifications/FamilySearchGEDCOMv7.html) `DateValue` grammar as a leaf module: validate a date, resolve a comparable year, normalise legacy prose. Genealogical dates (`ABT`, `BEF`, `BET…AND`, Old Style/New Style, non-Gregorian calendars) do not fit ISO, and this is what they fit instead. |
| `scripts/migrate_dates.py` | Converts dates written as display prose into that grammar, dry-run by default, never guessing and never rewriting a header. |
| Audit gates | `gen_person_index.py --integrity` (unique ids), `prose_audit.py` (prose-vs-canonical drift, plus a `DATE_DRIFT` header/field sync gate), `meta_presence_audit.py`, `header_xref_audit.py`, `dup_name_audit.py`, `build_edges.py --validate` (relationship-graph integrity), `harvest_sources.py` (source coverage). |
| Privacy enforcement | `check_narrative_privacy.py` mirrors the Ruby validator's living-person rule for the narrative model; both understand day-precision in ISO *and* GEDCOM notation. `privacy-audit-repo` additionally scans for record IDENTIFIERS, which point at a person even when no name appears. |
| Tests | Six runnable suites, no framework required: `test_gdate.py`, `test_person_store.py`, `test_migrate_dates.py`, `test_date_drift.py`, `test_privacy_dates.py`, `test_privacy_gate.rb`. |

Two working principles run through all of it, and they are worth stating because they shaped
the code more than any feature did:

- **Measure before shipping a parser change.** Every change to date or vitals parsing here was
  diffed against the full corpus of a real vault with a standing requirement of *zero* losses.
  Several plausible changes were rejected on that measurement, and three silently-wrong stored
  values were found by it.
- **A gate that reports a defect must not also cause one.** Checks that judge human prose stay
  advisory; only machine-vs-machine contradictions block a commit.

Design notes for each change live in `spec/`. If you are looking for the upstream project
rather than this toolkit, follow the link above.

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

### If you cloned this repo with Git, run this once

```bash
./scripts/install-hooks
```

That activates the tracked `.githooks/` directory for your clone, which installs a
**pre-commit PII gate**: it blocks a commit containing a private name from your
denylist, or a real record identifier (a FamilySearch PID or WikiTree id). An
external id is a *pointer to a person* — it discloses an ancestor even with no
name attached — so the gate treats it the same as a name.

It is one manual step because Git deliberately will not let a repository activate
its own hooks on clone: if it could, `git clone` would be arbitrary code
execution. The hook file travels with the repo; the switch (`core.hooksPath`)
lives in `.git/config`, which is never transferred. Re-running the script is
safe and idempotent.

Without a `.private/anonymization-denylist.txt` the name checks cannot run; the
hook says so loudly and allows the commit rather than making the repo
uncommittable for contributors.

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

20 files: a complete Obsidian vault starter kit with YAML frontmatter, plain markdown, readable anywhere. Includes both person-record templates: `person.md` (one file per person, the default) and `person_narrative.md` (many people per lineage file).

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

12 step-by-step guides: getting started, OCR pipeline, image archive navigation, new ancestor intake, document triage, oral history protocol, discrepancy resolution, phase planning, structured dates, header grammar, shard split, switching person model.

### Examples (`examples/`)

5 anonymized worked examples showing autoresearch in action: tree expansion session, cross-reference audit, DNA-to-genealogy mapping, name resolution, colonial deep dive.

## Scripts & Python Environment

The `scripts/` toolkit is **pure Python standard library by design** — the only third-party
package is **PyYAML**, and even that is imported defensively (the scripts degrade gracefully
without it). Requirements are declared in `pyproject.toml` and pinned in `uv.lock`.

- **Python:** 3.10+ — **no version is pinned**. `uv sync` uses the newest interpreter
  available on your machine that satisfies the `>=3.10` floor (ride-latest). Upgrading your
  system Python and re-running `uv sync` rebuilds the environment on the newer version.
- **Tooling:** [uv](https://docs.astral.sh/uv/). Install with `brew install uv`.

### First-time setup

```bash
uv sync          # creates .venv from uv.lock (installs PyYAML); reproducible on any machine
```

### Running a script

Every script needs a vault (there is no default): set `AUTORESEARCH_VAULT` or pass `--vault`.

```bash
# one-off, no activation needed:
AUTORESEARCH_VAULT=~/vaults/<name> uv run scripts/gen_person_index.py --integrity

# or activate once, then the existing `python3 scripts/...` docs work verbatim:
source .venv/bin/activate
export AUTORESEARCH_VAULT=~/vaults/<name>
python3 scripts/gen_person_index.py --integrity
```

### Notes

- **Do not `pip install` globally.** The env is managed entirely through `uv sync` /
  `uv.lock`. Add a dependency with `uv add <pkg>` (commit the updated lockfile).
- **OneDrive:** `.venv/` is git-ignored because this repo lives in OneDrive — a synced venv
  would upload thousands of interpreter files with machine-specific paths. Each machine runs
  its own `uv sync`. To keep the venv out of OneDrive entirely, point it elsewhere:
  `export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/autoresearch-genealogy` before `uv sync`.

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

Contributions welcome. If you have prompts, workflows, or archive guides that worked for your
research, open a PR against this fork. Fixes that are not specific to this fork's tooling are
worth sending to [upstream](https://github.com/mattprusak/autoresearch-genealogy) as well.

Please ensure all examples use placeholder names — **no real family data, and no real record
identifiers**. An external ID such as a FamilySearch PID resolves to a named person in one
click, so it discloses exactly what a placeholder name protects. `scripts/privacy-audit-repo`
checks both, and `scripts/validate-repo` checks the repository's structural contracts; run
both before opening a PR.
