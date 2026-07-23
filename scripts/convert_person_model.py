#!/usr/bin/env python3
"""convert_person_model.py — convert a vault between the two person models, and
prove the conversion round-trips (spec/optional-person-model, Spec 04c).

The two models encode the SAME PersonRecords (see person_store):
  - "file"      : one `type: person` Markdown file per person.
  - "narrative" : many people per `Family_Tree*.md`, each a `- meta:` entry.

This tool reads a source vault with one backend and writes the other model's files
into a destination directory. Because both backends yield/consume the common
PersonRecord, a source -> other -> source round trip is IDENTITY on the modeled
record fields — which is the safety guarantee that makes adopting the narrative
model reversible.

Losslessness (staged, spec Spec 04):
  - LOSSLESS on every MODELED field: id, name, born/died (verbatim), generation,
    evidence_tier, profile_status, life_status, external ids (fs/wt/anc),
    parents/spouse/flags (the '?' marker preserved). FileBackend now writes the
    external-id keys, so narrative->file keeps them even though the human-facing
    file TEMPLATE doesn't advertise them yet (a separate docs PR).
  - LOSSLESS on `sources` too (Spec 04c refinement): NarrativeBackend.iter_people
    now parses each entry's `**Sources**` bullet (structured sub-bullets AND the
    legacy flat form), and both writers re-emit them, so the record SET of source
    strings round-trips. `--check` reports any source-set mismatch alongside field
    mismatches. (File LAYOUT and non-vocabulary frontmatter like `family:`/`created:`
    are not round-trip-significant — identity is the PersonRecord, not the bytes.)

Usage:
    convert_person_model.py --check [--vault V]         # round-trip proof (both directions if possible)
    convert_person_model.py --from narrative --to file --src V --dst D [--apply]
Default is DRY-RUN (reports counts); --apply writes files. Idempotent: the same
input produces byte-identical output.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config
import person_store as ps

MODELS = ("file", "narrative")


# --------------------------------------------------------------------------- #
# read / write a specific model (bypassing the vault's configured backend)
# --------------------------------------------------------------------------- #
def read_as(vault, model):
    backend = ps.NarrativeBackend if model == "narrative" else ps.FileBackend
    return list(backend.iter_people(vault))


def _safe_basename(record):
    base = re.sub(r"[^\w\-]+", "_", (record.name or record.id or "person").strip()).strip("_")
    return f"{base}__{record.id}" if record.id else base


def write_file_model(dst, records, apply=False):
    """Write one `type: person` file per record into dst. Returns the file count."""
    os.makedirs(dst, exist_ok=True)
    for r in records:
        content = ps._render_new_person(r)
        if apply:
            with open(os.path.join(dst, _safe_basename(r) + ".md"), "w", encoding="utf-8") as fh:
                fh.write(content)
    return len(records)


UNDET = 10 ** 9  # sort key for records with no generation (they go last)


def _header_paren(r):
    bits = []
    if r.born:
        bits.append(f"b. {r.born}")
    if r.died:
        bits.append(f"d. {r.died}")
    return "; ".join(bits)


def _narrative_entry(r):
    paren = _header_paren(r)
    name = r.name or r.id
    if paren:
        header = f"**{name}** ({paren})"
    elif r.name and "(" in r.name:
        # The name itself contains a parenthetical (e.g. a placename) and there are
        # no vitals. Emit an EMPTY vitals paren so the reader's legacy
        # "vitals swallowed by the bold name" fallback doesn't misread the name's
        # own paren as born/died. Without this shield, such entries gain a spurious
        # year on round-trip.
        header = f"**{name}** ()"
    else:
        header = f"**{name}**"
    out = [header, ps._emit_meta_line(ps._record_to_meta(r))]
    if r.sources:
        out.append("- **Sources**")
        out.extend(f"  - {s}" for s in r.sources)
    return "\n".join(out) + "\n"


def write_narrative_model(dst, records, apply=False, filename="Family_Tree_Converted.md"):
    """Write all records into ONE gen-sorted Family_Tree file. Layout is not
    round-trip-significant (identity is on PersonRecord), so a single file is fine."""
    os.makedirs(dst, exist_ok=True)
    by_gen = {}
    for r in records:
        by_gen.setdefault(r.generation if r.generation is not None else UNDET, []).append(r)
    out = ["---", "type: family_tree", "---", ""]
    for gen in sorted(by_gen):
        out.append(f"### Generation {gen}" if gen != UNDET else "### Generation (undetermined)")
        out.append("")
        for r in by_gen[gen]:
            out.append(_narrative_entry(r).rstrip("\n"))
            out.append("")
    content = "\n".join(out)
    if apply:
        with open(os.path.join(dst, filename), "w", encoding="utf-8") as fh:
            fh.write(content)
    return len(records)


def write_model(dst, model, records, apply=False):
    if model == "file":
        return write_file_model(dst, records, apply)
    return write_narrative_model(dst, records, apply)


# --------------------------------------------------------------------------- #
# round-trip proof
# --------------------------------------------------------------------------- #
def _src_set(sources):
    return frozenset(str(s).strip() for s in (sources or []))


def roundtrip(src_vault, src_model):
    """src -> other -> src. Compares via full PersonRecord equality (sources
    included, now that NarrativeBackend captures them), so the guarantee is
    machine-checkable and covers EVERY modeled field."""
    other = "file" if src_model == "narrative" else "narrative"
    A = read_as(src_vault, src_model)
    t1 = tempfile.mkdtemp()
    t2 = tempfile.mkdtemp()
    write_model(t1, other, A, apply=True)
    B = read_as(t1, other)
    write_model(t2, src_model, B, apply=True)
    A3 = read_as(t2, src_model)

    a_by = {r.id: r for r in A if r.id}
    z_by = {r.id: r for r in A3 if r.id}
    id_match = set(a_by) == set(z_by)
    common = [pid for pid in a_by if pid in z_by]
    mism = [pid for pid in common if a_by[pid] != z_by[pid]]
    src_mism = [pid for pid in common if _src_set(a_by[pid].sources) != _src_set(z_by[pid].sources)]
    return {
        "src_model": src_model, "other_model": other,
        "n_src": len(A), "n_mid": len(B), "n_back": len(A3),
        "id_sets_equal": id_match,
        "modeled_mismatches": mism,
        "source_mismatches": src_mism,
        "records_with_sources": sum(1 for r in A if r.sources),
        "ok": id_match and not mism,
        "tmp": (t1, t2),
    }


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Convert a vault between person models; prove round-trip.")
    ap.add_argument("--check", action="store_true", help="Round-trip proof for the vault's configured model.")
    ap.add_argument("--from", dest="src_model", choices=MODELS, help="Source model (convert mode).")
    ap.add_argument("--to", dest="dst_model", choices=MODELS, help="Destination model (convert mode).")
    ap.add_argument("--src", help="Source vault dir (default: resolved vault).")
    ap.add_argument("--dst", help="Destination dir for converted files (convert mode).")
    ap.add_argument("--vault", help="Vault for --check (default: resolved vault).")
    ap.add_argument("--apply", action="store_true", help="Write files (default: dry-run).")
    args = ap.parse_args()

    if args.check:
        vault = vault_config.resolve_vault(args.vault or args.src)
        model = vault_config.get_person_model(vault)
        res = roundtrip(vault, model)
        print(f"round-trip {res['src_model']} -> {res['other_model']} -> {res['src_model']}")
        print(f"  records: {res['n_src']} -> {res['n_mid']} -> {res['n_back']}")
        print(f"  id sets equal:       {res['id_sets_equal']}")
        print(f"  field mismatches:    {len(res['modeled_mismatches'])}")
        print(f"  source mismatches:   {len(res['source_mismatches'])} "
              f"(of {res['records_with_sources']} source-bearing records)")
        print(f"  RESULT: {'LOSSLESS' if res['ok'] else 'MISMATCH'}")
        return 0 if res["ok"] else 1

    if not (args.src_model and args.dst_model and args.dst):
        ap.error("convert mode needs --from, --to, and --dst (or use --check)")
    if args.src_model == args.dst_model:
        ap.error("--from and --to are the same model")
    src = vault_config.resolve_vault(args.src)
    records = read_as(src, args.src_model)
    n = write_model(args.dst, args.dst_model, records, apply=args.apply)
    mode = "wrote" if args.apply else "would write"
    print(f"{mode} {n} records: {args.src_model} -> {args.dst_model} into {args.dst}"
          + ("" if args.apply else "  (dry-run; pass --apply)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
