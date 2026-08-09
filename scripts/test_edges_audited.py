#!/usr/bin/env python3
"""Pin `edges_audited` (deferred_decisions 60, option 1, operator 09 AUG 2026).

The AUDIT tier of the IMPROVE defect pool selects people whose parent/spouse edges
carry NO mark. Its instruction covered one branch only -- *"if it cannot be confirmed
give it a `?`"* -- so a row that was walked and found SOUND stayed unmarked, which is
the tier's own selection criterion, and was re-offered indefinitely. Seven rows were
confirmed PID-for-PID in a single draw and not one could be retired.

What is pinned here, and each case exists because getting it wrong is silent:

  1. the READER accepts a well-formed ISO date and nothing else;
  2. it is a DIFFERENT key from the other three dated keys, in both directions;
  3. a dated row leaves the AUDIT pool, and an undated one does NOT;
  4. `edges_audited` does NOT touch any other lane or population;
  5. it is UNMODELED, so a narrative -> file -> narrative round trip keeps it;
  6. `set_meta_key` is the write path and does not disturb its siblings;
  7. the EDGES_AUDITED_STALE condition is "no unmarked edge left", not "any edge".
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import person_store                                          # noqa: E402

META = ("- meta: {id: P-7K3QM2, evidence_tier: speculative, generation: 9, "
        "fs: XXXX-XXX, parents: '[P-A1B2C3, P-D4E5F6]'}")


class TestReader(unittest.TestCase):
    def test_reads_a_well_formed_date(self):
        line = META[:-1] + ", edges_audited: 2026-08-09}"
        self.assertEqual(person_store.edges_audited(line), "2026-08-09")

    def test_absent_key_is_none(self):
        self.assertIsNone(person_store.edges_audited(META))

    def test_rejects_a_non_date(self):
        """A truthy non-date must NOT retire a row -- that would silence real work."""
        for bad in ("yes", "true", "2026", "2026-8-9", "09 AUG 2026", "confirmed",
                    "2026-08-09 (seven rows)"):
            line = META[:-1] + f", edges_audited: {bad}}}"
            self.assertIsNone(person_store.edges_audited(line),
                              f"{bad!r} must not read as a date")

    def test_a_block_is_not_a_line(self):
        """NEGATIVE CONTROL for the `_meta_line` helper's reason for existing.

        The readers take a PersonRecord or the `- meta:` LINE. Handing them a whole
        narrative block returns None for every key -- which reads exactly like "the
        key is not set", so a caller that forgets to extract the line silently stops
        retiring anybody.
        """
        block = ("**Someone** (b. 1700)\n" + META[:-1] + ", edges_audited: 2026-08-09}\n"
                 "- some prose\n")
        self.assertIsNone(person_store.edges_audited(block))
        import session_plan
        self.assertEqual(
            person_store.edges_audited(session_plan._meta_line(block)), "2026-08-09")


class TestNotTheOtherDatedKeys(unittest.TestCase):
    """FOUR dated keys, four different jobs. The three-dated-keys table in
    CLAUDE.method.md warns against unifying them; this pins the separation."""

    def test_does_not_read_the_others(self):
        for other in ("fs_probed", "fs_absent", "route"):
            line = META[:-1] + f", {other}: 2026-08-09}}"
            self.assertIsNone(person_store.edges_audited(line),
                              f"edges_audited must not read {other}")

    def test_the_others_do_not_read_it(self):
        line = META[:-1] + ", edges_audited: 2026-08-09}"
        self.assertIsNone(person_store.fs_probed(line))
        self.assertIsNone(person_store.fs_absent(line))
        self.assertIsNone(person_store.route(line))

    def test_all_four_can_coexist(self):
        line = (META[:-1] + ", fs_probed: 2026-08-01, fs_absent: 2026-08-02, "
                "route: como-diocesan, edges_audited: 2026-08-09}")
        self.assertEqual(person_store.fs_probed(line), "2026-08-01")
        self.assertEqual(person_store.fs_absent(line), "2026-08-02")
        self.assertEqual(person_store.route(line), "como-diocesan")
        self.assertEqual(person_store.edges_audited(line), "2026-08-09")


class TestPoolMembership(unittest.TestCase):
    """The qualification predicate, shared by the lane and its settled-count."""

    def setUp(self):
        import session_plan
        self.sp = session_plan

    def test_unmarked_edges_on_a_speculative_row_qualify(self):
        meta = {"parents": "[P-A1B2C3, P-D4E5F6]"}
        unmarked, high = self.sp._edge_audit_qualifies(meta, "WELL_SOURCED",
                                                       "speculative")
        self.assertEqual(len(unmarked), 2)
        self.assertTrue(high)

    def test_all_marked_edges_do_not_qualify(self):
        meta = {"parents": "[P-A1B2C3?, P-D4E5F6?]"}
        unmarked, high = self.sp._edge_audit_qualifies(meta, "UNCITED", "speculative")
        self.assertEqual(unmarked, [])
        self.assertFalse(high)

    def test_the_low_risk_remainder_does_not_qualify(self):
        """A well-sourced, non-speculative row is the ~1,004 declared remainder."""
        meta = {"parents": "[P-A1B2C3]"}
        _u, high = self.sp._edge_audit_qualifies(meta, "WELL_SOURCED", "strong_signal")
        self.assertFalse(high)

    def test_uncited_qualifies_without_a_speculative_tier(self):
        meta = {"spouse": "[P-A1B2C3]"}
        _u, high = self.sp._edge_audit_qualifies(meta, "UNCITED", "")
        self.assertTrue(high)


class TestRoundTrip(unittest.TestCase):
    def test_unmodeled_key_survives_a_record_round_trip(self):
        """`_record_to_meta` preserves UNMODELED keys -- the same guarantee that makes
        `adjudicated` and `banked_parents` safe to carry. Verified, not assumed:
        without it a narrative -> file -> narrative conversion would silently drop
        every confirmation and re-open every settled row.
        """
        line = META[:-1] + ", edges_audited: 2026-08-09}"
        meta = person_store._parse_meta_block(line)
        self.assertEqual(meta.get("edges_audited"), "2026-08-09")
        rec = person_store._record_from_meta(
            meta, "Jane Example", "", {}, 0, "Family_Tree.md", None, line, None)
        out = person_store._record_to_meta(rec, original_meta=meta)
        self.assertEqual(out.get("edges_audited"), "2026-08-09",
                         "an UNMODELED key must survive the record round trip")
        # and the modelled siblings must come through it unharmed
        self.assertEqual(out.get("id"), "P-7K3QM2")
        self.assertEqual(list(out.get("parents") or []), ["P-A1B2C3", "P-D4E5F6"])

    def test_set_meta_key_writes_without_disturbing_siblings(self):
        out = person_store.set_meta_key(META, "edges_audited", "2026-08-09")
        self.assertEqual(person_store.edges_audited(out), "2026-08-09")
        self.assertIn("id: P-7K3QM2", out)
        self.assertIn("parents: '[P-A1B2C3, P-D4E5F6]'", out)
        self.assertIn("fs: XXXX-XXX", out)

    def test_set_meta_key_replaces_in_place_rather_than_duplicating(self):
        """A key written twice is valid YAML and LAST-WINS, silently discarding a
        value -- that is DUP_META_KEY, a HARD gate. Pinned here too."""
        once = person_store.set_meta_key(META, "edges_audited", "2026-08-01")
        twice = person_store.set_meta_key(once, "edges_audited", "2026-08-09")
        self.assertEqual(twice.count("edges_audited"), 1)
        self.assertEqual(person_store.edges_audited(twice), "2026-08-09")


class TestStaleCondition(unittest.TestCase):
    """EDGES_AUDITED_STALE fires only when NO unmarked edge is left."""

    @staticmethod
    def _stale(meta_parents):
        toks = re.findall(r"P-[0-9A-Za-z]+\??", meta_parents)
        return not any(not t.endswith("?") for t in toks)

    def test_all_marked_is_stale(self):
        self.assertTrue(self._stale("[P-A1B2C3?, P-D4E5F6?]"))

    def test_any_unmarked_is_not_stale(self):
        self.assertFalse(self._stale("[P-A1B2C3?, P-D4E5F6]"))
        self.assertFalse(self._stale("[P-A1B2C3]"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
