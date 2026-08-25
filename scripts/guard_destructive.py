#!/usr/bin/env python3
"""guard_destructive.py -- PreToolUse guard: refuse the writes that cannot be undone.

WHY THIS EXISTS. Two method rules were enforced by prose alone, and prose does not
survive iteration nine of an unattended sitting. The first is that the append-only
stores are written through their own scripts and NEVER through Edit; the second is
that investigating is not a licence to destroy the evidence. Both are mechanical
claims about a command or a path, so both can be checked rather than requested.

WHAT IT REFUSES.
  Bash   git reset --hard / clean -f / checkout -- / restore, in either repo;
         in-place stream edits (sed -i, perl -i) and truncating redirects onto
         vault Markdown; rm of vault Markdown.
  Edit   Research_Log.md and Open_Questions*.md, which have stores of their own
  Write  (log_session.py, question_store.py) that mint numbers and place blocks.

WHAT IT DOES NOT. It does not judge research. A wrong claim about a person is
caught by the gates and the operator; only irreversibility is caught here.

Bash matching is per shell segment, against the segment's argv rather than the raw
string, so a script name quoted inside a commit message or a grep pattern is not
mistaken for an invocation of it.

Exit 2 blocks the call and shows stderr to Claude. Exit 0 allows.
"""
import json
import os
import re
import shlex
import sys

# (leading argv tokens, why it is refused). A rule matches when the tokens appear in
# order in the segment's argv, the first at the command position.
DESTRUCTIVE_ARGV = [
    (["git", "reset", "--hard"], "discards uncommitted work in the tree"),
    (["git", "clean"],           "deletes untracked files, including anything not yet added"),
    (["git", "checkout", "--"],  "overwrites uncommitted changes in the named paths"),
    (["git", "restore"],         "overwrites uncommitted changes in the named paths"),
]

# Wrappers that stand in front of the real command without changing what it does.
PASSTHROUGH = {"sudo", "env", "time", "nohup", "command", "exec", "uv"}

# Vault Markdown, by name rather than by path: the vault dir is per-install, and a
# relative argument is common. These stems are the corpus.
VAULT_MD = re.compile(
    r"\b(Family_Tree|Open_Questions|Research_Log|Handoff|Unresolved_Persons|"
    r"Timeline|Witness_Network|Data_Inventory|Research_Strategy)\w*\.md\b"
)

# Written through their own store, never by hand. Archives are excluded: the archiver
# writes them, and it is not the Edit tool.
# (pattern, why it is not hand-written, the supported route). Archives and the
# Resolved file are excluded: the archiver writes those, and it is not the Edit tool.
STORE_OWNED = [
    (re.compile(r"(^|/)Open_Questions_Index\.md$"),
     "is GENERATED, so a hand edit survives only until the next regeneration",
     "python3 scripts/gen_question_index.py --write <path>"),
    (re.compile(r"(^|/)Research_Log\.md$"),
     "is append-only and has a store of its own",
     "python3 scripts/log_session.py --log \"logs/YYYY-MM-DD-slug\" --summary \"...\""),
    (re.compile(r"(^|/)Open_Questions(_(?!Archive|Resolved|Index)\w+)?\.md$"),
     "has a store of its own; a hand edit mints no number and can land a block in "
     "the wrong place",
     "python3 scripts/question_store.py --new|--append|--resolve"),
]


def segments(command):
    """Split on shell separators, yielding the argv of each segment."""
    for raw in re.split(r"(?:\|\||&&|[;|&\n])", command):
        raw = raw.strip()
        if not raw:
            continue
        try:
            argv = shlex.split(raw)
        except ValueError:                      # unbalanced quotes: fall back
            argv = raw.split()
        while argv and re.match(r"^\w+=", argv[0]):
            argv = argv[1:]
        while argv and os.path.basename(argv[0]) in PASSTHROUGH:
            argv = argv[1:]
        if argv:
            argv[0] = os.path.basename(argv[0])
            yield argv, raw


def leads_with(argv, tokens):
    """True when tokens appear in order in argv, the first at the command position."""
    if not argv or argv[0] != tokens[0]:
        return False
    rest = argv[1:]
    for token in tokens[1:]:
        if token not in rest:
            return False
        rest = rest[rest.index(token) + 1:]
    return True


def refuse(what, why, remedy):
    print(f"Blocked: {what} {why}.\n\n{remedy}", file=sys.stderr)
    return 2


DESTRUCTION_REMEDY = (
    "Destroying state is not a diagnostic step, and the vault repo has no copy but "
    "this one. See CLAUDE.method.md, \"a zero is a claim about the instrument\". If "
    "the state really is spent, say what will be lost and ask the operator. Do not "
    "reach for a variant that slips past this check."
)


def check_bash(command):
    for argv, raw in segments(command):
        for tokens, why in DESTRUCTIVE_ARGV:
            if not leads_with(argv, tokens):
                continue
            # git clean is harmless without a force flag, and is the usual preview.
            if tokens == ["git", "clean"] and not any(
                a.startswith("-") and "f" in a.lstrip("-") for a in argv
            ):
                continue
            # git restore --staged only unstages; the working tree is untouched.
            if tokens == ["git", "restore"] and "--staged" in argv and "--worktree" not in argv:
                continue
            return refuse(f"`{' '.join(tokens)}`", why, DESTRUCTION_REMEDY)

        # In-place stream edits over vault Markdown: the batch-corruption class. One
        # structural edge case rewrites every file before anything measures it.
        if argv[0] in {"sed", "perl", "ruby"} and VAULT_MD.search(raw):
            if any(a.startswith("-i") or a == "--in-place" for a in argv[1:]):
                return refuse(
                    "an in-place stream edit over vault Markdown",
                    "rewrites entries in bulk with nothing measuring the result",
                    "Use the owning script, or the Edit tool one anchored edit at a "
                    "time, then run scripts/precheck.sh while the edit is still in "
                    "your head.",
                )

        if argv[0] == "rm" and VAULT_MD.search(raw):
            return refuse("`rm` of vault Markdown", "deletes entries outright",
                          DESTRUCTION_REMEDY)

        # `>>` is an append and is left alone; see truncating_redirect on why this
        # is judged per segment, on argv, and not against the raw command.
        if truncating_redirect(argv):
            return refuse("a truncating redirect onto vault Markdown",
                          "replaces the whole file with the command's output",
                          DESTRUCTION_REMEDY)

    return 0


def truncating_redirect(argv):
    """True when a segment really redirects onto vault Markdown, `>>` excluded.

    ⚠⚠ THIS USED TO MATCH THE RAW COMMAND STRING, AND THAT BLOCKED TEXT THAT MERELY
    QUOTED A REDIRECT -- a commit message, a grep pattern, a test case naming one.
    It was the single check that fell back to raw matching while every rule above
    went through argv, which is the confusion this module's header says it avoids.

    Quoting is what separates them, and `shlex` already knows: a real operator
    survives as its own token, while `'x > f'` stays INSIDE one token.
    """
    for i, tok in enumerate(argv):
        bare = tok.lstrip("0123456789")          # `2>file` is still a redirect
        if bare == ">":
            target = argv[i + 1] if i + 1 < len(argv) else ""
        elif bare.startswith(">") and not bare.startswith(">>"):
            # An ATTACHED target never contains whitespace -- the shell would have
            # split it. Whitespace inside the token means quotes preserved it, i.e.
            # a grep pattern or a commit message, which redirects nothing.
            if any(c.isspace() for c in bare):
                continue
            target = bare.lstrip(">|")
        else:
            continue
        if VAULT_MD.search(target):
            return True
    return False


def check_edit(path):
    for pattern, why, remedy in STORE_OWNED:
        if pattern.search(path):
            return refuse(f"`{os.path.basename(path)}`", why,
                          f"Write it through:\n  {remedy}")
    return 0


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input", {})
    if tool == "Bash":
        return check_bash(tool_input.get("command", ""))
    if tool in {"Edit", "Write", "NotebookEdit"}:
        return check_edit(tool_input.get("file_path", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
