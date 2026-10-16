import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from release_eval.__main__ import ROOT
from release_eval.contracts import ContractError, canonical, parse_json
from release_eval.experiment import main
from release_eval.experiments import TrialRecordings, compare_experiments, load_splits, run_experiment
from release_eval.providers import ProviderError
from tools.verify_experiment import demonstrate

SPLITS = load_splits(ROOT / "data/cases.jsonl", ROOT / "data/reserved.jsonl")
CASES = SPLITS["development"]
PROMPT = (ROOT / "prompts/reviewer.txt").read_text(encoding="utf-8")


class Reference:
    metadata = {"kind": "test-double"}
    def respond(self, case, prompt, schema):
        return canonical(case["expected"])


class ExperimentTests(unittest.TestCase):
    def test_reserved_set_is_separate_and_policy_validated(self):
        self.assertEqual(len(SPLITS["reserved"]), 7)
        self.assertFalse({case["id"] for case in CASES} & {case["id"] for case in SPLITS["reserved"]})

    def test_same_split_file_cannot_be_reserved(self):
        with self.assertRaisesRegex(ContractError, "split_case_ids_overlap"):
            load_splits(ROOT / "data/cases.jsonl", ROOT / "data/cases.jsonl")

    def test_renamed_case_id_does_not_hide_exact_packet_reuse(self):
        values = copy.deepcopy(CASES)
        for case in values:
            case["id"] = "reserved-" + case["id"]
            case["evidence"].reverse()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reserved.jsonl"
            path.write_text("\n".join(canonical(case) for case in values), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "split_evidence_packets_overlap"):
                load_splits(ROOT / "data/cases.jsonl", path)

    def test_perfect_trials_pass(self):
        report = run_experiment(CASES, lambda trial: Reference(), PROMPT)
        self.assertEqual(report["summary"]["robust_passed"], 16)
        self.assertEqual(report["summary"]["passed_attempts"], 48)
        self.assertTrue(report["summary"]["gate_passed"])

    def test_reserved_trial_reference_is_validated_separately(self):
        report = run_experiment(SPLITS["reserved"], lambda trial: Reference(), PROMPT, split="reserved")
        self.assertEqual(report["summary"]["passed_attempts"], 21)
        self.assertEqual(report["split"], "reserved")

    def test_empty_experiment_cannot_pass_vacuously(self):
        with self.assertRaises(ContractError):
            run_experiment([], lambda trial: Reference(), PROMPT)

    def test_every_trial_makes_its_own_calls(self):
        calls = []
        class Counting(Reference):
            def respond(self, case, prompt, schema):
                calls.append(case["id"])
                return super().respond(case, prompt, schema)
        run_experiment(CASES, lambda trial: Counting(), PROMPT)
        self.assertEqual(len(calls), 48)
        self.assertTrue(all(calls.count(case["id"]) == 3 for case in CASES))

    def test_one_late_failure_blocks_promotion(self):
        baseline, candidate, comparison = demonstrate()
        self.assertEqual(candidate["summary"]["passed_attempts"], 47)
        self.assertEqual(candidate["summary"]["robust_passed"], 15)
        self.assertEqual(candidate["summary"]["unsafe_ready"], 1)
        self.assertEqual(candidate["summary"]["unstable_cases"], 1)
        self.assertFalse(comparison["no_regression"])
        self.assertEqual(comparison["regressions"][0]["case_id"], "injection-log")
        self.assertEqual(comparison["regressions"][0]["lost_criteria"], ["decision"])

    def test_whitespace_and_array_order_do_not_create_instability(self):
        class Reordered(Reference):
            def respond(self, case, prompt, schema):
                answer = copy.deepcopy(case["expected"])
                answer["citations"].reverse()
                return "\n " + canonical(answer) + "\n"
        report = run_experiment(CASES, lambda trial: Reference() if trial == 1 else Reordered(), PROMPT)
        self.assertEqual(report["summary"]["unstable_cases"], 0)

    def test_stably_wrong_is_not_correct(self):
        class Wrong(Reference):
            def respond(self, case, prompt, schema):
                answer = copy.deepcopy(case["expected"])
                answer["decision"] = "escalate"
                return canonical(answer)
        report = run_experiment(CASES, lambda trial: Wrong(), PROMPT)
        self.assertEqual(report["summary"]["unstable_cases"], 0)
        self.assertFalse(report["summary"]["gate_passed"])

    def test_provider_errors_remain_distinct_across_trials(self):
        class Broken(Reference):
            def respond(self, case, prompt, schema):
                raise ProviderError("synthetic-private-message")
        report = run_experiment(CASES, lambda trial: Broken(), PROMPT)
        self.assertEqual(report["summary"]["provider_errors"], 48)
        self.assertFalse(report["summary"]["gate_passed"])
        self.assertNotIn("synthetic-private-message", canonical(report))

    def test_invalid_trial_counts_rejected(self):
        for trials in (True, 0, 1, 6, 2.5):
            with self.subTest(trials=trials), self.assertRaises(ContractError):
                run_experiment(CASES, lambda trial: Reference(), PROMPT, trials)

    def test_changing_provider_mid_experiment_rejected(self):
        def factory(trial):
            adapter = Reference()
            adapter.metadata = {"model": str(trial)}
            return adapter
        with self.assertRaisesRegex(ContractError, "provider_changed_between_trials"):
            run_experiment(CASES, factory, PROMPT)

    def test_improvements_are_explicit_not_statistical_claims(self):
        baseline, candidate, _ = demonstrate()
        comparison = compare_experiments(baseline, candidate)
        self.assertTrue(comparison["no_regression"])
        self.assertEqual(comparison["improvements"][0]["gained_criteria"], ["decision"])
        self.assertFalse(comparison["statistical_significance_claimed"])

    def test_new_instability_is_regression_even_with_identical_check_counts(self):
        class Wrong(Reference):
            def __init__(self, decision):
                self.decision = decision
            def respond(self, case, prompt, schema):
                answer = copy.deepcopy(case["expected"])
                if case["id"] == "clean-ready":
                    answer["decision"] = self.decision
                return canonical(answer)
        baseline = run_experiment(CASES, lambda trial: Wrong("hold"), PROMPT)
        candidate = run_experiment(CASES, lambda trial: Wrong("escalate" if trial == 3 else "hold"), PROMPT)
        comparison = compare_experiments(candidate, baseline)
        self.assertEqual(comparison["regressions"], [{"case_id": "clean-ready", "lost_criteria": [], "new_instability": True}])

    def test_different_trial_counts_and_splits_cannot_be_compared(self):
        baseline = run_experiment(CASES, lambda trial: Reference(), PROMPT)
        for current in (run_experiment(CASES, lambda trial: Reference(), PROMPT, trials=2),
                        run_experiment(CASES, lambda trial: Reference(), PROMPT, split="reserved")):
            with self.assertRaises(ContractError):
                compare_experiments(current, baseline)

    def test_forged_aggregate_counts_rejected(self):
        baseline, candidate, _ = demonstrate()
        candidate["cases"][0]["criterion_pass_counts"]["decision"] = 0
        with self.assertRaisesRegex(ContractError, "inconsistent_experiment_aggregation"):
            compare_experiments(candidate, baseline)

    def test_duplicate_cases_or_wrong_trial_outcome_rejected(self):
        for mutate in (lambda report: report["cases"].__setitem__(0, report["cases"][1]),
                       lambda report: report["runs"][0]["cases"][0].update(passed=False)):
            baseline = run_experiment(CASES, lambda trial: Reference(), PROMPT)
            candidate = copy.deepcopy(baseline)
            mutate(candidate)
            with self.assertRaises(ContractError):
                compare_experiments(candidate, baseline)


class RecordingAndCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trial check ")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trials.jsonl"
        self.report = Path(self.temp.name) / "report.json"
        self.records = [{"case_id": case["id"], "trial": trial, "response": canonical(case["expected"])}
                        for case in CASES for trial in range(1, 4)]

    def save(self, records=None):
        self.path.write_text("\n".join(canonical(item) for item in (self.records if records is None else records)), encoding="utf-8")

    def run_cli(self, *extra):
        with patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
            return main(["--recordings", str(self.path), "--report", str(self.report)] + list(extra))

    def test_complete_explicit_trial_records_accepted(self):
        self.save()
        recordings = TrialRecordings(self.path, CASES, 3)
        self.assertTrue(run_experiment(CASES, recordings.provider, PROMPT)["summary"]["gate_passed"])

    def test_missing_duplicate_extra_and_boolean_trials_rejected(self):
        for records in (self.records[:-1], self.records + [self.records[0]],
                        self.records + [dict(self.records[0], trial=4)],
                        [dict(self.records[0], trial=True)] + self.records[1:]):
            self.save(records)
            with self.assertRaises(ContractError):
                TrialRecordings(self.path, CASES, 3)

    def test_cli_success_and_comparison(self):
        self.save()
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(self.run_cli("--baseline", str(self.report), "--report", str(self.report.with_name("next.json"))), 0)

    def test_cli_negative_trial_returns_one(self):
        self.records[-1]["response"] = "not json"
        self.save()
        self.assertEqual(self.run_cli(), 1)

    def test_cli_request_budget_is_preflighted(self):
        self.save()
        self.assertEqual(self.run_cli("--max-requests", "47"), 2)
        self.assertFalse(self.report.exists())

    def test_cli_does_not_overwrite_recordings(self):
        self.save()
        original = self.path.read_bytes()
        self.assertEqual(self.run_cli("--report", str(self.path)), 2)
        self.assertEqual(self.path.read_bytes(), original)

    def test_cli_invalid_baseline_prevents_live_calls(self):
        self.path.write_text("{}", encoding="utf-8")
        with patch("release_eval.providers.OllamaProvider.respond") as respond, \
             patch("sys.stderr", new_callable=io.StringIO):
            code = main(["--ollama-model", "test-model", "--baseline", str(self.path), "--report", str(self.report)])
        self.assertEqual(code, 2)
        respond.assert_not_called()

    def test_prompt_fingerprint_changes_without_changing_fixture_answers(self):
        self.save()
        self.assertEqual(self.run_cli("--prompt", str(ROOT / "prompts/reviewer-v2.txt")), 0)
        report = parse_json(self.report.read_text())
        self.assertNotEqual(report["prompt_sha256"], run_experiment(CASES, lambda trial: Reference(), PROMPT)["prompt_sha256"])


if __name__ == "__main__":
    unittest.main()
