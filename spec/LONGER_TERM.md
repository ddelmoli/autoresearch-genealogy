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

## WikiTree-shaped identifier detection in `privacy-audit-repo`

**Parked 22 JUL 2026**, the day the identifier scan shipped.

`privacy-audit-repo` flags the FamilySearch PID shape (`ABCD-123`) and allows
recognised placeholders. It does **not** flag the WikiTree shape, `Surname-Number`.

- **Why it is parked:** that shape is structurally identical to ordinary prose in
  these documents. `Pre-1800`, `Post-1906`, `Phase-1`, `Gen-2` all match it, and in
  the tracked tree they outnumber real ids by more than ten to one. A check that
  fires on prose is worse than no check, because it teaches you to skim past the
  one run that matters.
- **The gap is real, not theoretical.** A WikiTree id (`Surname-48` in its scrubbed
  form) survived the same manual pre-push review that caught four FamilySearch
  PIDs. It was found afterwards, by grep, by luck.
- **The route, if taken:** an allowlist of known-prose prefixes — `Pre`, `Post`,
  `Phase`, `Gen`, `Q`, `Spec`, `Tier` — rather than a cleverer regex. Measure it the
  way the PID scan was measured: enumerate every match in the tracked tree FIRST and
  confirm the check would ship at zero findings. A privacy check that arrives with a
  backlog of findings will be muted, and then it protects nothing.
- **Trigger:** a real WikiTree id appearing in the repo again, or adopting a second
  identifier vocabulary (Ancestry, Geni, FindaGrave) — at which point one shared
  "is this an external record pointer?" rule is worth building once.
- **Risk to design around:** the allowlist is a maintenance surface that grows
  quietly and fails open. Prefer few prefixes and a comment naming each.

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

---

## `DATE_DRIFT` coverage: the 15 header-missing medieval entries

**Parked 22 JUL 2026**, when the residue was cleared and the gate was promoted to
blocking.

`DATE_DRIFT` compares the meta date FIELD against the header parenthetical and is
at 0. Its coverage line reports 15 entries where the field exists but no year can
be resolved from the header, so the two sides cannot be compared at all.

- **Cause:** those headers carry medieval 3-digit years (`c.985/990`), and
  `gdate.resolve_year`'s layer-3 fallback is deliberately 4-digit only.
- **Why it is parked:** widening the fallback to 3 digits was measured and
  **rejected** — it reads Italian atto numbers such as `534` as death years. The
  fallback is a heuristic over prose, and prose is full of small numbers. The
  entries themselves are correct; only the cross-check is unavailable.
- **The route, if taken:** a narrower rule scoped to the header slot rather than to
  the value grammar — e.g. accept a 3-digit year only when the entry's own field
  already resolves to a 3-digit year, so the comparison is opt-in per entry and can
  never invent one. Measure with the standing 0-loss diff.
- **Trigger:** medieval entries gaining enough new dates that 15 becomes a number
  worth caring about, or a drift bug being found in exactly that population.
- **Risk to design around:** this is a gap in a CHECK, not in the data. Do not
  "fix" it by loosening the parser everything else depends on.
