"""Execution guardrails, not a substitute for provider-side access and billing limits."""

import os

from .contracts import ContractError


def require_live_permission(allowed, environ=None):
    environment = os.environ if environ is None else environ
    ci = any(str(environment.get(name, "")).lower() not in {"", "0", "false", "no"}
             for name in ("CI", "GITHUB_ACTIONS"))
    if not allowed or ci:
        raise ContractError("live_execution_requires_local_opt_in")


class RequestBudget:
    def __init__(self, limit):
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ContractError("invalid_request_budget")
        self.limit = limit
        self.used = 0

    def reserve(self):
        if self.used >= self.limit:
            raise ContractError("request_budget_exhausted")
        self.used += 1


def execution_plan(cases, trials, max_requests, provider, timeout):
    budget = RequestBudget(max_requests)
    count = len(cases) * trials
    if count > budget.limit:
        raise ContractError("request_budget_exceeded")
    return {"plan_only": True, "cases": len(cases), "trials": trials,
            "planned_requests": count if provider != "recorded" else 0,
            "case_attempts": count, "request_limit": budget.limit,
            "mode": provider, "timeout_seconds_per_request": timeout,
            "estimated_cost": "not_available", "requests_sent": 0}
