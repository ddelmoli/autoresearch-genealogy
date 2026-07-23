# LONGER-TERM OPTIONS (parked, not queued)

Framework work that is **deliberately deferred**. Revisit on purpose; do NOT let a
session drift into these because one looked easy while doing something else.

**Where things go.** Work inside an active lane belongs in that lane's
`progress.md`, under its "Still open, deliberately" heading. This file is for items
with **no lane** — a deferred decision that would otherwise survive only in a code
comment or a chat log, which is how a rationale gets lost and then re-litigated
from scratch six months later.

**What an entry must carry.** Not a to-do line. Each one records what already
exists, the trigger that would make it worth doing, **why it is parked**, and the
risk to design around *before* starting. If an item cannot justify that much, it is
probably either a bug (fix it) or noise (drop it).

**Anti-rot rule.** When an item is picked up it graduates into a lane and is
**deleted from this file** — no tombstone. The vault learned this the hard way with
`.audit_baseline.txt`, which grew five dated addenda that each superseded the last
until the top of the file was actively wrong. A parked-options list rots the same
way. If this file passes roughly a dozen entries, that is the signal to prune it,
not to add a heading.

---

## GEDCOM 7 beyond the date slot: marriage events, roles, and identifiers

**Parked 23 JUL 2026**, when the header-grammar lane was opened and the operator
asked whether marriage and place conventions should come along with it. They were
measured in the same pass. The **`PLAC` jurisdiction ordering graduated** into that
lane's R6; everything below did not, and this records why so the survey is not
repeated from scratch.

**Marriage is the largest unstructured fact class in the vault**, and the gap is
not subtle:

| | |
|---|---|
| marriage mentions in narrative prose | **1,667** |
| entries carrying a `spouse` edge | 652 of 1,165 (55%) |
| structured marriage **date or place** | **0** |
| ad-hoc `marriage:` prose bullets | ~20, each a different shape |

The `spouse` edge records *who* and never *when* or *where*. Those ~20 bullets are
a dialect forming in real time — the same pathology the header lane exists to
correct, one level down, which is the argument for settling it before it reaches
1,667 instances.

- **The blocker is architectural, not syntactic.** GEDCOM 7 puts marriage on the
  **`FAM` record** (`MARR`, plus `ENGA`, `MARB`, `MARC`, `MARL`, `MARS`, `DIV`,
  `DIVF`, `ANUL`, each with `HUSB.AGE` / `WIFE.AGE`). This vault has no family
  record at all. So the first decision is denormalised marriage fields on both
  partners (drifts, needs a gate, cheap) versus a real family record (correct,
  and a large change to `person_store`, the narrative model and every consumer).
  **Writing a marriage grammar before making that call would repeat exactly the
  mistake the header lane was opened to avoid.**
- **Why it is parked:** the header lane is mid-flight and its Spec 04 migration
  depends on a 0-loss discipline that a second concurrent content change would
  compromise. Also, a `FAM` record is plausibly a larger change than the whole
  header lane.
- **Trigger:** the header lane closing; or the ad-hoc `marriage:` bullet count
  growing past roughly 50, at which point the dialect is cheaper to prevent than
  to migrate.
- **Risk to design around:** denormalising onto both partners creates two stores
  for one fact, which is the drift integrity rule 7 exists to police and which
  the date work already had to gate once. Decide the record shape first.

**`ASSO` / `ROLE` is a weaker fit than it looks.** The vault already uses the
vocabulary — 355 role mentions in prose: witness 144, declarant 125, informant 67,
officiant 9, godparent / sponsor / godmother 10.

- The GEDCOM 7 `ROLE` enumeration is `CHIL, CLERGY, FATH, FRIEND, GODP, HUSB,
  MOTH, MULTIPLE, NGHBR, OFFICIATOR, PARENT, SPOU, WIFE, WITN, OTHER`.
- **The vault's two most common roles, declarant and informant (192 of 355), have
  no GEDCOM equivalent** and would be `OTHER` + `ASSO.PHRASE`. The standard buys
  less here than the vocabulary overlap suggests.
- **Why it is parked:** `Witness_Network.md` is 55 lines against 355 prose
  mentions, so the immediate gap is *research capture*, not grammar. Structuring
  a store that is 15% populated optimises the wrong end.
- **Trigger:** the witness network being worked as a research lane in its own
  right, at which point the roles want a shape before the rows are written.

**`EXID` and `RESN` are already there in substance.** `fs` / `wt` / `anc` are
structurally `EXID` + `TYPE`; `life_status: living` is `RESN` (`CONFIDENTIAL`,
`LOCKED`, `PRIVACY` — a `List:Enum`, so combinable). Adopting the names is
documentation with zero migration, which is also why it is not urgent.

- **Risk to design around:** `RESN` is a *restriction* marker and `life_status` is
  a *fact*. They correlate today only because the privacy gate keys on the fact.
  Renaming one to the other would quietly move the privacy decision out of
  `privacy_gate.py`, which is the one place `CLAUDE.method.md` insists it live.

**One mapping examined and REJECTED: `evidence_tier` to `QUAY` 0-3.** `QUAY` rates
how well a *source citation* supports a claim; `evidence_tier` rates the
*conclusion*. They sit at different levels, and collapsing them would let a single
strong citation silently promote a speculative conclusion. This is a category
error, not a deferred task — do not revisit it as though it were merely unfinished.

---

## Upstream contribution posture

**Parked 22 JUL 2026** (operator decision for the structured-dates lane: "nothing
upstream yet"), and unchanged by the fork's public push the same day.

This fork has diverged substantially: a person-record seam, a date grammar, a
migration tool, six audit gates and 376 tests that
[upstream](https://github.com/mattprusak/autoresearch-genealogy) has no equivalent
of. Most of it is fork-specific and should stay here. Three pieces are not.

- **`scripts/gdate.py`** — a leaf module, pure standard library, zero vault
  knowledge. It is the cleanest candidate by a distance.
- **`validate-genealogy-vault.rb`'s `exact_date?` hardening** — a genuine bug fix
  for any consumer: the check recognised ISO dates only, so a date in any other
  notation silently stopped counting as exact for a living person.
- **`validate-repo`'s scope fix** — also a genuine upstream bug. It enumerated the
  working tree, so anyone keeping a vault or local drafts inside their checkout got
  findings for files the repository does not own. That was 21 of 23 findings here.
- **Why it is parked:** upstream has been quiet, and a PR that sits open is worse
  than no PR — it splits the source of truth while changing nothing. Also, the
  date-field work changes the meaning of upstream's existing `born`/`died` keys
  (option A), which needs a conversation, not a drive-by patch.
- **Trigger:** upstream showing signs of life, or a second consumer of this fork
  appearing, at which point shared code wants a shared home.
- **Risk to design around:** these three have accumulated fork-specific
  cross-references (spec paths, `AUTORESEARCH_VAULT`, house conventions). Sending
  them upstream means genuinely decoupling them first, not just copying the file.
