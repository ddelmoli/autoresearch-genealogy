# Changelog

## 2026-05-19

Initial sanitized public release.

### Added
- Explicit `Inputs To Replace` sections for all numbered prompts.
- Living-person privacy guardrails for first-run genealogy workflows.
- Canonical vault file manifest and prompt path consistency rules.
- Split evidence schema: `evidence_tier` for claim quality and `profile_status` for file completeness.
- `scripts/validate-repo` plus GitHub Actions validation.
- `scripts/privacy-audit-repo` for local denylist scans across current `HEAD` and reachable Git history.
- Contribution guidance, including an optional local anonymization denylist.
- Archive guide `last_verified` metadata.
- Synthetic `fixtures/minimal-vault/` and `fixtures/golden-runs/01-tree-expansion.md` for safe prompt behavior review.

### Changed
- Public examples now use fictional names, locations, and percentages.
- GEDCOM and naming examples now use generic sample places and surnames.

### Notes
- The fixture data is synthetic and should not be treated as genealogical evidence.
