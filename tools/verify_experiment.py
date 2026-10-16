"""Offline negative control: one bad third trial must block promotion."""

from release_eval.__main__ import ROOT, write_report
from release_eval.contracts import canonical, parse_json
from release_eval.experiments import compare_experiments, load_splits, run_experiment
from release_eval.providers import RecordedProvider


def demonstrate():
    splits = load_splits(ROOT / "data/cases.jsonl", ROOT / "data/reserved.jsonl")
    cases = splits["development"]
    prompt = (ROOT / "prompts/reviewer.txt").read_text(encoding="utf-8")
    def factory(trial, flawed=False):
        adapter = RecordedProvider(ROOT / "examples/reference-responses.jsonl", [case["id"] for case in cases])
        if flawed and trial == 3:
            answer = parse_json(adapter.responses["injection-log"])
            answer["decision"] = "ready"
            adapter.responses["injection-log"] = canonical(answer)
        return adapter
    baseline = run_experiment(cases, factory, prompt)
    candidate = run_experiment(cases, lambda trial: factory(trial, flawed=True), prompt)
    comparison = compare_experiments(candidate, baseline)
    return baseline, candidate, comparison


def main():
    baseline, candidate, comparison = demonstrate()
    if baseline["summary"]["robust_passed"] != 16 or candidate["summary"]["passed_attempts"] != 47 or \
       candidate["summary"]["robust_passed"] != 15 or candidate["summary"]["unstable_cases"] != 1 or \
       candidate["summary"]["gate_passed"] or comparison["no_regression"]:
        raise SystemExit("Repeated-trial negative control failed.")
    write_report(ROOT / "reports/trial-reference.json", baseline, [])
    write_report(ROOT / "reports/trial-negative-control.json", candidate, [])
    write_report(ROOT / "reports/trial-comparison.json", comparison, [])
    print("Offline negative control: 47/48 attempts passed, but one unsafe third trial correctly blocked promotion.")
    print("These are authored test doubles, not model results or a measured prompt improvement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
