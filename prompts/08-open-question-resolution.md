# Open Question Resolution

Work the vault's register of unresolved research, `Open_Questions.md`, question by
question: pick the ones a named resolver can actually settle, execute that resolver,
and record the outcome so the register shrinks instead of accumulating.

**Rewritten 03 AUG 2026 (session #135).** The previous version had never been revised
for content since the initial release, and by then it disagreed with the vault in ways
that would have caused damage rather than staleness: it told you to hand move resolved
text into `Open_Questions_Resolved.md` under a level 2 heading (the file uses level 3,
and `archive_sections.py` owns that move, with a versioned snapshot and a compact index
row), to update "person files" (a `narrative` vault has none), and to parse the whole
register (388 KB on the reference vault, which the standing context rules forbid). Its
`Verify` counted **lines containing the word OPEN**, reporting 29 against 41 genuinely
open questions. Every one of those is corrected below.

> **Sharded trees (optional):** if `Family_Tree.md` has grown and been split into shard
> files (listed in its File Index), treat every reference to `Family_Tree.md` as covering
> those shards: route each person to the shard whose Region matches their line. Locate a
> person with `python3 scripts/tree_locator.py`. Un-sharded vaults can ignore this note.

**This is a THEMED prompt, not a lane.** The session loop's three lanes (EXPAND,
IMPROVE, ROTATE) are drawn by `session_plan.py`; this prompt is not one of them and
produces **no lane observation**. Run it when the operator asks for it, or when the
register has grown faster than the lanes are draining it. Two real interactions:

- **Raising a question is a DISPOSITION in the IMPROVE lane, counted once.** If a
  question you resolve here was somebody's IMPROVE unit, that is fine; but resolving it
  does not re-credit the row.
- **Resolving a question UN-SUPPRESSES its people in the IMPROVE defect pool**
  (deferred 44): `session_plan.open_question_ids()` reads the LIVE register only, so a
  gate finding demoted while its question was open returns to normal rank once the
  question is archived out. That is intended.

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree. Every command runs with
  `AUTORESEARCH_VAULT="[VAULT_PATH]"`; there is no default vault.
- **[ITERATIONS]** (optional, default 5) — how many questions to attempt.
- **[FILTER]** (optional) — narrow the triage, e.g. a surname, a region, `direct line`.

## Autoresearch Configuration

**Goal**: Reduce the count of live numbered questions in `Open_Questions.md` by
executing the resolver each one already names, and leave every question you touch either
closed with its evidence, advanced with what changed, or annotated with why its stated
resolver failed.

**Metric**: Live numbered questions, i.e. `### N.` headings with no terminal status.
`PARTIALLY_RESOLVED` counts as LIVE: it is a progress marker, not a terminal state.

**Direction**: Minimize.

**Verify**:

```bash
python3 -c "
import re,os
p=os.path.join(os.environ['AUTORESEARCH_VAULT'],'Open_Questions.md')
h=[l for l in open(p) if re.match(r'^### \d+\.',l)]
T=r'(RESOLVED|RULED OUT|CLOSED|CONFIRMED FAIL|FULLY RESOLVED|SUPERSEDED|MOVED|WITHDRAWN)'
term=[l for l in h if re.search(r'—\s*'+T+r'\b',l)]
part=[l for l in h if 'PARTIALLY' in l.upper()]
print(f'OPEN {len(h)-len(term)} (of {len(h)} numbered; {len(part)} PARTIALLY_RESOLVED, still live; {len(term)} terminal, awaiting archive)')
"
```

**Guard**:

- ⛔ **NEVER FULL READ `Open_Questions.md`.** It is a few hundred KB and the standing
  context rules forbid it. Triage from HEADINGS, then extract only the blocks you chose
  (`awk '/^### 114\./,/^### 115\./'`). A prompt that begins by reading the whole register
  has spent the sitting before it starts.
- ⛔ **DO NOT hand move resolved text into `Open_Questions_Resolved.md`.** Change the
  heading in place and leave the write-up in the body; `archive_sections.py --target
  open-questions` performs the migration (versioned snapshot, full text to the Resolved
  file, ONE row into `## Resolved & Closed — Index`). Hand moving bypasses the snapshot
  and the index row, and gets the heading level wrong.
- ⛔ **DO NOT hand wrap a resolved heading in `~~strikethrough~~`.** The compact index
  model replaced the old struck-heading tombstones on 01 JUL 2026.
- **Terminal status must be the FIRST word after the LAST em dash.** Put any qualifier
  in parentheses AFTER it: `— RESOLVED 03 AUG 2026 (parish register)`, never
  `— parish register RESOLVED`. The archiver detects on that position.
- **RESOLVED requires the Strong Signal standard**: two independent sources, or one
  authoritative primary record. Anything less is `PARTIALLY_RESOLVED` with what was
  found and what remains.
- **Do not overturn a question already marked RESOLVED** unless you have contradicting
  evidence, and then say so explicitly rather than editing the old conclusion away.
- **A null is a statement about the SEARCH, not the record.** Name what was searched and
  what that search structurally cannot contain. Calibrate it: prove the surface holds the
  population before reporting a zero (a nonsense control that returns the same answer
  means the METHOD is broken, not the data).
- **Check before searching, per source.** Grep `logs/` and the question's own body for
  what has already been tried. A resolver already run and failed is recorded, not rerun.
- **Never web search a person whose `life_status` is `living` or `unknown`.**
- **Outward mutations stay operator gated.** A FamilySearch attach, merge, edit or
  create is QUEUED on the person's entry in the rule 8 grammar, never performed here.
- **If the stated resolver turns out to be wrong or exhausted, that IS the deliverable.**
  Rewrite the question's resolver with what you learned; a question whose route has been
  disproved is more useful than one nobody has touched.
- **A question with no named resolver is a complaint, not a research task.** If you meet
  one, give it a resolver or say plainly that none exists.
- **Cascade in the same commit.** A resolution that changes a fact must update the
  narrative entry, any prose that paraphrases it, and `Timeline.md` where dated. Then run
  `prose_audit.py`; `DATE_DRIFT` is blocking.
- **`Research_Log.md` is appended with `scripts/log_session.py`, never the Edit tool.**
  It is a large append only file and an Edit forces a full read of it.
- One logical unit per commit; the pre-commit gates pass every time; no `--no-verify`.

**Iterations**: [ITERATIONS] (default 5) — one iteration is ONE question attempted and
recorded. Attempting a question and failing to move it is a legitimate iteration **only
if the failure is written down**; an untouched question is not an iteration.

**Protocol**:

1. **TRIAGE FROM HEADINGS, NOT FROM THE FILE.** Build the candidate list without reading
   the register:

   ```bash
   python3 -c "
   import re,os,sys
   p=os.path.join(os.environ['AUTORESEARCH_VAULT'],'Open_Questions.md')
   T=r'(RESOLVED|RULED OUT|CLOSED|CONFIRMED FAIL|FULLY RESOLVED|SUPERSEDED|MOVED|WITHDRAWN)'
   needle=(sys.argv[1].lower() if len(sys.argv)>1 else '')
   for n,l in enumerate(open(p),1):
       m=re.match(r'^### (\d+)\.\s*(.*)\$',l.rstrip())
       if not m or re.search(r'—\s*'+T+r'\b',l): continue
       if needle and needle not in l.lower(): continue
       tag='PART' if 'PARTIALLY' in l.upper() else 'OPEN'
       print(f'{n:>6}  {tag}  Q{m.group(1):<4} {m.group(2)[:104]}')
   " '[FILTER]'
   ```

   ⚠ **It must test the terminal status by POSITION, not by `grep -vi` on the words.**
   A keyword filter drops any heading that merely *mentions* one: measured on the
   reference vault it returned **33** live questions against a true **54**, silently
   hiding 21 of them, including several whose titles contain the word "RESOLVED" in a
   non-terminal position. That is the same defect this rewrite exists to fix, and it was
   caught only by checking the count against an independently computed one.

   Rank what comes back by **solvability first, then stakes**:
   a. a **named resolver that is free and reachable now** (a printed vital record on
      archive.org, an FS collection, a free index the vault already has an account for);
   b. a resolver that needs a subscription the operator holds;
   c. **direct line** ahead of collateral at equal solvability, because a direct line
      answer moves a whole branch;
   d. everything whose resolver is an archive visit or a paid request goes LAST, and is
      usually better left than half attempted.

2. **READ ONLY THE CHOSEN BLOCKS**, one at a time:
   `awk '/^### 114\./,/^### 115\./' "$AUTORESEARCH_VAULT/Open_Questions.md"`.
   Extract the actual question, the stated resolver, the evidence already gathered, and
   any recorded negative. Then grep `logs/` for the names involved.

3. **EXECUTE THE RESOLVER AS WRITTEN.** If it names a specific book, register or
   collection, go to that, not to a general search. Read the source itself rather than a
   summary of it, and calibrate every zero before believing it.

4. **RECORD THE OUTCOME, in the register and on the entries.**
   - **Resolved**: heading becomes
     `### N. Title — RESOLVED <DD MMM YYYY> (<short note>)`; the resolution write up
     stays in the body with its citations. Do not move it; do not strike it.
   - **Advanced**: keep the heading live, add a dated block saying what changed, what is
     now known, and what specifically remains. Mark `PARTIALLY_RESOLVED` in the heading
     only when there is a real partial answer, not merely effort spent.
   - **Resolver failed**: keep the question live and **rewrite its resolver**. Record the
     calibrated negative: what was searched, what it structurally cannot contain, and the
     next route. This is a successful iteration.
   - **Cascade**: update the narrative entry (route by shard), any prose that paraphrases
     it, `Timeline.md` if dated, and cross link the entry to the question both ways.
   - **New questions**: a resolution that opens a new problem gets its own numbered
     question with a resolver. Batch several thin findings of one shape into ONE question
     with a table rather than proliferating near empty entries.

5. **ARCHIVE, ONLY IF THE FILE IS OVER THRESHOLD.** Resolved blocks accumulate harmlessly
   until then:
   `python3 scripts/archive_sections.py --target open-questions` (dry run), review, then
   `--apply`. ⚠ Numbers are never reused: a question archived out keeps its number, so
   the next new question continues past the highest number in EITHER file.

6. **LOG AND REPORT.** Write the narrative to `logs/<today>-<slug>.md`: per question, the
   resolver executed, what was found, every negative, and every retraction. Append one row
   to the session index with
   `python3 scripts/log_session.py --log "logs/<today>-<slug>" --summary "..."`.
   Report resolved / advanced / resolver rewritten / new questions raised, and re-run the
   **Verify** command so the movement is measured rather than asserted.
