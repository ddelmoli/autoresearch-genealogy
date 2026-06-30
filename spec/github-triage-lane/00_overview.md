# GitHub Triage Lane
**Goal:** Add a maintainer workflow that keeps issues and pull requests classified, validated, and ready for human review.
**Architecture:** The lane uses deterministic local tooling around the GitHub CLI. It stores fetched issue and pull request snapshots in a local ignored state file, classifies each item with privacy-aware rules, and emits markdown reports that a maintainer can use before labeling, closing, merging, or requesting changes.
**Tech Stack:** Markdown, Ruby standard library, GitHub CLI, existing repository validation scripts.

## Spec Breakdown
| # | Spec | Description | Depends On |
|---|------|-------------|------------|
| 01 | Baseline And PR Gates | Restore a green validator baseline and document the maintainer gate for external PRs. | - |
| 02 | Durable Triage State | Add a GitHub triage script that syncs open issues and PRs, classifies them, and writes local state. | 01 |
| 03 | Issue Intake And Cleanup | Add issue templates, maintainer docs, UAT, and apply the lane to current public issues and PRs. | 01, 02 |

## Interface Summary
Spec 01 produces a trusted validation baseline. Spec 02 consumes that baseline and produces `scripts/github-triage`. Spec 03 consumes the triage report and turns it into repository intake defaults plus GitHub cleanup actions.
