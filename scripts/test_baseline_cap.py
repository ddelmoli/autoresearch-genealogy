#!/usr/bin/env python3
"""Regression tests for the baseline injection-cap gate.

Runnable with no test framework: `python3 scripts/test_baseline_cap.py`.

THE DEFECT IT GUARDS. `.audit_baseline.txt` is injected into every session's banner
and hard-capped; over the cap it is truncated FROM THE TAIL. The banner says so, but
only after the content is gone, and nothing stopped the file being committed that way.
Session #154 committed it over-cap SIX times in one sitting.

⚠⚠ THE ASSERTION THAT MATTERS MOST IS THAT THE GATE AND THE BANNER MEASURE THE SAME
THING. The injector truncates at the `----` history divider FIRST and applies the cap
SECOND, so a checker counting raw bytes would disagree with the banner on any vault
whose history block has grown -- and a gate that disagrees with the thing it guards is
worse than no gate. The divider case is pinned below, and so is the rule that the cap
is READ from session_audit.sh rather than duplicated.
"""
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import baseline_cap as BC

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def run(vault, *extra):
    # ⚠ AUTORESEARCH_VAULT OUTRANKS `--vault` -- that is the documented precedence
    # (env -> --vault -> sibling), not a bug. An earlier draft of this file left the
    # env var set and every fixture silently measured the REAL vault instead, so six
    # assertions failed against numbers from a file the test never wrote. Clear it.
    env = {k: v for k, v in os.environ.items() if k != "AUTORESEARCH_VAULT"}
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "baseline_cap.py"),
                        "--vault", vault, *extra],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout


def vault_with(text):
    d = tempfile.mkdtemp(prefix="baseline-cap-")
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        f.write('{"person_model": "narrative"}')
    with open(os.path.join(d, ".audit_baseline.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    return d


def main():
    cap = BC.injection_cap()
    print(f"the cap is READ from session_audit.sh, never duplicated: {cap}")
    check(cap > 0, f"a cap was found ({cap})")

    print()
    print("under / over the cap")
    code, out = run(vault_with("x" * (cap - 50)))
    check(code == 0 and "[ok]" in out, "under cap -> exit 0")
    code, out = run(vault_with("y" * (cap + 200)))
    check(code == 1, "over cap -> exit 1")
    check("OVER BY 200" in out, f"and it says BY HOW MUCH ({out.splitlines()[0][:46]})")

    print()
    print("⚠ IT MEASURES WHAT THE BANNER MEASURES: content ABOVE the `----` divider")
    # A file that is enormous overall but small above the divider is FINE -- that is
    # exactly what the divider is for, and a raw-bytes checker would wrongly fail it.
    below_divider = "z" * (cap * 3)
    code, out = run(vault_with("small current content\n----\n" + below_divider))
    check(code == 0,
          "huge history BELOW the divider does not trip the gate (raw-bytes would)")
    # ...and the converse: the divider does not excuse over-cap content ABOVE it.
    code, _ = run(vault_with("w" * (cap + 10) + "\n----\nhistory"))
    check(code == 1, "NEGATIVE CONTROL: over-cap ABOVE the divider still fails")

    print()
    print("the gate and the banner must not drift")
    text = "a" * 1234
    check(BC.injected_length(text) == 1234, "plain text measures its own length")
    check(BC.injected_length("abc\n----\n" + "q" * 9999)
          == len("abc\n" + BC.DIVIDER_NOTE), "divider replaced by the one-line note")

    print()
    print("--staged-only downgrades to advisory when the file is not in the commit")
    v = vault_with("y" * (cap + 200))          # a temp dir, not a git repo at all
    code, out = run(v, "--staged-only")
    check(code == 0, "not staged (no repo) -> advisory, exit 0")
    check("advisory here" in out, "and it SAYS it is advisory rather than going quiet")
    code, _ = run(v)
    check(code == 1, "POSITIVE CONTROL: without --staged-only the same vault fails")

    print()
    print("a vault with no baseline file is not an error")
    d = tempfile.mkdtemp(prefix="baseline-cap-none-")
    with open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8") as f:
        f.write('{"person_model": "narrative"}')
    code, out = run(d)
    check(code == 0 and "nothing to check" in out, "absent baseline -> exit 0, says so")

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
