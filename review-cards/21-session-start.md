# Review Card: Session Start

Prompt: [21 Session Start](../prompts/21-session-start.md)

## Good Output

- The session's first substantive act is the banner read + `session_plan.py` run; the ranked worklist and drawn lane are shown BEFORE any research happens.
- A gate above baseline is triaged before new work, not worked around.
- The session works the plan's ranking top-down within one lane, using the owning prompt/workflow per work type.
- If the drawn lane was overridden, the override is stated up front and the actually-worked lane is what gets recorded at close.
- Commits land one logical unit at a time, gates green each time; the session log accrues as findings land.
- The rename line reflects the drawn lane and top target.

## Red Flags

- Research begins before the plan is run, or the plan's output is summarized without being shown.
- Multiple lanes worked shallowly in one session (the design is one lane, worked properly).
- A red hard gate "noted" and bypassed.
- The lane bandit's early draws second-guessed or tuned on tiny n ("EXPAND keeps winning, skip the floor").
- Living/unknown people touched by any web-facing step.
- Priorities re-argued from prose instead of taken from the plan (the exact failure the loop exists to end).
