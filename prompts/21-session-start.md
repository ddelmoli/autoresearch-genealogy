# Session Start (the standing research-session opener)

The prompt that opens every routine research session on a vault running the
mechanized session loop (`scripts/session_plan.py` / `scripts/session_close.py`,
29 JUL 2026). It is a DISPATCHER, not a research campaign of its own: the plan
command merges the four lane worklists (EXPAND / IMPROVE / VERIFY / ROTATE),
draws the recommended lane with a bandit, and the session then works THAT lane
under the standing rules. Pair with `22-session-close.md` at the end.

**Revised after a session that opened with no banner at all.** The earlier
version said "Read the SessionStart banner" as though the banner is always
there. It is not: the hook needs `AUTORESEARCH_VAULT` set **in the shell that
launches the agent**, and when it is missing the hook reports
`VAULT AUDIT SUITE: skipped — no AUTORESEARCH_VAULT set` and the session opens
with **no gate values, no census, no frontier count and no heartbeats**. The
prompt's own Environment note made that harder to notice, because "prefix each
command" is the right advice for commands and cannot help a hook that already
ran. Step 1 now detects the skip and names the fallback. Three further gaps are
closed below: the baseline file is not a substitute for current values (step 1),
a pending lane draw may already be waiting from the last close (step 2), and the
profile-review slice is due EVERY session regardless of the lane drawn (step 3).

Copy-paste prompt (fill the placeholders):

```text
Start a research session.

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
   - ! If it says "VAULT AUDIT SUITE: skipped — no AUTORESEARCH_VAULT set", you
     have NO current numbers. Run the suite yourself before any research:
     AUTORESEARCH_VAULT="[VAULT_PATH]" bash scripts/session_audit.sh
     Tell me the hook was skipped, so I can fix my launch shell.
   - Then COMPARE current values against the vault's .audit_baseline.txt. The
     baseline file is the EXPECTED state, not the current one; reading it alone
     tells you nothing about today. Investigate anything above baseline BEFORE
     new research work, and never start a lane on a red HARD gate.
   - If the audit reports HOUSEKEEPING actions DUE, check deferred_decisions.md
     first: if the item is already queued there, say so and move on; if not,
     present the choices to me before other work.

2. GET THE LANE. Run scripts/session_plan.py and show me the ranked worklist and
   the drawn lane before starting work.
   - ! First check whether a draw is already PENDING from the previous close
     (the vault's session_plan_snapshots.json, `pending`). If one is, THAT is
     this session's lane — a re-run does not mint a fresh draw, and the lane
     there is not an unrecorded outcome from the last session.

3. WORK THE DRAWN LANE per the vault's Operating_Protocol: check-before-
   searching per source (grep logs/ and Open_Questions first), log negatives,
   wire only source-backed relationships (new edges carry ?), never web-search
   living/unknown people.
   - ! AND RUN THE PROFILE-REVIEW SLICE REGARDLESS OF WHICH LANE WAS DRAWN. It
     is due EVERY session, not only when ROTATE is drawn; a skipped session is
     coverage permanently deferred, not deferred-and-caught-up. Draw it, poll
     it, and record each entry with --record.

4. Commit continuously — one logical unit per commit, gates green each time.
   Anything needing my decision goes in deferred_decisions.md; keep working.

5. End your first reply with the rename line, filling in the drawn lane and top
   target: Use "/rename <Day Mon DD HHh> <lane>: <top target>"
   (If the hook injected its own rename reminder, this is the same slot: use
   the lane-and-target form.)
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (the private
  repo/directory holding `Family_Tree*.md`; e.g. `$(git rev-parse --show-toplevel)/vault-yourname`).

## Autoresearch Configuration

**Goal**: Open the session deterministically: establish the CURRENT gate state
(from the banner, or from `session_audit.sh` when the hook was skipped), verify
it against the baseline, obtain the ranked four-lane worklist from
`session_plan.py`, and work the drawn lane so that the lane's own metric moves —
instead of re-arguing priorities from prose.

**Metric**: The drawn lane's metric, as dispatched: EXPAND = frontier SILENT
count; IMPROVE = keystone count (LOAD x THIN rows over threshold); VERIFY =
`?`-suffixed edge tokens; ROTATE = rotation slice hits recorded. The plan prints
all four counts; the session reports the drawn lane's before/after. A session
that opened with no current numbers has no before, and so cannot report movement
— which is why step 1 is a precondition, not a formality.

**Direction**: Minimize (EXPAND / IMPROVE / VERIFY) or maximize recorded hits
(ROTATE) — per the drawn lane.

**Verify**: the SessionStart banner, or `bash scripts/session_audit.sh` when it
was skipped; `python3 scripts/session_plan.py` at start (counts + draw); the same
counts via the owning tool's heartbeat at close
(`extension_frontier.py --heartbeat`, `keystone_report.py --summary`,
`grep -rhoE "P-[0-9A-Z]{6}\?" [VAULT_PATH]/Family_Tree*.md | wc -l`,
`profile_review.py --heartbeat`).

**Guard**:
- **A missing banner is a silent failure, not an empty one.** The hook skipping
  looks like an ordinary quiet start; there is no error to notice. Confirm you
  have current gate values before touching research, and say so when you had to
  generate them yourself.
- **The baseline file is the EXPECTED state.** Comparing it to itself proves
  nothing; it has to be compared against a fresh audit.
- Gates above baseline are investigated BEFORE new research; never start a lane
  on a red hard gate.
- **A pending draw belongs to the session that consumes it.** If the previous
  close left one, that is your lane; do not read it as an unrecorded outcome and
  do not record it on the previous session's behalf.
- **The profile-review slice is due every session, independent of the lane.**
  Partial is fine and must be stated; silent omission is not.
- The draw is a recommendation: overriding it is allowed, but the lane actually
  worked is the one recorded at close — never record the drawn lane if a
  different one was worked.
- **A null is a statement about the search, not about the record.** Before
  writing any negative, name what was searched and what that search
  structurally cannot contain: one spelling, one field value, one repository.
  Calibrating a zero proves the index holds the population; it does NOT prove
  your filter values were right.
- All standing Operating_Protocol guards apply: check-before-searching per
  source; negatives logged; source-backed edges only, `?` on unverified;
  living/unknown people never web-searched; CREATE/outward mutations
  operator-gated; Research_Log appended via `scripts/log_session.py`, never the
  Edit tool.
- One logical unit per commit; the pre-commit gates pass every time; no
  `--no-verify`.

**Iterations**: 1 (one draw per session; the loop across sessions is the
bandit's).

**Protocol**:

1. Establish current gate state: read the banner, or run `session_audit.sh` if
   the hook was skipped, and report the skip. Compare against the vault's
   baseline file; triage anything above it first. Check housekeeping DUE items
   against `deferred_decisions.md` before presenting them.
2. Check for a pending draw; otherwise run `session_plan.py`. Present the
   counts, the drawn lane, and the top candidates to the operator before
   starting.
3. Work the lane top-down (the plan's ranking is the priority order), applying
   the owning prompt/workflow for the work type (e.g. prompt 18 for VERIFY
   edges, prompt 19 for a ROTATE/harvest target, the frontier declaration
   pattern for EXPAND rows that terminate). Run the profile-review slice this
   session whatever the lane.
4. Checkpoint: commit each logical unit; update the session log as findings
   land (narrative lives in `logs/`, not the Handoff).
5. When the lane is exhausted or the session nears its end, switch to the
   close prompt (`22-session-close.md`).
