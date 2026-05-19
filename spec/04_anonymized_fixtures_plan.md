# Plan: Spec 04 Anonymized Fixtures

## Tasks
1. Remove private-vault implementation notes from public spec files.
2. Add fake fixture vault files.
3. Add a golden-run transcript for `01-tree-expansion`.
4. Add optional local denylist support to `scripts/validate-repo`.
5. Run validation with a local untracked denylist.

## Files And Tests
| Task | Files | Verification |
|---|---|---|
| Scrub public specs | `spec/*` | denylist scan |
| Fixture vault | `fixtures/minimal-vault/*` | `scripts/validate-repo` |
| Golden run | `fixtures/golden-runs/01-tree-expansion.md` | manual review |
| Privacy denylist | `scripts/validate-repo`, `.gitignore`, `CONTRIBUTING.md` | local `.private/anonymization-denylist.txt` scan |

## Risks
- The local denylist is intentionally untracked, so CI cannot enforce Matt-specific private terms. CI enforces structure; local validation enforces the private denylist before publishing.
