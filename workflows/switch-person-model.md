---
type: workflow
created: 2026-07-07
tags: [workflow, person-model, conversion, maintenance]
---

# Switching a vault's person model (file ⇄ narrative)

A vault stores each person in one of two on-disk encodings, chosen by
`person_model` in `.autoresearch.json` (shape reference:
`vault-template/.autoresearch.example.json`; the record model and the meta-block
grammar are documented in `CLAUDE.method.md`):

- **`file`** (default) — one `type: person` Markdown file per person.
- **`narrative`** — many people per `Family_Tree*.md`, each a `- meta:` entry.

Both hold the same `PersonRecord` fields, so conversion round-trips without data
loss on the modeled fields (id, name, born/died, generation, evidence_tier,
profile_status, life_status, external ids, parents/spouse/flags, and sources).
`scripts/convert_person_model.py` does the conversion; `scripts/person_store.py`
is the seam both models share.

## 1. Check the current model and prove it round-trips

```
# which model is this vault on?
AUTORESEARCH_VAULT=/path/to/vault python3 scripts/vault_config.py /path/to/vault | grep person_model

# round-trip proof for the vault's configured model (src -> other -> src).
# Reports field + source mismatches; 0/0 = lossless. Read-only (temp dirs).
AUTORESEARCH_VAULT=/path/to/vault python3 scripts/convert_person_model.py --check
```

Run `--check` FIRST. If it reports mismatches, stop and investigate before
converting — a non-lossless case means a record uses a shape the converter does
not yet handle (e.g. a vitals string containing the header-paren delimiters).

## 2. Convert (dry-run, then apply)

The converter WRITES the other model's files into a fresh destination directory;
it does not mutate the source. Convert into an empty dir, review, then swap.

```
# narrative vault -> file model (dry-run: reports the record count)
python3 scripts/convert_person_model.py --from narrative --to file \
    --src /path/to/vault --dst /tmp/vault-as-file

# apply (writes one type:person file per person into --dst)
python3 scripts/convert_person_model.py --from narrative --to file \
    --src /path/to/vault --dst /tmp/vault-as-file --apply
```

Reverse (`--from file --to narrative`) writes a single gen-sorted
`Family_Tree_Converted.md`. Conversion is idempotent — the same input produces
byte-identical output.

## 3. Adopt the converted vault

1. Move the converted person files into the vault (replacing the old model's
   files), OR point a new vault at `--dst`.
2. Set `person_model` in the vault's `.autoresearch.json` to the NEW model.
   **This must match the on-disk layout** — the seam dispatches on it, so a
   mismatch makes `iter_people` read the wrong backend (and return nothing).
3. Re-run the gates:
   ```
   AUTORESEARCH_VAULT=/path/to/vault python3 scripts/gen_person_index.py --integrity
   # narrative vaults also:
   AUTORESEARCH_VAULT=/path/to/vault python3 scripts/check_narrative_privacy.py
   ```
4. Commit in the vault repo; the pre-commit re-runs the integrity gate.

## Notes

- **File layout is not round-trip-significant** — identity is the `PersonRecord`,
  not the bytes. A file→narrative→file trip preserves every modeled field but not,
  e.g., a hand-written `family:`/`created:` frontmatter key the record model does
  not carry, nor the exact file names.
- **Keep `person_model` and the on-disk layout in lockstep.** They are a pair.
- **The narrative model is for large, multi-source trees** (many people per
  lineage file keeps a big tree navigable); the **file model is the simpler
  default** and the better fit for a small or new vault, where one file per
  person stays easy to read and edit by hand.
