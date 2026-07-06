# Progress: Multi-Anchor, Multi-Repository Model
| # | Spec | Status | Tests | Commit |
|---|------|--------|-------|--------|
| 00 | Overview | planned | - | - |
| 01 | Config Foundation | planned | - | - |
| 02 | Anchor Model | planned | - | - |
| 03 | Source Locator Model | planned | - | - |
| 04 | Repository Write-Back | planned | - | - |

## Current: Design drafted, awaiting review
Specs written, no code yet. Dependency order is 01 (foundation), then 02 and 03 in parallel, then 04. Item 1 (Spec 02) is the smallest and lowest-risk and can land first as a quick win. Spec 03 is the load-bearing change that unlocks Spec 04.

Each spec has two sides: a framework change (this public repo) and a vault-adoption step (the separate local-only vault repo). A spec is done only when both pass. Per-family values land on the private side (the vault's gitignored `.autoresearch.json` and the private instance doc), never in these public specs.

## Resolved decisions (2026-07-06)
- WikiTree write-back: **schema-capable, ships disabled.** The `repositories` registry can express a WikiTree write target, but it defaults to `write.enabled: false`, so WikiTree stays corroboration-only unless a vault opts in. Reflected in Spec 01 and Spec 04.
- Example config: **sibling `vault-template/.autoresearch.example.json`.** The real `.autoresearch.json` stays strict JSON (no inline comments); the example uses `"_comment"` keys. Reflected in Spec 01.
- Sources bullet: **migrate `FS-attached sources` to `Sources`, parser accepts both transitionally, then converge.** One-time migration, no data loss, no flag day. Reflected in Spec 03.

## Log
- 2026-07-06 Created the lane. Drafted overview and specs 01 through 04 from three framework-generalization asks: couple anchors, decoupled research vs write-back logins, and a source model that names the host and supports one record across multiple hosts.
- 2026-07-06 Resolved the three open decisions (WikiTree schema-capable but disabled, sibling example config, migrate sources bullet with transitional dual-label). Folded into specs 01, 03, 04.
- 2026-07-06 Added the vault-adoption dimension: each spec now carries a Vault adoption acceptance criterion (apply the change to the live vault, committed in its own repo), and the overview documents the two-repo split. Keeps public specs generic; per-family values stay on the private side.
