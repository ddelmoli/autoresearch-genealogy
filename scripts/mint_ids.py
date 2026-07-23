#!/usr/bin/env python3
"""mint_ids.py — seed a vault-owned internal person id into every `- meta:` block.

Phase 1 of the internal-ID model (see memory project_person_index_retirement):
the vault gets its OWN primary key per person, decoupled from FamilySearch (and
ready to carry WikiTree/Ancestry/etc. as interchangeable external-id attributes).

Format: `P-` + 6 Crockford base32 chars (no I/L/O/U) -> ~1e9 space, collision-checked.
Inserted as the FIRST meta field, purely additive. Handles BOTH meta grammars:
    v3 flow-mapping:  - meta: {id: P-7K3QM2, evidence_tier: strong_signal, ...}
    legacy:           - meta: id: P-7K3QM2; FS: XXXX-XXX; tier: S; gen: 6

Idempotent: meta blocks that already carry an `id:` KEY are left alone. The
check is keyed on the `id:` field, not on any `P-xxxxxx` token in the body —
Phase-2 metas carry OTHER people's ids in `parents:`/`spouse:` edge lists, and
a bare-token check mistook those for the entry's own id and refused to seed
(a bug fixed 02 JUL 2026 where an entry with parent/spouse edges was skipped).
Dry-run by default; --apply writes (per-file .bak).
"""
import os, sys, random, argparse
SD=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SD)
import vault_config
import person_store as ps                                # Spec 05: write through the seam
VAULT=vault_config.resolve_vault_optional()  # None => no vault; main() re-raises
ALPHABET="0123456789ABCDEFGHJKMNPQRSTVWXYZ"          # Crockford base32 (no I L O U)

def existing_ids():
    """Every person id already in the vault — OWN ids plus the ids referenced in
    parents/spouse edge lists — so a mint never collides. Model-agnostic (reads
    through the seam), so this works on a file OR narrative vault."""
    ids=set()
    for r in ps.iter_people(VAULT):
        if r.id:
            ids.add(r.id)
        for e in list(r.parents or [])+list(r.spouse or []):
            ids.add(str(e).rstrip("?"))
    return ids

def mint(taken):
    while True:
        c="P-"+"".join(random.choice(ALPHABET) for _ in range(6))
        if c not in taken:
            taken.add(c); return c

def main():
    vault_config.require_vault(VAULT)
    ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true"); a=ap.parse_args()
    taken=existing_ids()
    print(f"existing ids already present: {len(taken)}")
    records=list(ps.iter_people(VAULT))
    idless=[r for r in records if not r.id]
    seeded=0
    for r in idless:                          # purely additive: only touches idless entries
        r.id=mint(taken)
        if a.apply:
            ps.write_person(VAULT, r)          # surgical insert of `id` as the first meta key
        seeded+=1
    print(f"person records: {len(records)}  | already had id: {len(records)-len(idless)}  | newly seeded: {seeded}")
    print(f"{'APPLIED' if a.apply else 'DRY-RUN (use --apply)'}")

if __name__=="__main__": main()
