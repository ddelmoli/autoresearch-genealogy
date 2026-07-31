# Review Card: Research Iterations

Prompt: [22 Research Iterations](../prompts/22-research-iterations.md)

Phase 2 of 4, and the only loop in a session. One iteration = draw a lane, work it to the lane target, record the outcome.

## Good Output

- Each iteration shows the plan's counts, the drawn lane with its reason, the LANE TARGET line and the top candidates BEFORE work starts.
- A pending draw is consumed as this iteration's lane rather than re-drawn.
- Work follows the plan's ranking top-down and dispatches to the owning prompt for the work type (18 for VERIFY edges, 19 for a harvest, 01 for expansion).
- Every iteration is recorded with `session_plan.py --record` before the next draw, for the lane actually WORKED, hit only when the lane target was met or the lane ran dry.
- New edges carry `?`; a `?` is stripped only after the entry was read, and FS-GAP / SCHOLARLY HEDGE / PRIVACY survivals are left with their reason recorded.
- Outward FS mutations are queued with their evidence, never performed.
- The profile-review slice runs once for the sitting, sized to what was actually polled.
- Commits land one logical unit at a time with gates green, and the session log accrues as findings land.

## Red Flags

- Every iteration recorded as a hit. Sixteen consecutive hits is what made the bandit meaningless in the first place; short of target is a miss.
- A recorded lane that differs from the lane worked, or an iteration recorded twice.
- The lane target read as rows skimmed rather than people moved (EXPAND that walks twenty rows and adds nobody).
- SILENT rising after EXPAND treated as a failure; it is the expected shape.
- A `?` stripped off the same FS panel that produced the edge, or stripped mechanically across a batch.
- Research_Log row or Handoff close block written here (those belong to phase 4).
- A rotation slice drawn far larger than what was polled, with the remainder unnamed.
- Living or unknown people web-searched; an FS write performed rather than queued.

## Verify Manually

- Count `history` rows added to `session_plan_snapshots.json` this sitting: one per iteration worked, no more.
- Re-run the owning heartbeat for each drawn lane and check the movement against the recorded hit/miss.
- Spot-check 2-3 worked rows against the plan's ranking: were they actually the top of the drawn lane?
- Read one cleared `?` edge end to end: was the child's own FS page used, and both parent identities checked?
- `git -C <vault> log --oneline` — one logical unit per commit, no `--no-verify`.

## Reject The Result When

- An iteration was worked and never recorded, or a record exists with no work behind it.
- A hit was recorded on work that fell short of the lane target without saying so.
- A `?` was stripped without reading the entry, or a documented scholarly hedge was deleted.
- Any FS write, merge or create was performed rather than queued for operator approval.
- A living or unknown person was touched by any web-facing step.

## Next Prompt

`23-session-review` — reconcile the sitting before anything is filed.
