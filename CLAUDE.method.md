# Method: portable genealogy-vault methodology

The reusable "how" of an autoresearch genealogy vault: conventions, the person
meta-block grammar, integrity rules, and operational style. This file is
**vault-agnostic** (nothing here names a real person) and is reused verbatim
across vaults. It is tracked, and `CLAUDE.md` `@import`s it, so a clone loads
it automatically.

**This is the RULES file.** The full narratives behind these rules (originating
incidents, measurements, superseded texts, dated operator rulings) live in
**`CLAUDE.method.cases.md`**, which is NOT imported into sessions: grep it on
demand. Rules with substantial history carry a pointer of the form (case law:
§ "Section"). When the two files disagree, this one wins.

**The private half stays local.** Per-client facts (the subject, the
generation-anchor table, a vault's lineage to file layout) are real family
data: they live in a gitignored `CLAUDE.instance.md`, pulled in by a thin,
also-gitignored `CLAUDE.local.md`. Nothing here depends on either existing.
See CONTRIBUTING.md "The framework/private boundary".

## Project Structure

The generic dir roles (`prompts/`, `reference/`, `workflows/`, `vault-template/`) are in **CLAUDE.md**. A working install adds:

- A **vault directory**: the live working tree. Keep it as its own repo, or at least gitignored; it holds real people and must never be committed to the framework repo.
- **Per-vault constants live in the vault's `.autoresearch.json`, read via `scripts/vault_config.py`, never hard-coded in scripts.** Keys: `gedcom` (falls back to the single `*.ged`); `structural_gap` (`deep_gen_threshold` + region rules; **prefer `before_year`, which states the CRITERION, over `pid_prefixes`/`pids` enumerations, which drift**; an entry with no dated vitals never satisfies a `before_year` rule); `anchor` (`kind: individual|couple` + `people[]` = the Gen-1 set; `get_anchor`); `repositories` (a write target ships `enabled:false` unless opted in; `get_repositories`); `hosts` (source-host registry, `locator_kind: ark|url|id`; `get_hosts`); `person_model` (`file` default | `narrative`; `get_person_model`; an unrecognized value is a hard error); `known_gen_collapse`; `known_dup_fs_pids`. **Omit a block to accept its default; write only what deviates.** Shape: `vault-template/.autoresearch.example.json`. New per-family constants go here, behind the loader. (`session_audit.sh` similarly externalizes its advisory baseline to the vault's `.audit_baseline.txt`.)
- **Vault resolution is central: `vault_config.resolve_vault()`**, precedence `AUTORESEARCH_VAULT` env var, then `--vault` arg, then a `../vault` sibling only if one exists, else a clear error. **NO implicit default vault.** Export `AUTORESEARCH_VAULT` before launching; wire a new `--vault` arg as `vault_config.resolve_vault(args.vault)`. ONE exception, for the read-only SessionStart banner only: `session_audit.sh` resolves env, then `.claude/last_vault`, then the sole vault-looking dir, then asks, and **always names the source in the banner**; an inferred resolution must be confirmed by the agent before any write, and 2+ candidates are never guessed (`--set-vault /path` to repoint). Mutating scripts stay strict. (case law: § "Project Structure")

## Prompt Format

The 7-field prompt structure (Goal / Metric / Direction / Verify / Guard / Iterations / Protocol) and the `Inputs To Replace` requirement are in **CLAUDE.md**. Addition: prompts use placeholder names `[SURNAME]`, `[ANCESTOR]`, `[LOCATION]`, `[DATE]`, `[VAULT_PATH]`.

## Vault Template Conventions

The generic file-frontmatter conventions live in **CLAUDE.md**, deliberately not restated here. **Deltas** for the `narrative` person model (the model this file documents):
- **People are bold-name NARRATIVE entries with a `- meta:` block** inside `Family_Tree*.md`, not per-person files. Template: [vault-template/templates/person_narrative.md](vault-template/templates/person_narrative.md); the per-person file model ([vault-template/templates/person.md](vault-template/templates/person.md)) is the framework default.
- **Region / surname content is inline** ("Origins and Toponymy" sections), not separate region/surname files. Size exception: when a lineage file crosses the shard threshold and the Origins prose is the growth, the essay moves to `Family_Tree_<Region>_Origins.md` (a 2-line pointer stays inline).

## Style

Generic style rules are in **CLAUDE.md**. Additional operational rules:

- **The session loop is FOUR PHASE PROMPTS and two commands**: `21-session-start` (gates vs baseline, vault confirmed, Handoff read), then `22-research-iterations` (**the only loop**: `Iterations: N` lane draws), then `23-session-review` (reconcile, re-measure, assemble the FS write-back queue), then `24-session-close`. `python3 scripts/session_plan.py` prints ONE ranked worklist across **THREE lanes**: EXPAND (parentless SILENT frontier), IMPROVE, ROTATE (profile review). Lane target = a floor in PEOPLE per iteration. (case law: § "Style")
  - ⛔ VERIFY was collapsed into IMPROVE; **confirming an FS PID is live SCORES NOTHING** (step 0 of prompt 25, never a unit). **IMPROVE** = SOURCE_GAP + SINGLE_SOURCED entries plus a reserved **DEFECT** share (`IMPROVE_DEFECT_SHARE`: gate findings + unadjudicated `?` edges; `build_edges.gen_mismatches()` is the shared computation behind gate line and worklist). Dispositions: `--sourced` (0 records to cited), `--corroborated` (1 host to 2+), `--verified` (a DEFECT row settled).
  - Lanes are drawn by a **bandit** (state in `session_plan_snapshots.json`; ⚠ a redefined lane gets a `lane_epochs` entry; retired arms go to `retired_arms`, never deleted). ⚠ **Candidates ROTATE**: per-lane cooldown (`offer_cooldown`, default 3, `.maintenance.json`) plus a seeded stratified sample after the strict-priority head (`1/HEAD_FRACTION`); a cooled row is deprioritised, never removed; offers are stamped at `--record` only when the recorded lane matches the drawn one; keyed on the **vault `id`**, never an external PID. (pinned: `scripts/test_candidate_rotation.py`)
  - **Each iteration records its own outcome**: `session_plan.py --record --lane <L> --outcome hit|miss`; **hit = target met or lane ran dry; short of target is a MISS.** Close with `python3 scripts/session_close.py [--log ... --summary ...] --next-plan` (no `--lane/--outcome` by default; phase 2 already recorded). ⚠ **ORDER: record, THEN plan** (`--record` sets `pending: null`, wiping any earlier plan run; `--next-plan` draws last; pinned: `scripts/test_session_close.py`). The banner's `plan ->` line is state-only.
- **THE GOAL IS A COMPLETE BIOGRAPHY PER PERSON; FAMILYSEARCH IS ONLY THE SYNC POINT.** `25-person-research-sweep` is the default unit of work (FS Sources + Research Help + discussions, then Ancestry, WikiTree and what it CITES, the region's own archive, newspapers, library surfaces, logging every resource including the empty ones); `19-fs-source-harvest` is its FS leg. IMPROVE is un-gated from `harvestable_pid()`. The census carries `SINGLE_SOURCED` / `MULTI_SOURCED` (cross-cutting counts, not categories). `bio_completeness.py` measures whether a LIFE HAS BEEN WRITTEN; ⚠ its keyword facets are a FLOOR. **A record count is not a biography.** (case law: § "Style")
- **The lineage points at its own tried routes**: the `ROUTES ALREADY TRIED IN THIS LINEAGE` block heading every `Family_Tree*` file; regenerate with `python3 scripts/route_digest.py --apply`. Routes are REGIONAL, not personal. Scope is the LINEAGE (root file + name-extending shards; ⚠ the bare `Family_Tree` stem is excluded from root candidacy). CLOSED routes sort above OPEN, grouped per shard. ⚠ **Every emitted line is blockquoted (`> `), load-bearing**: an unquoted bold span at line start would mint a phantom entry. Extract the WHOLE bullet, not one sentence. (case law: § "Style")
- **Read the `- **Prior work**` bullet FIRST** before doing anything to a person: it sits directly under `- meta:` (never above) listing the `logs/` sessions that cite the person's identifiers, newest-first; regenerate with `python3 scripts/log_backlinks.py --apply`. ⚠ Matched on IDENTIFIERS, never names; a token claimed by two people is DROPPED. ⚠ A log that considered and REJECTED a PID still counts; that rejection is prior work not to redo. (case law: § "Style")
- **Check before searching.** Grep `vault/logs/` and `vault/Open_Questions.md` before researching an ancestor; do not repeat prior negative searches without a new source or strategy. The `Prior work` bullet is the cheap check; the grep remains required for uncovered people and for PLACES, REPOSITORIES and ROUTES.
- **Check FS source citations before gap-fill scans**: Sources tab, Detail View ON, look for "**Web Page (Link to the Record)**" external links; a pasted archive ARK can resolve in one drill what a thousand register scans cannot. (case law: § "Style")
- **Downsize register images before Read.** `sips -Z 1500 input.jpg --out /tmp/input-small.jpg`, or crop one atto at full detail: `magick input.jpg -crop WxH+X+Y /tmp/atto.png` (optionally `-resize 180% -normalize -sharpen 0x1`). ImageMagick 7 at `/opt/homebrew/bin/magick`; PIL NOT installed. Repeated full-size Reads can 413 the session (32 MB ceiling); for genuine full-page work use the localhost-HTTP + browser zoom path.
- **Declarant-age estimates are ESTIMATES**: expect ±2-12 yr vs corroborated years; prefer FS-precise values; widen sibling-match tolerance to ±12 yr for declarant-derived rows.
- ⭐ **REPORT THE SPREAD, NEVER THE AGREEMENT.** For a value attested more than once (ages at successive events, a year given by several records), write the RANGE the attestations imply and the count behind it, not a convergence claim. ⛔ "the ages all agree on about 1842" is not a finding, it is a summary that the next record can falsify: a fourth act giving 29 in 1874 makes it 1842-1845, and the sentence has to be retracted rather than extended. ⚠ **For declarant-derived ages the agreement claim is never available in the first place** — the rule above puts them ±2-12 yr, so a 3-year spread is the EXPECTED shape and calling it agreement asserts a precision the source class does not carry. Say "consistent with", give the range, and let a `born` value stay unentered while the range is wider than the claim would need it to be. (case law: § "Style")
- **Append to the Research_Log "## Session Index" via `python3 scripts/log_session.py --log "logs/YYYY-MM-DD-slug" --summary "..."`, NEVER via Edit**; the file is append-only and must never be full-read into context.
- **A person entry states CURRENT state; how it was learned lives in `logs/`.** A superseded bullet MOVES to the session log; the entry keeps one current-state bullet + the log pointer. Dated bullets are for FACTS, not the entry's revision history; hand-struck history moves too. (Same-name-hazard markers are the exception, never at line start.) (case law: § "Style")
- ⭐ **Anything needing further research gets an `Open_Questions.md` entry, in addition to the narrative.** The register, not the entry, is what picks work. Owed when RESOLVING NEEDS WORK NOT YET DONE; not owed for settled findings or closed negatives (those are entry declarations, possibly a `structural_gap` rule). Batch thin same-shape findings into ONE question with a table. Cross-link both ways. ⚠ Name what would settle it, or it is a complaint, not a research task. (case law: § "Style")
  - ⛔ **Write questions through `scripts/question_store.py`, NEVER the Edit tool** (15 AUG 2026): `--new` mints the global number and requires a resolver, `--append` lands a write-up inside the right block, `--resolve` writes an archivable heading. Same rule and reason as `log_session.py`; `question_audit.py` gates the register structure in pre-commit (Q_BELOW_INDEX / DUP_LIVE_Q / ZOMBIE_Q, baseline 0). Filing a question is a lane disposition ONLY for a row the sitting cannot advance; a question naming a FREE resolver gets worked, and a dry lane drains the register instead of stopping (prompt 22).
- **Resolve an Open_Question with a PLAIN heading + terminal status** (`RESOLVED` / `RULED OUT` / `CLOSED` / `CONFIRMED FAIL` / `FULLY RESOLVED`), the FIRST word after the LAST em-dash, qualifiers in parens after it; never hand-strikethrough. ⚠⚠ **Provenance goes INTO THE TITLE**: `### N. Title (raised 05 AUG 2026, session #144) — RESOLVED 09 AUG 2026 (note)`; a suffix after the status silently makes the block un-archivable. Lint: `archive_sections.py --lint-headings` (advisory, baseline 0, banner `oq-headings`). Archive: `python3 scripts/archive_sections.py --target open-questions` then `--apply` (full text to the Resolved file + one row in `## Resolved & Closed — Index`). ⛔ Do NOT widen the detector to accept a status in any em-dash segment (it would archive live questions citing another question's status). (case law: § "Style")

## The entry is a biography (entry shape; operator goals, 15 AUG 2026)

**The target for a person entry is a Wikipedia-style biographical article**, and the
order of an entry is the order of that article:

1. **Header + `- meta:`** — the title and infobox (machine layer; grammar below).
2. **`- **Prior work**`** — the generated pointer, directly under the meta.
3. **The biography** — a lede (who this person was, in a sentence), then the life in
   chronological order: origin, parents, occupation, residences, migration,
   marriage(s), children, death, burial. Prose or fact bullets; this is the axis
   `bio_completeness.py` measures and the part a human reads. Narrative prose is
   WANTED here — "thirty ARKs and no prose is not finished work."
4. **`- **Sources**`** — the references (Spec 03 grammar, rule 8).
5. **Compact apparatus, LAST** — `Named-in` / `Sibling records` / negated locators /
   `FS write-back` bullets.

**Process narration is the TALK PAGE and stays off the article.** How a fact was
found, corrected, retracted or re-counted is session history: it belongs in the
session log (which `Prior work` points at) — or, when it is reusable, in the route
register. (case law: § "The entry is a biography")

- **Emphasis marks live hazards, not history.** `⛔`/`⚠` on an entry is for a
  same-name trap, a refuted identity, a privacy constraint — something the next
  reader must not miss. A corrected count or a superseded estimate is not shouted;
  it moves to the log with the rest of the chronology.
- **Burn down on touch, never in bulk.** When a lane draws a person, part of the
  disposition is triaging the entry toward this shape: conclusions into the
  biography, source/route facts into the route register, chronology into the log.
  ⚠ Diff the census by row whenever moved prose carries locators — negation scope
  is the ENTRY, and moving a quoted token can silently negate or credit it.

## Knowledge routing: three kinds, three homes (operator goals, 15 AUG 2026)

Everything a session learns is one of three kinds. **File it where the next session
will already be standing** — the same placement principle as the `Prior work`
bullet:

| kind | test | home |
|---|---|---|
| person fact — including a person-scoped negative ("no [SURNAME] death in the printed town VR 1710-1720") | about ONE life | the entry: biography, `Sources`, negated apparatus |
| route/source fact ("FreeREG Droitwich coverage is 1929-1948 only"; "England Marriages 1538-1973 has no widow field on any record") | true whichever person you research | the **route register** — `Route_Register.md`, one `##` section per lineage; `route_digest.py --apply` renders the per-file digest view from it, `--candidates` lists prose statements not yet moved |
| method/tooling ruling | about how the vault itself works | a rule in this file, its incident narrative in the case-law companion |

A route fact written into one person's entry is findable only by accident — that is
the misfiling the old digest scraped around, and it is how one archive's coverage
boundary was re-derived in three separate sittings. The routing decides where the
KNOWLEDGE lives; `Open_Questions` still decides what is OWED (an unresolved item of
any kind gets its register entry, per the standing rule).

## Person entry meta block (the machine-readable person record; v3 YAML-flow grammar)

This section describes the **`narrative` person model**: many people per lineage file, each a `- meta:` entry. The framework default is the **`file`** model (one person file, YAML frontmatter); both encode the same `PersonRecord` fields and are inter-convertible (`scripts/convert_person_model.py`; runbook [workflows/switch-person-model.md](workflows/switch-person-model.md)). **All record-consuming tooling goes through the model-agnostic seam `scripts/person_store.py`** (`iter_people`/`write_person`). The narratives are the single source of truth (`Person_Index.md` is retired); the gen-sorted roster is generated on demand: `python3 scripts/gen_person_index.py --write /tmp/roster.md` (also `--integrity`, `--gap-report`). **v3 grammar = a VALID YAML flow-mapping**, parseable by `yaml.safe_load` and by `gen_person_index._parse_flow_mapping`. Template: [vault-template/templates/person_narrative.md](vault-template/templates/person_narrative.md).

```
**Jane Example Ancestor** (b. Dec 1840, Somewhereton; d. 1873; FS PID XXXX-XXX)
- meta: {id: P-7K3QM2, evidence_tier: strong_signal, profile_status: complete, life_status: deceased, generation: 6, fs: XXXX-XXX}
- **FS-attached sources** (...)
```

**The meta block, NOT the bold name, is the identity and detection anchor**; the bold name is display only.

Fields:

- `id` — vault-owned primary key: `P-` + 6 Crockford base32 chars (no I/L/O/U). **REQUIRED, unique, NEVER reused or hand-edited**; the ONLY identity key. Mint with `python3 scripts/mint_ids.py --apply`; a deleted id is retired.
- `evidence_tier` — `strong_signal` / `moderate_signal` / `speculative`. OPTIONAL: absence = unassessed; no fourth value.
- `profile_status` — `stub` / `partial` / `complete`, orthogonal to `evidence_tier`. `complete` = a `- **Sources**` bullet citing EITHER (a) independent primary records (`host:locator`) OR (b) **scholarly apparatus** (FMG Medlands, Richardson, Complete Peerage, ODNB with DOI, the Henry Project, MGH and named chronicles, Great Migration, NEHGR / TAG, published town Vital Records), with page or section refs. User trees earn nothing under either limb. This does not change the ARK metric; the census splits 0-ARK structural entries into **`BOOK_SOURCED`** (cites apparatus: finished work) vs **`UNCITED`** (no citation: the real worklist; its route is a library pass, not an FS harvest). (case law: § "Person entry meta block")
- `life_status` — `living` / `deceased` / `unknown`. **Autonomous web research MUST skip `living` AND `unknown`.** Write-back is gated per-target in ONE place, `scripts/privacy_gate.py` `gate(vault, repo_id, life_status)`: public targets (FS, WikiTree) deny `living`/`unknown`; do not restate the rule inline. 110-year presumption seeds it.
- `generation` — integer from the subject (Gen 1), or omitted if undetermined. Per-person source of truth, never inferred from headings. ⚠ Write it explicitly in a `## Collateral stub entries` section: the heading fallback stops at any `#`/`##` boundary, so an entry past one reports `generation: None` (visible to `NEEDS_META`). An explicit value always wins.
- `fs` — FS PID, or `TBD` (not yet searched) / `none` (searched, no profile) / **`~PID` (a profile EXISTS and was REJECTED)**; optionally `wt`, `anc`. External pointers, never identity. ⚠ `none` and `~PID` are OPPOSITE instructions: `none` invites creating the person on FS; `~PID` means creating would push a DUPLICATE. The PID in a rejection is the point (re-checkable); the reason goes in entry prose. **Read via `person_store.external_id_state()` / `live_external_id()`, never a literal `not in ("TBD","none")` test** (a `~PID` is PID-shaped; pinned: `scripts/test_rejected_external_ids.py`).
- `fs_private_keys` — living-person FS PIDs, INSTEAD OF `fs`: one private PID per tree, so a single-quoted flat flow-list `fs_private_keys: '[AAAA-AAA, BBBB-BBB]'` (no per-tree keys; the tree is resolved at access time). Keeps living people out of the PID-bearing harvest set. Prune stale PIDs.
- `parents`, `spouse`, `flags` — edges: **single-quoted YAML flow-lists of vault `id`s** (`parents: '[P-A?, P-B?]'`; comma'd values MUST be single-quoted); `flags` = `Q##`, `dup`. **Trailing `?` = not yet FS-confirmed**; every hand-authored edge gets one. Generate GEDCOM-seedable edges with `scripts/build_edges.py` (idempotent upsert; `--apply` writes), never by hand.
  - ⚠ **The `?` is overloaded; never strip it blindly.** It legitimately survives an FS-walk for three reasons: (a) **FS-GAP** (edge right, FS lacks the link or the far end is `fs: none`/`TBD`); (b) **SCHOLARLY HEDGE** (FS asserts, the best authority doubts: the `?` is a VERDICT and stays); (c) **PRIVACY** (endpoint `living`/`unknown`, never searched). Read the entry before dropping any `?`; report the breakdown. (case law: § "Person entry meta block")
  - ⚠ A token that is not id-shaped is **`MALFORMED_EDGE_REF`** (structural, baseline 0, `build_edges --validate`; the judge regex is strict, the extractor deliberately looser; pinned: `scripts/test_build_edges.py`).
- `adjudicated` — far-end ids of `?` edges WALKED AND JUDGED with the `?` kept deliberately (`adjudicated: '[P-G4C4Z5]'`); this is what makes such work a countable disposition. Write it only for an edge actually read and judged. ⛔ Never as a token suffix (`P-XXXXXX?!` is destroyed by the next `build_edges --apply`; a sibling key survives by construction). `ADJUDICATED_STALE` (advisory, baseline 0) flags a note that outlived its `?`; a stale entry HIDES a real candidate. (case law: § "Person entry meta block")
  - ⭐ `adjudicated_why`: **`fs-gap`** / **`hedge`** / **`contradicted`** / **`privacy`** / **`no-second-parent`**; missing = `ADJUDICATED_UNEXPLAINED` (advisory). **Only `fs-gap` with a live FS PID at the far end is ever re-offered** (a labelled RE-CHECK row, ranked last); hedges and contradictions expire on EVENTS tracked as Open_Questions, not a clock. **`no-second-parent`** declares an ABSENCE ("one named parent is correct"), retires a `HALF_WIRED_PARENT` row, and stands ALONE with no `adjudicated` list; the key is therefore multi-valued (bare scalar `fs-gap` or quoted list `'[fs-gap, no-second-parent]'`): **read with `person_store.adjudicated_why_values()`, never a regex** (unknown tokens dropped). ⛔ Declare only from a RECORD or named authority, never the graph (closing a parent edge from a spouse edge picks the wrong woman whenever there was a remarriage). (pinned: `scripts/test_adjudicated_why.py`)
- `fs_probed` / `route` — "FS was checked and is EMPTY, and the records are actually over THERE." `fs_probed` = ISO date of a probe actually performed (⛔ never invent one; an undated negative reads as expired); it is NOT `fs: none` (the attached-source set was READ and holds no records; a live PID can coexist). `route` = lowercase slug, 2-40 chars (a registered host id like `metryki`, `jri`, `antenati`, or an archive slug for in-person routes). Both optional, both meaningful alone. **Read with `person_store.fs_probed()` / `route()`, write with `person_store.set_meta_key`** (unmodeled keys, round-trip conversion); an unrecognised route slug is RETURNED, not dropped (routes are open-ended; swallowing one makes a declaration silently fail: deliberately opposite to `adjudicated_why_values`). (pinned: `scripts/test_route_declaration.py`; case law: § "Person entry meta block")
  - ⭐ **"Empty" means no records OF THIS PERSON.** Books, memorials, user trees, reference works and NFS stubs are not records (screen titles with `harvest_sources.is_book_collection` / `is_memorial_collection` / `is_obituary_collection` / `reference_work_limb`, never by eye; ⛔ never treat the unrecognised residual as records); a limb (g)/(h) kin record does not block the declaration either. **The entry prose must name what was read and each excluded record with its reason** ("probed, empty" is not auditable). Credits nobody: the person stays `SOURCE_GAP`/`UNCITED`.
  - A `route` permanently RETIRES a `BOOK_SOURCED` or `UNCITED` row from those ROTATE arms (`ROUTE_RETIRING_ARMS`; the filter lives in `allocate()` so `pool` stays honest and the draw prints `rtrd`); ⛔ `fs_probed` retires nothing (dated, cooldown-shaped). ⭐ **A terminus is not a missing route** (terminus = ANCESTRY, route = DOCUMENTATION): a `BOOK_SOURCED` row has a route by construction, derived from the MOST SPECIFIC work it cites (named chronicles and targeted references before the Medlands catch-all); a fully declared arm is "floor unmet" for a different reason than a cold one, and the report says which.
- `edges_audited` — ISO date this entry's UNMARKED edges were walked and CONFIRMED; suppresses the IMPROVE `audit` tier and nothing else. ⛔ Do not reuse `adjudicated` for it (defined against `?` edges; would trip `ADJUDICATED_STALE`); ⛔ no date for an audit not performed, and say in prose what was compared against what. ⚠ It dates an ENTRY, not an edge set: **re-stamp it whenever you wire a new edge onto an audited row.** Read with `person_store.edges_audited()` (a non-date reads as absent); write with `set_meta_key`; `EDGES_AUDITED_STALE` advisory. ⚠⚠ **The four dated keys must not be unified**: `route` (where the evidence is; retires two ROTATE arms), `fs_probed` (sources read, no records; suppresses an IMPROVE SOURCE_GAP row), `fs_absent` (no profile; feeds the EXISTENCE cooldown), `edges_audited` (unmarked edges confirmed; suppresses the audit tier); a row may carry all four. (case law: § "Person entry meta block")
- `banked_parents` — the host on which the parents were LOCATED and deliberately NOT WIRED: scalar `fs` / `wt` / `anc`. **An FS couple is a TREE ASSERTION, not a source**: bank it, then find one record naming the parents and wire with `?`. A drawable IMPROVE sub-population (`session_plan.lane_banked()`, the `banked` defect tier, below `edge`, above `audit`; disposition `--verified`). ⚠ Selected via `person_store.banked_parents_host()`, never from declaration prose (a prose grep double-counts through the route digest); a scalar, not a PID list (the PIDs live in the frontier declaration). Exit test = the `parents` EDGE; leftover key = `BANKED_STALE` (advisory), prune on wiring. **Bank with `set_meta_key`, never by splicing text** (pinned: `scripts/test_banked_parents.py`). ⭐ Wiring a banked pair moves DECLARED down and SILENT, SOURCE_GAP, `?` up, and all are honest (circulation, not loss); ⛔ do NOT pre-declare the minted parents to hold SILENT flat; ⚠ the guard in `22-research-iterations` is per-EFFECT, not per-lane (any lane minting parents pushes SILENT up, a cross-lane effect the bandit does not model). (case law: § "Person entry meta block")
  - ⭐ **No "effort" stops: a frontier declaration is about ANCESTRY, never about work not yet done.** TERMINUS = no cited authority carries the line further; a STOP is a to-do, which is what SILENT is for. `extension_frontier.DECLARED_RE` no longer matches effort language (`NOT WORKED`, `deliberate stop`, `do NOT adopt|extend|wire`, ...). A false DECLARED is the expensive error: it removes a row from EXPAND permanently and silently. ⚠ Free-text ancestry phrases stay ambiguous; **the explicit `FRONTIER DECLARATION <date>` marker is the only unambiguous form: prefer it**, and name the authority. (pinned: `scripts/test_frontier_declaration.py`)
- **Pedigree collapse is DECLARED, not renumbered.** `generation` is a PATH label: two descent paths of different length legitimately give `parent != child gen + 1` on correct edges. Never renumber a branch; declare the edges in `.autoresearch.json` `known_gen_collapse` (`{child, parent, note}`; `get_known_gen_collapse`) and annotate all three entries. `build_edges --validate` then reports `GEN_COLLAPSE (expected)`, leaving `PARENT-GEN MISMATCH` meaning UNEXPLAINED. Never bulk-declare to drive the count to 0.

### The bold-name HEADER also has a grammar

```
**[Name]** (<field>; <field>; …)   [free prose after the paren]
```

**The rule constrains the DATE SLOT, not the sentence:** a `b.`/`bapt.`/`chr.`/`d.` field carries a GEDCOM 7 `DateValue` or the literal `unknown`; the place follows the date behind a comma; no parenthesis inside the date slot; no vital field required when the meta block has no `born`/`died`. **Everything else stays free prose, deliberately, even when it contains a year** (`Gen 35`, `a weaver`, `alive 1852`, `atto 534`): a conforming reader only looks inside a declared date slot. Do NOT convert a floruit or a document number into a vital field; those exact values are what positional guessing used to turn into births.

`header_audit.py --changed-only` runs in the vault pre-commit hook and **BLOCKS any header this commit writes or edits** (the legacy backlog stays advisory). The five write-time rules with worked examples: [workflows/header-grammar.md](workflows/header-grammar.md) § "Writing a header by hand"; read it before hand-authoring a header. (case law: § "The bold-name HEADER also has a grammar")

### Dates (`born` / `died` / `born_phrase` / `died_phrase`)

Dates are a **record field**, not prose recovered by regex. Value grammar: [GEDCOM 7 `DateValue`](https://gedcom.io/specifications/FamilySearchGEDCOMv7.html) (bare ISO also accepted on read). Validate with `python3 scripts/gdate.py '~1750'`; full production list in [workflows/structured-dates.md](workflows/structured-dates.md) § "Writing a date by hand". Values are single-quoted in the flow-mapping:

```
- meta: {id: P-XXXXXX, …, generation: 8, fs: XXXX-XXX, born: '3 SEP 1780', died: 'BET 1816 AND 13 FEB 1823'}
```

Four rules (case law: § "Dates"):

1. **Omit the key when the date is unknown.** Never store `unknown` / `Deceased` / `?` as a value.
2. **Places stay OUT of the date value.** The header keeps `date, place`; `prose_audit` takes the place from the header, the year from the field.
3. **`EST`, not `ABT`, for a declarant-age-derived year.** The discriminator is "calculated from other data", not vagueness: **EST = ABT + CAL.**

   | the value was… | approximate | derived from other data | use |
   |---|---|---|---|
   | a rough guess, nothing computed | ✔ | ✘ | **`ABT`** |
   | computed, and you believe the result is exact | ✘ | ✔ | **`CAL`** |
   | computed, result still approximate | ✔ | ✔ | **`EST`** |

   ⛔ (event year − stated age) is a calculation whatever the age's precision: such a row is `EST`, never `ABT`. ⚠ An exactly computed date (death date plus age in years, months, days) is `CAL`. ⚠ No gate can flag a wrong one (all three normalise to the same year); it is correct only if written correctly the first time.
4. **OS/NS dual dates use BOTH keys, and the DATE takes the NEW STYLE (later) year** (GEDCOM 7 Appendix A § 6.2); taking the earlier year silently backdates January-to-March events by a year.

```
- meta: {id: P-XXXXXX, …, born: 'JULIAN 30 JAN 1649', born_phrase: '30 January 1648/49'}
```

The header parenthetical stays human-authored (it carries what a structured field cannot); the advisory **`DATE_DRIFT`** metric compares the YEARS (integrity rule 7). Migrator and residue worklist: [workflows/structured-dates.md](workflows/structured-dates.md).

**Cross-model field-map** (narrative `- meta:` ⇄ `file` frontmatter; `scripts/convert_person_model.py`): `evidence_tier`, `profile_status`, `life_status` are identical; upstream `name` = the bold-name header; the header's vitals paren has its own gated grammar (above); `born`/`died` = GEDCOM 7 `DateValue` fields (authoritative) + header display, drift gated by `DATE_DRIFT`; `born_phrase`/`died_phrase` = the GEDCOM 7 `PHRASE` escape hatch; upstream `sources:` list = the `- **Sources**` bullet; `family`/`type`/`created`/`tags` are omitted as redundant; `id`, `fs`/`wt`/`anc`, `fs_private_keys`, `generation` have no upstream equivalent (upstream identity is the person file's name).

**Files stay sorted by generation** (`### Generation N` headings; entries gen-ascending, no-generation last; `generation` is machine truth AND sort key).

**Collateral stub entries**: thin collateral kin live in a `## Collateral stub entries (migrated from Person_Index)` section at the END of their lineage file, gen-sorted, each a terse entry + meta block with the relationship note; living people stay terse (approximate year only). **Size exception**: when a lineage file crosses the shard threshold AND the stub section is the bulk of it, the stubs move to `Family_Tree_<Region>_Stubs.md` with a `— MOVED` pointer left behind. ⚠ Check the share before cutting. ⚠ A move is a FILE change only: re-run `route_digest.py --apply` and `log_backlinks.py --apply`, and diff the census by row (it must not move). (case law: § "Dates")

Rules:
- **Every new person entry MUST get a `- meta:` flow-mapping with at least `id` + `generation`** (`evidence_tier`/`profile_status`/`life_status`/`fs` strongly recommended). **Mint the id with `python3 scripts/mint_ids.py --apply`; do NOT write an id by hand** (hand-authoring produced 15 malformed ids; `ID_GRAMMAR` is the advisory check, and consumers read ids through the `person_store` seam, never by regex). One minter, one grammar, one gate.
- **External ids live in the meta block, never in the header**; the header carries only the entry's own external id, cross-refs go in body bullets and edges.
- **Do NOT strip, reorder, or renumber meta blocks; never reuse an `id`.**
- **There is no separate person index.** The one narrative-native HARD gate is `gen_person_index.py --integrity`; the roster is generated on demand.

## Vault Integrity Rules

When adding or modifying person entries in any Family_Tree file:

1. **Single-generation headings only**: `### Generation N:` uses one number, never a range; split multi-generation sections by lineage.

2. **Assign a generation to every person**, traced as the shortest path from Gen 1; never guessed from the section they "feel like" they belong in.

3. **No duplicate person entries.** Grep the target file for the name first; merge into an existing entry, never create a second one.

4. **Every new person entry gets a `- meta:` flow-mapping in the same commit** (at least `id` + `generation`, id minted mechanically). The narrative + meta block IS the record.

5. **Verify before committing.** The checks are the `person-entry` and `audit-gates` skills; the pre-commit hook enforces the HARD ones (`gen_person_index --integrity` = 0). The one check no gate performs: grep the target file for each new person's name, merge if found.

6. **Header lines carry ONLY the entry's own FS PID.** A spouse/parent/child PID goes in a body bullet (`- Married Mary Smith (FS: XXXX-XXX)`), never the header: scripted insertion anchors on the header PID, and a foreign PID there mis-attributes bullets (a real incident hit living relatives). Gated by `header_xref_audit.py` (advisory); no new violations, burn the backlog down incrementally. Identity is the meta `id:`; a malformed bold name cannot hide or duplicate an entry.

7. **Prose summaries stay in sync with canonical entries; so does the header/meta date pairing.**
   - Dates live in TWO places: the `- meta:` field is AUTHORITATIVE, the header is display; change both in the same commit. `DATE_DRIFT` compares YEARS and is **BLOCKING** (`--no-strict-dates` for one run). Derived prose (intro paragraphs, interconnection essays) changes in the same commit as the entry it paraphrases.
   - Run `python3 scripts/prose_audit.py` after editing vitals, parents, spouse, generation, or PID; fix every ERROR. **Verify against the canonical entry BEFORE writing new prose**: in every drift bug so far the entry was right and the prose was wrong.
   - Relationship descriptors: generations count from the anchor; Gen 2 = parents, Gen 3 = grandparents; **for Gen N ≥ 4 the person is the (N − 3)th great-grandparent** (Gen 14 = 11th great-grandparent). Confirm the arithmetic.
   - Session logs in `vault/logs/` are EXCLUDED from prose_audit (write-once history).

8. **Source-coverage invariant.** Each PID-bearing entry cites the primary-source records documenting that person in a **`- **Sources**`** bullet, Spec 03 **record / host:locator grammar**: one sub-bullet per RECORD, each with one or more `host:locator` pairs, e.g. `- 1910 US Census, Manhattan — fs:1:1:XXXX-XXX` or `- 1847 birth atto — antenati:ark:/12657/an_…, fs:3:1:YYYY-ZZZZ`. (case law for every limb and ruling: § "Vault Integrity Rules")
   - `host` comes from the **`hosts` registry** (read with `python3 scripts/vault_config.py <vault>`, never a prose list). **Registering a host is the whole job**: `harvest_sources.EMITTED_HOST_IDS` derives from the registry. ⚠ A locator token is a NON-SPACE run (`tna:C1/548/65`); it keeps its namespace (`1:1:` indexed, `3:1:` image, `ark:/…`).
   - **The metric counts distinct RECORDS, not locator tokens** (one record on two hosts = ONE record). The legacy flat `- **FS-attached sources**:` form still parses; `scripts/migrate_sources.py` (dry-run default, `--apply`, idempotent) converts. Write NEW bullets in the `**Sources**` grammar.
   - **NAME THE RECORD IN THE SUB-BULLET**, never a bare locator: a locator says where, only the description says what, and a census that cannot say what it counts cannot be audited.
   - **Include limbs:** (a) FS-indexed record ARKs (`1:1:`); (a2) FS image ARKs (`3:1:`) for browse-only registers, **but a `3:1:` may be a digitised BOOK; only the collection title can tell, so read it and screen with `harvest_sources.is_book_collection(title)` before crediting**; (b) external archive image links from a source's "Web Page (Link to the Record)" field pointing at a primary register (Antenati, metryki, szukajwarchiwach).
   - **Exclude limbs:**
     - (c) **Published books and journals**: bibliographic; cite the important ones in prose with page numbers, note their count in the bullet, never fabricate ARKs. One home: `harvest_sources.is_book_collection(title)` (books wear record-shaped locators on BOTH hosts). ⭐ **Exception: a printed TRANSCRIPTION of a primary record series IS a record** (printed town Vital Records, county Deeds, County Court, Probate, Wills Abstracts): the line is TRANSCRIPTION vs NARRATIVE, not print vs film. ⛔ Any future move of this class must widen `is_book_collection` AND `SCHOLARLY_CITATION_RE` in the same commit (pinned: `scripts/test_printed_record_series.py`). The marker list deliberately under-catches: a false positive DESTROYS a real record.
     - (d) **User trees** (RootsFinder, copied Ancestry/WikiTree/Geni): not independent evidence. Also (d): **user-editable reference sites** (Wikipedia, Quora and kin): negate with `~`; ⛔ a deep entry must never reach `profile_status: complete` on Wikipedia. Edited citable works (Britannica, the IGI, named encyclopaedias) fall under (c). One home: `harvest_sources.reference_work_limb(title)` / `is_reference_work`.
     - (e) **Memorial and headstone indexes: the test is the ARTIFACT, three tiers.** Tier 1: **a photographed stone whose image you have seen, cut at or near the burial, IS a primary record and COUNTS**, whatever index hosts it (say the photo was read and when; ⚠ never sufficient alone for a BIRTH date). Tier 2: an image-less memorial page is a contributor's assertion, worth nothing: negate (`~fs:1:1:…`). Tier 3: **a modern commemorative monument is SECONDARY even when photographed** (marker age relative to the death decides); record off-metric in a `- **Burial evidence**` bullet saying it is post-hoc (also the home for a read stone whose subject is a RELATIVE). Class detector: `harvest_sources.is_memorial_collection(title)` (JOWBR deliberately allowlisted); it decides the CLASS, not the TIER, which needs the memorial opened. ⚠ The FS `Find a Grave Index` record's `Photograph Included` Y/N field mechanically separates tier 2, but it is client-rendered (a raw fetch silently reports it absent) and BillionGraves records lack it. Apply (e) at HARVEST time, when the citation shows the collection title; a bare ARK already in the vault cannot be classified afterwards.
     - (f) **Obituaries are SECONDARY and do not count** (per [reference/source-hierarchy.md](reference/source-hierarchy.md)). Record them in a labelled off-metric bullet with `~`-negated locators (often the richest naming source for 20th-century collateral). One obituary is ONE item however many personas FS mints; a RELATIVE's obituary is limbs (g)/(h) and counts only for the person whose death it reports. Screens: `harvest_sources.is_obituary_collection(title)` + `obituary_postdates_death(title, event_year, died_year)`; a title match is a screen, not a verdict; a missing year is judged neither way.
     - (g) **A child's record naming a parent is `Named-in` EVIDENCE: off the census, recorded, never counted.** Labelled bullet, `~`-negated locators:

       ```
       - **Named-in** (off the ARK coverage metric; each documents a CHILD and names him as the father):
         - son <Son's name>'s 1946 death, naming "<Name>" as his father — ~fs:1:1:XXXX-XXX
       ```

       ⚠ The bullet NAME does nothing mechanically; **the `~` is what suppresses** (deliberate: bullet text must not be a failure surface). Does not re-open Spec 05: the parent is credited nothing; a `Named-in`-only person stays SOURCE_GAP (upheld 07 AUG 2026; do not re-litigate without new measurement; `bio_completeness` still scores such a person TRUE on `sources`). ⚠ Do not write "Sources: none" on such an entry (only an OWN-LIFE record is missing), and re-check `profile_status` in the same edit.
     - (h) **A sibling's record credits nothing at all**, not even identity, but is RECORDED in a labelled `- **Sibling records on the profile**` bullet with `~`-negated locators: the `~` says "seen and dismissed"; absence says nothing. ⚠ Limbs (g)+(h) are most of a typical FS Sources tab (an FS profile is closer to a HOUSEHOLD's record set than one person's): **group by the event descriptor in each citation BEFORE writing a Sources bullet**.
   - **`~` negation.** A `~` prefix marks a locator that is deliberately NOT evidence; `harvest_sources.strip_negated_locators` suppresses it before any counter runs (pinned: `scripts/test_negated_locators.py`). Use for (d)/(e)/(f) exclusions, detached or superseded ARKs, locators pending an identity check. An unmarked locator on the same line still counts.
     - ⭐⭐ **MIGRATE OR NEGATE: never leave a bare ARK in prose.** A bare ARK (no `host:` prefix) still counts, and `~fs:1:1:X` cannot negate a bare `X` (the `~` attaches to the token AS WRITTEN). Fix every bare ARK you meet: **migrate** (add the host prefix) when the prose is a real citation; **negate** when it refutes, excludes, or merely discusses. ⛔ Never delete: a deleted locator is indistinguishable from one nobody looked at.
     - ⛔⛔ **`~` suppresses a token EVERYWHERE in the ENTRY, not on its line.** Decision rule: is the token cited un-negated elsewhere in the same entry? If yes, MIGRATE the prose mention (negating would destroy the citation, the ordinary case when an entry quotes its own best record). Scope stops at the entry, which is why the correct way to mention a relative's record on someone else's entry is `~`-negated with its reason: it credits nobody twice and leaves the relative's own citation intact. ⚠ Diff the census BY ROW after either fix; negation is non-monotonic.
     - ⛔⛔ **Do not bulk-negate**: most bare ARKs are ordinary evidence nobody migrated, and a blanket `~` pass destroys real citations. Gate: `scripts/bare_ark_audit.py` (`--changed-only` BLOCKING in the vault pre-commit on added/modified lines; whole-vault backlog advisory, banner `bare-arks`, baseline not 0, only ever goes down).
   - **Entry boundary.** A bold name at LINE START is an entry header; anywhere else it is prose. Bold an archive or relative mid-sentence freely; do NOT begin a line with a bold `Words (parenthetical)` span unless it is a person entry. Gate: `python3 scripts/entry_boundary_audit.py` (HARD `ENTRY_MISATTRIBUTION`, baseline 0, pre-commit; `SOURCE_MISATTRIBUTION` = the subset landing on Sources). **When it fires, the fault is in the PARSER; do not rewrite the narrative to appease it.**
   - **A cross-reference does not inherit sources (Spec 05).** A relative's sources inside someone else's entry go on that relative's OWN bullet with locators (`- **FS-attached sources for wife <Name>** (<PID>, inline collateral; …): …`); a name in a `- Siblings/Children/Parents:` list credits nothing. Rule 6 is the header-level counterpart.
   - **Cite a locator, never the locator FORM**: name a locator class in words; a bare `host:type:` prefix written as a class name once counted as a record.
   - **WikiTree corroboration is a separate qualitative layer, not part of the ARK metric.** Capture what a profile CITES and its analytical content as `- **WikiTree corroboration** (<ID>, read <date>; off the FS-ARK coverage metric): …`; never its bare assertion. Operator-gated; mechanics in [prompts/19-fs-source-harvest.md](prompts/19-fs-source-harvest.md).
   - ⚠ **Detail View MUST be ON before extracting** from the FS Sources tab (ARK hrefs and external links only enter the DOM with it on; a fresh navigate usually needs a second JS call). Off = a false "0 ARKs" read.
   - ⚠ **The Sources tab shows only what is attached.** The other half (unattached hints, possible duplicates, data problems, prior not-a-match decisions) is the Research Help card, which never renders under automation: fetch the page's own endpoints instead (endpoints and calibration in [prompts/19-fs-source-harvest.md](prompts/19-fs-source-harvest.md)). Policy: **a hint is a CANDIDATE, not a record** (evaluate on identifiers; a score is not evidence), and **attaching a hint is a WRITE to a shared public tree: operator-gated**; reading is free, queue the attach.
   - The Recipe-S harvest mechanics and the `harvest_sources.py` CLI: [prompts/19-fs-source-harvest.md](prompts/19-fs-source-harvest.md) (this rule keeps the include/exclude POLICY). Census categories: **SOURCE_GAP** (0 ARKs), **LOW_COVERAGE** (1-3), **WELL_SOURCED** (4+), printed in the SessionStart banner. New PID + entry: harvest same session if practical, else queue; SOURCE_GAP output is the canonical Recipe-S priority list.
   - **An outward write the vault cannot perform is QUEUED ON THE ENTRY, not in a ledger file.** Grammar exact because a grep is the ledger:

     ```
     - **FS write-back QUEUED 31 JUL 2026** (<PID>; promote birth conclusion): FS carries year-only
       1909; the vault holds 12 OCT 1908 — evidence fs:1:1:XXXX-XXX (NYC birth record) — life_status: deceased
     ```

     | Slot | Rule |
     |---|---|
     | token | `FS write-back` + `QUEUED` / `DONE` / `DROPPED`, bolded, then the date. Three states, no fourth; an item that no longer applies is DROPPED with its reason, never deleted. |
     | paren | `(<PID>; <action or note>)`; semicolons inside, never commas. |
     | body | what and why, then `— evidence <host:locator>`, then `— life_status: <value>`, in that order, on QUEUED. DONE says what was actually written. |
     | HELD | not a fourth state: a waiting item stays QUEUED and says `— **HELD, do not act yet**`. |

     Readers match case-insensitively, accept `writeback`, ignore a leading check mark: count on the words. DONE REPLACES QUEUED. The ledger is EMERGENT: `grep -ric "FS write-back QUEUED" [VAULT]/Family_Tree*.md`; no queue file, no meta key. Evidence and `life_status` are part of the grammar (per-target gate: `scripts/privacy_gate.py`). A queued item is a CANDIDATE: name the identifier check that would settle it. Produced by `23-session-review`, drained by `17-familysearch-tree-contribution` with the operator present; deliberately NOT a session-plan lane (write-back is a byproduct, not a driver).

9. **The meta block is the machine record; keep it lean.** Only the fixed-grammar fields; research-history prose lives in the narrative body. Sub-rules:
   - ⚠ **A key written twice is valid YAML and last-wins, silently discarding a value.** `DUP_META_KEY` is HARD in `gen_person_index --integrity` (baseline 0); the write side is `person_store.set_meta_key(line, key, value)`: **write meta keys through that, never by splicing text**. The gate and the reader share one splitter (`_split_flow_items`).
   - **Files stay sorted by `generation`** within each section; collateral files keep family grouping. No deferred addition tables: fold new people into the right section immediately.
   - **Pre-commit expectation**: which gates block and how to read a non-zero is the **`audit-gates` skill**. `DUP_FS_PID` is ADVISORY (an FS PID is an external attribute; expected baseline in `known_dup_fs_pids`); a known field-drift or gen-numbering backlog is a separate task, not a commit blocker.

## Content-boundary policy (per-lineage file routing)

A lineage that outgrows one file is split into companion shards by content ROLE, not just size:

| Content role | File |
|---|---|
| Direct-line ancestor + spouse | the lineage's main `Family_Tree_<Region>.md` |
| Immediate sibling-collateral that authenticates a direct ancestor (atto declarant/witness, primary-source kin proxy) — 1-2 line inline entry | same main file |
| Extended sibling-collateral with its own multi-source sub-pedigree; in-law deep pedigrees; surname-cluster collateral discovered via record scans | `Family_Tree_<Region>_Collateral.md` |
| Region/surname "Origins and Toponymy" essay once it crosses the shard threshold | `Family_Tree_<Region>_Origins.md` (a 2-line pointer stays inline) |
| Open questions, hypotheses, methodology, register-scan plans | a `<Region>_Extension_Plan.md` (planning-only; no ancestor entries) |
| Witnesses/sponsors at vault-direct events | `Witness_Network.md` |

**The file an ancestor's entry lives in** is where their full sourced write-up sits, not where they appear as a sibling-link; the roster groups by that file. When migrating an entry between files, move it with its `- meta:` block intact (never re-mint its `id`), in the same commit, gen-sorted, and confirm it landed under the right heading.

**A given vault's specific lineages, companion-file layout, and generation-anchor table are per-client facts: keep them in a gitignored `CLAUDE.instance.md`, never in this file.**
