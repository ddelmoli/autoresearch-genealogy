#!/usr/bin/env python3
"""session_close.py — the session-end checklist as ONE command.

WHY IT EXISTS (29 JUL 2026 framework review). Closing a session correctly took five
separate commands listed as prose in the Handoff, and nothing ran them as a unit or
failed when one was skipped. Metrics went stale, the handoff drifted from its
template, and the next session inherited the confusion. This wraps the close steps
in order, reports each as PASS / DUE / SKIP / FAIL, and never silently omits one.

STEPS, IN ORDER
  0. close#     with --session N, report whether this is a FIRST CLOSE or a RE-CLOSE,
                and FAIL if a re-close passes --lane/--outcome or --log. ** Derived,
                not remembered (31 JUL 2026): ** the close prompt used to ask the agent
                whether it had already closed this sitting, which a resumed or cold
                agent cannot answer -- `history` carries a date and a lane, and two
                sittings in one day is normal here. The close now stamps `last_close`
                with the session number, so the next run can simply look.
  1. plan       record the worked lane's outcome into the session-plan bandit
                (--lane/--outcome[/--note] -> session_plan.py --record). If a lane
                is pending and you give none, that is reported, not hidden.
                ** Under the four-phase loop (21/22/23/24) this is normally SKIPPED
                on purpose: `22-research-iterations` records each iteration as it
                finishes, and recording again here would be a second observation
                for the same work. Pass --lane/--outcome only for an iteration that
                was worked and never recorded. **
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
  7. next       with --next-plan, run session_plan.py to register the NEXT session's
                draw. ** ORDER MATTERS AND IT USED TO BE WRONG. ** session_plan.py
                --record sets `pending: null`, so a plan run BEFORE the close (which
                the close prompt used to instruct) has its pending draw wiped by step
                1. That is not hypothetical: a Handoff announced "a pending draw is
                waiting: EXPAND" over a state file holding no pending draw, and the
                next session drew a different lane. Running it here, last, cannot be
                got wrong. Without the flag the step reports DUE with the ordering
                rule rather than staying silent.

Then it prints the reminder that the Handoff's OPEN / NEXT for the next session
should be written FROM the plan, so the next session starts from a ranked list, not
from memory.

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
from datetime import date

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
    ap.add_argument("--lane", help="lane actually worked this session (EXPAND/IMPROVE/ROTATE)")
    ap.add_argument("--outcome", choices=["hit", "miss"])
    ap.add_argument("--note", default="")
    ap.add_argument("--session", type=int, metavar="N",
                    help="the session number 21-session-start established. Stamps the "
                         "sitting on any observation recorded here, and lets this "
                         "command DETECT a re-close instead of asking you to remember "
                         "one (history rows carry only a date, and two sittings in a "
                         "day is normal).")
    ap.add_argument("--rotation-done", action="store_true",
                    help="the profile-review slice was polled AND recorded; reset its clock")
    ap.add_argument("--log", help="logs/YYYY-MM-DD-slug for the Research_Log index row")
    ap.add_argument("--summary", help="one-line summary for the Research_Log index row")
    ap.add_argument("--apply-archive", action="store_true",
                    help="actually archive Handoff sections when due (default: report only)")
    ap.add_argument("--next-plan", action="store_true", dest="next_plan",
                    help="after the outcome is recorded, run session_plan.py to register "
                         "the NEXT session's draw (order matters: --record clears `pending`, "
                         "so a plan run before this command is wiped by it)")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    failed = False
    report = []

    # 0. First close, or re-close? DERIVED, not remembered (31 JUL 2026). The close
    # prompt's step 0 used to ask the agent whether it had already closed this sitting,
    # which a resumed or cold agent cannot answer, and `history` carries only date+lane.
    import session_plan as sp  # noqa: E402
    state = sp.load_state(vault)
    prior = (state.get("last_close") or {}).get("session")
    reclose = a.session is not None and prior == a.session
    if a.session is not None:
        report.append(("close#", "INFO",
                       f"session #{a.session}" + (
                           f" — RE-CLOSE (already closed {(state.get('last_close') or {}).get('date')}): "
                           "record no new observation, add no second Research_Log row, "
                           "rewrite the close block to cover the whole sitting"
                           if reclose else " — first close")))
        if reclose and (a.lane or a.log):
            report.append(("guard", "FAIL",
                           "this sitting is already closed: --lane/--outcome and --log "
                           "are REFUSED below (they would double-count the bandit and "
                           "add a second Research_Log row). Correct the existing note "
                           "and row in place instead."))
            failed = True

    # 1. Plan outcome.
    if reclose and a.lane and a.outcome:
        report.append(("plan", "BLOCK",
                       "refused: session already closed, so this would be a SECOND "
                       "observation for one sitting"))
    elif a.lane and a.outcome:
        rec_args = ["--record", "--lane", a.lane, "--outcome", a.outcome, "--note", a.note]
        if a.session is not None:
            rec_args += ["--session", str(a.session)]
        ok, out = run("session_plan.py", *rec_args, vault=vault)
        report.append(("plan", "PASS" if ok else "FAIL", out))
        failed |= not ok
    else:
        ok, out = run("session_plan.py", "--heartbeat", vault=vault)
        plan_state = "DUE" if "NOT yet recorded" in out else "SKIP"
        report.append(("plan", plan_state,
                       out if plan_state == "DUE" else
                       "no --lane/--outcome given; nothing recorded here (correct when "
                       "each iteration recorded itself via session_plan.py --record)"))

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
    if reclose and (a.log or a.summary):
        report.append(("log", "BLOCK",
                       "refused: session already closed, so this would be a SECOND "
                       "Research_Log row for one sitting; correct the existing row in "
                       "place with a targeted replacement"))
    elif a.log and a.summary:
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

    # 6b. QUESTION register close (added 15 AUG 2026). Until now the close ran the
    # handoff archive target and NONE of the question targets, so terminal-status
    # blocks sat live for days (8 at the time this step was added) and the index /
    # router counts went stale between manual runs. Three sub-steps:
    #   q-archive   every drop-by-status target (dry-run; --apply-archive applies)
    #   q-index     regenerate Open_Questions_Index.md (a generated view is only a
    #               view if something regenerates it)
    #   q-router    refresh the shard-table counts in Open_Questions.md
    #   q-structure question_audit summary (the hook blocks NEW findings; this line
    #               is the whole-register reading for the close block)
    import json
    q_targets = []
    try:
        with open(os.path.join(vault, ".maintenance.json"), encoding="utf-8") as fh:
            q_targets = [t["name"] for t in json.load(fh).get("targets", [])
                         if t.get("policy") == "drop-by-status"]
    except (OSError, ValueError):
        pass
    if q_targets:
        outs, ok_all = [], True
        for name in q_targets:
            t_args = ["--target", name] + (["--apply"] if a.apply_archive else [])
            ok, out = run("archive_sections.py", *t_args, vault=vault)
            ok_all &= ok
            if "nothing to do" not in out:
                outs.append(f"{name}: {out[:80]}")
        label = ("PASS" if a.apply_archive else "INFO") if ok_all else "FAIL"
        report.append(("q-archive", label,
                       "; ".join(outs) if outs else
                       f"nothing to archive across {len(q_targets)} question target(s)"))
        failed |= not ok_all
    else:
        report.append(("q-archive", "SKIP", "no drop-by-status targets configured"))

    ok, out = run("gen_question_index.py", "--write",
                  os.path.join(vault, "Open_Questions_Index.md"), vault=vault)
    report.append(("q-index", "PASS" if ok else "FAIL", out))
    failed |= not ok

    ok, out = run("gen_question_index.py", "--router", vault=vault)
    report.append(("q-router", "PASS" if ok else "FAIL", out))
    failed |= not ok

    ok, out = run("question_audit.py", vault=vault)
    report.append(("q-structure", "PASS" if ok and "hard 0" in out else "CHECK", out))

    # 7. The NEXT session's draw — LAST, after the outcome above is recorded.
    # session_plan.py --record clears `pending`, so a plan run before this command
    # loses the draw it just registered (see the module docstring).
    if a.next_plan:
        ok, out = run("session_plan.py", vault=vault, timeout=900)
        report.append(("next", "PASS" if ok else "FAIL", out))
        failed |= not ok
    else:
        report.append(("next", "DUE",
                       "no --next-plan; run scripts/session_plan.py NOW — AFTER this "
                       "command, never before (--record clears `pending`) — and write "
                       "its lane into the Handoff's OPEN / NEXT"))

    if a.session is not None and not failed:
        st = sp.load_state(vault)
        st["last_close"] = {"session": a.session, "date": date.today().isoformat()}
        sp.save_state(vault, st)

    width = max(len(n) for n, _, _ in report)
    print("=== SESSION CLOSE ===")
    for name, state, out in report:
        print(f"  {name:<{width}}  {state:<5}  {out[:180]}")
    print()
    print("  Now write the Handoff close block (template in Operating_Protocol.md),")
    print("  set OPEN / NEXT from the `next` step's drawn lane, update the suggested")
    print("  /rename line and the next session's starting command, and commit the")
    print("  vault. handoff_lint runs again in the pre-commit hook.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
