#!/bin/bash
# SessionStart hook: run the vault audit suite and inject a summary into Claude's context.
# Emits hook JSON on stdout (hookSpecificOutput.additionalContext).
#
# Multi-vault: the vault to audit comes from $AUTORESEARCH_VAULT (there is no
# default vault). Export it before launching, e.g.
#   export AUTORESEARCH_VAULT="$HOME/.../vault-<name>"
# If it is unset, this hook SKIPS the audit rather than guessing a vault.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/..}" || exit 0

if [ -z "${AUTORESEARCH_VAULT:-}" ]; then
    msg="VAULT AUDIT SUITE: skipped — no AUTORESEARCH_VAULT set (there is no default vault). Export AUTORESEARCH_VAULT=/path/to/vault before launching to audit a specific vault."
    jq -n --arg m "$msg" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$m}}' 2>/dev/null \
      || printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
    exit 0
fi

python3 - <<'PY'
import json, re, subprocess, os
from pathlib import Path

# The vault to audit (guaranteed set: the bash guard above exits if it is not).
VAULT = Path(os.path.expanduser(os.environ["AUTORESEARCH_VAULT"]))

def run(script, pattern, max_lines=4, args=None):
    # The child scripts inherit AUTORESEARCH_VAULT and resolve the same vault.
    try:
        out = subprocess.run(["python3", f"scripts/{script}"] + (args or []),
                             capture_output=True, text=True, timeout=90).stdout
    except Exception as e:
        return f"FAILED ({e})"
    lines = [l.strip() for l in out.splitlines() if re.search(pattern, l)]
    return "; ".join(lines[:max_lines]) if lines else "no summary lines"

def next_session_size():
    # Heartbeat for the Handoff archiving process (scripts/archive_next_session.py).
    p = VAULT / "Handoff.md"
    if not p.exists():
        return "Handoff.md missing"
    txt = p.read_text(encoding="utf-8")
    nlines = txt.count("\n") + 1
    # Keep this list identical to archive_next_session.PINNED_PATTERNS -- it was
    # missing LONGER-TERM OPTIONS, so the heartbeat counted one more "session
    # section" than the archiver did and the two tools disagreed on every run.
    pinned = ("Start here", "WATCHLIST AGING REMINDER", "Quick-resume commands",
              "Reminders for next session", "LONGER-TERM OPTIONS")
    session = sum(1 for ln in txt.splitlines()
                  if ln.startswith("## ") and not any(k in ln for k in pinned))
    # Nested `### #NN CLOSE` blocks live inside the pinned "Start here" H2 and are
    # usually the bulk of the file; the archiver can now trim them (--keep-closes).
    # Same shape the archiver's CLOSE_RE requires (`### #<digits> CLOSE`), so the
    # two tools cannot disagree about what counts as a close.
    closes = len(re.findall(r"^### #\d+ CLOSE", txt, re.M))
    # Nudge ONLY when the archiver can actually act, i.e. mirror its own defaults
    # (--keep 5 H2 sessions, --keep-closes 3). The old condition included
    # `nlines > 450`, which fired forever on a file whose 3 kept closes are ~400
    # lines by themselves -- an unactionable nag that trained everyone to ignore it.
    # Size alone is reported in the line count; it is not an archiver action.
    nudge = ("  <-- run scripts/archive_next_session.py"
             if session > 5 or closes > 3 else " OK")
    # ASCII guard: defer to ascii_handoff's policy (Latin letters with
    # diacritics are ALLOWED as real names; only symbols/emoji/typographic
    # punctuation/non-Latin scripts are flagged). A naive ord()>127 count
    # false-alarms on perfectly ordinary names spelled with diacritics.
    try:
        import sys; sys.path.insert(0, "scripts")
        import ascii_handoff
        nonascii = ascii_handoff.count()
    except Exception:
        nonascii = sum(1 for c in txt if ord(c) > 127)
    ascii_status = "ASCII OK" if nonascii == 0 else f"NON-ASCII {nonascii} <-- python3 scripts/ascii_handoff.py --fix"
    return (f"{nlines} lines, {session} session sections, {closes} nested closes"
            f"{nudge}; {ascii_status}")

# Post-Person_Index-retirement (2026-06-24): the index drift-policing audits
# (duplicate_rows, harvest_pids, gen_audit) were retired. The narrative-native
# HARD gate is gen_person_index --integrity (unique internal id + complete meta).
# The FRAMEWORK repo's PII gate. Distinct from every other line in this banner:
# those audit the VAULT (local-only, no remote, a mistake is editable). This one
# audits the public fork, where a leaked name or record identifier is in
# published history and a later edit does not undo it.
#
# Surfaced here as well as in the framework pre-commit hook because the two catch
# different moments: the hook stops a bad commit, this tells you at session start
# whether the repo is ALREADY carrying something — including anything that
# arrived via --no-verify or before the hook was installed (23 JUL 2026).
#
# It is Ruby, so it cannot use run() above, which shells python3.
def privacy_repo():
    denylist = Path("scripts").parent / ".private" / "anonymization-denylist.txt"
    if not denylist.exists():
        return "skipped (no .private denylist in this checkout; name checks cannot run)"
    try:
        # LANG is commonly unset under a hook; the script pins UTF-8 internally as
        # of 23 JUL 2026, and this belt-and-braces keeps an older copy working.
        env = dict(os.environ)
        env.setdefault("LANG", "en_US.UTF-8")
        pr = subprocess.run(["scripts/privacy-audit-repo"], capture_output=True,
                            text=True, timeout=180, env=env)
    except Exception as e:
        return f"ERROR ({type(e).__name__})"
    out = (pr.stdout + pr.stderr).strip()
    if pr.returncode == 0:
        return "PASS (public fork clean: 0 denylist hits at HEAD, 0 in history, 0 record-identifier leaks)"
    tail = " / ".join(l.strip() for l in out.splitlines()[-3:] if l.strip())
    return f"** FINDINGS ** (exit {pr.returncode}) {tail[:200]}"

parts = [
    "integrity -> " + run("gen_person_index.py",
                          r"DUP_ID \(|MISSING_ID \(|DUP_FS_PID \(|HARD violations",
                          args=["--integrity"]),
    # prose_audit now also emits DATE_DRIFT (spec/structured-dates Spec 06): the
    # header-vs-field year sync gate for the two-store date model. Advisory,
    # baseline 0; a non-zero count means a header and its `- meta:` date field
    # disagree on the YEAR, which no other gate can see.
    "prose_audit -> " + run("prose_audit.py",
                            r"ERROR issues:|WARN issues:|DATE_DRIFT:", max_lines=3),
    "header_xref -> " + run("header_xref_audit.py", r"HEADER_XREF violations:"),
    # Header grammar conformance (spec/header-grammar Spec 02). ADVISORY with a
    # large known baseline — the migration is Spec 04, so a non-zero number here
    # is the backlog, not a regression. Watch it go DOWN, and watch for it going
    # UP, which means a new entry was written in a dialect the grammar forbids.
    "header_grammar -> " + run("header_audit.py", r"HEADER_GRAMMAR:"),
    "dup_name -> " + run("dup_name_audit.py", r"DUP_NAME_STRONG:|DUP_NAME_POSSIBLE:"),
    # Both metrics from meta_presence_audit: META_PRESENCE (narrative with no meta
    # block — invisible to the integrity gate) and ORPHANED_META (meta block split
    # from its bold name, so the parser adopts the WRONG display name + vitals).
    "meta_presence -> " + run("meta_presence_audit.py",
                              r"META_PRESENCE violations:|ORPHANED_META violations:",
                              max_lines=2),
    # Phase-2 edge-graph integrity (build_edges.py --validate): structural violations
    # (dangling id refs / self-edges / broken spouse reciprocity) must stay 0; the
    # parent-gen mismatch count is the known gen-numbering backlog signal, not edge bugs.
    "edges -> " + run("build_edges.py", r"structural violations|PARENT-GEN MISMATCH \(",
                      args=["--validate"]),
    "watchlist -> " + run("watchlist_age.py", r"Watchlist:"),
    # New-Records Watch (discovery) aging: reads .maintenance.json `new_records`
    # tiers (A/B/C = 90/180/365d) + prints per-tier DUE/OK. Sibling of the
    # contributor-change watchlist; registry in New_Records_Watch.md.
    "new-records -> " + run("new_records_age.py", r"New-Records:", max_lines=1),
    "handoff -> " + next_session_size(),
    "housekeeping -> " + run("size_heartbeat.py", r"HOUSEKEEPING", max_lines=1),
    # Recipe-S FS source-harvest coverage + cadence (harvest_sources.py --heartbeat):
    # SOURCE_GAP/LOW/WELL counts + DUE/OK vs the .maintenance.json `harvest` cadence.
    "privacy-repo -> " + privacy_repo(),
    "recipe-s -> " + run("harvest_sources.py", r"RECIPE-S:", args=["--heartbeat"], max_lines=1),
]
# The project-specific "known baseline" (which advisory findings are expected and
# at what counts) lives in an OPTIONAL vault-local file so this hook stays generic.
# If the file is absent, fall back to a neutral reminder.
_bp = VAULT / ".audit_baseline.txt"
baseline = (_bp.read_text(encoding="utf-8").strip() if _bp.exists()
            else "Compare against your project's known baseline; investigate anything above it "
                 "before new vault work. The pre-commit hook enforces gen_person_index --integrity "
                 "(HARD: unique id + complete meta) on every vault commit; prose_audit + header_xref "
                 "are advisory.")
ctx = (f"VAULT AUDIT SUITE (SessionStart hook, scripts/session_audit.sh; vault={VAULT.name}): "
       + " || ".join(parts) + ". " + baseline)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                          "additionalContext": ctx}}))
PY
