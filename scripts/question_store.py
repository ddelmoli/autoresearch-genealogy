#!/usr/bin/env python3
"""question_store.py — the STRUCTURED WRITER for the Open_Questions register.

Create, resolve, and append to question blocks WITHOUT hand-editing the shard
files. Same rule and same reason as `log_session.py` ("append via the script,
NEVER via the Edit tool") and `person_store.set_meta_key`: every write-discipline
incident in the register's history — orphaned write-ups, zombie duplicates,
malformed status slots, wrong-file appends — happened while a session spliced
text into a 20-175 KB markdown file by hand. This tool locates the block through
the shared grammar (`question_block.py`), so a write cannot land outside it.

Operations (all dry-run by default; --apply writes):

  --new --shard SLUG --title T --resolver R [--body-file F] [--session N]
        Mint the next free GLOBAL Q number (live shards + Resolved store), write
        a canonical block at the end of the shard's questions (before the
        Resolved index). Provenance goes in the title parens; the status slot is
        left empty — it belongs to --resolve.
  --resolve QLABEL --status KW [--note TEXT]
        Rewrite the heading of the live block to `… — KW DD MON YYYY (note)` and
        VERIFY the result is archivable (terminal per the shared rule, no
        provenance trap, AND in the shard's `archive_statuses` in the vault's
        .maintenance.json when it has one). Refuses if the block is already
        terminal, or if the number matches more than one live block (a
        duplicate must be repaired, not written through).
  --restatus QLABEL --status KW
        Repair a STRANDED resolution: a terminal heading whose status the
        archive target will not archive. Changes the keyword only; date and
        note are kept.
  --append QLABEL (--text TEXT | --body-file F) [--sub-heading H]
        Insert content at the END of the live block — the write physically
        cannot orphan itself under the wrong question.
  --replace QLABEL --old TEXT --with TEXT [--old TEXT --with TEXT ...]
        Exact-substring replacement INSIDE one live block. Each --old must occur
        exactly once in that block. Refuses to change the question's number or
        its terminal state, to add an em-dash to the heading, to drop a resolver
        line, or to introduce a line that would open a new question block.
  --where QLABEL       locate a question (any state) across every file
  --show QLABEL        print ONE question block, whole, using the shared boundary
  --next-number        print the next free global Q integer

The em-dash is MACHINE-OWNED in headings: a --new title containing one is
refused (the text after the last em-dash is the status slot; provenance and
subtitles go in parens or after a colon).
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_config
import question_block as QB

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def today_str() -> str:
    d = datetime.date.today()
    return f"{d.day:02d} {MONTHS[d.month - 1]} {d.year}"


def parse_qlabel(s: str):
    m = re.fullmatch(r"(\d+)([a-z]?)", s.strip().lstrip("Qq"))
    if not m:
        raise SystemExit(f"not a Q label: {s!r} (expected e.g. 280 or 143a)")
    return int(m.group(1)), m.group(2)


def resolve_shard(vault: str, slug: str) -> str:
    """Map a slug (e.g. 'method', 'colonial-new-england', or a full filename)
    to exactly one live shard path."""
    files = QB.question_files(vault)
    by_base = {os.path.basename(p): p for p in files}
    if slug in by_base:
        return by_base[slug]
    want = re.sub(r"[^a-z0-9]+", "", slug.lower())
    hits = []
    for p in files:
        base = os.path.basename(p)
        stem = re.sub(r"[^a-z0-9]+", "", base[len("Open_Questions"):-len(".md")].lower())
        if stem == want or (want and want in stem):
            hits.append(p)
    if len(hits) == 1:
        return hits[0]
    names = ", ".join(os.path.basename(p) for p in (hits or files))
    raise SystemExit(f"shard {slug!r} is {'ambiguous' if hits else 'unknown'}: {names}")


def archive_statuses_for(vault, path):
    """The status keywords `archive_sections.py` will actually archive for the shard at
    `path`: the `archive_statuses` of its drop-by-status target in the vault's
    `.maintenance.json`. None when the vault has no such config or no target for this
    file, i.e. nothing constrains the status beyond the shared terminal list.

    ⚠ WHY THIS EXISTS (24 SEP 2026): `QB.STATUS_KWS` is the list that decides whether a
    heading is TERMINAL; this is the list that decides whether it gets ARCHIVED, and they
    had drifted. A status in the first and not the second (plain CONFIRMED) was accepted
    by --resolve, read as closed by every liveness check, and never moved by the archiver:
    the question sat stranded in its live shard and --replace could no longer reach it."""
    cfg_path = os.path.join(str(vault), ".maintenance.json")
    if not os.path.exists(cfg_path):
        return None
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    base = os.path.basename(path)
    for t in cfg.get("targets", []):
        if t.get("policy") == "drop-by-status" and t.get("file") == base:
            return list(t.get("archive_statuses", []))
    return None


def _check_archivable(vault, path, status):
    """Refuse a status the archiver will not archive for this shard."""
    allow = archive_statuses_for(vault, path)
    if allow is not None and not QB.matches_terminal(status, allow):
        raise SystemExit(
            f"status {status!r} is terminal but {os.path.basename(path)}'s archive target "
            f"will not archive it, so the question would be stranded in the live shard. "
            f"Use one of: {', '.join(allow)}")


def find_all(vault, num, suffix):
    """Every block (any state) for a number across live shards + the Resolved
    store: [(path, start, end, head)]."""
    out = []
    paths = QB.question_files(vault)
    rf = QB.resolved_file(vault)
    if os.path.exists(rf):
        paths = paths + [rf]
    for p in paths:
        for s, e, h, _lines in QB.iter_questions(p):
            if h["num"] == num and h["suffix"] == suffix:
                out.append((p, s, e, h))
    return out


def _write(path: str, lines, apply: bool, verb: str):
    if not apply:
        print(f"  [dry-run] would {verb} {os.path.basename(path)} — re-run with --apply")
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"  wrote {os.path.basename(path)}")


def op_new(vault, args):
    shard = resolve_shard(vault, args.shard)
    title = args.title.strip()
    if QB.EMDASH in title:
        raise SystemExit("title contains an em-dash — that slot is machine-owned "
                         "(status). Use a colon or parens; provenance is added "
                         "automatically.")
    if not args.resolver and not args.body_file:
        raise SystemExit("--resolver is required (a question without a named resolver "
                         "is a complaint, not a research task). Or supply --body-file "
                         "whose text names one.")
    num = QB.next_free_number(vault)
    prov = f"(raised {today_str()}" + (f", session #{args.session}" if args.session else "") + ")"
    heading = f"### {num}. {title} {prov}"

    body = []
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8").rstrip("\n").split("\n")
    if args.resolver:
        if body:
            body.append("")
        body.append(f"**⏭ WHAT WOULD SETTLE IT:** {args.resolver.strip()}")

    with open(shard, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    # insert after the LAST question block, before the Resolved index / EOF
    blocks = list(QB.split_blocks(lines))
    if blocks:
        at = blocks[-1][1]
    else:
        at = next((i for i, ln in enumerate(lines) if QB.RESOLVED_INDEX.match(ln)),
                  len(lines))
    new_block = [heading, ""] + body + [""]
    out = lines[:at] + new_block + lines[at:]
    print(f"Q{num} -> {os.path.basename(shard)}")
    print(f"  {heading}")
    _write(shard, out, args.apply, f"insert Q{num} into")
    if args.apply:
        print(f"  (regenerate the index: gen_question_index.py --write "
              f"<vault>/Open_Questions_Index.md)")
    return 0


def op_move(vault, args):
    """Move a whole question block from one lineage shard to another (Q286).

    WHY THIS EXISTS. A question filed under the wrong lineage is invisible to the
    sitting equipped to answer it -- the register is triaged by shard, so a Colonial
    question sitting in the Italian register is read by nobody who can advance it.
    Q286 found one that had sat misfiled since the 12 AUG split, and nothing noticed:
    not the archiver, not the index, not question_audit, not the pre-commit hook.

    ⚠ THE POINT IS THAT THIS IS THE ONLY SUPPORTED WAY. Before it existed the only
    option was a hand cut-and-paste between two 100-200 KB markdown files, which is
    the exact operation that orphaned eight write-ups in August. The block is located
    and carried through the shared grammar (`question_block`), so a move cannot drop
    its body or land outside a block boundary.

    ⛔ Refuses on anything ambiguous: no live block, more than one live block for the
    number (a duplicate must be repaired, not moved through), or a no-op self-move.
    """
    num, suffix = parse_qlabel(args.move)
    dest = resolve_shard(vault, args.shard)
    hits = QB.find_live_blocks(vault, num, suffix)
    label = f"Q{num}{suffix}"
    if not hits:
        raise SystemExit(f"{label}: no LIVE block found (already resolved, or wrong number)")
    if len(hits) > 1:
        where = ", ".join(f"{os.path.basename(x[0])}:{x[1]+1}" for x in hits)
        raise SystemExit(f"{label}: {len(hits)} live blocks ({where}) — repair the "
                         f"duplicate first; a move must not pick one silently")
    src, start, end, head, _blines = hits[0]
    if os.path.abspath(src) == os.path.abspath(dest):
        raise SystemExit(f"{label} is already in {os.path.basename(dest)} — nothing to do")

    with open(src, encoding="utf-8") as fh:
        src_lines = fh.read().split("\n")
    block = src_lines[start:end]
    # Trim trailing blanks off the carried block; the insert re-adds exactly one.
    while block and not block[-1].strip():
        block.pop()

    with open(dest, encoding="utf-8") as fh:
        dest_lines = fh.read().split("\n")
    blocks = list(QB.split_blocks(dest_lines))
    at = blocks[-1][1] if blocks else next(
        (i for i, ln in enumerate(dest_lines) if QB.RESOLVED_INDEX.match(ln)), len(dest_lines))

    new_src = src_lines[:start] + src_lines[end:]
    new_dest = dest_lines[:at] + block + [""] + dest_lines[at:]

    print(f"{label}: {os.path.basename(src)}:{start+1} -> {os.path.basename(dest)}:{at+1}")
    print(f"  {head.get('title','')[:130]}")
    print(f"  carrying {len(block)} line(s)")
    _write(src, new_src, args.apply, f"remove {label} from")
    _write(dest, new_dest, args.apply, f"insert {label} into")
    if args.apply:
        print("  (regenerate the index: gen_question_index.py --write "
              "<vault>/Open_Questions_Index.md)")
    return 0


def op_resolve(vault, args):
    num, suffix = parse_qlabel(args.resolve)
    status = args.status.strip().upper()
    if status not in QB.STATUS_KWS:
        raise SystemExit(f"status {status!r} is not terminal; one of: "
                         f"{', '.join(QB.STATUS_KWS)}")
    hits = QB.find_live_blocks(vault, num, suffix)
    if not hits:
        others = find_all(vault, num, suffix)
        where = "; ".join(f"{os.path.basename(p)}:{s+1} ({h['status'] or 'no status'})"
                          for p, s, e, h in others) or "nowhere"
        raise SystemExit(f"no LIVE block for Q{num}{suffix} — found: {where}")
    if len(hits) > 1:
        where = "; ".join(f"{os.path.basename(p)}:{s+1}" for p, s, e, h, _l in hits)
        raise SystemExit(f"Q{num}{suffix} is DUPLICATED across live shards ({where}) — "
                         f"repair the duplicate first; refusing to resolve through it.")
    path, s, _e, h, lines = hits[0]
    _check_archivable(vault, path, status)
    note = f" ({args.note.strip()})" if args.note else ""
    head_line = lines[s].rstrip()
    # An INTERIM status (PARTIALLY_RESOLVED) is provenance once the question is
    # terminal, and provenance belongs in the TITLE PARENS — so fold it there
    # rather than stacking a second status segment behind it. Blind appending
    # would have made Q33 the register's first double-status heading: every
    # existing multi-em-dash heading is a SUBTITLE plus one status, and 14 live
    # questions carry an interim marker that would each have stacked the same way.
    # ⚠ The segment is moved VERBATIM — no re-casing, no unwrapping of its own
    # parens — because the point is to preserve a dated fact, not to tidy it.
    folded = None
    if h["status"] and QB.INTERIM_STATUS_RE.match(h["status"].strip()):
        cut = head_line.rfind(QB.EMDASH)
        folded = head_line[cut + len(QB.EMDASH):].strip()
        head_line = f"{head_line[:cut].rstrip()} ({folded})"
    new_head = f"{head_line} {QB.EMDASH} {status} {today_str()}{note}"
    check = QB.parse_heading(new_head)
    if not check or not check["terminal"] or QB.PROVENANCE_RE.match(check["status"]):
        raise SystemExit(f"internal: rewritten heading is not archivable: {new_head!r}")
    print(f"Q{num}{suffix} in {os.path.basename(path)}:{s+1}")
    print(f"  old: {lines[s][:110]}")
    print(f"  new: {new_head[:110]}")
    if folded:
        print(f"  folded the interim status into the title: ({folded})")
    lines[s] = new_head
    _write(path, lines, args.apply, f"resolve Q{num}{suffix} in")
    if args.apply:
        print("  (archive it: archive_sections.py --apply, or leave for session close)")
    return 0


def op_restatus(vault, args):
    """Repair a STRANDED resolution: a block whose heading is terminal (so every
    liveness check treats it as closed and --replace refuses it) but whose status the
    shard's archive target will not archive. Rewrites the status KEYWORD only; the
    date and note after it are kept verbatim. Refuses anything else: a live block
    (use --resolve), a block the archiver would already take, a tombstone."""
    num, suffix = parse_qlabel(args.restatus)
    status = args.status.strip().upper()
    if status not in QB.STATUS_KWS:
        raise SystemExit(f"status {status!r} is not terminal; one of: "
                         f"{', '.join(QB.STATUS_KWS)}")
    live_files = set(QB.question_files(vault))
    hits = [(p, s, h) for p, s, _e, h in find_all(vault, num, suffix)
            if p in live_files and h["terminal"]
            and not (h["tombstone"] or h["struck"] or h["original"])]
    if len(hits) != 1:
        raise SystemExit(f"need exactly one terminal, un-archived Q{num}{suffix} block in a "
                         f"live shard, found {len(hits)}")
    path, s, h = hits[0]
    allow = archive_statuses_for(vault, path)
    if allow is None:
        raise SystemExit(f"{os.path.basename(path)} has no archive target in "
                         f".maintenance.json, so nothing is stranded to repair")
    if QB.matches_terminal(h["status"], allow):
        raise SystemExit(f"Q{num}{suffix} is not stranded: its status {h['status'][:40]!r} "
                         f"is already archivable")
    _check_archivable(vault, path, status)
    old_kw = next(k for k in QB.STATUS_KWS if QB.matches_terminal(h["status"], [k]))
    lines = open(path, encoding="utf-8").read().split("\n")
    head_line = lines[s].rstrip()
    cut = head_line.rfind(QB.EMDASH)
    tail = h["status"][len(old_kw):]
    new_head = f"{head_line[:cut].rstrip()} {QB.EMDASH} {status}{tail}"
    check = QB.parse_heading(new_head)
    if not check or not check["terminal"] or QB.PROVENANCE_RE.match(check["status"]):
        raise SystemExit(f"internal: rewritten heading is not archivable: {new_head!r}")
    print(f"Q{num}{suffix} in {os.path.basename(path)}:{s+1}")
    print(f"  old: {lines[s][-110:]}")
    print(f"  new: {new_head[-110:]}")
    lines[s] = new_head
    _write(path, lines, args.apply, f"restatus Q{num}{suffix} in")
    return 0


def op_append(vault, args):
    num, suffix = parse_qlabel(args.append)
    text = args.text
    if args.body_file:
        text = Path(args.body_file).read_text(encoding="utf-8")
    if not text or not text.strip():
        raise SystemExit("--append needs --text or --body-file")
    hits = QB.find_live_blocks(vault, num, suffix)
    if len(hits) != 1:
        where = "; ".join(f"{os.path.basename(p)}:{s+1}" for p, s, e, h, _l in hits)
        raise SystemExit(f"need exactly one LIVE Q{num}{suffix} block, found "
                         f"{len(hits)}{' (' + where + ')' if hits else ''}")
    path, s, e, h, lines = hits[0]
    addition = text.rstrip("\n").split("\n")
    if args.sub_heading:
        addition = [f"## {args.sub_heading.strip()}", ""] + addition
    # insert before the block's trailing blank/--- run so the write stays inside it
    t = e
    while t > s + 1 and lines[t - 1].strip() in ("", "---"):
        t -= 1
    out = lines[:t] + [""] + addition + lines[t:]
    print(f"append {len(addition)} line(s) to Q{num}{suffix} "
          f"({os.path.basename(path)}:{t+1})")
    _write(path, out, args.apply, f"append to Q{num}{suffix} in")
    return 0


def _sub_level(ln):
    """2 for a `##` sub-section heading, 3 for `###`, else 0 (boundaries included)."""
    # ⚠ BOTH `##` AND `###` ARE SUB-SECTION HEADINGS INSIDE A BLOCK, and the
    # register uses them interchangeably — measured across the 16 BIG_BLOCK rows,
    # 6 use `###`, 4 use `##`, and 6 use neither. A `###`-only reader covered
    # barely a third of the population it was built for.
    # ⛔ `split_blocks` stops at NO heading but a numbered `###`, so a `##` here
    # is genuinely inside the block and safe to treat as a section.
    if QB.QUESTION_HEAD.match(ln):
        return 0
    if ln.startswith("## "):
        return 2
    if ln.startswith("### "):
        return 3
    return 0


def _subsections(lines, s, e):
    """The `##` / `###` sub-sections INSIDE one question block: [(idx, end, heading)].

    ⛔ A boundary heading (`### N.`) is never a sub-section — dropping one would
    merge two questions and silently destroy the second. `QB.QUESTION_HEAD` is the
    same grammar `split_blocks` uses to find blocks in the first place, so a heading
    cannot be a boundary here and content there.

    ⛔⛔ A SECTION ENDS AT THE NEXT HEADING OF ITS OWN LEVEL OR HIGHER, NOT AT THE NEXT
    HEADING. The live register nests `###` passes under a `##` parent (23 blocks
    measured 13 SEP 2026, several parents with no body of their own). Ending every
    section at the next heading of any level made a `##` parent span only its own
    heading line, so dropping it deleted the title and left its `###` children
    standing under whatever section preceded it: text misfiled, not removed. A
    parent and its children are therefore BOTH listed, and they overlap.
    """
    heads = [i for i in range(s + 1, e) if _sub_level(lines[i])]
    out = []
    for i in heads:
        lvl = _sub_level(lines[i])
        stop = e
        for j in range(i + 1, e):
            if QB.QUESTION_HEAD.match(lines[j]) or 0 < _sub_level(lines[j]) <= lvl:
                stop = j
                break
        out.append((i, stop, lines[i].strip()))
    return out


def _heading_label(heading):
    """The heading text without its `#` marks, whatever the level.

    ⚠ This was `heading[4:]`, which is right for `### ` only: on a `## ` heading it
    ate the first letter, so the pointer — the one greppable record of what a trim
    removed — named a section that never existed.
    """
    return re.sub(r"^#+\s*", "", heading)


def _one_live(vault, label):
    num, suffix = parse_qlabel(label)
    hits = QB.find_live_blocks(vault, num, suffix)
    if len(hits) != 1:
        where = "; ".join(f"{os.path.basename(p)}:{s+1}" for p, s, e, h, _l in hits)
        raise SystemExit(f"need exactly one LIVE Q{num}{suffix} block, found "
                         f"{len(hits)}{' (' + where + ')' if hits else ''}")
    return (num, suffix) + hits[0]


def op_sections(vault, args):
    """List a block's trimmable sub-sections, largest first."""
    num, suffix, path, s, e, h, lines = _one_live(vault, args.sections)
    subs = _subsections(lines, s, e)
    total = sum(len(ln) + 1 for ln in lines[s:e])
    print(f"Q{num}{suffix}  {os.path.basename(path)}:{s+1}-{e}  "
          f"{total/1024:.1f} KB, {len(subs)} sub-section(s)")
    head_kb = (subs[0][0] - s if subs else e - s)
    print(f"  (head: lines {s+1}-{s+head_kb}, "
          f"{sum(len(ln)+1 for ln in lines[s:s+head_kb])/1024:.1f} KB — never trimmed)")
    for i, stop, heading in sorted(subs, key=lambda r: -(r[1] - r[0])):
        kb = sum(len(ln) + 1 for ln in lines[i:stop]) / 1024
        res = " [HOLDS THE RESOLVER]" if any(
            QB.RESOLVER_RE.search(ln) for ln in lines[i:stop]) else ""
        # Parents and children overlap; say so, or the sizes read as additive.
        nested = sum(1 for j, _st, _h in subs if i < j < stop)
        res += f" [contains {nested} nested]" if nested else ""
        print(f"  {kb:6.1f} KB  lines {i+1}-{stop}{res}")
        print(f"            {heading[:96]}")
    return 0


def op_trim(vault, args):
    """Remove whole `##` / `###` sub-sections from a live block, leaving a pointer.

    ⭐⭐ WHY THIS EXISTS. `question_audit` reports BIG_BLOCK for a live block over
    15 KB — session narration accreting in place of current state — and names the
    remedy: current state and resolver stay, dated chronology moves to `logs/`. But
    every writer this module had (`--new`, `--append`, `--resolve`, `--move`) either
    CREATES or GROWS a block. Nothing shrank one, so the only way to do the remedy
    was the hand splice into a 20-175 KB file that this module exists to forbid.
    Sixteen blocks accreted past the cap while every hard gate stayed at 0. A
    register with writers only for growth grows.

    ⚠ NOTHING IS DELETED WITHOUT A POINTER. A snapshot of the whole file is written
    first, and the block keeps a dated line naming every heading removed and where
    the narrative now lives. A section that is simply gone is indistinguishable from
    one nobody wrote.
    """
    num, suffix, path, s, e, h, lines = _one_live(vault, args.trim)
    subs = _subsections(lines, s, e)
    if not subs:
        raise SystemExit(f"Q{num}{suffix} has no `##`/`###` sub-sections to trim")

    chosen = []
    for want in args.drop_section:
        hit = [x for x in subs if want.lower() in x[2].lower()]
        if len(hit) != 1:
            raise SystemExit(
                f"--drop-section {want!r} matched {len(hit)} sub-section(s) in "
                f"Q{num}{suffix}; it must match exactly one. Run --sections Q{num}{suffix} "
                "to see them.")
        if hit[0] in chosen:
            raise SystemExit(f"--drop-section {want!r} named the same section twice")
        chosen.append(hit[0])

    drop = set()
    for i, stop, _hd in chosen:
        drop.update(range(i, stop))
    freed = sum(len(lines[i]) + 1 for i in drop)
    # A `###` named alongside the `##` that contains it is already inside the drop;
    # the pointer names the outermost heading only.
    chosen = [x for x in chosen
              if not any(o is not x and o[0] < x[0] and x[1] <= o[1] for o in chosen)]
    # ⚠ Sections OVERLAP (a `##` parent spans its `###` children), so "kept" is
    # judged by LINE, never by listing the sections not named.
    kept = [x for x in subs if x[0] not in drop]

    # ⛔ The resolver is what makes a question a research task rather than a
    # complaint. Refuse to trim it away even when explicitly named. Judged on the
    # lines that actually survive: a resolver inside a `###` child of a dropped `##`
    # goes with its parent, even though the child itself was not named.
    resolver_lines = [i for i in range(s, e) if QB.RESOLVER_RE.search(lines[i])]
    surviving = [i for i in resolver_lines if i not in drop]
    if resolver_lines and not surviving:
        raise SystemExit(
            f"refusing: the trim would remove every resolver line from Q{num}{suffix}. "
            "Current state and the resolver stay; move the chronology instead.")

    pointer = (f"> **Trimmed {today_str()}**: {len(chosen)} dated sub-section(s) "
               f"removed from this block; the narrative is in {args.pointer}. "
               f"Dropped: " + "; ".join(f'"{_heading_label(hd)[:70]}"'
                                        for _i, _s2, hd in chosen))
    t = e
    while t > s + 1 and lines[t - 1].strip() in ("", "---"):
        t -= 1
    out = [ln for i, ln in enumerate(lines) if i not in drop or i >= t]
    # recompute the insert point in the TRIMMED list
    shift = sum(1 for i in drop if i < t)
    out = out[:t - shift] + ["", pointer] + out[t - shift:]

    before = sum(len(ln) + 1 for ln in lines[s:e])
    print(f"trim Q{num}{suffix} in {os.path.basename(path)}: "
          f"{len(chosen)} section(s), {before/1024:.1f} KB -> "
          f"{(before - freed)/1024:.1f} KB (-{freed/1024:.1f} KB)")
    for _i, _s2, hd in chosen:
        print(f"    drop: {hd[:92]}")
    print(f"    keep: {len(kept)} sub-section(s) + the head")

    if args.apply:
        ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
        snap_dir = Path(vault) / "Open_Questions_Archive"
        snap_dir.mkdir(exist_ok=True)
        snap = snap_dir / f"{Path(path).stem}_pretrim_{ts}.md"
        snap.write_text("\n".join(lines), encoding="utf-8")
        print(f"    snapshot: {snap.relative_to(Path(vault))}")
    _write(path, out, args.apply, f"trim Q{num}{suffix} in")
    return 0


def op_replace(vault, args):
    """Exact-substring replacement inside ONE live block.

    ⭐ WHY THIS EXISTS (16 SEP 2026). The writers could create, grow, resolve,
    move and trim a block, but not correct a token inside one. A question filed
    with a bare FS ARK in a table was then blocked by the bare-ARK gate, and the
    guard (rightly) refused a hand edit of the shard: the only remaining fix was
    to find a way round the guard. A correction is a write like any other, so it
    goes through the same locator as every other write.

    ⚠ The scope is the block, never the file: an --old that occurs once in the
    file but outside the target block is not found. Every refusal below protects
    something another consumer reads: the number (minting and the index), the
    terminal state (archiving), the em-dash (the status slot), the resolver line
    (RESOLVERLESS), and the block boundary (a new `### N.` line would split it).
    """
    num, suffix, path, s, e, h, lines = _one_live(vault, args.replace)
    if not args.old or len(args.old) != len(args.with_text):
        raise SystemExit("--replace needs matching --old/--with pairs")
    block = "\n".join(lines[s:e])
    for old, new in zip(args.old, args.with_text):
        n = block.count(old)
        if n != 1:
            raise SystemExit(f"--old {old[:60]!r} occurs {n} time(s) in Q{num}{suffix}; "
                             "it must occur exactly once")
        block = block.replace(old, new)
    new_lines = block.split("\n")
    h0, h1 = QB.parse_heading(lines[s]), QB.parse_heading(new_lines[0])
    if not h1 or (h1["num"], h1.get("suffix")) != (h0["num"], h0.get("suffix")):
        raise SystemExit("refusing: the replacement changes the question's number")
    if h1["terminal"] != h0["terminal"]:
        raise SystemExit("refusing: the terminal state is --resolve's to change")
    if new_lines[0].count("\u2014") > lines[s].count("\u2014"):
        raise SystemExit("refusing: an added em-dash in the heading moves the status slot")
    if len(list(QB.split_blocks(new_lines))) != 1:
        raise SystemExit("refusing: the replacement would open a new question block "
                         "(judged by the shared boundary rule)")
    had = sum(1 for ln in lines[s:e] if QB.RESOLVER_RE.search(ln))
    has = sum(1 for ln in new_lines if QB.RESOLVER_RE.search(ln))
    if has < had:
        raise SystemExit("refusing: the replacement removes a resolver line")
    out = lines[:s] + new_lines + lines[e:]
    print(f"replace {len(args.old)} substring(s) in Q{num}{suffix} "
          f"({os.path.basename(path)}:{s+1})")
    _write(path, out, args.apply, f"replace in Q{num}{suffix} in")
    return 0


def op_show(vault, args):
    """Print one question block WHOLE, cut by the shared boundary.

    ⚠ THIS EXISTS SO NOTHING ELSE HAS TO PARSE THE REGISTER. The old
    `08-open-question-resolution` prompt extracted a block with an inline
    `awk '/^### 114\\./,/^### 115\\./'` — which assumes questions are contiguous
    and live in one file, and both stopped being true at the 12 AUG lineage
    shard split (Q114's neighbour is in a different shard, so the range ran to
    EOF or matched nothing). A reader that re-implements the boundary is the
    same defect as a writer that does; there is ONE home."""
    num, suffix = parse_qlabel(args.show)
    rows = find_all(vault, num, suffix)
    if not rows:
        print(f"Q{num}{suffix}: not found in any question file")
        return 1
    live = [r for r in rows if QB.is_live(r[3])]
    chosen = live or rows
    for path, s, e, h in chosen:
        state = "LIVE" if QB.is_live(h) else (
            "terminal" if h["terminal"] else
            "tombstone" if h["tombstone"] or h["struck"] else "original")
        print(f"--- {os.path.basename(path)}:{s+1}-{e}  [{state}]")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        print("\n".join(lines[s:e]).rstrip())
    if live and len(rows) > len(live):
        print(f"\n(+{len(rows)-len(live)} non-live block(s) for this number not shown; "
              f"--where lists them)")
    return 0


def op_where(vault, args):
    num, suffix = parse_qlabel(args.where)
    rows = find_all(vault, num, suffix)
    if not rows:
        print(f"Q{num}{suffix}: not found in any question file")
        return 1
    for p, s, e, h in rows:
        state = ("LIVE" if QB.is_live(h) else
                 "terminal" if h["terminal"] else
                 "tombstone" if h["tombstone"] or h["struck"] else "original")
        print(f"Q{num}{suffix}  {os.path.basename(p)}:{s+1}  [{state}]  "
              f"{(h['status'] or h['title'])[:80]}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--new", action="store_true", help="create a question")
    ap.add_argument("--shard", help="target shard for --new (slug or filename)")
    ap.add_argument("--title", help="heading title for --new (no em-dash)")
    ap.add_argument("--resolver", help="what would settle it (required for --new)")
    ap.add_argument("--session", help="session number for the provenance paren")
    ap.add_argument("--resolve", metavar="QLABEL", help="mark terminal, e.g. 280 / 143a")
    ap.add_argument("--status", help="terminal keyword for --resolve / --restatus")
    ap.add_argument("--restatus", metavar="QLABEL",
                    help="repair a STRANDED resolution: change the status keyword of a "
                         "terminal heading the archive target will not archive")
    ap.add_argument("--note", help="parenthetical after the status date")
    ap.add_argument("--append", metavar="QLABEL", help="append content to a live block")
    ap.add_argument("--sub-heading", help="wrap the appended text under '## <H>'")
    ap.add_argument("--text", help="content for --append")
    ap.add_argument("--body-file", help="file holding content for --new/--append")
    ap.add_argument("--move", metavar="QLABEL",
                    help="move a live question block to another lineage shard "
                         "(requires --shard). The ONLY supported way to re-file one.")
    ap.add_argument("--where", metavar="QLABEL", help="locate a question")
    ap.add_argument("--show", metavar="QLABEL",
                    help="print one question block whole (shared boundary; "
                         "prefers the LIVE block when a number has several)")
    ap.add_argument("--sections", metavar="QLABEL",
                    help="list a live block's trimmable `###` sub-sections, largest "
                         "first — what --trim can take")
    ap.add_argument("--trim", metavar="QLABEL",
                    help="remove whole `###` sub-sections from a live block (needs "
                         "--drop-section and --pointer). The BIG_BLOCK remedy.")
    ap.add_argument("--drop-section", action="append", default=[], metavar="TEXT",
                    help="substring identifying one sub-section to drop; repeatable. "
                         "Must match EXACTLY one.")
    ap.add_argument("--pointer", metavar="TEXT",
                    help="where the removed narrative lives (e.g. a logs/ path). "
                         "Required by --trim: nothing is deleted without a pointer.")
    ap.add_argument("--replace", metavar="QLABEL",
                    help="exact-substring replacement inside one live block "
                         "(needs --old/--with pairs)")
    ap.add_argument("--old", action="append", default=[], metavar="TEXT",
                    help="substring to replace; must occur exactly once in the block")
    ap.add_argument("--with", dest="with_text", action="append", default=[],
                    metavar="TEXT", help="replacement for the matching --old")
    ap.add_argument("--next-number", action="store_true")
    args = ap.parse_args()
    vault = vault_config.resolve_vault(args.vault)

    if args.next_number:
        print(QB.next_free_number(vault))
        return 0
    if args.new:
        if not (args.shard and args.title):
            raise SystemExit("--new needs --shard and --title")
        return op_new(vault, args)
    if args.resolve:
        if not args.status:
            raise SystemExit("--resolve needs --status")
        return op_resolve(vault, args)
    if args.restatus:
        if not args.status:
            raise SystemExit("--restatus needs --status")
        return op_restatus(vault, args)
    if args.append:
        return op_append(vault, args)
    if args.move:
        if not args.shard:
            raise SystemExit("--move needs --shard (the destination lineage shard)")
        return op_move(vault, args)
    if args.sections:
        return op_sections(vault, args)
    if args.trim:
        if not args.drop_section:
            raise SystemExit("--trim needs at least one --drop-section")
        if not args.pointer:
            raise SystemExit(
                "--trim needs --pointer naming where the removed narrative lives. "
                "A section that is simply gone is indistinguishable from one nobody "
                "wrote.")
        return op_trim(vault, args)
    if args.replace:
        return op_replace(vault, args)
    if args.show:
        return op_show(vault, args)
    if args.where:
        return op_where(vault, args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
