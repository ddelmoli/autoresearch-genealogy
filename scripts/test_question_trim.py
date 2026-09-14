#!/usr/bin/env python3
"""Pin `question_store --trim`: the register's first writer that SHRINKS a block.

WHY THE OPERATION EXISTS. `question_audit` reports BIG_BLOCK for a live block over
15 KB and names the remedy — current state and resolver stay, dated chronology moves
to `logs/`. Every writer this module had (`--new`, `--append`, `--resolve`, `--move`)
creates or grows a block; nothing shrank one. So the remedy's only route was the hand
splice into a 20-175 KB file that the module exists to forbid, and sixteen blocks
accreted past the cap while every hard gate read 0. **A register with writers only
for growth grows.**

WHY THE REFUSALS ARE THE INTERESTING PART. A trim is the one register operation that
destroys text, so each pin below is a way it could destroy the wrong text:

  - dropping a BOUNDARY heading would merge two questions and silently swallow the
    second — the block after it becomes part of the block before it;
  - an ambiguous `--drop-section` would remove a section the caller did not name;
  - trimming away every resolver turns a research task into a complaint, which is
    the one thing the register's own rules say a question must never be;
  - a delete with no pointer is indistinguishable from a section nobody wrote.
"""
import os
import re
import subprocess
import sys
import pathlib
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import question_block as QB  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(label)


BLOCK = """# Open Questions — Scratch

### 10. A scratch question (raised 01 JAN 2026, session #1)

**Current state.** One sentence that must survive every trim.

**⏭ WHAT WOULD SETTLE IT:** read the register and report.

### FIRST DATED PASS, 02 JAN 2026 (session #2)

Chronology that duplicates the session log. Line one.
Line two.

### SECOND DATED PASS, 03 JAN 2026 (session #3)

More chronology. Line one.

### 11. A second scratch question (raised 04 JAN 2026, session #4)

**Current state.** This block must never be touched by a trim of Q10.

**⏭ WHAT WOULD SETTLE IT:** stay intact.
"""


def vault(text=BLOCK):
    d = tempfile.mkdtemp()
    open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8").write("{}")
    open(os.path.join(d, "Open_Questions_Scratch.md"), "w", encoding="utf-8").write(text)
    return d


def run(d, *args):
    """Invoke the CLI against the SCRATCH vault.

    ⛔⛔ `AUTORESEARCH_VAULT` MUST BE SCRUBBED FROM THE CHILD ENVIRONMENT, AND THIS
    IS NOT A DETAIL. `vault_config.resolve_vault` resolves the ENV VAR FIRST and the
    `--vault` argument second — that precedence is deliberate and documented. So a
    subprocess test that passes `--vault <scratch>` while the operator's shell
    exports `AUTORESEARCH_VAULT` runs every case, INCLUDING `--apply`, against the
    LIVE VAULT while appearing to be sandboxed.

    This was not hypothetical: the first run of this file did exactly that. It wrote
    nothing only because the live vault's Q10 happens to have no `###` sub-sections,
    so the trim refused before reaching the write — luck, not a safety property. Any
    test that shells out to a MUTATING script needs this scrub.
    """
    env = {k: v for k, v in os.environ.items() if k != "AUTORESEARCH_VAULT"}
    r = subprocess.run([sys.executable, str(HERE / "question_store.py"), "--vault", d, *args],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def live_numbers(d):
    p = os.path.join(d, "Open_Questions_Scratch.md")
    return sorted(h["num"] for _s, _e, h, _l in QB.iter_questions(p))


d = vault()
print("Fixture sanity:")
check("two live questions", live_numbers(d), [10, 11])

print("\n`--sections` lists only the sub-sections, never the boundaries:")
rc, out = run(d, "--sections", "10")
check("exit 0", rc, 0)
check("both dated passes listed", out.count("DATED PASS"), 2)
check("⛔ the NEXT question's boundary is not offered", "A second scratch question" in out, False)

print("\nA dry run writes nothing:")
rc, out = run(d, "--trim", "10", "--drop-section", "FIRST DATED", "--pointer", "logs/x")
check("exit 0", rc, 0)
check("says dry-run", "[dry-run]" in out, True)
check("file untouched", "FIRST DATED PASS" in
      open(os.path.join(d, "Open_Questions_Scratch.md"), encoding="utf-8").read(), True)

print("\n⛔ REFUSALS — each is a way the trim could destroy the wrong text:")
rc, out = run(d, "--trim", "10", "--drop-section", "DATED", "--pointer", "logs/x")
check("an AMBIGUOUS --drop-section is refused", rc != 0 and "matched 2" in out, True)

rc, out = run(d, "--trim", "10", "--drop-section", "A second scratch question",
              "--pointer", "logs/x")
check("⛔ a BOUNDARY heading cannot be dropped", rc != 0 and "matched 0" in out, True)

rc, out = run(d, "--trim", "10", "--drop-section", "FIRST DATED")
check("no --pointer is refused", rc != 0 and "pointer" in out.lower(), True)

rc, out = run(d, "--trim", "10", "--drop-section", "FIRST DATED", "--drop-section",
              "FIRST DATED", "--pointer", "logs/x")
check("the same section named twice is refused", rc != 0, True)

resolver_only = BLOCK.replace("**⏭ WHAT WOULD SETTLE IT:** read the register and report.\n", "")
d2 = vault(resolver_only.replace(
    "### SECOND DATED PASS, 03 JAN 2026 (session #3)\n\nMore chronology. Line one.",
    "### SECOND DATED PASS, 03 JAN 2026 (session #3)\n\n"
    "**⏭ WHAT WOULD SETTLE IT:** the only resolver now lives in here."))
rc, out = run(d2, "--trim", "10", "--drop-section", "SECOND DATED", "--pointer", "logs/x")
check("⛔ trimming away the LAST resolver is refused",
      rc != 0 and "resolver" in out.lower(), True)

print("\nThe apply path — one section out, everything else intact:")
rc, out = run(d, "--trim", "10", "--drop-section", "FIRST DATED", "--pointer",
              "logs/2026-01-02-session-2", "--apply")
text = open(os.path.join(d, "Open_Questions_Scratch.md"), encoding="utf-8").read()
check("exit 0", rc, 0)
# ⚠ Test for the HEADING LINE, not the string: the pointer deliberately QUOTES the
# dropped heading, so a bare substring test fails on the very feature below.
check("the named section's heading line is gone",
      bool(re.search(r"^### FIRST DATED PASS", text, re.M)), False)
check("its body went with it", "Chronology that duplicates" in text, False)
check("the OTHER dated pass survives", "SECOND DATED PASS" in text, True)
check("the head survives", "One sentence that must survive" in text, True)
check("the resolver survives", "WHAT WOULD SETTLE IT" in text, True)
check("⭐ the next question is untouched", "This block must never be touched" in text, True)
check("both questions still parse", live_numbers(d), [10, 11])

print("\n⚠ Nothing is deleted without a pointer, and the pointer is greppable:")
check("a dated trim line is left", bool(re.search(r"\*\*Trimmed \d", text)), True)
check("it names where the narrative went", "logs/2026-01-02-session-2" in text, True)
check("it names the dropped heading", "FIRST DATED PASS" in
      re.search(r"^> \*\*Trimmed.*$", text, re.M).group(0), True)

print("\nA snapshot of the pre-trim file is written:")
snaps = list(pathlib.Path(d, "Open_Questions_Archive").glob("*_pretrim_*.md"))
check("exactly one snapshot", len(snaps), 1)
check("it holds the removed text", "Chronology that duplicates" in
      snaps[0].read_text(encoding="utf-8"), True)

print("\n⛔⛔ `##` SUB-SECTIONS, and a `##` parent that NESTS `###` passes:")
# The live register uses `##` and `###` interchangeably inside a block, and in 23
# blocks a `##` parent holds `###` children, several with no body of their own. Two
# defects shipped with the `##` reader and both are pinned here:
#   (1) every section ended at the next heading of ANY level, so a bodiless `##`
#       parent spanned its heading line alone: dropping it deleted the title and left
#       its children standing under the preceding section, misfiled rather than removed;
#   (2) the pointer label was `heading[4:]`, right for `### ` and one character too
#       many for `## `, so the greppable record of the trim misnamed what it removed.
NESTED = """# Open Questions — Scratch

### 20. A nested scratch question (raised 01 JAN 2026, session #1)

**Current state.** One sentence that must survive every trim.

**⏭ WHAT WOULD SETTLE IT:** read the register and report.

## SESSION HISTORY

### PASS ONE, 02 JAN 2026 (session #2)

Nested chronology alpha.

### PASS TWO, 03 JAN 2026 (session #3)

Nested chronology beta.

## CURRENT READING

A later `##` section that must survive a trim of the one above it.

### 21. A following scratch question (raised 04 JAN 2026, session #4)

**Current state.** This block must never be touched by a trim of Q20.

**⏭ WHAT WOULD SETTLE IT:** stay intact.
"""


def read(dd):
    return open(os.path.join(dd, "Open_Questions_Scratch.md"), encoding="utf-8").read()


d3 = vault(NESTED)
rc, out = run(d3, "--sections", "20")
check("`##` parents and `###` children are all listed", rc == 0 and all(
    t in out for t in ("SESSION HISTORY", "PASS ONE", "PASS TWO", "CURRENT READING")), True)
check("the parent says it overlaps its children", "[contains 2 nested]" in out, True)

rc, out = run(d3, "--trim", "20", "--drop-section", "SESSION HISTORY", "--pointer",
              "logs/x", "--apply")
text = read(d3)
check("exit 0", rc, 0)
check("the `##` heading line is gone", bool(re.search(r"^## SESSION HISTORY", text, re.M)), False)
check("⛔ its NESTED children went with it, not left orphaned",
      ("Nested chronology alpha" in text, "Nested chronology beta" in text), (False, False))
check("⛔ the next `##` section at the same level survives", "must survive a trim" in text, True)
check("the head and resolver survive", ("One sentence that must survive" in text,
                                        "WHAT WOULD SETTLE IT" in text), (True, True))
check("both questions still parse", live_numbers(d3), [20, 21])
ptr = re.search(r"^> \*\*Trimmed.*$", text, re.M).group(0)
check("⭐ the pointer names the `##` heading WHOLE, first letter included",
      '"SESSION HISTORY"' in ptr, True)

d4 = vault(NESTED)
rc, out = run(d4, "--trim", "20", "--drop-section", "PASS ONE", "--pointer", "logs/x", "--apply")
text = read(d4)
check("a single `###` child can be dropped on its own",
      (rc, "Nested chronology alpha" in text), (0, False))
check("its parent heading and sibling stay",
      ("## SESSION HISTORY" in text, "Nested chronology beta" in text), (True, True))

d5 = vault(NESTED)
rc, out = run(d5, "--trim", "20", "--drop-section", "SESSION HISTORY", "--drop-section",
              "PASS ONE", "--pointer", "logs/x", "--apply")
check("naming a child inside a named parent: the pointer lists the parent only",
      (rc, re.search(r"^> \*\*Trimmed.*$", read(d5), re.M).group(0).count("PASS ONE")), (0, 0))

d6 = vault(NESTED.replace("**⏭ WHAT WOULD SETTLE IT:** read the register and report.\n", "")
           .replace("Nested chronology beta.",
                    "**⏭ WHAT WOULD SETTLE IT:** the only resolver, inside a nested child."))
rc, out = run(d6, "--trim", "20", "--drop-section", "SESSION HISTORY", "--pointer", "logs/x",
              "--apply")
check("⛔ a resolver in an UNNAMED child of a dropped parent still blocks the trim",
      (rc != 0 and "resolver" in out.lower(), "the only resolver" in read(d6)), (True, True))

print()
if FAILED:
    print(f"FAILED ({len(FAILED)}): " + "; ".join(FAILED))
    sys.exit(1)
print("All question_store --trim pins pass.")
