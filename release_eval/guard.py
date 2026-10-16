"""Fail-closed recommendation checks, independent of authored expected labels.

Acceptance is policy consistency, never release authorization or evidence authenticity.
"""

from .contracts import (MAX_BYTES, ContractError, identifier, keys, parse_json,
                        validate_output)


def _facts(packet):
    keys(packet, {"revision", "evidence"})
    identifier(packet["revision"])
    records = packet["evidence"]
    if not isinstance(records, list) or len(records) > 50:
        raise ContractError("invalid_evidence_count")
    ids = set()
    groups = {name: {"passed": set(), "failed": set()} for name in ("ui", "api", "security")}
    for record in records:
        keys(record, {"id", "check", "revision", "result", "details"})
        for field in ("id", "check", "revision"):
            identifier(record[field])
        if record["id"] in ids:
            raise ContractError("duplicate_evidence_id")
        ids.add(record["id"])
        if not isinstance(record["result"], str) or record["result"] not in {"passed", "failed"}:
            raise ContractError("invalid_result")
        if not isinstance(record["details"], str) or len(record["details"]) > 8000:
            raise ContractError("invalid_details")
        if record["revision"] == packet["revision"] and record["check"] in groups:
            groups[record["check"]][record["result"]].add(record["id"])
    return groups


def guard_recommendation(packet, response):
    """Return safe status codes only; no raw content, repaired answer, or tool action."""
    rejected = lambda code: {"accepted": False, "violations": [code], "authorizes_release": False}
    try:
        groups = _facts(packet)
    except (ContractError, RecursionError):
        return rejected("invalid_evidence")
    try:
        if not isinstance(response, str) or len(response.encode("utf-8")) > MAX_BYTES:
            return rejected("invalid_recommendation")
        answer = validate_output(parse_json(response))
    except (ContractError, UnicodeError, RecursionError):
        return rejected("invalid_recommendation")

    blockers, citations, reasons = set(), set(), set()
    for outcomes in groups.values():
        blockers.update(outcomes["failed"])
        citations.update(outcomes["passed"] | outcomes["failed"])
        if not outcomes["passed"] and not outcomes["failed"]:
            reasons.add("missing_check")
        if outcomes["passed"] and outcomes["failed"]:
            reasons.add("conflicting_evidence")
    if blockers:
        reasons.add("failed_check")
    decision = "hold" if blockers else "escalate" if "missing_check" in reasons else "ready"
    expected = {"decision": decision, "blocking_evidence": blockers,
                "citations": citations, "reason_codes": reasons or {"checks_passed"}}
    violations = []
    for field, value in expected.items():
        actual = answer[field] if field == "decision" else set(answer[field])
        if actual != value:
            violations.append(field + "_mismatch")
    return {"accepted": not violations, "violations": violations, "authorizes_release": False}
