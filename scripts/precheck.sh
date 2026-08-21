#!/usr/bin/env bash
#
# precheck.sh — the WRITE-TIME half of the vault gate suite.
#
# WHY THIS EXISTS (session #177, 21 AUG 2026).
# Every gate this runs already existed, and every one of them is wired into the
# vault's pre-commit hook. The problem was never coverage, it was TIMING: the
# hook fires at `git commit`, which in this workflow is the END of a lane
# iteration, so a mistake made in the first write of an iteration is not
# reported until a dozen tool calls later — as a BLOCKED COMMIT that then has to
# be diagnosed, fixed and re-staged.
#
# Session #177 made three errors in one sitting. Two of them were caught by
# gates in this file:
#   * a bare ARK written into prose (a bare locator CREDITS itself, and
#     `~fs:1:1:X` cannot negate a bare `X`) — caught by bare_ark_audit at commit,
#     three calls and one failed commit after it was written;
#   * a child's birth act cited as a **Sources** record on the two parents it
#     was used to MINT — caught by census_diff at commit, after both entries
#     were fully written. The record documents the CHILD; being the declarant
#     does not make it the declarant's record (rule 8 limb (g)).
# Both were found by running these exact checks. Neither needed to be found late.
#
# So: run this after each entry write, not at the end of the iteration.
#
# ⚠ IT STAGES. The `--changed-only` gates read the git INDEX, not the working
# tree, so an unstaged edit is invisible to them — during #177 a fix appeared
# not to work for exactly this reason. This script therefore runs `git add -A`
# in the vault first. That is the same content the commit would stage anyway and
# it is not destructive, but it IS a side effect, so it is announced. Use
# --no-stage to check what is already staged instead.
#
# USAGE
#   AUTORESEARCH_VAULT=/path/to/vault bash scripts/precheck.sh [--no-stage] [--fast]
#
#   --no-stage   do not `git add -A`; audit whatever is staged right now
#   --fast       skip the whole-vault checks (integrity, prose, entry-boundary)
#                and run only the --changed-only gates + census_diff
#
# EXIT CODE
#   0  no BLOCKING finding
#   1  a BLOCKING gate fired — fix before continuing, do not carry it to commit
#
# ⛔ This does NOT replace the pre-commit hook and must never be used to justify
# `--no-verify`. The hook is the backstop; this is the fast feedback loop.

set -uo pipefail

STAGE=1
FAST=0
for arg in "$@"; do
    case "$arg" in
        --no-stage) STAGE=0 ;;
        --fast)     FAST=1 ;;
        -h|--help)  sed -n '2,45p' "$0"; exit 0 ;;
        *) echo "precheck: unknown argument '$arg'" >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Vault resolution: env var, else a sole ../vault-looking sibling. Deliberately
# stricter than session_audit.sh — this script is called mid-edit, and guessing
# the wrong vault here would audit the wrong tree and report a false clean.
VAULT="${AUTORESEARCH_VAULT:-}"
if [ -z "$VAULT" ]; then
    echo "precheck: AUTORESEARCH_VAULT is not set. Export it and re-run." >&2
    exit 2
fi
if [ ! -d "$VAULT" ]; then
    echo "precheck: AUTORESEARCH_VAULT='$VAULT' is not a directory." >&2
    exit 2
fi

export AUTORESEARCH_VAULT="$VAULT"
cd "$ROOT" || exit 2

BLOCKING=0
LINES=()

note()  { LINES+=("$1"); }
fail()  { BLOCKING=1; LINES+=("$1"); }

# Run a gate, extract its count from a named field, and classify it.
#   $1 label   $2 blocking(1/0)   $3 regex to pull "N" from   $4.. command
gate() {
    local label="$1" blocking="$2" pat="$3"; shift 3
    local out n
    out="$("$@" 2>&1)"
    n="$(printf '%s\n' "$out" | grep -oE "$pat" | grep -oE '[0-9]+' | tail -1)"
    if [ -z "$n" ]; then
        note "  ?  ${label}: could not read a count — RUN IT BY HAND"
        return
    fi
    if [ "$n" -eq 0 ]; then
        note "  ok ${label}: 0"
    elif [ "$blocking" -eq 1 ]; then
        fail "  ✗  ${label}: ${n}   [BLOCKING]"
    else
        note "  !  ${label}: ${n}   [advisory — read the rows]"
    fi
}

echo "=== PRECHECK — $(basename "$VAULT") ==="

if [ "$STAGE" -eq 1 ]; then
    ( cd "$VAULT" && git add -A ) || { echo "precheck: git add failed in $VAULT" >&2; exit 2; }
    echo "  (staged the vault working tree so the --changed-only gates can see it)"
fi

# ---- changed-only gates: cheap, and the ones that catch a bad write ----------
gate "bare ARK in prose (changed)"   1 'BARE_ARK \(changed\): *[0-9]+' \
     python3 scripts/bare_ark_audit.py --changed-only
gate "header grammar (changed)"      1 'HEADER_GRAMMAR \(changed\): *[0-9]+' \
     python3 scripts/header_audit.py --changed-only
gate "question register (changed)"   1 'QUESTION_AUDIT \(hard\): *[0-9]+' \
     python3 scripts/question_audit.py --changed-only
gate "entry attribution (changed)"   0 'ENTRY_ATTRIBUTION \(changed\): *[0-9]+' \
     python3 scripts/entry_attribution_audit.py --changed-only

# ---- whole-vault gates: slower, skipped under --fast ------------------------
if [ "$FAST" -eq 0 ]; then
    gate "integrity HARD"            1 'HARD violations[^:]*: *[0-9]+' \
         python3 scripts/gen_person_index.py --integrity
    gate "DATE_DRIFT"                1 'DATE_DRIFT: *[0-9]+' \
         python3 scripts/prose_audit.py
    gate "entry boundary"            1 'ENTRY_MISATTRIBUTION *[0-9]+' \
         python3 scripts/entry_boundary_audit.py
    gate "self-negation"             0 'SELF_NEGATION: *[0-9]+' \
         python3 scripts/self_negation_audit.py
fi

# ---- census diff: NOT a pass/fail. The point is that you READ it. -----------
# This is what caught #177's limb-(g) error: two newly minted parents came back
# LOW_COVERAGE/1 when they should have been UNCITED/0, because the child's birth
# act had been cited as their own record. No count is "wrong" here — an
# unexplained ROW is the finding.
echo
echo "--- census rows this edit MOVES (advisory; account for every row) ---"
CENSUS="$(python3 scripts/census_diff.py 2>&1)"
if printf '%s\n' "$CENSUS" | grep -q '0 row(s) moved, 0 added, 0 removed'; then
    echo "  no census row moved."
else
    printf '%s\n' "$CENSUS" | sed -n '/=== CENSUS DIFF/,$p' | sed 's/^/  /'
fi

echo
printf '%s\n' "${LINES[@]}"
echo

if [ "$BLOCKING" -ne 0 ]; then
    echo "PRECHECK: BLOCKING finding — fix it now, while the edit is still in your head."
    echo "  A bare ARK: give it a host prefix if it is a citation, or negate it in the"
    echo "  form written (~1:1:X cannot be negated by ~fs:1:1:X). Never delete it."
    exit 1
fi
echo "PRECHECK: no blocking finding. Census rows above still need accounting for."
exit 0
