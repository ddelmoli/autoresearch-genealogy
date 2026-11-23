#!/usr/bin/env python3
"""Regression tests for the pre-session sign-in check (23 NOV 2026).

Runnable with no test framework: `python3 test_session_logins.py` (exit 0 = pass).

Pins the parts that fail silently: a probe kind the browser function does not know
(it would answer UNKNOWN forever), a probe expression that is not awaited
(javascript_tool returns an un-awaited async IIFE as `{}`, readable as neither
signed in nor out), and a credential request that would raise one consent prompt
per site instead of one for the batch, or one too long for the password manager to
accept (more than 5 entries). The probe's reading of menus and slow pages is pinned
by its source text here; it was checked against the live sites on 23 NOV 2026. Fixture sites are generic.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import session_logins as sl  # noqa: E402

FAILS = []


def check(name, cond):
    if not cond:
        FAILS.append(name)
        print("FAIL", name)


good = [
    {"id": "a", "label": "Site A", "url": "https://a.example.org/x", "keywords": ["a"]},
    {"id": "b", "label": "Site B", "url": "https://b.example.org/", "keywords": ["b"],
     "probe": {"kind": "fetch_json", "url": "/api/me"}},
    {"id": "c", "label": "Site C", "url": "https://c.example.org/", "keywords": ["c"],
     "probe": {"kind": "cookie", "name": "session"}},
]
check("valid list has no problems", sl.validate(good) == [])
bad = [
    {"id": "a", "url": "https://a.example.org/", "keywords": ["a"], "probe": {"kind": "magic"}},
    {"id": "a", "url": "http://a.example.org/", "keywords": []},
    {"id": "t", "url": "https://t.example.org/", "keywords": ["t"], "probe": {"kind": "text"}},
    {"id": "f", "url": "https://f.example.org/", "keywords": ["f"], "probe": {"kind": "fetch_json", "url": "https://other.example.org/me"}},
]
probs = "\n".join(sl.validate(bad))
for frag in ("not one of", "duplicate id", "url must be https", "keywords", "needs a pattern", "same-origin"):
    check("validate catches: " + frag, frag in probs)

js = sl.probe_js(good[1])
check("probe expression is awaited", js.lstrip().startswith("await (async"))
check("probe spec is embedded", '"kind": "fetch_json"' in js and '"/api/me"' in js)
check("probe never reads a cookie value", "c.split('=')[0]" in js)
check("sign-out in a closed menu counts", "all.find((e) => OUT_TXT.test(label(e)) || OUT_HREF" in js)
check("a visible sign-in blocks the hidden-menu reading", "if (hidden && !signin)" in js)
check("long texts never decide the state", "t.length <= 40" in js)
check("DOM kinds wait for a slow page", "while (v[0] !== 'SIGNED_IN' && Date.now() < deadline)" in js)
check("neither control reads UNKNOWN, not signed out", "'UNKNOWN', 'neither a sign-in nor a sign-out" in js)
for kind in sl.PROBE_KINDS:
    check("browser function handles kind " + kind, f"kind === '{kind}'" in js)

req = sl.request_payload(good)
check("one request for the batch", isinstance(req["entries"], list) and len(req["entries"]) == 3)
# The password manager refuses more than 5 entries in one call ("invalid: schema",
# measured 23 NOV 2026 with 7): split, never send an over-long request.
many = [dict(good[0], id=f"s{i}", label=f"Site {i}", url=f"https://s{i}.example.org/") for i in range(12)]
reqs = sl.request_payloads(many)
check("12 sites become 3 requests", [len(r["entries"]) for r in reqs] == [5, 5, 2])
check("no request exceeds the limit", all(len(r["entries"]) <= sl.MAX_ENTRIES_PER_REQUEST for r in sl.request_payloads(many)))
check("split keeps every site once", [e["website"] for r in reqs for e in r["entries"]] == [f"https://s{i}.example.org" for i in range(12)])
try:
    sl.request_payload(many)
    check("an over-long single request is refused", False)
except ValueError:
    pass
check("small batch is still one request", len(sl.request_payloads(good)) == 1)
check("website defaults to the url's origin", req["entries"][0]["website"] == "https://a.example.org")
check("every entry is a login with a reason", all(e["kind"] == "login" and e["reason"] for e in req["entries"]))
check("goal fits the 140-char limit",
      len(sl.request_payload([dict(g, label=g["label"] * 30) for g in good])["goal"]) <= 140)

NODE = shutil.which("node")
if NODE:
    r = subprocess.run([NODE, "--check", "-"], input="async function f(){ return " + js + " }", capture_output=True, text=True)
    check("probe expression parses as JavaScript", r.returncode == 0)
else:
    print("SKIP probe JS parse: node not installed")

with tempfile.TemporaryDirectory() as d:
    with open(os.path.join(d, ".autoresearch.json"), "w") as f:
        json.dump({"logins": good}, f)
    env = dict(os.environ, AUTORESEARCH_VAULT=d)
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "session_logins.py"), "--request", "a", "c"],
                       capture_output=True, text=True, env=env)
    check("--request exits 0", r.returncode == 0)
    check("--request prints a list with one two-entry request",
          r.returncode == 0 and [len(x["entries"]) for x in json.loads(r.stdout)] == [2])
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "session_logins.py"), "--probe", "zzz"],
                       capture_output=True, text=True, env=env)
    check("unknown id is refused", r.returncode == 2)
    with open(os.path.join(d, ".autoresearch.json"), "w") as f:
        json.dump({}, f)
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "session_logins.py")],
                       capture_output=True, text=True, env=env)
    check("no logins block says so", r.returncode == 1 and "no `logins` block" in r.stdout)

if FAILS:
    print(f"{len(FAILS)} failure(s)")
    sys.exit(1)
print("test_session_logins: ok")
