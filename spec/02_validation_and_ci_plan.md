# Plan: Spec 02 Validation And CI

## Tasks
1. Add `scripts/validate-repo` using Ruby standard library only.
2. Validate prompt structure, input sections, vault-template frontmatter, canonical prompt paths, local markdown links, and README counts.
3. Add GitHub Actions workflow that runs the validator.
4. Run the validator locally and fix failures.

## Files And Tests
| Task | Files | Verification |
|---|---|---|
| Validator | `scripts/validate-repo` | `scripts/validate-repo` |
| CI | `.github/workflows/validate.yml` | workflow uses the same command |
| Progress | `spec/progress.md` | status updated after green validation |

## Risks
- README count validation can be brittle if wording changes. Keep checks targeted to current count statements.
