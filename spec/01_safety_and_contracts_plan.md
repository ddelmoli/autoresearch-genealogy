# Plan: Spec 01 Safety And Contracts

## Tasks
1. Add `Inputs To Replace` blocks to every numbered prompt.
2. Add living-person privacy guardrails to Quick Start, getting started, and tree expansion.
3. Align prompt references to canonical core vault file names.
4. Split evidence quality from profile completeness in templates and reference docs.
5. Add a canonical vault file manifest.

## Files And Tests
| Task | Files | Verification |
|---|---|---|
| Prompt inputs | `prompts/[0-9]*.md`, `prompts/README.md` | `rg '^## Inputs To Replace' prompts/[0-9]*.md` |
| Privacy | `README.md`, `workflows/getting-started.md`, `prompts/01-tree-expansion.md` | Manual review |
| Naming | `prompts/06-unresolved-persons.md`, `prompts/12-dna-chromosome-analysis.md`, `reference/vault-file-manifest.md` | `rg 'unresolved_persons|chromosome_painting'` |
| Confidence schema | `reference/confidence-tiers.md`, templates, workflows | `rg 'confidence:'` |

## Risks
- Existing private vault files may still use older frontmatter. Spec 04 will mirror guidance without forcing migration of every person file.
