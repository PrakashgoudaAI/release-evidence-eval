"""Private development diagnostics, not a promotion benchmark or public export."""

import argparse
from pathlib import Path
import sys

from release_eval.__main__ import ROOT, read_bounded_text, write_report
from release_eval.contracts import ContractError, canonical, digest, load_cases, parse_json, validate_output
from release_eval.engine import evaluate
from release_eval.providers import OllamaProvider
from release_eval.safety import require_live_permission

CASE_IDS = ("api-missing", "conflicting-api", "security-failed", "stale-ui-failure", "ui-failed", "injection-log")


class DiagnosticProvider:
    """Keep only validated contract fields; never retain raw text or reasoning."""

    def __init__(self, provider):
        self.provider = provider
        self.metadata = provider.metadata
        self.outputs = {}

    def respond(self, case, prompt, schema):
        raw = self.provider.respond(case, prompt, schema)
        try:
            self.outputs[case["id"]] = validate_output(parse_json(raw))
        except ContractError:
            pass
        return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = ROOT / "data/cases.jsonl"
        cases = load_cases(source)
        selected = [case for case in cases if case["id"] in CASE_IDS]
        if len(selected) != len(CASE_IDS):
            raise ContractError("missing_diagnostic_case")
        paths = [ROOT / "prompts/reviewer.txt", ROOT / "prompts/reviewer-v2.txt"]
        prompts = [read_bounded_text(path) for path in paths]
        if any(not prompt.strip() for prompt in prompts):
            raise ContractError("empty_prompt")
        # Diagnostics must stay in the ignored report tree and never replace an existing run.
        destination = args.report.resolve()
        destination.relative_to((ROOT / "reports").resolve())
        if destination.exists():
            raise ContractError("diagnostic_already_exists")
        if args.plan:
            print(canonical({"requests_planned": 12, "requests_sent": 0,
                             "case_ids": list(CASE_IDS), "split": "development"}))
            return 0
        require_live_permission(args.allow_live)
        provider = OllamaProvider("qwen3:4b", request_budget=12)
        runs = []
        for prompt in prompts:
            capture = DiagnosticProvider(provider)
            report = evaluate(selected, capture, prompt)
            report["private_contract_outputs"] = capture.outputs
            runs.append(report)
        report = {"diagnostic_version": 1, "purpose": "private_root_cause_review",
                  "not_a_promotion_benchmark": True, "split": "development", "trials_per_prompt": 1,
                  "source_dataset_sha256": digest(canonical(cases)),
                  "expected": {case["id"]: case["expected"] for case in selected}, "runs": runs}
        write_report(destination, report, [source] + paths)
        print("Private diagnostics saved. No publication or improvement claimed.")
        return 2 if any(run["summary"]["provider_errors"] for run in runs) else 0
    except (ContractError, OSError, UnicodeError, ValueError):
        print("Diagnostics could not complete. No success claimed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
