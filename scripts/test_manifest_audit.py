#!/usr/bin/env python3
"""Pin MANIFEST_EMPTY_HEADING: the POINTER, not the word, is what resolves a heading.

WHY THIS FILE EXISTS. The check's whole value is a discrimination, and the obvious
way to write that discrimination is wrong. A heading emptied by a split is resolved
when it carries a pointer naming where the people went; the tempting test is to
match the word "moved". Measured on the reference vault, the 17 resolved sections
write that pointer at least four different ways, and one of them never says "moved"
at all. The wikilink test scored all 17 identically because it tests what the
remediation actually requires: a destination a reader can follow.

The second pin is the section-extent rule. A Generation heading whose entries live
under `####` subheadings is POPULATED, and a naive "stop at the next heading of any
level" rule reports it empty -- a false positive on a correct file, which is the
expensive direction here: this check's claim is that it has none.
"""
import os
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import manifest_audit as MA  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(label)


ENTRY = ("**Placeholder Ancestor** (b. 1700; d. 1750)\n"
         "- meta: {id: P-TEST01, generation: 9, life_status: deceased}\n")
ENTRY2 = ("**Second Placeholder** (b. 1725; d. 1780)\n"
          "- meta: {id: P-TEST02, generation: 8, life_status: deceased}\n")


def run(body):
    """Write one Family_Tree file into a scratch vault and scan it.

    ⚠ The scratch vault MUST declare `person_model: narrative`. `person_store`
    dispatches on `vault_config.get_person_model`, which defaults to the FILE model
    for a config-less directory -- and the file backend finds no people in a
    `Family_Tree*.md`, so every fixture reads "empty" and every pin passes for the
    wrong reason. That is exactly the flattering direction: the check under test
    reports emptiness, so a backend that sees nothing agrees with it about
    everything.
    """
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, ".autoresearch.json"), "w", encoding="utf-8").write(
            '{"person_model": "narrative"}')
        open(os.path.join(d, "Family_Tree_Scratch.md"), "w", encoding="utf-8").write(body)
        rows = MA.scan(d)
        return [(r["line"], r["pointered"]) for r in rows]


print("A heading with an entry under it is never reported:")
check("populated", run("### Generation 9: Placeholder\n\n" + ENTRY), [])

print("\nA heading with NO entry and NO pointer is a finding:")
check("bare empty", run("### Generation 9: Placeholder\n\n---\n"), [(1, False)])
check("empty then a populated sibling",
      run("### Generation 9: Reserved\n\n### Generation 8: Held\n\n" + ENTRY2),
      [(1, False)])

print("\nA pointer RESOLVES it, however the sentence is worded (all four dialects seen in the vault):")
for label, body in [
    ("heading marker + blockquote",
     "### Generation 9: Placeholder — MOVED\n\n> **MOVED to [[Family_Tree_Other]] on 2026-08-02.**\n"),
    ("date between the verb and the target",
     "### Generation 9: Placeholder — MOVED\n\n> **Moved 2026-07-30** to [[Family_Tree_Other]] to keep this shard small.\n"),
    ("no verb at all, only a signpost",
     "### Generation 9: Placeholder\n\n> Kept as a pointer rather than deleted; the entries are in [[Family_Tree_Other]].\n"),
    ("lowercase split-to",
     "### Generation 9: Placeholder\n\n> split to [[Family_Tree_Other]]\n"),
]:
    check(f"pointered: {label}", run(body), [(1, True)])

print("\n⛔ The word 'moved' WITHOUT a destination does not resolve it")
print("   (a heading that says it is empty but not where to go is still a dead end):")
check("verb, no target", run("### Generation 9: Placeholder — MOVED\n\nMoved out of this file.\n"),
      [(1, False)])

print("\nSection extent: a heading is POPULATED by entries under its subheadings:")
check("entries under a #### subheading",
      run("### Generation 9: Placeholder\n\n#### The cadet branch\n\n" + ENTRY),
      [])
check("a DEEPER Generation heading does not close its parent",
      run("### Generation 9: Placeholder\n\n#### Generation 10: Below\n\n" + ENTRY),
      [])

print("\nA sibling heading at the same level DOES close it:")
check("same-level sibling closes the section",
      run("### Generation 9: Empty\n\n### Generation 8: Populated\n\n" + ENTRY2),
      [(1, False)])

print("\nNon-Generation headings are out of scope entirely:")
check("plain ## section with no entries",
      run("## Collateral stub entries\n\nSome prose, no people.\n"), [])

print()
if FAILED:
    print(f"FAILED ({len(FAILED)}): " + "; ".join(FAILED))
    sys.exit(1)
print("All manifest_audit pins pass.")
