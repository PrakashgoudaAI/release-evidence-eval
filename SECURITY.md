# Security and data handling

This project evaluates synthetic recommendations. It is not an authentication service, deployment gate, or security certification tool.

The optional Ollama adapter sends the prompt and evidence to a loopback HTTP endpoint. It ignores environment proxies, rejects redirects, bounds response reads, does not execute model tools, and never retries automatically. A local Ollama service can still be misconfigured or use a remote model. Verify the runtime before introducing any non-synthetic data.

Both CLIs require an explicit `--allow-live` flag for model calls. Network transport also rejects execution in CI. Request limits are checked before execution and consumed before each attempted provider call. A planning mode sends nothing. These are guardrails against mistakes, not authorization boundaries against someone who can modify the code, nor provider-side billing limits. The workflow has no model credential configuration and must stay offline for untrusted contributions.

Default reports contain identifiers, model metadata, checks, and hashes rather than raw content. Hashing is not anonymization, and identifier validation is not content redaction. Review inputs, artifact access, and retention before adapting this pattern to private systems.

Use the allowlisted summary exporter before reviewing a result for publication. It drops raw/private fields and model names, but still includes identifiers and hashes. Run the publication checker on both the source and the exact proposed artifact. Known-pattern detection is incomplete by nature. Reachable history can be scanned only when available; unavailable history is reported and requires later review. If a real credential is exposed, revoke/rotate it first; deleting the current file or hiding a report is not sufficient.

Do not include credentials or exploit payloads from real systems in public issues. Report a suspected vulnerability privately to the repository owner through an available private channel; do not assume GitHub private vulnerability reporting has been enabled. No response-time commitment is advertised.
