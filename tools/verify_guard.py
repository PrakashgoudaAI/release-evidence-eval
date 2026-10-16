"""Offline guard checks against authored development answers and deliberate faults."""

from release_eval.__main__ import ROOT
from release_eval.contracts import canonical, load_cases
from release_eval.guard import guard_recommendation


def main():
    accepted, rejected, faults = 0, 0, 0
    cases = load_cases(ROOT / "data/cases.jsonl")
    for case in cases:
        packet = {key: case[key] for key in ("revision", "evidence")}
        answer = case["expected"]
        accepted += guard_recommendation(packet, canonical(answer))["accepted"]
        for decision in sorted({"ready", "hold", "escalate"} - {answer["decision"]}):
            faults += 1
            rejected += not guard_recommendation(packet, canonical(dict(answer, decision=decision)))["accepted"]
    print("Authored answers accepted: %d/%d; wrong-decision faults rejected: %d/%d." %
          (accepted, len(cases), rejected, faults))
    print("Offline fixtures only; not model accuracy, evidence authenticity, or deployment authorization.")
    return 0 if accepted == len(cases) and rejected == faults else 1


if __name__ == "__main__":
    raise SystemExit(main())
