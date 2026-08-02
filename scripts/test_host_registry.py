#!/usr/bin/env python3
"""Pin the source-host registry as the SINGLE source of truth for locator hosts.

** Why this file exists (02 AUG 2026, session #130). ** `harvest_sources` kept a
hard-coded `EMITTED_HOST_IDS` list while `vault_config.DEFAULTS["hosts"]` kept a
separate registry, and the two disagreed in BOTH directions:

  * `anc` and `wt` were COUNTED but were not in the registry;
  * anything ADDED to the registry counted for nothing, because no counter read it.

So "register the host" -- the remedy deferred_decisions 17 chose, and the remedy the
operator asked for again this session -- was a no-op for the census. A host is now
registered in one place and every counter follows.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest_sources as H  # noqa: E402
import vault_config as VC  # noqa: E402


class RegistryIsTheSourceOfTruth(unittest.TestCase):
    def test_registered_hosts_are_emitted(self):
        """Every host in the registry is detectable, under its `short` if it has one."""
        hosts = VC.DEFAULTS["hosts"]
        for key, spec in hosts.items():
            expected = spec.get("short") or key
            self.assertIn(expected, H.EMITTED_HOST_IDS,
                          f"registered host {key!r} is not detectable as {expected!r}")

    def test_familysearch_emits_as_fs_not_as_its_key(self):
        self.assertIn("fs", H.EMITTED_HOST_IDS)
        self.assertNotIn("familysearch", H.EMITTED_HOST_IDS)

    def test_anc_and_wt_are_now_REGISTERED_not_just_hard_coded(self):
        """They were counted for months without appearing in the registry."""
        for h in ("anc", "wt"):
            self.assertIn(h, VC.DEFAULTS["hosts"], f"{h} must be in the registry")

    def test_ids_are_sorted_LONGEST_FIRST(self):
        """These are joined into a regex alternation and `|` is first-match-wins, so a
        short id that prefixes a longer one would shadow it."""
        lens = [len(i) for i in H.EMITTED_HOST_IDS]
        self.assertEqual(lens, sorted(lens, reverse=True), H.EMITTED_HOST_IDS)

    def test_no_id_shadows_another_in_the_live_regex(self):
        for a in H.EMITTED_HOST_IDS:
            for b in H.EMITTED_HOST_IDS:
                if a != b and b.startswith(a):
                    self.assertLess(H.EMITTED_HOST_IDS.index(b),
                                    H.EMITTED_HOST_IDS.index(a),
                                    f"{a!r} would shadow {b!r} in the alternation")


class NewlyRegisteredHostsCount(unittest.TestCase):
    """The four added 02 AUG 2026 on the deferred-17 precedent."""

    CASES = {
        "fold3": "fold3:700334294",
        "nycdoris": "nycdoris:D-B-1921-0002748",
        "jri": "jri:872-31",
        "geshergalicia": "geshergalicia:AGD-1902-banns-4471",
    }

    def test_each_counts_as_one_record(self):
        for host, tok in self.CASES.items():
            body = f"- **Sources** (x):\n  - a real record — {tok}\n"
            self.assertEqual(H.count_records(body), 1, f"{host}: {tok}")
            self.assertEqual(dict(H.per_host_locators(body)).get(host), 1, tok)

    def test_they_also_count_STRICT_inside_a_Sources_bullet(self):
        for host, tok in self.CASES.items():
            body = f"- **Sources** (x):\n  - a real record — {tok}\n"
            self.assertEqual(H.count_records_strict(body), 1, tok)

    def test_negation_still_suppresses_them(self):
        for tok in self.CASES.values():
            body = f"- **Sources** (x):\n  - excluded — ~{tok}\n"
            self.assertEqual(H.count_records(body), 0, tok)


class NegativeControls(unittest.TestCase):
    """A new host id must not turn ordinary prose into a record."""

    def test_prose_mentioning_a_host_name_is_NOT_a_locator(self):
        # The real corpus line that prompted this check.
        prose = "**-> Operator/fold3:** pull the EDNY declaration matching arrival 1900"
        self.assertEqual(H.record_locators(prose), [])
        self.assertEqual(dict(H.per_host_locators(prose)), {})

    def test_a_bare_prefix_naming_the_FORM_is_not_a_record(self):
        for tok in ("fold3:", "nycdoris:", "jri:", "geshergalicia:", "anc:"):
            self.assertFalse(H.is_record_locator(tok), tok)

    def test_JOWBR_IS_DELIBERATELY_NOT_A_HOST(self):
        """The 01 AUG 2026 memorial ruling keeps burial evidence OFF the ARK metric;
        registering JOWBR would fold that class back in by the back door."""
        self.assertNotIn("jowbr", VC.DEFAULTS["hosts"])
        self.assertNotIn("jowbr", H.EMITTED_HOST_IDS)
        body = "- **Sources** (x):\n  - burial — jowbr:12345\n"
        self.assertEqual(H.count_records(body), 0)

    def test_JOWBR_is_still_ALLOWLISTED_as_a_collection_title(self):
        """Not a record HOST, and also not the EXCLUDED memorial class -- both true."""
        self.assertFalse(H.is_memorial_collection("JOWBR Burial Registry"))

    def test_an_unregistered_host_counts_for_nothing(self):
        body = "- **Sources** (x):\n  - x — notahost:12345\n"
        self.assertEqual(H.count_records(body), 0)


class FallbackIsSafe(unittest.TestCase):
    def test_ids_resolve_even_with_no_vault_selected(self):
        """`resolve_vault()` is strict and raises with no vault; import must not."""
        saved = os.environ.pop("AUTORESEARCH_VAULT", None)
        try:
            ids = H._emitted_host_ids()
            self.assertTrue(ids)
            self.assertIn("fs", ids)
        finally:
            if saved is not None:
                os.environ["AUTORESEARCH_VAULT"] = saved

    def test_the_live_regex_actually_uses_the_resolved_ids(self):
        for host in ("fold3", "nycdoris"):
            self.assertTrue(re.search(r"\b" + host + r"\b", H.FULL_HOST_LOC_RE.pattern),
                            f"{host} missing from the compiled detector")


if __name__ == "__main__":
    unittest.main()
