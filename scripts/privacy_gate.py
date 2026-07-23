#!/usr/bin/env python3
"""privacy_gate.py — Spec 04 (multi-anchor-multi-repo): per-target write-back gate.

The living-person privacy rule is NOT a blanket "skip living" — it is a function
of (life_status, target visibility):

    a PUBLIC target  (a shared tree: FamilySearch, WikiTree)  -> deny living/unknown
    a PRIVATE target (a personal tree: an Ancestry-style tree) -> may include them

Today's blanket rule is exactly the public column; the private column is what the
decoupling adds. Getting this wrong leaks living-person data to a public tree, so
EVERY write path (person add, relationship, source attach) resolves its target and
calls the gate HERE, rather than restating the rule in prose where it can drift.

Design:
- Fail CLOSED: an unrecognized visibility, or a missing life_status, denies.
- A write TARGET is a repository whose `write.enabled` is true (from the Spec-01
  `repositories` registry via vault_config.get_repositories). A repo that is not a
  write target (e.g. WikiTree shipped disabled) is refused before the gate.
- The repository id IS the meta external-id key (`fs`/`wt`/`anc`), so a person
  write-back records the new id under meta[repo_id].

Usage:
    import privacy_gate as pg
    ok, reason, target = pg.gate(vault_dir, "fs", life_status)
    if ok: ...write...
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config

# life_status values withheld from a PUBLIC target (the conservative gate).
PUBLIC_DENY = frozenset({"living", "unknown"})
VALID_VISIBILITY = frozenset({"public", "private"})


def may_write(life_status, visibility):
    """(allowed, reason) for writing data about a person of `life_status` to a
    target of `visibility` ('public' | 'private'). Fails closed."""
    ls = (life_status or "unknown").strip().lower()
    vis = (visibility or "").strip().lower()
    if vis not in VALID_VISIBILITY:
        return (False, f"unknown target visibility {vis!r} — refusing (fail closed)")
    if vis == "public" and ls in PUBLIC_DENY:
        return (False, f"{ls} person withheld from a public target")
    return (True, f"{ls} person allowed to a {vis} target")


def resolve_write_target(vault_dir, repo_id="fs"):
    """(target_dict, reason) for repo_id if it is a WRITE target, else (None, why).
    Reads the Spec-01 `repositories` registry."""
    repos = vault_config.get_repositories(vault_dir)
    target = repos.get(repo_id)
    if target is None:
        return (None, f"no repository {repo_id!r} in .autoresearch.json repositories")
    write = target.get("write") or {}
    if not write.get("enabled"):
        return (None, f"repository {repo_id!r} is not a write target (write.enabled is false)")
    return (target, "ok")


def gate(vault_dir, repo_id, life_status):
    """Resolve the target AND apply the person gate. Returns
    (allowed, reason, target_dict). `repo_id` doubles as the meta external-id key
    to record a new PID under (meta[repo_id])."""
    target, why = resolve_write_target(vault_dir, repo_id)
    if target is None:
        return (False, why, None)
    visibility = (target.get("write") or {}).get("visibility", "public")
    allowed, reason = may_write(life_status, visibility)
    return (allowed, reason, target)


def write_targets(vault_dir):
    """List repo ids that are write-enabled (for a prompt to enumerate targets)."""
    repos = vault_config.get_repositories(vault_dir)
    return [rid for rid, r in repos.items() if (r.get("write") or {}).get("enabled")]


if __name__ == "__main__":
    # CLI: print the gate decision for each life_status against each write target.
    vault = vault_config.resolve_vault(sys.argv[1] if len(sys.argv) > 1 else None)
    repos = vault_config.get_repositories(vault)
    print(f"write targets: {write_targets(vault)}")
    for rid in repos:
        for ls in ("deceased", "living", "unknown"):
            ok, reason, _ = gate(vault, rid, ls)
            print(f"  {rid:<6} {ls:<9} -> {'ALLOW' if ok else 'DENY '}  ({reason})")
