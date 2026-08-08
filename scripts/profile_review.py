#!/usr/bin/env python3
"""profile_review.py — the profile-review ROTATION: a multi-armed bandit that
picks ~1.5% of the vault per session to re-check against FamilySearch, WikiTree and
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
no count in it), which is why the cadence is a small slice and not the whole
vault. Since 30 JUL 2026 a poll also reads the Research Help endpoints (record
hints / duplicates / data problems / not-a-match), so it costs more per person
and is worth more per person.
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
import person_store

SNAPSHOT_FILE = "profile_review_snapshots.json"
MAINTENANCE_FILE = ".maintenance.json"
CONFIG_KEY = "profile_review"

# ---------------------------------------------------------------------------
# Constants that encode a DECIDED rule. Each is here because changing it changes
# the design, not merely a default.
# ---------------------------------------------------------------------------
# THE SAMPLE RATE HAS THREE LAYERS, highest wins (added 30 JUL 2026 — the rate
# was a code constant, and "easily configurable" is not the same as "one line to
# edit in a script"):
#
#   1. --sample-percent X   per-SESSION override, one run only
#   2. `sample_percent` in .maintenance.json `profile_review`   the standing rate
#   3. DEFAULT_SAMPLE_PERCENT below                             no-config fallback
#
# ** WHAT THE CLAMP MEANS, AND A CORRECTION TO WHY IT EXISTED. **
#
# This comment used to read: it was "not negotiable upward" (operator, 28 JUL
# 2026). ** THE OPERATOR NEVER SAID THAT. ** Traced 30 JUL 2026 to vault commit
# ab39581, where what they actually wrote was:
#
#     "These activities are expensive - I'm ok with a SLOW BURN, PERHAPS 1% of
#      the vault with each session."
#
# A hedged preference — "I'm ok with", "perhaps". In the SAME commit a session
# wrote "Not negotiable upward" into the spec and "OPERATOR SET THE CADENCE AT
# 1%" into the Research_Log, and from there it hardened at every hop: quoted as
# an operator rule in this file, restated in resolve_cadence's docstring and
# twice in Operating_Protocol, and finally ENFORCED IN CODE as a clamp that
# refused to let the rate rise. On 30 JUL the operator asked to raise it and hit
# a machine guard invented on their behalf.
#
# The clamp is still worth having, on its own merits and stated in its own voice:
# nothing should exceed the standing rate SILENTLY or BY ACCIDENT, because the FS
# half costs a page visit per person. So an absolute count (`--cadence N`, or
# `per_session` in config)
# is still clamped DOWN to the effective rate's ceiling and the clamp is reported.
# An explicit `--sample-percent` is a deliberate act by the operator for one
# session, so it is HONORED even above the standing rate — and announced, with the
# standing rate named, so an override can never be mistaken for the norm.
#
# History: 1% (28 JUL 2026) -> 1.5% (30 JUL 2026). It moved because the rotation
# was fixed that day (it had never rotated — the draw printed one key, the
# cooldown read another) and because a poll now reads a SECOND surface (Research
# Help), so each person costs more and yields more.
#
# DEFAULT_CADENCE is only the no-vault fallback for allocate()'s signature.
DEFAULT_SAMPLE_PERCENT = 1.5
DEFAULT_CADENCE = 20
# Back-compat alias: the fraction form of the default rate.
CADENCE_FRACTION = DEFAULT_SAMPLE_PERCENT / 100.0
# At least one entry from EVERY arm, every session. The anti-assumption device.
EXPLORATION_FLOOR = 1

# deferred 42 (operator, 03 AUG 2026) — OPPORTUNISTIC AUDIT, not a campaign.
# A raw locator list overstates a person's OWN records because limbs (g) and (h)
# (children's and siblings' records) are most of a typical FS Sources tab; measured
# inflation ran 4x-23x across five people. The backlog is deliberately NOT swept.
# But a drawn row is different: the poll opens the Sources tab regardless, and the
# event descriptor sits in the same citation string as the collection title — so
# the regrouping costs nothing WHILE THE PAGE IS OPEN and is unrecoverable after
# (a bare ARK already in the vault carries no descriptor at all).
#
# 4 is the WELL_SOURCED threshold itself: below it there is nothing to inflate.
AUDIT_ARK_FLOOR = 4


def needs_ark_grouping_audit(pid, ark_count):
    """Should this DRAWN row have its locators re-grouped by event while open?

    ONE home for the predicate so the printed draw, the `--json` payload and the
    test cannot drift apart. Two conditions, and both are load-bearing:
      * a live PID  -- no Sources tab to open without one, so nothing to audit;
      * >= AUDIT_ARK_FLOOR cited ARKs -- below the WELL_SOURCED threshold there is
        no count worth inflating.
    """
    return bool(pid) and (ark_count or 0) >= AUDIT_ARK_FLOOR
# No exploitation on a tiny sample: an arm with fewer than this many COMPLETED
# polls is filled by exploration (least-sampled first), never by its hit-rate.
# The code-side enforcement of the protocol's "do not tune on n<=3" rule.
MIN_EXPLOIT_SAMPLES = 5
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
# ROUTE RETIREMENT — the two STRUCTURAL arms ask a different question.
#
# For every other arm the poll is "has anything NEW appeared on FamilySearch?".
# For these two it cannot be, because the whole point of the category is that
# FamilySearch is not where this person's evidence lives: BOOK_SOURCED cites
# scholarly apparatus, and UNCITED's own documented route is a LIBRARY pass.
# Polling them against FS asks a question whose answer is known in advance.
#
# ** MEASURED, WHICH IS WHY THIS EXISTS (07 AUG 2026, deferred 51 + Q157). **
# These two arms hit 0.17 and 0.15 against 0.43-0.48 for every other arm, while
# holding 355 of the 1,386 rotation pool -- 26%. The vault was declaring "FS will
# never document this person" and then polling FS for them, about one poll in
# four. Two rows were re-polled in a single sitting for exactly that reason.
#
# So (operator ruling, deferred 51 decision 1) the poll for these arms becomes
# "is the non-FS route NAMED on this entry?" -- a row carrying `route` has
# answered it and RETIRES; a row without one stays, and NAMING the route is the
# disposition that retires it.
#
# ⚠ THE RETIREMENT IS PERMANENT FOR THESE ARMS, AND DELIBERATELY SO. `route` is
# a standing declaration about WHERE THE EVIDENCE IS, not a dated negative like
# `fs_probed`, so it does not expire and no cooldown applies to it. If the route
# is later worked and the person becomes sourceable here, their CATEGORY changes
# and they re-enter the rotation through a different arm on their own.
#
# ⛔ `fs_probed` DELIBERATELY DOES NOT GATE HERE. It is a DATED point-in-time
# reading ("FS held no records on this day"), which is a cooldown-shaped fact,
# not a retirement-shaped one. Conflating the two would make a stale probe look
# permanent. (It DOES suppress in IMPROVE's SOURCE_GAP pool -- deferred 58 -- which
# is a different question: "is this a prime harvest target today", not "is this
# settled for ever". Two jobs, one key; do not unify them.)
#
# ⚠ `fs_absent` IS DIFFERENT AGAIN AND IT *DOES* GATE, via the EXISTENCE_PROBE
# COOLDOWN rather than by retiring (deferred 56 option 2). `fs_probed` = the sources
# were read and are empty; `fs_absent` = no profile exists at all. A row may carry
# both. `fs_absent` does NOT suppress in IMPROVE: FamilySearch having no profile is
# silent about whether an archive or a register does.
ROUTE_RETIRING_ARMS = ("BOOK_SOURCED", "UNCITED")


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


def probe_status(entry_state, platform, today, cooldown=PROBE_COOLDOWN_DAYS,
                 record_date=None):
    """(due, days_since_or_None, reason) for the ~365d EXISTENCE probe.

    ** AN UNDATED NEGATIVE IS EXPIRED ON SIGHT. ** `fs: none` means "searched
    FamilySearch, confirmed absent" and it carries NO DATE, so a profile created
    since that search makes it silently wrong and nothing ever expires it. The same
    will be true of any wt/anc negative the moment one is written. The fix is not
    to trust the token: an absent probe date reads as due, always.

    ** `record_date` IS THE `fs_absent` KEY (deferred 56 option 2, 08 AUG 2026). **
    Before it, the ONLY date lived in the rotation state file, so a probe recorded by
    a session that never ran `--record` was invisible, and 13 `fs: none` rows returned
    every cycle for ever. Putting the date ON THE RECORD is the same choice `route`
    and `fs_probed` made, for the same reason: the knowledge is visible to anyone
    reading the entry, not just to the arm's state file.

    ⚠ **The MORE RECENT of the two wins.** They are independent observations -- the
    state file records when the ROTATION last polled, the key records when a HUMAN
    last verified absence -- and taking the newer is the only reading that cannot
    resurrect a settled row or silence a freshly-created profile.
    """
    d = parse_date((entry_state or {}).get(f"last_probed_{platform}"))
    r = parse_date(record_date)
    if r and (d is None or r > d):
        d, src = r, f"`{platform}_absent` on the record"
    elif d is not None:
        src = "the rotation state"
    if d is None:
        return True, None, f"no dated {platform} probe (undated negative = expired on sight)"
    days = (today - d).days
    return (days >= cooldown), days, f"{platform}-probed {days}d ago per {src} (cooldown {cooldown}d)"


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
    retired_by_route = defaultdict(int)
    for c in candidates:
        by_arm[c["arm"]].append(c)
        es = entries_state.get(c["id"], {})
        if c["arm"] == EXISTENCE_PROBE:
            # deferred 56 option 2: the record's own `fs_absent` date counts as a
            # probe, so a verified absence no longer depends on somebody having run
            # `--record` in the same sitting.
            due, days, why = probe_status(es, "fs", today,
                                          record_date=c.get("fs_absent"))
        else:
            due, days, why = poll_status(es, today)
        # ROUTE RETIREMENT (see ROUTE_RETIRING_ARMS above). Applied AFTER the
        # cooldown so the two reasons cannot be confused in `_why`, and applied
        # UNCONDITIONALLY rather than only to due rows -- a declared row is never
        # due for this arm again, so the count is a stable "how many of this arm
        # are settled" rather than a per-draw artefact of who happened to be cold.
        if c["arm"] in ROUTE_RETIRING_ARMS and c.get("route"):
            due = False
            why = f"route declared ({c['route']}) — this arm's poll is answered"
            retired_by_route[c["arm"]] += 1
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

    # Phase 2: exploitation by observed hit-rate, highest first — but NEVER on a
    # tiny sample. The protocol has said from day one "do not tune the allocation
    # on one session of data / leave the bandit weights alone (n<=3)", yet the
    # first version enforced that rule on the HUMAN and ignored it in the CODE:
    # a 3-for-3 arm drew 46% of the very next session's slots. Now an arm whose
    # OBSERVED n (completed polls, not this session's assignments) is below
    # MIN_EXPLOIT_SAMPLES is not exploitable on its rate; while any such arm has
    # eligible candidates, remaining slots go to the least-sampled of them
    # (counting this session's assignments, so the fill spreads). Only when every
    # available arm has a real sample does the loop exploit. (29 JUL 2026)
    while len(draw) < cadence:
        avail = [a for a in ordered if assigned[a] < len(eligible_by_arm.get(a) or [])]
        if not avail:
            break                      # pool exhausted; report it, never pad
        def _polled(a):
            return (arms_state.get(a) or {}).get("polled", 0)
        undersampled = [a for a in avail if _polled(a) < MIN_EXPLOIT_SAMPLES]
        if undersampled:
            arm = min(undersampled,
                      key=lambda a: (_polled(a) + assigned[a], ordered.index(a)))
            take(arm, f"explore (n={_polled(arm)} < {MIN_EXPLOIT_SAMPLES})")
            continue
        arm = min(avail,
                  key=lambda a: (-smoothed_rate((arms_state.get(a) or {}).get("hits", 0),
                                                _polled(a) + assigned[a]),
                                 ordered.index(a)))
        # The printed rate is the SELECTION score (denominator includes this
        # session's assignments). The first version recomputed it without
        # `assigned`, so slots 2..n printed a stale rate — the draw lied about
        # its own reasoning. (29 JUL 2026)
        rate = smoothed_rate((arms_state.get(arm) or {}).get("hits", 0),
                             _polled(arm) + assigned[arm])
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
                        "retired_by_route": retired_by_route.get(a, 0),
                        "polled": (arms_state.get(a) or {}).get("polled", 0),
                        "hits": (arms_state.get(a) or {}).get("hits", 0)}
                    for a in ordered},
        "pool_total": len(candidates),
        "eligible_total": sum(len(v) for v in eligible_by_arm.values()),
        "retired_by_route_total": sum(retired_by_route.values()),
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
            # deferred 41: a `~`-prefixed PID is a REJECTED profile, reported as
            # its own state so an EXISTENCE_PROBE row says "already looked, and
            # declined" rather than the "tbd"/"absent" that invites a re-search.
            "fs_state": ("pid" if rec.get("pid")
                         else {"rejected": "rejected", "unknown": "tbd"}.get(
                             person_store.external_id_state(ext.get("fs")),
                             str(ext.get("fs") or "absent").lower())),
            "has_wt": bool(ext.get("wt") or ext.get("wikitree")),
            "has_anc": bool(ext.get("anc") or ext.get("ancestry")),
            # Q157 / deferred 51: the standing declaration "this person IS
            # sourceable, just not here". Read through the seam, never by regex --
            # an unrecognised slug must be RETURNED, not swallowed, or a
            # declaration fails silently and the row is polled for ever.
            "route": (person_store.route(p) if p else None),
            # Recorded but NOT gating (see ROUTE_RETIRING_ARMS): a dated negative
            # is cooldown-shaped, not retirement-shaped. Carried so a draw can
            # SHOW that FS was already read, without that fact retiring anything.
            "fs_probed": (person_store.fs_probed(p) if p else None),
            # deferred 56 option 2: DATED "no profile exists". Unlike `fs_probed`
            # this one DOES gate -- it feeds the EXISTENCE_PROBE cooldown above,
            # which is the whole point of the key. ⚠ It is cooldown-shaped, NOT
            # retirement-shaped: it expires, so a profile created later is still
            # found.
            "fs_absent": (person_store.fs_absent(p) if p else None),
            # deferred 42 (operator, 03 AUG 2026): the WELL_SOURCED backlog is NOT
            # audited as a campaign -- but a row DRAWN here is audited on the spot,
            # because the poll opens the Sources tab anyway and the event descriptors
            # are free only while it is open. A bare ARK in the vault carries none.
            "audit_ark_grouping": needs_ark_grouping_audit(rec.get("pid"), rec["ark_count"]),
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


def resolve_sample_percent(config, override=None):
    """The effective rate for this run, and WHERE it came from.

    Precedence: `override` (per-session CLI) > config `sample_percent` (standing)
    > DEFAULT_SAMPLE_PERCENT. Returns (percent, source, standing_percent) so the
    caller can say which layer won and what the standing rate is — an override
    that is not announced is indistinguishable from a changed setting.
    """
    raw = config.get("sample_percent")
    try:
        standing = float(raw) if raw is not None else DEFAULT_SAMPLE_PERCENT
    except (TypeError, ValueError):
        standing = DEFAULT_SAMPLE_PERCENT
    if standing <= 0:
        standing = DEFAULT_SAMPLE_PERCENT
    if override is None:
        src = "config" if raw is not None else "default"
        return standing, src, standing
    pct = float(override)
    if pct <= 0:
        raise SystemExit("profile_review: --sample-percent must be > 0")
    return pct, "session-override", standing


def resolve_cadence(config, pool_size, sample_percent=None):
    """Size the slice: a fraction of the LIVE pool, tracked, with the ceiling
    enforced in code and any clamp REPORTED rather than applied silently.

    ⚠ 1% was a TARGET, not merely a ceiling (corrected 29 JUL 2026): the first
    version read `per_session` and used the live rate only as a clamp, so the draw
    would have stayed at a snapshot value forever as the vault grew — scaling DOWN
    but never UP. An ABSENT/null `per_session` means "track the live pool at the
    effective rate" (the recommended config); an explicit number is honored as a
    smaller override and still clamped.

    `sample_percent` is the already-resolved effective rate (see
    resolve_sample_percent); None means "use the code default".
    """
    pct = DEFAULT_SAMPLE_PERCENT if sample_percent is None else float(sample_percent)
    ceiling = max(1, round(pool_size * pct / 100.0))
    raw = config.get("per_session")
    want = int(raw) if raw else ceiling
    return min(want, ceiling), want, ceiling


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_draw(result, clamp_note=None, rate=None):
    print("=== PROFILE-REVIEW ROTATION — DRAW (dry run; nothing written, no network) ===")
    # `rate` = (percent, source). Shown because the slice size is meaningless
    # without it: 20 could be the standing rate or a one-off override.
    rate_s = f"  rate {rate[0]:g}% ({rate[1]})" if rate else ""
    print(f"date {result['date']}  cadence {result['cadence']}{rate_s}  "
          f"exploration floor {result['floor']}/arm  "
          f"pool {result['pool_total']}  eligible {result['eligible_total']}")
    if clamp_note:
        print(clamp_note)
    print()
    print(f"{'ARM':<16} {'pool':>6} {'rtrd':>5} {'elig':>6} {'drawn':>6} "
          f"{'polled':>7} {'hits':>5} {'rate':>7}")
    for arm in result["arms"]:
        a = result["per_arm"][arm]
        rate = smoothed_rate(a["hits"], a["polled"])
        seen = f"{a['hits']}/{a['polled']}" if a["polled"] else "n=0"
        ret = a.get("retired_by_route", 0)
        print(f"{arm:<16} {a['pool']:>6} {(ret or '-'):>5} {a['eligible']:>6} {a['drawn']:>6} "
              f"{a['polled']:>7} {a['hits']:>5} {rate:>6.2f} ({seen})")
    if result.get("retired_by_route_total"):
        print()
        print(f"  rtrd = RETIRED BY A DECLARED `route` ({result['retired_by_route_total']} "
              f"across {', '.join(ROUTE_RETIRING_ARMS)}). For these two arms the poll is")
        print("  \"is the non-FS route NAMED?\", so a declared row has answered it and is out.")
        print("  ** A RISE IN THESE ARMS' HIT RATE FROM HERE IS MECHANICAL, NOT THE LANE")
        print("  IMPROVING ** -- what is left is the undeclared remainder, which is the real")
        print("  work. Do not read it as evidence in the ROTATE arm-selection decision.")
    print()
    print("THE DRAW:")
    for i, c in enumerate(result["draw"], 1):
        ident = c["pid"] or f"={c['id']}"
        why = ", ".join(prior_reasons(c)) or "no prior boost"
        print(f"{i:>3}. [{c['arm']}] {ident:<10} {str(c['name'])[:42]:<42} "
              f"Gen {str(c['gen']):>3}  {c['region']}")
        print(f"      draw: {c['draw_reason']}; prior: {why}; cooldown: {c['_why']}")
        if c.get("audit_ark_grouping"):
            print(f"      ** AUDIT ({c['ark_count']} ARKs): re-group by EVENT before trusting the count "
                  f"(deferred 42) **")
            print("         limbs (g)+(h) — children's and siblings' records — are most of a typical")
            print("         Sources tab; measured inflation ran 4x-23x. You are opening this profile")
            print("         anyway, which is the only moment the event descriptors are free.")
        if c.get("probes"):
            print("      probe: " + "; ".join(f"{p} ({w})" for p, w in c["probes"]))
    print()
    if result["floor_unmet"]:
        # ** THE REASON IS PART OF THE MESSAGE, AND THERE ARE NOW TWO OF THEM. **
        # This line used to assert "every candidate is inside its cooldown" for
        # every unmet arm. Once `route` retirement landed that became false: an arm
        # can be unmet because its rows are temporarily COLD (it returns next
        # session) or because they are permanently DECLARED (it does not). Reporting
        # a settled arm as a cold one invites somebody to go looking for a rotation
        # bug that is not there -- so the cause is computed per arm, never assumed.
        parts = []
        for arm in result["floor_unmet"]:
            a = result["per_arm"][arm]
            ret, poolsz = a.get("retired_by_route", 0), a["pool"]
            if ret and ret >= poolsz:
                parts.append(f"{arm} (all {poolsz} DECLARED — settled, not cold; "
                             f"this arm is complete and will not return)")
            elif ret:
                parts.append(f"{arm} ({ret} of {poolsz} declared, the rest in cooldown)")
            else:
                parts.append(f"{arm} (every candidate inside its cooldown)")
        print("** FLOOR UNMET for: " + "; ".join(parts)
              + ". Reported, NOT padded from another arm.")
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
    # ** interval_days 0 MEANS EVERY SESSION, and it is spelled 0 because "per
    # session" IS NOT A TIME INTERVAL. ** The spec's cadence is "a fraction of the vault
    # per session"; a session is not a day, and several can happen in one day (or
    # one across two). A positive interval silently converts a per-session
    # obligation into a per-calendar one and the loop then skips sessions --
    # which is exactly what a 7-day value did on the day this shipped.
    # Rendered in words, not as "DUE(0d)", so nobody later "fixes" the 0.
    cadence = "every session" if iv == 0 else f"{iv}d"
    print(f"Profile-Review: last slice {days}d ago ({last.isoformat()}); "
          f"{'DUE' if due else 'OK'} ({cadence}); {tally}"
          + ("" if not due else
             " — ACTION: run scripts/profile_review.py for the draw, poll it, "
             "--record each outcome, then --complete."))
    return 0


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------
def resolve_person_key(vault, person_id, candidates=None):
    """Normalize whatever the operator typed into the VAULT id the draw keys on.

    ** THE DRAW DISPLAYS `pid`, THE COOLDOWN READS `id`, AND THAT MISMATCH SILENTLY
    BROKE THE ROTATION FOR SEVEN WEEKS (found 30 JUL 2026, session #117). ** The
    draw prints `c["pid"] or "=" + c["id"]` — so for anyone with a FamilySearch
    profile the line the reader copies is the **FS PID**, while `allocate()` looks
    up `entries_state.get(c["id"])`, the `P-xxxxxx` vault id. Recording by the
    displayed identifier therefore wrote a key nothing ever read: the entry never
    entered its 180-day cooldown, and the SAME people were re-drawn every session.

    It was invisible because the *arms* were updated correctly either way, so the
    bandit's hit-rates and the `polled` counts all advanced and the report looked
    healthy. On this vault 11 of 26 records had landed on FS-PID keys, and session
    #116's 13-person slice put only 2 entries into cooldown — the next session's
    draw re-issued eight people whose work was already done and written up.

    Accepting BOTH spellings is the fix, rather than telling the reader to type a
    different identifier than the one printed: an interface that displays one key
    and demands another will keep producing this bug.
    """
    if not person_id or person_id.startswith("P-"):
        return person_id
    if candidates is None:
        try:
            candidates = build_candidates(vault)
        except Exception:                                    # pragma: no cover
            return person_id
    for c in candidates:
        if c.get("pid") and str(c["pid"]).upper() == person_id.upper():
            return c["id"]
    return person_id


def record(vault, state, person_id, outcome, arm=None, note=None, probed=(), today=None):
    """Record ONE polled entry's outcome.

    ** REWARD IS SUBSTANTIVE. ** A hit is a source we do not cite, a relationship
    we do not hold, a vital that corrects or sharpens ours, or anything that
    advances an Open Question. ** A SOURCE COUNT GOING UP IS NOT A HIT. ** The
    vault's ark_count counts records CITED; FS's "Sources (N)" counts sources
    ATTACHED. They measure different things, and a naive delta between them must
    never be read as "FS gained or lost sources" — the pilot's +125 delta was a
    WRITE-BACK queue, not a discovery.

    `person_id` may be either the vault `P-xxxxxx` id or the FS PID the draw
    prints; see `resolve_person_key`.
    """
    today = today or date.today()
    if outcome not in ("hit", "miss"):
        raise SystemExit("profile_review: --outcome must be 'hit' or 'miss'")
    person_id = resolve_person_key(vault, person_id)
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
        description="Profile-review rotation: allocate and record a ~1.5% slice.")
    ap.add_argument("--vault", help="Vault directory (else $AUTORESEARCH_VAULT).")
    ap.add_argument("--gen-range", help='Narrow the pool, e.g. "4-6".')
    ap.add_argument("--region", help="Narrow the pool by region substring.")
    ap.add_argument("--confidence", help="Narrow the pool by tier (S/M/Sp/U).")
    ap.add_argument("--sample-percent", "--pct", type=float, dest="sample_percent",
                    metavar="X",
                    help="Sample X%% of the pool THIS RUN ONLY (e.g. --pct 3). Overrides "
                         "the standing `sample_percent` in .maintenance.json and is "
                         "announced in the output. The standing rate is the config key; "
                         "this flag does not change it.")
    ap.add_argument("--cadence", type=int, help="Override the per-session draw size "
                                                "(still clamped to CADENCE_FRACTION of the pool).")
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
    ap.add_argument("--migrate-keys", action="store_true",
                    help="One-time repair: re-key any entry recorded under an FS PID "
                         "to its vault id, so its cooldown is actually read. "
                         "Dry-run unless --apply.")
    ap.add_argument("--apply", action="store_true", help="With --migrate-keys: write.")
    args = ap.parse_args()

    vault = vault_config.resolve_vault(args.vault)

    if args.heartbeat:
        return heartbeat(vault)

    state = load_state(vault)
    today = date.today()

    if args.migrate_keys:
        cands = build_candidates(vault)
        moved, collided = [], []
        for key in [k for k in list(state["entries"]) if not k.startswith("P-")]:
            vid = resolve_person_key(vault, key, candidates=cands)
            if vid == key:
                collided.append((key, "no vault id found in the pool"))
                continue
            if vid in state["entries"]:
                # Both spellings recorded: keep the LATER poll date, do not lose one.
                a, b = state["entries"][vid], state["entries"][key]
                keep = b if (b.get("last_polled") or "") > (a.get("last_polled") or "") else a
                merged = {**a, **b, **keep}
                if args.apply:
                    state["entries"][vid] = merged
                    del state["entries"][key]
                moved.append((key, vid, "merged with existing vault-id record"))
                continue
            if args.apply:
                state["entries"][vid] = state["entries"].pop(key)
            moved.append((key, vid, "re-keyed"))
        for k, v, how in moved:
            print(f"  {k:<12} -> {v:<10} {how}")
        for k, why in collided:
            print(f"  {k:<12} !! LEFT AS-IS: {why}")
        print(f"\n{'APPLIED' if args.apply else 'DRY-RUN'}: "
              f"{len(moved)} re-keyed, {len(collided)} left as-is "
              f"(arms/history are unchanged — only the cooldown lookup was broken).")
        if args.apply:
            print(f"wrote {os.path.basename(save_state(vault, state))}")
        else:
            print("re-run with --apply to write.")
        return 0

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
    pct, pct_src, standing = resolve_sample_percent(cfg, args.sample_percent)
    cadence, want, ceiling = resolve_cadence(cfg, len(candidates), pct)
    clamp = (f"** cadence CLAMPED {want} -> {cadence}: ~{pct:g}% of a "
             f"{len(candidates)}-entry pool is {ceiling}. Raise the rate with "
             f"--pct X (this run) or `sample_percent` in .maintenance.json. **"
             if cadence < want else None)
    if pct_src == "session-override":
        # ** stderr, NOT stdout. ** --json is a machine contract (session_plan
        # parses it); a banner on stdout broke it, and session_plan's except
        # turned the parse error into "ROTATE 0 candidates" — a tool failure
        # rendered as an empty worklist. The JSON carries sample_percent +
        # sample_percent_source, so nothing is lost to a machine reader.
        print(f"** SAMPLE RATE OVERRIDDEN FOR THIS RUN: {pct:g}% (standing rate "
              f"{standing:g}%) -> {cadence} entries, not {max(1, round(len(candidates) * standing / 100.0))}. "
              f"This does NOT change the standing rate; edit `sample_percent` in "
              f"{MAINTENANCE_FILE} for that. **", file=sys.stderr)

    result = allocate(candidates, state, today=today, cadence=cadence)
    for c in result["draw"]:
        c["probes"] = probe_targets(c, state, today)

    if args.json:
        # Carry the effective rate + which layer set it, so a machine reader
        # (session_plan) sees the same provenance the human banner states.
        result = dict(result, sample_percent=pct, sample_percent_source=pct_src,
                      standing_sample_percent=standing)
        print(json.dumps(result, indent=2, default=str))
    else:
        print_draw(result, clamp, rate=(pct, pct_src))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
