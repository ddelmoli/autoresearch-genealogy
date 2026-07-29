# Session Start (the standing research-session opener)

The prompt that opens every routine research session on a vault running the
mechanized session loop (`scripts/session_plan.py` / `scripts/session_close.py`,
29 JUL 2026). It is a DISPATCHER, not a research campaign of its own: the plan
command merges the four lane worklists (EXPAND / IMPROVE / VERIFY / ROTATE),
draws the recommended lane with a bandit, and the session then works THAT lane
under the standing rules. Pair with `22-session-close.md` at the end.

Copy-paste prompt (fill the placeholders):

```text
Start a research session.

Environment: export AUTORESEARCH_VAULT="[VAULT_PATH]" applies to every toolkit
command — env vars do not persist between shell calls, so prefix each command:
AUTORESEARCH_VAULT="[VAULT_PATH]" python3 scripts/session_plan.py

1. Read the SessionStart banner. Gates must be at baseline (the vault's
   .audit_baseline.txt); investigate anything above baseline BEFORE new
   research work.
2. Run scripts/session_plan.py and show me the ranked worklist and the drawn
   lane before starting work.
3. Work the drawn lane per the vault's Operating_Protocol: check-before-
   searching per source (grep logs/ and Open_Questions first), log negatives,
   wire only source-backed relationships (new edges carry ?), never web-search
   living/unknown people.
4. Commit continuously — one logical unit per commit, gates green each time.
   Anything needing my decision goes in deferred_decisions.md; keep working.
5. End your first reply with the rename line, filling in the drawn lane and
   top target: Use "/rename <Day Mon DD HHh> <lane>: <top target>"
```

## Inputs To Replace

- **[VAULT_PATH]** — absolute path to the vault working tree (the private
  repo/directory holding `Family_Tree*.md`; e.g. `$(git rev-parse --show-toplevel)/vault-yourname`).

## Autoresearch Configuration

**Goal**: Open the session deterministically: verify the gate baseline, obtain
the ranked four-lane worklist from `session_plan.py`, and work the drawn lane so
that the lane's own metric moves — instead of re-arguing priorities from prose.

**Metric**: The drawn lane's metric, as dispatched: EXPAND = frontier SILENT
count; IMPROVE = keystone count (LOAD x THIN rows over threshold); VERIFY =
`?`-suffixed edge tokens; ROTATE = rotation slice hits recorded. The plan prints
all four counts; the session reports the drawn lane's before/after.

**Direction**: Minimize (EXPAND / IMPROVE / VERIFY) or maximize recorded hits
(ROTATE) — per the drawn lane.

**Verify**: `python3 scripts/session_plan.py` at start (counts + draw);
the same counts via the owning tool's heartbeat at close
(`extension_frontier.py --heartbeat`, `keystone_report.py --summary`,
`grep -rhoE "P-[0-9A-Z]{6}\?" [VAULT_PATH]/Family_Tree*.md | wc -l`,
`profile_review.py --heartbeat`).

**Guard**:
- Gates above baseline are investigated BEFORE new research; never start a lane
  on a red hard gate.
- The draw is a recommendation: overriding it is allowed, but the lane actually
  worked is the one recorded at close — never record the drawn lane if a
  different one was worked.
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

1. Read the SessionStart banner; compare against the vault's baseline file.
   Anything above baseline is triaged first.
2. Run `session_plan.py`; present the counts, the drawn lane, and the top
   candidates to the operator before starting.
3. Work the lane top-down (the plan's ranking is the priority order), applying
   the owning prompt/workflow for the work type (e.g. prompt 18 for VERIFY
   edges, prompt 19 for a ROTATE/harvest target, the frontier declaration
   pattern for EXPAND rows that terminate).
4. Checkpoint: commit each logical unit; update the session log as findings
   land (narrative lives in `logs/`, not the Handoff).
5. When the lane is exhausted or the session nears its end, switch to the
   close prompt (`22-session-close.md`).
