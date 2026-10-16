# Before making the repository public

The public deliverable is code, synthetic cases, and reviewed evidence. It is not an open inference service.

## Source and history

- Run all automated checks from a clean source-only copy.
- Run `python3 -m tools.publication_check` and investigate findings or incomplete scans.
- Confirm the scan actually includes available Git history; a source-only pass does not establish clean history.
- Review all proposed files manually. Known credential patterns do not catch arbitrary passwords, personal information, or employer material.
- If an actual credential was committed, revoke it before any history remediation. Never rely on deletion alone.

## Results

- Identify fixture, test-double, recorded-unattributed, and real-model results accurately. Do not present the crafted 47/48 failure as a model incident.
- Export a content-minimized summary, then scan that exact file explicitly.
- Review case identifiers, fingerprints, model information added to a case study, and screenshots before publishing.
- Report runtime/model identity separately only after review. The exporter omits model names deliberately; it is not a complete reproducibility record.
- Keep raw responses, private logs, credentials, and account/billing details outside the public repository.
- Exclude the entire reports directory, including private diagnostic contract outputs, even when a file passes the credential-pattern scan. Ignore rules alone do not protect files selected manually for browser upload.
- Report guard acceptance separately from model correctness. Never describe rejected recommendations as corrected model answers.

## CI and live calls

- Keep public CI offline and credential-free. Do not add model secrets to pull-request workflows.
- Use a private, explicitly authorized execution environment for hosted model calls if a provider is added later.
- Review request and token limits, timeout behavior, provider retention terms, and billing controls before spending money. A request-count cap does not guarantee a dollar cap.
- Do not publish an endpoint that lets strangers spend your credits. No such endpoint is implemented here.

## Current status

No hosted account or API key is configured and no paid calls were made. Ollama and Qwen3 4B are installed locally. Development and reserved model evaluations failed their quality gates; see the scoped studies rather than treating fixture scores as model results. The local publication scan is a bounded known-pattern check, not a comprehensive security certification. The implementation was merged through pull request #1 in PrakashgoudaAI/release-evidence-eval. The four-job CI matrix passed; follow-up artifact review confirmed matching parsed report contents across platforms. Independent review remains outstanding. Reserved findings are frozen separately and have not been used to retune prompts or the guard.
