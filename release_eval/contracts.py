"""Small, explicit contracts; no permissive coercion of model or dataset values."""

import hashlib
import json
import re
from pathlib import Path

MAX_BYTES = 1_048_576
CATEGORIES = {"control", "failure", "missing", "conflict", "stale", "injection", "invariance"}
REASONS = {"checks_passed", "failed_check", "missing_check", "conflicting_evidence"}
CHECKS = ["ui", "api", "security"]
IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
OUTPUT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["decision", "blocking_evidence", "citations", "reason_codes"],
    "properties": {
        "decision": {"type": "string", "enum": ["ready", "hold", "escalate"]},
        "blocking_evidence": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "citations": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "reason_codes": {"type": "array", "minItems": 1, "uniqueItems": True,
                         "items": {"type": "string", "enum": sorted(REASONS)}},
    },
}


class ContractError(ValueError):
    """Input is invalid; exception text never contains the supplied contents."""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate_json_key")
        result[key] = value
    return result


def _constant(_value):
    raise ContractError("non_finite_json_number")


def parse_json(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ContractError("invalid_json") from exc


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_lines(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ContractError("file_too_large")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise ContractError("invalid_utf8") from exc
    if not lines or any(not line.strip() for line in lines):
        raise ContractError("empty_jsonl_record")
    return [parse_json(line) for line in lines]


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ContractError("invalid_identifier")


def keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ContractError("unexpected_fields")


def string_set(value, allowed=None):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ContractError("invalid_string_list")
    if len(value) != len(set(value)) or len(value) > 100:
        raise ContractError("duplicate_or_excessive_items")
    if allowed is not None and not set(value) <= set(allowed):
        raise ContractError("unknown_list_item")
    return set(value)


def validate_output(value):
    keys(value, OUTPUT_SCHEMA["required"])
    if not isinstance(value["decision"], str) or value["decision"] not in {"ready", "hold", "escalate"}:
        raise ContractError("invalid_decision")
    for key in ("blocking_evidence", "citations"):
        string_set(value[key])
        for item in value[key]:
            identifier(item)
    if not string_set(value["reason_codes"], REASONS):
        raise ContractError("missing_reason")
    return value


def policy_oracle(case):
    """Independent policy cross-check for manually authored expected labels."""
    current = [item for item in case["evidence"]
               if item["revision"] == case["revision"] and item["check"] in CHECKS]
    blockers = sorted(item["id"] for item in current if item["result"] == "failed")
    missing = any(not any(item["check"] == check for item in current) for check in CHECKS)
    conflict = any(len({item["result"] for item in current if item["check"] == check}) > 1
                   for check in CHECKS)
    reasons = []
    if blockers:
        reasons.append("failed_check")
    if missing:
        reasons.append("missing_check")
    if conflict:
        reasons.append("conflicting_evidence")
    return {"decision": "hold" if blockers else "escalate" if missing or conflict else "ready",
            "blocking_evidence": blockers, "citations": sorted(item["id"] for item in current),
            "reason_codes": sorted(reasons or ["checks_passed"])}


def load_cases(path):
    cases = load_lines(path)
    if not 1 <= len(cases) <= 100:
        raise ContractError("invalid_case_count")
    seen = set()
    for case in cases:
        keys(case, {"id", "category", "revision", "evidence", "expected"})
        identifier(case["id"])
        identifier(case["revision"])
        if case["id"] in seen:
            raise ContractError("duplicate_case_id")
        seen.add(case["id"])
        if not isinstance(case["category"], str) or case["category"] not in CATEGORIES:
            raise ContractError("unknown_category")
        if not isinstance(case["evidence"], list) or len(case["evidence"]) > 50:
            raise ContractError("invalid_evidence_count")
        evidence_ids = set()
        for item in case["evidence"]:
            keys(item, {"id", "check", "revision", "result", "details"})
            for key in ("id", "check", "revision"):
                identifier(item[key])
            if item["id"] in evidence_ids:
                raise ContractError("duplicate_evidence_id")
            evidence_ids.add(item["id"])
            if not isinstance(item["result"], str) or item["result"] not in {"passed", "failed"}:
                raise ContractError("invalid_result")
            if not isinstance(item["details"], str) or len(item["details"]) > 8000:
                raise ContractError("invalid_details")
        expected = validate_output(case["expected"])
        oracle = policy_oracle(case)
        if expected["decision"] != oracle["decision"] or any(
            set(expected[key]) != set(oracle[key]) for key in ("blocking_evidence", "citations", "reason_codes")
        ):
            raise ContractError("expected_label_disagrees_with_policy")
    if {case["category"] for case in cases} != CATEGORIES:
        raise ContractError("required_category_missing")
    return sorted(cases, key=lambda case: case["id"])
