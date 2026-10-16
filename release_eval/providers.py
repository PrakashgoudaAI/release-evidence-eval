"""Recorded outputs and an opt-in, loopback-only Ollama transport."""

import re
from urllib import error, request

from .contracts import MAX_BYTES, ContractError, canonical, keys, load_lines, parse_json
from .safety import RequestBudget, require_live_permission


class ProviderError(RuntimeError):
    pass


class RecordedProvider:
    def __init__(self, path, case_ids):
        self.responses = {}
        for item in load_lines(path):
            keys(item, {"case_id", "response"})
            if not isinstance(item["case_id"], str) or not isinstance(item["response"], str):
                raise ContractError("invalid_recorded_response")
            if item["case_id"] in self.responses:
                raise ContractError("duplicate_recorded_response")
            self.responses[item["case_id"]] = item["response"]
        if set(self.responses) != set(case_ids):
            raise ContractError("response_case_ids_do_not_match")
        self.metadata = {"kind": "recorded", "model": "not_recorded"}

    def respond(self, case, prompt, schema):
        return self.responses[case["id"]]


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("redirect_rejected")


class OllamaProvider:
    def __init__(self, model, port=11434, timeout=30, transport=None, request_budget=100):
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model):
            raise ContractError("invalid_model_name")
        if model.lower().endswith(":cloud"):
            raise ContractError("cloud_model_not_allowed")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ContractError("invalid_port")
        if type(timeout) is not int or not 1 <= timeout <= 30:
            raise ContractError("invalid_timeout")
        self.model, self.port, self.timeout = model, port, timeout
        self.transport = transport or self._send
        self.budget = RequestBudget(request_budget)
        self.metadata = {"kind": "ollama", "model": model, "temperature": 0, "seed": 42}
        if model.lower().startswith("qwen3:"):
            self.metadata["thinking"] = False

    def _send(self, payload):
        # Network transport is also blocked in CI when called outside the CLI.
        require_live_permission(True)
        # Ignore proxy environment variables and reject redirects: prompts stay on loopback.
        opener = request.build_opener(request.ProxyHandler({}), _NoRedirect())
        req = request.Request("http://127.0.0.1:%d/api/chat" % self.port,
                              data=canonical(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
        with opener.open(req, timeout=self.timeout) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ProviderError("provider_response_too_large")
        return raw.decode("utf-8")

    def respond(self, case, prompt, schema):
        # The model never receives golden labels or category names.
        evidence = {key: case[key] for key in ("revision", "evidence")}
        payload = {"model": self.model, "stream": False, "format": schema,
                   "options": {"temperature": 0, "seed": 42},
                   "messages": [{"role": "system", "content": prompt},
                                {"role": "user", "content": canonical(evidence)}]}
        if "thinking" in self.metadata:
            payload["think"] = self.metadata["thinking"]
        try:
            self.budget.reserve()
        except ContractError as exc:
            raise ProviderError("request_budget_exhausted") from exc
        try:
            envelope = parse_json(self.transport(payload))
            if not isinstance(envelope, dict) or envelope.get("done") is not True:
                raise ProviderError("incomplete_provider_response")
            message = envelope.get("message")
            if not isinstance(message, dict) or message.get("role") != "assistant" or message.get("tool_calls"):
                raise ProviderError("invalid_provider_message")
            content = message.get("content")
            if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_BYTES:
                raise ProviderError("invalid_provider_content")
            return content
        except ProviderError:
            raise
        except (error.URLError, TimeoutError, OSError, UnicodeError, ContractError) as exc:
            raise ProviderError("provider_transport_or_envelope_error") from exc
