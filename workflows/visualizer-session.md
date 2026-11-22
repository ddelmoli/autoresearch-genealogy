---
type: workflow
created: 2026-11-22
tags: [workflow, session, visualizer]
---

# Session visualizer: a research sitting someone can watch

A normal sitting is readable by the operator and nobody else. This workflow runs
the same sitting (prompts 21 to 24, nothing skipped) with a live page beside it
that shows, in plain English, what is being done and why: the phase and lane,
the person drawn, every record looked at with its verdict, every empty search,
and each change written to the tree.

## The parts

| Part | Role |
|---|---|
| `scripts/visualizer_events.py --hook` | Claude Code hook (PostToolUse, UserPromptSubmit, Stop). Records WHAT ran. A no-op unless the visualizer is active. |
| `scripts/narrate.py` | Records WHY: narration, phase, person, evidence verdicts, negatives, findings. |
| `scripts/visualizer.py` | Serves the page on `127.0.0.1` and streams the events live. |
| `.claude/visualizer/events.jsonl` | The stream. Gitignored. Holds vault text, so it is private. |

## One-time setup

Add the hook to `.claude/settings.json` (local, not tracked) beside the existing ones:

```json
"PostToolUse":      [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR:-.}/scripts/visualizer_events.py\" --hook", "timeout": 5}]}],
"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR:-.}/scripts/visualizer_events.py\" --hook", "timeout": 5}]}],
"Stop":             [{"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR:-.}/scripts/visualizer_events.py\" --hook", "timeout": 5}]}]
```

The hook does nothing while the visualizer is off, so it can stay wired.

## Running a visualized sitting

1. Start the viewer and open the page (on a second screen or a TV):

   ```bash
   python3 scripts/visualizer.py
   ```

   Then open `http://127.0.0.1:8765/`. Each person card names whose ancestor the
   person is, walked from the vault's parent edges (never from the generation
   number: in a couple-anchored vault most people are on only one line). To add a
   line for a watcher who is an anchor's parent, pass their vault id:
   `?viewer=P-XXXXXX&viewer_label=Dad`; the line appears only for people on that watcher's line.

2. Start the session in Claude Code with a prompt along these lines:

   > Visualizer on: follow workflows/visualizer-session.md. Run `python3 scripts/narrate.py start --title "..."`, then a standard sitting.

3. At the end, `python3 scripts/narrate.py stop`. Starting a new sitting archives
   the old stream beside it as `events-<timestamp>.jsonl`.

## Narration protocol (instructions for Claude while the visualizer is on)

The hooks already show every tool call. Narration is for the reasoning a
watcher cannot see. Write for an experienced family historian who does not know
this vault's tooling: plain words, no script names, no internal jargon (say
"a record naming her" rather than "limb (g)").

- **Every phase and lane draw**: `narrate.py phase "Research iterations" --lane EXPAND --detail "why this lane"`.
- **Every person drawn**: `narrate.py person "<name>" --id P-XXXXXX --gen N --born ... --died ... --place ... --why "<why this person now>"`.
- **Before a search**: one `say` line naming what is about to be searched and what it would show.
- **Every record judged**: `narrate.py evidence "<record, in words>" --verdict counted|excluded|candidate --why "<the reason>"`. This is the heart of the visualizer. Say the reason the method gives (a user tree is not evidence; an image-less memorial page is a contributor's assertion; a sibling's baptism does not name her; a hint is a candidate until its identifiers match).
- **Every empty search**: `narrate.py negative "<what was searched, which years>"`. A negative is data; show it.
- **Every conclusion**: `narrate.py finding "<claim>" --tier strong|moderate|speculative`.
- **A term the watcher will not know**: `narrate.py term "<term>" "<one-line meaning>"`, once.

Pace: narrate before acting, not after a long run of tool calls, so the page
leads the work instead of trailing it.

## Privacy

The page and the stream carry vault content, including living people. The
server binds to `127.0.0.1` only. Never publish the page, never commit the stream,
and keep the normal rules: no web research on living or unknown people.
