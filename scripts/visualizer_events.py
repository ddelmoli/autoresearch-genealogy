#!/usr/bin/env python3
"""visualizer_events.py -- the event stream behind the session visualizer.

WHY THIS EXISTS. A research sitting is legible to the operator, who reads the
transcript, and to nobody else in the room. For a sitting someone is WATCHING,
the interesting part is not the raw tool calls but the decisions: which person
was drawn, which records were counted, which were thrown out and why. This module
writes those moments to one append-only JSON Lines file that
`scripts/visualizer.py` streams to a browser page.

TWO WRITERS, ONE FILE.
  * The Claude Code hooks (PostToolUse, UserPromptSubmit, Stop) call
    `python3 scripts/visualizer_events.py --hook`. That records WHAT ran.
  * `scripts/narrate.py` records WHY: plain-English narration, the phase and
    lane, the person being worked, and each evidence verdict.

OFF UNLESS THE VISUALIZER IS RUNNING. The hook is a no-op unless the ACTIVE flag file
exists (`narrate.py start` creates it, `narrate.py stop` removes it), so the
hooks can stay wired permanently at no cost to ordinary sittings.

PRIVACY. Events carry vault text (edit diffs, command output), so the stream
lives under `.claude/visualizer/`, which the framework `.gitignore` already excludes,
and the viewer binds to 127.0.0.1 only. Never publish the page or the file.

The hook ALWAYS exits 0: a viewer must never be able to block or fail a tool call.
"""
import datetime as _dt
import difflib
import json
import os
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
VIS_DIR = pathlib.Path(os.environ.get("AUTORESEARCH_VISUALIZER_DIR", REPO / ".claude" / "visualizer"))
EVENTS = VIS_DIR / "events.jsonl"
ACTIVE = VIS_DIR / "ACTIVE"

MAX_TEXT = 4000      # per text field
MAX_OUTPUT_LINES = 40

# Bash scripts the framework runs, mapped to a label a watcher can read.
SCRIPT_LABELS = [
    ("session_plan.py", "Session plan"),
    ("session_close.py", "Session close"),
    ("session_audit.sh", "Vault audit"),
    ("gen_person_index.py", "Integrity check"),
    ("prose_audit.py", "Prose check"),
    ("header_audit.py", "Header check"),
    ("build_edges.py", "Family links"),
    ("harvest_sources.py", "Source harvest"),
    ("question_drain.py", "Open questions"),
    ("question_store.py", "Open questions"),
    ("bio_slice.py", "Biography"),
    ("bio_completeness.py", "Biography"),
    ("log_session.py", "Research log"),
    ("log_backlinks.py", "Research log"),
    ("route_digest.py", "Routes tried"),
    ("mint_ids.py", "New person id"),
    ("census", "Source census"),
    ("privacy", "Privacy check"),
    ("git commit", "Save (commit)"),
    ("git ", "Version control"),
]


def now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def is_active():
    return ACTIVE.exists()


def clip(text, limit=MAX_TEXT):
    if text is None:
        return ""
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + f"\n... ({len(text) - limit} more characters)"


def rel(path):
    """Show a path relative to the repo, so the screen is not all /Users/..."""
    if not path:
        return ""
    try:
        return str(pathlib.Path(path).resolve().relative_to(REPO))
    except (ValueError, OSError):
        return str(path)


def append(event):
    """Append one event. Safe to call whether or not the visualizer is active."""
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    event.setdefault("ts", now())
    with open(EVENTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _output_head(resp):
    if isinstance(resp, dict):
        out = resp.get("stdout") or resp.get("output") or ""
        err = resp.get("stderr") or ""
        text = out + (("\n[stderr]\n" + err) if err.strip() else "")
    else:
        text = clip(resp, MAX_TEXT * 2)
    lines = text.splitlines()
    head = "\n".join(lines[:MAX_OUTPUT_LINES])
    if len(lines) > MAX_OUTPUT_LINES:
        head += f"\n... ({len(lines) - MAX_OUTPUT_LINES} more lines)"
    return clip(head)


def _failed(resp):
    if isinstance(resp, dict):
        if resp.get("interrupted") or resp.get("is_error"):
            return True
        code = resp.get("exit_code", resp.get("returncode"))
        return isinstance(code, int) and code != 0
    return False


def _in_vault(path):
    """True for a file inside a vault (the live one, or any vault*/ sibling)."""
    vault = os.environ.get("AUTORESEARCH_VAULT")
    if vault and str(path).startswith(str(pathlib.Path(vault).resolve())):
        return True
    first = rel(path).split("/", 1)[0]
    return first.startswith("vault") and first != "vault-template"


def _bash_label(cmd):
    for needle, label in SCRIPT_LABELS:
        if needle in cmd:
            return label
    return "Command"


def _host(url):
    m = re.match(r"^(?:[a-z]+://)?([^/]+)", url or "")
    return m.group(1) if m else ""


PERSON_ID_RE = re.compile(r"\bid: (P-[0-9A-HJKMNP-TV-Z]{6})\b")


def tool_event(payload):
    """Translate one PostToolUse payload into a viewer event, or None to skip."""
    name = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    resp = payload.get("tool_response")
    ev = {"type": "tool", "tool": name, "failed": _failed(resp)}

    if name == "Bash":
        cmd = inp.get("command", "")
        if "narrate.py" in cmd:          # narration already reported itself
            return None
        ev.update(category="command", label=_bash_label(cmd),
                  title=inp.get("description") or cmd.splitlines()[0][:120],
                  detail=clip(cmd, 600), output=_output_head(resp))
    elif name in ("Edit", "MultiEdit"):
        path = inp.get("file_path", "")
        edits = inp.get("edits") or [{"old_string": inp.get("old_string", ""),
                                       "new_string": inp.get("new_string", "")}]
        diff = []
        for e in edits:
            diff.extend(difflib.unified_diff(
                (e.get("old_string") or "").splitlines(),
                (e.get("new_string") or "").splitlines(), lineterm="", n=2))
        diff = [d for d in diff if not d.startswith(("---", "+++"))]
        ids = sorted(set(PERSON_ID_RE.findall("\n".join(e.get("new_string") or "" for e in edits))))
        ev.update(category="vault-edit" if _in_vault(path) else "edit",
                  label="Edit", title=f"Edited {pathlib.Path(path).name}",
                  file=rel(path), diff=clip("\n".join(diff), MAX_TEXT * 2), person_ids=ids)
    elif name == "Write":
        path = inp.get("file_path", "")
        n = len((inp.get("content") or "").splitlines())
        ev.update(category="edit", label="Write",
                  title=f"Wrote {pathlib.Path(path).name} ({n} lines)", file=rel(path))
    elif name == "Read":
        path = inp.get("file_path", "")
        ev.update(category="read", label="Read", title=f"Read {pathlib.Path(path).name}",
                  file=rel(path))
    elif name in ("Grep", "Glob"):
        ev.update(category="read", label="Search files",
                  title=f"Searched files for {inp.get('pattern', '')!r}",
                  detail=clip(inp.get("path", ""), 300))
    elif "navigate" in name or name.endswith("preview_start"):
        url = inp.get("url", "")
        ev.update(category="web", label="Browser",
                  title=f"Opened {_host(url) or url or inp.get('name') or 'a browser tab'}",
                  detail=clip(url, 600))
    elif "get_page_text" in name or "read_page" in name:
        ev.update(category="web", label="Browser", title="Read the page",
                  output=_output_head(resp))
    elif "find" in name and ("Browser" in name or "chrome" in name):
        ev.update(category="web", label="Browser",
                  title=f"Looked on the page for {inp.get('query', '')!r}")
    elif "javascript" in name:
        ev.update(category="web", label="Browser", title="Read data from the page",
                  detail=clip(inp.get("text", ""), 600), output=_output_head(resp))
    elif "browser_batch" in name:
        steps = []
        for item in inp.get("actions") or []:
            i = item.get("input") or {}
            if i.get("url"):
                steps.append(f"open {_host(i['url'])}")
            elif i.get("action_summary"):
                steps.append(i["action_summary"])
            elif i.get("action") not in (None, "wait", "screenshot"):
                steps.append(str(i.get("action")))
            elif "get_page_text" in item.get("name", "") or "read_page" in item.get("name", ""):
                steps.append("read the page")
        ev.update(category="web", label="Browser",
                  title=("; ".join(steps) or "Looked at the page")[:200])
    elif name.endswith("__computer"):
        summary = inp.get("action_summary") or inp.get("action") or "Browser actions"
        ev.update(category="web", label="Browser", title=str(summary)[:160])
    elif name in ("WebSearch",):
        ev.update(category="web", label="Web search",
                  title=f"Searched the web for {inp.get('query', '')!r}")
    elif name in ("WebFetch",):
        ev.update(category="web", label="Web", title=f"Fetched {_host(inp.get('url', ''))}")
    elif name.startswith("mcp__ccd_") or name in ("ToolSearch",):
        return None                      # app plumbing, not research
    else:
        ev.update(category="other", label=name.split("__")[-1], title=name.split("__")[-1],
                  detail=clip(inp, 600))
    return ev


def hook_main():
    try:
        if not is_active():
            return
        payload = json.load(sys.stdin)
        kind = payload.get("hook_event_name", "")
        if kind == "PostToolUse":
            ev = tool_event(payload)
        elif kind == "UserPromptSubmit":
            ev = {"type": "prompt", "text": clip(payload.get("prompt", ""), 1500)}
        elif kind == "Stop":
            ev = {"type": "turn_end"}
        else:
            ev = None
        if ev:
            append(ev)
    except Exception as exc:  # never fail a tool call because of the viewer
        try:
            append({"type": "error", "text": f"visualizer hook: {exc!r}"})
        except Exception:
            pass


if __name__ == "__main__":
    if "--hook" in sys.argv:
        hook_main()
    sys.exit(0)
