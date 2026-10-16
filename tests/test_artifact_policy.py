"""Keep routine CI artifacts separate from opt-in private diagnostics."""

import unittest

from release_eval.__main__ import ROOT


class ArtifactPolicyTests(unittest.TestCase):
    def test_only_named_offline_reports_are_uploaded(self):
        workflow = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("          path: |\n"), 1)
        block = workflow.split("          path: |\n", 1)[1].split("          if-no-files-found:", 1)[0]
        paths = [line.strip() for line in block.splitlines() if line.strip()]
        self.assertEqual(set(paths), {
            "reports/reference.json", "reports/comparison.json", "reports/mutations.json",
            "reports/trial-reference.json", "reports/trial-negative-control.json",
            "reports/trial-comparison.json", "reports/public-summary.json",
        })
        self.assertEqual(len(paths), 7)
        self.assertIn("          if-no-files-found: error", workflow)
        self.assertIn("          retention-days: 7", workflow)

    def test_private_report_tree_stays_ignored(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("reports/", ignored)

    def test_checkout_has_explicit_lf_policy(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertIn("* text=auto eol=lf", attributes)

    def test_checked_out_prompts_have_lf_bytes(self):
        for path in (ROOT / "prompts").glob("*.txt"):
            with self.subTest(prompt=path.name):
                self.assertNotIn(b"\r", path.read_bytes())
