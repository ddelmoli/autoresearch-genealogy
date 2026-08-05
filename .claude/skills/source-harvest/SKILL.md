---
name: source-harvest
description: Research a person across archives and cite what you find — the multi-repository research sweep, the FamilySearch source harvest, the `- **Sources**` record/host:locator grammar, and what does and does not count as a record in the coverage census. Use when harvesting sources for an ancestor, writing or migrating a Sources bullet, deciding whether a citation counts, or working a SOURCE_GAP / UNCITED worklist.
---

# Harvesting and citing sources

**The goal is a complete biography per person; any single online tree is only a sync
point.** The default unit of work is the full multi-resource sweep
(`prompts/25-person-research-sweep.md`), not a single-host harvest. Log every
resource consulted, including the empty ones — a negative result is data.

## Check before searching

Read the entry's `- **Prior work**` bullet, then grep `logs/` and `Open_Questions.md`
for the person, the place, and the route. A route already measured and closed in a
sibling shard is the classic wasted sitting; the `ROUTES ALREADY TRIED IN THIS
LINEAGE` block at the head of each lineage file is the cheap version of that check.

## The citation grammar

One sub-bullet per RECORD, each carrying one or more `host:locator` pairs:

```
- **Sources**
  - 1910 US Census, [PLACE] — fs:1:1:XXXX-XXX
  - 1847 birth atto — antenati:ark:/12657/an_…, fs:3:1:YYYY-ZZZZ
```

- **Name the record.** A locator says *where*; only the description says *what*. A
  census that cannot say what it is counting cannot be audited.
- **The metric counts distinct RECORDS, not locator tokens.** One record on two
  hosts is one record with two locators.
- **A `~` prefix marks a locator that is deliberately NOT evidence** (`~fs:1:1:…`).
  It records the exclusion without crediting it. Suppression happens before any
  counter runs, so every count inherits it.
- `host` ids come from the `hosts` registry — read it with
  `python3 scripts/vault_config.py <vault>`, never from a list written in prose.

## What counts

The include/exclude limbs (a)-(h) — indexed records, image ARKs, external archive
links, books, user trees, memorials, obituaries, named-in and sibling records — are
**policy** and live in `CLAUDE.method.md` integrity rule 8. Read them there; they
are deliberately kept in always-loaded context.

Two screens are mechanical, so call them rather than judging by eye:

```python
harvest_sources.is_book_collection(title)      # digitised books wearing record locators
harvest_sources.is_memorial_collection(title)  # memorial/headstone indexes
```

Both key on the **collection title**, which is only available at harvest time — the
locator form alone cannot tell a register leaf from a book page.

## The FamilySearch leg

`prompts/19-fs-source-harvest.md` is the home for the mechanics: the Detail View
requirement, the Research Help endpoints (which never render under automation), the
Recipe-S loop, the `harvest_sources.py` CLI, and per-region yield calibration.

Two constraints that are policy, not procedure:

- **A hint is a candidate, not a record.** Judge it on identifiers before citing.
- **Attaching anything to a shared public tree is a WRITE, and operator-gated.**
  Reading is free; queue the write as an `FS write-back QUEUED` bullet on the
  person's own entry.

## Audit

```bash
python3 scripts/harvest_sources.py            # SOURCE_GAP / LOW_COVERAGE / WELL_SOURCED
python3 scripts/harvest_sources.py --sources-conformance
python3 scripts/bio_completeness.py           # whether a LIFE has been written
```

A record count is not a biography: thirty locators and no prose is not finished work.

## Related

- `person-entry` skill — where the Sources bullet sits in an entry.
- `audit-gates` skill — reading the census heartbeat in the session banner.
