"""CLI for recorded repeated trials or an explicitly selected local model."""

import argparse
from pathlib import Path
import sys

from .__main__ import ROOT, read_bounded_text, write_report
from .contracts import ContractError, canonical, parse_json
from .experiments import TrialRecordings, compare_experiments, load_splits, run_experiment, validate_trials
from .providers import OllamaProvider
from .safety import execution_plan, require_live_permission


def main(argv=None):
    parser = argparse.ArgumentParser(description="Repeated release-evidence evaluation; no deployment actions.")
    parser.add_argument("--development", type=Path, default=ROOT / "data/cases.jsonl")
    parser.add_argument("--reserved", type=Path, default=ROOT / "data/reserved.jsonl")
    parser.add_argument("--split", choices=("development", "reserved"), default="development")
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts/reviewer.txt")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=100)
    provider = parser.add_mutually_exclusive_group(required=True)
    provider.add_argument("--recordings", type=Path, help="JSONL with an explicit trial number for every response")
    provider.add_argument("--ollama-model")
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path, default=Path("reports/experiment.json"))
    args = parser.parse_args(argv)
    try:
        validate_trials(args.trials)
        splits = load_splits(args.development, args.reserved)
        cases = splits[args.split]
        plan = execution_plan(cases, args.trials, args.max_requests,
                              "recorded" if args.recordings else "ollama", args.timeout)
        prompt = read_bounded_text(args.prompt)
        if not prompt.strip():
            raise ContractError("empty_prompt")
        protected = [args.development, args.reserved, args.prompt, args.recordings, args.baseline]
        if args.report.resolve() in {path.resolve() for path in protected if path}:
            raise ContractError("report_would_overwrite_input")
        if args.recordings:
            factory = TrialRecordings(args.recordings, cases, args.trials).provider
        else:
            adapter = OllamaProvider(args.ollama_model, args.port, args.timeout, request_budget=args.max_requests)
            factory = lambda trial: adapter
        # Preflight every baseline before any live requests using a zero-I/O oracle fixture.
        baseline = parse_json(read_bounded_text(args.baseline)) if args.baseline else None
        if args.baseline:
            class Preflight:
                metadata = {"kind": "preflight-only"}
                def respond(self, case, prompt, schema):
                    return canonical(case["expected"])
            compare_experiments(run_experiment(cases, lambda trial: Preflight(), prompt, args.trials, args.split), baseline)
        if args.plan:
            print(canonical(plan))
            return 0
        if args.ollama_model:
            require_live_permission(args.allow_live)
        report = run_experiment(cases, factory, prompt, args.trials, args.split)
        if args.baseline:
            report["comparison"] = compare_experiments(report, baseline)
            report["summary"]["gate_passed"] &= report["comparison"]["no_regression"]
        write_report(args.report, report, protected)
        summary = report["summary"]
        print("%d/%d cases passed every trial; %d/%d attempts passed; unstable: %d; gate: %s" %
              (summary["robust_passed"], summary["total_cases"], summary["passed_attempts"], summary["total_attempts"],
               summary["unstable_cases"], "PASS" if summary["gate_passed"] else "FAIL"))
        return 2 if summary["provider_errors"] else 0 if summary["gate_passed"] else 1
    except (ContractError, OSError, UnicodeError):
        print("Experiment could not complete: invalid input or local file operation. No success claimed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
