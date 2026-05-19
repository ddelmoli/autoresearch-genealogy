# Repository Quality Pass
**Goal:** Make the public toolkit safer, more mechanically verifiable, and easier to maintain without leaking private research content.
**Architecture:** This is a markdown-first repository. The quality pass adds prompt contracts, canonical vault naming rules, privacy guardrails, anonymized fixtures, validation scripts, and CI.
**Tech Stack:** Markdown, Ruby standard library validation, GitHub Actions.

## Spec Breakdown
| # | Spec | Description | Depends On |
|---|------|-------------|------------|
| 01 | Safety And Contracts | Add privacy rules, canonical file names, prompt input blocks, and confidence schema guidance. | - |
| 02 | Validation And CI | Add repository validator and GitHub Actions workflow. | 01 |
| 03 | Documentation Polish | Fix README/example drift, glossary typo, contribution docs, and archive verification metadata. | 01, 02 |
| 04 | Anonymized Fixtures | Add a minimal fake vault and golden-run example for behavior-oriented prompt review. | 01, 02, 03 |

## Interface Summary
Spec 01 produces the content conventions that Spec 02 validates. Spec 03 documents how contributors run those checks. Spec 04 provides fake data that future prompt behavior tests can use.
