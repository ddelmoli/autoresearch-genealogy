---
name: session-loop
description: Run a research sitting end to end — the four phase prompts (session start, research iterations, session review, session close), the three lanes and how they are drawn, what counts as a hit or a miss, and the order in which outcomes must be recorded. Use when starting or closing a session, drawing a lane, recording an iteration outcome, or deciding what work a sitting should do.
---

# The session loop

Four phase prompts, in order. The loop is the phases, not an ad-hoc sitting.

| Phase | Prompt | What it does |
|---|---|---|
| 1 | `prompts/21-session-start.md` | Gate state vs baseline, vault confirmed, handoff read, operator items surfaced |
| 2 | `prompts/22-research-iterations.md` | **The only loop.** `Iterations: N` lane draws |
| 3 | `prompts/23-session-review.md` | Reconcile against the tools, re-measure every lane metric, assemble the write-back queue |
| 4 | `prompts/24-session-close.md` | File the sitting and set up the next draw |

The default unit of research work inside phase 2 is
`prompts/25-person-research-sweep.md`.

## The three lanes

**What each lane is FOR** (operator, 07 AUG 2026 — this is the definition; the pool a
builder happens to compute is an approximation of it):

| lane | purpose |
|---|---|
| **EXPAND** | Extend the tree. Review all **leaf nodes** on a regular basis — especially those with **0 or 1 parents**, or **0 spouses**. |
| **IMPROVE** | Review people who are **thinly sourced**, to see whether more can be gathered about them. |
| **ROTATE** | Re-visit **all** people periodically, to see whether new information has appeared. |

⭐⭐ **ROTATE IS THE EXPLOITATION ARM; EXPAND AND IMPROVE ARE THE EXPLORATION ARMS**
(operator, 07 AUG 2026). That is a statement about what the lanes ARE, not about how
they have scored. It matters because a bandit that maximises hit-rate will always
prefer the exploit arm: re-polling a known person is cheap and reliably "succeeds",
while extending and sourcing are slow and often fail. **Measured on this vault:
ROTATE 0.75, EXPAND 0.38, IMPROVE 0.06, and 8 of the last 12 draws went to ROTATE.**
A lane being cheap is not evidence that it is the valuable one. See
`deferred_decisions.md` for the open question about the mechanism.

`python3 scripts/session_plan.py` prints one ranked worklist across the three, and a
bandit picks the recommended one and prints the lane target.

⚠ **EXPAND's builder currently draws a NARROWER population than the definition above.**
It offers the SILENT frontier (0 parents, no declared reason). Measured 07 AUG 2026:
**563** entries have 0 parents, **108** have exactly one (`HALF_WIRED_PARENT`, 97
undeclared), and **535** have no spouse — and the last two are **drawn by nothing**.
⚠ Neither is a defect count: one parent is often correct, and many people never
married. They are candidate pools, and they need the same read-before-acting care.

`--lane VERIFY` is rejected; that lane was collapsed into IMPROVE.

## Two rules that are easy to get wrong

**The lane target is a floor, the same in every lane** — a percentage of the vault
counted in PEOPLE, on every draw. Cost per person and value of the person are not
inputs. If the floor is missed, report what blocked it rather than arguing the floor.

**Order: record, THEN plan.** `--record` clears the pending draw, so running
`session_plan.py` before the close is wiped by it. Use `session_close.py
--next-plan`, which runs the checklist in order so this cannot be got wrong.

```bash
python3 scripts/session_plan.py                              # the draw
python3 scripts/session_plan.py --record --lane <L> --outcome hit|miss
python3 scripts/session_close.py --log ... --summary ... --next-plan
```

**A hit is the lane target met, or the lane ran dry. Short of target is a MISS.** An
arm that never loses carries no signal.

**A miss is a result, not wasted effort, and never a reason to skip an iteration**
(operator, 07 AUG 2026). Run the requested number of iterations. Expecting to miss
is not grounds for not drawing; an expensive or thin lane is not grounds for stopping
early. **Prefer a worked miss to an unrun iteration** — one is an observation, the
other is nothing. The only forbidden thing is recording a cycle that was *not worked*;
that has never meant a cycle with a *small yield*.

## Recording work

- **Research_Log session index**: `python3 scripts/log_session.py`, never the Edit
  tool — the file is append-only and must never be read into context whole.
- **Anything needing further research** gets an `Open_Questions.md` entry *as well as*
  the narrative bullet. An entry states current state; the register is what is
  unresolved. Say what would settle it — a question with no named resolver is a
  complaint, not a research task.
- **A disposition is required to remove a row from a lane pool.** Prose alone is not
  a disposition.

## Related

- `audit-gates` skill — reading the phase-1 banner.
- `source-harvest` skill — the work phase 2 usually does.
- `person-entry` skill — writing what phase 2 finds.
