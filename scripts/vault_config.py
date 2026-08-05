#!/usr/bin/env python3
"""vault_config.py — per-vault instance-config loader (zero dependency).

The local toolkit (gen_person_index, harvest_sources, build_edges, ...) is
vault-agnostic EXCEPT for a small set of per-family constants that used to be
hard-coded inline: the GEDCOM filename and the "structurally unsourceable"
allowlists (deep-generation threshold, region-scoped PID prefixes / PID sets).

Those now live in `vault/.autoresearch.json`, read through this loader, so a new
client vault is stood up by writing one small JSON file instead of editing the
scripts. An ABSENT file or absent key falls back to DEFAULTS below, so a
config-less (fresh) vault still runs with generic behavior — it simply has no
structural-gap exceptions until the operator declares them.

Usage:
    import vault_config
    cfg = vault_config.load_config(VAULT)          # -> dict, merged over DEFAULTS
    ged = vault_config.gedcom_path(VAULT)          # -> resolved .ged path (or auto-detected)

Design notes:
- JSON, not YAML: stdlib only (PyYAML is optional in this repo).
- `load_config` is memoized per vault dir; the config is read once per process.
- Unknown keys in the JSON are preserved (merged), so operators can stash extra
  vault metadata (subject name, notes) without the loader rejecting them.
"""
import json
import os
import glob
import functools

# Documented fallbacks. A config-less vault behaves generically:
#   - gedcom None  => callers auto-detect the single *.ged in the vault
#   - no structural-gap rules => nothing is exempted from the SOURCE_GAP to-do count
DEFAULTS = {
    "vault_name": None,      # display label, e.g. "Smith-Jones"
    "subject": None,         # the Gen-1 subject, informational (legacy single-subject convention)
    "gedcom": None,          # filename within the vault; None => auto-detect single *.ged
    "structural_gap": {
        "deep_gen_threshold": 16,   # Gen >= this is peerage/visitation-documented, never an indexed ARK
        # list of {label, region?, before_year?, pid_prefixes?, pids?}
        #
        # ⭐ `before_year` IS THE CRITERION AND THE OTHER TWO ARE ENUMERATIONS
        # (operator ruling 05 AUG 2026, Q157/Q144). With a `region` it reads: all
        # this person's DATED vitals fall before the year that region's civil
        # registration begins, in a parish whose registers are not online. That is
        # what a `pid_prefixes` rule always MEANT, and a criterion does not drift
        # the way a list does — the reference vault's one region-scoped rule keyed on the
        # FS-PID prefixes `P6K`/`P97`, which carry no meaning whatever, and had
        # silently fallen 16 entries short of the cluster it describes.
        # ⚠ An entry with NO dated vitals is NOT structural: the condition is
        # vacuously true of it, and an undated person is unevidenced rather than
        # unresearchable. `harvest_sources.is_structural` enforces that guard.
        # ⚠ Keep `pids` for the class a date CANNOT express: people whose records
        # exist and are simply not on FamilySearch.
        "rules": [],
    },
    "known_dup_fs_pids": {"count": 0, "note": ""},  # advisory baseline for the DUP_FS_PID display
    "dup_fs_pid_overrides": {},     # FS PID -> canonical vault id, for the ambiguous DUP_FS_PID pairs

    # Declared PEDIGREE COLLAPSE (deferred_decisions 16, settled 31 JUL 2026).
    # When a vault descends from one couple by two paths of different length, the
    # shorter path fixes the descendant's generation and the longer one fixes the
    # ancestor's, so `parent != child gen + 1` on the edge between them. Every edge
    # is correct; `generation` is a PATH label, not a global depth. Without this
    # list the PARENT-GEN MISMATCH advisory mixes declared collapse with real
    # generation bugs and neither can be read. Each entry is
    #   {child: "P-XXXXXX", parent: "P-YYYYYY", note: "why"}
    # and `build_edges --validate` reports those rows as GEN_COLLAPSE (declared)
    # separately from GEN mismatches it has never been told about.
    "known_gen_collapse": [],

    # --- multi-anchor / multi-repository model (spec/multi-anchor-multi-repo) ---
    # A vault is anchored on an individual OR a married couple. Generation 1 is the
    # whole `people` set (one person, or two for a couple). Empty `people` => the
    # loader synthesizes a single person from the legacy `subject` string, so a
    # config-less vault still yields one anchor label.
    "anchor": {
        "kind": "individual",       # "individual" | "couple"
        "people": [],               # list of {id?, name?, fs?}; Gen-1 set
    },
    # Where the toolkit reads from and writes back to. Default is FamilySearch only,
    # reproducing today's behavior exactly: a shared tree, autonomous (read-only)
    # harvest, and operator-gated public write-back. Read/write auth are separate.
    # Additional repositories may be declared per vault; a write target ships
    # DISABLED (write.enabled false) unless the operator opts in (e.g. WikiTree stays
    # corroboration-only by default). visibility drives the living-person gate:
    # a public target skips living/unknown; a private target may include them.
    "repositories": {
        "fs": {
            "kind": "shared-tree",
            "read": {"autonomous": True},
            "write": {"enabled": True, "operator_gated": True, "visibility": "public"},
        },
    },
    # Source-host registry: where a source record can be hosted. `locator_kind` is
    # "ark" when the host mints ARKs (self-describing via the NAAN), else "url"/"id".
    # Seeded with the hosts harvest_sources.py recognizes today.
    "hosts": {
        # `short` is the prefix emitted in a locator token when it differs from the
        # registry key. FamilySearch is the only one; everything else emits its key.
        "familysearch":     {"label": "FamilySearch", "short": "fs", "ark_naan": "61903", "locator_kind": "ark"},
        "antenati":         {"label": "Portale Antenati",    "ark_naan": "12657", "locator_kind": "ark"},
        "metryki":          {"label": "Metryki (genealodzy.pl)", "url_pattern": "metryki.genealodzy.pl",  "locator_kind": "url"},
        "szukajwarchiwach": {"label": "Szukaj w Archiwach",  "url_pattern": "szukajwarchiwach.gov.pl",     "locator_kind": "url"},
        "agad":             {"label": "AGAD (Fond 300)",     "url_pattern": "agadd2.home.net.pl",          "locator_kind": "id"},
        # TNA, added 30 JUL 2026 (deferred_decisions 17). A National Archives CLASS
        # REFERENCE is a stable, resolvable identifier for a REAL primary record --
        # which is what a locator is for -- even when the document is not digitised
        # and what was read is the calendared catalogue abstract. That is NOT a book
        # citation (rule 8 limb (b)), which is why it may count.
        # ** SPELLING: NO SEPARATOR. ** TNA writes "C 1/548/65"; a locator token is a
        # non-space run, so `tna:C 1/548/65` truncates at the space and cites "C".
        # An underscore is not enough either: the record detector needs a 3+ char
        # alphanumeric run and `C_78/3/3` has none, so that spelling counts for some
        # references and silently not for others. Write `tna:C1/548/65`, `tna:C78/3/3`
        # -- both verified to count -- and keep the human-readable reference in the
        # sub-bullet description, which is where a reader wants it anyway.
        "tna":              {"label": "The National Archives (UK)", "url_pattern": "discovery.nationalarchives.gov.uk", "locator_kind": "id"},

        # ** anc / wt WERE ALREADY COUNTED AND WERE NEVER REGISTERED (fixed 02 AUG 2026). **
        # `harvest_sources.EMITTED_HOST_IDS` carried them as a hard-coded literal while
        # this registry did not list them, so the two sources of truth for "what is a
        # host" disagreed. They are added here to close that, NOT to change behaviour:
        # this vault already cites 86 `anc:` locators.
        "anc":              {"label": "Ancestry",               "url_pattern": "ancestry.com",            "locator_kind": "id"},
        "wt":               {"label": "WikiTree",               "url_pattern": "wikitree.com",            "locator_kind": "id"},

        # --- added 02 AUG 2026 (session #130, operator-directed), all on the
        # deferred-17 precedent: a stable resolvable identifier for a REAL primary
        # record is a locator, even when the image sits behind a login.
        # ** SPELLING: a locator token is a NON-SPACE run** (see the TNA note above) --
        # write `nycdoris:D-B-1921-0002748`, never with spaces.
        "fold3":            {"label": "Fold3",                  "url_pattern": "fold3.com",               "locator_kind": "id"},
        "nycdoris":         {"label": "NYC Historical Vital Records (DORIS)", "url_pattern": "a860-historicalvitalrecords.nyc.gov", "locator_kind": "id"},
        "jri":              {"label": "JRI-Poland",             "url_pattern": "jri-poland.org",          "locator_kind": "id"},
        "geshergalicia":    {"label": "Gesher Galicia All-Galicia Database", "url_pattern": "gesher-galicia.org", "locator_kind": "id"},
        # ⚠ JOWBR IS DELIBERATELY *NOT* REGISTERED. It is a burial index, and the
        # 01 AUG 2026 memorial ruling keeps burial evidence OFF the ARK coverage metric
        # ("Burial evidence credits the BIOGRAPHY instead" -- the bio_completeness
        # `burial` facet, plus a `- **Burial evidence**` bullet). Registering it would
        # fold exactly the class that ruling excluded back into the census, by the back
        # door. JOWBR stays allowlisted in `is_memorial_collection` (it is not the
        # EXCLUDED class either) -- it is simply not a RECORD host.
    },

    # --- optional person-record model (spec/optional-person-model) ---
    # How person records are stored on disk. "file" (default) = one Markdown file
    # per person (the upstream/legacy model). "narrative" = many people per lineage
    # file, each a bold-name entry with an inline `- meta:` block. Both encode the
    # same fields; a vault that omits this key gets "file".
    "person_model": "file",
}


def default_vault():
    """The default vault: the `vault/` sibling of the scripts directory."""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(scripts_dir), "vault")


def resolve_vault(cli_vault=None):
    """Resolve which vault directory the toolkit should operate on.

    Precedence (the multi-vault contract):
        1. the AUTORESEARCH_VAULT environment variable, if set — the primary
           mechanism for pointing one toolkit install at many client vaults
           (`AUTORESEARCH_VAULT=~/vaults/client-b python3 scripts/...`);
        2. an explicit --vault / CLI value passed in by the caller;
        3. the default `../vault` sibling of the scripts directory.

    `~` is expanded. With no env var and no CLI value, falls back to a `../vault`
    sibling ONLY if it actually exists; otherwise raises. There is no implicit
    default vault — you must say which vault you mean.
    """
    env = os.environ.get("AUTORESEARCH_VAULT")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    if cli_vault:
        return os.path.abspath(os.path.expanduser(cli_vault))
    d = default_vault()
    if os.path.isdir(d):
        return d
    raise SystemExit(
        "No vault specified. Set AUTORESEARCH_VAULT=/path/to/vault (or pass "
        "--vault) — there is no default vault. "
        "Inspect a vault's config with: python3 scripts/vault_config.py <path>")


def resolve_vault_optional(cli_vault=None):
    """Like `resolve_vault`, but returns None instead of raising when no vault is
    resolvable.

    This exists for MODULE-LEVEL binding (`VAULT = resolve_vault_optional()`).
    Most scripts here resolve the vault once at import; doing that with the
    raising form makes the module un-IMPORTABLE without a configured vault, so a
    library consumer — a test, or a fresh clone that has no vault yet — dies at
    the import line rather than at the point it actually needs vault data. That
    is what made the whole test suite unrunnable on a clean clone.

    The "no implicit default vault" contract is UNCHANGED: pair this with
    `require_vault()` at each CLI entry point so using a tool without a vault
    still fails loudly with the same message. Only the timing moves.
    """
    try:
        return resolve_vault(cli_vault)
    except SystemExit:
        return None


def require_vault(vault_dir):
    """Assert a vault was actually resolvable; raise the standard error if not.

    Call at the top of a CLI entry point whose module-level VAULT came from
    `resolve_vault_optional`. Returns the vault so it can be used inline."""
    if not vault_dir:
        return resolve_vault()  # raises the canonical "No vault specified" SystemExit
    return vault_dir


def config_path(vault_dir):
    return os.path.join(vault_dir, ".autoresearch.json")


def _deep_update(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


@functools.lru_cache(maxsize=8)
def load_config(vault_dir):
    """Return the merged config dict for a vault (DEFAULTS deep-updated by the file)."""
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy of defaults
    path = config_path(vault_dir)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            _deep_update(cfg, json.load(fh))
    return cfg


def gedcom_path(vault_dir):
    """Resolve the GEDCOM path: the explicit `gedcom` config value if set, else
    the single `*.ged` in the vault. Returns None if no GEDCOM exists; raises if
    the vault has several and none is pinned in the config."""
    cfg = load_config(vault_dir)
    name = cfg.get("gedcom")
    if name:
        return os.path.join(vault_dir, name)
    geds = sorted(glob.glob(os.path.join(vault_dir, "*.ged")))
    if not geds:
        return None
    if len(geds) == 1:
        return geds[0]
    raise SystemExit(
        "[vault_config] multiple *.ged files in %s; pin one via \"gedcom\" in "
        ".autoresearch.json: %s" % (vault_dir, [os.path.basename(g) for g in geds])
    )


def structural_gap(vault_dir):
    """Return (deep_gen_threshold, rules) for the structural-unsourceable classifier."""
    sg = load_config(vault_dir)["structural_gap"]
    return sg.get("deep_gen_threshold", 16), sg.get("rules", [])


def get_anchor(vault_dir):
    """Return the anchor spec: {"kind": "individual"|"couple", "people": [...]}.

    Generation 1 is the whole `people` set. When `people` is empty but the legacy
    `subject` string is set, synthesize a single-person anchor from it so callers
    always get at least one Gen-1 label without requiring the new block."""
    cfg = load_config(vault_dir)
    anchor = json.loads(json.dumps(cfg.get("anchor") or {}))  # copy; don't mutate cache
    anchor.setdefault("kind", "individual")
    anchor.setdefault("people", [])
    if not anchor["people"] and cfg.get("subject"):
        anchor["people"] = [{"name": cfg["subject"]}]
    return anchor


def get_repositories(vault_dir):
    """Return the repository registry: id -> {kind, read, write}. Defaults to
    FamilySearch only (shared tree, autonomous read, operator-gated public write)."""
    return load_config(vault_dir).get("repositories", {})


def get_hosts(vault_dir):
    """Return the source-host registry: id -> {label, ark_naan?, url_pattern?,
    locator_kind}. Defaults to the hosts harvest_sources.py recognizes today."""
    return load_config(vault_dir).get("hosts", {})


def get_known_gen_collapse(vault_dir):
    """Return the declared pedigree-collapse edges as a set of (child_id, parent_id)
    pairs, plus the id->note map for display.

    Pedigree collapse is not a defect: it is what happens when a vault reaches one
    couple by two paths of different length. Declaring the affected edges here is
    the operator saying "this mismatch is understood", which is what lets the
    PARENT-GEN MISMATCH advisory mean "unexplained" again. An undeclared vault gets
    an empty set and the historical behavior exactly."""
    rows = load_config(vault_dir).get("known_gen_collapse", []) or []
    pairs, notes = set(), {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        child, parent = r.get("child"), r.get("parent")
        if child and parent:
            pairs.add((child, parent))
            notes[(child, parent)] = r.get("note", "")
    return pairs, notes


PERSON_MODELS = ("file", "narrative")


def get_route_hints(vault_dir):
    """Per-vault region -> non-FamilySearch research-route hints, most specific first.

    ** THIS IS PER-CLIENT DATA AND MUST NOT BE HARD-CODED. ** The hints are keyed on a
    vault's own REGION labels, which are its lineage and place names -- i.e. private
    family facts. A first cut of this feature inlined them in session_plan.py and the
    repo PII audit blocked the commit, correctly: the framework repo is public. Generic
    ethnicity/region keys (Italian, Polish, British, Colonial, Jewish...) stay in the
    script as defaults; anything naming a specific comune, parish or surname lives here.

    Shape, in the vault's .autoresearch.json:
        "route_hints": [["<region substring>", "<where to look>"], ...]
    Order matters: the first substring match wins, so put the specific ones first.
    Absent = the script's generic defaults alone.
    """
    cfg = load_config(vault_dir) or {}
    out = []
    for row in cfg.get("route_hints") or []:
        if isinstance(row, (list, tuple)) and len(row) == 2:
            out.append((str(row[0]), str(row[1])))
    return out


def get_person_model(vault_dir):
    """Return the vault's person-record model: "file" (default) or "narrative".

    "file"      = one Markdown file per person (the upstream/legacy model).
    "narrative" = many people per lineage file, each a bold-name entry with an
                  inline `- meta:` block.
    A vault that omits the `person_model` key gets "file". An unrecognized value is
    a hard error (not a silent fallback), so a typo surfaces immediately rather than
    quietly selecting the wrong backend."""
    model = load_config(vault_dir).get("person_model", "file")
    if model not in PERSON_MODELS:
        raise SystemExit(
            "[vault_config] unrecognized person_model %r in %s; expected one of %s"
            % (model, config_path(vault_dir), list(PERSON_MODELS)))
    return model


if __name__ == "__main__":
    import sys
    _vault = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vault")
    print(json.dumps(load_config(_vault), indent=2, ensure_ascii=False))
    print("gedcom ->", gedcom_path(_vault))
    print("anchor ->", json.dumps(get_anchor(_vault), ensure_ascii=False))
    print("repositories ->", json.dumps(get_repositories(_vault), ensure_ascii=False))
    print("hosts ->", json.dumps(get_hosts(_vault), ensure_ascii=False))
    print("person_model ->", get_person_model(_vault))
