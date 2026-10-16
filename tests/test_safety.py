import copy
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from release_eval.__main__ import ROOT, main
from release_eval.contracts import ContractError, canonical
from release_eval.experiment import main as experiment_main
from release_eval.providers import OllamaProvider, ProviderError
from release_eval.safety import RequestBudget, execution_plan, require_live_permission
from tools.export_summary import export
from tools.publication_check import matches, scan
from tools.verify_experiment import demonstrate


class LiveSafetyTests(unittest.TestCase):
    def test_missing_opt_in_and_ci_rejected(self):
        for allowed, env in ((False, {}), (True, {"CI": "true"}), (True, {"GITHUB_ACTIONS": "true"})):
            with self.subTest(env=env), self.assertRaises(ContractError):
                require_live_permission(allowed, env)

    def test_explicit_local_opt_in_allowed(self):
        require_live_permission(True, {"CI": "false"})

    def test_actual_request_budget_consumed_before_transport(self):
        calls = []
        def transport(payload):
            calls.append(payload)
            raise TimeoutError("unavailable")
        adapter = OllamaProvider("test-model", transport=transport, request_budget=1)
        case = {"revision": "r2", "evidence": []}
        with self.assertRaises(ProviderError):
            adapter.respond(case, "prompt", {})
        with self.assertRaisesRegex(ProviderError, "request_budget_exhausted"):
            adapter.respond(case, "prompt", {})
        self.assertEqual(len(calls), 1)

    def test_budget_rejects_invalid_limits(self):
        for limit in (True, 0, 501, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ContractError):
                RequestBudget(limit)

    def test_direct_network_transport_cannot_run_in_ci(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}, clear=True), \
             patch("release_eval.providers.request.build_opener") as opener:
            with self.assertRaises(ContractError):
                OllamaProvider("test-model")._send({})
        opener.assert_not_called()

    def test_plan_counts_calls_without_claiming_a_cost_estimate(self):
        plan = execution_plan([{}] * 16, 3, 100, "ollama", 30)
        self.assertEqual(plan["planned_requests"], 48)
        self.assertEqual(plan["requests_sent"], 0)
        self.assertEqual(plan["estimated_cost"], "not_available")
        self.assertEqual(execution_plan([{}] * 16, 3, 100, "recorded", 30)["planned_requests"], 0)

    def test_live_cli_without_opt_in_makes_no_calls(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("release_eval.providers.OllamaProvider.respond") as respond, \
             patch("sys.stderr", new_callable=io.StringIO):
            report = Path(directory) / "report.json"
            self.assertEqual(main(["--ollama-model", "test-model", "--report", str(report)]), 2)
            self.assertFalse(report.exists())
        respond.assert_not_called()

    def test_planning_both_clis_does_not_call_model_or_write_report(self):
        for entry in (main, experiment_main):
            with self.subTest(entry=entry.__module__), tempfile.TemporaryDirectory() as directory, \
                 patch("release_eval.providers.OllamaProvider.respond") as respond, \
                 patch("sys.stdout", new_callable=io.StringIO) as output:
                report = Path(directory) / "report.json"
                code = entry(["--ollama-model", "test-model", "--plan", "--report", str(report)])
                self.assertEqual(code, 0)
                self.assertFalse(report.exists())
                self.assertIn('"plan_only":true', output.getvalue())
                respond.assert_not_called()

    def test_explicit_live_flag_still_blocked_in_ci(self):
        with patch.dict("os.environ", {"CI": "true"}, clear=True), \
             patch("release_eval.providers.OllamaProvider.respond") as respond, \
             patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(main(["--ollama-model", "test-model", "--allow-live"]), 2)
        respond.assert_not_called()


class PublicationTests(unittest.TestCase):
    def test_known_secret_patterns_detected_without_returning_value(self):
        values = [b"gh" + b"p_" + b"A" * 36, b"sk" + b"-" + b"B" * 30,
                  b"AK" + b"IA" + b"C" * 16, b"-----BEGIN " + b"PRIVATE KEY-----",
                  b'api_key = "' + b"D" * 30 + b'"']
        for value in values:
            with self.subTest(value_length=len(value)):
                self.assertTrue(matches(value))
                self.assertNotIn(value.decode(), str(matches(value)))

    def test_environment_file_is_a_finding_even_without_obvious_token(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".env").write_text("private settings", encoding="utf-8")
            result = scan(directory, history=False)
            self.assertFalse(result["passed"])
            self.assertEqual(result["findings"][0]["rule"], "private-environment-file")

    def test_oversized_files_are_not_silent_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large.bin").write_bytes(b"x" * (1_048_576 + 1))
            result = scan(root, history=False)
            self.assertFalse(result["passed"])
            self.assertEqual(len(result["incomplete"]), 1)

    def test_symlinks_are_not_silent_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "file.txt").write_text("synthetic", encoding="utf-8")
            try:
                (root / "link").symlink_to(root / "file.txt")
            except OSError:
                self.skipTest("Host does not permit creating symlinks.")
            result = scan(root, history=False)
            self.assertFalse(result["passed"])
            self.assertEqual(len(result["incomplete"]), 1)

    def test_private_reports_are_excluded_but_can_be_explicitly_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            path = root / "reports/result.json"
            path.write_text("sk" + "-" + "E" * 30, encoding="utf-8")
            self.assertTrue(scan(root, history=False)["passed"])
            self.assertFalse(scan(path, history=False)["passed"])

    def test_removed_secret_is_detected_in_git_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hooks = root / "empty-hooks"
            hooks.mkdir()
            def git(*args):
                subprocess.run(["git", "-C", directory, "-c", "core.hooksPath=" + str(hooks),
                                "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
                               check=True, capture_output=True)
            git("init", "-q")
            path = root / "removed.txt"
            token = "gh" + "p_" + "F" * 36
            path.write_text(token, encoding="utf-8")
            git("add", "-f", "removed.txt")
            git("commit", "--no-gpg-sign", "-qm", "Add synthetic test token")
            path.unlink()
            git("add", "-u")
            git("commit", "--no-gpg-sign", "-qm", "Remove synthetic test token")
            result = scan(root)
            self.assertFalse(result["passed"])
            self.assertEqual(result["history"], "scanned_reachable_objects")
            self.assertTrue(any(item["location"].startswith("git-object:") for item in result["findings"]))
            self.assertNotIn(token, canonical(result))

    def test_current_source_has_no_known_pattern_findings(self):
        result = scan(ROOT, history=False)
        self.assertTrue(result["passed"], result)


class ExportTests(unittest.TestCase):
    def test_raw_content_model_names_and_arbitrary_metadata_never_copied(self):
        baseline, _, _ = demonstrate()
        baseline["private_notes"] = "synthetic-secret-marker"
        baseline["provider"]["model"] = "synthetic-secret-marker"
        for run in baseline["runs"]:
            run["provider"]["model"] = "synthetic-secret-marker"
            run["raw_response"] = "synthetic-secret-marker"
        result = export(baseline)
        self.assertNotIn("synthetic-secret-marker", canonical(result))
        self.assertEqual(result["passed_attempts"], 48)
        self.assertTrue(result["publication_requires_human_review"])

    def test_export_counts_come_from_attempts_not_claimed_summary(self):
        _, candidate, _ = demonstrate()
        candidate["summary"]["passed_attempts"] = 48
        result = export(candidate)
        self.assertEqual(result["passed_attempts"], 47)
        self.assertEqual(result["unsafe_ready"], 1)

    def test_export_rejects_unexpected_failure_text_and_sensitive_identifiers(self):
        baseline, _, _ = demonstrate()
        for field, value in (("failure", "synthetic-secret-marker"), ("case_id", "private@example.invalid")):
            report = copy.deepcopy(baseline["runs"][0])
            report["cases"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                export(report)


if __name__ == "__main__":
    unittest.main()
