# Safety And UX Polish

**Goal:** Harden privacy validation and make the first-run path coherent for nontechnical users.

**Architecture:** This is a markdown and Ruby validation pass. Public repo validation catches safer defaults, prompt guardrails reduce risky autonomous behavior, and the private mirror receives the same public toolkit changes without Git history or private audit artifacts.

**Tech Stack:** Markdown, Ruby validation scripts, GitHub Actions.

## Spec Breakdown

| # | Spec | Description | Depends On |
|---|------|-------------|------------|
| 01 | Privacy Audit Hardening | Redact denylist terms in reports, move reports outside the repo by default, add public privacy checks, and harden private vault validation | none |
| 02 | Prompt Guardrails | Tighten tree expansion, GEDCOM, and DNA prompt safety so growth, exports, and genetic analysis stay conservative | 01 |
| 03 | First-Run UX Route | Remove expansion-first contradictions, add a download-first path, and convert first-run paths to links | 02 |
| 04 | Mirror And UAT Notes | Mirror the sanitized toolkit into the private vault and record validation evidence | 03 |

## Interface Summary

Spec 01 produces safer validators consumed by Specs 02 and 03. Spec 04 consumes the final public repo state and mirrors it into the private vault.

