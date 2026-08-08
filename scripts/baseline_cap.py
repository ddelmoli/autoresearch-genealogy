#!/usr/bin/env python3
"""Gate: the vault's `.audit_baseline.txt` must fit the SessionStart injection cap.

** WHY THIS EXISTS (operator-directed, 08 AUG 2026). ** The baseline is injected into
every session's banner and hard-capped. Over the cap it is TRUNCATED FROM THE TAIL --
the banner says so, loudly, but only AFTER the content is gone, and nothing prevented
committing the file in that state. Session #154 committed it over-cap **six times in
one sitting**, each time by adding a line without cutting one, each time noticing only
because the next banner said so. A warning that fires after the loss is not a guard.

** IT MEASURES WHAT THE BANNER MEASURES, AND THAT IS THE WHOLE POINT. ** The injector
first truncates at the `----` history divider, THEN applies the cap. A checker that
counted raw file bytes would disagree with the banner on any vault whose history block
has grown -- the classic two-readers-one-file drift this repo has been bitten by. So
the divider logic is reproduced here deliberately, and the cap is READ FROM
`session_audit.sh` rather than duplicated: one home for the number.

** BLOCKING WHEN THE FILE IS STAGED, ADVISORY OTHERWISE**, which is a deliberate
departure from this repo's "new gates ship advisory" convention:
  - The convention exists because heuristic gates produce false positives that would
    block real work. **This gate is an exact byte count. It has no false-positive
    class**, so the reason for the soft landing does not apply.
  - Blocking only on a STAGED edit means it fires on the commit that introduces the
    overage, and never blocks unrelated work on a pre-existing one -- the same shape
    as `header_audit.py --changed-only`.

Usage:
    python3 scripts/baseline_cap.py                # advisory report
    python3 scripts/baseline_cap.py --staged-only  # block only if the file is staged
Exit 1 = over cap (and, with --staged-only, the file is in this commit).
"""
import argparse
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import vault_config

BASELINE_NAME = ".audit_baseline.txt"
DIVIDER_NOTE = "[baseline truncated at history divider; rest in .audit_baseline_history.txt]"


def injection_cap(script_dir=SCRIPT_DIR):
    """The cap, read from `session_audit.sh` — ONE home for the number.

    ⛔ Never defaults. A silently-wrong cap would make this gate agree with nothing,
    which is worse than not having it: the whole value here is that the gate and the
    banner cannot disagree."""
    path = os.path.join(script_dir, "session_audit.sh")
    with open(path, encoding="utf-8") as f:
        m = re.search(r"^BASELINE_CAP\s*=\s*(\d+)", f.read(), re.M)
    if not m:
        raise SystemExit(
            "baseline_cap: could not find `BASELINE_CAP = <n>` in session_audit.sh. "
            "The cap moved or was renamed -- fix this reader rather than hard-coding "
            "a second copy of the number.")
    return int(m.group(1))


def injected_length(text):
    """Length of what the banner would actually inject.

    Mirrors `session_audit.sh`: cut at the first `----` divider (replacing the rest
    with a one-line note), strip, then measure."""
    kept = []
    for line in text.splitlines():
        if line.strip().startswith("----"):
            kept.append(DIVIDER_NOTE)
            break
        kept.append(line)
    return len("\n".join(kept).strip())


def is_staged(vault, name=BASELINE_NAME):
    """True when `name` is in the staged diff of the repo that owns the vault."""
    try:
        out = subprocess.run(["git", "-C", str(vault), "diff", "--cached", "--name-only"],
                             capture_output=True, text=True, check=False)
    except OSError:
        return False
    return any(os.path.basename(p.strip()) == name for p in out.stdout.splitlines())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--staged-only", action="store_true",
                    help="exit non-zero ONLY when the baseline is staged in this commit")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    vault = vault_config.resolve_vault(args.vault)
    path = os.path.join(str(vault), BASELINE_NAME)
    if not os.path.exists(path):
        if not args.quiet:
            print(f"BASELINE_CAP: no {BASELINE_NAME} in this vault — nothing to check")
        return 0

    cap = injection_cap()
    with open(path, encoding="utf-8") as f:
        n = injected_length(f.read())
    over = n - cap
    staged = is_staged(vault)

    if over <= 0:
        if not args.quiet:
            print(f"BASELINE_CAP: {n}/{cap} chars (headroom {-over})  [ok]")
        return 0

    print(f"BASELINE_CAP: {n}/{cap} chars — OVER BY {over}.")
    print(f"  The SessionStart banner will DROP {over} chars from the TAIL of")
    print(f"  {BASELINE_NAME}, and the next session will not see them.")
    print("  ** Adding a line to that file means CUTTING one. ** Superseded blocks go")
    print("  below a `----` divider, into .audit_baseline_history.txt.")
    if args.staged_only and not staged:
        print("  [advisory here: the baseline is NOT staged in this commit]")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
