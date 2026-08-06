---
name: audit-gates
description: Run and interpret the vault audit suite — which gates are HARD versus advisory, what a non-zero reading means, and how to investigate one. Use when a gate fires, when a session-start banner value moves off its baseline, when a commit is blocked by the pre-commit hook, or when deciding whether a count is a regression or a backlog.
---

# Reading the gates

Point the toolkit at a vault first — there is **no default vault**:

```bash
export AUTORESEARCH_VAULT=/path/to/vault
```

## The standing rule

**A gate at baseline 0 is a REGRESSION when non-zero, not a backlog.** The
session-start banner reports every gate against its baseline
(`<vault>/.audit_baseline.txt`). A value that moves UP is the signal; investigate it
rather than absorbing it.

Some gates are **non-zero by design** and only up-movement matters. The baseline file
says which, and why. Read it before treating a count as damage.

## HARD gates — these block a commit

| Gate | Command |
|---|---|
| Unique + complete ids | `gen_person_index.py --integrity` (DUP_ID, MISSING_ID, DUP_META_KEY) |
| Entry ownership | `entry_boundary_audit.py` (ENTRY_MISATTRIBUTION) |
| Header/field date agreement | `prose_audit.py` (DATE_DRIFT) |
| Header grammar on changed lines | `header_audit.py --changed-only` |

## Advisory gates

`header_xref_audit.py`, `meta_presence_audit.py`, `dup_name_audit.py`,
`gen_heading_audit.py`, `frontmatter_audit.py`, `build_edges.py --validate`
(PARENT-GEN MISMATCH, GEN_COLLAPSE, ADJUDICATED_STALE, ADJUDICATED_UNEXPLAINED,
BANKED_STALE), `handoff_lint.py`, `source_symmetry_audit.py`
(SPOUSE_ASYMMETRY, DESCRIBED_NOT_NEGATED).

**`source_symmetry_audit.py` finds sources the vault OWNS but has not APPLIED**, and
is the one advisory check whose non-zero reading is expected rather than tolerated:

- **SPOUSE_ASYMMETRY** — a marriage locator cited on one spouse and not the other. A
  marriage documents both parties, so most rows are an **uncited opportunity**, not a
  defect. Cite it on both, or record why not.
- **DESCRIBED_NOT_NEGATED** — a locator the entry's own prose calls non-evidence,
  left without the `~` that stops the census counting it. It found two real
  over-credits on adoption, and it **cannot** tell "this caveat is about this
  locator" from "this line holds a caveat and a real citation at once" — the same
  limit `harvest_sources.sources_bullet_text` documents. **Read the line before
  adding a `~`.**

Run it after a source harvest and after citing any marriage. It is not in the
SessionStart banner.

## Three things that go wrong when reading a gate

1. **A gate reporting 0 may be blind, not clean.** If a count never moves, diff the
   entry pattern it matches against `person_store`'s. Two readers of one entry
   disagreeing is how several real defects surfaced.
2. **A mechanical check yields CANDIDATES, not findings.** Open the flagged rows
   before acting. Several gates carry known false-positive rates; the baseline file
   records them.
3. **Never bulk-declare rows to drive a count to 0.** A declaration inherits the
   correctness of its reason. Driving the number down destroys the signal the gate
   exists to give — this applies to `PARENT-GEN MISMATCH`, the frontier, and every
   allowlist.

## Whole-suite run

```bash
bash scripts/session_audit.sh          # the full banner; also runs at SessionStart
bash scripts/privacy-audit-repo        # must report ok before any push
```

`privacy-audit-repo` is enforced by the framework repo's pre-commit hook, and must
pass before pushing — the framework fork is public and the vault is not.

## Related

- `person-entry` skill — the write-side rules the HARD gates enforce.
- `session-loop` skill — where in a sitting each gate is read.
