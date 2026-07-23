# Shard Split Workflow (splitting an oversized Family_Tree shard)

When a `Family_Tree*.md` shard grows large enough that tools read it fully into
context on every pass, split it. This workflow covers the **semantic** decision
(what to split, and where) and the **mechanical** move (done safely by
`scripts/split_shard.py`).

## When to run this

- A shard exceeds your size threshold. If you use the housekeeping heartbeat
  (`scripts/size_heartbeat.py` + `vault/.maintenance.json`), it flags oversized
  shards as a "split-shard" item in the SessionStart Vault Housekeeping menu.
- Measure in **tokens, not lines**: a few hundred dense narrative lines can be
  tens of thousands of tokens. `scripts/archive_sections.py --list` and the
  heartbeat both report token sizes.

## Step 1: decide whether to split at all (semantic)

Not every large shard should be split. Two shapes:

- **Multi-cluster shard** (several distinct families/places that rarely interact
  during research): a strong split candidate — separate by cluster. This is the
  classic case (e.g. a colonial file holding four unrelated branches).
- **Single coherent lineage** (one family climbing many generations): splitting
  fragments one pedigree across files. Often the better move is to leave it and
  raise the threshold, OR split by a natural generation seam (recent/living core
  vs deep deceased origins). Don't split a coherent line just to chase a number.

Use `scripts/tree_locator.py` to see what's actually in the shard before deciding.

## Step 2: choose the boundary

- **Cluster split:** pick which `### Generation N` blocks (and any `##` sections)
  belong to each new shard. This may need hand-editing if clusters interleave.
- **Generation-range split:** pick a contiguous range `[gen-min, gen-max]` to carve
  out (e.g. the deep, all-deceased generations), leaving the recent core in place.
  This is what `split_shard.py` automates.

Give the new shard a name following your convention
(`Family_Tree_<Region>_<Branch>.md`), a Region label, and a one-line Content
description for the File Index manifest.

## Step 3: carve it mechanically (generation-range case)

```
python3 scripts/split_shard.py --source Family_Tree_<X>.md \
    --gen-min N --gen-max M --dest Family_Tree_<X>_<Branch>.md \
    --region <Region> --content "<one-line manifest description>"
```

Dry-run by default. It reports the blocks + person `meta` blocks that would move and
a **meta-conservation check** (every `id` preserved + unique across source+dest);
it refuses to apply if that check fails. Re-run with `--apply` to:

- move the in-range `### Generation N` blocks (each person's `- meta:` block travels
  intact — ids are never changed or re-minted);
- leave a cross-reference stub in the source where they were, and a "split from"
  note + back-link in the new shard's header;
- add a File Index manifest row for the new shard;
- snapshot every touched file first (under `Shard_Split_Archive/`).

Only `### Generation N` blocks in range move; other `##` sections and out-of-range
generations stay in the source — move those by hand if the split calls for it.

## Step 4: review + commit

- Update the **source shard's** File Index row (its generation range / content now
  that part of it moved) — the tool adds the new row but leaves the source row for
  you to adjust.
- Confirm the new shard is grouped correctly by `scripts/tree_locator.py --by-file`.
- Commit. The pre-commit integrity gate (`gen_person_index.py --integrity`) runs on
  the result — every entry must still have a unique `id` + complete meta. Because the
  carve moves whole blocks verbatim, this normally passes by construction.
