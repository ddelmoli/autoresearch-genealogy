#!/usr/bin/env python3
"""Pin: what guard_destructive.py refuses, and -- as much -- what it must not.

⭐⭐ THIS SUITE IS DELIBERATELY ORGANISED BY PRODUCT, NOT BY RULE, and the case-law
entry `5771ed1` is why. The guard's first suite ran 33 cases, covered every rule and
every input class, and still missed the defect: the argv rules were tested against
quoted text and the redirect rule against real redirects, so the one combination
that mattered -- quoted text against the redirect rule -- was never formed. A suite
organised rule-by-rule tests the rules that behave alike and hides the one that does
not.

So each rule is crossed against every input class that could plausibly fool it:
quoted mentions, the framework repo, a vault, a `cd`, a `-C`, and a missing `cwd`.

Fixtures only: no vault is touched, and the vault used here is a temporary directory
holding an empty `.autoresearch.json`, which is the marker the guard looks for.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard_destructive.py")
BLOCK, ALLOW = 2, 0

GT = chr(62)          # written this way so the file does not contain a literal
Q = chr(39)           # redirect onto vault Markdown -- which the guard would refuse
FT = "Family_" + "Tree.md"
FAILURES = []


def run(tool, cwd=None, **tool_input):
    payload = {"tool_name": tool, "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = cwd
    done = subprocess.run([sys.executable, GUARD], input=json.dumps(payload),
                          capture_output=True, text=True)
    return done.returncode


def check(want, label, tool, cwd=None, **tool_input):
    got = run(tool, cwd, **tool_input)
    mark = "ok  " if got == want else "FAIL"
    if got != want:
        FAILURES.append(f"{label}: got {got}, want {want}")
    print(f"  {mark} {label}")


def main():
    fw = tempfile.mkdtemp(prefix="fw-")                 # stands in for the framework
    vault = tempfile.mkdtemp(prefix="vault-")
    pathlib.Path(vault, ".autoresearch.json").write_text("{}\n")

    print("git rules x WHICH REPO -- the narrowing")
    for cmd in ("git reset --hard HEAD", "git clean -fd",
                "git checkout -- scripts/foo.py", "git restore README.md"):
        check(ALLOW, f"framework: {cmd}", "Bash", fw, command=cmd)
    for cmd in ("git reset --hard HEAD", "git clean -fd", "git restore Handoff.md"):
        check(BLOCK, f"vault: {cmd}", "Bash", vault, command=cmd)

    print("git rules x REACHING INTO a vault from outside it")
    check(BLOCK, "-C into the vault", "Bash", fw,
          command=f"git -C {vault} reset --hard")
    check(BLOCK, "cd then reset", "Bash", fw,
          command=f"cd {vault} && git reset --hard")
    check(BLOCK, "names a vault file outright", "Bash", fw,
          command=f"git checkout -- some/path/{FT}")

    print("git rules x MISSING cwd -- must fail safe, never open a hole")
    check(BLOCK, "no cwd supplied", "Bash", None, command="git reset --hard")

    print("git rules x HARMLESS VARIANTS")
    check(ALLOW, "clean without -f is a preview", "Bash", vault, command="git clean -n")
    check(ALLOW, "restore --staged only unstages", "Bash", vault,
          command=f"git restore --staged {FT}")
    check(ALLOW, "ordinary work", "Bash", vault, command="git commit -m ok && git push")

    print("every rule x QUOTED TEXT -- the class the first suite never crossed")
    check(ALLOW, "reset named in a commit message", "Bash", vault,
          command=f"git commit -m {Q}never git reset --hard{Q}")
    check(ALLOW, "redirect named in a commit message", "Bash", vault,
          command=f"git commit -m {Q}never x {GT} {FT}{Q}")
    check(ALLOW, "redirect named in a grep pattern", "Bash", vault,
          command=f"grep -rn {Q}{GT} {FT}{Q} guides/")

    print("redirect rule x FORM")
    check(BLOCK, "real, spaced", "Bash", vault, command=f"echo x {GT} {FT}")
    check(BLOCK, "real, attached", "Bash", vault, command=f"echo x {GT}{FT}")
    check(BLOCK, "with a file descriptor", "Bash", vault, command=f"echo x 2{GT}{FT}")
    check(ALLOW, "append is not truncation", "Bash", vault, command=f"echo x {GT}{GT} {FT}")
    check(ALLOW, "redirect to a non-vault path", "Bash", vault,
          command=f"echo x {GT} /tmp/scratch.txt")

    print("vault-Markdown rules")
    check(BLOCK, "rm of vault Markdown", "Bash", vault, command=f"rm -f {FT}")
    check(BLOCK, "in-place sed", "Bash", vault, command=f"sed -i .bak s/a/b/ {FT}")
    check(ALLOW, "read-only sed", "Bash", vault, command=f"sed -n 1,5p {FT}")

    print("store-owned registers x Edit/Write")
    check(BLOCK, "Edit Research_Log", "Edit", fw, file_path="v/Research_" + "Log.md")
    check(BLOCK, "Edit a question shard", "Edit", fw,
          file_path="v/Open_" + "Questions_Method.md")
    check(BLOCK, "Write the generated index", "Write", fw,
          file_path="v/Open_" + "Questions_Index.md")
    check(ALLOW, "Edit a tree file", "Edit", fw, file_path="v/" + FT)
    check(ALLOW, "Edit the resolved store (archiver-written)", "Edit", fw,
          file_path="v/Open_" + "Questions_Resolved.md")
    check(ALLOW, "Edit the handoff", "Edit", fw, file_path="v/Handoff.md")

    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print("  -", f)
        sys.exit(1)
    print("\nall pinned cases pass")


if __name__ == "__main__":
    main()
