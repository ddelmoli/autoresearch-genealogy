# Open Question Resolution

Work the vault's register of unresolved research question by question: pick the ones a
named resolver can actually settle, execute that resolver, and record the outcome so the
register drains instead of accumulating.

**Rewritten 15 AUG 2026 (session #169). The previous version's COMMANDS WERE DEAD and
failed silently** — its `Verify` and its triage both parsed `Open_Questions.md`, which has
held zero question blocks since the 12 AUG lineage shard split, so run verbatim they
reported `OPEN 0 (of 0 numbered)` and returned **0 candidates against 135 live questions**.
A sitting dispatched on it would have triaged nothing and then measured itself successful.

⭐ **THE LESSON IS WHY THIS VERSION EMBEDS NO PARSER.** The 03 AUG rewrite had already
fixed that generation's parser bugs; the register was re-laid-out underneath it and the
prompt could not follow, because it carried its own copy of the grammar. **Every command
below calls a tool that reads the ONE home (`scripts/question_block.py`).** When the
register moves again, the tools move and this prompt keeps working. Do not reintroduce an
`awk` range, a `grep -vi` status filter, or an inline heading regex — each has already
shipped a silent wrong answer here.

> **Sharded trees:** route each person to the shard whose Region matches their line;
> locate one with `python3 scripts/tree_locator.py`.

**This is a THEMED prompt, not a lane.** The loop's lanes (EXPAND, IMPROVE, ROTATE) are
drawn by `session_plan.py`; this produces **no lane observation**. Two relationships:

- **Prompt 22 covers the INCIDENTAL case** — when a drawn lane runs dry or is blocked
  mid-sitting, its drain rule sends the session to the register for the rest of the
  iteration. **This prompt is the DELIBERATE case:** a whole sitting pointed at the
  register because it has grown faster than the lanes drain it.
- **Resolving a question UN-SUPPRESSES its people in the IMPROVE defect pool**
  (deferred 44). `session_plan.open_question_ids()` reads every LIVE shard, so a gate
  finding demoted while its question was open returns to normal rank once the question is
  archived out. That is intended. ⚠ That function read only the router between 12 and 15
  AUG and the suppression set had collapsed 238 -> 3; if IMPROVE starts offering rows that
  are fully characterised in a live question, suspect it again.

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree. Every command runs with
  `AUTORESEARCH_VAULT="[VAULT_PATH]"`; there is no default vault.
- **[ITERATIONS]** (optional, default 5) — how many questions to attempt.
- **[FILTER]** (optional) — narrow the triage to a tag (`free`, `UNREAD-SRC`, `op-gated`,
  `BIG`) or grep the index for a surname, region or shard.

## Autoresearch Configuration

**Goal**: Drain the register. Leave every question you touch in one of five recorded
states — closed with its evidence, advanced with what changed, its failed resolver
rewritten, its missing resolver supplied, or its bloated block triaged — and leave the
register's structure at baseline.

**Metric**: Live questions, computed by the shared model (`gen_question_index.py`), never
by a hand-rolled count. `PARTIALLY_RESOLVED` is LIVE: it is a progress marker, not a
terminal state.

**Direction**: Minimize.

**Verify**:

```bash
AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/gen_question_index.py --heartbeat
AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/question_audit.py
```

The first line is the metric (live count, KB, and the triage tag totals). The second is the
register's structural health: HARD findings are baseline 0, and the advisory tail
(`RESOLVERLESS`, `BIG_BLOCK`) is itself a worklist this prompt can work.

**Guard**:

- ⛔ **WRITE EVERY OUTCOME THROUGH `scripts/question_store.py`, NEVER the Edit tool.**
  `--resolve` writes an archivable heading and refuses a duplicate or an already-terminal
  block; `--append` lands a write-up INSIDE the right block; `--new` mints the next global
  number and requires a resolver. Hand-editing a shard is how eight resolution write-ups
  were orphaned, a live question was destroyed by an index rebuild, and a resolved question
  sat live for nine days. The pre-commit gate (`question_audit --changed-only`) now blocks
  the structural half of that, but it cannot un-orphan a write-up after the fact.
- ⛔ **NEVER hand-move text into `Open_Questions_Resolved.md`, and never hand-strike a
  heading.** `--resolve` marks it; `archive_sections.py` performs the migration with a
  versioned snapshot and one compact-index row; `session_close.py` runs that archive step
  every sitting, so a resolved block does not need you to chase it.
- ⛔ **NEVER hand-number a question.** `--new` mints across all ten shards AND the Resolved
  store. Numbers are global and never reused.
- **Terminal status is the FIRST word after the LAST em-dash**, qualifiers in parens after
  it. `--resolve` constructs this for you and verifies the result is archivable — which is
  the point of using it.
- **`RESOLVED` requires the Strong Signal standard**: two independent sources, or one
  authoritative primary record. Anything less is an ADVANCE, recorded with what was found
  and what remains.
- **Do not overturn a question already marked RESOLVED** without contradicting evidence,
  and then say so explicitly rather than editing the old conclusion away.
- **A null is a statement about the SEARCH, not the record.** Name what was searched and
  what that search structurally cannot contain, and calibrate it: a nonsense control that
  returns the same answer means the METHOD is broken, not the data. ⚠ Identical failures
  across every probe in a batch is that signature.
- **Check before searching, per source.** Read the question's own body and grep `logs/`
  for what has already been tried. ⚠ **A resolver already run is recorded, not rerun** —
  #168 re-read an article the vault had read in full three weeks earlier and gained
  nothing; the question's own resolver line had said "same repository already used".
- **ROUTE FACTS GO TO THE ROUTE REGISTER, NOT INTO THE QUESTION.** A coverage boundary or
  a spent search is true whichever person you research: put it in `Route_Register.md`
  (CLAUDE.method.md, "Knowledge routing") and let the question keep only what is specific
  to it. A route fact buried in a question body is findable only by accident.
- **Never web-search a person whose `life_status` is `living` or `unknown`.**
- **Outward mutations stay operator-gated.** A FamilySearch attach, merge, edit or create
  is QUEUED on the person's entry in the rule 8 grammar, never performed here.
- **If the stated resolver turns out to be wrong or exhausted, that IS the deliverable.**
  Rewrite the resolver with what you learned. A question whose route has been disproved is
  worth more than one nobody has touched.
- **A question with no named resolver is a complaint, not a research task** — and there
  are currently 31 of them. Supplying one is a full iteration.
- **Cascade in the same commit.** A resolution that changes a fact updates the narrative
  entry (biography shape: conclusion into the life, not a new dated audit bullet), any
  prose that paraphrases it, and `Timeline.md` where dated. Then run `prose_audit.py`;
  `DATE_DRIFT` is blocking.
- **`Research_Log.md` is appended with `scripts/log_session.py`, never the Edit tool.**
- One logical unit per commit; the pre-commit gates pass every time; no `--no-verify`.

**Iterations**: [ITERATIONS] (default 5) — one iteration is ONE question attempted and
recorded. Attempting a question and failing to move it is a legitimate iteration **only if
the failure is written down**; an untouched question is not an iteration.

**Protocol**:

1. **TRIAGE FROM THE GENERATED INDEX.** It is ~26 KB and already carries the tags, the
   sizes and each question's first named resolver:

   ```bash
   AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/gen_question_index.py --tag [FILTER]
   ```

   Omit `--tag` for the whole register; read `Open_Questions_Index.md` directly if it is
   fresher for you. ⚠ **If the index looks stale, regenerate it** (`--write
   [VAULT_PATH]/Open_Questions_Index.md`) rather than working from a snapshot.

   **Rank by cost-to-answer, then stakes:**
   a. **`UNREAD-SRC` — the cheapest class in the register.** The source is already located
      or attached and simply has not been read. No search at all; open it.
   b. **`free`** — a named resolver executable now. ⚠ The tag is keyword-derived and does
      NOT know about the operator's subscriptions: **"free" means no NEW cost**, so an
      Ancestry, JewishGen, Gesher Galicia, Internet Archive, OpenAthens, FCPL or GRONI
      route is also cheap even when untagged. Judge the resolver, not the tag.
   c. **`RESOLVERLESS` questions** (from `question_audit`) — give one a resolver, or say
      plainly that none exists. Cheap, and it converts a dead entry into workable stock.
   d. **direct line before collateral** at equal solvability: it moves a whole branch.
   e. **`BIG` blocks** — over 15 KB is accreted session narration, not a question. Triage
      it: current state plus resolver at the top, chronology to `logs/`, route facts to the
      route register. ⚠ Diff the census by row if moved prose carries locators.
   f. **`op-gated`, archive visits and paid requests go LAST**, and are usually better left
      than half-attempted.

2. **READ THE CHOSEN BLOCK, whole and by itself:**

   ```bash
   AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/question_store.py --show 114
   ```

   Then grep `logs/` for the names involved. ⛔ Do NOT `awk` a line range: questions are
   not contiguous and do not share a file. `--where` locates a number in any state
   (including a copy already archived).

3. **EXECUTE THE RESOLVER AS WRITTEN.** If it names a book, register or collection, go to
   that, not to a general search. Read the source itself rather than a summary of it, and
   calibrate every zero before believing it.

4. **RECORD THE OUTCOME.** One of five, all through the writer:

   | outcome | command |
   |---|---|
   | **Resolved** (Strong Signal met) | `--resolve N --status RESOLVED --note "<short>" --apply` |
   | **Advanced** | `--append N --sub-heading "⏩ WORKED <date> (session #N)" --body-file F --apply` |
   | **Resolver failed / rewritten** | `--append` with the calibrated negative AND the next route |
   | **Resolver supplied** | `--append` a `⏭ WHAT WOULD SETTLE IT` block to a RESOLVERLESS question |
   | **Block triaged** | `--append` the current-state summary; move chronology to `logs/`, route facts to `Route_Register.md` |

   Terminal keywords: `RESOLVED`, `FULLY RESOLVED`, `RESOLVED NEGATIVE`, `RULED OUT`,
   `CONFIRMED FAIL`, `CLOSED`, `CONFIRMED`, `DIGITALLY CLOSED`.
   **Cascade** to the entry, its prose and `Timeline.md`; cross-link entry and question
   both ways. **A resolution that opens a new problem** gets `--new` with a resolver —
   ⚠ but first check the index for an existing question of the same SHAPE and `--append`
   to it instead. Proliferating near-duplicates is how the register became unreadable.

5. **DO NOT CHASE THE ARCHIVE.** `session_close.py` runs every question archive target,
   regenerates the index and refreshes the router counts at close. Only if you need a
   shard smaller mid-sitting, run ONE named target (`--target` takes a single name, not a
   glob; `--list` shows them all):

   ```bash
   AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/archive_sections.py --target open-questions-method
   ```

   Review the dry-run, then re-run with `--apply`.

6. **LOG AND REPORT.** Write the narrative to `logs/<today>-<slug>.md`: per question, the
   resolver executed, what was found, every negative, every retraction. Append the index
   row with `log_session.py`. Then **re-run both Verify commands** and report the movement
   measured, not asserted: resolved / advanced / resolvers rewritten / resolvers supplied /
   blocks triaged / new questions raised, and the live count before and after.
