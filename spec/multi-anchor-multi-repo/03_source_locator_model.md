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
- Provide a migration for existing narrative bullets: today's flat ARK lists become records where derivable, or a single-locator record each where not, so no coverage is lost silently. Log what was migrated.
- WikiTree tree assertions remain off-metric by construction: a `wt:` locator counts only when it points at a primary source WikiTree hosts, never at a bare tree profile. Document this as the natural consequence of the record/locator split.

## Files
- Modify: `scripts/harvest_sources.py` (record/locator parser, per-host breakdown, records-based metric)
- Create: a one-time migration path (a `--migrate` mode or a helper) for the bullet relabel and record grouping
- Modify: `CLAUDE.method.md` Rule 8 and the sources-bullet convention
- Modify: `vault-template` person templates and any prompt that writes the sources bullet (`17`, `19`)

## Boundary Map
- **Produces**: the record/locator bullet grammar, a provider-neutral records-based coverage metric, a per-host locator breakdown.
- **Consumes**: `get_hosts` from Spec 01; the narrative roster from `gen_person_index.parse_narrative()`.

## Acceptance Criteria
- [ ] A record with three locators across two hosts counts as one record, not three.
- [ ] `harvest_sources.py` reports a per-host locator breakdown and unchanged category names.
- [ ] Migration converts existing FS-attached-source bullets with no loss of counted coverage; the run logs each change.
- [ ] An unknown host in a locator is a warning, not a crash.
- [ ] `scripts/validate-repo` passes under UTF-8 and `LC_ALL=C`.
- [ ] **Vault adoption:** the migration runs over the live vault's narrative files (`$AUTORESEARCH_VAULT`), the relabeled `Sources` bullets and `host:locator` lists are committed in the vault repo, and `harvest_sources.py` reports the same or better per-record coverage as before the migration (no silent loss). Run against the vault's existing structural-gap allowlist so exempt entries stay exempt.

## Test Plan
- Fixtures: one single-host record, one multi-host record, one legacy flat-ARK bullet, one unknown-host locator.
- Assert the record count, the per-host breakdown, and the warning on the unknown host.
- Run the migration on a copy of a legacy fixture and diff coverage counts before and after.
