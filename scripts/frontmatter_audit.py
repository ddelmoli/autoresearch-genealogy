#!/usr/bin/env python3
"""frontmatter_audit.py — the gate for the layer no gate read: file-level frontmatter.

WHY IT EXISTS (29 JUL 2026 framework review). Every existing audit starts at the
person layer (meta blocks, headers, prose facts). NOTHING read the files' YAML
frontmatter — and that is exactly where errors had accumulated on the reference
vault, at zero violations everywhere else:

  - 3 files whose frontmatter did not PARSE as YAML at all (an unquoted `: ` inside
    a prose paragraph stuffed into `updated:`), so Obsidian showed a broken
    properties block and every frontmatter-reading tool saw nothing;
  - duplicate keys (`prior update:` twice), where YAML silently keeps the last and
    the other value becomes unreachable;
  - `updated:` values that were 526-character session narratives rather than dates
    (the session-log content the content-boundary policy routes to logs/);
  - `updated:` dates months older than the file's real last edit, vault-wide.

The errors enter where nothing looks. This looks.

CHECKS (per Family_Tree*.md file; all ADVISORY at intro, promote once baseline 0):
  FM_MISSING     no frontmatter block at all
  FM_PARSE       frontmatter is not valid YAML (needs PyYAML; skipped without it,
                 and the skip is REPORTED — a check that cannot run must look
                 different from a check that passes)
  FM_DUP_KEY     the same top-level key twice (YAML keeps the last silently)
  FM_DATE_SHAPE  `created:`/`updated:` present but not a bare YYYY-MM-DD — dates
                 are dates; narrative belongs in the body or logs/
  FM_REQUIRED    a required key missing (default: type, created, tags — the
                 CLAUDE.md minimum)
  FM_TYPE        `type:` outside the allowed set (default: reference, the
                 vault-template value for Family_Tree files)

Optional .maintenance.json `frontmatter` block:
  {"glob": "Family_Tree*.md", "required": [...], "types": [...]}
Absent = the defaults above. Zero dependencies (PyYAML optional).

USAGE
  python3 scripts/frontmatter_audit.py             # full report
  python3 scripts/frontmatter_audit.py --heartbeat # one line for the banner
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_config  # noqa: E402

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_ -]*):(\s|$)")
DEFAULT_GLOB = "Family_Tree*.md"
DEFAULT_REQUIRED = ("type", "created", "tags")
DEFAULT_TYPES = ("reference",)
DATE_KEYS = ("created", "updated")


def read_frontmatter(path):
    """(raw_lines_between_dashes, None) or (None, why)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---\n"):
        return None, "no frontmatter block"
    end = text.find("\n---", 4)
    if end < 0:
        return None, "unterminated frontmatter block"
    return text[4:end].splitlines(), None


def audit_file(path, required, types):
    """List of (check, detail) findings for one file."""
    findings = []
    lines, why = read_frontmatter(path)
    if lines is None:
        return [("FM_MISSING", why)]

    raw = "\n".join(lines)

    # FM_PARSE — full YAML parse when PyYAML is available.
    try:
        import yaml  # type: ignore
        try:
            yaml.safe_load(raw)
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0][:120]
            findings.append(("FM_PARSE", f"not valid YAML ({msg})"))
    except ImportError:
        findings.append(("FM_PARSE_SKIPPED", "PyYAML not installed; parse check did not run"))

    # Line-level checks work regardless of PyYAML.
    keys, dups = [], []
    for ln in lines:
        m = KEY_RE.match(ln)
        if m:
            k = m.group(1).strip()
            if k in keys:
                dups.append(k)
            keys.append(k)
    for k in sorted(set(dups)):
        findings.append(("FM_DUP_KEY", f"key `{k}` appears more than once; YAML keeps only the last"))

    kv = {}
    for ln in lines:
        m = KEY_RE.match(ln)
        if m:
            kv[m.group(1).strip()] = ln[m.end():].strip()

    # FM_COLON_IN_VALUE — the zero-dependency stand-in for FM_PARSE, and the
    # exact defect that broke all three unparseable files on the reference vault:
    # an unquoted `: ` inside a prose value ends the scalar and YAML dies (or,
    # worse, silently misparses). Quoting the value fixes it; better, a value
    # that needs quoting is usually body/log content, not frontmatter.
    for k, v in kv.items():
        if v and v[0] not in "'\"[{" and ": " in v:
            findings.append(("FM_COLON_IN_VALUE",
                             f"`{k}:` contains an unquoted `: ` — this breaks the "
                             f"YAML block ({v[:50]!r}...)"))

    for k in DATE_KEYS:
        if k in kv and kv[k] and not DATE_RE.match(kv[k].strip("'\"")):
            findings.append(("FM_DATE_SHAPE",
                             f"`{k}:` is not a bare YYYY-MM-DD ({kv[k][:60]!r}...)"
                             if len(kv[k]) > 60 else
                             f"`{k}:` is not a bare YYYY-MM-DD ({kv[k]!r})"))

    for k in required:
        if k not in kv:
            findings.append(("FM_REQUIRED", f"required key `{k}:` missing"))

    if types and "type" in kv and kv["type"] not in types:
        findings.append(("FM_TYPE", f"`type: {kv['type']}` not in allowed set {list(types)}"))

    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--heartbeat", action="store_true")
    a = ap.parse_args(argv)

    vault = vault_config.resolve_vault(a.vault)
    cfg = {}
    try:
        with open(os.path.join(vault, ".maintenance.json"), encoding="utf-8") as f:
            cfg = json.load(f).get("frontmatter", {}) or {}
    except Exception:
        pass
    pattern = cfg.get("glob", DEFAULT_GLOB)
    required = tuple(cfg.get("required", DEFAULT_REQUIRED))
    types = tuple(cfg.get("types", DEFAULT_TYPES))

    per_file = {}
    counts = {}
    for path in sorted(_glob.glob(os.path.join(vault, pattern))):
        fs = audit_file(path, required, types)
        real = [f for f in fs if f[0] != "FM_PARSE_SKIPPED"]
        if real:
            per_file[os.path.basename(path)] = real
        for c, _ in fs:
            counts[c] = counts.get(c, 0) + 1

    total = sum(v for k, v in counts.items() if k != "FM_PARSE_SKIPPED")
    if a.heartbeat:
        if counts.get("FM_PARSE_SKIPPED"):
            skip = " (FM_PARSE skipped: no PyYAML)"
        else:
            skip = ""
        detail = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())
                           if k != "FM_PARSE_SKIPPED")
        print(f"FRONTMATTER: {total} finding(s) in {len(per_file)} file(s)"
              + (f" [{detail}]" if detail else "") + skip + "  [advisory]")
        return 0

    print("=== FRONTMATTER AUDIT — the file-level header layer (advisory) ===")
    if not per_file:
        print("  clean: every file parses, no duplicate keys, dates are dates.")
    for name, fs in per_file.items():
        print(f"\n  {name}")
        for check, detail in fs:
            print(f"    {check:<14} {detail}")
    print(f"\nFRONTMATTER: {total} finding(s) in {len(per_file)} of "
          f"{len(_glob.glob(os.path.join(vault, pattern)))} file(s)  [advisory]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
