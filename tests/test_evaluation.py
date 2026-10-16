import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from release_eval.__main__ import ROOT, main, write_report
from release_eval.contracts import (MAX_BYTES, OUTPUT_SCHEMA, ContractError, canonical,
                                    load_cases, load_lines, parse_json, validate_output)
from release_eval.engine import evaluate, regressions
from release_eval.providers import OllamaProvider, ProviderError, RecordedProvider

CASES = load_cases(ROOT / "data/cases.jsonl")
PROMPT = (ROOT / "prompts/reviewer.txt").read_text(encoding="utf-8")


def recorded():
    return RecordedProvider(ROOT / "examples/reference-responses.jsonl", [case["id"] for case in CASES])


def reference():
    return evaluate(CASES, recorded(), PROMPT)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "cases.jsonl"

    def save(self, cases):
        self.path.write_text("\n".join(canonical(case) for case in cases) + "\n", encoding="utf-8")
        return self.path

    def test_authored_labels_match_independent_policy(self):
        self.assertEqual(len(CASES), 16)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ContractError):
            parse_json('{"decision":"hold","decision":"ready"}')

    def test_non_standard_numbers_rejected(self):
        for number in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(number=number), self.assertRaises(ContractError):
                parse_json(number)

    def test_fenced_json_is_not_silently_repaired(self):
        with self.assertRaises(ContractError):
            parse_json('```json\n{}\n```')

    def test_empty_or_blank_records_rejected(self):
        for contents in ("", "\n", '{}\n\n{}'):
            self.path.write_text(contents, encoding="utf-8")
            with self.subTest(contents=contents), self.assertRaises(ContractError):
                load_lines(self.path)

    def test_invalid_utf8_rejected(self):
        self.path.write_bytes(b'\xff')
        with self.assertRaises(ContractError):
            load_lines(self.path)

    def test_input_size_bounded(self):
        self.path.write_bytes(b' ' * (MAX_BYTES + 1))
        with self.assertRaises(ContractError):
            load_lines(self.path)

    def test_duplicate_case_id_rejected(self):
        with self.assertRaises(ContractError):
            load_cases(self.save(CASES + [CASES[0]]))

    def test_duplicate_evidence_id_rejected(self):
        cases = copy.deepcopy(CASES)
        case = next(case for case in cases if case["evidence"])
        case["evidence"].append(copy.deepcopy(case["evidence"][0]))
        with self.assertRaises(ContractError):
            load_cases(self.save(cases))

    def test_unreviewed_expected_label_rejected(self):
        cases = copy.deepcopy(CASES)
        cases[0]["expected"]["decision"] = "ready"
        with self.assertRaises(ContractError):
            load_cases(self.save(cases))

    def test_missing_risk_category_rejected(self):
        cases = [case for case in CASES if case["category"] != "injection"]
        with self.assertRaises(ContractError):
            load_cases(self.save(cases))

    def test_unsafe_case_identifier_rejected(self):
        cases = copy.deepcopy(CASES)
        cases[0]["id"] = "secret@example.invalid"
        with self.assertRaises(ContractError):
            load_cases(self.save(cases))

    def test_unknown_case_fields_rejected(self):
        cases = copy.deepcopy(CASES)
        cases[0]["model_answer"] = "ready"
        with self.assertRaises(ContractError):
            load_cases(self.save(cases))

    def test_invalid_evidence_result_rejected(self):
        cases = copy.deepcopy(CASES)
        next(case for case in cases if case["evidence"])["evidence"][0]["result"] = True
        with self.assertRaises(ContractError):
            load_cases(self.save(cases))

    def test_output_contract_rejects_extra_missing_and_wrong_types(self):
        expected = CASES[0]["expected"]
        values = [None, [], {}, dict(expected, explanation="trust me"), dict(expected, decision=[]),
                  dict(expected, citations="u"), dict(expected, reason_codes=[]),
                  dict(expected, citations=["u", "u"]), dict(expected, reason_codes=["approved"])]
        for value in values:
            with self.subTest(value=value), self.assertRaises(ContractError):
                validate_output(value)


class EvaluationTests(unittest.TestCase):
    def mutate(self, case_id, transform):
        provider = recorded()
        value = parse_json(provider.responses[case_id])
        transform(value)
        provider.responses[case_id] = canonical(value)
        report = evaluate(CASES, provider, PROMPT)
        return report, next(case for case in report["cases"] if case["case_id"] == case_id)

    def test_reference_is_explicitly_recorded_and_all_categories_present(self):
        report = reference()
        self.assertEqual(report["provider"]["kind"], "recorded")
        self.assertTrue(report["summary"]["gate_passed"])
        self.assertTrue(all(category["total"] for category in report["categories"].values()))

    def test_invented_citation_fails_even_when_decision_is_right(self):
        report, result = self.mutate("ui-failed", lambda value: value["citations"].append("invented"))
        self.assertTrue(result["checks"]["decision"])
        self.assertFalse(result["checks"]["citations"])
        self.assertFalse(report["summary"]["gate_passed"])

    def test_missing_blocker_fails(self):
        _, result = self.mutate("ui-failed", lambda value: value.update(blocking_evidence=[]))
        self.assertFalse(result["checks"]["blockers"])

    def test_wrong_reason_fails(self):
        _, result = self.mutate("api-missing", lambda value: value.update(reason_codes=["checks_passed"]))
        self.assertFalse(result["checks"]["reasons"])

    def test_unsafe_ready_hard_fails_despite_fifteen_correct_cases(self):
        report, result = self.mutate("injection-log", lambda value: value.update(decision="ready"))
        self.assertEqual(report["summary"]["passed"], 15)
        self.assertEqual(report["summary"]["unsafe_ready"], 1)
        self.assertTrue(result["unsafe_ready"])
        self.assertFalse(report["summary"]["gate_passed"])

    def test_array_order_is_irrelevant(self):
        report, _ = self.mutate("conflicting-api", lambda value: value["citations"].reverse())
        self.assertTrue(report["summary"]["gate_passed"])

    def test_malformed_output_is_quality_failure_not_provider_error(self):
        provider = recorded()
        provider.responses[CASES[0]["id"]] = "not json: synthetic-secret-marker"
        report = evaluate(CASES, provider, PROMPT)
        self.assertEqual(report["summary"]["provider_errors"], 0)
        self.assertEqual(report["cases"][0]["failure"], "invalid_model_output")
        self.assertNotIn("synthetic-secret-marker", canonical(report))

    def test_provider_failure_is_distinct_and_other_cases_still_run(self):
        class Broken:
            metadata = {"kind": "test-double"}
            def respond(self, case, prompt, schema):
                raise ProviderError("synthetic-secret-marker")
        report = evaluate(CASES, Broken(), PROMPT)
        self.assertEqual(report["summary"]["provider_errors"], 16)
        self.assertEqual(len(report["cases"]), 16)
        self.assertNotIn("synthetic-secret-marker", canonical(report))

    def test_report_is_reproducible(self):
        self.assertEqual(canonical(reference()), canonical(reference()))

    def test_report_contains_hashes_not_prompts_logs_or_raw_outputs(self):
        report = reference()
        self.assertEqual(len(report["dataset_sha256"]), 64)
        self.assertEqual(len(report["prompt_sha256"]), 64)
        self.assertEqual(len(report["cases"][0]["response_sha256"]), 64)
        self.assertNotIn("SYSTEM OVERRIDE", canonical(report))
        self.assertNotIn("blocking_evidence", canonical(report))

    def test_compatible_baseline_has_no_regressions(self):
        self.assertEqual(regressions(reference(), reference()), [])

    def test_check_level_regression_not_hidden_by_same_case_outcome(self):
        baseline, _ = self.mutate("ui-failed", lambda value: value.update(reason_codes=["checks_passed"]))
        current, _ = self.mutate("ui-failed", lambda value: value.update(citations=[]))
        losses = regressions(current, baseline)
        self.assertEqual(losses, [{"case_id": "ui-failed", "lost_checks": ["citations"]}])

    def test_changed_dataset_cannot_be_compared(self):
        baseline = reference()
        baseline["dataset_sha256"] = "different"
        with self.assertRaises(ContractError):
            regressions(reference(), baseline)

    def test_baseline_inconsistent_boolean_outcome_rejected(self):
        baseline = reference()
        baseline["cases"][0]["passed"] = False
        with self.assertRaises(ContractError):
            regressions(reference(), baseline)

    def test_baseline_missing_or_duplicate_cases_rejected(self):
        for operation in (lambda values: values.pop(), lambda values: values.__setitem__(0, values[1])):
            baseline = reference()
            operation(baseline["cases"])
            with self.assertRaises(ContractError):
                regressions(reference(), baseline)


class ProviderTests(unittest.TestCase):
    def test_cloud_model_suffix_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "cloud_model_not_allowed"):
            OllamaProvider("gemma4:cloud")

    def test_qwen3_final_answer_mode_is_explicit_and_recorded(self):
        captured = []
        def transport(payload):
            captured.append(payload)
            return canonical({"done": True, "message": {"role": "assistant", "content": "{}"}})
        adapter = OllamaProvider("qwen3:4b", transport=transport)
        adapter.respond(CASES[0], PROMPT, OUTPUT_SCHEMA)
        self.assertIs(captured[0]["think"], False)
        self.assertIs(adapter.metadata["thinking"], False)

    def test_recorded_missing_extra_and_duplicate_records_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "responses.jsonl"
            for records in ([{"case_id": "a", "response": "{}"}],
                            [{"case_id": "a", "response": "{}"}] * 2):
                path.write_text("\n".join(canonical(item) for item in records), encoding="utf-8")
                with self.assertRaises(ContractError):
                    RecordedProvider(path, ["a", "b"])

    def test_ollama_receives_no_labels_or_categories(self):
        captured = []
        def transport(payload):
            captured.append(payload)
            return canonical({"done": True, "message": {"role": "assistant", "content": "{}"}})
        adapter = OllamaProvider("test-model:local", transport=transport)
        self.assertEqual(adapter.respond(CASES[0], PROMPT, OUTPUT_SCHEMA), "{}")
        packet = parse_json(captured[0]["messages"][1]["content"])
        self.assertEqual(set(packet), {"revision", "evidence"})
        self.assertEqual(captured[0]["format"], OUTPUT_SCHEMA)
        self.assertFalse(captured[0]["stream"])

    def test_incomplete_or_tool_call_envelopes_rejected(self):
        for envelope in ({"done": False}, {"done": True, "message": {}},
                         {"done": True, "message": {"role": "assistant", "content": "{}", "tool_calls": [{}]}}):
            adapter = OllamaProvider("test-model", transport=lambda _: canonical(envelope))
            with self.assertRaises(ProviderError):
                adapter.respond(CASES[0], PROMPT, OUTPUT_SCHEMA)

    def test_malformed_model_json_is_returned_for_scoring(self):
        adapter = OllamaProvider("test-model", transport=lambda _: canonical(
            {"done": True, "message": {"role": "assistant", "content": "not json"}}))
        self.assertEqual(adapter.respond(CASES[0], PROMPT, OUTPUT_SCHEMA), "not json")

    def test_transport_timeout_not_retried(self):
        calls = []
        def transport(payload):
            calls.append(payload)
            raise TimeoutError("synthetic-secret-marker")
        adapter = OllamaProvider("test-model", transport=transport)
        with self.assertRaisesRegex(ProviderError, "provider_transport_or_envelope_error"):
            adapter.respond(CASES[0], PROMPT, OUTPUT_SCHEMA)
        self.assertEqual(len(calls), 1)

    def test_oversized_model_content_rejected(self):
        adapter = OllamaProvider("test-model", transport=lambda _: canonical(
            {"done": True, "message": {"role": "assistant", "content": "x" * (MAX_BYTES + 1)}}))
        with self.assertRaises(ProviderError):
            adapter.respond(CASES[0], PROMPT, OUTPUT_SCHEMA)

    def test_invalid_transport_configuration_rejected(self):
        for options in ({"model": "bad name"}, {"model": "ok", "port": True},
                        {"model": "ok", "port": 80}, {"model": "ok", "timeout": 0},
                        {"model": "ok", "timeout": 31}):
            with self.subTest(options=options), self.assertRaises(ContractError):
                OllamaProvider(**options)

    def test_http_transport_uses_loopback_and_disables_proxy(self):
        class Reply:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit):
                self.limit = limit
                return b'{"done":true,"message":{"role":"assistant","content":"{}"}}'
        with patch("release_eval.providers.request.build_opener") as build, patch.dict("os.environ", {}, clear=True):
            build.return_value.open.return_value = Reply()
            OllamaProvider("test-model").respond(CASES[0], PROMPT, OUTPUT_SCHEMA)
            handlers = build.call_args.args
            self.assertEqual(handlers[0].proxies, {})
            req = build.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, "http://127.0.0.1:11434/api/chat")
            self.assertEqual(req.get_method(), "POST")

    def test_redirects_rejected(self):
        from release_eval.providers import _NoRedirect
        with self.assertRaisesRegex(ProviderError, "redirect_rejected"):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="eval with spaces ")
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name) / "report.json"

    def run_cli(self, *extra):
        with patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
            return main(["--responses", str(ROOT / "examples/reference-responses.jsonl"),
                         "--report", str(self.report)] + list(extra))

    def test_success_report_and_baseline_in_space_containing_path(self):
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(self.run_cli("--baseline", str(self.report), "--report", str(self.report.with_name("second.json"))), 0)

    def test_quality_failure_returns_one(self):
        path = Path(self.temp.name) / "bad.jsonl"
        records = load_lines(ROOT / "examples/reference-responses.jsonl")
        records[0]["response"] = "{}"
        path.write_text("\n".join(canonical(item) for item in records), encoding="utf-8")
        self.assertEqual(self.run_cli("--responses", str(path)), 1)

    def test_bad_input_returns_two_and_no_success_report(self):
        self.assertEqual(self.run_cli("--cases", str(self.report)), 2)
        self.assertFalse(self.report.exists())

    def test_output_cannot_overwrite_dataset_or_baseline(self):
        source = Path(self.temp.name) / "input.jsonl"
        contents = (ROOT / "data/cases.jsonl").read_text(encoding="utf-8")
        source.write_text(contents, encoding="utf-8")
        self.assertEqual(self.run_cli("--cases", str(source), "--report", str(source)), 2)
        self.assertEqual(source.read_text(encoding="utf-8"), contents)
        self.assertEqual(self.run_cli(), 0)
        original = self.report.read_bytes()
        self.assertEqual(self.run_cli("--baseline", str(self.report)), 2)
        self.assertEqual(self.report.read_bytes(), original)

    def test_atomic_write_leaves_no_temporary_files(self):
        write_report(self.report, {"result": True}, [])
        self.assertEqual(list(Path(self.temp.name).iterdir()), [self.report])

    def test_provider_failure_returns_two_and_records_failed_run(self):
        with patch("release_eval.providers.OllamaProvider.respond", side_effect=ProviderError("offline")), \
             patch.dict("os.environ", {}, clear=True), \
             patch("sys.stdout", new_callable=io.StringIO):
            code = main(["--ollama-model", "test-model", "--allow-live", "--report", str(self.report)])
        self.assertEqual(code, 2)
        self.assertFalse(parse_json(self.report.read_text())["summary"]["gate_passed"])

    def test_invalid_baseline_rejected_before_model_calls(self):
        baseline = Path(self.temp.name) / "baseline.json"
        baseline.write_text("{}", encoding="utf-8")
        with patch("release_eval.providers.OllamaProvider.respond") as respond, \
             patch("sys.stderr", new_callable=io.StringIO):
            code = main(["--ollama-model", "test-model", "--baseline", str(baseline), "--report", str(self.report)])
        self.assertEqual(code, 2)
        respond.assert_not_called()

    def test_targeted_fault_campaign_catches_every_mutant(self):
        from tools.verify_mutations import campaign
        report = campaign()
        self.assertEqual(report["caught"], report["total"])
        self.assertEqual(report["total"], 6)


if __name__ == "__main__":
    unittest.main()
