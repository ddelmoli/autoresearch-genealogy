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

Before contributing examples, read [Privacy Mode](guides/privacy-mode.md). Use the synthetic fixture under `fixtures/minimal-vault/` when possible.

If you maintain a private source vault, create an untracked `.private/anonymization-denylist.txt` file with sensitive surnames, place names, and phrases. `scripts/validate-repo` will scan tracked public files against it. The `.private/` directory is gitignored and must never be committed.

Before publishing, also run:

```bash
scripts/privacy-audit-repo
```

This scans both current `HEAD` and reachable Git history against the local denylist, excluding `LICENSE`. Reports are written outside the repo by default under `~/.cache/autoresearch-genealogy/privacy-audits/`, and matched private terms are shown only as fingerprints plus length.

To choose a different report location, set:

```bash
PRIVACY_AUDIT_REPORT_DIR=/path/to/private/reports scripts/privacy-audit-repo
```

## Archive Guides

Archive guides must include `last_verified` metadata. Update it whenever you check URLs, pricing, login requirements, or AI accessibility.

## Evidence Standards

Use `evidence_tier` for claim quality and `profile_status` for file completeness. Do not collapse both into one confidence field.

## Maintainer Triage

For public issues and pull requests, start with the read-only triage lane:

```bash
scripts/github-triage report --repo mattprusak/autoresearch-genealogy --refresh
```

Use the report to decide labels, comments, closures, merges, or a maintainer branch. The script writes local state under `.github-triage/`, which is ignored because issue bodies can contain private genealogy details.

Before merging a PR:

- Run `scripts/validate-repo`.
- If `scripts/validate-repo` changes, also run `LC_ALL=C scripts/validate-repo`.
- For archive guides, verify links and source claims are generic and public.
- For prompts, fixtures, and examples, reject real family data.
- For public genealogy help issues, answer with self-service guidance. Do not research a private family in a public issue thread.
