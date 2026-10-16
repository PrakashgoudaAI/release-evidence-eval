"""Prove the evaluator rejects six targeted response faults, not just perfect fixtures."""

from release_eval.__main__ import ROOT, write_report
from release_eval.contracts import canonical, load_cases, parse_json
from release_eval.engine import evaluate
from release_eval.providers import RecordedProvider


def campaign():
    cases = load_cases(ROOT / "data/cases.jsonl")
    prompt = (ROOT / "prompts/reviewer.txt").read_text(encoding="utf-8")
    source = ROOT / "examples/reference-responses.jsonl"
    faults = [
        ("unsafe-ready", "injection-log", "decision", "ready"),
        ("omitted-blocker", "ui-failed", "blocking_evidence", []),
        ("invented-citation", "api-missing", "citations", ["u", "s", "invented"]),
        ("stale-citation", "stale-ui-failure", "citations", ["u", "a", "s", "old-u"]),
        ("hidden-conflict", "conflicting-api", "reason_codes", ["failed_check"]),
        ("malformed-json", "clean-ready", None, "not-json"),
    ]
    outcomes = []
    for name, case_id, field, value in faults:
        adapter = RecordedProvider(source, [case["id"] for case in cases])
        if field:
            output = parse_json(adapter.responses[case_id])
            output[field] = value
            adapter.responses[case_id] = canonical(output)
        else:
            adapter.responses[case_id] = value
        report = evaluate(cases, adapter, prompt)
        result = next(case for case in report["cases"] if case["case_id"] == case_id)
        outcomes.append({"fault": name, "case_id": case_id, "caught": not report["summary"]["gate_passed"],
                         "failed_checks": [key for key, passed in result["checks"].items() if not passed]})
    return {"kind": "targeted_response_faults_not_code_mutation_coverage", "outcomes": outcomes,
            "caught": sum(outcome["caught"] for outcome in outcomes), "total": len(outcomes)}


def main():
    report = campaign()
    write_report(ROOT / "reports/mutations.json", report, [])
    print("Caught %d/%d targeted response faults (offline fixtures, not model results)." %
          (report["caught"], report["total"]))
    return 0 if report["caught"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
