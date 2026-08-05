---
name: person-entry
description: Write, edit, or migrate a person record in a genealogy vault — the `- meta:` block grammar, minting vault ids, the bold-name header grammar, GEDCOM 7 date fields, and the entry-boundary rules. Use whenever adding a person to a Family_Tree file, editing an existing entry's vitals/parents/spouse/external ids, or converting between the narrative and file person models.
---

# Writing a person record

Two storage models exist; `person_model` in the vault's `.autoresearch.json` selects
one. Read it through `scripts/person_store.py` (`iter_people` / `write_person`),
never by parsing files directly.

- **`narrative`** — many people per lineage file, each a bold-name entry whose first
  body bullet is a `- meta:` YAML flow-mapping.
- **`file`** — one Markdown file per person, YAML frontmatter.

They encode the same fields and are inter-convertible with
`scripts/convert_person_model.py`. Runbook: `workflows/switch-person-model.md`.

## Before you write

1. **Grep the target file for the name** — merge into an existing entry rather than
   creating a second one. Identity is the meta `id`, never a name or external PID.
2. **Read the `- **Prior work**` bullet** under the entry's `- meta:` line. It lists
   the sessions that already touched this person, newest first. Re-deriving finished
   work is this vault's dominant measured failure.
3. **Determine `generation` by tracing the shortest path from Gen 1** — do not infer
   it from the section an entry "feels like" it belongs in, and write it explicitly.

## The three grammars

| What | Where the full spec lives |
|---|---|
| The `- meta:` field vocabulary and every key's semantics | `CLAUDE.method.md` § "Person entry meta block" |
| The bold-name header (date slot, place, free prose) | `workflows/header-grammar.md` § "Writing a header by hand" |
| `born` / `died` as GEDCOM 7 `DateValue` | `workflows/structured-dates.md` § "Writing a date by hand" |

Copy-paste shapes: `vault-template/templates/person_narrative.md` and
`vault-template/templates/person.md`.

## Ids

**Never type a `P-` id** — not from memory, not as a placeholder. The order is:
write the entry with no id → `python3 scripts/mint_ids.py --apply` → read the minted
id back from the file → wire any edges that reference it. A deleted entry's id is
retired, never reused.

## Verify before committing

```bash
python3 scripts/gen_person_index.py --integrity   # HARD: DUP_ID, MISSING_ID, DUP_META_KEY
python3 scripts/entry_boundary_audit.py           # HARD: ENTRY_MISATTRIBUTION
python3 scripts/prose_audit.py                    # BLOCKING: DATE_DRIFT
python3 scripts/build_edges.py --validate         # structural edge violations
```

The vault pre-commit hook enforces these. When `entry_boundary_audit` fires, the
fault is in the parser — do not rewrite the narrative to appease it.

## Related

- `audit-gates` skill — what each gate means and what a non-zero reading implies.
- `source-harvest` skill — the `- **Sources**` bullet grammar and what counts as a record.
