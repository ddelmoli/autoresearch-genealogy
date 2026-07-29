#!/usr/bin/env python3
"""session_close.py — the session-end checklist as ONE command.

WHY IT EXISTS (29 JUL 2026 framework review). Closing a session correctly took five
separate commands listed as prose in the Handoff, and nothing ran them as a unit or
failed when one was skipped. Metrics went stale, the handoff drifted from its
template, and the next session inherited the confusion. This wraps the close steps
in order, reports each as PASS / DUE / SKIP / FAIL, and never silently omits one.

STEPS, IN ORDER
  1. plan       record the worked lane's outcome into the session-plan bandit
                (--lane/--outcome[/--note] -> session_plan.py --record). If a lane
                is pending and you give none, that is reported, not hidden.
  2. rotation   with --rotation-done, run profile_review.py --complete (resets the
                cadence clock). Only pass it when the drawn slice was actually
                polled and recorded — resetting the clock on unpolled work lies to
                the next session.
  3. log        with --log SLUG --summary "...", append the Research_Log session
                index row via log_session.py (NEVER the Edit tool on that file).
  4. lint       handoff_lint.py --quiet — the close-block template check.
  5. ascii      ascii_handoff.py count (fix with: python3 scripts/ascii_handoff.py --fix).
  6. archive    archive_sections.py --target handoff dry-run status; add
                --apply-archive to actually archive when due.

Then it prints the reminder that the Handoff's OPEN / NEXT for the next session
should be written FROM the plan (`session_plan.py` re-run or its printed table), so
the next session starts from a ranked list, not from memory.

Exit code: 1 if any step FAILED (subprocess error), else 0. DUE/SKIP are honest
states, not failures.

USAGE
  python3 scripts/session_close.py --lane EXPAND --outcome hit --note "2 silent closed"
  python3 scripts/session_close.py --lane ROTATE --outcome hit --rotation-done \\
      --log logs/2026-07-29-slug --summary "..." --apply-archive
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def run(script, *args, vault=None, timeout=300):
    """Run a sibling script; returns (ok, last_lines)."""
    try:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                           capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "AUTORESEARCH_VAULT": vault or ""})
    except Exception as e:  # noqa: BLE001
        return False, f"({type(e).__name__}: {e})"
    tail = [ln for ln in (r.stdout + r.stderr).strip().splitlines() if ln.strip()]
    return r.returncode == 0, "; ".join(tail[-3:]) if tail else "(no output)"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--lane", help="lane actually worked this session (EXPAND/IMPROVE/VERIFY/ROTATE)")
    ap.add_argument("--outcome", choices=["hit", "miss"])
    ap.add_argument("--note", default="")
    ap.add_argument("--rotation-done", action="store_true",
                    help="the profile-review slice was polled AND recorded; reset its clock")
    ap.add_argument("--log", help="logs/YYYY-MM-DD-slug for the Research_Log index row")
    ap.add_argument("--summary", help="one-line summary for the Research_Log index row")
    ap.add_argument("--apply-archive", action="store_true",
                    help="actually archive Handoff sections when due (default: report only)")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    failed = False
    report = []

    # 1. Plan outcome.
    if a.lane and a.outcome:
        ok, out = run("session_plan.py", "--record", "--lane", a.lane,
                      "--outcome", a.outcome, "--note", a.note, vault=vault)
        report.append(("plan", "PASS" if ok else "FAIL", out))
        failed |= not ok
    else:
        ok, out = run("session_plan.py", "--heartbeat", vault=vault)
        state = "DUE" if "NOT yet recorded" in out else "SKIP"
        report.append(("plan", state,
                       out if state == "DUE" else
                       "no --lane/--outcome given; lane outcome not recorded"))

    # 2. Rotation clock.
    if a.rotation_done:
        ok, out = run("profile_review.py", "--complete", vault=vault)
        report.append(("rotation", "PASS" if ok else "FAIL", out))
        failed |= not ok
    else:
        report.append(("rotation", "SKIP",
                       "--rotation-done not given; profile-review clock untouched "
                       "(correct if the slice was not polled this session)"))

    # 3. Research_Log index row.
    if a.log and a.summary:
        ok, out = run("log_session.py", "--log", a.log, "--summary", a.summary, vault=vault)
        report.append(("log", "PASS" if ok else "FAIL", out))
        failed |= not ok
    elif a.log or a.summary:
        report.append(("log", "FAIL", "--log and --summary must be given together"))
        failed = True
    else:
        report.append(("log", "SKIP",
                       "no --log/--summary; remember scripts/log_session.py (never Edit)"))

    # 4. Handoff close-block lint.
    ok, out = run("handoff_lint.py", "--quiet", vault=vault)
    report.append(("lint", "PASS" if ok else "CHECK", out))

    # 5. ASCII guard.
    ok, out = run("ascii_handoff.py", vault=vault)
    report.append(("ascii", "PASS" if ok else "CHECK", out))

    # 6. Handoff archive due?
    args = ["--target", "handoff"] + (["--apply"] if a.apply_archive else [])
    ok, out = run("archive_sections.py", *args, vault=vault)
    label = "PASS" if a.apply_archive and ok else ("FAIL" if not ok else "INFO")
    report.append(("archive", label, out))
    failed |= (not ok)

    width = max(len(n) for n, _, _ in report)
    print("=== SESSION CLOSE ===")
    for name, state, out in report:
        print(f"  {name:<{width}}  {state:<5}  {out[:180]}")
    print()
    print("  Now write the Handoff close block (template in Operating_Protocol.md),")
    print("  set OPEN / NEXT from the session plan (scripts/session_plan.py), and")
    print("  commit the vault. handoff_lint runs again in the pre-commit hook.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
