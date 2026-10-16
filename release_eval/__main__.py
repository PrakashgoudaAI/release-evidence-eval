import argparse
import os
from pathlib import Path
import sys
import tempfile

from .contracts import MAX_BYTES, ContractError, canonical, load_cases, parse_json
from .engine import evaluate, provenance, regressions, validate_baseline
from .providers import OllamaProvider, RecordedProvider
from .safety import execution_plan, require_live_permission

ROOT = Path(__file__).resolve().parent.parent


def read_bounded_text(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ContractError("text_file_too_large")
    return raw.decode("utf-8")


def write_report(path, report, protected):
    path = Path(path).resolve()
    if path in {Path(item).resolve() for item in protected if item}:
        raise ContractError("report_would_overwrite_input")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".eval-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(canonical(report) + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate release-evidence recommendations; never deploys a release.")
    parser.add_argument("--cases", type=Path, default=ROOT / "data/cases.jsonl")
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts/reviewer.txt")
    provider = parser.add_mutually_exclusive_group(required=True)
    provider.add_argument("--responses", type=Path, help="Recorded JSONL responses, not a live model benchmark")
    provider.add_argument("--ollama-model", help="Opt-in local Ollama model; no downloads or retries")
    parser.add_argument("--allow-live", action="store_true", help="Permit model calls locally; never in CI")
    parser.add_argument("--plan", action="store_true", help="Validate inputs and print the plan without model calls")
    parser.add_argument("--max-requests", type=int, default=100)
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path, default=Path("reports/evaluation.json"))
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.cases)
        prompt = read_bounded_text(args.prompt)
        if not prompt.strip():
            raise ContractError("invalid_prompt")
        adapter = (RecordedProvider(args.responses, [case["id"] for case in cases]) if args.responses
                   else OllamaProvider(args.ollama_model, args.port, args.timeout, request_budget=args.max_requests))
        plan = execution_plan(cases, 1, args.max_requests, "recorded" if args.responses else "ollama", args.timeout)
        # Validate report destination before making model calls.
        protected = [args.cases, args.prompt, args.responses, args.baseline]
        if args.report.resolve() in {item.resolve() for item in protected if item}:
            raise ContractError("report_would_overwrite_input")
        baseline = parse_json(read_bounded_text(args.baseline)) if args.baseline else None
        # Preflight baseline compatibility without sending any model request.
        if args.baseline:
            validate_baseline({**provenance(cases, prompt), "cases": [{"case_id": case["id"]} for case in cases]}, baseline)
        if args.plan:
            print(canonical(plan))
            return 0
        if args.ollama_model:
            require_live_permission(args.allow_live)
        report = evaluate(cases, adapter, prompt)
        if args.baseline:
            report["regressions"] = regressions(report, baseline)
            report["summary"]["gate_passed"] &= not report["regressions"]
        write_report(args.report, report, protected)
        summary = report["summary"]
        print("%d/%d cases passed; unsafe ready: %d; provider errors: %d; gate: %s" %
              (summary["passed"], summary["total"], summary["unsafe_ready"], summary["provider_errors"],
               "PASS" if summary["gate_passed"] else "FAIL"))
        return 2 if summary["provider_errors"] else 0 if summary["gate_passed"] else 1
    except (ContractError, OSError, UnicodeError):
        # Do not leak model content, filesystem locations, or transport details to CI logs.
        print("Evaluation could not complete: invalid input or local file operation. No success claimed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
