#!/usr/bin/env python3
"""Regression tests for the batch FamilySearch Sources reader (23 NOV 2026).

Runnable with no test framework: `python3 test_fs_sources_reader.py` (exit 0 = pass).

Two halves:
  1. `harvest_sources.screen_title` / `--screen-titles`: the reader hands its
     collection titles to Python rather than re-implementing the policy screens
     in the browser, so the screens keep ONE home.
  2. `fs_sources_reader.js` formatting, run under node when node is installed
     (skipped, and said so, when it is not). The network half cannot be tested
     offline (the COUNT MISMATCH instrument check lives there, and was verified
     live on 23 NOV 2026); what IS pinned here is the grouping and the
     deduplication of a record attached several times, which is where a raw
     attachment count overstates a person's own records.

Fixture names are placeholders.
"""
import json
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import harvest_sources as hs  # noqa: E402

FAILS = []


def check(name, cond):
    if not cond:
        FAILS.append(name)
        print("FAIL", name)


# --- 1. screen_title -----------------------------------------------------------
check("memorial title screened", "memorial" in hs.screen_title("U.S., Find A Grave Index, 1600s-Current"))
check("wikipedia is limb d", "reference-d" in hs.screen_title("Wikipedia"))
check("record collection trips nothing", hs.screen_title("England, Births and Christenings, 1538-1975") == [])
check("empty title trips nothing", hs.screen_title("") == [])

env = dict(os.environ)
env.setdefault("AUTORESEARCH_VAULT", os.path.join(SCRIPT_DIR, "..", "fixtures", "minimal-vault"))
r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "harvest_sources.py"), "--screen-titles"],
                   input="Find a Grave Index\n\nEngland, Births and Christenings, 1538-1975\n",
                   capture_output=True, text=True, env=env)
check("--screen-titles exits 0", r.returncode == 0)
check("--screen-titles labels memorial", any(l.startswith("memorial") and "Find a Grave" in l for l in r.stdout.splitlines()))
check("--screen-titles counts non-blank lines", "SCREENED 2 title(s)" in r.stdout)

# --- 2. the JS formatter, under node ------------------------------------------
NODE = shutil.which("node")
if not NODE:
    print("SKIP fs_sources_reader.js formatting: node not installed")
else:
    person = {
        "pid": "AAAA-AAA", "name": "John Example", "lifespan": "1606-1682", "status": "ok",
        "cardSourceCount": 6, "refIds": 6, "missingIds": [], "rejectedHints": [], "hints": [],
        "sources": [
            {"id": "S1", "title": 'John Exampel, "England, Births and Christenings, 1538-1975"',
             "uri": "https://familysearch.org/ark:/61903/1:1:AAAA-111", "event": {"year": "1606", "type": "Christening"}},
            {"id": "S2", "title": 'John Exampel, "England, Births and Christenings, 1538-1975"',
             "uri": "https://familysearch.org/ark:/61903/1:1:AAAA-111", "event": {"year": "1606", "type": "Christening"}},
            {"id": "S3", "title": 'John Example in entry for Mary Example, "Massachusetts Births"',
             "uri": "https://familysearch.org/ark:/61903/1:1:AAAA-222", "event": {"year": "1640"}},
            {"id": "S4", "title": 'Lucy Example, "Massachusetts Births"',
             "uri": "https://familysearch.org/ark:/61903/1:1:AAAA-333", "event": {"year": "1642"}},
            {"id": "S5", "title": "U.S., Find A Grave Index", "uri": "https://example.org/rec/2", "event": {}},
            {"id": "S6", "title": "Some Book p. 4", "uri": "", "event": {}},
        ],
    }
    js = """
global.window = global; global.document = {};
require(%s);
const p = JSON.parse(process.argv[1]);
const out = {readAt: 'T', aborted: null, people: [p]};
console.log(JSON.stringify({text: fsSourcesFormat(p), pages: fsSourcesPaginate(out)}));
""" % json.dumps(os.path.join(SCRIPT_DIR, "fs_sources_reader.js"))
    r = subprocess.run([NODE, "-e", js, json.dumps(person)], capture_output=True, text=True)
    check("node ran the reader", r.returncode == 0)
    if r.returncode == 0:
        res = json.loads(r.stdout)
        t = res["text"]
        check("spelling variant groups as OWN", " OWN (1)" in t and "AAAA-111" in t.split(" NAMED-IN")[0])
        check("double attachment is ONE record", "src S1,S2  (attached 2x: ONE record)" in t)
        check("persona in a relative's entry is NAMED-IN", " NAMED-IN (1)" in t)
        check("a different persona is OTHER PERSONA", " OTHER PERSONA (1)" in t and "Lucy Example" in t)
        check("collection-only title is NO PERSONA", " NO PERSONA IN TITLE (1)" in t)
        check("no uri is NO RECORD LINK", " NO RECORD LINK (1)" in t)
        check("attachments vs distinct locators", "6 attachments = 5 distinct locators" in t)
        check("title list feeds --screen-titles", "--screen-titles" in res["pages"][-1] and "Massachusetts Births" in res["pages"][-1])

if FAILS:
    print(f"{len(FAILS)} failure(s)")
    sys.exit(1)
print("test_fs_sources_reader: ok")
