import unittest

from release_eval.contracts import OUTPUT_SCHEMA, canonical
from tools.diagnose import DiagnosticProvider


class DiagnosticsTests(unittest.TestCase):
    def capture(self, raw):
        class Fake:
            metadata = {"kind": "test"}

            def respond(self, case, prompt, schema):
                return raw

        adapter = DiagnosticProvider(Fake())
        self.assertEqual(adapter.respond({"id": "sample"}, "prompt", OUTPUT_SCHEMA), raw)
        return adapter.outputs

    def test_valid_contract_captured(self):
        output = {"decision": "ready", "blocking_evidence": [], "citations": [], "reason_codes": ["checks_passed"]}
        self.assertEqual(self.capture(canonical(output)), {"sample": output})

    def test_invalid_text_not_retained(self):
        self.assertEqual(self.capture("private unstructured response"), {})

    def test_extra_fields_not_retained(self):
        self.assertEqual(self.capture('{"reasoning":"private"}'), {})
