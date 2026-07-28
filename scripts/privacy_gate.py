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

# life_status values that AUTONOMOUS RESEARCH must never touch, on any platform.
# Same two values as PUBLIC_DENY, deliberately a SEPARATE name: they answer
# different questions (may I publish this person? vs may I go look this person
# up?) and one could change without the other.
RESEARCH_DENY = frozenset({"living", "unknown"})
# The only value that is affirmatively researchable. Anything else — a typo, a
# vocabulary a future vault invents, an absent field — denies (fail closed).
RESEARCHABLE = frozenset({"deceased"})


def may_research(life_status):
    """(allowed, reason) for AUTONOMOUS WEB RESEARCH about a person of
    `life_status`. Fails closed: an absent or unrecognized value denies.

    THE ONE PLACE THE RESEARCH-SIDE RULE LIVES (added 28 JUL 2026, session #111,
    closing deferred_decisions item 11). The vault's standing rule is that
    autonomous runs must not web-search anyone `living` or `unknown`, and until
    now that rule existed only as PROSE in CLAUDE.method.md while `may_write`
    (the publication-side rule) was the only thing implemented.

    What the prose-only version cost: framework fc6efe2 (26 JUL) re-keyed the
    source-coverage census on the vault `id` instead of the FS PID — a good fix,
    closing a blind spot in which 210 entries reached no category at all. Living
    people are PID-less BY DESIGN (`fs_private_keys`, no `fs`), so they were swept
    into the census with every other non-PID entry: 15 living/unknown people
    landed inside it and 9 of them inside SOURCE_GAP, the bucket this vault's own
    integrity rule 8 documents as "the highest-priority Recipe-S harvest target".
    Recipe-S is a web-research workflow. A session working that worklist top-down
    would have met the operator's own children as targets. Nothing leaked — but a
    worklist that names living people is a defect whether or not it is acted on.

    So every RESEARCH target-set builder calls this, exactly as every write path
    calls `gate`: harvest_sources (the census) and profile_review (the rotation
    bandit) both do. Do not restate the rule inline where it can drift — that is
    how it came to be true in the docs and false in the code.
    """
    ls = (life_status or "unknown").strip().lower()
    if ls in RESEARCH_DENY:
        return (False, f"{ls} person is never web-researched (autonomous research gate)")
    if ls not in RESEARCHABLE:
        return (False, f"unrecognized life_status {ls!r} — refusing (fail closed)")
    return (True, f"{ls} person may be researched")


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
    print("research gate (autonomous web research; no target — the rule is blanket):")
    for ls in ("deceased", "living", "unknown", None):
        ok, reason = may_research(ls)
        print(f"  {str(ls):<9} -> {'ALLOW' if ok else 'DENY '}  ({reason})")
