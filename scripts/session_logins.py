#!/usr/bin/env python3
"""Pre-session sign-in check: which research sites are signed in, before work starts.

A sitting that discovers a lapsed login halfway through loses the work it did while
signed out, and worse, can log it: a signed-out FamilySearch answers every request
with a sign-in redirect, and "no records" from a signed-out site looks exactly like
"no records". Checking every site once, BEFORE phase 1, turns that into a list of
sites to fix while the operator is still at the keyboard.

The site list is per-OPERATOR (the accounts this person holds), so it lives in the
vault's `.autoresearch.json` `logins` block, read through `vault_config.get_logins`.
Shape: `vault-template/.autoresearch.example.json`. Passwords never appear here or in
the conversation: signing in goes through the password manager's own consent prompt
(`request_credentials`, then `autofill_credential` on the sign-in page).

This script does not drive a browser. It prints what the agent runs:

  python3 scripts/session_logins.py                 # the plan: one line per site
  python3 scripts/session_logins.py --probe ID      # the JS expression for that site's tab
  python3 scripts/session_logins.py --request ID ID # the ONE request_credentials payload
                                                    #   for the sites found signed out

Procedure (the `session-logins` skill has it in full):
  1. For each site, put a tab of this session's group on its `url` and run the
     `--probe` expression with javascript_tool. It returns JSON:
     {state: SIGNED_IN | SIGNED_OUT | UNKNOWN, how, login_href}.
  2. Collect the SIGNED_OUT ids; run `--request` with them and make that ONE
     request_credentials call (one consent prompt, not one per site).
  3. For each, navigate to `login_href` (or the configured `login_url`), call
     autofill_credential, submit, use enter_verification_code if a code is asked
     for, and re-run the probe. Only a re-probe reading SIGNED_IN counts.
  4. Report the table: signed in already / signed in now / still signed out (why).

Probe kinds:
  signout_visible  (default) a VISIBLE link or button reading "sign out" / "log out".
                   Visibility matters: one site keeps a hidden "Log in" next to a
                   visible "Sign out", and a text scan reads both.
  text             `pattern` (a JS regex source, case-insensitive) in the page text,
                   for sites that greet a signed-in user instead ("Hello, ...").
  cookie           a cookie NAMED `name` exists. Only the name is tested, never a
                   value, and nothing about it is returned.
  fetch_json       same-origin GET of `url` answers 200 with a JSON body; a sign-in
                   redirect answers HTML.
An UNKNOWN (the probe could not run, or the page did not load) is never treated as
signed in.
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import vault_config  # noqa: E402

PROBE_KINDS = ("signout_visible", "text", "cookie", "fetch_json")

# One function, parameterised by the site's probe spec. Kept as a single expression
# so one javascript_tool call per tab both defines and runs it. The leading `await`
# is load-bearing: javascript_tool returns a bare async IIFE as `{}` (an unresolved
# Promise serialised), which would read as neither signed in nor out.
_PROBE_JS = r"""await (async (spec) => {
  const vis = (e) => !!(e.offsetParent || (e.getClientRects && e.getClientRects().length));
  const ctl = [...document.querySelectorAll('a,button,[role=button]')].filter(vis);
  const txt = (e) => ((e.innerText || e.getAttribute('aria-label') || '').trim());
  const signin = ctl.find((e) => /^(sign|log) ?in\b/i.test(txt(e)));
  const login_href = signin && signin.getAttribute && signin.getAttribute('href') ? new URL(signin.getAttribute('href'), location.href).href.split('?')[0] : null;
  const out = (state, how) => JSON.stringify({ id: spec.id, state, how, login_href: state === 'SIGNED_IN' ? null : login_href, page: location.origin + location.pathname });
  try {
    if (document.readyState === 'loading') return out('UNKNOWN', 'page still loading');
    const p = spec.probe || {};
    const kind = p.kind || 'signout_visible';
    if (kind === 'signout_visible') {
      const so = ctl.find((e) => /\b(sign|log) ?out\b/i.test(txt(e)));
      return so ? out('SIGNED_IN', 'visible "' + txt(so).slice(0, 30) + '"') : out('SIGNED_OUT', 'no visible sign-out control');
    }
    if (kind === 'text') {
      return new RegExp(p.pattern, 'i').test(document.body.innerText) ? out('SIGNED_IN', 'page text matches /' + p.pattern + '/') : out('SIGNED_OUT', 'page text lacks /' + p.pattern + '/');
    }
    if (kind === 'cookie') {
      const names = document.cookie.split(';').map((c) => c.split('=')[0].trim());
      return names.includes(p.name) ? out('SIGNED_IN', 'cookie ' + p.name + ' present') : out('SIGNED_OUT', 'cookie ' + p.name + ' absent');
    }
    if (kind === 'fetch_json') {
      const r = await fetch(p.url, { headers: { accept: 'application/json' }, credentials: 'include' });
      const ct = r.headers.get('content-type') || '';
      return r.ok && ct.includes('json') ? out('SIGNED_IN', 'GET ' + p.url.split('?')[0] + ' -> ' + r.status + ' JSON') : out('SIGNED_OUT', 'GET -> ' + r.status + ' ' + ct.split(';')[0]);
    }
    return out('UNKNOWN', 'unrecognised probe kind ' + kind);
  } catch (e) { return out('UNKNOWN', 'probe error: ' + String(e && e.message || e)); }
})(__SPEC__)"""


def validate(sites):
    """Return a list of problems with the configured site list (empty = fine)."""
    problems, seen = [], set()
    for s in sites:
        sid = s.get("id")
        if sid in seen:
            problems.append(f"{sid}: duplicate id")
        seen.add(sid)
        kind = (s.get("probe") or {}).get("kind", "signout_visible")
        if kind not in PROBE_KINDS:
            problems.append(f"{sid}: probe kind {kind!r} not one of {PROBE_KINDS}")
        p = s.get("probe") or {}
        if kind == "text" and not p.get("pattern"):
            problems.append(f"{sid}: text probe needs a pattern")
        if kind == "cookie" and not p.get("name"):
            problems.append(f"{sid}: cookie probe needs a name")
        if kind == "fetch_json" and not str(p.get("url", "")).startswith("/"):
            problems.append(f"{sid}: fetch_json probe needs a same-origin url starting with /")
        if not str(s.get("url", "")).startswith("https://"):
            problems.append(f"{sid}: url must be https")
        if not s.get("keywords"):
            problems.append(f"{sid}: keywords (1Password hints) missing")
    return problems


def probe_js(site):
    spec = {"id": site["id"], "probe": site.get("probe") or {}}
    return _PROBE_JS.replace("__SPEC__", json.dumps(spec))


def request_payload(sites):
    """The single request_credentials call for the given (signed-out) sites."""
    labels = ", ".join(s.get("label", s["id"]) for s in sites)
    return {
        "goal": ("Sign in to research sites before a genealogy session: " + labels)[:140],
        "entries": [{
            "kind": "login",
            "website": s.get("website") or s["url"].split("/", 3)[0] + "//" + s["url"].split("/", 3)[2],
            "reason": ("Sign in to " + s.get("label", s["id"]))[:100],
            "keywords": [str(k)[:50] for k in (s.get("keywords") or [])][:5],
        } for s in sites],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default=None)
    ap.add_argument("--probe", metavar="ID", help="print the JS probe expression for one site")
    ap.add_argument("--request", nargs="+", metavar="ID",
                    help="print the request_credentials payload for these signed-out sites")
    ap.add_argument("--json", action="store_true", help="print the site list as JSON")
    a = ap.parse_args(argv)
    vault = vault_config.resolve_vault(a.vault)
    sites = vault_config.get_logins(vault)
    if not sites:
        print("session_logins: no `logins` block in " + vault_config.config_path(vault) +
              " (shape: vault-template/.autoresearch.example.json)")
        return 1
    by_id = {s["id"]: s for s in sites}
    problems = validate(sites)
    if problems:
        print("session_logins: config problems:\n  " + "\n  ".join(problems))
        return 2
    if a.probe:
        if a.probe not in by_id:
            print(f"unknown site id {a.probe!r}; known: {', '.join(by_id)}")
            return 2
        print(probe_js(by_id[a.probe]))
        return 0
    if a.request:
        missing = [i for i in a.request if i not in by_id]
        if missing:
            print(f"unknown site id(s) {missing}; known: {', '.join(by_id)}")
            return 2
        print(json.dumps(request_payload([by_id[i] for i in a.request]), indent=2))
        return 0
    if a.json:
        print(json.dumps(sites, indent=2))
        return 0
    print(f"=== PRE-SESSION SIGN-IN CHECK ({len(sites)} sites) ===")
    for s in sites:
        kind = (s.get("probe") or {}).get("kind", "signout_visible")
        print(f"  {s['id']:<18} {kind:<16} {s['url']}" + (f"   [{s['note']}]" if s.get("note") else ""))
    print("\nProbe each tab:  python3 scripts/session_logins.py --probe <id>   (javascript_tool)")
    print("Then, for the SIGNED_OUT ids, ONE consent prompt:")
    print("                 python3 scripts/session_logins.py --request <id> <id> ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
