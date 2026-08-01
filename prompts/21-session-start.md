# Session Start (phase 1 of 4: initialize the session)

The prompt that OPENS every routine research session on a vault running the
mechanized session loop (`scripts/session_plan.py` / `scripts/session_close.py`).
It establishes the ground the session stands on, and it does no research: current
gate state, which vault, which session number, what the last session left, what
needs the operator's decision, and the name this session should run under.

**A full session is FOUR prompts, and only one of them is a loop:**

| Phase | Prompt | Loop? |
|---|---|---|
| 1. Initialize | **`21-session-start`** (this one) | no, single pass |
| 2. Research | `22-research-iterations` | **yes** — `Iterations: N` lane draws |
| 3. Review | `23-session-review` | no, single pass |
| 4. Close | `24-session-close` | no, single pass |

**Split out of the old combined start prompt (31 JUL 2026).** The earlier version
opened the session AND worked a lane AND carried the per-sitting obligations, so
its `Iterations` field meant two things at once: raising it was supposed to draw N
lanes, but the initialize steps and the per-sitting obligations sat inside the
same loop and had to be excluded one by one in prose. Phase 1 is now a single pass
with no research in it. **If you find yourself researching in this prompt, you
have skipped phase 2** — the lane draw lives there, and so does the work.

Copy-paste prompt (fill the placeholders):

```text
Initialize a research session. Do NOT start research in this prompt: this phase
establishes state and hands off to 22-research-iterations.

Environment: the toolkit needs AUTORESEARCH_VAULT="[VAULT_PATH]".
  - For the SessionStart HOOK to run at all, it must be exported in the shell
    that LAUNCHES the agent. Prefixing commands afterwards cannot fix a hook
    that has already run.
  - For your own commands, env vars do not persist between shell calls, so
    prefix each one:
    AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/session_plan.py

1. ESTABLISH THE CURRENT GATE STATE, and do not assume the banner exists.
   - If the SessionStart banner is present, read it: it carries the CURRENT
     gate values, the census, the frontier count and the timed-loop heartbeats.
   - ! CONFIRM WHICH VAULT IT AUDITED. The banner opens with
     "VAULT: <name> (source: ...)". The hook resolves the vault in four steps
     (env -> .claude/last_vault -> the sole vault-looking dir -> ask), and it
     cannot prompt me itself, so confirming a non-explicit choice is YOUR job:
       - source: env — I chose it explicitly. Nothing to confirm.
       - source: last-session / sole-candidate — it INFERRED the vault. Name it
         in your first reply and confirm before writing anything. Switch with
         bash scripts/session_audit.sh --set-vault /path/to/other-vault
       - "skipped — ... N candidate vaults exist" or "no vault-looking
         directory" — ASK me which vault; do not pick one.
       - "skipped — AUTORESEARCH_VAULT is set to '<path>', which does not look
         like a vault" — a typo or stale path in my launch shell. Quote the
         exact value back to me. Do not substitute a guess.
   - ! If the banner is skipped for any reason, you have NO current numbers.
     Once the vault is settled, run the suite yourself before any research:
     AUTORESEARCH_VAULT="[VAULT_PATH]" bash scripts/session_audit.sh
     Tell me the hook was skipped, so I can fix my launch shell.
   - Then COMPARE current values against the vault's .audit_baseline.txt. The
     baseline file is the EXPECTED state, not the current one; reading it alone
     tells you nothing about today. Investigate anything above baseline BEFORE
     research, and never hand off to phase 2 on a red HARD gate.
   - RECORD THE SESSION-START VALUES you will be judged against at review.
     The banner carries the frontier and census numbers; the other two are NOT
     in it, so run them:
       python3 scripts/harvest_sources.py --heartbeat        # SOURCE_GAP (IMPROVE)
       python3 scripts/keystone_report.py --summary          # keystones (report, no longer a lane)
       grep -rhoE "P-[0-9A-Z]{6}\?" [VAULT_PATH]/Family_Tree*.md | wc -l   # ? edges
     Phase 3 compares against these four, and a session that never wrote down a
     "before" cannot honestly report movement.

2. READ THE HANDOFF, which is the previous session's half of this handshake.
   Read `Handoff.md` "Start here" and the ONE live close block (not the archive):
     - OPEN / NEXT — the previous session's stated priority order.
     - Any announced PENDING DRAW. ! Verify it against the vault's
       session_plan_snapshots.json `pending` field rather than believing the
       prose: a close that ran the plan BEFORE the close command had its pending
       draw wiped by the close's own record step, and the announcement outlives
       the state. If they disagree, say so; the JSON is the truth.
     - The stored "Suggested rename for the next session" line (step 5).
     - `deferred_decisions.md` — the open items only.

3. ESTABLISH THE SESSION NUMBER and state it in your first reply. It is
   (the highest #N in Handoff.md + the Research_Log Session Index) + 1.
   ! Derive it, do not assume it follows the last one you personally saw: five
   commits in one sitting were written as "#118" when #118 was already taken by
   an earlier session THAT SAME DAY, and the number had to be retracted in the
   log afterwards. Every commit message, the log slug and the close block use
   the number you establish here.

4. SURFACE WHAT NEEDS ME, in one short list, before research starts:
   a. HOUSEKEEPING actions the audit reports DUE (`size_heartbeat.py`). Check
      `deferred_decisions.md` FIRST: an item already queued there is reported in
      one line and NOT re-asked, because the script cannot see that file.
   b. OPEN DEFERRED DECISIONS that are blocking or newly actionable — number,
      one line each, and what you need from me. Do not re-litigate parked items.
   c. THE FS WRITE-BACK QUEUE DEPTH, which is operator-gated work waiting on me.
      The banner's `writeback ->` line carries it, counted off the ENTRIES; if the
      banner was skipped, derive it:
      grep -ric "FS write-back QUEUED" [VAULT_PATH]/Family_Tree*.md
      Report the total and name the oldest few. No lane draws this queue by design
      (write-back is a byproduct, not a driver) and no gate fails when it grows,
      so that line is the only thing that keeps it visible; when it is deep enough
      to be worth a sitting, say so and offer 17-familysearch-tree-contribution
      instead of research iterations.
   d. Anything above baseline from step 1.
   Then: if I am present, ask with AskUserQuestion (multiSelect) and act on the
   answers. If I am away or this is an autonomous run, Operating_Protocol wins
   ("keep working, do not stop to ask"): queue the item in deferred_decisions.md
   with what it is and why it needs me, and carry on to phase 2. "BEFORE other
   work" in the heartbeat's own wording is NOT a licence to block.

5. SUGGEST THE SESSION RENAME COMMAND at the end of your first reply, in the
   form: Use "/rename <Day Mon DD HHh> <lane or theme>: <top target>"
   - ! DO NOT COMPOSE IT FROM SCRATCH FIRST. The previous close already wrote
     one, near the top of Handoff.md as "**Suggested rename for the next
     session:** `/rename ...`". READ IT and use it. It was authored before this
     session existed, so reconcile it against what step 2 actually found and
     sharpen it; say so if you changed it. The lane is not settled until phase 2
     draws, so name the theme and refine after the first draw if it moved.
   - If the hook injected its own rename reminder with a generated name, this is
     the same slot: prefer the lane-and-target form.

6. HAND OFF TO PHASE 2. Report: the vault and its source, gate state vs
   baseline, the session number, the pending draw (or none), the operator list,
   and the rename line. Then continue with 22-research-iterations
   (Iterations = [ITERATIONS], Lane target = [LANE_PCT]).
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (the private
  repo/directory holding `Family_Tree*.md`; e.g. `$(git rev-parse --show-toplevel)/vault-yourname`).
- **[ITERATIONS]** (optional, default 1) — how many lane draws phase 2 should
  run. Passed through to `22-research-iterations`; this prompt does not loop.
- **[LANE_PCT]** (optional) — the Lane target for phase 2, as a percent of the
  vault. Omit to inherit the profile-review `sample_percent`.

## Autoresearch Configuration

**Goal**: Put the session on known ground before any research happens: the right
vault, CURRENT gate values (not the baseline file, not last session's numbers),
the correct session number, the previous session's handoff read, everything
needing an operator decision surfaced once, and a session name proposed.

**Metric**: Preconditions left unestablished at hand-off to phase 2. The five:
(1) vault confirmed, (2) current gate values in hand and compared to baseline,
(3) session number derived, (4) Handoff read incl. pending-draw state verified
against the JSON, (5) operator items surfaced or queued — housekeeping DUE, open
deferred decisions, and the FS write-back queue depth.

**Direction**: Minimize (target 0).

**Verify**: the SessionStart banner, or `bash scripts/session_audit.sh` when it
was skipped; the vault's `.audit_baseline.txt` for comparison;
`python3 scripts/session_plan.py --heartbeat` and the `pending` field of
`session_plan_snapshots.json`; `Handoff.md` "Start here" plus the live close
block; `deferred_decisions.md` open items;
`grep -ric "FS write-back QUEUED" [VAULT_PATH]/Family_Tree*.md`.

**Guard**:
- **No research in this prompt.** The lane is drawn in phase 2. A session that
  starts researching here loses the draw, the lane target and the per-iteration
  record all at once.
- **A missing banner is a silent failure, not an empty one.** The hook skipping
  looks like an ordinary quiet start; there is no error to notice. Confirm you
  have current gate values, and say so when you had to generate them yourself.
- **A RESOLVED vault is not a CONFIRMED vault.** The hook falls back to the
  last-session vault or the sole candidate rather than skipping, which trades a
  silent no-op for a silent assumption. It labels the source for exactly that
  reason: an inferred vault gets named to the operator and confirmed before any
  write, and 2+ candidates are never resolved by guessing. Read-only fallback is
  the hook's alone — `vault_config.resolve_vault()`, which every mutating script
  goes through, stays strict.
- **The baseline file is the EXPECTED state.** Comparing it to itself proves
  nothing; it has to be compared against a fresh audit.
- Gates above baseline are investigated BEFORE phase 2; never hand off on a red
  hard gate.
- **Handoff PROSE about a pending draw can outlive the state it describes.**
  Check `session_plan_snapshots.json`. A pending draw belongs to the session that
  consumes it, and consuming it is phase 2's job, not this prompt's.
- **The session number is DERIVED, not remembered.** Two sittings on one day is
  the normal case, and the second one inherits nothing.
- **The FS write-back queue has no lane and no gate — only this list.** Nothing
  draws it, nothing fails when it grows, and it is exactly the kind of backlog
  that goes quiet. Report the count every session, even when it is unchanged.
- **`size_heartbeat.py`'s "BEFORE other work" does not outrank the away-policy.**
  The script is a heartbeat with no view of `deferred_decisions.md` and no idea
  whether the operator is at the keyboard; Operating_Protocol decides whether to
  ask or to queue.
- **The close prompt writes a rename suggestion; this prompt must READ it.** The
  two ends of the loop hand off through `Handoff.md`, and a suggestion nobody
  opens is wasted work. Reconcile rather than re-invent.
- ⚠ When listing `scripts/`, do not pipe through `head` — a truncated listing
  silently hides tools and reads as an absent one.

**Iterations**: 1 — **this prompt is a PHASE, not a loop**, and raising it is
meaningless: initializing a session twice establishes the same state twice. The
dial you want is `22-research-iterations` with `Iterations=N`, which this prompt
passes through as [ITERATIONS].

**Protocol**:

1. Settle the vault and the gate state: read the banner, or run
   `session_audit.sh` if the hook was skipped and report the skip. Compare
   against `.audit_baseline.txt`; triage anything above it. Write down the
   session-start values of the four lane metrics.
2. Read `Handoff.md` (Start here + the live close block) and the open items in
   `deferred_decisions.md`. Verify any announced pending draw against
   `session_plan_snapshots.json`.
3. Derive and state the session number.
4. Surface housekeeping DUE items, blocking deferred decisions and the FS
   write-back queue depth once: ask if the operator is present, queue if away.
5. Propose the rename command from the Handoff's stored suggestion, reconciled.
6. Report the six items and hand off to `22-research-iterations`.
