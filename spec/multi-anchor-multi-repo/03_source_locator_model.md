# Spec 03: Source Locator Model
**Goal:** Represent a source as one underlying record plus one or more host locators, so the vault can say where a source is hosted and record a single record that lives in several places. Make the coverage metric count distinct records rather than locator tokens.
**Depends on:** 01

## Design notes
- Two layers. A *record* is the abstract primary source (for example "1920 US Census, ED 42, Smith household"), the unit proof rests on. A *locator* is a `host:id` pointer to where that record is hosted, where `id` is the host-native durable id: an ARK when the host mints one, else the host's stable id or URL, plus a locator kind (indexed, image, transcription, memorial).
- ARK stays the preferred locator form wherever the host issues one, because it is host-independent and its NAAN self-identifies the host. It is not universal: Ancestry (`dbid`), WikiTree, Geneteka, GRONI, FindAGrave, NYC Municipal Archives, and others do not mint ARKs. Do not fabricate ARKs for non-ARK hosts, mirroring today's rule against fabricating ARKs for book citations.
- One record can carry several locators (an FS `1:1:` index ARK, an FS `3:1:` image ARK, and an Ancestry `dbid` all point at one census page). Counting locators double-counts the record; the honest metric counts records.

## Bullet grammar
- Rename the `**FS-attached sources**` bullet to `**Sources**` (it is no longer FS-only). Accept the old label during a transition and provide a migration.
- One sub-bullet per record: a short record descriptor, then an em-dash, then a comma-separated list of `host:locator` pairs.
  - Example: `1920 US Census, Smith hh (Anytown ED 42) - fs:1:1:ABCD-123, fs:3:1:XXXX-YYYY, anc:dbid=6061`
  - Example: `Antenati 1847 birth atto #12 - antenati:ark:/12657/an_ua..., fs:3:1:...`
- `host` ids come from the Spec 01 `hosts` map. A locator whose host is unknown is a validation warning, not a hard error.

## Requirements
- Rewrite `scripts/harvest_sources.py` to parse record sub-bullets and their `host:locator` lists rather than counting raw ARK tokens. The coverage count is the number of distinct records; report a per-host locator breakdown alongside it.
- Preserve the existing category thresholds (SOURCE_GAP 0 records, LOW_COVERAGE 1 to 3, WELL_SOURCED 4 or more) and the STRUCTURAL_GAP allowlist behavior, now counting records.
- Provide a migration for existing narrative bullets (approach b, chosen). Phase A is mechanical and non-destructive: relabel `FS-attached sources` to `Sources`, host-prefix every locator (the host is derivable from the token form), and default to ONE record per locator EXCEPT where a high-confidence multi-locator pattern is detected, which is auto-merged into one record. High-confidence patterns to auto-merge: a `persona`/`household` FS ARK pair on the same census line, and an index (`1:1:`) + image (`3:1:`) pair explicitly cited as the same act. Anything ambiguous is left as separate single-locator records and FLAGGED for human review, never silently merged. No coverage is ever lost. Log every relabel, host-prefix, auto-merge, and flag.
- WikiTree tree assertions remain off-metric by construction: a `wt:` locator counts only when it points at a primary source WikiTree hosts, never at a bare tree profile. Document this as the natural consequence of the record/locator split.

## Files
- Modify: `scripts/harvest_sources.py` (record/locator parser, per-host breakdown, records-based metric)
- Create: a one-time migration path (a `--migrate` mode or a helper) for the bullet relabel, host-prefix, and record grouping. Default dry-run (preview + flagged-ambiguous report); `--apply` writes. Idempotent (re-running on a migrated file is a no-op), so it is safe to run per file during the transition.
- Modify: `CLAUDE.method.md` Rule 8 and the sources-bullet convention
- Modify: `vault-template` person templates and any prompt that writes the sources bullet (`17`, `19`)

## Boundary Map
- **Produces**: the record/locator bullet grammar, a provider-neutral records-based coverage metric, a per-host locator breakdown.
- **Consumes**: `get_hosts` from Spec 01; the narrative roster from `gen_person_index.parse_narrative()`.

## Vault Adoption (measured against the live vault, 06 JUL 2026)

Scale of the live-vault migration:

| Quantity | Count |
|---|---|
| Narrative files with source bullets | 28 |
| `FS-attached sources` bullets to relabel | ~697 |
| FS `1:1:` locator tokens | ~6,958 |
| FS `3:1:` image-locator tokens | ~969 |
| External locators (Antenati/metryki/szukaj/AGAD) | ~29 |
| Total locator tokens | ~7,900 |
| Multi-locator-same-record candidate spots (persona/household, index/image) | ~40+ across ~15 files |

Key safety fact: `harvest_sources.py` counts ARK tokens in the entry BODY, not by the bullet label, so the relabel does not disturb the counter. The literal `FS-attached sources` string is also referenced in the vault's `templates/person_narrative.md` and the local prompts `17`/`19` (which WRITE the bullet); those are updated to emit `Sources`. Archived scripts and `vault/logs/` historical notes are left as-is.

The migration is GRADUAL, not a flag-day, because the parser accepts both grammars transitionally:
- **Phase A (one mechanical pass, this spec):** relabel + host-prefix + one-record-per-locator, with the high-confidence multi-locator patterns auto-merged (approach b). Delivers the host-labeling and multi-host capability immediately. Because most flat lists stay one-record-per-locator, the record count starts approximately equal to the old locator count; the metric becomes provider-neutral and host-honest but does not drop yet, except for the auto-merged high-confidence pairs.
- **Phase B (incremental, ongoing, NOT this spec):** hand-group the flagged ambiguous multi-locator cases and, later, the same record cited across FS + Ancestry + WikiTree. This is where "count records not locators" actually tightens the number, burned down opportunistically when a file is edited for other reasons (same pattern as the header-xref backlog).

Non-destructive guarantee: coverage never drops during Phase A; a bullet that fails to parse cleanly is left in the old grammar and flagged, not dropped.

## Acceptance Criteria
- [ ] A record with three locators across two hosts counts as one record, not three.
- [ ] `harvest_sources.py` reports a per-host locator breakdown and unchanged category names.
- [ ] Migration converts existing FS-attached-source bullets with no loss of counted coverage; the run logs each change.
- [ ] Approach b: a high-confidence `persona`/`household` (or index/image same-act) locator pair is auto-merged into one record; an ambiguous multi-locator bullet is left as separate records and flagged, never silently merged.
- [ ] An unknown host in a locator is a warning, not a crash.
- [ ] `scripts/validate-repo` passes under UTF-8 and `LC_ALL=C`.
- [ ] **Vault adoption (Phase A):** the mechanical pass runs over the live vault's ~697 bullets (`$AUTORESEARCH_VAULT`) as a dry-run first, then `--apply`; the relabeled `Sources` bullets + host-prefixed locators + auto-merged high-confidence pairs are committed in the vault repo; `harvest_sources.py` reports no coverage loss (record count starts near the old locator count, minus the auto-merges) and honors the existing structural-gap allowlist. The flagged ambiguous cases are recorded for Phase B, not resolved here.

## Test Plan
- Fixtures: one single-host record, one multi-host record, one legacy flat-ARK bullet, one unknown-host locator, one `persona`/`household` pair (auto-merge), one ambiguous multi-locator bullet (flag, no merge).
- Assert the record count, the per-host breakdown, the warning on the unknown host, the auto-merge of the high-confidence pair, and the flag (not merge) of the ambiguous case.
- Run the migration on a COPY of a real vault file (dry-run then apply) and diff coverage counts before and after: expect no loss, a drop only equal to the auto-merged pairs, and idempotency on a second run.
