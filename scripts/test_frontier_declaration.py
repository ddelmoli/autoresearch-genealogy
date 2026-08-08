#!/usr/bin/env python3
"""Pin the frontier DECLARED grammar: there are NO "effort" stops.

** OPERATOR RULING, 07 AUG 2026. ** A DECLARED row means the ANCESTRY stops here on
some authority. It does NOT mean nobody has got round to it yet. Those are opposite
states, and the vault had been recording both in the same field:

  - a TERMINUS is about ANCESTRY  -- no cited authority carries the line further
  - a STOP     is about EFFORT    -- the work is simply undone

The second is a research to-do, which is exactly what SILENT is for. Measured at the
ruling: **39 of 327 declared rows rested on effort language ALONE** and became SILENT.

Negative controls are the point of this file. A false SILENT merely nags; a false
DECLARED **removes a real row from the EXPAND pool permanently and silently**, and
nothing ever re-examines it -- two were minted by accident in a single sitting
(`deferred_decisions` 55), one of them by a bullet reading "Bank, do not wire from
the tree", which is a statement about METHOD and closed a frontier row.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import extension_frontier as EF  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}"
          + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(label)


def declares(text):
    return bool(EF.DECLARED_RE.search(text))


print("EFFORT language must NOT declare (the ruling):")
for phrase in [
    "Gen 39+ NOT WORKED -- deliberate stop.",
    "NOT EXTENDED, DELIBERATELY (recorded 23 JUL 2026).",
    "This line is not yet worked.",
    "deliberate stop pending a Cawley read",
    "Bank, do not wire from the tree -- an FS couple is an assertion.",
    "Do not adopt a Widukind descent without reading the source.",
    "do not extend above him until the charter is read",
    # `brick wall` dropped 07 AUG 2026 -- slang for "I cannot get past this", which is
    # a statement about the SEARCHER. 21 rows declared on it alone.
    "Parents: Unknown. Brick wall.",
    "Bermuda records not accessible online. Confirmed brick wall.",
]:
    check(f"effort: {phrase[:52]!r}", declares(phrase), False)

print()
print("ANCESTRY claims must STILL declare (a real terminus is not weakened):")
for phrase in [
    "RURIKID TERMINUS (semi-legendary).",
    "TERMINUS -- this is the documented top of Royal line D.",
    "His parentage is unknown per the sources consulted.",
    "Parentage not given by Cawley.",
    "her parentage is not securely established",
    "The descent above him is legendary.",
    "reliability ceiling for this branch",
    "his origin is unknown",
]:
    check(f"ancestry: {phrase[:52]!r}", declares(phrase), True)

print()
print("The explicit marker is the unambiguous form and must always declare:")
check("FRONTIER DECLARATION 03 AUG 2026", declares("FRONTIER DECLARATION 03 AUG 2026"), True)
check("lowercase marker", declares("frontier declaration 03 aug 2026"), True)

print()
print("Plain prose must not declare (guards against over-broad matching):")
for phrase in [
    "Father of Mary Leavitt, who married Elisha Vining Sr.",
    "A cooper, resident on North St. near the harbour.",
    "Created Earl of Lincoln 1232.",
    "His parents are named on his 1762 marriage register.",
    "",
]:
    check(f"plain: {phrase[:52]!r}", declares(phrase), False)

print()
print("The two phrasings that tripped deferred 55 in the wild:")
# Heinrich I: a METHOD statement that closed his frontier row. Now inert.
check("'Bank, do not wire from the tree' is inert",
      declares("Bank, do not wire from the tree -- the edge waits on Cawley."), False)
# Reginlind: an ancestry claim about an OPEN state. STILL declares -- the residual
# hazard of deferred 55, which this ruling narrows but does not remove. Pinned so the
# limit is visible rather than assumed.
check("'her parentage is unknown' still declares (residual 55 hazard)",
      declares("Her own parentage is unknown per the sources consulted."), True)

print()
print("RESIDUAL (deferred 57): `no parents recorded` still declares even with an")
print("effort qualifier beside it, because \"recorded\" means both \"in the record\"")
print("and \"in what I searched\" and no regex separates them:")
check("'No parents recorded in free sources ... Brick wall for now' still declares",
      declares("No parents recorded in free sources accessible here. Brick wall for now."), True)

print()
print("`backed` is scoped to the DECLARING BULLET, not the whole entry:")
# The defect this pins: an entry that cites Cawley for something unrelated used to
# make a BARE declaration read as "backed". Entry-scope reported 0 unbacked rows
# across the whole vault; bullet-scope reports 29.
entry_with_unrelated_source = "\n".join([
    "**Someone** (b. 1700)",
    "- meta: {id: P-000001, generation: 12}",
    "- His marriage is in the Cawley Medlands ENGLAND chapter and the parish register.",
    "- Parentage unknown.",
])
decl = EF.declaring_lines(entry_with_unrelated_source)
check("declaring_lines finds exactly the declaring bullet", len(decl), 1)
check("...and it is the bare one", "Parentage unknown" in decl[0], True)
check("bare declaration reads UNBACKED even though the entry cites Cawley",
      any(EF.BACKED_RE.search(l) for l in decl), False)

entry_backed_in_place = "\n".join([
    "**Someone** (b. 1700)",
    "- meta: {id: P-000002, generation: 12}",
    "- TERMINUS: parentage not given by Cawley, Medlands ENGLAND ch. 3.",
])
check("declaration that names its authority IN the bullet reads BACKED",
      any(EF.BACKED_RE.search(l) for l in EF.declaring_lines(entry_backed_in_place)), True)

# route_digest blockquotes mirror entry text at the head of every lineage file; if
# they counted, one person's declaration would be credited to the whole shard.
quoted = "> - TERMINUS: parentage not given by Cawley."
check("blockquoted mirror is not a declaring line", EF.declaring_lines(quoted), [])

print()
if FAILED:
    print(f"{len(FAILED)} FAILED: {FAILED}")
    sys.exit(1)
print("all frontier-declaration checks passed")
