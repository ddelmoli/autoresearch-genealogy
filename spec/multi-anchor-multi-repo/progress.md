# Progress: Multi-Anchor, Multi-Repository Model
| # | Spec | Status | Tests | Commit |
|---|------|--------|-------|--------|
| 00 | Overview | planned | - | - |
| 01 | Config Foundation | done | loader smoke test (defaults/synthesis/couple/copy-safety), `gen_person_index --integrity`, `harvest_sources` | pending |
| 02 | Anchor Model | done | prose_audit regression + synthetic two-root fixture; vault get_anchor=couple; vault pre-commit integrity | 15c6d59 (fw) / vault 4bc2933 |
| 03 | Source Locator Model | done (Phase A); Phase B backlog (98 flags) | fixtures + byte-identical pre-migration CSV; migrated vault coverage-neutral (categories identical, 0 inflation); vault pre-commit integrity | private scripts / vault template 68d5d06, migration 5c266d6 |
| 04 | Repository Write-Back | planned | - | - |

## Current: Specs 01 and 02 done; 03 and 04 planned
Spec 01 landed the config foundation: `get_anchor` / `get_repositories` / `get_hosts` loaders + backward-compatible DEFAULTS in `vault_config.py`, and `vault-template/.autoresearch.example.json`.

Spec 02 done (framework + vault adoption). Framework: generation numbering was already couple-safe; fixed the one single-root assumption in `prose_audit.build_relation_map` (per-root father/mother tracking) and noted couple anchors in prompt 01. Vault adoption: wrote `anchor: couple` (two ids + PIDs, no living names) into the vault's `.autoresearch.json` (committed 4bc2933, pre-commit integrity passed) and updated the private instance doc to the couple framing. `get_anchor` returns the couple.

Deferred follow-up (not blocking): extend `Family_Tree.md`'s ASCII diagram with the second anchor's ancestry as a second root, so prose_audit's relationship descriptors cover that spouse's lines too.

Spec 03 step 1 done (framework tooling, private scripts, fixtures only — no vault touched):
- `harvest_sources.py` now counts RECORDS not locator tokens and prints a per-host locator breakdown. Backward-compat proven: on the all-legacy vault the `--csv` output is byte-identical to the pre-change baseline (record_count == old ark_count until a file migrates). Record/host semantics unit-tested on fixtures (legacy flat, multi-host single record, mixed migrated+stray, prose-colon false-positive).
- `migrate_sources.py` (new): relabel `FS-attached sources` -> `Sources`, host-prefix every locator (namespace preserved so it stays recountable), approach-b grouping — auto-merge persona/household pairs, freeform bullets get locators + a preserved pre-migration note + a flag, structured merge-hint bullets flagged. Dry-run default, `--apply`, idempotent. Fixtures pass; a full dry-run over the live vault processed all 700 bullets: 7091 locators -> 7090 records, 98 flagged for Phase B (48 freeform + 50 merge-hint). No vault write.

Step 2 done (writers/docs): the vault `templates/person_narrative.md` (vault commit 68d5d06), local prompts 17/19, and `CLAUDE.method.md` Rule 8 now emit/describe the `**Sources**` record/host:locator grammar, with the transitional dual-label note and a pointer to `migrate_sources.py`.

Step 3 done (Phase A vault adoption, vault commit 5c266d6): ran `migrate_sources.py --apply` over 24 files (700 bullets). Diagnosed and fixed a counting bug found during verification — `count_records` counted record LINES, so pre-existing duplicate ARKs (the same source cited in a person's bullet and a children note) that the legacy set-based count deduped were inflating the migrated count (e.g. 40->51). Fix: a record's identity is its SET of `host:locator` tokens, deduped. After the fix the migrated vault is provably coverage-neutral: `harvest_sources` categories are IDENTICAL to pre-migration (SOURCE_GAP 17, LOW 176, WELL 618, STRUCTURAL 147), with 0 increases and only merge-driven decreases. Idempotent (second `--apply` = 0 changes); pre-commit integrity 0 HARD.

Phase B (incremental, ongoing, NOT this spec): 98 flagged bullets (48 freeform + 50 merge-hint) each carry a preserved `note (pre-migration)` line — re-attach per-record descriptors and confirm any same-record locator merges. Burn down opportunistically when editing a file.

Spec 03 complete. Next: Spec 04 (repository write-back + per-target privacy gate).

Next: Spec 03 (source-locator model) — the load-bearing change that unlocks Spec 04. Vault impact measured (06 JUL 2026): ~697 `FS-attached sources` bullets across 28 files, ~7,900 locator tokens, ~40+ multi-locator-same-record spots. Folded into Spec 03 as its Vault Adoption section. Migration approach = **(b)**: Phase A mechanical pass (relabel + host-prefix + one-record-per-locator) that AUTO-MERGES high-confidence pairs (persona/household, index/image) and FLAGS ambiguous cases for a later incremental Phase B. Dual-label parser makes it gradual and non-destructive.

## Design drafted, awaiting review
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
- 2026-07-06 Implemented Spec 01: added get_anchor/get_repositories/get_hosts loaders + DEFAULTS to vault_config.py, vault-template/.autoresearch.example.json, and CLAUDE.method.md docs. Smoke test passes (defaults, subject-synthesis, couple parse, WikiTree-disabled, cache-copy safety); gen_person_index --integrity and harvest_sources unchanged on the live vault. No vault edit needed (defaults suffice).
- 2026-07-06 Spec 02 framework: fixed prose_audit.build_relation_map father/mother detection to be per-root (couple-safe); single-root regression byte-identical on the live vault, synthetic two-root couple fixture labels both subtrees correctly. Added a couple-anchor note to prompt 01.
- 2026-07-06 Spec 02 vault adoption: wrote anchor:couple (the two anchor people, ids + PIDs only) into the vault's .autoresearch.json (vault commit 4bc2933; pre-commit integrity 0 HARD) and updated the private instance doc to couple framing. Spec 02 done. ASCII-diagram second root deferred.
- 2026-07-06 Measured Spec 03 vault impact against the live vault and folded it into the spec as a Vault Adoption section. Chose migration approach (b): Phase A auto-merges high-confidence multi-locator pairs and flags ambiguous ones for incremental Phase B. Added acceptance criteria + test-plan cases for the auto-merge/flag and idempotent dry-run/apply migration.
- 2026-07-06 Spec 03 step 1 (tooling): rewrote harvest_sources.py to count records + per-host (byte-identical vault CSV proves backward-compat) and added migrate_sources.py (approach-b migration, dry-run/apply/idempotent). Fixtures pass; 700-bullet vault dry-run: 7091 locators -> 7090 records, 98 flagged. Private scripts (OneDrive-backed).
- 2026-07-06 Spec 03 step 2 (writers/docs): vault person-narrative template (vault 68d5d06), local prompts 17/19, and CLAUDE.method.md Rule 8 now emit/describe the **Sources** record/host:locator grammar with the transitional dual-label note. Step 3 (vault --apply migration) paused for review.
- 2026-07-06 Spec 03 step 3 (Phase A migration, vault 5c266d6): --apply over 24 files. Fixed a count_records line-vs-set inflation bug found in verification (dedupe records by host:locator token-set). Migrated vault coverage-neutral (categories identical to pre-migration, 0 inflation), idempotent, pre-commit 0 HARD. Spec 03 done; Phase B backlog = 98 flagged bullets with preserved pre-migration notes.
