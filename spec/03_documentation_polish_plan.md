# Plan: Spec 03 Documentation Polish

## Tasks
1. Fix README count drift and glossary typo.
2. Add contributor instructions for validation and privacy.
3. Add archive guide verification metadata to every archive guide.
4. Enforce archive verification metadata in `scripts/validate-repo`.

## Files And Tests
| Task | Files | Verification |
|---|---|---|
| Counts and typo | `README.md`, `reference/glossary.md` | `scripts/validate-repo` |
| Contribution docs | `CONTRIBUTING.md` | Manual review |
| Archive metadata | `archives/*.md`, `archives/README.md` | `scripts/validate-repo` |
| Validator enforcement | `scripts/validate-repo` | `scripts/validate-repo` |

## Risks
- `last_verified` dates are only as good as the last human review. The metadata makes staleness visible but does not prove URLs remain live forever.
