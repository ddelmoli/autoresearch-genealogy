# UAT: Repository Quality Pass

## Spec 01: Safety And Contracts
**Demo**: Prompts and templates expose safer contracts.
- [ ] `rg '^## Inputs To Replace' prompts/[0-9]*.md | wc -l` outputs `12`.
- [ ] `rg 'living people|possibly living|life_status' README.md workflows/getting-started.md prompts/01-tree-expansion.md` shows privacy rules.
- [ ] `rg 'unresolved_persons.md|chromosome_painting.md' prompts` returns no matches.
- [ ] `rg 'evidence_tier|profile_status' reference/confidence-tiers.md vault-template/templates/person.md` shows split evidence and completeness fields.

## Spec 02: Validation And CI
**Demo**: Repository checks are executable.
- [ ] `scripts/validate-repo` outputs `validate-repo: ok`.
- [ ] `.github/workflows/validate.yml` runs `scripts/validate-repo`.

## Spec 03: Documentation Polish
**Demo**: Contributor and archive docs are current.
- [ ] `rg 'Secondary source' reference/glossary.md` finds the corrected glossary entry.
- [ ] `rg 'scripts/validate-repo' CONTRIBUTING.md archives/README.md` finds local validation guidance.
- [ ] `rg '^last_verified:' archives/*.md | wc -l` outputs `23`.

## Spec 04: Anonymized Fixtures
**Demo**: The repo has fake fixture data and a golden-run prompt example.
- [ ] `test -f fixtures/minimal-vault/Family_Tree.md` succeeds.
- [ ] `test -f fixtures/golden-runs/01-tree-expansion.md` succeeds.
- [ ] `scripts/validate-repo` outputs `validate-repo: ok`.
