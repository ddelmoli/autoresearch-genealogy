# Session Review (phase 3 of 4: reconcile the sitting before closing it)

The prompt that reads the whole sitting back before anything is written into the
permanent record. It reconciles what was CLAIMED against what the tools SAY,
re-measures every lane metric against the session-start values, assembles the
**FS write-back queue** (the outward mutations the research surfaced but was not
allowed to perform), and hands `24-session-close` a set of facts to file rather
than a memory to reconstruct.

**New in the four-phase split (31 JUL 2026).** The old two-prompt loop went
straight from research to close, so the close prompt was simultaneously deciding
what happened, judging whether it was a hit, and running the checklist that
records it. Two consequences showed up in the record: an outcome recorded from
impression rather than from a re-measured metric (sixteen straight hits), and
write-back candidates that were noticed mid-research, mentioned once in a log,
and never surfaced anywhere an operator would see them.

**This phase performs no research and no writes to FamilySearch.** It reads,
reconciles, and queues. If it uncovers work, the work is queued, not started.

Copy-paste prompt (fill the placeholders):

```text
Review this research session before closing it. Every command runs with
AUTORESEARCH_VAULT="[VAULT_PATH]". Do NOT start new research in this phase, and
do NOT perform any FamilySearch write.

1. RECONSTRUCT THE SITTING FROM THE TOOLS, NOT FROM MEMORY. Read the vault's
   session_plan_snapshots.json (`arms`, `history`, `pending`) and build one row
   per iteration:

     # | lane | how drawn | lane target | actually worked | recorded outcome

   ! Reconcile the count: the OBSERVATIONS added to `history` this sitting must
   equal the iterations actually worked. (An "observation" is one recorded lane
   outcome; a "row" in this project is a worklist candidate, i.e. a person. One
   iteration works many rows and produces exactly one observation.) An iteration worked but never recorded is a
   missing observation; a record with no work behind it is a false one. Fix the
   mismatch now (record the missing outcome, or correct the note), because after
   the close nothing distinguishes it from a genuine session.

2. RE-MEASURE EVERY LANE METRIC and compare against the session-start values
   captured in phase 1:
     python3 scripts/extension_frontier.py --heartbeat     # SILENT / DECLARED
     python3 scripts/keystone_report.py --summary          # keystone count
     grep -rhoE "P-[0-9A-Z]{6}\?" [VAULT_PATH]/Family_Tree*.md | wc -l   # ? edges
     python3 scripts/profile_review.py --heartbeat         # rotation clock
   - ! Confirm each recorded hit/miss is STILL TRUE against these numbers. A
     recorded hit the heartbeat contradicts is corrected IN PLACE now (edit the
     history row's note and, if the outcome itself was wrong, say so explicitly
     in the log) — never left standing to be read later as a real observation.
   - Remember what each number means: EXPAND legitimately raises SILENT while
     adding people, so read the people added, not the backlog direction.

3. VERIFY THE GATES AGAINST THE BASELINE, NOT AGAINST AN EXIT CODE. A
   "[pre-commit] PASS" can coexist with a FLAGGED advisory gate, so passing is
   not the test. Run the suite and compare each number to the vault's
   .audit_baseline.txt:
     AUTORESEARCH_VAULT="[VAULT_PATH]" bash scripts/session_audit.sh
   Anything above baseline that THIS SITTING introduced is a regression: fix it
   before the close, not after. Anything above baseline you did not cause:
   investigate, or record why it is being left.

4. QUEUE THE FS WRITE-BACKS, ON THE ENTRIES. Every outward mutation this sitting
   surfaced and did not perform, because outward mutations are operator-gated.
   Sources to sweep: the iteration notes, the entries you touched, FS record
   hints and data-problem endpoints you read, and any duplicate or conflation
   you found. Typical items: attach an unattached record hint; merge a confirmed
   duplicate (or record a not-a-match); create a person FS does not hold; correct
   a relationship, date or name FS has wrong; a vault edge FS could confirm.

   ! THE QUEUE ITEM LIVES ON THE PERSON'S OWN ENTRY, not in a ledger file — the
   vault has recorded write-backs this way since June, and it is the only shape
   that survives the write-once rule for logs. Add ONE bullet per item, in the
   grammar of CLAUDE.method.md rule 8:

     - **FS write-back QUEUED <date>** (<PID>; <action>): <what and why>
       — evidence <host:locator> — life_status: deceased

   Then write the NARRATIVE (what you read, what it proves, what was ruled out)
   into logs/<today>-<slug>.md under a "## FS WRITE-BACK QUEUE" heading. The
   entry carries the state; the log carries the reasoning.

   Rules:
   - ! PRIVACY GATE PER TARGET. A public tree (FamilySearch, WikiTree) denies
     life_status living AND unknown; a private tree may include them. Mark each
     item with the person's life_status and never queue a living or unknown
     person against a public target. scripts/privacy_gate.py decides this in one
     place.
   - A HINT IS A CANDIDATE, NOT A RECORD. Anything queued off an FS hint says so,
     and carries the identifier check that would justify attaching it.
   - An item about someone with NO vault entry gets the entry first (that is
     EXPAND work); until it has one, the item lives only in the log and must be
     named explicitly in OPEN / NEXT, because no grep can see it.
   - Do NOT perform any of it here. 17-familysearch-tree-contribution drains the
     queue with the operator present, and rewrites each bullet to its DONE form.
   - Report the COUNT, derived not hand-counted:
     grep -ric "FS write-back QUEUED" [VAULT_PATH]/Family_Tree*.md
     and hand that command's total, plus the log pointer, to the close prompt for
     OPEN / NEXT.

5. CONFIRM THE SESSION LOG IS COMPLETE: logs/<today>-<slug>.md exists, carries
   the narrative of every iteration, every negative, every record citation and
   every retraction, and now the write-back queue. The close block will INDEX
   this file, so anything missing here is lost.

6. COLLECT THE CLOSE-BLOCK MATERIAL, so phase 4 only files it:
   - GATES: at baseline, or the one exception.
   - WHAT MOVED: per iteration, in the lane's own unit.
   - FINDINGS: at most 5, one sentence each.
   - RETRACTIONS: what you asserted this sitting that turned out wrong. REQUIRED;
     may say "none". ! A field filled only when convenient is not a record.
   - NEGATIVES / DO-NOT-REDO: routes now closed, with what made them closed.
   - NEW TRAPS: tool behaviours and do-not-conflate warnings.
   - OPEN / NEXT: what is left, including unworked iterations, unpolled rotation
     entries, and the write-back queue count.
   - OPERATOR QUEUE DELTA: deferred_decisions items added or resolved.

7. REPORT ALL OF THIS TO ME IN ONE SUMMARY, then continue with
   24-session-close.
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (same value used in
  `21-session-start.md`).

## Autoresearch Configuration

**Goal**: Reconcile the sitting against the tools before it becomes the permanent
record: every iteration accounted for, every recorded outcome still true when
re-measured, every gate at or below baseline, every operator-gated write-back
surfaced where an operator will see it, and the close block's material assembled.

**Metric**: Unreconciled items at hand-off to phase 4: iterations worked but not
recorded (or recorded but not worked); recorded outcomes the heartbeats
contradict; gate counts above baseline that are neither fixed nor explained;
write-back candidates surfaced in the work but carrying no `FS write-back
QUEUED` bullet on their entry; required close-block fields with no material.

**Direction**: Minimize (target 0).

**Verify**: the vault's `session_plan_snapshots.json` (observations added to
`history` this sitting = iterations worked); `extension_frontier.py --heartbeat`;
`keystone_report.py --summary`; the `?`-token grep; `profile_review.py
--heartbeat`; `bash scripts/session_audit.sh` compared line by line against
`.audit_baseline.txt`; `grep -ric "FS write-back QUEUED" [VAULT_PATH]/Family_Tree*.md`
(the emergent queue ledger) alongside the "## FS WRITE-BACK QUEUE" section of
`logs/<today>-<slug>.md`.

**Guard**:
- **No new research in this phase, and no FamilySearch writes.** Work uncovered
  here is queued for the next session, not started. The queue is the deliverable.
- **A recorded outcome the heartbeat contradicts is corrected NOW.** After the
  close, a wrong observation is indistinguishable from a real one, and it is the
  input the next session's draw is computed from.
- **Read the metric in its own direction.** EXPAND raising SILENT while adding
  people is the working shape, not a regression; the lane target is in people.
- **An advisory gate can be FLAGGED inside a passing pre-commit.** "PASS" is not
  the baseline check; reading the numbers is the baseline check.
- **The write-back queue carries EVIDENCE and a PRIVACY MARK per item**, or it is
  not queued. A queue of bare PIDs asks the next session to redo the research
  that justified it, and an unmarked living person is a privacy incident waiting
  for a later, less careful pass.
- **The queue is ENTRY STATE, not a ledger file, and not a log-only note.** A log
  is write-once, so an item recorded only there can never be marked done where it
  was written; a separate queue file is a second store that nothing audits. One
  bullet on the person, replaced by its DONE form when performed, is the shape
  the vault already uses and the only one that stays true.
- **A hint is a candidate.** FS matches on name, date and place; queue it as a
  hint with the identifier check that would settle it, never as a record.
- **Partial work is named, not rounded off.** Unworked iterations and unpolled
  rotation entries are listed individually; "mostly done" is not a state the next
  session can act on.
- **No hand-copied derivable metrics.** Canonical, census, SILENT/DECLARED and
  every gate count are computed by the banner each session; a copy goes stale
  silently. Keep a number only when the number IS the finding.

**Iterations**: 1 — **this prompt is a PHASE, not a loop**. Reviewing a sitting
twice reviews the same sitting; if new work happened in between, that work was an
iteration of `22-research-iterations` and is reviewed as part of the same sitting.

**Protocol**:

1. Rebuild the per-iteration table from `session_plan_snapshots.json` and
   reconcile its count against the work actually done.
2. Re-measure the four lane metrics; confirm or correct each recorded outcome.
3. Run the audit suite and compare against `.audit_baseline.txt`; fix what this
   sitting introduced.
4. Queue each FS write-back as a bullet on the person's own entry (evidence +
   per-target privacy mark), with the reasoning in the session log; report the
   count from the grep, not by hand.
5. Confirm the session log is complete.
6. Assemble the close-block material, including the required RETRACTIONS and
   NEGATIVES / DO-NOT-REDO fields.
7. Summarize to the operator and hand off to `24-session-close`.
