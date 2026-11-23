#!/usr/bin/env python3
"""visualizer_events.py -- the event stream behind the session visualizer.

WHY THIS EXISTS. A research sitting is legible to the operator, who reads the
transcript, and to nobody else in the room. For a sitting someone is WATCHING,
the interesting part is not the raw tool calls but the decisions: which person
was drawn, which records were counted, which were thrown out and why. This module
writes those moments to one append-only JSON Lines file that
`scripts/visualizer.py` streams to a browser page.

TWO WRITERS, ONE FILE.
  * The Claude Code hooks (PreToolUse, PostToolUse, UserPromptSubmit, Stop) call
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


# --- Which session owns the stream ------------------------------------------
# The hooks fire for EVERY Claude Code session in this repo. Without an owner, a
# second session (the operator asking a side question) wrote its prompts and edits
# into the watched page. The ACTIVE file is "title" then an optional
# "session: <id>" line; the session that ran `narrate.py start` claims it, through
# the PostToolUse event of that very Bash call, and every other session is ignored.

def owner():
    try:
        for line in ACTIVE.read_text(encoding="utf-8").splitlines()[1:]:
            if line.startswith("session: "):
                return line[len("session: "):].strip()
    except OSError:
        pass
    return None


def claim(session_id):
    try:
        title = ACTIVE.read_text(encoding="utf-8").splitlines()[:1]
        ACTIVE.write_text("\n".join(title + [f"session: {session_id}"]) + "\n", encoding="utf-8")
    except OSError:
        pass


# --- Open questions ----------------------------------------------------------
QSHOW_RE = re.compile(r"question_store\.py\b[^|;&\n]*--show\s+(Q?\d+[a-z]?)")
MD_NOISE = re.compile(r"[⭐⛔⚠⏭️✅❌]")


def _plain(md):
    """Markdown to the plain sentence a watcher reads."""
    t = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), md)
    t = MD_NOISE.sub("", t).replace("**", "").replace("`", "")
    t = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def question_context(label):
    """Title, provenance, gist and settle-condition of one question, read through
    question_store (the register's one reader). None if it cannot be read."""
    try:
        import question_store as qs
        import vault_config as vc
        vault = vc.resolve_vault(None)
        num, suffix = qs.parse_qlabel(label)
        rows = qs.find_all(vault, num, suffix)
        if not rows:
            return None
        live = [r for r in rows if qs.QB.is_live(r[3])]
        path, s, e, _h = (live or rows)[0]
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")[s:e]
    except Exception:
        return None
    heading = re.sub(r"^#+\s*\d+[a-z]?\.\s*", "", lines[0]) if lines else ""
    raised = re.search(r"\(raised ([^)]*)\)", heading)
    title = _plain(re.sub(r"\s*\(raised [^)]*\)", "", heading))
    status = ""
    head, sep, tail = title.rpartition(" \u2014 ")
    if sep and re.match(r"(RESOLVED|RULED OUT|CLOSED|CONFIRMED FAIL|FULLY RESOLVED)\b", tail):
        title, status = head, tail
    paras, cur = [], []
    for ln in lines[1:]:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            paras.append(" ".join(cur)); cur = []
    if cur:
        paras.append(" ".join(cur))
    settle_raw = next((p for p in paras if re.search(r"would settle|to settle|settles it", p, re.I)), "")
    settle = re.sub(r"^.*?(?:would settle it|to settle it|settles it)\s*[:.]?\s*", "",
                    _plain(settle_raw), flags=re.I) if settle_raw else ""
    gist = next((_plain(p) for p in paras
                 if not p.startswith(("#", "|", "-")) and p is not settle_raw), "")
    # The people the question is ABOUT, by vault id: the page keeps a question that
    # was only read along the way while the work stays on one of them, and clears
    # it when the work turns to anyone else. (Operator, 23 NOV 2026: a question read
    # for one row stayed up when the next row was a different person, because the
    # page had taken "the first person after the read" to be its subject.)
    people = sorted(set(re.findall(r"\bP-[0-9A-HJKMNP-TV-Z]{6}\b", "\n".join(lines))))
    return {"label": f"Q{num}{suffix}", "title": title, "status": status,
            "raised": _plain(raised.group(1)) if raised else "",
            "file": pathlib.Path(path).stem, "live": bool(live),
            "gist": clip(gist, 500), "settle": clip(settle, 500), "people": people}


# --- Who the next piece of work is about ---------------------------------------
# WHY BEFORE, NOT AFTER. The cards on the right used to change only when the
# session narrated a record it had already read, so the watcher saw the work
# happen under the previous person's name and the card catch up afterwards. The
# PreToolUse hook now looks at what a tool is ABOUT to touch: when its input names
# exactly one person (a vault id, or an FS PID the vault holds), the card switches
# before the tool runs. Two or more people in one call (a roster grep, an audit)
# say nothing about who is being worked, so they switch nothing.
VAULT_ID_RE = re.compile(r"\bP-[0-9A-HJKMNP-TV-Z]{6}\b")
FS_PID_RE = re.compile(r"(?<![:\w-])[0-9A-Z]{4}-[0-9A-Z]{3}(?![\w-])")
SUBJECT = VIS_DIR / "subject"          # last person put on the card, so repeats are quiet


def _input_text(inp):
    if isinstance(inp, dict):
        return "\n".join(_input_text(v) for v in inp.values())
    if isinstance(inp, list):
        return "\n".join(_input_text(v) for v in inp)
    return inp if isinstance(inp, str) else ""


def subject_of(text):
    """The one vault id a tool input is about, or None."""
    ids = set(VAULT_ID_RE.findall(text))
    pids = set(FS_PID_RE.findall(text))
    if pids:
        try:
            import person_store as ps
            import vault_config as vc
            for r in ps.iter_people(vc.resolve_vault(None)):
                fs = str((r.external_ids or {}).get("fs") or "")
                if fs in pids:
                    ids.add(r.id)
        except Exception:
            pass
    return ids.pop() if len(ids) == 1 else None


def pre_events(payload):
    """Events to show BEFORE a tool runs: the question it opens, the person it is about."""
    name = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    cmd = inp.get("command", "") if name == "Bash" else ""
    if "narrate.py" in cmd or name.startswith("mcp__ccd_") or name == "ToolSearch":
        return []
    m = QSHOW_RE.search(cmd)
    if m:
        q = question_context(m.group(1))
        if q:
            _remember(None)          # a new question starts with nobody on the card
            return [{"type": "question", "auto": True, **q}]
        return []
    pid = subject_of(_input_text(inp))
    if not pid or pid == _remember():
        return []
    import narrate                   # lazy: narrate imports this module
    ev = narrate.person_event(pid=pid)
    if not ev.get("name") or (ev["name"] == pid and ev.get("kin") is None):
        return []                    # not a person the vault holds
    _remember(pid)
    ev["auto"] = True
    return [{k: v for k, v in ev.items() if v not in (None, "")}]


def _remember(pid=...):
    """Read (no argument) or set the id last shown on the person card."""
    if pid is ...:
        try:
            return SUBJECT.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None
    try:
        SUBJECT.write_text(pid or "", encoding="utf-8")
    except OSError:
        pass
    return pid


# --- Prompts that are not the operator -----------------------------------------
# The harness delivers some of its own messages through the prompt channel: a
# background command finishing arrives as a <task-notification>, and other
# sessions and CI report the same way. Shown raw they read as the operator typing
# XML. A finished background command is real work, so it becomes a tool line; the
# other harness messages are plumbing and are dropped.
TAG_RE = re.compile(r"^\s*<([a-z][a-z0-9-]*)[\s>]")


def _tag(text, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", text, re.S)
    return m.group(1).strip() if m else ""


def prompt_event(text):
    m = TAG_RE.match(text or "")
    if not m:
        return {"type": "prompt", "text": clip(text, 1500)}
    if m.group(1) != "task-notification":
        return None
    summary = _tag(text, "summary")
    status = _tag(text, "status")
    desc = re.search(r'"([^"]+)"', summary)
    result = re.search(r"\(([^()]*)\)\s*$", summary)
    title = (desc.group(1) if desc else summary or "Background command") + " (finished in the background"
    plain = re.sub(r"^exit code \d+:\s*", "", result.group(1)).strip().lower() if result else ""
    title += f": {plain})" if plain else ")"
    output = ""
    out_file = _tag(text, "output-file")
    if out_file:
        try:
            output = _output_head({"stdout": pathlib.Path(out_file).read_text(encoding="utf-8", errors="replace")})
        except OSError:
            pass
    # grep's exit 1 means "no matches", an answer rather than a failure; only a
    # command that did not complete is shown as failed.
    return {"type": "tool", "tool": "Background", "category": "command", "label": "Background",
            "title": title, "output": output, "failed": status not in ("completed", "")}



# --- Claude's chat text, carried onto the page -------------------------------
# The running commentary Claude writes to the operator between tool calls is the
# best plain-English account of what is happening, and it never passed through
# narrate.py, so the page missed it (operator, 23 NOV 2026). The hooks receive the
# session transcript path; before each tool runs and at the end of each turn, any
# assistant text written since the sitting started and not yet shown becomes a
# "say" event. SAID keeps the ids already shown.
SAID = VIS_DIR / "said"
TAIL_BYTES = 3_000_000          # screenshots sit in the transcript as base64, so text can be far back


def _since_start():
    try:
        return _dt.datetime.fromtimestamp(ACTIVE.stat().st_mtime, _dt.timezone.utc)
    except OSError:
        return None


def chat_events(payload):
    path = payload.get("transcript_path")
    start = _since_start()
    if not path or start is None:
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            raw = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    try:
        seen = set(SAID.read_text(encoding="utf-8").split())
    except OSError:
        seen = set()
    out, new_ids = [], []
    for line in raw.splitlines():
        if '"assistant"' not in line or '"text"' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue                      # the first line of the tail may be cut
        if e.get("type") != "assistant" or e.get("isSidechain"):
            continue
        uid = e.get("uuid")
        if not uid or uid in seen:
            continue
        try:
            ts = _dt.datetime.fromisoformat(str(e.get("timestamp", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts < start:
            continue
        text = " ".join(c.get("text", "") for c in (e.get("message") or {}).get("content") or []
                        if isinstance(c, dict) and c.get("type") == "text").strip()
        if not text:
            continue
        new_ids.append(uid)
        out.append({"type": "say", "text": clip(_plain(text), 1500), "source": "chat"})
    if new_ids:
        try:
            keep = (list(seen) + new_ids)[-500:]
            SAID.write_text("\n".join(keep) + "\n", encoding="utf-8")
        except OSError:
            pass
    return out


def hook_main():
    try:
        if not is_active():
            return
        payload = json.load(sys.stdin)
        kind = payload.get("hook_event_name", "")
        sid = payload.get("session_id")
        cmd = (payload.get("tool_input") or {}).get("command", "") if kind == "PostToolUse" else ""
        if owner() is None and sid and "narrate.py start" in cmd:
            claim(sid)
        own = owner()
        if own and sid and sid != own:
            return
        if kind in ("PreToolUse", "Stop"):
            for e in chat_events(payload):
                append(e)
        if kind == "PreToolUse":
            for e in pre_events(payload):
                append(e)
            return
        if kind == "PostToolUse":
            ev = tool_event(payload)
        elif kind == "UserPromptSubmit":
            ev = prompt_event(payload.get("prompt", ""))
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
