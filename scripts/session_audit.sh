#!/bin/bash
# SessionStart hook: run the vault audit suite and inject a summary into Claude's context.
# Emits hook JSON on stdout (hookSpecificOutput.additionalContext).
#
# ---------------------------------------------------------------------------
# WHICH VAULT (resolution chain, widened 29 JUL 2026)
#
# This used to be one step: read $AUTORESEARCH_VAULT, and SKIP the whole suite
# if it was unset. That is why the hook did nothing on the sessions where it
# mattered most — the var has to be exported in the shell that LAUNCHES the
# agent, and forgetting is invisible: the session opens quiet, with no gate
# values, no census, no frontier count, and no error to notice. Prefixing
# commands afterwards cannot retro-fix a hook that already ran.
#
# The chain now, first match wins, and the source is ALWAYS named in the banner:
#   1. env         — $AUTORESEARCH_VAULT (an explicit operator choice)
#   2. last-session — .claude/last_vault, written by this hook on every success
#   3. sole-candidate — exactly ONE vault-looking dir in the project
#   4. ambiguous   — 0 or 2+ candidates: still SKIP, but now LIST the candidates
#                    and tell the agent to ASK which one
#
# Steps 2-3 do NOT reverse the "no implicit default vault" rule in
# CLAUDE.method.md. That rule guards vault_config.resolve_vault(), which every
# MUTATING script goes through, and it stays strict. This hook only READS and
# injects text, so a labelled fallback is safe where a silent one is not:
# a fallback-resolved banner instructs the agent to confirm the vault with the
# operator before writing anything.
#
# A hook cannot prompt (it runs non-interactively), so "confirm the vault" is
# necessarily the AGENT's first-turn job; the banner carries the instruction.
#
# To point the loop at a different vault without relaunching:
#   bash scripts/session_audit.sh --set-vault /path/to/vault
# ---------------------------------------------------------------------------
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/..}" || exit 0

PROJECT_DIR="$(pwd)"
STATE_FILE="$PROJECT_DIR/.claude/last_vault"

# A directory only counts as a vault if it carries a vault signature. This is
# what stops a typo'd export or a stray sibling dir from being audited as one.
vault_ok() {
    [ -n "$1" ] && [ -d "$1" ] && \
      { [ -f "$1/.autoresearch.json" ] || ls "$1"/Family_Tree*.md >/dev/null 2>&1; }
}

remember_vault() {
    mkdir -p "$PROJECT_DIR/.claude" 2>/dev/null && printf '%s\n' "$1" > "$STATE_FILE" 2>/dev/null
}

# Candidate vaults in the project tree (depth 1). vault-template/ is the empty
# starter kit, never a working vault.
find_candidates() {
    for d in "$PROJECT_DIR"/*/; do
        d="${d%/}"
        [ "$(basename "$d")" = "vault-template" ] && continue
        vault_ok "$d" && printf '%s\n' "$d"
    done
}

# Manual affordance: set the remembered vault and exit (plain text, NOT hook JSON).
if [ "${1:-}" = "--set-vault" ]; then
    if vault_ok "$2"; then
        remember_vault "$(cd "$2" && pwd)"
        echo "remembered vault: $(cd "$2" && pwd)  (written to .claude/last_vault)"
        exit 0
    fi
    echo "not a vault (no .autoresearch.json, no Family_Tree*.md): ${2:-<missing arg>}" >&2
    exit 1
fi

emit_skip() {
    jq -n --arg m "$1" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$m}}' 2>/dev/null \
      || printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$1"
    exit 0
}

VAULT_SOURCE=""
if [ -n "${AUTORESEARCH_VAULT:-}" ]; then
    if ! vault_ok "$AUTORESEARCH_VAULT"; then
        emit_skip "VAULT AUDIT SUITE: skipped — AUTORESEARCH_VAULT is set to '$AUTORESEARCH_VAULT', which does not look like a vault (no .autoresearch.json and no Family_Tree*.md). This is almost certainly a typo or a stale path in the launching shell. Tell the operator the exact value, and do NOT audit or research a guessed substitute."
    fi
    VAULT_SOURCE="env"
elif [ -s "$STATE_FILE" ] && IFS= read -r _remembered < "$STATE_FILE" && vault_ok "$_remembered"; then
    AUTORESEARCH_VAULT="$_remembered"
    VAULT_SOURCE="last-session"
else
    _cands="$(find_candidates)"
    _n="$(printf '%s\n' "$_cands" | grep -c . )"
    if [ "$_n" -eq 1 ]; then
        AUTORESEARCH_VAULT="$_cands"
        VAULT_SOURCE="sole-candidate"
    elif [ "$_n" -eq 0 ]; then
        emit_skip "VAULT AUDIT SUITE: skipped — no AUTORESEARCH_VAULT set, no remembered vault in .claude/last_vault, and no vault-looking directory found in $PROJECT_DIR (a vault carries .autoresearch.json or Family_Tree*.md). ASK the operator which vault to use before any research, then: bash scripts/session_audit.sh --set-vault /path/to/vault"
    else
        emit_skip "VAULT AUDIT SUITE: skipped — no AUTORESEARCH_VAULT set and no remembered vault, and $_n candidate vaults exist, so guessing is unsafe: $(printf '%s\n' "$_cands" | tr '\n' ' '). ASK the operator WHICH vault this session is for (do not pick one), then: bash scripts/session_audit.sh --set-vault /path/to/vault  — and run: bash scripts/session_audit.sh  to get the gate values this session is missing."
    fi
fi

AUTORESEARCH_VAULT="$(cd "$AUTORESEARCH_VAULT" && pwd)"
export AUTORESEARCH_VAULT AUTORESEARCH_VAULT_SOURCE="$VAULT_SOURCE"
remember_vault "$AUTORESEARCH_VAULT"

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
    # READ THE PINNED LIST FROM .maintenance.json, which is what the ARCHIVER reads.
    # It used to be hardcoded here "identical to archive_next_session.PINNED_PATTERNS",
    # and it drifted twice: first by missing LONGER-TERM OPTIONS, then again on
    # 28 JUL 2026 when the protocol block moved out and 'Operating protocol' was
    # pinned in its place -- each time the heartbeat counted one more "session
    # section" than the archiver did, and the two tools disagreed on every run.
    # One list, one reader. The literal is only a fallback for a vault with no config.
    pinned = ("Start here", "Operating protocol", "WATCHLIST AGING REMINDER",
              "Quick-resume commands", "Reminders for next session", "LONGER-TERM OPTIONS")
    keep = 1  # archive_sections handoff default; overridden by the config below
    try:
        import json as _json
        _cfg = _json.loads((VAULT / ".maintenance.json").read_text(encoding="utf-8"))
        for _t in _cfg.get("targets", []):
            if _t.get("name") == "handoff":
                if _t.get("pinned_patterns"):
                    pinned = tuple(_t["pinned_patterns"])
                if _t.get("keep") is not None:
                    keep = int(_t["keep"])
    except Exception:
        pass
    session = sum(1 for ln in txt.splitlines()
                  if ln.startswith("## ") and not any(k in ln for k in pinned))
    # Nested `### #NN CLOSE` blocks live inside the pinned "Start here" H2 and are
    # usually the bulk of the file; the archiver can now trim them (--keep-closes).
    # Same shape the archiver's CLOSE_RE requires (`### #<digits> CLOSE`), so the
    # two tools cannot disagree about what counts as a close.
    closes = len(re.findall(r"^### #\d+ CLOSE", txt, re.M))
    # Nudge ONLY when the archiver can actually act. The archiver is
    # archive_sections.py --target handoff, and its `keep` comes from the SAME
    # .maintenance.json read above (one list, one reader — this line previously
    # pointed at the legacy archive_next_session.py with a hardcoded keep of 5,
    # 5x looser than the configured policy; corrected 29 JUL 2026). The old
    # condition also included `nlines > 450`, which fired forever on a file whose
    # kept closes are ~400 lines by themselves -- an unactionable nag that trained
    # everyone to ignore it. Size alone is reported in the line count.
    nudge = ("  <-- run scripts/archive_sections.py --target handoff --apply"
             if session > keep or closes > 3 else " OK")
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

def writeback():
    """FS write-back queue depth, counted straight off the person entries.

    THE POINT IS THAT THERE IS NO QUEUE FILE. `FS_Writeback_Queue.md` was retired
    31 JUL 2026 after drifting in both directions across eight sessions (two
    executed write-backs still reading "queued" on their entries; seven of nine
    "no fs: key" rows silently resolved). The flag now lives on the person, whose
    entry already holds the evidence, and the count is derived here every session
    so nothing has to remember to look. Nothing else surfaces it: no lane draws
    this work and no gate fails when it grows.

    ** THE MATCH IS DELIBERATELY TOLERANT. ** The corpus held FIVE spellings when
    the grammar was written (`FS WRITE-BACK DONE`, `FS write-back DONE`, either
    with or without a leading check mark, plus the QUEUED forms), and the first
    version of this counter matched case-sensitively and undercounted DONE by
    four. Canonical is `**FS write-back QUEUED|DONE|DROPPED <date>**` per
    CLAUDE.method.md rule 8; this reads all of them."""
    import glob
    import re as _re
    pat = _re.compile(r"FS\s+write-?back\s+(QUEUED|DONE|DROPPED)", _re.IGNORECASE)
    n = {"QUEUED": 0, "DONE": 0, "DROPPED": 0}
    files = set()
    for f in glob.glob(os.path.join(VAULT, "Family_Tree*.md")):
        try:
            t = open(f, encoding="utf-8").read()
        except OSError:
            continue
        for m in pat.finditer(t):
            state = m.group(1).upper()
            n[state] += 1
            if state == "QUEUED":
                files.add(os.path.basename(f))
    closed = n["DONE"] + n["DROPPED"]
    if not n["QUEUED"]:
        return f"WRITEBACK: 0 queued ({closed} closed to date)  [operator-gated; nothing pending]"
    return (f"WRITEBACK: {n['QUEUED']} FS write-back(s) QUEUED across {len(files)} file(s), "
            f"{closed} closed to date ({n['DONE']} done / {n['DROPPED']} dropped) - "
            f"operator-gated, drained by prompt 17; "
            f"grep -ric 'FS write-back QUEUED' Family_Tree*.md")

parts = [
    # THE PLAN COMES FIRST (29 JUL 2026): the banner used to lead with 10 integrity
    # gates and bury the work signals, which pointed sessions at INTEGRITY when the
    # stated priority is EXTENSION-first. The plan heartbeat is state-only (cheap);
    # the session's first COMMAND is phase 1 (`21-session-start`); the plan itself is
    # phase 2's first command (`python3 scripts/session_plan.py`), which prints the
    # ranked worklist and draws the lane. Close with scripts/session_close.py.
    "plan -> " + run("session_plan.py", r"PLAN:", args=["--heartbeat"], max_lines=1),
    "integrity -> " + run("gen_person_index.py",
                          r"DUP_ID \(|MISSING_ID \(|DUP_FS_PID \(|COUPLE_NAME \(|HARD violations",
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
    # Generation-heading drift (gen_heading_audit.py): the `### Generation N`
    # heading vs the meta `generation:` field — two copies of one fact, same
    # defect class as DATE_DRIFT. 81 entries had drifted when the check landed
    # (29 JUL 2026), and in 80 of 81 the FIELD agreed with the edge graph — the
    # headings were lying. Advisory; drive to 0, then promote.
    "gen-heading -> " + run("gen_heading_audit.py", r"GEN_HEADING_DRIFT:",
                            args=["--heartbeat"], max_lines=1),
    # File-level frontmatter (frontmatter_audit.py): the layer no other gate reads.
    # On the reference vault 3 files had frontmatter that did not PARSE (unquoted
    # `: ` in a prose value), 2 had duplicate keys silently dropping data, and 10
    # carried session narratives in `updated:`. Advisory; baseline 0 as of 29 JUL
    # 2026 — a non-zero here is a REGRESSION, not a backlog.
    "frontmatter -> " + run("frontmatter_audit.py", r"FRONTMATTER:",
                            args=["--heartbeat"], max_lines=1),
    # Both metrics from meta_presence_audit: META_PRESENCE (narrative with no meta
    # block — invisible to the integrity gate) and ORPHANED_META (meta block split
    # from its bold name, so the parser adopts the WRONG display name + vitals).
    "meta_presence -> " + run("meta_presence_audit.py",
                              r"META_PRESENCE violations:|ORPHANED_META violations:",
                              max_lines=2),
    # Phase-2 edge-graph integrity (build_edges.py --validate): structural violations
    # (MALFORMED_EDGE_REF / dangling id refs / self-edges / broken spouse reciprocity)
    # must stay 0. PARENT-GEN MISMATCH is the UNEXPLAINED gen-numbering backlog signal,
    # not edge bugs; GEN_COLLAPSE is the subset the operator has declared as pedigree
    # collapse in .autoresearch.json and is expected to be non-zero (deferred 16).
    "edges -> " + run("build_edges.py",
                      r"structural violations|PARENT-GEN MISMATCH \(|GEN_COLLAPSE \(|MALFORMED_EDGE_REF \(",
                      args=["--validate"]),
    # Entry-boundary attribution (spec/entry-boundary). ENTRY_MISATTRIBUTION is the
    # HARD one, baseline 0: any narrative line credited to an entry other than the
    # header that precedes it at line start means the census parser has lost a body
    # boundary — the silent defect that under-credited 92 people. SOURCE_MISATTRIBUTION
    # is the subset that lands on a `Sources` bullet, i.e. moves the census today.
    "entry-boundary -> " + run("entry_boundary_audit.py", r"ENTRY_BOUNDARY:", max_lines=1),
    "watchlist -> " + run("watchlist_age.py", r"Watchlist:"),
    # New-Records Watch (discovery) aging: reads .maintenance.json `new_records`
    # tiers (A/B/C = 90/180/365d) + prints per-tier DUE/OK. Sibling of the
    # contributor-change watchlist; registry in New_Records_Watch.md.
    "new-records -> " + run("new_records_age.py", r"New-Records:", max_lines=1),
    # Profile-review rotation (profile_review.py --heartbeat): the THIRD timed loop,
    # asking whether a SLICE of the vault has gained new sources / relationships /
    # vitals on FS, WikiTree or Ancestry since we last looked. Reads .maintenance.json
    # `profile_review` + profile_review_snapshots.json only -- no census, so it is
    # cheap. Absent config => a "not configured" line, so the check stays upstream-safe.
    "profile-review -> " + run("profile_review.py", r"Profile-Review:",
                               args=["--heartbeat"], max_lines=1),
    "handoff -> " + next_session_size(),
    # Handoff close-block conformance (handoff_lint.py --quiet). ADVISORY; promote to
    # blocking once its baseline is 0. Checks the item-12 template: required fields
    # (RETRACTIONS and NEGATIVES / DO-NOT-REDO especially), the ~120-line cap, that
    # exactly ONE close block is live, and that no banner-computed metric has been
    # hand-copied into prose — the failure mode that carried `SOURCE_GAP 218` forward
    # while the live value was 243. READ THE FLAGGED ROWS before trusting the count.
    "handoff-lint -> " + run("handoff_lint.py", r"HANDOFF_LINT:", args=["--quiet"], max_lines=1),
    "housekeeping -> " + run("size_heartbeat.py", r"HOUSEKEEPING", max_lines=1),
    # Open_Questions heading grammar (archive_sections.py --lint-headings). ADVISORY,
    # baseline 0. A heading whose terminal-status slot holds a provenance clause
    # ("— raised <date>") CANNOT ARCHIVE once resolved, because the status is read as
    # the text after the LAST em-dash — so resolved blocks accumulate inline while the
    # archiver truthfully reports "nothing to archive". Found in 28 of 144 questions on
    # 11 AUG 2026 (2 already blocking, 26 latent); all 28 fixed, hence baseline 0.
    # A NON-ZERO IS A FUTURE SILENT BACKLOG, not a present error — fix the heading.
    "oq-headings -> " + run("archive_sections.py", r"HEADING_LINT",
                            args=["--lint-headings"], max_lines=1),
    # Question-register size + triage counts (gen_question_index.py --heartbeat).
    # ** THE COUNTS ARE COMPUTED, NEVER COPIED. ** The register outgrew a single
    # context (~800 KB / ~206k tokens at 146 live questions) while the vault's own
    # prose still described it as "~310 KB" -- 2.6x stale. A hand-written size is a
    # number that lies; this line regenerates it every session. `Open_Questions_Index.md`
    # is the READABLE view (~26 KB, one Read); if it disagrees with this line, the
    # snapshot is stale -- regenerate with `gen_question_index.py --write`.
    "questions -> " + run("gen_question_index.py", r"QUESTIONS:",
                          args=["--heartbeat"], max_lines=1),
    # Recipe-S FS source-harvest coverage + cadence (harvest_sources.py --heartbeat):
    # SOURCE_GAP/LOW/WELL counts + DUE/OK vs the .maintenance.json `harvest` cadence.
    "privacy-repo -> " + privacy_repo(),
    "recipe-s -> " + run("harvest_sources.py", r"RECIPE-S:", args=["--heartbeat"], max_lines=1),
    # Extension frontier (extension_frontier.py --heartbeat): SILENT = parentless AND
    # no stated reason. STANDING GOAL IS SILENT 0 — every row exits either by gaining
    # parents or by gaining a written reason. Surfaced every session so the goal is
    # standing rather than remembered; the trailing "[review]" counts DECLARED rows
    # that cite no source or route, which is the cheap-win failure mode.
    "frontier -> " + run("extension_frontier.py", r"FRONTIER:", args=["--heartbeat"], max_lines=1),
    # BIOGRAPHICAL completeness (bio_completeness.py), which is a DIFFERENT AXIS from
    # the source census above: that one counts RECORDS, this one asks whether a life
    # has actually been written. An entry with 30 ARKs and no prose scores
    # WELL_SOURCED and is not finished work. Standing goal (operator, 01 AUG 2026):
    # "every person in the vault to have as complete a biographical entry as
    # possible". Reported every session so it cannot drift back into an intention.
    "bio -> " + run("bio_completeness.py", r"BIO_COMPLETE", args=["--heartbeat"], max_lines=1),
    # FS write-back queue, counted off the ENTRIES (no queue file exists -- see the
    # writeback() docstring). Operator-gated work that no lane draws and no gate
    # counts, so the banner is the only thing that keeps it visible.
    "writeback -> " + writeback(),
]
# The project-specific "known baseline" (which advisory findings are expected and
# at what counts) lives in an OPTIONAL vault-local file so this hook stays generic.
# If the file is absent, fall back to a neutral reminder.
#
# CURRENT BASELINE ONLY: the file is injected into context EVERY session, and by
# 29 JUL 2026 it had accumulated 712 lines of appended history (~14k tokens per
# session, the single largest context cost of the whole suite). Superseded blocks
# now live in .audit_baseline_history.txt; as a guard against the history creeping
# back, this hook injects only the content ABOVE the first `----` divider line,
# and hard-caps the injected baseline (with an explicit truncation note).
#
# ** THE CAP WAS RAISED 4000 -> 6000 ON 04 AUG 2026, AND A HEADROOM LINE ADDED,
# because the cap kept firing on the WRONG failure (operator: "we keep running
# into that 4000 character limit"). ** Three things were wrong with it:
#   1. It was written to catch HISTORY CREEPING BACK -- a 712-line, unmistakable
#      regression -- but what actually tripped it was CURRENT, legitimate content
#      growing by ~200 chars. The cap cannot tell those apart. The `----` divider
#      above is the guard that actually stops the history case, and it works: the
#      history file sits at ~64 KB and never reaches context.
#   2. ** WHAT IT DROPPED WAS POSITIONAL, NOT BY IMPORTANCE. ** Truncating at a
#      byte offset kills whatever is LAST in the file, and this vault had put its
#      CONTEXT RULES block -- the most operationally load-bearing lines in it --
#      at the very end. The least expendable content was structurally first to go.
#      (Fixed on the vault side too: CONTEXT RULES moved to the TOP of the file.)
#   3. ** NOTHING REPORTED THE SIZE UNTIL IT WAS ALREADY TOO LATE. ** The only
#      signal was the truncation note itself, i.e. after content had been lost.
#      The `baseline ->` part now prints chars/cap and the headroom EVERY session,
#      so growth is visible while there is still room to act on it.
# The baseline is ~half of an ~8 KB banner, so the extra 2 KB is a small price for
# not amputating the tail; the divider, not the cap, is what bounds the real risk.
BASELINE_CAP = 6000
_bp = VAULT / ".audit_baseline.txt"
_bl_note = ""
if _bp.exists():
    baseline = _bp.read_text(encoding="utf-8")
    _kept = []
    for _ln in baseline.splitlines():
        if _ln.strip().startswith("----"):
            _kept.append("[baseline truncated at history divider; rest in .audit_baseline_history.txt]")
            break
        _kept.append(_ln)
    baseline = "\n".join(_kept).strip()
    _bl_chars = len(baseline)
    if _bl_chars > BASELINE_CAP:
        baseline = baseline[:BASELINE_CAP] + (
            f" [!! BASELINE TRUNCATED at {BASELINE_CAP} chars -- {_bl_chars - BASELINE_CAP} chars of the"
            " TAIL of .audit_baseline.txt were DROPPED and you are not seeing them. Trim the file to"
            " CURRENT state only; move superseded blocks below a `----` divider.]")
        _bl_note = (f"baseline -> !! TRUNCATED: {_bl_chars}/{BASELINE_CAP} chars, "
                    f"{_bl_chars - BASELINE_CAP} DROPPED from the tail -- trim .audit_baseline.txt")
    else:
        _bl_note = (f"baseline -> {_bl_chars}/{BASELINE_CAP} chars "
                    f"(headroom {BASELINE_CAP - _bl_chars}; injected every session, keep it CURRENT-only)")
else:
    _bl_note = "baseline -> no .audit_baseline.txt in this vault (neutral reminder injected instead)"
    baseline = ("Compare against your project's known baseline; investigate anything above it "
                "before new vault work. The pre-commit hook enforces gen_person_index --integrity "
                "(HARD: unique id + complete meta) on every vault commit; prose_audit + header_xref "
                "are advisory.")
# WHICH VAULT, AND HOW IT WAS CHOSEN. The bash chain above always names its
# source; an `env` resolution is an explicit operator choice and needs no
# confirmation, while a fallback one does. A hook cannot ask, so the agent is
# told to — and is given the exact command prefix, since env vars do not
# survive between the agent's shell calls.
_src = os.environ.get("AUTORESEARCH_VAULT_SOURCE", "env")
_prefix = f'AUTORESEARCH_VAULT="{VAULT}"'
if _src == "env":
    _vline = f"VAULT: {VAULT.name} (source: explicit AUTORESEARCH_VAULT). Prefix your own commands: {_prefix}"
else:
    _how = {"last-session": "the vault this project audited LAST session (.claude/last_vault)",
            "sole-candidate": "the only vault-looking directory in the project"}.get(_src, _src)
    _vline = (f"VAULT: {VAULT.name} (source: {_src} — NOT an explicit choice this session; resolved as {_how}). "
              f"CONFIRM this is the intended vault with the operator in your first reply, before any write; "
              f"to switch: bash scripts/session_audit.sh --set-vault /path/to/other-vault. "
              f"Prefix your own commands: {_prefix}")
ctx = (f"VAULT AUDIT SUITE (SessionStart hook, scripts/session_audit.sh): {_vline} || "
       + " || ".join(parts + [_bl_note]) + ". " + baseline)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                          "additionalContext": ctx}}))
PY
