#!/usr/bin/env python3
"""gdate.py — the GEDCOM 7 `DateValue` grammar, in one place.

spec/structured-dates Spec 02. A LEAF module: pure standard library, no I/O, no
vault access, no imports from the rest of the toolkit. Every consumer that needs
to know whether a string is a date, or what year to compare it by, imports this
instead of writing its own year regex.

WHY IT EXISTS. Three separate regexes used to guess years out of prose and they
disagreed: `person_store._parse_vitals`, `harvest_pids.YEAR_RE` (feeding
`dup_name_audit`) and `prose_audit.YEAR_RE`. Two carried a **1500 floor**
(`1[5-9]\\d{2}|20[0-2]\\d`), so no medieval person could be year-checked at all —
105 of 157 Magna Carta rows had empty vitals, and two entirely different people
named "Henry I" (England 1068-1135, France 1008-1060) were invisible to duplicate
detection. Here a year is a year: `954` parses exactly like `1954`, so that class
of bug is impossible by construction.

THE GRAMMAR (FamilySearch GEDCOM 7.0, https://gedcom.io/specifications/FamilySearchGEDCOMv7.html):

    DateValue  = date | DatePeriod | dateRange | dateApprox
    date       = [calendar D] [[day D] month D] year [D epoch]
    dateApprox = (ABT | CAL | EST) D date
    dateRange  = BET D date D AND D date | AFT D date | BEF D date
    DatePeriod = FROM D date [D TO D date] | TO D date
    calendar   = GREGORIAN | JULIAN | FRENCH_R | HEBREW      (absent = GREGORIAN)
    epoch      = BCE

Modifier semantics are the spec's, and the distinctions matter here:

    ABT   near x, exact unknown          ~1750, c.985
    EST   near x, and x is CALCULATED    declarant-age birth estimates (the vault's
                                         +/-2-12 yr class; CLAUDE.method.md insists
                                         these are estimates, not facts — EST puts
                                         that in the data instead of a prose caveat)
    CAL   x is calculated from other data  age-at-death arithmetic
    BEF / AFT   no later / no earlier than x
    BET…AND     between two bounds
    FROM…TO     lasted across a span     floruit approximations

TWO DIALS, ON PURPOSE:

    is_valid   is STRICT. GEDCOM 7 keywords and months are uppercase, and that is
               what a stored value must be. Lowercase `abt 1750` is NOT valid.
    normalise  is LENIENT. It is the migration path from legacy prose INTO the
               strict form, and it never guesses: when it cannot produce a value
               that `is_valid` accepts, it returns None rather than an invention.

ONE DELIBERATE EXTENSION beyond the grammar: `is_valid` also accepts a bare ISO
`YYYY-MM-DD`. That is the Spec 03 option-(A) decision — the file model's existing
`born`/`died` keys are ISO-shaped upstream, and widening the same key pair beats
carrying two representations of one fact. `normalise` converts ISO to GEDCOM form,
so newly written values are GEDCOM, while every ISO value already on disk stays
readable.

NOT IN SCOPE: calendar arithmetic, Julian<->Gregorian conversion, `datetime`
objects. This module reasons about NOTATION, not time. It cannot tell you how many
days apart two dates are, and it should never learn to.
"""
from __future__ import annotations

import re

__all__ = [
    "is_valid", "year", "year_range", "is_day_precise", "normalise", "split_dual_year",
    "CALENDARS", "MONTHS",
]

# --- vocabulary ----------------------------------------------------------- #

CALENDARS = ("GREGORIAN", "JULIAN", "FRENCH_R", "HEBREW")

_MONTHS_GREG = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_MONTHS_HEBREW = ("TSH", "CSH", "KSL", "TVT", "SHV", "ADR", "ADS",
                  "NSN", "IYR", "SVN", "TMZ", "AAV", "ELL")
_MONTHS_FRENCH = ("VEND", "BRUM", "FRIM", "NIVO", "PLUV", "VENT",
                  "GERM", "FLOR", "PRAI", "MESS", "THER", "FRUC", "COMP")
MONTHS = {
    "GREGORIAN": _MONTHS_GREG,
    "JULIAN": _MONTHS_GREG,
    "HEBREW": _MONTHS_HEBREW,
    "FRENCH_R": _MONTHS_FRENCH,
}
_ALL_MONTHS = _MONTHS_GREG + _MONTHS_HEBREW + _MONTHS_FRENCH

_CAL_ALT = "|".join(CALENDARS)
# Longest-first so FRUC does not shadow FRIM etc. and 4-char tokens win over 3.
_MON_ALT = "|".join(sorted(_ALL_MONTHS, key=len, reverse=True))

# `date = [calendar D] [[day D] month D] year [D epoch]`. A day without a month is
# NOT a date — the grammar nests them, and the regex keeps that nesting.
_DATE = (
    rf"(?:(?P<cal>{_CAL_ALT})\s+)?"
    rf"(?:(?:(?P<day>\d{{1,2}})\s+)?(?P<mon>{_MON_ALT})\s+)?"
    r"(?P<year>\d{1,4})"
    r"(?:\s+(?P<epoch>BCE))?"
)


def _d(suffix):
    """The date production with its group names suffixed, so several copies can
    live in one pattern (`BET <date> AND <date>`)."""
    return re.sub(r"\(\?P<(\w+)>", lambda m: f"(?P<{m.group(1)}{suffix}>", _DATE)


# Alternatives are tried in order and the LONGEST anchored match wins, so
# `BET 1816 AND 1823` is read as a range and not as the bare date `1816`.
_PRODUCTIONS = (
    ("range_bet", rf"BET\s+{_d('_a')}\s+AND\s+{_d('_b')}"),
    ("period_fromto", rf"FROM\s+{_d('_a')}\s+TO\s+{_d('_b')}"),
    ("period_from", rf"FROM\s+{_d('_a')}"),
    ("period_to", rf"TO\s+{_d('_a')}"),
    ("range_bef", rf"BEF\s+{_d('_a')}"),
    ("range_aft", rf"AFT\s+{_d('_a')}"),
    ("approx", rf"(?P<approx>ABT|CAL|EST)\s+{_d('_a')}"),
    ("iso", r"(?P<iso_y>\d{4})-(?P<iso_m>\d{2})-(?P<iso_d>\d{2})"),
    ("date", _d("_a")),
)
_COMPILED = [(kind, re.compile(rf"\A\s*(?:{pat})")) for kind, pat in _PRODUCTIONS]


def _check_date_part(m, suffix):
    """Semantic checks the regex cannot express: day range, and month-belongs-to-
    calendar. Returns True when the part is absent or well formed."""
    yr = m.group(f"year{suffix}")
    if yr is None:
        return True
    day = m.group(f"day{suffix}")
    if day is not None and not (1 <= int(day) <= 31):
        return False
    mon = m.group(f"mon{suffix}")
    if mon is not None:
        cal = m.group(f"cal{suffix}") or "GREGORIAN"
        if mon not in MONTHS[cal]:
            return False
    if m.group(f"epoch{suffix}") and (m.group(f"cal{suffix}") or "GREGORIAN") not in \
            ("GREGORIAN", "JULIAN"):
        return False
    return True


def _parse(value):
    """Longest valid DateValue anchored at the START of `value`.
    Returns (kind, match, end_offset) or None. `end_offset` indexes into `value`."""
    if value is None:
        return None
    s = str(value)
    best = None
    for kind, rx in _COMPILED:
        m = rx.match(s)
        if not m:
            continue
        if kind != "iso":
            if not _check_date_part(m, "_a"):
                continue
            if m.groupdict().get("year_b") is not None and not _check_date_part(m, "_b"):
                continue
        elif not (1 <= int(m.group("iso_m")) <= 12 and 1 <= int(m.group("iso_d")) <= 31):
            continue
        if best is None or m.end() > best[2]:
            best = (kind, m, m.end())
    return best


def is_valid(value):
    """True when `value` is a complete GEDCOM 7 DateValue (or a bare ISO date).

    STRICT: keywords and months must be uppercase, and nothing may trail the
    value. Use `normalise` to get here from legacy prose."""
    if value is None:
        return False
    s = str(value).strip()
    if not s:
        return False
    got = _parse(s)
    return got is not None and got[2] == len(s)


def _year_of(m, suffix):
    yr = m.group(f"year{suffix}")
    if yr is None:
        return None
    y = int(yr)
    return -y if m.group(f"epoch{suffix}") else y


def year_range(value):
    """(lo, hi) comparable years, or (None, None) when `value` is not a date.

    A bound the notation genuinely does not fix is None:
        3 SEP 1780            -> (1780, 1780)
        ABT/CAL/EST 1750      -> (1750, 1750)   near x, so both bounds are x
        BET 1816 AND 1823     -> (1816, 1823)
        FROM 1650 TO 1672     -> (1650, 1672)
        BEF 1866              -> (None, 1866)
        AFT 1672              -> (1672, None)
        44 BCE                -> (-44, -44)
    """
    if not is_valid(value):
        return (None, None)
    kind, m, _ = _parse(str(value).strip())
    if kind == "iso":
        y = int(m.group("iso_y"))
        return (y, y)
    a = _year_of(m, "_a")
    b = _year_of(m, "_b") if m.groupdict().get("year_b") is not None else None
    if kind in ("range_bet", "period_fromto"):
        return (a, b)
    if kind in ("range_bef", "period_to"):
        return (None, a)
    if kind in ("range_aft", "period_from"):
        return (a, None)
    return (a, a)


def year(value):
    """A single comparable year for sorting and matching, or None.

    Rules (Spec 02): a plain date gives its year; ABT/CAL/EST/BEF/AFT give the
    inner year; BET…AND and FROM…TO give the EARLIER bound. Consumers that need
    both bounds call `year_range`. BCE years are negative, so ordinary numeric
    comparison keeps working across the epoch."""
    lo, hi = year_range(value)
    return lo if lo is not None else hi


_PID_TOKEN = re.compile(r"\b[A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+\b")
_BARE_YEAR = re.compile(r"\b(\d{4})\b")


def resolve_year(value, allow_prose=True):
    """THE year-resolution path for every gate (spec/structured-dates Spec 05).

    A record's date value may be a proper DateValue (post-migration), legacy
    display prose (pre-migration, or a residue entry), or nothing. Three layers,
    tried in order, each one weaker and each one EXPLICIT:

      1. a valid DateValue          -> `year()`. The authoritative answer.
      2. legacy prose               -> `normalise()`, then `year()`. Handles
                                       `~1750`, `bef. 1866`, `1969, Place, MA`.
      3. the fallback heuristic     -> the first bare 4-digit token, after PID-like
                                       tokens are stripped (`LZ19-924`, `G1HP-4CV`,
                                       `Wentworth-48`). Only with allow_prose.

    This replaces the three divergent `YEAR_RE`s that each guessed a year out of
    prose and disagreed — two of which carried a **1500 floor**
    (`1[5-9]\\d{2}|20[0-2]\\d`), so no medieval person could be year-checked at all.
    That is why two entirely different people named "Henry I" (England 1068-1135,
    France 1008-1060) were invisible to duplicate detection: with no year,
    `dup_name_audit` neither flagged them NOR cleared them.

    Layer 3 is deliberately 4-digit only. Allowing 3 digits was measured on 22 JUL
    2026 and rejected: it reads atto numbers like `534` as death years. Medieval
    years reach layer 1 or 2 as a real value (`954` IS a valid DateValue), so the
    fallback never needs them — the floor is gone without the false positives."""
    if value is None:
        return None
    y = year(value)
    if y is not None:
        return y
    normalised, _residue = normalise(value)
    if normalised is not None:
        return year(normalised)
    if not allow_prose:
        return None
    m = _BARE_YEAR.search(_PID_TOKEN.sub(" ", str(value)))
    return int(m.group(1)) if m else None


def resolve_year_range(value):
    """(lo, hi) for a record value, through the same layers as `resolve_year`.
    Consumers that need the LAST year (a death year out of `1883-1885`) use hi."""
    lo, hi = year_range(value)
    if lo is not None or hi is not None:
        return (lo, hi)
    normalised, _residue = normalise(value)
    if normalised is not None:
        return year_range(normalised)
    years = _BARE_YEAR.findall(_PID_TOKEN.sub(" ", str(value or "")))
    if not years:
        return (None, None)
    return (int(years[0]), int(years[-1]))


def is_day_precise(value):
    """True when `value` fixes one specific DAY.

    ⚠ NOT the privacy predicate. The privacy gates (Spec 01,
    `validate-genealogy-vault.rb` DAY_PRECISE / `check_narrative_privacy._EXACT_DATE`)
    keep their OWN copy on purpose: they SEARCH and fail closed, so a day-precise
    bound inside a range (`BET 3 SEP 1780 AND 1790`) trips them. This one answers
    the different question "does the value resolve to a single day?", which for a
    range is False. Do not swap one for the other."""
    if not is_valid(value):
        return False
    kind, m, _ = _parse(str(value).strip())
    if kind == "iso":
        return True
    if kind != "date":
        return False
    return m.group("day_a") is not None


# --- normalise: legacy prose -> the strict form --------------------------- #

# Values that are ABSENCE MARKERS, not dates. Measured on the live vault:
# `unknown` x34, `Deceased` x10, `?` x8, plus dashes. These must return None so
# the key is OMITTED, never filled with junk — "absence = unassessed" is the
# vault's existing convention and a junk value would defeat it.
_ABSENCE = re.compile(
    r"\A\s*(?:unknown|unk|not\s+known|no\s+date[sd]?|none|n/?a|tbd|\?+|[-–—]+|"
    r"living|alive|deceased|dead|died|d\.)\b", re.I)

_MONTH_WORDS = {
    "JANUARY": "JAN", "FEBRUARY": "FEB", "MARCH": "MAR", "APRIL": "APR",
    "MAY": "MAY", "JUNE": "JUN", "JULY": "JUL", "AUGUST": "AUG",
    "SEPTEMBER": "SEP", "SEPT": "SEP", "OCTOBER": "OCT", "NOVEMBER": "NOV",
    "DECEMBER": "DEC",
}
_KEYWORDS = ("ABT", "CAL", "EST", "BET", "AND", "BEF", "AFT", "FROM", "TO", "BCE") + CALENDARS

# A residue that STARTS like a continuation of the date means the "value" is a
# TRUNCATION, not a complete date, and returning it would be a guess. Measured on
# the live vault, this rule is load-bearing — without it:
#   '2 APR c.747/748'  -> value '2'          (the year TWO)
#   '18 JUL c.640'     -> value '18'
#   '6 FEB 1712/13'    -> value '6 FEB 1712' (an OS/NS dual date, silently halved)
#   'c.985/990'        -> value 'ABT 985'    (one of two candidate years, picked)
#   '~1750-56'         -> value 'ABT 1750'
# Each of those is a real entry. They are refused here and land on the Spec 04
# worklist, where a human decides between BET…AND, a PHRASE, and a single date.
_CONTINUATION = re.compile(rf"\A(?:[/\-–—]\s*\d|\d|(?:{_MON_ALT})\b)")
# …but a TIME OF DAY is not a continuation of the date. Two live entries carry one
# ('17 APR 1875 14:15 pomeridiane…', '27 MAR 1899 8 pm') and the date before it is
# complete and correct, so the guard above must not swallow them.
_TIME_OF_DAY = re.compile(
    r"\A\d{1,2}(?::\d{2}|\s*[ap]\.?\s?m\.?\b|\s+(?:pomeridiane|antimeridiane)\b)", re.I)

# Old Style / New Style dual years — `6 JAN 1743/4`, `13 JAN 1699/1700`, `~1649/50`.
# GEDCOM 7 Appendix A §6.2 answers this case exactly, and losslessly: normalise the
# value AND keep the original notation beside it —
#     2 DATE 30 JAN 1649
#     3 PHRASE 30 January 1648/49
# so the pair is (value, phrase), which is two fields and therefore does NOT fit
# `normalise`'s single-value contract. `normalise` refuses these outright rather
# than silently halving them; `split_dual_year` is the explicit, opt-in path the
# Spec 04 migration uses to convert the whole class mechanically.
_DUAL_YEAR = re.compile(r"\A(?P<head>.*?)(?P<y1>\d{3,4})/(?P<y2>\d{1,4})(?P<tail>.*)\Z")


def _rewrite(s):
    """Mechanical legacy-prose rewrites. Order matters and is load-bearing."""
    s = re.sub(r"[*`\[\]]", "", s).strip()
    # Leading punctuation is a vitals-parser artifact, never part of a date:
    # a header like "(b. X /chr. Y)" yields values such as ". 1641, Marblehead".
    # Strip it so the date behind it is reachable. A leading WORD is left alone —
    # "chr. 30 JUL 1758" stays refused, because a christening is not a birth and
    # deciding that is an editorial act, not a normalisation.
    s = re.sub(r"\A[.,;:/\s]+", "", s)
    s = s.replace("’", "'")
    # ISO first, so the range rule below cannot mistake 1780-09-03 for a range.
    s = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b",
               lambda m: f"{int(m.group(3))} {_MONTHS_GREG[int(m.group(2)) - 1]} {m.group(1)}"
               if 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31 else m.group(0), s)
    # Month words and abbreviations -> the uppercase 3-letter token. The matched
    # token must be a month EXACTLY: an earlier prefix-based version turned
    # `JULIAN` into `JUL` (mangling `JULIAN 30 JAN 1649` into `JUL 30`), and by the
    # same rule would have read `Decatur` as DEC and `Augusta` as AUG — inventing
    # a date out of a place name.
    def _mon(m):
        w = m.group(0).rstrip(".").upper()
        if w in _MONTH_WORDS:
            return _MONTH_WORDS[w]
        return w if w in _MONTHS_GREG else m.group(0)
    s = re.sub(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?", _mon, s, flags=re.I)
    # Approximation markers. `~1750`, `c.1750`, `ca 1750`, `about 1750`, `circa 1750`.
    # …and the same lookahead widening the bounds get below: an approximation can
    # sit in front of a MONTH, not just a year ("~NOV 1698"). The month rewrite has
    # already run, so the token is uppercase by now.
    s = re.sub(r"(?:\A|(?<=[\s(]))(?:~|c\.\s*|ca\.?\s+|circa\s+|about\s+|abt\.?\s+|approx\.?\s+)"
               rf"(?=\d|(?:{_MON_ALT})\b)", "ABT ", s, flags=re.I)
    s = re.sub(r"\b(?:est\.?|estimated)\s+(?=\d)", "EST ", s, flags=re.I)
    s = re.sub(r"\b(?:calc\.?|calculated)\s+(?=\d)", "CAL ", s, flags=re.I)
    _after_bound = r"(?=\d|ABT\b|CAL\b|EST\b|(?:%s)\b)" % _MON_ALT
    s = re.sub(r"\b(?:bef\.?|before|by|no\s+later\s+than)\s+" + _after_bound, "BEF ", s, flags=re.I)
    s = re.sub(r"\b(?:aft\.?|after|no\s+earlier\s+than)\s+" + _after_bound, "AFT ", s, flags=re.I)
    # "before about 1730" -> BEF 1730. A bound on an approximation is still a
    # bound, and `BEF ABT x` is not grammatical; the approximation is subsumed.
    s = re.sub(r"\b(BEF|AFT)\s+(?:ABT|CAL|EST)\s+", r"\1 ", s)
    # "bet." is as common as "between" in this house style, and both may precede a
    # full day-month-year bound ("bet. 9 JUL 1744 and 3 MAR 1747").
    s = re.sub(rf"\bbet(?:ween|\.)\s+(?=\d|(?:{_MON_ALT})\b)", "BET ", s, flags=re.I)
    s = re.sub(r"\bfrom\s+(?=\d)", "FROM ", s, flags=re.I)
    # `1810-1830` / `1810–1830` -> `BET 1810 AND 1830`. Guarded: both sides 3-4
    # digits and the second not earlier, so a stray `1780-09` or a PID fragment
    # cannot become a range.
    s = re.sub(r"\b(\d{3,4})\s*[-–—]\s*(\d{3,4})\b",
               lambda m: f"BET {m.group(1)} AND {m.group(2)}"
               if int(m.group(2)) >= int(m.group(1)) else m.group(0), s)
    # `~1877-1881` rewrites to `ABT BET 1877 AND 1881`, which is not grammatical.
    # An approximate span IS a span: drop the redundant ABT.
    s = re.sub(r"\bABT\s+BET\b", "BET", s, flags=re.I)
    # Now that BET exists, its connector must be the keyword.
    s = re.sub(r"(?<=\d)\s+and\s+(?=\d)", " AND ", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s+to\s+(?=\d)", " TO ", s, flags=re.I)
    for kw in _KEYWORDS:
        s = re.sub(rf"\b{kw}\b", kw, s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def normalise(prose):
    """Best-effort conversion of a legacy prose date into the strict form.

    Returns **(value, residue)**:
      * `value`   — a string `is_valid` accepts, or **None** when no valid date
                    could be produced. Never a guess: `early 1621` yields None,
                    not `ABT 1621`.
      * `residue` — the text left over. Usually a PLACE that had leaked into the
                    date slot (`1969, Pittsfield, MA`), which is why the value is
                    taken as the longest valid PREFIX.

    ⚠ A non-empty residue means the value is a PREFIX of the input, so the caller
    must TRIAGE before writing it. Most residue is a place and is safe to drop,
    but some of it changes the meaning (`1810 or 1811` -> value `1810`, residue
    `or 1811`). That triage is Spec 04's job, not this function's — reporting the
    residue honestly is how this module avoids guessing on the caller's behalf."""
    if prose is None:
        return (None, "")
    original = str(prose)
    s = original.strip()
    if not s or _ABSENCE.match(s):
        return (None, original.strip())
    s = _rewrite(s)
    got = _parse(s)
    if got is None:
        return (None, original.strip())
    value = s[:got[2]].strip()
    if not is_valid(value):           # belt and braces: never return a bad value
        return (None, original.strip())
    tail = s[got[2]:].strip()
    if _CONTINUATION.match(tail) and not _TIME_OF_DAY.match(tail):
        return (None, original.strip())   # the value is a truncation -> refuse, don't guess
    residue = tail.lstrip(",;( ").strip()
    return (value, residue)


def split_dual_year(prose):
    """Old Style / New Style dual year -> (value, phrase, residue), or None.

    GEDCOM 7 Appendix A §6.2's own worked example, which is also the case
    `CLAUDE.method.md` cites as the reason dates were kept as prose:

        split_dual_year('6 JAN 1743/4')     -> ('6 JAN 1744', '6 JAN 1743/4', '')
        split_dual_year('13 JAN 1699/1700') -> ('13 JAN 1700', '13 JAN 1699/1700', '')
        split_dual_year('~1649/50, Somewhereton')
                                            -> ('ABT 1650', '~1649/50', 'Somewhereton')

    ⚠ The value takes the **SECOND** year, not the first. That is GEDCOM 7's own
    worked example (Appendix A §6.2):

        2 DATE 30 JAN 1649
        3 PHRASE 30 January 1648/49

    In `1648/49` the first year is Old Style (the year began on 25 March) and the
    second is New Style; the DATE carries the New Style year, which is the one
    every modern source uses. Taking the FIRST year was this function's original
    behaviour and it was WRONG — applied to a real vault it produced four
    `prose_audit` year-drift ERRORs in a single run, each an early-17th/18th-c.
    colonial figure whose `d. 21 FEB 1620/21`-shaped date became 1620 where every
    published account says 1621. **Only January-to-March dates are affected**,
    which is exactly why the bug is easy to miss and why a drift gate catches it.

    The phrase preserves the original DATE notation verbatim, so nothing is lost
    and the conversion is reversible. A place or commentary that had leaked into
    the date slot comes back as `residue`, exactly as `normalise` reports it, and
    needs the same triage.

    Returns None when the slash is NOT a dual year — the two years must be
    CONSECUTIVE once the short form is expanded. That is what separates an OS/NS
    date from a medieval "one of these two" span:

        '1712/13'   -> 1713 == 1712+1   dual year
        'c.985/990' -> 990  != 986      NOT dual; a 5-year span, left for a human

    Consumers: the Spec 04 migration, which writes born/born_phrase as a pair.
    `normalise` deliberately does NOT call this — it returns one value, and this
    case needs two fields."""
    if prose is None:
        return None
    original = str(prose).strip()
    m = _DUAL_YEAR.match(original)
    if not m:
        return None
    y1, y2raw = m.group("y1"), m.group("y2")
    # Expand the short form against the first year: 1743/4 -> 1744, 1699/1700 -> 1700.
    y2 = y2raw if len(y2raw) == len(y1) else y1[:len(y1) - len(y2raw)] + y2raw
    if not y2.isdigit() or int(y2) != int(y1) + 1:
        return None
    value, residue = normalise(m.group("head") + y2 + m.group("tail"))
    if value is None:
        return None
    # The phrase is the original DATE notation only — the trailing place or
    # commentary belongs in `residue`, not in a PHRASE about the date.
    phrase = (m.group("head") + y1 + "/" + y2raw).strip().strip(",;( ")
    return (value, phrase, residue)


if __name__ == "__main__":  # tiny CLI for spot checks
    import sys
    for arg in sys.argv[1:]:
        v, r = normalise(arg)
        print(f"{arg!r}\n  valid={is_valid(arg)} year={year(arg)} range={year_range(arg)} "
              f"day_precise={is_day_precise(arg)}\n  normalise -> value={v!r} residue={r!r}")
