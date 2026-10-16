"""Repeated trials, split isolation, and paired criterion-level comparisons."""

from .contracts import ContractError, canonical, digest, keys, load_cases, load_lines
from .engine import CHECK_NAMES, evaluate


def load_splits(development_path, reserved_path):
    development, reserved = load_cases(development_path), load_cases(reserved_path)
    if {case["id"] for case in development} & {case["id"] for case in reserved}:
        raise ContractError("split_case_ids_overlap")
    # Ignore evidence order when catching reused packets with renamed case IDs.
    def packets(cases):
        return {digest(canonical({"revision": case["revision"],
                                  "evidence": sorted(case["evidence"], key=lambda item: item["id"])}))
                for case in cases}
    if packets(development) & packets(reserved):
        raise ContractError("split_evidence_packets_overlap")
    return {"development": development, "reserved": reserved}


class TrialRecordings:
    """Require a complete transcript for every trial; never silently replay one answer."""

    def __init__(self, path, cases, trials):
        validate_trials(trials)
        self.responses = {}
        for record in load_lines(path):
            keys(record, {"case_id", "trial", "response"})
            if not isinstance(record["case_id"], str) or type(record["trial"]) is not int or not isinstance(record["response"], str):
                raise ContractError("invalid_trial_record")
            key = (record["case_id"], record["trial"])
            if key in self.responses:
                raise ContractError("duplicate_trial_record")
            self.responses[key] = record["response"]
        required = {(case["id"], trial) for case in cases for trial in range(1, trials + 1)}
        if set(self.responses) != required:
            raise ContractError("incomplete_or_extra_trial_records")

    def provider(self, trial):
        responses = self.responses
        class View:
            metadata = {"kind": "recorded-trials", "model": "not_recorded"}
            def respond(self, case, prompt, schema):
                return responses[(case["id"], trial)]
        return View()


def validate_trials(trials):
    if type(trials) is not int or not 2 <= trials <= 5:
        raise ContractError("trials_must_be_between_two_and_five")


def run_experiment(cases, provider_factory, prompt, trials=3, split="development"):
    validate_trials(trials)
    if not 1 <= len(cases) <= 100:
        raise ContractError("invalid_case_count")
    if split not in {"development", "reserved"}:
        raise ContractError("invalid_split")
    runs = [evaluate(cases, provider_factory(trial), prompt) for trial in range(1, trials + 1)]
    if any(run["provider"] != runs[0]["provider"] for run in runs):
        raise ContractError("provider_changed_between_trials")
    by_trial = [{item["case_id"]: item for item in run["cases"]} for run in runs]
    outcomes = []
    for case in cases:
        attempts = [trial[case["id"]] for trial in by_trial]
        signatures = {item["semantic_sha256"] or item["failure"] for item in attempts}
        outcomes.append({"case_id": case["id"], "category": case["category"],
                         "pass_count": sum(item["passed"] for item in attempts),
                         "robust_pass": all(item["passed"] for item in attempts),
                         "unstable": len(signatures) > 1,
                         "criterion_pass_counts": {key: sum(item["checks"][key] for item in attempts) for key in CHECK_NAMES}})
    outcomes.sort(key=lambda item: item["case_id"])
    errors = sum(run["summary"]["provider_errors"] for run in runs)
    return {"experiment_version": 1, "trials": trials, "split": split,
            "report_version": runs[0]["report_version"], "runner_version": runs[0]["runner_version"],
            "rubric_version": runs[0]["rubric_version"], "dataset_sha256": runs[0]["dataset_sha256"],
            "schema_sha256": runs[0]["schema_sha256"], "prompt_sha256": runs[0]["prompt_sha256"],
            "provider": runs[0]["provider"], "cases": outcomes, "runs": runs,
            "summary": {"robust_passed": sum(item["robust_pass"] for item in outcomes), "total_cases": len(cases),
                        "total_attempts": len(cases) * trials,
                        "passed_attempts": sum(run["summary"]["passed"] for run in runs),
                        "unstable_cases": sum(item["unstable"] for item in outcomes),
                        "unsafe_ready": sum(run["summary"]["unsafe_ready"] for run in runs),
                        "provider_errors": errors,
                        "gate_passed": all(run["summary"]["gate_passed"] for run in runs)}}


def _validated_experiment(report):
    """Recompute aggregation instead of trusting a comparison input's summary."""
    if not isinstance(report, dict) or report.get("experiment_version") != 1:
        raise ContractError("invalid_experiment")
    trials = report.get("trials")
    validate_trials(trials)
    runs = report.get("runs")
    if not isinstance(runs, list) or len(runs) != trials or not isinstance(report.get("cases"), list):
        raise ContractError("invalid_trial_runs")
    ids = set()
    for case in report["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str) or case["case_id"] in ids:
            raise ContractError("invalid_experiment_case")
        ids.add(case["case_id"])
        counts = case.get("criterion_pass_counts")
        if not isinstance(counts, dict) or set(counts) != set(CHECK_NAMES) or any(type(value) is not int or not 0 <= value <= trials for value in counts.values()):
            raise ContractError("invalid_criterion_counts")
        attempts = []
        for run in runs:
            if not isinstance(run, dict) or any(run.get(key) != report.get(key) for key in
                ("report_version", "runner_version", "rubric_version", "dataset_sha256", "schema_sha256", "prompt_sha256", "provider")):
                raise ContractError("inconsistent_trial_metadata")
            if not isinstance(run.get("cases"), list):
                raise ContractError("invalid_trial_cases")
            entries = [entry for entry in run["cases"] if isinstance(entry, dict) and entry.get("case_id") == case["case_id"]]
            if len(entries) != 1 or len(run["cases"]) != len(report["cases"]):
                raise ContractError("invalid_trial_cases")
            entry = entries[0]
            checks = entry.get("checks")
            if not isinstance(checks, dict) or set(checks) != set(CHECK_NAMES) or any(type(value) is not bool for value in checks.values()):
                raise ContractError("invalid_trial_checks")
            if type(entry.get("passed")) is not bool or entry["passed"] != all(checks.values()):
                raise ContractError("invalid_trial_outcome")
            if not isinstance(entry.get("semantic_sha256"), (str, type(None))) or not isinstance(entry.get("failure"), (str, type(None))):
                raise ContractError("invalid_trial_signature")
            attempts.append(entry)
        actual_counts = {key: sum(entry["checks"][key] for entry in attempts) for key in CHECK_NAMES}
        robust = all(entry["passed"] for entry in attempts)
        unstable = len({entry["semantic_sha256"] or entry["failure"] for entry in attempts}) > 1
        if counts != actual_counts or type(case.get("robust_pass")) is not bool or case["robust_pass"] != robust or \
           type(case.get("unstable")) is not bool or case["unstable"] != unstable or \
           type(case.get("pass_count")) is not int or case["pass_count"] != sum(entry["passed"] for entry in attempts):
            raise ContractError("inconsistent_experiment_aggregation")
    if not ids:
        raise ContractError("empty_experiment")
    return {case["case_id"]: case for case in report["cases"]}


def compare_experiments(candidate, baseline):
    candidate_cases, baseline_cases = _validated_experiment(candidate), _validated_experiment(baseline)
    for key in ("experiment_version", "report_version", "runner_version", "rubric_version", "dataset_sha256", "schema_sha256", "trials", "split"):
        if candidate.get(key) != baseline.get(key):
            raise ContractError("incompatible_experiments")
    if set(candidate_cases) != set(baseline_cases):
        raise ContractError("incompatible_experiment_cases")
    regressions, improvements = [], []
    for case_id in sorted(candidate_cases):
        current, previous = candidate_cases[case_id], baseline_cases[case_id]
        lost = [key for key in CHECK_NAMES if current["criterion_pass_counts"][key] < previous["criterion_pass_counts"][key]]
        gained = [key for key in CHECK_NAMES if current["criterion_pass_counts"][key] > previous["criterion_pass_counts"][key]]
        if lost or (current["unstable"] and not previous["unstable"]):
            regressions.append({"case_id": case_id, "lost_criteria": lost,
                                "new_instability": current["unstable"] and not previous["unstable"]})
        if gained:
            improvements.append({"case_id": case_id, "gained_criteria": gained})
    return {"regressions": regressions, "improvements": improvements,
            "no_regression": not regressions, "statistical_significance_claimed": False}
