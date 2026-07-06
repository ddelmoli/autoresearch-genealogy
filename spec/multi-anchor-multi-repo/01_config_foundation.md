# Spec 01: Config Foundation
**Goal:** Add the three config blocks that the rest of the lane consumes, plus their loaders, without changing behavior for any vault that omits them.
**Depends on:** none

## Requirements
- Extend `vault/.autoresearch.json` with three optional top-level blocks:
  - `anchor`: `{ "kind": "individual" | "couple", "people": [ { "id", "name", "fs"? } ] }`. One person for `individual`, two for `couple`. Consumed by Spec 02.
  - `repositories`: a map of repository id to `{ "kind": "shared-tree" | "personal-tree" | "corroboration", "read": { "autonomous": bool }, "write": { "enabled": bool, "operator_gated": bool, "visibility": "public" | "private" } }`. Consumed by Spec 04.
  - `hosts`: a map of host id to `{ "label", "ark_naan"?, "url_pattern"?, "locator_kind": "ark" | "url" | "id" }`. Consumed by Spec 03. Seeded with the hosts already recognized by `harvest_sources.py` (familysearch NAAN 61903, antenati NAAN 12657, metryki, szukajwarchiwach).
- Add loader functions in `scripts/vault_config.py`, each returning a documented default when its block is absent:
  - `get_anchor(cfg)`: defaults to a single-person anchor synthesized from the legacy subject convention (an `individual` anchor with an empty people list is acceptable as the null default).
  - `get_repositories(cfg)`: defaults to a single `fs` repository, `shared-tree`, read autonomous, write enabled and operator-gated, visibility public. This exactly reproduces today's FamilySearch-only behavior.
  - `get_hosts(cfg)`: defaults to the four hosts hardcoded in `harvest_sources.py` today.
- Defaults must be defined once and shared, so a fresh vault with no `.autoresearch.json` and a legacy vault with a partial one both behave like the current framework.
- The default `repositories` map is FamilySearch only. A vault may add a WikiTree entry, but it ships **write-disabled** (`write.enabled: false`), so WikiTree stays corroboration-only unless a vault explicitly opts in (see Spec 04). The example config shows a disabled `wt` entry to document the shape without enabling it.

## Files
- Modify: `scripts/vault_config.py` (add the three loaders and their defaults)
- Create: `vault-template/.autoresearch.example.json` (a documented, loadable example using `"_comment"` keys for the three blocks). The real `.autoresearch.json` stays strict JSON parsed by `vault_config.py`, so no inline `//` comments are introduced and the loader keeps its zero-dependency `json.load` path.
- Modify: `CLAUDE.method.md` (document the three blocks under the `.autoresearch.json` paragraph, pointing at the example file)

## Boundary Map
- **Produces**: `get_anchor`, `get_repositories`, `get_hosts` plus their defaults.
- **Consumes**: the existing `vault_config` JSON load and `resolve_vault` plumbing.

## Acceptance Criteria
- [ ] A vault with no `anchor` / `repositories` / `hosts` blocks yields the documented defaults from each loader.
- [ ] A vault with each block populated yields the parsed values.
- [ ] `scripts/gen_person_index.py --integrity` and `scripts/harvest_sources.py` still run unchanged (no consumer wired yet).
- [ ] `scripts/validate-repo` passes under UTF-8 and `LC_ALL=C`.

## Test Plan
- Unit-style smoke: load a fixture config with all three blocks and assert parsed shape; load an empty config and assert each default.
- Run `harvest_sources.py` and `gen_person_index.py --integrity` against the sample fixtures to confirm no regression.
