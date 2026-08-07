#!/usr/bin/env python3
"""Pin the `fs_probed` / `route` grammar (Open_Questions Q157 + deferred_decisions 51).

The pair exists because the vault could say "this person cannot be sourced"
(`structural_gap`) but not "this person CAN be sourced, just not on FamilySearch"
-- so six people whose records demonstrably exist sat in an opaque `pids`
enumeration, and the two structural ROTATE arms re-probed FamilySearch for 355
people it will never index (hit rates 0.15 / 0.17 against 0.43-0.48 elsewhere).

Negative controls are the point of this file: a reader that accepts too much is
how a declaration silently starts counting.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import person_store as ps  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}"
          + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(label)


def meta(inner):
    return "- meta: {id: P-0XAMP1, " + inner + "}"


print("fs_probed -- accepts an ISO date, and NOTHING else")
check("plain ISO date", ps.fs_probed(meta("fs_probed: 2026-08-03")), "2026-08-03")
check("quoted ISO date", ps.fs_probed(meta("fs_probed: '2026-08-03'")), "2026-08-03")
# the vault writes GEDCOM dates everywhere; an undated negative is what this key exists to fix,
# so a GEDCOM-shaped value must NOT quietly pass as a date
check("GEDCOM date rejected", ps.fs_probed(meta("fs_probed: 3 AUG 2026")), None)
check("year only rejected", ps.fs_probed(meta("fs_probed: 2026")), None)
check("bare word rejected", ps.fs_probed(meta("fs_probed: yes")), None)
check("absent key", ps.fs_probed(meta("route: metryki")), None)

print("\nroute -- a slug, and unrecognised slugs are RETURNED not dropped")
check("registered host id", ps.route(meta("route: metryki")), "metryki")
check("archive slug", ps.route(meta("route: como-diocesan")), "como-diocesan")
check("uppercase folded", ps.route(meta("route: AS-Sondrio")), "as-sondrio")
# open vocabulary: an unknown slug must survive, or a declaration silently fails.
# This is deliberately the OPPOSITE of adjudicated_why_values, whose vocabulary is closed.
check("unknown slug survives", ps.route(meta("route: archivio-di-narnia")), "archivio-di-narnia")
# ...but shape is enforced, so prose cannot become a route
check("quoted phrase rejected", ps.route(meta("route: 'Como Diocesan Archive'")), None)
check("single char rejected", ps.route(meta("route: x")), None)
check("absent key", ps.route(meta("fs_probed: 2026-08-03")), None)

print("\nthe two keys are INDEPENDENT -- each is meaningful alone")
check("probed without route", ps.fs_probed(meta("fs_probed: 2026-08-03")), "2026-08-03")
check("route without probed", ps.route(meta("route: jri")), "jri")

print("\nnon-meta input is refused rather than guessed at")
check("prose line", ps.route("- Some bullet mentioning route: metryki"), None)
check("legacy `;` meta form", ps.route("- meta: id: P-0XAMP1; route: metryki"), None)
check("empty string", ps.fs_probed(""), None)

print("\nset_meta_key round-trip (the WRITE side must not duplicate a key)")
line = meta("fs: none")
line = ps.set_meta_key(line, "fs_probed", "2026-08-03")
line = ps.set_meta_key(line, "route", "como-diocesan")
check("round-trips probed", ps.fs_probed(line), "2026-08-03")
check("round-trips route", ps.route(line), "como-diocesan")
check("no duplicate key", line.count("route:"), 1)
# replacing in place, not prepending -- a duplicated key is valid YAML and LAST WINS,
# which is how deferred_decisions 25 silently discarded a banked PID
line2 = ps.set_meta_key(line, "route", "as-sondrio")
check("replaced in place", ps.route(line2), "as-sondrio")
check("still one key", line2.count("route:"), 1)
check("sibling key preserved", "fs: none" in line2, True)

print()
if FAILED:
    print(f"{len(FAILED)} FAILED: {FAILED}")
    sys.exit(1)
print("all route-declaration checks passed")
