#!/usr/bin/env python3
"""
Shard-manifest loader for sharded family-tree vaults.

A growing tree is typically capped at N generations in `Family_Tree.md` and the
rest split into branch/region files (`Family_Tree_<Region>.md`). Rather than
hardcode any particular project's shard names, the audit scripts read an
OPTIONAL manifest declared inside `Family_Tree.md`: a markdown table that has a
`File` column and a `Region` column. Each row maps a shard file to the region
label the scripts should group it under.

Example (place anywhere in Family_Tree.md):

    ## File Index

    | File | Region | Content |
    |---|---|---|
    | [[Family_Tree_Maternal_Highland]] | Highland | ... |
    | [[Family_Tree_Paternal_Coastal]]  | Coastal  | ... |
    | [[Family_Tree_Colonial_North]]    | Colonial | ... |

Behavior:
- If `Family_Tree.md` (or the File/Region table) is absent, `load_shard_manifest`
  returns {} and `region_for` falls back to a generic label. The scripts still
  run on a single un-sharded `Family_Tree.md` with no configuration.
- `region_for` matches a Person_Index section header (a shard file basename) to
  the LONGEST manifest key that is a prefix of it, so a master entry
  (`Family_Tree_Maternal`) covers its children (`Family_Tree_Maternal_Highland`)
  without listing each, while a more specific entry
  (`Family_Tree_Paternal_Coastal`) overrides a broader one
  (`Family_Tree_Paternal`).

This module is data-driven and contains no project-specific names, so it is
safe to contribute upstream; the actual shard->region mappings live in the
vault's Family_Tree.md.
"""

import os
import re

# Generic label for the un-sharded main file (and any shard not in the manifest
# whose name still begins with the family-tree prefix).
MAIN_REGION = "Family_Tree (main)"
OTHER_REGION = "Other"
TREE_PREFIX = "Family_Tree"

_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")


def _cells(line: str):
    """Split a markdown table row into trimmed cell strings."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _normalize_file(cell: str) -> str:
    """Reduce a File-column cell to a bare shard basename.

    Handles `[[Family_Tree_X]]` wikilinks, `Family_Tree_X.md`, backtick-wrapped
    names, and markdown links `[label](path)`."""
    s = cell.strip()
    # markdown link [text](target) -> prefer the link text
    m = re.match(r"\[([^\]]+)\]\([^)]*\)", s)
    if m:
        s = m.group(1)
    s = s.strip("`").strip()
    s = s.replace("[[", "").replace("]]", "")
    s = re.sub(r"\.md\b", "", s)
    # drop any leading path
    s = s.rsplit("/", 1)[-1]
    return s.strip()


def load_shard_manifest(vault_dir: str) -> dict:
    """Parse `<vault>/Family_Tree.md` for a File/Region table.

    Returns {shard_basename: region}. Empty dict if no manifest is found."""
    path = os.path.join(vault_dir, "Family_Tree.md")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        lines = f.readlines()

    manifest: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line:
            headers = [c.lower() for c in _cells(line)]
            if "file" in headers and "region" in headers:
                file_idx = headers.index("file")
                region_idx = headers.index("region")
                i += 1
                # skip the |---|---| separator row if present
                if i < len(lines) and _SEPARATOR_RE.match(lines[i]):
                    i += 1
                # consume contiguous table rows
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    cells = _cells(lines[i])
                    if len(cells) > max(file_idx, region_idx):
                        fname = _normalize_file(cells[file_idx])
                        region = cells[region_idx].strip()
                        if fname and region:
                            manifest[fname] = region
                    i += 1
                break
        i += 1
    return manifest


def region_for(section: str, manifest: dict) -> str:
    """Classify a Person_Index section header (shard basename) into a region.

    Longest-prefix match against the manifest; generic fallback otherwise."""
    section = section.strip()
    best_key = None
    for key in manifest:
        if section == key or section.startswith(key + "_"):
            if best_key is None or len(key) > len(best_key):
                best_key = key
    if best_key is not None:
        return manifest[best_key]
    if section.startswith(TREE_PREFIX):
        return MAIN_REGION
    return OTHER_REGION
