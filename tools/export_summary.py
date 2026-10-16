"""Export allowlisted evaluation facts; raw/private fields are never copied."""

import argparse
from pathlib import Path
import re

from release_eval.__main__ import read_bounded_text, write_report
from release_eval import __version__
from release_eval.contracts import CATEGORIES, ContractError, identifier, parse_json
from release_eval.engine import validate_baseline
from release_eval.experiments import _validated_experiment


def _single(report):
    if any(key not in report for key in ("report_version", "runner_version", "rubric_version")):
        raise ContractError("missing_export_versions")
    if type(report["report_version"]) is not int or report["report_version"] != 2 or \
       type(report["rubric_version"]) is not int or report["rubric_version"] != 1 or report["runner_version"] != __version__:
        raise ContractError("unsupported_export_version")
    validate_baseline(report, report)
    if not 1 <= len(report["cases"]) <= 100:
        raise ContractError("invalid_export_case_count")
    output = []
    for case in report["cases"]:
        identifier(case["case_id"])
        if not isinstance(case.get("category"), str) or case["category"] not in CATEGORIES:
            raise ContractError("invalid_export_category")
        failure = case.get("failure")
        if "failure" not in case or type(case.get("unsafe_ready")) is not bool or not isinstance(failure, (str, type(None))) or failure not in {None, "provider_error", "invalid_model_output"}:
            raise ContractError("invalid_export_outcome")
        if case["passed"] and (failure is not None or case["unsafe_ready"]):
            raise ContractError("inconsistent_export_outcome")
        output.append({"case_id": case["case_id"], "category": case["category"], "checks": case["checks"],
                       "passed": case["passed"], "unsafe_ready": case["unsafe_ready"], "failure": case["failure"]})
    return sorted(output, key=lambda case: case["case_id"])


def export(report):
    if not isinstance(report, dict):
        raise ContractError("invalid_export_report")
    fingerprints = {}
    for field in ("dataset_sha256", "prompt_sha256", "schema_sha256"):
        value = report.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ContractError("invalid_export_fingerprint")
        fingerprints[field] = value
    provider = report.get("provider")
    if not isinstance(provider, dict) or not isinstance(provider.get("kind"), str) or provider["kind"] not in {"recorded", "recorded-trials", "ollama"}:
        raise ContractError("unknown_export_source")
    if "experiment_version" in report:
        _validated_experiment(report)
        attempts = [_single(run) for run in report["runs"]]
    else:
        attempts = [_single(report)]
    flattened = [case for trial in attempts for case in trial]
    return {"summary_export_version": 1, "mode": provider["kind"], "fingerprints": fingerprints,
            "trials": len(attempts), "case_attempts": len(flattened),
            "passed_attempts": sum(case["passed"] for case in flattened),
            "unsafe_ready": sum(case["unsafe_ready"] for case in flattened),
            "provider_errors": sum(case["failure"] == "provider_error" for case in flattened),
            "attempts": attempts, "publication_requires_human_review": True,
            "model_identity_omitted": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare a content-minimized summary for manual publication review.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        summary = export(parse_json(read_bounded_text(args.input)))
        write_report(args.output, summary, [args.input])
        print("Summary prepared for review. Nothing uploaded; identifiers still require checking.")
        return 0
    except (ContractError, OSError, UnicodeError, TypeError):
        print("Summary export rejected. No publication performed.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
