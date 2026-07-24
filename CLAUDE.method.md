# Method: portable genealogy-vault methodology

The reusable "how" of an autoresearch genealogy vault — conventions, the person
meta-block grammar, integrity rules, and operational style. This file is **vault-
agnostic**: nothing here names a real person, and it is meant to be reused
verbatim across vaults. It is tracked, and `CLAUDE.md` `@import`s it, so a clone
loads it automatically.

**The private half stays local.** Per-client facts — the subject, the
generation-anchor table, a given vault's lineage→file layout — are real family
data, so they live in a `CLAUDE.instance.md` that is gitignored. The convention
is a thin, also-gitignored `CLAUDE.local.md` that `@import`s your instance file;
create one if you want per-vault facts in context. Nothing in this file depends
on either existing. See CONTRIBUTING.md "The framework/private boundary".

## Project Structure

The generic dir roles (`prompts/`, `reference/`, `workflows/`, `vault-template/`) are in **CLAUDE.md** (loaded alongside this file). A working install adds:
- A **vault directory** — the live, populated working tree (Family_Tree files + data). `vault-template/` is the empty starter you copy from; the vault is the instance. Keep it as its own repo (or at least gitignored): it holds real people and must never be committed to the framework repo.
- **Per-vault instance constants live in the vault's `.autoresearch.json`, read via `scripts/vault_config.py` (zero-dependency JSON loader) — NOT hard-coded in the scripts** (extracted 06 JUL 2026 for multi-vault / contract reuse). Covers: the GEDCOM filename (`gedcom`; falls back to the single `*.ged`), and the "structurally unsourceable" allowlists (`structural_gap`: `deep_gen_threshold` + region-scoped `pid_prefixes`/`pids` rules) consumed by `harvest_sources.py` and `build_edges.py`. Also: `anchor` (`kind: individual|couple` + `people[]` = the Gen-1 set; empty `people` synthesizes one person from `subject`; read via `vault_config.get_anchor`), `repositories` (id → read/write auth + `write.visibility`, default FamilySearch-only, a write target ships `enabled:false` unless opted in; `get_repositories`), and `hosts` (source-host registry, `locator_kind: ark|url|id`; `get_hosts`). Also: `person_model` (`file` default | `narrative`) selects how person records are stored on disk — one Markdown file per person (upstream/legacy) vs many people per lineage file, each a bold-name entry with an inline `- meta:` block; read via `vault_config.get_person_model` (an unrecognized value is a hard error, not a silent fallback). **Omit a block to accept its default — do NOT copy the default `repositories`/`hosts` into a vault config just to have them; write only what deviates.** Shape reference: `vault-template/.autoresearch.example.json`. An absent file/key falls back to generic defaults, so a fresh vault runs with zero config. When adding a new per-family constant to a script, put it here behind the loader instead of inlining it. (`session_audit.sh` similarly externalizes its advisory baseline to the vault's `.audit_baseline.txt`.) **Which vault the toolkit operates on** is resolved centrally by `vault_config.resolve_vault()` — precedence `AUTORESEARCH_VAULT` env var → a script's `--vault` arg → (a `../vault` sibling **only if one exists**, else a clear error). **There is NO implicit default vault** — you must say which vault you mean, so one toolkit install drives many vaults: `AUTORESEARCH_VAULT=~/vaults/<name> python3 scripts/gen_person_index.py --integrity`. Export `AUTORESEARCH_VAULT` before launching so the SessionStart audit + pre-commit run against the right vault (the pre-commit auto-points at the vault it is committing). A new per-script `--vault` arg should be wired as `vault_config.resolve_vault(args.vault)`.

## Prompt Format

The 7-field prompt structure (Goal / Metric / Direction / Verify / Guard / Iterations / Protocol) and the `Inputs To Replace` requirement are in **CLAUDE.md**. Addition: prompts use placeholder names `[SURNAME]`, `[ANCESTOR]`, `[LOCATION]`, `[DATE]`, `[VAULT_PATH]`.

## Vault Template Conventions

The **generic** file-frontmatter conventions — the `type`/`created`/`tags` minimum, the person/transcription/region/surname frontmatter fields (incl. `life_status` / `evidence_tier` / `profile_status`), the underscore-filename rule, the wikilink convention, and the `reference/vault-file-manifest.md` core-file names — live in **CLAUDE.md**, which Claude loads alongside this file. They are deliberately NOT restated here, so they cannot drift. (An earlier copy in this file had gone stale at `confidence` vs upstream's `evidence_tier`/`profile_status`; deferring to CLAUDE.md is the fix.)

**Deltas** for a vault on the `narrative` person model (the model this file documents):
- **People are recorded as bold-name NARRATIVE entries with a `- meta:` block** inside `Family_Tree*.md` (see "Person entry meta block" below) — NOT as per-person files. The template is [vault-template/templates/person_narrative.md](vault-template/templates/person_narrative.md); the per-person YAML *file* ([vault-template/templates/person.md](vault-template/templates/person.md)) is the other supported model, and the framework default.
- **Region / surname content is inline** ("Origins and Toponymy" sections within the lineage file), not separate `type: region` / `type: surname` files. **Size exception:** when a lineage file crosses the shard threshold and the Origins prose is the growth, the essay moves to a `Family_Tree_<Region>_Origins.md` companion (a 2-line pointer stays inline in the lineage file).

## Style

The generic style rules (no hyphens-as-punctuation, no emojis, source-first, log negative results, confidence tiers Strong/Moderate/Speculative, living-person privacy) are in **CLAUDE.md**. This vault's additional operational rules:

- Check before searching. Before researching an ancestor, grep `vault/logs/` and `vault/Open_Questions.md` for their name to see what has already been tried. Do not repeat prior negative searches unless using a new source or strategy.
- **Check FS source citations before launching gap-fill scans.** Before running repeated scans of archive registers (Antenati, FamilySearch image collections) for a known person, open that person's FamilySearch profile, click the **Sources** tab, toggle **Detail View** on, and check each source for a "**Web Page (Link to the Record)**" field. Community contributors often paste the direct Antenati ARK to the source image. That image may sit in an adjacent fascicolo (e.g., a matrimoni processetti bundle) containing additional documents (estratti, marriage atti, consent docs) that resolve the question in one drill. Worked example: one ancestor's death date was resolved by a single FS source-link trace after ~1,200 gap-fill register scans had already been run on the wrong hypothesis — check the citations first.
- **Downsize register images before reading them with the Read tool.** Files saved from FamilySearch (`3Q9M-*.jpg`), Antenati, Geneteka, etc. are typically 3000-4500 px wide. The Anthropic API auto-downsizes images to about 1.15 MP for the model but still transmits the full base64 payload, so a 4218×3007 page costs roughly 10× more request bytes than the model actually uses. Multiple Reads of one large image over a long session can push the total request past the 32 MB API ceiling (`request_too_large: 413`). Before Read, run `sips -Z 1500 input.jpg --out /tmp/input-small.jpg` and Read the small copy. **To read a *specific* atto/entry at full cursive detail, crop just that region instead of downsizing the whole page: `magick input.jpg -crop WxH+X+Y /tmp/atto.png` (offset is +X+Y from top-left; optionally add `-resize 180% -normalize -sharpen 0x1` to aid 19th-c cursive), then Read the small crop — full detail for the region of interest at low payload.** ImageMagick 7 is installed at `/opt/homebrew/bin/magick` (PIL/Pillow is NOT installed — use ImageMagick, not Python PIL). If full resolution is genuinely needed across a whole page or for interactive locating, use the localhost-HTTP + browser zoom path instead, which keeps the full-res image out of the conversation context entirely. Incident to avoid: a 4218×3007 jpg Read 10× over one long session pushed the payload past 32 MB and blocked all further prompts with 413 until the file was removed.
- **Declarant-age estimates are ESTIMATES, not facts.** When a vault row's birth year is derived from an Italian (or other) 19th-century atto declarant-age field ("age 47 in 1879" → b.~1832), mark it as an estimate and expect ±2-12 yr outlier from any FS-corroborated birth year. Multiple datapoints across 19th-c Italian collateral rows have shown a consistent ±2-12 yr range, weighted toward 8-12 yr for older collaterals. Always prefer FS-precise birth years over declarant-age-derived estimates when both exist. When matching a declarant-derived vault row against FS Family-tab siblings, expand the age-window match tolerance to ±12 years rather than the usual ±2.
- **Append to the Research_Log "## Session Index" via `scripts/log_session.py`, NEVER via the Edit tool.** The prompts say "append a one-line summary entry to the session index" but name no tool; an Edit forces a full Read of the ~35k-token append-only file just to add one row. Use `python3 scripts/log_session.py --log "logs/YYYY-MM-DD-slug" --summary "..."` (structure-aware: inserts at the bottom of the table, before any trailing section; appends by default, `--dry-run` to preview). This file is append-only — nothing should ever full-read it into context.
- **Resolve an Open_Question with a PLAIN heading + terminal status; do NOT hand-strikethrough it.** When a question is fully resolved, change its heading to `### N. Title — RESOLVED <date> (note)` (terminal status — `RESOLVED` / `RULED OUT` / `CLOSED` / `CONFIRMED FAIL` / `FULLY RESOLVED` — must be the FIRST word *after the last em-dash*, so put any qualifier in parens AFTER it: `— RESOLVED 30 JUN 2026 (pirate detach)`, never `— pirate detach RESOLVED`). Leave the resolution write-up in the body. **Do NOT manually wrap the heading in `~~strikethrough~~`.** When the archiver migrates the block it now **removes the block entirely** and records ONE terse line in a single **`## Resolved & Closed — Index`** section (compact-index model adopted 01 JUL 2026, replacing the old per-question inline struck-heading tombstones — 0 wikilinks depended on the in-file anchors, and 45 scattered struck headings were more clutter than the breadcrumb was worth). A hand-struck heading still migrates fine (detection keys on terminal status, not the `~~`). To sweep resolved entries into `Open_Questions_Resolved.md` (when the file is over its `.maintenance.json` token threshold): `python3 scripts/archive_sections.py --target open-questions` (dry-run) then `--apply` (versioned snapshot to `Open_Questions_Archive/`, idempotent; full text -> Resolved file + one index row -> live file). One-time back-fill of legacy inline tombstones: `--migrate-tombstones` (done 01 JUL 2026: 48 converted).

## Person entry meta block (the machine-readable person record; v3 YAML-flow grammar adopted 24 JUN 2026)

**This section describes the `narrative` person model** (`person_model: narrative` in `.autoresearch.json`) — many people per lineage file, each a `- meta:` entry. The framework also supports the default **`file`** model (one `type: person` Markdown file per person, YAML frontmatter); the two encode the SAME `PersonRecord` fields and are inter-convertible (`scripts/convert_person_model.py`, runbook [workflows/switch-person-model.md](workflows/switch-person-model.md)). All record-consuming tooling reads/writes through the model-agnostic seam `scripts/person_store.py` (`iter_people`/`write_person`, dispatched by `vault_config.get_person_model`); the meta-block grammar below is how the narrative backend spells each field. See spec `optional-person-model`. The file-model spelling of the same fields is the person-file frontmatter (the optional `id`/`generation`/`parents`/`spouse`/`flags` keys added upstream), per the field-map at the end of this section.

The narratives are the single source of truth for people; **`Person_Index.md` was RETIRED and deleted on 24 JUN 2026**. Each person entry in a `Family_Tree*.md` file carries a **machine-readable meta block** as its **first body bullet**, directly under the bold-name header. The gen-sorted roster the old index provided is produced ON DEMAND: `python3 scripts/gen_person_index.py --write /tmp/roster.md`. See `scripts/gen_person_index.py` (generator / `--integrity` gate / `--gap-report`), `scripts/mint_ids.py` (id minter).

Copy-paste template: **[vault-template/templates/person_narrative.md](vault-template/templates/person_narrative.md)** (the narrative-entry + meta-block shape; [vault-template/templates/person.md](vault-template/templates/person.md) is the standalone per-person-file model).

**v3 grammar = a VALID YAML flow-mapping** (adopted to maximize compatibility with the upstream `templates/person.md` frontmatter vocabulary — see the field-map below). It is parseable by `yaml.safe_load` *and* by the zero-dependency reader in `gen_person_index._parse_flow_mapping` (PyYAML is optional). The format can't be file-frontmatter (that's per-file; the narrative model packs many people per file), but the inline flow-mapping is real YAML with upstream's exact field names + values.

```
**Jane Example Ancestor** (b. Dec 1840, Somewhereton; d. 1873; FS PID XXXX-XXX)
- meta: {id: P-7K3QM2, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 6, fs: XXXX-XXX}
- **FS-attached sources** (...)
```

**The meta block — NOT the bold name — is the identity and detection anchor.** `gen_person_index` finds entries by their `- meta:` line and keys identity on `id`; it reads the bold name from the line above purely for DISPLAY + vitals. So a bold name with parens, quotes, commas, or lowercase words is fine — it can no longer make an entry invisible or duplicate it. Format the bold name for human readability; the machine never depends on it.

Grammar (YAML flow-mapping `{k: v, k: v}`; conventional field order below):
- `id` — the **vault-owned primary key**: `P-` + 6 Crockford base32 chars (no I/L/O/U), e.g. `P-7K3QM2`. **REQUIRED, unique, NEVER reused or hand-edited.** The ONLY identity key — dedup, matching, and Phase-2 `parents`/`spouse` edges reference `id`, never names/dates/external PIDs. Mint with `python3 scripts/mint_ids.py --apply` (idempotent; handles both grammars). A deleted entry's id is retired, not reused.
- `evidence_tier` — `strong_signal` / `moderate_signal` / `speculative` (upstream's claim-quality vocabulary). **OPTIONAL: absence = unassessed** (pair with `profile_status: stub`). There is NO `unknown`/`U` tier — "haven't assessed" is expressed by omitting the field, not by a fourth value.
- `profile_status` — `stub` / `partial` / `complete` (upstream's file-completeness vocabulary, **orthogonal to evidence_tier**: a well-sourced record can be `complete` with no `evidence_tier`, and a `strong_signal` claim can still be a `stub`). `complete` = the entry carries a **`- **Sources**` bullet**; `partial` = tiered but unsourced; `stub` = thin/unassessed collateral.
  - **AMENDED 23 JUL 2026 — a RECORD ARK is not the only thing that earns `complete`.** The old wording made `complete` mean "has an FS-attached-sources bullet", which silently tied a *documentation* judgement to one *evidence class*. For record-era ancestors that is harmless. For medieval, peerage and colonial-book lines it is simply wrong: those people are documented by charters, chronicles and scholarly compilations, and the Recipe-S policy **deliberately excludes** book/journal citations from the ARK metric (invariant 8, class (c)) so that coverage cannot inflate on bibliography. The two rules composed into an absurdity — a Carolingian cited to Cawley, Richardson and the *Monumenta Germaniae Historica* could never be better than `stub`, which reads as "nobody has researched this" about some of the best-documented people in the vault.
  - **The rule now:** `complete` is earned by a `- **Sources**` bullet citing EITHER (a) independent primary **records** (`host:locator` per Spec 03 — the ARK path), OR (b) **scholarly apparatus**: FMG Medlands (Cawley), Richardson *Royal Ancestry* / *Magna Carta Ancestry*, Complete Peerage, ODNB (with DOI), the Henry Project, MGH / named chronicles, Great Migration, NEHGR / TAG, published town Vital Records. Cite (b) with page or section refs in the bullet, the same way (a) cites locators. **This does NOT change the ARK coverage metric** — `harvest_sources` still counts only records, so the census stays honest. It changes only what the per-entry status field is allowed to claim.
  - **Not everything counts.** User trees (Geni, Ancestry, RootsFinder, copied WikiTree assertions) earn nothing under either limb — they copy each other, and often copy your vault. WikiTree's *cited sources* remain a separate corroboration layer, not a status upgrade.
  - **The matching census split:** `harvest_sources` now reports **`BOOK_SOURCED`** (0 ARKs, structurally unsourceable, but cites scholarly apparatus — finished work) and **`UNCITED`** (0 ARKs and no citation of any kind — the real worklist) in place of the single `STRUCTURAL_GAP`. At the split this vault's 186 structural entries were 101 / 85, so nearly half of what the census described as "cited in prose" was not cited anywhere. **`UNCITED` is the list to work, and its route is a library/archive pass, not an FS harvest.**
- `life_status` — `living` / `deceased` / `unknown` (upstream's privacy field). **Autonomous web research MUST skip `living` AND `unknown`.** For WRITE-BACK the gate is **per-target** (Spec 04, `multi-anchor-multi-repo`): a **public** target (a shared tree — FamilySearch, WikiTree) denies `living`/`unknown`; a **private** target (a personal Ancestry-style tree) may include them. This is decided in ONE place — `scripts/privacy_gate.py` `gate(vault, repo_id, life_status)` — which every write path calls (it also refuses a repo that is not a `write.enabled` target); do NOT restate the rule inline where it can drift. With no `repositories` configured the only target is public FS, so the effective rule is the historical "skip `living` and `unknown`". 110-year presumption seeds `life_status`; explicit "living"/"possibly living" in the header → `living`.
- `generation` — generation counted from the subject (Gen 1), integer, or omitted if undetermined. REQUIRED for the roster. Per-person source of truth (not inferred from `### Generation N` headings, which fail for theme-organized collateral). Phase 2: computed from the parent-edge graph.
- `fs` — FamilySearch PID, or `TBD` (not-yet-searched) / `none` (searched, no profile). Optionally `wt` (WikiTree), `anc` (Ancestry), etc. These are EXTERNAL pointers for lookup — **never the identity key** (FS PIDs rot on merges; the vault spans many sources). All optional; an entry with no `fs` is fully valid as long as it has `id` + `generation`.
- `fs_private_keys` — **living-person FS PIDs (used INSTEAD OF `fs` for living people).** On FamilySearch a *deceased* person has ONE shared PID on the Global tree (that goes in `fs`); a *living* person has NO public PID and instead a **separate private PID in every tree they appear in** (the Global tree and each private Group Tree). So a living person's PIDs are a **single-quoted YAML flow-list, unlabeled** (do NOT create a per-tree key): `fs_private_keys: '[AAAA-AAA, BBBB-BBB]'`. The tree each PID belongs to is **disambiguated at access time** (navigate the tree and resolve), not encoded in the vault — the list is just the set of known private PIDs for that person. A living entry uses `fs_private_keys` and omits `fs` (so `gen_person_index` reports an empty `pid`, correct: no public PID); this also keeps living people out of the `harvest_sources` PID-bearing target set. A PID that turns out stale (e.g. the person was deleted from that Group Tree) can be pruned from the list. Deliberately a flat list, not per-tree keys.
- `parents`, `spouse`, `flags` — Phase 2 edges. **`parents`/`spouse` = single-quoted YAML flow-lists of vault `id`s** (NEVER names/dates/external PIDs), e.g. `parents: '[P-A, P-B]', spouse: '[P-C]'`. **A trailing `?` on an id marks that edge as NOT YET FS-CONFIRMED** (`parents: '[P-A?, P-B?]'`) — regardless of source: GEDCOM-seeded OR vault-authored (hand-derived from the narrative). The `?` is the verification worklist marker: any edge not yet cross-checked against FamilySearch carries a `?` so it counts as unverified rather than silently-done (this is what keeps the prompt-18 metric honest). The FS-walk verification pass drops the `?` per edge as it confirms against FamilySearch, and LEAVES the `?` on FS-GAP edges that are correct but not yet on FS (e.g. a parent who is `fs: none`, or a relative FS hasn't linked). `flags` = `Q##`, `dup`. **Do not hand-author GEDCOM-seedable edges — generate with `scripts/build_edges.py`** (GEDCOM seed → id edges; idempotent upsert/merge; `--apply` writes, default is write-preview); when you DO hand-author an edge from the vault narrative (a person/relative absent from the GEDCOM or from FS), write it WITH a `?` so it enters the verification worklist. Values containing commas/brackets MUST be single-quoted (YAML flow-mapping rule). Phase-2 GEDCOM-seed pass done 25 JUN 2026 (~23% parent coverage); FS-walk verify/fill pass worked 22-23 JUL 2026 (see below).
  - **⚠ THE `?` IS OVERLOADED, AND AN FS-WALK MUST NOT STRIP IT BLINDLY.** As written above, `?` means "not yet FS-confirmed", and the FS-walk is told to drop it on confirmation. But the same mark also gets used to record a **scholarly hedge** — an edge that FamilySearch *does* assert and that the best independent authority doubts. Those are opposite situations wearing the same mark, and a mechanical pass would silently delete documented caveats. Expect this on medieval and peerage lines, where an entry may say in so many words that FS links the couple and the `?` reflects the scholarly doubt rather than a missing FS link.
  - **Before dropping any `?`, read the entry.** If the prose gives a source-based reason for doubt, the `?` is a VERDICT and stays no matter what FamilySearch shows.
  - **Three distinct reasons a `?` survives an FS-walk**, all legitimate, none a defect: (a) **FS-GAP** — the edge is right but FamilySearch has not linked it, or a parent is `fs: none`/`TBD` (a common shape: an FS couple that lists only some of their known children, or a child absent from both parents' child lists); (b) **SCHOLARLY HEDGE** — as above; (c) **PRIVACY** — either endpoint is `life_status: living`/`unknown`, which is never web-searched at all. Only a `?` that is none of these is actionable. Report the breakdown, because the honest denominator is much smaller than the raw count — in one measured pass fewer than half the unverified parent edges were FS-checkable at all, the rest being unclearable by construction.

### The bold-name HEADER also has a grammar

The `- meta:` block above is machine-grade. The **header beside it was not** — it was
free prose a parser had to guess at, eight dialects accumulated, and the guessing
wrote 25 wrong dates into this vault before an audit caught them. The corrective is
at the WRITE end. **`header_audit.py --changed-only` runs in the vault pre-commit
hook and BLOCKS any header this commit writes or edits** (the ~750-entry legacy
backlog stays advisory until the Spec 04 migration).

```
**[Name]** (<field>; <field>; …)   [free prose after the paren]
```

**The rule constrains the DATE SLOT, not the sentence:**

- A field opening with **`b.` / `bapt.` / `chr.` / `d.`** (or `born` / `died`) MUST
  carry a valid GEDCOM 7 `DateValue`, or the literal `unknown`. Write `ABT 1750`,
  not `~1750` or `c.1750`; `BET 1810 AND 1830`, not `1810-1830`; `BEF 1866`, not
  `bef. 1866`. Same grammar as the meta field — check one with
  `python3 scripts/gdate.py '<value>'`.
- A **place follows the date behind a comma** (`b. 1810, Villagio`), jurisdictions
  smallest to largest (GEDCOM 7 `PLAC`). Never inside the date slot.
- **No parenthesis inside the DATE SLOT.** Put it after the place
  (`b. 3 SEP 1780, Villagio (parish copy)`), in its own `;` field, or after the
  closing `)`. A paren ELSEWHERE in the header is fine and always was:
  `Gloucester (Barton St Mary)` is a place name, not a dialect. (This rule was
  narrowed 23 JUL 2026 after the migration measured it: of 34 headers it flagged,
  30 were parenthesised PLACE NAMES that a semicolon cannot express.)
- If the meta block carries **no** `born`/`died`, no vital field is required. The
  grammar never asks you to invent a date.

**Everything else in the header stays free prose — deliberately, including when it
contains a year.** `Gen 35`, `a weaver`, `alive 1852` (a floruit), `atto 534`, an
editorial aside: all legal and all unread, because a conforming reader only looks
inside a declared date slot. That is the entire point. Do NOT "helpfully" convert a
floruit or a document number into a vital field — those exact values are what the
old positional guessing turned into births.

Copy-paste shape: [vault-template/templates/person_narrative.md](vault-template/templates/person_narrative.md).
Full grammar, rationale and the migration runbook:
[workflows/header-grammar.md](workflows/header-grammar.md).

### Dates (`born` / `died` / `born_phrase` / `died_phrase`)

Dates are a **record field**, not prose
recovered by regex. The value grammar is the [GEDCOM 7 `DateValue`](https://gedcom.io/specifications/FamilySearchGEDCOMv7.html),
which exists precisely for genealogical dates; a bare ISO `YYYY-MM-DD` is also accepted
on read. Validate one value with `python3 scripts/gdate.py '~1750'`.

```
1780                  a plain year — and a year is a year: 954 parses like 1954
SEP 1780              month precision
3 SEP 1780            day precision
ABT 1750              near x, exact unknown            (~1750, c.985)
EST 1832              near x, and x is CALCULATED      <- declarant-age estimates
CAL 1780              x calculated from other data     (age-at-death arithmetic)
BEF 1866 / AFT 1672   no later / no earlier than x
BET 1816 AND 13 FEB 1823     between two bounds
FROM 1650 TO 1672     lasted across a span             (floruit approximations)
JULIAN 30 JAN 1649    a non-Gregorian calendar         (also GREGORIAN/FRENCH_R/HEBREW)
44 BCE                an epoch
```

Values are single-quoted in the meta flow-mapping:

```
- meta: {id: P-XXXXXX, …, generation: 8, fs: XXXX-XXX, born: '3 SEP 1780', died: 'BET 1816 AND 13 FEB 1823'}
```

Four rules, each of which exists because breaking it caused a real defect:

1. **Omit the key when the date is unknown.** Absence = unknown, the same convention
   `evidence_tier` uses. Never store `unknown` / `Deceased` / `?` as a *value*.
2. **Places stay OUT of the date value.** The header keeps `date, place` for humans.
   `prose_audit` takes the PLACE from the header and the YEAR from the field; deriving
   a place from a date field is a category error that produced a live false positive.
3. **`EST`, not `ABT`, for a declarant-age-derived year.** That puts this vault's
   "declarant-age estimates are ESTIMATES, not facts" rule *in the data* instead of in
   a prose caveat.
4. **Old Style / New Style dual dates use BOTH keys, and the DATE takes the NEW STYLE
   (later) year** — GEDCOM 7 Appendix A §6.2's own worked example. Taking the earlier
   year is the intuitive choice and it is wrong; it silently backdates every
   January-to-March event by a year.

```
- meta: {id: P-XXXXXX, …, born: 'JULIAN 30 JAN 1649', born_phrase: '30 January 1648/49'}
```

The header parenthetical is unchanged and stays human-authored — it carries what a
structured field cannot (`near Weymouth, MA`, `killed King Philip's War`,
`christened 3 SEP 1676`). The two are kept honest by the advisory **`DATE_DRIFT`**
metric, which compares their YEARS (integrity rule 7).

Full runbook, including the migrator and the residue worklist:
[workflows/structured-dates.md](workflows/structured-dates.md).

**Cross-model field-map** (the narrative `- meta:` block ⇄ the `file` model's [person.md](vault-template/templates/person.md) YAML frontmatter — the two are mechanically inter-convertible via `scripts/convert_person_model.py`):

| upstream frontmatter field | v3 meta key | notes |
|---|---|---|
| `evidence_tier: strong_signal\|moderate_signal\|speculative` | `evidence_tier` (same values) | identical |
| `profile_status: stub\|partial\|complete` | `profile_status` (same values) | identical |
| `life_status: living\|deceased\|unknown` | `life_status` (same values) | identical |
| `name` (frontmatter) | bold-name header (display) | name is the header, not a meta field |
| — (no upstream field) | the bold-name header's **vitals paren** | has its OWN grammar: a `b.`/`d.` field carries a GEDCOM 7 `DateValue`, the place follows a comma, everything else stays free prose. Gated at write time by `header_audit.py --changed-only` |
| `born` / `died` (`YYYY-MM-DD`) | `born` / `died` (GEDCOM 7 `DateValue`) + the header parenthetical | **BOTH, with defined roles.** The premise still holds — `ABT`, `bef.`, OS/NS `1603/04` don't fit ISO — but they DO fit GEDCOM 7, which was designed for them. Machine value in the meta field (authoritative), human display in the header, drift gated by `DATE_DRIFT`. See **Dates** below |
| — (no upstream field) | `born_phrase` / `died_phrase` | the GEDCOM 7 `PHRASE` escape hatch: free text for what the grammar cannot express (`30 January 1648/49`) |
| `sources:` list | `- **FS-attached sources**` bullet + ARKs | different shape, same purpose |
| `family` / `type: person` / `created` / `tags` | (omitted) | redundant inline / file-level |
| — (no upstream field) | `id` | vault primary key; upstream identity = the person *file's* name |
| — (no upstream field) | `fs` / `wt` / `anc` | upstream has no external-id field; this fills that gap |
| — (no upstream field) | `fs_private_keys` | living-person per-tree private FS PIDs (flow-list, replaces `fs` for living people) |
| — (no upstream field) | `generation` | upstream uses tree indentation + shard ranges |

**Files stay sorted by generation.** Keep the `### Generation N` headings and the ordering. Entries within a file are ordered by `generation` ascending (Gen 1 first); entries with no `generation` sort to the END. `generation` is the machine truth AND the sort key — they must agree.

**Collateral stub entries.** Thin collateral kin (a sibling/aunt/cousin worth only an external id + a one-line relationship, not a full sourced write-up) live in a dedicated `## Collateral stub entries (migrated from Person_Index)` section at the END of their lineage file, gen-sorted (`gen: ?` last). Each is a terse bold-name entry + meta block carrying the relationship-to-anchor note. Living people stay terse (approximate year only, no exact DOB).

Rules:
- **Every new person entry MUST get a `- meta:` flow-mapping with at least `id` + `generation`** (`evidence_tier`/`profile_status`/`life_status`/`fs` strongly recommended). Run `python3 scripts/mint_ids.py --apply` to mint the id mechanically (it seeds any meta block lacking one, in either grammar), or write `id` by hand using a fresh `P-xxxxxx` not already present in the vault.
- **External ids (FS/WT/ANC) live in the meta block, never in the header.** Keep cross-reference PIDs (parents/spouse/child) out of the bold-name header (header carries only the entry's own external id in the display parenthetical, if any) — cross-refs go in a body bullet now, and in `parents:`/`spouse:` (`id` edges) in Phase 2.
- **Do NOT strip, reorder, or renumber meta blocks; never reuse an `id`.** They are the source of truth for the generated roster and the edge graph.
- There is **no separate person index**. An earlier design kept a `Person_Index.md` table alongside the narratives and a family of audit scripts to police drift between the two; both were retired once the narrative + its meta block became the single record. The one narrative-native HARD gate is `gen_person_index.py --integrity` (unique `id` + complete meta), and the gen-sorted roster the index used to provide is generated on demand.

## Vault Integrity Rules

When adding or modifying person entries in any Family_Tree file:

1. **Single-generation headings only.** Every `### Generation N:` heading must use a single number, never a range. If a section would span multiple generations, split it into separate headings grouped by lineage (e.g., `### Generation 12: Smith / Jones (Anytown, County)`).

2. **Assign a generation number to every person.** Generation counts from the subject (Gen 1). Before adding a person, trace the shortest path from Gen 1 to determine their generation. Do not guess from the section they "feel like" they belong in.

3. **No duplicate person entries.** Before adding a person, grep the target Family_Tree file for their name. If they already exist, merge new information (FS PIDs, children lists, source details) into the existing entry. Never create a second entry in a different section.

4. **Every new person entry gets a `- meta:` flow-mapping in the same commit (this replaces the retired "update Person_Index" rule).** A person added to a Family_Tree file must carry a `- meta: {…}` block as its first body bullet with at least `id` + `generation` (`evidence_tier`/`profile_status`/`life_status`/`fs` recommended). Mint the `id` mechanically with `python3 scripts/mint_ids.py --apply`. There is no second store to keep in sync — the narrative + its meta block IS the record. The gen-sorted roster regenerates on demand (`gen_person_index.py --write`).

5. **Verify before committing.** After any batch of changes:
   - Grep the target Family_Tree file for each new person's name to confirm you are not creating a duplicate (merge into the existing entry if found).
   - Confirm the `generation` in the meta block matches the `### Generation N` section heading (for files that use them).
   - Confirm no bold-name entries were left in deleted/merged sections.
   - Run `python3 scripts/gen_person_index.py --integrity` — it must report 0 HARD violations (every entry has a unique `id` + complete meta). The pre-commit hook enforces this.

6. **Header lines carry ONLY the entry's own FS PID — no cross-reference PIDs in the bold-name header.** Do not put another person's PID (spouse / parent / child / sibling) on the same line as the bold name. Cross-reference PIDs belong in a **body bullet** (e.g., `- Married Mary Smith (FS: XXXX-XXX)`), never the header. Rationale: scripted source-bullet insertion (Recipe-S write-back) anchors each bullet on the header's PID; a foreign PID in a header causes mis-attribution — a real incident attached bullets to the wrong people (and to living relatives) because headers inlined "father John Smith XXXX-XXX"-style cross-refs. Audit with `python3 scripts/header_xref_audit.py` (advisory; surfaces header lines with >1 distinct PID). Any pre-existing backlog (headers from before this rule) — do NOT add new violations; burn it down incrementally (move the foreign PID into a body bullet) when editing a file for other reasons.
   - The convention for the entry's own PID: `**Name** (..., FS PID XXXX-XXX)` or `**Name** (..., FS: XXXX-XXX)` in the header parenthetical, AND/OR `FS: XXXX-XXX` in the meta block (the meta block is the machine-authoritative copy).
   - **Identity is the meta `id:`, never a name/date/external PID.** Dedup and matching key on `id`. A malformed bold name (parens, quotes, commas, lowercase) is fine — `gen_person_index` detects entries by their `- meta:` line, not the bold name, so a bad name can no longer make an entry invisible or duplicate it.

7. **Prose summaries must stay in sync with canonical entries — and so must the header/meta date pairing, and the header must match the header GRAMMAR.**
   - **Dates now live in TWO places with different jobs**: the `- meta:` `born`/`died` FIELD is the machine value (gates, sorting, matching, exports) and is AUTHORITATIVE; the header parenthetical is the human display and keeps what a structured field cannot carry (`near Weymouth, MA`, `killed King Philip's War`, `christened 3 SEP 1676`). When you change one, change the other in the same commit. `prose_audit`'s **`DATE_DRIFT`** check compares their YEARS (not strings), so they may differ in wording but never in fact. Baseline 0, and **BLOCKING** as of 22 JUL 2026 — a commit with a header/field date disagreement fails the vault pre-commit hook. `--no-strict-dates` overrides for one run. Intro paragraphs, "Lineage interconnections" sections, hereditary-society walks, mayflower-line write-ups, and similar derived prose paraphrase the canonical bold-name entry + its meta block. When canonical entries are updated (vitals, places, parents, generation, PIDs), the prose that paraphrases them must update in the same commit. (`prose_audit.py` builds its canonical fact map from the narratives via `gen_person_index.parse_narrative()` — there is no separate index to drift against.)
   - After editing any person's birth/death date or place, parents, spouse, generation assignment, or FS PID, run `python3 scripts/prose_audit.py` to surface drift. Fix any ERROR-level issues (year-drift, place-drift, wrong-relation, stale-death-unknown, wrong-direct-line-relation, generation-relation-mismatch).
   - When writing new prose that mentions a named person with dates or relationship descriptors, verify against the canonical entry BEFORE writing. This check has caught real drift bugs (an intro-paragraph spouse mix-up, a name typo in a prose summary, a "Gen 6 = grandparents" miscount, a stale "d. ?" placeholder in a derived write-up); in each, the canonical entry was correct and the summary prose was wrong.
   - Relationship descriptors ("paternal grandmother X", "great-great-grandfather Y") are especially error-prone. Generations count from the anchor (Gen 1; your vault's anchor set is declared in its `.autoresearch.json`, and named in your local instance file if you keep one) — Gen 2 = parents, Gen 3 = grandparents, Gen 4 = great-grandparents, Gen 6 = great-great-grandparents. When phrasing "Generation N (her X generation)", confirm the arithmetic: subject + offset = N.
   - Session logs in `vault/logs/` are EXCLUDED from prose_audit by design — they're write-once historical research notes documenting what was known at the time, not living summaries.

8. **Source-coverage invariant.** Each PID-bearing narrative entry should cite the primary-source records (census, vital records, immigration, naturalization, etc.) that document that person. Sources are documented in the entry's **`- **Sources**`** bullet using the Spec 03 (`multi-anchor-multi-repo`) **record / host:locator grammar**: one sub-bullet per RECORD (the primary source), each carrying one or more `host:locator` pairs, e.g. `- 1910 US Census, Manhattan — fs:1:1:XXXX-XXX` or `- 1847 birth atto — antenati:ark:/12657/an_…, fs:3:1:YYYY-ZZZZ` (one record, several hosts). `host` is a short id from `.autoresearch.json` `hosts` (`fs`/`antenati`/`metryki`/`szukajwarchiwach`/`agad`/`anc`/`wt`); the locator keeps its namespace (`1:1:` indexed, `3:1:` image, `ark:/12657/…`). **The coverage metric counts distinct RECORDS, not locator tokens** — a census cited on FS + Ancestry is ONE record with two locators. `scripts/harvest_sources.py` reports records + a per-host locator breakdown and is backward-compatible: the **legacy flat `- **FS-attached sources**: 1:1:…, 3:1:…` form is still parsed during the transition** (an un-migrated entry counts one record per locator, identical to before), and `scripts/migrate_sources.py` (dry-run default, `--apply`, idempotent; approach b — auto-merges persona/household + index/image pairs, flags the rest for a later Phase B) converts files to the `**Sources**` form. Write NEW bullets in the `**Sources**` grammar.
   - **What to harvest (policy adopted 02 JUN 2026): independent PRIMARY records only.** INCLUDE: (a) FS-indexed record ARKs (`ark:/61903/1:1:...`); (a2) **FS image/browse-record ARKs (`ark:/61903/3:1:...`)** — the "View the original document" register-IMAGE links, which are the primary source for browse-only collections. **Some browse-only civil-registration (Stato Civile / Tribunale) registers attach as `3:1:` image ARKs, NOT `1:1:` indexed records** — the `1:1:`-only harvest reads these as false "0 ARKs" (e.g. one profile carried 13 `3:1:` register atti the old harvest ignored). Capture and cite `3:1:` ARKs the same as `1:1:`; (b) external archive image links in a source's "**Web Page (Link to the Record)**" field that point to a primary register — Antenati (`ark:/12657/...`), metryki.genealodzy.pl, szukajwarchiwach (the genuinely-valuable primary sources for Italian/Polish lines, which the `1:1:`-only harvest used to miss). EXCLUDE: (c) published-book / journal citations (GSMD Silver Books, Great Migration, NEHGR, TAG articles, archive.org / americanancestors.org / Google Books) — these are real but bibliographic; cite the important ones in narrative **prose** with page numbers, and note their count in the bullet (e.g., "+ 2 TAG/Silver-Book citations, no record ARK"), do NOT fabricate ARKs for them; (d) user-tree citations (RootsFinder, copied Ancestry/WikiTree/Geni trees) — NOT independent evidence (they copy each other and often copy this vault), and excluded by the prompt-05 independence guard. Rationale: the coverage metric must reflect independent primary records, not inflate on copied trees.
   - **⚠ Detail View MUST be ON before extracting.** The `ark:/61903/1:1:` hrefs (and the "Web Page (Link to the Record)" external links) only enter the DOM when the Sources-tab Detail View toggle is on. Harvesting with it off yields a FALSE "0 ARKs / book-citations-only" read. After a fresh navigate the SPA usually needs a second JS call to render the list. Early "0 ARK" bullets may be wrong (two England-parish profiles were corrected from a stale "0 ARK" read to 7/9 real parish ARKs once Detail View was on).
   - The **Recipe-S harvest workflow** (Claude in Chrome MCP → `/tree/person/sources/{PID}` → toggle Detail View checkbox via JS → extract `ark:/61903/1:1:` hrefs + domain-scoped external archive links). Scope external capture to known archive domains only (antenati `ark:/12657`, metryki, szukajwarchiwach) — a whole-page external-href scan picks up FS footer junk (YouTube/Facebook). Methodology validated 21 MAY 2026 across 26 anchors / 399 ARKs (rounds 1-3); Colonial round 4 (02 JUN 2026) added 20 anchors / ~163 ARKs.
   - Run `python3 scripts/harvest_sources.py` to audit which PID-bearing narrative entries lack source coverage (it sources its roster from the narratives via `gen_person_index.parse_narrative()`). Categories: **SOURCE_GAP** (0 ARKs — highest-priority Recipe-S harvest target), **LOW_COVERAGE** (1-3 ARKs), **WELL_SOURCED** (4+ ARKs). (The old **NO_NARRATIVE** category is now vacuous by construction — every PID comes FROM a narrative entry.)
   - Useful filters: `--gen N`, `--gen-range 3-5`, `--confidence S/M/Sp/U`, `--region Italian/Polish/British`, `--limit N`, `--csv`.
   - ARK notation accepted by the script: `1:1:XXXX-XXX` (Recipe-S output style), `ark:/61903/1:1:XXXX-XXX` (full URL), or `FamilySearch ARK XXXX-XXX` (legacy bare-PID-as-ARK form used in pre-Recipe-S vault narratives). As of 02 JUN 2026 the script also counts: FS image ARKs `3:1:XXXX-XXXX-XXXX` (multi-segment register-image links), and external-archive primary sources — Antenati `ark:/12657/...`, `metryki.genealodzy.pl/...`, and `szukajwarchiwach...` URLs. Record these in the bullet alongside the `1:1:` ARKs so they credit (e.g., "...; 3:1:XXXX-YYYY-ZZZZ; ext: ark:/12657/an_..."). NOTE: adding `3:1:` crediting alone reclassified 17 Strong entries out of SOURCE_GAP (their narratives already cited register-image ARKs the old script ignored).
   - When adding a new FS PID + narrative entry: the source-coverage harvest should follow within the same session if practical, OR be queued as a target for a future Recipe-S round. SOURCE_GAP entries from `harvest_sources.py` output are the canonical Recipe-S priority list.
   - **Yield expectations vary by line type**: Anglo-American ancestors typically yield 20-35 ARKs (dense US + UK vital + census coverage); Italian civil-registration ancestors 3-8 ARKs (province-dependent; some lines surface mostly via emigrant children's US records); parish-resident ancestors whose registers are not on FS may yield only their children's emigrant-country records — the primary research lives at the origin parish/regional archive, not FS.
   - **A BOLD NAME AT LINE START IS AN ENTRY HEADER. Anywhere else on the line it is prose, and that is now enforced by position, not by guesswork** (spec/entry-boundary, 23 JUL 2026). Two consequences when writing a narrative: (a) it is perfectly safe to bold an archive, a record series or a relative mid-sentence — "filmed by the **Archivio di Stato di X (Stato Civile)** series" — because a mid-line bold span can no longer become an entry boundary; (b) do NOT begin a line with a bold `Words (parenthetical)` span unless it really is a person entry, because that IS the entry grammar. Before the fix a mid-line bold span truncated the entry it sat in and adopted everything below it, commonly the whole `Sources` bullet: 92 people under-credited on the reference vault, three of them reported as having ZERO sources while holding 16, 11 and 3 records. Nothing looked malformed and every other gate stayed green, so the standing gate is `python3 scripts/entry_boundary_audit.py` (HARD `ENTRY_MISATTRIBUTION`, baseline 0, in the vault pre-commit hook: every non-blank line must be owned by the header preceding it at line start, with `SOURCE_MISATTRIBUTION` reported as the subset that lands on a `Sources` bullet). **When it fires, the fault is in the PARSER — do not rewrite the narrative to appease it.**
   - **A CROSS-REFERENCE DOES NOT INHERIT SOURCES. If you record a relative's sources inside someone else's entry, put them on that relative's OWN bullet, with their locators on it** (spec/entry-boundary Spec 05, 23 JUL 2026). The census credits a PID from an entry when the PID is the entry's own (header or `- meta:`), or when a line mentioning it — with its sub-bullets — carries at least one locator. So the inline-collateral convention keeps working exactly as written: `- **FS-attached sources for wife <Name>** (<PID>, inline collateral; …): 1:1:…, 1:1:…`. But a name in a `- Siblings …` / `- Children of …` / `- Parents:` list now credits nothing, because it documents nothing. Before this rule, `max(records)` was taken over every block that MENTIONED a PID: 112 people on the reference vault were credited entirely through a relative, including a child who died in infancy reading as WELL_SOURCED off his adult brother's records, and a correction the operator had already made by hand was silently reverted by a later parser change. **Consequence: SOURCE_GAP is roughly 8x what the vault previously believed** — the old number was not low, it was wrong. Integrity rule 6 bans a foreign PID in a HEADER for the same reason; this is its body-level counterpart.
   - **Cite a locator, never the locator FORM.** The mirror hazard, same file, same silence: writing a bare `host:type:` prefix in prose as a class name ("browse-only registers attach as `fs:3:1:` image ARKs") once matched the locator detector and counted as a RECORD, inventing a source. A locator now only counts with a real id after the prefix, but the writing rule stands on its own — name the form in words, or cite an actual id.
   - **WikiTree corroboration is a SEPARATE qualitative layer, NOT part of this ARK metric.** WikiTree-as-a-tree stays excluded (it copies FS, and may copy your vault — circular). But a WikiTree profile's *cited primary sources* and *analytical/disambiguation content* (Research Notes, G2G threads, "Was she X?" pages) are valuable for contested/patriot/deep Anglo entries. Capture them as a distinct `- **WikiTree corroboration** (<ID>, read <date>; off the FS-ARK coverage metric): …` narrative bullet — corroboration comes from *what WikiTree cites, never its bare assertion*. Operator-gated (WikiTree blocks anonymous reads — needs the operator's logged-in session); read the PAGE (the API exposes only vitals + `Touched`); pace ~1 read / 2 s (throttles fast → 429). Scope = Anglo-American/British contested + patriot + Magna-Carta + `Q##` + Moderate/Speculative entries; SKIP regions a pilot shows WikiTree does not cover (re-probe ~annually).

9. **The meta block is the machine record; keep it lean. Research-history prose lives in the narrative body, not the meta block.** Each `- meta:` flow-mapping carries only the fixed-grammar fields (`id, evidence_tier, profile_status, life_status, generation, fs/wt/anc, parents, spouse, flags`). Do NOT stuff harvest provenance, dates of discovery, or relationship narration into it — that belongs in the bold-name entry's body bullets. The gen-sorted roster (the lookup the retired `Person_Index.md` used to provide) regenerates on demand: `python3 scripts/gen_person_index.py --write /tmp/roster.md`. Two sub-rules:
   - **Files stay sorted by `generation`** within each `### Generation N` section (Gen 1 first; no-generation last). Collateral/theme-organized files keep their family grouping — the gen-sorted VIEW is the generated roster, not the file order. Do not append deferred "Coverage Audit Additions" / "Recipe-N" tables — fold new people into the right section immediately, each with a meta block.
   - **Pre-commit expectation.** The pre-commit hook in `vault/.git/hooks/pre-commit` enforces `gen_person_index.py --integrity` (HARD: DUP_ID + MISSING_ID — block on any) and `entry_boundary_audit.py` (HARD: `ENTRY_MISATTRIBUTION`, baseline 0 — a narrative line credited to an entry other than the header preceding it at line start), and runs `prose_audit.py` + `header_xref_audit.py` (advisory). Run `python3 scripts/gen_person_index.py --integrity` yourself after a batch of entry edits. `DUP_FS_PID` (one FS PID on two entries) is ADVISORY (FS is an external attribute, not the identity key; a known cross-file pair or two may be legitimately expected — record that baseline in `vault/.autoresearch.json` `known_dup_fs_pids`). Any known field-drift / gen-numbering-backlog cleanup is a separate task, not a commit blocker.

## Content-boundary policy (per-lineage file routing)

A lineage that outgrows one file is split into companion shard files by content
ROLE, not just size. The reusable routing pattern:

| Content role | File |
|---|---|
| Direct-line ancestor + spouse | the lineage's main `Family_Tree_<Region>.md` |
| Immediate sibling-collateral that authenticates a direct ancestor (atto declarant/witness, primary-source kin proxy) — 1-2 line inline entry | same main file |
| Extended sibling-collateral with its own multi-source sub-pedigree; in-law deep pedigrees; surname-cluster collateral discovered via record scans | `Family_Tree_<Region>_Collateral.md` |
| Region/surname "Origins and Toponymy" essay once it crosses the shard threshold | `Family_Tree_<Region>_Origins.md` (a 2-line pointer stays inline) |
| Open questions, hypotheses, methodology, register-scan plans | a `<Region>_Extension_Plan.md` (planning-only; no ancestor entries) |
| Witnesses/sponsors at vault-direct events | `Witness_Network.md` |

**The file an ancestor's narrative entry lives in** is the one where their full sourced write-up sits (not where they merely appear inline as a sibling-link). The generated roster groups people by that file (`gen_person_index --write` emits one `## <Family_Tree_FileName>` section per file), so placing the entry in the right file is what keeps the roster correct. When migrating an entry between files, move it **with its `- meta:` block intact** (never reuse or re-mint its `id`) to the correct file in the same commit, gen-sorted within its section, and confirm it landed under the right heading.

**A given vault's specific lineages, its companion-file layout, and its generation-anchor table are per-client facts: keep them in a gitignored `CLAUDE.instance.md`, never in this file.**
