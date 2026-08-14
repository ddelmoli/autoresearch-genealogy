#!/usr/bin/env python3
"""Test whether each cited FamilySearch ARK still resolves — headless, resumable.

[[Open_Questions]] Q275. Built 14 AUG 2026 after a hand-driven browser sweep was found
to be **silently faking clean results**.

** WHY THIS CANNOT BE A `fetch`. ** `/ark:/61903/<id>` returns HTTP **200 and ~13,630
bytes for a valid id, an invalid id and a junk control alike** — it is the SPA shell, and
the record (or the 404) only exists after JavaScript runs. Measured three ways; there is
no status code, no Location header and no length difference to key on. The page must be
RENDERED.

** WHY EVERY BATCH CARRIES A CONTROL, AND WHY THAT IS THE WHOLE POINT. ** The hand-driven
version injected iframes in batches and read their text. At batch 37 a slice containing a
KNOWN 404 reported *"404s: none"* — the iframes had not finished rendering inside the wait
window, and an unloaded frame is indistinguishable from a clean one. Three earlier batches
had carried no control at all and had read as clean. **A detector that cannot be seen
failing will report zeros forever.** So:

  * every run tests the two controls FIRST -- one ark known DEAD on this host and one
    known LIVE -- and REFUSES TO RUN if either misbehaves;
  * the controls are re-tested every `--control-every` arks thereafter, and the run
    ABORTS the moment one stops behaving — a half-finished honest sweep beats a complete
    dishonest one.

⛔⛔ ** THIS SCRIPT DOES NOT CURRENTLY WORK AGAINST FAMILYSEARCH, AND THE REASON IS NOT
FIXABLE FROM HERE (measured 14 AUG 2026). ** FamilySearch fronts these URLs with Imperva /
Incapsula bot protection, and a headless Chrome gets the challenge page instead of the
record: an **883-byte** document containing `_Incapsula_Resource`, an `incident_id` and
`NOINDEX, NOFOLLOW`. That page does not contain the 404 wording, so a naive sweep scores
**every ark "live"** — 1,448 confident false negatives. The other control simply timed out.

** THE CONTROL GATE CAUGHT THIS ON THE FIRST RUN AND REFUSED TO PROCEED. ** That is the
script working, not failing: the LIVE control came back `live` (wrongly -- off the WAF
page, which merely fails to match the 404 wording) while the DEAD control timed out. The
pair disagreed with expectation and the run aborted before writing a single row.

⛔ ** DO NOT "FIX" THIS BY EVADING THE BOT PROTECTION. ** Spoofing a user agent, driving a
stealth-patched browser or solving the challenge is out of bounds — the host is
deliberately refusing automated access, and this vault has no business working around
that. If FamilySearch ARKs must be swept at scale, the routes are: ask FamilySearch for
API access, or run the sweep through the operator's OWN signed-in browser at a human pace.

** WHAT IT IS STILL GOOD FOR. ** The control-gated harness is host-agnostic. It runs
unchanged against any host that does not bot-block (Antenati, archive.org, metryki), and
the dead/live control pattern is the reusable part: point it at a different `--list` and
supply a control pair for that host.

** AUTH. ** Nothing here signs in and nothing here handles credentials. The test only
distinguishes *"FamilySearch's 404 page"* from *"anything else"*, which does not require
being logged in — a signed-out record page is still not the 404 page. It runs in a
throwaway `--user-data-dir` so it cannot touch the operator's own Chrome profile or
session.

** RESUMABLE. ** Results append to the CSV as they are produced and completed arks are
skipped on restart, so the job can be killed and resumed. Progress goes to stderr.

Usage
-----
    python3 scripts/ark_404_sweep.py --flagged \\
        --control-dead 1:1:XXXX-XXX --control-live 1:1:YYYY-YYY --out sweep.csv

    # --list arks.txt instead of --flagged for an arbitrary population;
    # --limit 50 for a short calibration run before committing to the whole thing.

Exit status is 2 if a control failed (results still usable up to that point), else 0.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ⚠ THE CONTROLS ARE SUPPLIED AT RUN TIME AND ARE DELIBERATELY NOT HARD-CODED. A control
# is a real record identifier — a pointer to a real person — and this is the PUBLIC repo,
# so committing one publishes it. (The pre-commit PII audit blocked exactly that when this
# file first carried them; the guard was right.) Pass your own with --control-dead and
# --control-live, e.g. `--control-dead 1:1:XXXX-XXX --control-live 1:1:YYYY-YYY`, and keep
# the pair in your vault's notes rather than here.

NOT_FOUND_RE = re.compile(r"this is unexpected|can't seem to find", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def render(ark, budget_ms, timeout_s, profile):
    """Return (verdict, dom_bytes). verdict is 'dead' | 'live' | 'error'."""
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-extensions", "--disable-background-networking",
        "--user-data-dir=" + profile,
        "--virtual-time-budget=%d" % budget_ms,
        "--dump-dom", "https://www.familysearch.org/ark:/61903/" + ark,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return "error", 0
    dom = p.stdout.decode("utf-8", "replace")
    if len(dom) < 500:
        # Too short to be either page: a crash or a blocked launch, NOT a pass.
        return "error", len(dom)
    text = TAG_RE.sub(" ", dom)
    return ("dead" if NOT_FOUND_RE.search(text) else "live"), len(dom)


def check_controls(args):
    """Both controls must behave. Returns True on success."""
    bad, _ = render(args.control_dead, args.budget, args.timeout, args.profile)
    good, _ = render(args.control_live, args.budget, args.timeout, args.profile)
    ok = (bad == "dead" and good == "live")
    if not ok:
        sys.stderr.write(
            "CONTROL FAILURE: %s expected dead got %s; %s expected live got %s\n"
            % (args.control_dead, bad, args.control_live, good))
    return ok


def load_flagged(vault_arg):
    """The Q275 population: entries capped at 24 or marked 'representative listed'."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import harvest_sources as h
    import vault_config
    v = vault_config.resolve_vault(vault_arg)
    toks = set()
    for _p, ents in h.entry_blocks_with_ids(v).items():
        for _vid, _name, _li, body in ents:
            locs = h.record_locators(body)
            if len(locs) == 24 or "representative listed" in body:
                toks |= {x[3:] for x in locs if x.startswith("fs:1:1:")}
    return sorted(toks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", help="file of ARK ids, one per line (with or without 1:1:)")
    ap.add_argument("--flagged", action="store_true", help="sweep the Q275 population")
    ap.add_argument("--vault")
    ap.add_argument("--out", default="ark_404_sweep.csv")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--budget", type=int, default=8000, help="virtual time budget, ms")
    ap.add_argument("--timeout", type=int, default=45, help="hard per-ark timeout, s")
    ap.add_argument("--control-dead", required=True,
                    help="ark id known to be DEAD on this host (a 404). Required: a sweep\n"
                         "whose detector cannot be seen failing is worthless.")
    ap.add_argument("--control-live", required=True,
                    help="ark id known to be LIVE on this host.")
    ap.add_argument("--control-every", type=int, default=25)
    ap.add_argument("--profile", default="/tmp/ark404-profile")
    args = ap.parse_args()

    if args.flagged:
        arks = load_flagged(args.vault)
    elif args.list:
        arks = [l.strip() for l in open(args.list) if l.strip()]
    else:
        ap.error("give --list or --flagged")
    arks = [a if a.startswith("1:1:") else "1:1:" + a for a in arks]

    done = {}
    if os.path.exists(args.out):
        with open(args.out) as f:
            for row in csv.DictReader(f):
                done[row["ark"]] = row["verdict"]
    todo = [a for a in arks if a not in done]
    if args.limit:
        todo = todo[:args.limit]
    sys.stderr.write("population %d | already done %d | this run %d\n"
                     % (len(arks), len(done), len(todo)))
    if not todo:
        return 0

    sys.stderr.write("calibrating controls...\n")
    if not check_controls(args):
        sys.stderr.write("REFUSING TO RUN. A sweep whose detector cannot be seen "
                         "failing is worthless.\n")
        return 2

    new = not os.path.exists(args.out)
    fh = open(args.out, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(["ark", "verdict", "dom_bytes", "checked"])
        fh.flush()

    t0 = time.time()
    dead = errors = 0
    for i, ark in enumerate(todo, 1):
        if i > 1 and (i - 1) % args.control_every == 0:
            if not check_controls(args):
                sys.stderr.write(
                    "ABORTING at %d/%d — every result after the last good control is "
                    "suspect. Re-run to resume; completed rows are kept.\n" % (i, len(todo)))
                fh.close()
                return 2
            sys.stderr.write("  [controls still good at %d]\n" % i)
        verdict, nbytes = render(ark, args.budget, args.timeout, args.profile)
        w.writerow([ark, verdict, nbytes, int(time.time())])
        fh.flush()
        if verdict == "dead":
            dead += 1
            sys.stderr.write("  DEAD %s\n" % ark)
        elif verdict == "error":
            errors += 1
        if i % 25 == 0:
            rate = (time.time() - t0) / i
            sys.stderr.write("  %d/%d  dead=%d err=%d  %.1fs/ark  eta %.0fmin\n"
                             % (i, len(todo), dead, errors, rate,
                                rate * (len(todo) - i) / 60))
    fh.close()
    sys.stderr.write("DONE %d checked, %d dead, %d errors -> %s\n"
                     % (len(todo), dead, errors, args.out))
    # errors are NOT failures of the ark; they are failures of the test, and are left
    # in the CSV as `error` so a resume can retry them rather than scoring them clean.
    return 0


if __name__ == "__main__":
    sys.exit(main())
