#!/usr/bin/env python3
"""Pin precheck.sh's DATE gates to the pre-commit hook's semantics.

THE DEFECT THIS PINS (session #217, 21 SEP 2026). precheck.sh gated only
`DATE_DRIFT` from prose_audit.py. The vault pre-commit hook blocks on
prose_audit's EXIT CODE, which is also non-zero for `DATE_IMPOSSIBLE` and
`DATE_UNATTESTED`. An entry whose meta `died` year was not attested in its
header got "PRECHECK: no blocking finding", then a refused commit.

These tests run the REAL precheck.sh, copied into a throwaway tree whose
`scripts/` holds stub audits that print fixed summary lines, against a throwaway
git "vault". No real vault is read.
"""
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

STUBS = {
    "bare_ark_audit.py": 'print("  BARE_ARK (changed):       0  [BLOCKING]")',
    "header_audit.py": 'print("  HEADER_GRAMMAR (changed):  0  [BLOCKING]")',
    "question_audit.py": 'print("QUESTION_AUDIT (hard): 0  [BLOCKING]")',
    "entry_attribution_audit.py": 'print("ENTRY_ATTRIBUTION (changed): 0")',
    "gen_person_index.py": 'print("  HARD violations (DUP_ID + MISSING_ID + DUP_META_KEY): 0")',
    "entry_boundary_audit.py": 'print("ENTRY_BOUNDARY: ENTRY_MISATTRIBUTION 0 (0 lines), SOURCE_MISATTRIBUTION 0")',
    "self_negation_audit.py": 'print("SELF_NEGATION: 0 LOST citation(s)")',
    "census_diff.py": 'print("CENSUS_DIFF: 0 row(s) moved, 0 added, 0 removed")',
    # prose_audit: counts and exit code come from the environment.
    "prose_audit.py": textwrap.dedent("""
        import os, sys
        d = int(os.environ.get("PA_DRIFT", "0"))
        i = int(os.environ.get("PA_IMP", "0"))
        u = int(os.environ.get("PA_UNATT", "0"))
        print("=== SUMMARY ===")
        print(f"  ERROR issues:  {d + i + u}")
        print(f"  DATE_IMPOSSIBLE / DATE_UNATTESTED: {i} / {u}   [BLOCKING]")
        print(f"  DATE_DRIFT:    {d}   [BLOCKING]  (coverage: field missing 0)")
        sys.exit(int(os.environ.get("PA_RC", "1" if (d or i or u) else "0")))
    """),
}


class PrecheckDateGates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="precheck-test-")
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, "scripts"))
        shutil.copy(os.path.join(SCRIPTS, "precheck.sh"),
                    os.path.join(self.root, "scripts", "precheck.sh"))
        for name, body in STUBS.items():
            with open(os.path.join(self.root, "scripts", name), "w") as fh:
                fh.write(body.strip() + "\n")
        self.vault = os.path.join(self.tmp, "vault")
        os.makedirs(self.vault)
        subprocess.run(["git", "init", "-q", self.vault], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_precheck(self, *args, **env):
        e = dict(os.environ, AUTORESEARCH_VAULT=self.vault, **env)
        return subprocess.run(
            ["bash", os.path.join(self.root, "scripts", "precheck.sh"), *args],
            capture_output=True, text=True, env=e)

    def test_all_zero_passes_and_reports_all_three(self):
        r = self.run_precheck()
        self.assertEqual(r.returncode, 0, r.stdout)
        for label in ("DATE_DRIFT", "DATE_IMPOSSIBLE", "DATE_UNATTESTED"):
            self.assertIn(f"ok {label}: 0", r.stdout)
        self.assertIn("PRECHECK: no blocking finding", r.stdout)

    def test_unattested_blocks(self):
        # The #217 case: DATE_DRIFT 0, DATE_UNATTESTED 1.
        r = self.run_precheck(PA_UNATT="1")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("DATE_UNATTESTED: 1   [BLOCKING]", r.stdout)
        self.assertIn("ok DATE_DRIFT: 0", r.stdout)

    def test_impossible_blocks(self):
        r = self.run_precheck(PA_IMP="2")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("DATE_IMPOSSIBLE: 2   [BLOCKING]", r.stdout)

    def test_drift_still_blocks(self):
        r = self.run_precheck(PA_DRIFT="1")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("DATE_DRIFT: 1   [BLOCKING]", r.stdout)

    def test_failing_exit_with_zero_counts_is_not_a_clean_pass(self):
        r = self.run_precheck(PA_RC="1")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RUN IT BY HAND", r.stdout)

    def test_fast_skips_the_date_gates(self):
        r = self.run_precheck("--fast", PA_UNATT="1")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("DATE_UNATTESTED", r.stdout)


if __name__ == "__main__":
    unittest.main()
