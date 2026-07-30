# Edge Verification (vault ⇄ FamilySearch reconciliation)

Reconcile the vault's relationship graph against the live FamilySearch tree connected to subject **[SUBJECT_PID]**. For every **unverified** parent/spouse edge in `vault/Family_Tree*.md` (an edge whose target id carries the `?` suffix — gedcom-seeded **or** vault-authored but not yet cross-checked against FS), walk the person's FS family page, compare, and classify the edge into one of four states: **CONFIRMED** (drop the `?`), **CONTRADICTED** (FS shows a different relative — stop, open an Open_Question, do NOT auto-change), **FS-GAP** (the edge is correct but absent on FS — leave `?`, queue for prompt-17), or **FS-CONFLATION** (FS carries an extra/duplicate couple the vault correctly avoids — queue for the FS-cleanup recipe).

This prompt is the verify/validate half of the Phase-2 edge work: `build_edges.py` *seeds* edges, `verify_edges.py` is the *writer* that drops/removes the `?`, and this prompt is the *driver* that points the autoresearch loop at the unverified-edge count. **It never mutates FamilySearch** — it only READS family pages. All FS-side fixes it discovers are routed to other loops (prompt-17 for adds, the `reference_fs_edit_reparent_method` recipe for detaches).

## Expected outcome distribution (read before running)

Most `?` edges that point at a relative who exists on FS will **CONFIRM** cleanly — the vault edge graph has been built from GEDCOM + vault narrative, both of which usually agree with FS. The valuable minority outcomes are:

- **CONTRADICTED** (rare, high-value): FS shows a *different* parent couple or spouse than the vault's `?` edge. This is a stop-and-ask gate that produces an Open_Question — a contradiction usually means either a vault error worth fixing or a genuine FS disagreement worth understanding. Never silently pick a side.
- **FS-GAP** (common on sparse-curation lines — Jewish/Italian/Polish): the vault edge is right but FS hasn't been linked yet (the relative exists on FS but the parent/child edge was never wired, or the relative is `fs: none`). The `?` stays; the edge is queued for prompt-17 to push up.
- **FS-CONFLATION**: FS attaches the person to *two or three* parent-couples (merge churn). The vault edge is the correct subset; queue the wrong FS couples for the detach/re-parent cleanup recipe.

The metric drops on every CONFIRMED edge (and on every CONTRADICTED edge once the operator resolves it), so the loop is convergent toward the floor.

## Tooling prerequisite (read first)

FamilySearch family pages must be read from an interactive logged-in session:
- **Claude in Chrome** at https://www.familysearch.org/ with the operator's FS account signed in; group tree [FS_GROUP_TREE], subject pedigree https://www.familysearch.org/en/tree/pedigree/landscape/[SUBJECT_PID].
- Local tooling (gitignored): `scripts/buildout.py` (`worklist` / `extractor`), `scripts/verify_edges.py` (the `?`-dropping writer), `scripts/build_edges.py --validate` and `scripts/gen_person_index.py --integrity` (gates). The FS-walk extractor + poll-for-PIDs pattern are in memory [[fs-anchor-walk-via-get-page-text-prompt-17-tooling]].

A WebSearch/WebFetch-only run cannot read the SPA family pages and so cannot verify; it can only report the worklist.

## Inputs To Replace

- **[SUBJECT_PID]** — the subject's FamilySearch PID (pedigree root).
- **[FS_GROUP_TREE]** — the family group-tree URL contributions must remain reachable from.
- **[VAULT_PATH]** — path to the vault working tree (the nested `vault/` repo).

## Autoresearch Configuration

**Goal**: Drive the count of unverified (`?`-suffixed) parent/spouse edges in `vault/Family_Tree*.md` to its irreducible floor by FS-walking each unverified edge's endpoints and resolving it — CONFIRM (drop `?`), CONTRADICTED (Open_Question + operator gate), FS-GAP (leave + queue for prompt-17), or FS-CONFLATION (queue for cleanup) — while never mutating FamilySearch and keeping the edge graph structurally clean.

**Metric**: Number of `?`-suffixed edge tokens across `vault/Family_Tree*.md`.

**Direction**: Minimize.

**Verify**: `grep -rhoE "P-[0-9A-Z]{6}\?" vault/Family_Tree*.md | wc -l` before and after each iteration; log the delta. The **floor is not 0** — it is the sum of edges that *cannot* be confirmed away: (a) held-out conflations (`flags: dup` / known merge-pending); (b) FS-GAP edges (correct but FS-absent — they belong to prompt-17, not here); (c) CONTRADICTED edges awaiting operator resolution; (d) edges on `life_status: living`/`unknown` (privacy-skipped). Report the breakdown so the convergence target is the *confirmable* remainder, which goes to 0.

**Guard**:
- **Read-only on FamilySearch.** This prompt performs ZERO FS mutations (no add, no detach, no save). It only reads `/tree/person/family/{PID}`. Every FS fix it finds is *routed*, never executed: FS-GAP → prompt-17 queue; FS-CONFLATION → `reference_fs_edit_reparent_method` cleanup queue.
- **Contradiction = hard stop-and-ask + Open_Question.** When FS shows a parent/spouse that disagrees with a vault `?` edge, do NOT drop, change, or remove the edge. Write an `Open_Questions.md` entry (vault edge vs FS edge, both ids + names + the conflicting source), then stop and surface it to the operator. A contradiction must be understood (vault error? FS error? two different same-name people?) before either side is changed. Resolution is operator-directed.
- **Vault writes are autonomous only for CONFIRMED edges** (dropping the `?` via `verify_edges.py`), under the pre-commit hook. Removing or rewriting an edge requires the operator decision from a resolved Open_Question.
- **Privacy gate**: skip any node whose meta is `life_status: living` or `life_status: unknown` — do not walk or verify their edges. Their `?` stays and counts toward the floor.
- **Held-out conflations stay held out**: do not touch edges flagged `dup` or otherwise marked as a known pending merge; leave their `?`.
- **Batch budget**: walk up to **~9 nodes per browser batch** (operator-gated FS reads; pace them). Cluster the worklist by family/file (reuse `buildout.py worklist`) so a single FS-walk of a parent couple confirms several children's edges at once.
- **Structural gates after every applied batch**: `build_edges.py --validate` structural violations must stay **0** (dangling + self + reciprocity); `gen_person_index.py --integrity` HARD must stay **0**. Confirm the apply is a **meta-only diff** before committing.
- **Vault is the default source of truth**; FS is the external cross-check. The prompt confirms/queues, it does not adopt FS edges into the vault wholesale (that would re-introduce the drift the Phase-2 design avoids). FS-only edges the vault lacks are reported, not auto-added.

**Iterations**: 10

**Protocol**:

1. **Baseline**: compute the Verify count + a per-file and per-floor-category breakdown (confirmable vs FS-GAP vs contradiction-pending vs living vs held-out). Record in `vault/logs/YYYY-MM-DD-edge-verification.md`.
2. **Select a batch**: pick ~9 deceased, non-held-out nodes carrying `?` edges, clustered by family/file (`python3 scripts/buildout.py worklist` gives per-file sets; prefer walking parent couples to confirm children in bulk).
3. **Walk**: for each node, navigate `/tree/person/family/{PID}` and run the `buildout.py extractor` JS (poll-for-PIDs, ~9/batch). Capture parents/spouse/children PIDs.
4. **Translate + classify**: map FS PIDs → vault ids (the `gen_person_index.parse_narrative` fs→id map). For each vault `?` edge on the node:
   - **CONFIRMED** — FS shows the same parent couple / spouse → mark for `?`-drop.
   - **CONTRADICTED** — FS shows a *different* relative → write the Open_Question, flag for operator gate, leave the edge untouched.
   - **FS-GAP** — relative absent on FS (parentless on FS, or `fs: none`) → leave `?`, append to the prompt-17 queue.
   - **FS-CONFLATION** — FS carries extra/duplicate couples → append the wrong couples to the cleanup queue; the vault edge is unaffected.
5. **Apply CONFIRMED**: build a `verify_edges.py` spec for the confirmed set, review the name-level output, then `--apply` (drops the `?`). Skip CONTRADICTED/FS-GAP edges (they keep their `?`).
6. **Gates**: `build_edges.py --validate` (structural 0) + `gen_person_index.py --integrity` (HARD 0); confirm meta-only diff; remove `.bak`.
7. **Commit + log** (one batch/cluster per commit): write the four-bucket reconciliation report (CONFIRMED / CONTRADICTED / FS-GAP / FS-CONFLATION counts + ids) and the metric delta to the session log; append CONTRADICTED items to `Open_Questions.md`; append FS-GAP and FS-CONFLATION items to their routed queues.
8. **Repeat** until a batch yields no new confirmations (the confirmable remainder is dry) or the iteration cap is reached. Report the residual floor breakdown so it's clear what's left and which downstream loop owns it.
