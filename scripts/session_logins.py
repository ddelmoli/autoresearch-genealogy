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
  python3 scripts/session_logins.py --request ID ID # the request_credentials payloads (a JSON
                                                    #   list, at most 5 sites each) for the
                                                    #   sites found signed out

Procedure (the `session-logins` skill has it in full):
  1. For each site, put a tab of this session's group on its `url` and run the
     `--probe` expression with javascript_tool. It returns JSON:
     {state: SIGNED_IN | SIGNED_OUT | UNKNOWN, how, login_href}.
  2. Collect the SIGNED_OUT ids; run `--request` with them and make one
     request_credentials call per printed payload (one consent prompt per batch of
     up to five sites, never one per site; the password manager refuses more).
  3. For each, navigate to `login_href` (or the configured `login_url`), call
     autofill_credential, submit, use enter_verification_code if a code is asked
     for, and re-run the probe. Only a re-probe reading SIGNED_IN counts.
  4. Report the table: signed in already / signed in now / still signed out (why).

Probe kinds:
  signout_visible  (default) a link or button reading "sign out" / "log out".
                   SIGNED_IN on a visible one, or on one inside a closed menu
                   (hidden, matched by text or by a logout-shaped href) when no
                   sign-in control is visible; SIGNED_OUT on a visible sign-in
                   control; UNKNOWN when the page shows neither. Visibility still
                   matters for SIGN-IN: one site keeps a hidden "Log in" next to a
                   visible "Sign out", so only a visible sign-in control counts.
                   Measured 23 NOV 2026: two sites keep "Sign out" only inside an
                   account menu, and a visible-only test read both as signed out.
  text             `pattern` (a JS regex source, case-insensitive) in the page text,
                   for sites that greet a signed-in user instead ("Hello, ...").
  cookie           a cookie NAMED `name` exists. Only the name is tested, never a
                   value, and nothing about it is returned.
  fetch_json       same-origin GET of `url` answers 200 with a JSON body; a sign-in
                   redirect answers HTML.
The DOM kinds (signout_visible, text) re-judge every 0.5 s for up to 8 s
(`wait_ms` in the site's probe block overrides) until the page reads SIGNED_IN: a page whose
header is drawn by a script after load read as signed out on the first look
(measured 23 NOV 2026, one single-page app). A real SIGNED_OUT therefore costs the
full wait; that is the price of not misreading a slow page.
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
  const txt = (e) => ((e.innerText || e.textContent || e.getAttribute('aria-label') || '').trim());
  const OUT_TXT = /\b(sign|log) ?out\b/i;
  const OUT_HREF = /(sign|log)[-_ ]?(out|off)\b/i;
  const IN_TXT = /^(sign|log) ?in\b/i;
  // A control's LABEL is short; a long text is a container or a sentence ("Don't
  // forget to log out"), and must not decide the state.
  const label = (e) => { const t = txt(e); return t.length <= 40 ? t : ''; };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let login_href = null;
  const out = (state, how) => JSON.stringify({ id: spec.id, state, how, login_href: state === 'SIGNED_IN' ? null : login_href, page: location.origin + location.pathname });
  const p = spec.probe || {};
  const kind = p.kind || 'signout_visible';
  const judge = () => {
    const all = [...document.querySelectorAll('a,button,[role=button],[role=menuitem]')];
    const ctl = all.filter(vis);
    const signin = ctl.find((e) => IN_TXT.test(label(e)));
    login_href = signin && signin.getAttribute && signin.getAttribute('href') && !/^javascript:/i.test(signin.getAttribute('href')) ? new URL(signin.getAttribute('href'), location.href).href.split('?')[0] : null;
    if (document.readyState === 'loading') return ['UNKNOWN', 'page still loading'];
    if (kind === 'signout_visible') {
      const so = ctl.find((e) => OUT_TXT.test(label(e)));
      if (so) return ['SIGNED_IN', 'visible "' + txt(so).slice(0, 30) + '"'];
      const hidden = all.find((e) => OUT_TXT.test(label(e)) || OUT_HREF.test(e.getAttribute('href') || ''));
      if (hidden && !signin) return ['SIGNED_IN', 'sign-out control inside a closed menu ("' + (txt(hidden) || hidden.getAttribute('href') || '').slice(0, 30) + '")'];
      if (signin) return ['SIGNED_OUT', 'visible "' + txt(signin).slice(0, 30) + '", no sign-out control'];
      return ['UNKNOWN', 'neither a sign-in nor a sign-out control on the page'];
    }
    if (kind === 'text') {
      return new RegExp(p.pattern, 'i').test(document.body.innerText) ? ['SIGNED_IN', 'page text matches /' + p.pattern + '/'] : ['SIGNED_OUT', 'page text lacks /' + p.pattern + '/'];
    }
    return null;
  };
  try {
    if (kind === 'signout_visible' || kind === 'text') {
      // Pages that render their header after load (single-page apps, a greeting
      // filled in by a script) read as signed out on the first look. Re-judge
      // until the page settles on SIGNED_IN or the wait runs out.
      const deadline = Date.now() + (p.wait_ms || 8000);
      let v = judge();
      while (v[0] !== 'SIGNED_IN' && Date.now() < deadline) { await sleep(500); v = judge(); }
      return out(v[0], v[1]);
    }
    judge();
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


# The password manager refuses a request_credentials call with more than this many
# entries (it answers {"status":"invalid","reason":"schema"}, naming no field), so a
# longer list of signed-out sites goes out as consecutive requests of at most this size.
MAX_ENTRIES_PER_REQUEST = 5


def request_payload(sites):
    """One request_credentials call for up to MAX_ENTRIES_PER_REQUEST sites."""
    if len(sites) > MAX_ENTRIES_PER_REQUEST:
        raise ValueError(f"{len(sites)} sites in one request; the limit is {MAX_ENTRIES_PER_REQUEST}")
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


def request_payloads(sites):
    """The request_credentials calls for the given (signed-out) sites: as few as the
    per-request limit allows, each a complete payload."""
    n = MAX_ENTRIES_PER_REQUEST
    return [request_payload(sites[i:i + n]) for i in range(0, len(sites), n)]


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
        # Always a JSON list, one element per request_credentials call, so the
        # shape does not change with the number of sites.
        print(json.dumps(request_payloads([by_id[i] for i in a.request]), indent=2))
        return 0
    if a.json:
        print(json.dumps(sites, indent=2))
        return 0
    print(f"=== PRE-SESSION SIGN-IN CHECK ({len(sites)} sites) ===")
    for s in sites:
        kind = (s.get("probe") or {}).get("kind", "signout_visible")
        print(f"  {s['id']:<18} {kind:<16} {s['url']}" + (f"   [{s['note']}]" if s.get("note") else ""))
    print("\nProbe each tab:  python3 scripts/session_logins.py --probe <id>   (javascript_tool)")
    print("Then, for the SIGNED_OUT ids, one consent prompt per printed payload (<=5 sites each):")
    print("                 python3 scripts/session_logins.py --request <id> <id> ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
