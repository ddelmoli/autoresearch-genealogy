# Spec 04: Repository Write-Back
**Goal:** Make write-back a configured set of repositories, each with its own read and write auth, rather than a hardwired FamilySearch push. Drive the living-person privacy gate off the target repository's visibility, not a single global rule.
**Depends on:** 01, 03

## Design notes
- Read auth and write auth are already distinct for FamilySearch: Recipe-S harvest is read-only and autonomous, prompt-17 push is a write and operator-gated. Generalize that split to every repository in the registry instead of hardcoding it for FS.
- The current privacy gate (autonomous web research and FS mutation skip `living` and `unknown`) is a blanket rule because the only write target is public FamilySearch. A private personal tree (for example an Ancestry tree) can legally hold living people that a public shared tree cannot. So the gate must be a function of `(life_status, target.visibility)`: public target skips living and unknown; private target may include them. Getting this wrong leaks living-person data to a public tree, so it is the highest-risk change in the lane.
- WikiTree's status is a deliberate policy choice, not a default. Today it is corroboration-only and off the coverage metric because as a tree it copies FS and this vault. The registry is **schema-capable** for a WikiTree write target, but it ships **write-disabled** (`write.enabled: false`): WikiTree stays corroboration-only until a vault explicitly opts in. Keep the distinction between a WikiTree tree assertion (never evidence) and a primary source WikiTree hosts (a `wt:` locator, per Spec 03).

## Requirements
- Any prompt or recipe that performs a write-back must resolve its target from `get_repositories` and honor that target's `write.enabled`, `write.operator_gated`, and `write.visibility`.
- Implement the per-target privacy gate: before writing a person, compute allow/deny from `life_status` and the target's `visibility`. A public target denies `living` and `unknown`; a private target allows them. The gate is centralized so every write path shares it.
- Person write-back records the new external id under the matching meta key (`fs` / `wt` / `anc` / other) for the target repository. Source write-back adds a `host:locator` (Spec 03) for that repository's host.
- Generalize the FS-centric prompt language: `17-familysearch-tree-contribution`, `18-edge-verification`, `19-fs-source-harvest` must describe the operation in terms of a target repository, with FamilySearch as the default target when `repositories` is unset.
- No new provider API client is built in this spec. It defines the registry-driven routing, the gate, and the prompt generalization. A concrete non-FS write client (Ancestry or WikiTree) is a later lane.

## Files
- Create: a small shared privacy-gate helper (target visibility plus `life_status` to allow/deny), reusable by prompts and any future write client
- Modify: `prompts/17-familysearch-tree-contribution.md`, `prompts/18-edge-verification.md`, `prompts/19-fs-source-harvest.md`, `prompts/README.md`
- Modify: `CLAUDE.method.md` privacy-gate and write-back language
- Modify: `reference/common-pitfalls.md` (per-target privacy consequence)

## Boundary Map
- **Produces**: registry-driven write-back routing, a per-target `(life_status, visibility)` privacy gate, provider-neutral write-back prompts.
- **Consumes**: `get_repositories` from Spec 01; the `host:locator` grammar from Spec 03; the meta external-id keys.

## Acceptance Criteria
- [ ] A public target denies a `living` or `unknown` person; a private target allows the same person.
- [ ] With `repositories` unset, behavior matches today (FamilySearch only, operator-gated, public, skip living and unknown).
- [ ] A person write-back records the new external id under the correct meta key for the target.
- [ ] A source write-back adds the target's `host:locator` to the record per Spec 03.
- [ ] `scripts/validate-repo` passes under UTF-8 and `LC_ALL=C`.
- [ ] **Vault adoption:** the live vault's `.autoresearch.json` `repositories` block is set (the default `fs` target, plus any schema-capable-but-disabled targets the operator wants documented), committed in the vault repo, and the per-target privacy gate is confirmed against `$AUTORESEARCH_VAULT` (a public target still skips the vault's `living`/`unknown` entries).

## Test Plan
- Gate unit table: cross `life_status` in {living, deceased, unknown} with visibility in {public, private}; assert allow/deny.
- Default-target smoke: unset `repositories`, confirm the FS path and gate are unchanged.
- Fixture write-back: record a `wt:` external id and a `wt:` source locator on a fixture entry and confirm meta and Sources bullet update.
