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

## The framework/private boundary

This repo is a public **framework**. It is normally developed alongside a
**private vault** of real family data living in the same working tree. The
tracked `.gitignore` is what keeps those apart, and it is worth understanding
before you add a file, because it uses **two opposite defaults on purpose**:

| Directory | Default | Why |
|---|---|---|
| `scripts/` | **tracked** | It is framework code. An ignored script breaks a clone (see below), and code rarely contains names. |
| `prompts/`, `reference/`, `workflows/` | **ignored** | These hold research prose. A stray note can name living people, so publishing one is opt-in via a `!` negation. |

Always private, never committed: any vault directory (`vault/`, `vault-*/`),
`CLAUDE.instance.md` and `CLAUDE.local.md` (per-client facts — the subject and
lineage layout are family names by construction), `.private/` (the anonymization
denylist), and the personal `spec/<lane>/` design lanes.

**Put boundary rules in `.gitignore`, never in `.git/info/exclude`.** An exclude
file is machine-local and is never part of a clone, so a rule that lives only
there protects your working tree and nobody else's. This is not hypothetical:
the boundary used to live entirely in `.git/info/exclude`, written as "ignore
`scripts/*.py`, then re-add about 19 files by name". Under that shape
`scripts/vault_config.py` was never re-added while 15 of the scripts that import
it were tracked, so a fresh clone raised `ImportError` across nearly the whole
toolkit, including every test. Defaulting code to *tracked* is what stops that
class of bug from recurring.

Two consequences worth remembering:

- **Adding a new script?** It is tracked automatically. The pre-commit privacy
  audit is the backstop, not the `.gitignore` — keep real names out of comments
  and examples, including in illustrative asides.
- **Adding a new generic doc** to `prompts/`, `reference/`, or `workflows/`? Add
  a matching `!` negation, or it stays invisible. Tracking a new workflow also
  means bumping the workflow count in `README.md`, which `scripts/validate-repo`
  checks.

Verify the boundary still holds after editing it:

```bash
git check-ignore -v <path>          # confirm a private path is ignored
scripts/privacy-audit-repo          # must print: ok
scripts/validate-repo               # must print: ok
```

`privacy-audit-repo` scans **staged and tracked** files, so `git add` a file
before trusting its verdict on it.

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
