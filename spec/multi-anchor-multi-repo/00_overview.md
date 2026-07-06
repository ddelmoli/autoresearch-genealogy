# Multi-Anchor, Multi-Repository Model
**Goal:** Generalize the framework off two hardwired assumptions: that a vault is anchored on a single subject, and that the only research/write-back repository is FamilySearch. After this lane a vault can be anchored on an individual or a married couple, can name any number of external repositories with independent read and write credentials, and can record a source by the record it documents plus every host where that record lives.
**Architecture:** All three generalizations land on one config surface, `vault/.autoresearch.json`, read through the existing zero-dependency `scripts/vault_config.py` loader. Three new config blocks (`anchor`, `repositories`, `hosts`) drive three otherwise independent changes: an anchor-set generation model, a record/locator source model in the narrative bullets and `harvest_sources.py`, and a per-target write-back and privacy gate. An absent block falls back to today's behavior (single subject, FamilySearch only), so existing vaults keep running with zero config.
**Tech Stack:** Python standard library (the existing script toolkit), JSON config via `vault_config.py`, Markdown prompts and reference docs.

## Motivating observations
- A vault can already be a de-facto couple vault (both spouses' lines present, with one spouse's lines carried as bolted-on collateral) while modeled as single-subject. Item 1 formalizes existing practice.
- A read/write auth split already exists for FamilySearch: Recipe-S source harvest is read-only and autonomous, while prompt-17 push is a write and operator-gated. Item 2 generalizes that split across providers instead of inventing it.
- ARK notation is genuinely the most durable locator form because it is designed for host-independent persistence and its NAAN prefix encodes the host (61903 = FamilySearch, 12657 = Antenati). Its two limits are that most hosts do not mint ARKs, and that an ARK identifies a *locator*, not the underlying *record*. Item 3 keeps ARK as the preferred locator while modeling the record separately so one record can carry several host locators.

## Spec Breakdown
| # | Spec | Description | Depends On |
|---|------|-------------|------------|
| 01 | Config Foundation | Add `anchor`, `repositories`, `hosts` blocks to `.autoresearch.json` and loaders in `vault_config.py`, all backward-compatible. | - |
| 02 | Anchor Model | Support an anchor set (individual or couple) and key generation counting on the set instead of a single subject. | 01 |
| 03 | Source Locator Model | Represent a source as one record with one or more `host:locator` pairs; rewrite `harvest_sources.py` to count distinct records; rename the sources bullet. | 01 |
| 04 | Repository Write-Back | Make write-back a configured set of repositories, each with its own auth and a per-target privacy gate driven by target visibility. | 01, 03 |

## Interface Summary
Spec 01 produces the three config blocks and their loaders. Spec 02 consumes `anchor`. Spec 03 consumes `hosts` and produces the record/locator grammar plus a provider-neutral coverage metric. Spec 04 consumes `repositories` and the Spec 03 locator model to route source and person write-backs to any enabled target under the correct privacy gate.

## Non-goals
- No database. The vault stays flat Markdown; the record/locator model is a bullet convention, not a schema migration.
- No new provider integrations are built here (no Ancestry or WikiTree API client). This lane defines the model and gates; a specific provider's write client is a later lane.
- No renumbering of existing generations. A couple anchor and any conversion from individual to couple must leave existing generation numbers unchanged.
