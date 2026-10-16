"""Task-specific, deterministic scoring and hard gates."""

from . import __version__
from .contracts import CATEGORIES, OUTPUT_SCHEMA, ContractError, canonical, digest, parse_json, validate_output
from .providers import ProviderError

CHECK_NAMES = ("schema", "decision", "blockers", "citations", "reasons")


def provenance(cases, prompt):
    return {"report_version": 2, "runner_version": __version__, "rubric_version": 1,
            "dataset_sha256": digest(canonical(cases)), "prompt_sha256": digest(prompt),
            "schema_sha256": digest(canonical(OUTPUT_SCHEMA))}


def evaluate(cases, provider, prompt):
    results = []
    for case in cases:
        checks = dict.fromkeys(CHECK_NAMES, False)
        output_hash, semantic_hash, failure, unsafe_ready = None, None, None, False
        try:
            raw = provider.respond(case, prompt, OUTPUT_SCHEMA)
            output_hash = digest(raw)
            actual = validate_output(parse_json(raw))
            normalized = {key: sorted(value) if isinstance(value, list) else value for key, value in actual.items()}
            semantic_hash = digest(canonical(normalized))
            checks["schema"] = True
            expected = case["expected"]
            checks["decision"] = actual["decision"] == expected["decision"]
            for check, field in (("blockers", "blocking_evidence"), ("citations", "citations"), ("reasons", "reason_codes")):
                checks[check] = set(actual[field]) == set(expected[field])
            unsafe_ready = actual["decision"] == "ready" and expected["decision"] != "ready"
        except ContractError:
            failure = "invalid_model_output"
        except ProviderError:
            failure = "provider_error"
        results.append({"case_id": case["id"], "category": case["category"], "checks": checks,
                        "passed": all(checks.values()), "unsafe_ready": unsafe_ready,
                        "failure": failure, "response_sha256": output_hash, "semantic_sha256": semantic_hash})
    results.sort(key=lambda item: item["case_id"])
    categories = {category: {"passed": sum(item["passed"] for item in results if item["category"] == category),
                             "total": sum(item["category"] == category for item in results)}
                  for category in sorted(CATEGORIES)}
    errors = sum(item["failure"] == "provider_error" for item in results)
    unsafe = sum(item["unsafe_ready"] for item in results)
    return {**provenance(cases, prompt), "provider": provider.metadata,
            "summary": {"passed": sum(item["passed"] for item in results), "total": len(results),
                        "provider_errors": errors, "unsafe_ready": unsafe,
                        "gate_passed": all(item["passed"] for item in results) and not errors and not unsafe},
            "categories": categories, "cases": results}


def validate_baseline(current, baseline):
    """Check comparability and internal case consistency before model calls."""
    if not isinstance(baseline, dict) or any(baseline.get(key) != current[key] for key in
        ("report_version", "runner_version", "rubric_version", "dataset_sha256", "schema_sha256")):
        raise ContractError("incompatible_baseline")
    previous = baseline.get("cases")
    if not isinstance(previous, list) or len(previous) != len(current["cases"]):
        raise ContractError("incompatible_baseline_cases")
    by_id = {}
    for item in previous:
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str) or item["case_id"] in by_id:
            raise ContractError("invalid_baseline_case")
        checks = item.get("checks")
        if not isinstance(checks, dict) or set(checks) != set(CHECK_NAMES) or any(type(v) is not bool for v in checks.values()):
            raise ContractError("invalid_baseline_checks")
        if type(item.get("passed")) is not bool or item["passed"] != all(checks.values()):
            raise ContractError("invalid_baseline_outcome")
        by_id[item["case_id"]] = item
    if set(by_id) != {item["case_id"] for item in current["cases"]}:
        raise ContractError("incompatible_baseline_cases")
    return by_id


def regressions(current, baseline):
    """Compare case-level outcomes; an improved average cannot hide a regression."""
    by_id = validate_baseline(current, baseline)
    return [{"case_id": item["case_id"], "lost_checks": [name for name in CHECK_NAMES
             if by_id[item["case_id"]]["checks"][name] and not item["checks"][name]]}
            for item in current["cases"] if any(by_id[item["case_id"]]["checks"][name] and not item["checks"][name]
                                                for name in CHECK_NAMES)]
