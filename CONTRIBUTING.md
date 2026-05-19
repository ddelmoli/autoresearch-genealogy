# Contributing

Contributions are welcome if they preserve source rigor and privacy.

## Before Opening A PR

Run:

```bash
scripts/validate-repo
```

The validator checks:
- Numbered prompt structure and `Inputs To Replace` sections
- Vault-template YAML frontmatter
- Archive guide verification metadata
- Local markdown links
- README counts
- Canonical core vault file names in prompts
- Required anonymized fixtures
- Optional local privacy denylist terms

## Prompt Changes

Every numbered prompt must include:
- `Inputs To Replace`
- `Goal`
- `Metric`
- `Direction`
- `Verify`
- `Guard`
- `Iterations`
- `Protocol`

Use exact canonical vault file names from `reference/vault-file-manifest.md`.

## Privacy

Do not include real family data in examples. Do not add exact birth dates, addresses, phone numbers, emails, or other private details for living or possibly living people.

If you maintain a private source vault, create an untracked `.private/anonymization-denylist.txt` file with sensitive surnames, place names, and phrases. `scripts/validate-repo` will scan tracked public files against it. The `.private/` directory is gitignored and must never be committed.

Before publishing, also run:

```bash
scripts/privacy-audit-repo
```

This scans both current `HEAD` and reachable Git history against the local denylist, excluding `LICENSE`, then writes a local ignored report under `privacy-audits/`.

## Archive Guides

Archive guides must include `last_verified` metadata. Update it whenever you check URLs, pricing, login requirements, or AI accessibility.

## Evidence Standards

Use `evidence_tier` for claim quality and `profile_status` for file completeness. Do not collapse both into one confidence field.
