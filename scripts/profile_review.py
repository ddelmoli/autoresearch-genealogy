#!/usr/bin/env python3
"""profile_review.py — the profile-review ROTATION: a multi-armed bandit that
picks ~1% of the vault per session to re-check against FamilySearch, WikiTree and
Ancestry, and records what each poll actually yielded.

THE QUESTION THIS LOOP ASKS, which no existing loop asked:
    has a SLICE of the vault gained new sources / relationships / vitals on FS,
    WikiTree or Ancestry since we last looked — and, for entries with no external
    id at all, does a profile EXIST there yet?

Its two siblings, whose shape this follows exactly:
    watchlist_age.py     + watchlist_snapshots.json      — have the profiles we
                                                           CITE been changed by others?
    new_records_age.py   + new_records_snapshots.json    — have NEW collections
                                                           or indexes appeared?

** IT IS A ROTATION, NOT A SWEEP. ** Watchlist.md's own standing rule is "do NOT
poll the whole tree — most of it is static or low-signal (collaborative trees copy
each other, sometimes from this vault)". A whole-vault pass would spend days
re-reading profiles that have not changed. So each session polls a small slice and
the rotation RESUMES (per-entry `last_polled`) rather than restarting.

WHY A BANDIT RATHER THAN A PRIORITY LIST (Operating_Protocol.md, operator-directed
28 JUL 2026). A pilot slice of 5 WELL_SOURCED Gen-4 anchors returned a discovery
yield of ZERO, and the draft that came out of it turned that n=5 null into a
PERMANENT EXCLUSION of 705 entries. The operator's correction is the design:

    "We shouldn't make assumptions about which ones will yield new information -
     generally you've been wrong when you've made assumptions. ... essentially we
     want to 'one-arm bandit' this - balanced between EXPLOITATION and
     EXPLORATION. Even the deep medieval and peerage ones may be worth a look at
     times."

So: ** EVERY ARM DRAWS AT LEAST ONE ENTRY, EVERY SESSION, INCLUDING BOOK_SOURCED. **
That exploration floor is the anti-assumption device and the reason the design
survived. No stratum can be written off on thin evidence, because none ever goes
to zero. It is pinned by scripts/test_profile_review.py in BOTH directions — with
a wildly lopsided hit-rate history the floor still holds, and with the floor
disabled the same fixture collapses into one arm (a fixture that cannot be made to
fail proves nothing).

USAGE
    python3 scripts/profile_review.py                 # dry-run the draw (no writes, no network)
    python3 scripts/profile_review.py --json          # same, machine-readable
    python3 scripts/profile_review.py --gen-range 4-6 --region Italian   # narrow the pool
    python3 scripts/profile_review.py --record P-XXXXXX --outcome hit --note "..." \
                                      --probed fs,wt   # record one polled entry
    python3 scripts/profile_review.py --complete      # reset the cadence clock
    python3 scripts/profile_review.py --heartbeat     # the SessionStart line

ZERO DEPENDENCIES, and ABSENT CONFIG IS A SILENT NO-OP (the archive_sections
pattern), so this stays upstream-safe: a vault with no `profile_review` block in
.maintenance.json gets a "not configured" heartbeat and defaults everywhere else.

NO NETWORK. Everything here — the census, the allocation, the state, the heartbeat
— runs headless. The actual page visits are the operator-Chrome half, driven from
the worklist this prints. FS costs ONE RENDERED PAGE VISIT PER PERSON (its
internal JSON API 404s and /tree/person/sources/{PID} is a ~13 KB SPA shell with
no count in it), which is why the cadence is 13 and not 130.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import privacy_gate
import vault_config

SNAPSHOT_FILE = "profile_review_snapshots.json"
MAINTENANCE_FILE = ".maintenance.json"
CONFIG_KEY = "profile_review"

# ---------------------------------------------------------------------------
# Constants that encode a DECIDED rule. Each is here because changing it changes
# the design, not merely a default.
# ---------------------------------------------------------------------------
# ~1% of the vault per session. "Not negotiable upward" (operator, 28 JUL 2026) —
# so it is CLAMPED against the live pool size rather than merely defaulted, and a
# configured value above 1% is reported as clamped instead of silently obeyed.
DEFAULT_CADENCE = 13
CADENCE_FRACTION = 0.01
# At least one entry from EVERY arm, every session. The anti-assumption device.
EXPLORATION_FLOOR = 1
# Do not re-poll an entry inside its cooldown. Change-polling and existence-probing
# get different cadences because profile CREATION is slower than profile EDITING.
POLL_COOLDOWN_DAYS = 180
PROBE_COOLDOWN_DAYS = 365
# The external-id platforms whose existence question this loop asks. `fs` is the
# only one any entry currently answers; `wt` and `anc` are zero vault-wide, which
# means the existence question has never been asked for ANY entry on those two.
PLATFORMS = ("fs", "wt", "anc")

# ** A DISPLAY / TIE-BREAK ORDER, NOT A POPULATION. ** The arms themselves are
# DERIVED from the live census every run (see build_candidates): the counts in the
# spec were measured on one day and were stale the moment they were written. An arm
# observed in the data but absent from this tuple still gets its floor and its own
# row — it is appended, never dropped.
ARM_DISPLAY_ORDER = ("SOURCE_GAP", "UNCITED", "LOW_COVERAGE",
                     "WELL_SOURCED", "BOOK_SOURCED", "EXISTENCE_PROBE")
EXISTENCE_PROBE = "EXISTENCE_PROBE"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def empty_state():
    return {
        "_comment": (
            "Profile-review rotation state (versioned, so git tracks the bandit's "
            "learning). Written by scripts/profile_review.py --record. `arms` holds "
            "per-arm polled/hits (the exploitation signal); `entries` holds per-entry "
            "last_polled plus last_probed_fs / last_probed_wt / last_probed_anc. "
            "THIS STATE IS DELIBERATELY OUT OF THE `- meta:` BLOCK (CLAUDE.method.md "
            "integrity rule 9: the meta block is the machine record and stays lean; "
            "research history lives elsewhere). A NEGATIVE IS A MEASUREMENT WITH A "
            "DATE, NOT A PROPERTY — an undated negative is treated as EXPIRED ON SIGHT."
        ),
        "arms": {},
        "entries": {},
        "history": [],
    }


def load_state(vault):
    path = os.path.join(vault, SNAPSHOT_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
    except FileNotFoundError:
        return empty_state()
    except (json.JSONDecodeError, OSError) as e:
        raise SystemExit(f"profile_review: {SNAPSHOT_FILE} unreadable ({e})")
    st.setdefault("arms", {})
    st.setdefault("entries", {})
    st.setdefault("history", [])
    return st


def save_state(vault, state):
    path = os.path.join(vault, SNAPSHOT_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    return path


def load_config(vault):
    """The OPTIONAL `profile_review` block of .maintenance.json. Absent => {}."""
    try:
        with open(os.path.join(vault, MAINTENANCE_FILE), encoding="utf-8") as f:
            return json.load(f).get(CONFIG_KEY) or {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def parse_date(val):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(val or ""))
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


# ---------------------------------------------------------------------------
# Cooldowns. "A NEGATIVE IS A MEASUREMENT WITH A DATE, NOT A PERMANENT PROPERTY."
# ---------------------------------------------------------------------------
def poll_status(entry_state, today, cooldown=POLL_COOLDOWN_DAYS):
    """(due, days_since_or_None, reason) for the ~180d CHANGE poll."""
    d = parse_date((entry_state or {}).get("last_polled"))
    if d is None:
        return True, None, "never polled"
    days = (today - d).days
    return (days >= cooldown), days, f"polled {days}d ago (cooldown {cooldown}d)"


def probe_status(entry_state, platform, today, cooldown=PROBE_COOLDOWN_DAYS):
    """(due, days_since_or_None, reason) for the ~365d EXISTENCE probe.

    ** AN UNDATED NEGATIVE IS EXPIRED ON SIGHT. ** `fs: none` means "searched
    FamilySearch, confirmed absent" and it carries NO DATE, so a profile created
    since that search makes it silently wrong and nothing ever expires it. The same
    will be true of any wt/anc negative the moment one is written. The fix is not
    to trust the token: an absent probe date reads as due, always.
    """
    d = parse_date((entry_state or {}).get(f"last_probed_{platform}"))
    if d is None:
        return True, None, f"no dated {platform} probe (undated negative = expired on sight)"
    days = (today - d).days
    return (days >= cooldown), days, f"{platform}-probed {days}d ago (cooldown {cooldown}d)"


# ---------------------------------------------------------------------------
# The PRIOR: a tilt within an arm, never a rule that fixes the draw.
# ---------------------------------------------------------------------------
def prior_score(cand):
    """Operator's prior: "Low-sourced entries or entries related to open questions
    are likely the ones we're most interested in." That BIASES the draw inside an
    arm; it does not decide which arms are drawn (the floor and the hit-rates do).
    """
    s = 0
    if cand.get("ark_count", 0) == 0:
        s += 2
    elif cand["ark_count"] <= 3:
        s += 1
    if cand.get("open_question"):
        s += 2
    return s


def prior_reasons(cand):
    out = []
    if cand.get("ark_count", 0) == 0:
        out.append("0 records")
    elif cand["ark_count"] <= 3:
        out.append(f"{cand['ark_count']} records")
    if cand.get("open_question"):
        out.append(f"open question ({cand['open_question']})")
    return out


# ---------------------------------------------------------------------------
# THE ALLOCATOR — pure, so the tests can drive it with fixtures and no vault.
# ---------------------------------------------------------------------------
def smoothed_rate(hits, polled):
    """Laplace-smoothed hit rate. An UNTRIED arm scores 0.5; an arm measured at
    0-for-10 scores 1/12 = 0.083. So an unexplored stratum outranks a
    demonstrated-null one — the anti-assumption bias, in the arithmetic rather
    than in a comment."""
    return (hits + 1.0) / (polled + 2.0)


def allocate(candidates, state, today=None, cadence=DEFAULT_CADENCE,
             floor=EXPLORATION_FLOOR, arm_order=ARM_DISPLAY_ORDER):
    """Draw the session's slice. Returns a dict; writes nothing.

    Two phases, deliberately simple (the operator asked for epsilon-greedy, not a
    Thompson sampler):

      1. FLOOR   — `floor` entries from EVERY arm that has an eligible candidate.
      2. EXPLOIT — the remainder, one slot at a time, to the arm with the highest
                   smoothed hit-rate that still has eligible candidates.

    The exploit loop counts slots ALREADY ASSIGNED THIS SESSION in the denominator
    (`polled + assigned + 2`), which is what stops a single hot arm taking every
    remaining slot without needing an epsilon parameter: each pull it wins lowers
    its own next score. With no history at all every arm sits at 0.5 and the loop
    degenerates to round-robin, which is the correct behaviour for session 1 —
    ** the first hit-rates are n=0, and tuning an allocation on one session of data
    is exactly the mistake this whole design exists to avoid. **

    Determinism is deliberate: no randomness anywhere. The same vault + same state
    + same day draws the same 13, so a draw can be reviewed, re-run and tested.
    The rotation still advances, because polling an entry puts it in cooldown.
    """
    today = today or date.today()
    arms_state = state.get("arms", {})
    entries_state = state.get("entries", {})

    # Arms are DERIVED from the candidates. arm_order is only a tie-break.
    seen_arms = {c["arm"] for c in candidates}
    ordered = [a for a in arm_order if a in seen_arms] + sorted(seen_arms - set(arm_order))

    by_arm, eligible_by_arm = defaultdict(list), defaultdict(list)
    for c in candidates:
        by_arm[c["arm"]].append(c)
        es = entries_state.get(c["id"], {})
        if c["arm"] == EXISTENCE_PROBE:
            due, days, why = probe_status(es, "fs", today)
        else:
            due, days, why = poll_status(es, today)
        c = dict(c, _due=due, _days=days, _why=why, _score=prior_score(c))
        if due:
            eligible_by_arm[c["arm"]].append(c)

    # Rank inside an arm: prior first, then staleness (never-polled ahead of
    # long-ago-polled), then id so the order is stable and reviewable.
    for arm in eligible_by_arm:
        eligible_by_arm[arm].sort(
            key=lambda c: (-c["_score"], -(c["_days"] if c["_days"] is not None else 10 ** 6),
                           str(c["id"])))

    draw, assigned = [], defaultdict(int)
    floor_unmet = []

    def take(arm, reason):
        pool = eligible_by_arm.get(arm) or []
        if assigned[arm] >= len(pool):
            return False
        pick = dict(pool[assigned[arm]])
        pick["draw_reason"] = reason
        assigned[arm] += 1
        draw.append(pick)
        return True

    # Phase 1: the exploration floor.
    for arm in ordered:
        for _ in range(floor):
            if len(draw) >= cadence:
                break
            if not take(arm, "exploration floor"):
                floor_unmet.append(arm)
                break

    # Phase 2: exploitation by observed hit-rate, highest first.
    while len(draw) < cadence:
        ranked = sorted(
            (a for a in ordered if assigned[a] < len(eligible_by_arm.get(a) or [])),
            key=lambda a: (-smoothed_rate((arms_state.get(a) or {}).get("hits", 0),
                                          (arms_state.get(a) or {}).get("polled", 0) + assigned[a]),
                           ordered.index(a)))
        if not ranked:
            break                      # pool exhausted; report it, never pad
        arm = ranked[0]
        rate = smoothed_rate((arms_state.get(arm) or {}).get("hits", 0),
                             (arms_state.get(arm) or {}).get("polled", 0))
        take(arm, f"exploit (hit-rate {rate:.2f})")

    return {
        "date": today.isoformat(),
        "cadence": cadence,
        "floor": floor,
        "arms": ordered,
        "draw": draw,
        "floor_unmet": floor_unmet,
        "short": len(draw) < cadence,
        "per_arm": {a: {"pool": len(by_arm[a]), "eligible": len(eligible_by_arm.get(a) or []),
                        "drawn": assigned[a],
                        "polled": (arms_state.get(a) or {}).get("polled", 0),
                        "hits": (arms_state.get(a) or {}).get("hits", 0)}
                    for a in ordered},
        "pool_total": len(candidates),
        "eligible_total": sum(len(v) for v in eligible_by_arm.values()),
    }


# ---------------------------------------------------------------------------
# Candidate construction — the impure half.
# ---------------------------------------------------------------------------
def open_question_tokens(vault):
    """Identifiers named in the LIVE Open_Questions.md: vault ids and FS PIDs.

    Deliberately identifier-based, not name-based. A name match over a 300 KB file
    would fire on every same-surname relative, and this signal only TILTS a draw —
    an imprecise tilt is worse than a narrow one. THE LIMITATION IS REAL AND
    STATED: a person mentioned in an open question by NAME ONLY is not detected
    here. Resolved questions are excluded (a different file), which is correct: a
    closed question is not a reason to re-poll.
    """
    path = os.path.join(vault, "Open_Questions.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return set()
    toks = set(re.findall(r"\bP-[0-9A-Za-z]{5,8}\b", text))
    toks |= set(re.findall(r"\b[A-Z0-9]{4}-[A-Z0-9]{3}\b", text))
    return toks


def build_candidates(vault, gen_lo=None, gen_hi=None, confidence=None, region=None):
    """The pollable population, arm-assigned.

    READ THROUGH THE SEAMS, NEVER BY REGEX. The census comes from
    harvest_sources.gather_records (which reads entries via person_store) and the
    person attributes from person_store.iter_people. ** An id is an opaque primary
    key here. ** A consumer that built an id regex from the documented Crockford
    grammar silently stranded 15 entries whose ids the live vault actually
    contains (mnemonic ids carrying `L`/`O`, one only five chars). Validating an
    id's shape is the integrity gate's job, not a consumer's.
    """
    os.environ.setdefault("AUTORESEARCH_VAULT", vault)
    import harvest_sources as H          # imported late: it resolves its vault at import
    import person_store as PS

    people = {r.id: r for r in PS.iter_people(vault) if r.id}
    oq = open_question_tokens(vault)
    out = []
    for rec in H.gather_records(gen_lo, gen_hi, confidence, region):
        p = people.get(rec["id"])
        # THE PRIVACY GATE, IN ONE PLACE. harvest_sources already re-categorizes
        # living/unknown to LIVING_EXCLUDED via the same function; this is the same
        # rule asked again at the point of use, not a second copy of it. Living and
        # unknown people are never polled, never probed, never queued.
        allowed, _why = privacy_gate.may_research(
            rec.get("life_status") if p is None else p.life_status)
        if not allowed or rec["category"] == "LIVING_EXCLUDED":
            continue

        ext = (p.external_ids if p else {}) or {}
        flags = (p.flags if p else []) or []
        # ARM ASSIGNMENT. An entry with no usable FS PID cannot be change-polled at
        # all — Recipe-S needs /tree/person/sources/{PID} — so it belongs to the
        # EXISTENCE arm, which asks a different question ("does a profile exist
        # yet?") on a different cadence. Everyone else takes their census category.
        arm = EXISTENCE_PROBE if not rec.get("pid") else rec["category"]
        q = next((str(f) for f in flags if re.match(r"Q\d+", str(f))), None)
        if not q and (rec["id"] in oq or (rec.get("pid") and rec["pid"] in oq)):
            q = "named in Open_Questions"
        out.append({
            "id": rec["id"],
            "pid": rec.get("pid"),
            "name": rec["name"],
            "gen": rec["gen"],
            "region": rec["region"],
            "category": rec["category"],
            "ark_count": rec["ark_count"],
            "confidence": rec["confidence"],
            "arm": arm,
            "open_question": q,
            "fs_state": ("pid" if rec.get("pid")
                         else str(ext.get("fs") or "absent").lower()),
            "has_wt": bool(ext.get("wt") or ext.get("wikitree")),
            "has_anc": bool(ext.get("anc") or ext.get("ancestry")),
        })
    return out


def probe_targets(cand, state, today):
    """Which platforms this drawn entry should ALSO be existence-probed on.

    Rides along on whatever the bandit drew, rather than forming its own arm, for
    a measured reason: `wt` and `anc` are ZERO vault-wide, so a "needs a wt probe"
    arm would be the entire vault and would swallow every slot. The FS existence
    question does have a bounded population, and that is the arm.
    """
    es = state.get("entries", {}).get(cand["id"], {})
    out = []
    for plat in PLATFORMS:
        have = {"fs": cand["fs_state"] == "pid",
                "wt": cand["has_wt"], "anc": cand["has_anc"]}[plat]
        if have:
            continue
        due, _days, why = probe_status(es, plat, today)
        if due:
            out.append((plat, why))
    return out


def resolve_cadence(config, pool_size):
    """The configured cadence, CLAMPED to ~1% of the live pool.

    "CADENCE ~1% = ~13 entries per session. Not negotiable upward." Enforced in
    code rather than trusted to a comment, and a clamp is REPORTED, never silent.
    """
    want = int(config.get("per_session") or DEFAULT_CADENCE)
    ceiling = max(1, round(pool_size * CADENCE_FRACTION))
    return min(want, ceiling), want, ceiling


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_draw(result, clamp_note=None):
    print("=== PROFILE-REVIEW ROTATION — DRAW (dry run; nothing written, no network) ===")
    print(f"date {result['date']}  cadence {result['cadence']}  "
          f"exploration floor {result['floor']}/arm  "
          f"pool {result['pool_total']}  eligible {result['eligible_total']}")
    if clamp_note:
        print(clamp_note)
    print()
    print(f"{'ARM':<16} {'pool':>6} {'elig':>6} {'drawn':>6} {'polled':>7} {'hits':>5} {'rate':>7}")
    for arm in result["arms"]:
        a = result["per_arm"][arm]
        rate = smoothed_rate(a["hits"], a["polled"])
        seen = f"{a['hits']}/{a['polled']}" if a["polled"] else "n=0"
        print(f"{arm:<16} {a['pool']:>6} {a['eligible']:>6} {a['drawn']:>6} "
              f"{a['polled']:>7} {a['hits']:>5} {rate:>6.2f} ({seen})")
    print()
    print("THE DRAW:")
    for i, c in enumerate(result["draw"], 1):
        ident = c["pid"] or f"={c['id']}"
        why = ", ".join(prior_reasons(c)) or "no prior boost"
        print(f"{i:>3}. [{c['arm']}] {ident:<10} {str(c['name'])[:42]:<42} "
              f"Gen {str(c['gen']):>3}  {c['region']}")
        print(f"      draw: {c['draw_reason']}; prior: {why}; cooldown: {c['_why']}")
        if c.get("probes"):
            print("      probe: " + "; ".join(f"{p} ({w})" for p, w in c["probes"]))
    print()
    if result["floor_unmet"]:
        print("** FLOOR UNMET for: " + ", ".join(result["floor_unmet"])
              + " — every candidate in that arm is inside its cooldown. "
                "Reported, NOT padded from another arm.")
    if result["short"]:
        print(f"** SHORT DRAW: {len(result['draw'])} of {result['cadence']} — "
              "the eligible pool is exhausted. No silent top-up.")
    if not result["floor_unmet"] and not result["short"]:
        print(f"FLOOR HELD: every one of the {len(result['arms'])} arms drew at least "
              f"{result['floor']}.")


def heartbeat(vault):
    """One line for the SessionStart audit suite. Reads state + config only — no
    census, so it stays cheap. Absent config => a silent 'not configured'."""
    cfg = load_config(vault)
    st = load_state(vault)
    arms = st.get("arms", {})
    polled = sum((a or {}).get("polled", 0) for a in arms.values())
    hits = sum((a or {}).get("hits", 0) for a in arms.values())
    entries = len(st.get("entries", {}))
    tally = f"lifetime {hits}/{polled} hits over {entries} entries"
    if not cfg:
        print(f"Profile-Review: not configured (no `{CONFIG_KEY}` block in "
              f"{MAINTENANCE_FILE}); {tally}")
        return 0
    iv = cfg.get("interval_days")
    last = parse_date(cfg.get("last_checked"))
    if last is None:
        print(f"Profile-Review: DUE-baseline (never run); {tally}. "
              "Run scripts/profile_review.py to draw the first slice.")
        return 0
    days = (date.today() - last).days
    due = iv is not None and days >= iv
    print(f"Profile-Review: last slice {days}d ago ({last.isoformat()}); "
          f"{'DUE' if due else 'OK'}({iv}d); {tally}"
          + ("" if not due else
             " — ACTION: run scripts/profile_review.py for the draw, poll it, "
             "--record each outcome, then --complete."))
    return 0


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------
def record(vault, state, person_id, outcome, arm=None, note=None, probed=(), today=None):
    """Record ONE polled entry's outcome.

    ** REWARD IS SUBSTANTIVE. ** A hit is a source we do not cite, a relationship
    we do not hold, a vital that corrects or sharpens ours, or anything that
    advances an Open Question. ** A SOURCE COUNT GOING UP IS NOT A HIT. ** The
    vault's ark_count counts records CITED; FS's "Sources (N)" counts sources
    ATTACHED. They measure different things, and a naive delta between them must
    never be read as "FS gained or lost sources" — the pilot's +125 delta was a
    WRITE-BACK queue, not a discovery.
    """
    today = today or date.today()
    if outcome not in ("hit", "miss"):
        raise SystemExit("profile_review: --outcome must be 'hit' or 'miss'")
    e = state["entries"].setdefault(person_id, {})
    e["last_polled"] = today.isoformat()
    e["outcome"] = outcome
    if arm:
        e["arm"] = arm
    if note:
        e["note"] = note
    for plat in probed:
        plat = plat.strip().lower()
        if plat not in PLATFORMS:
            raise SystemExit(f"profile_review: unknown probe platform {plat!r} "
                             f"(known: {', '.join(PLATFORMS)})")
        e[f"last_probed_{plat}"] = today.isoformat()
    a = state["arms"].setdefault(arm or e.get("arm") or "UNASSIGNED",
                                 {"polled": 0, "hits": 0})
    a["polled"] += 1
    if outcome == "hit":
        a["hits"] += 1
    state["history"].append({"date": today.isoformat(), "id": person_id,
                             "arm": arm or e.get("arm"), "outcome": outcome,
                             "note": note or ""})
    return state


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Profile-review rotation: allocate and record a ~1% slice.")
    ap.add_argument("--vault", help="Vault directory (else $AUTORESEARCH_VAULT).")
    ap.add_argument("--gen-range", help='Narrow the pool, e.g. "4-6".')
    ap.add_argument("--region", help="Narrow the pool by region substring.")
    ap.add_argument("--confidence", help="Narrow the pool by tier (S/M/Sp/U).")
    ap.add_argument("--cadence", type=int, help="Override the per-session draw size "
                                                "(still clamped to ~1%% of the pool).")
    ap.add_argument("--json", action="store_true", help="Machine-readable draw.")
    ap.add_argument("--heartbeat", action="store_true", help="SessionStart status line.")
    ap.add_argument("--record", metavar="VAULT_ID", help="Record one polled entry.")
    ap.add_argument("--outcome", choices=("hit", "miss"), help="With --record.")
    ap.add_argument("--arm", help="With --record: the arm it was drawn from.")
    ap.add_argument("--note", help="With --record: what was found (or not).")
    ap.add_argument("--probed", default="", help="With --record: platforms probed, "
                                                 "comma-separated (fs,wt,anc).")
    ap.add_argument("--complete", action="store_true",
                    help="Reset the cadence clock in .maintenance.json.")
    args = ap.parse_args()

    vault = vault_config.resolve_vault(args.vault)

    if args.heartbeat:
        return heartbeat(vault)

    state = load_state(vault)
    today = date.today()

    if args.record:
        if not args.outcome:
            raise SystemExit("profile_review: --record needs --outcome hit|miss")
        probed = [p for p in args.probed.split(",") if p.strip()]
        record(vault, state, args.record, args.outcome, arm=args.arm,
               note=args.note, probed=probed, today=today)
        path = save_state(vault, state)
        print(f"recorded {args.record}: {args.outcome}"
              + (f" (arm {args.arm})" if args.arm else "")
              + (f"; probed {', '.join(probed)}" if probed else "")
              + f" -> {os.path.basename(path)}")
        return 0

    if args.complete:
        p = os.path.join(vault, MAINTENANCE_FILE)
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
        if CONFIG_KEY not in cfg:
            raise SystemExit(f"profile_review: no `{CONFIG_KEY}` block in {p} to complete")
        cfg[CONFIG_KEY]["last_checked"] = today.isoformat()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"profile_review.last_checked = {today.isoformat()}")
        return 0

    gen_lo = gen_hi = None
    if args.gen_range:
        a, b = args.gen_range.split("-")
        gen_lo, gen_hi = int(a), int(b)
    candidates = build_candidates(vault, gen_lo, gen_hi, args.confidence, args.region)
    if not candidates:
        print("profile_review: no candidates (every entry filtered out or "
              "privacy-gated). Nothing drawn.")
        return 0

    cfg = load_config(vault)
    if args.cadence:
        cfg = dict(cfg, per_session=args.cadence)
    cadence, want, ceiling = resolve_cadence(cfg, len(candidates))
    clamp = (f"** cadence CLAMPED {want} -> {cadence}: ~{CADENCE_FRACTION:.0%} of a "
             f"{len(candidates)}-entry pool is {ceiling}. Not negotiable upward. **"
             if cadence < want else None)

    result = allocate(candidates, state, today=today, cadence=cadence)
    for c in result["draw"]:
        c["probes"] = probe_targets(c, state, today)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_draw(result, clamp)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
