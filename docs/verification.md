# Verification — local milestones

Date: 16 October 2026. Environment: macOS, Python 3.9.6 supplied by the host. Earlier sections record historical milestones; current results and limitations are summarized below.

## Current summary

- 103 automated tests pass locally. Offline reference, mutation, repeated-trial negative-control, and policy-guard checks pass.
- Qwen3 development results: v1 24/48 passing attempts, v2 15/48, v3 12/48. All failed the quality gate; both candidates were rejected. See the [v3 study](experiments/004-v3-comparison.md).
- A private 12-response diagnostic replay accepted four correct recommendations and rejected eight incorrect ones through the new [policy guard](policy-guard.md). This selected development sample is not held-out validation and does not improve raw model accuracy.
- The guard accepted all 16 authored development answers and rejected 32 deliberately wrong decisions. It does not authorize deployment or authenticate evidence.
- Known-pattern source scanning passed, but Git history is unavailable because this project is not a Git repository. No full security-audit claim is made.
- Reserved-model evaluation and independent review remain outstanding. The source is published on [review pull request #1](https://github.com/PrakashgoudaAI/release-evidence-eval/pull/1); it is not merged.
- All four Python 3.11/3.13 Linux/Windows jobs passed in [the initial CI run](https://github.com/PrakashgoudaAI/release-evidence-eval/actions/runs/38909886088), at commit `49494e8aec8e706fc26ed3e9335b87465124f597`. The downloaded branch archive contained exactly 44 source files, all byte-identical to reviewed local inputs, with no private reports or unexpected files. Later documentation updates trigger their own verification runs.

## Initial 0.1 milestone

- 47 standard-library unittest checks passed.
- All 16 authored reference responses passed the evaluator.
- All six targeted response faults were rejected.
- Compatible baseline comparison passed in automated CLI tests, including a path containing spaces.
- Negative tests verified exit code 1 for a quality failure and exit code 2 for invalid inputs and provider failures.
- Mocked transport checks verified request construction, withheld labels, proxy disabling, redirect rejection, timeout behavior, and envelope validation.
- A fresh source-only copy (without reports or caches) passed the same 47 tests, 16-case reference run, six-fault campaign, and explicit baseline-comparison command. No package installation was required.

These are harness results. The fixture score is not model accuracy. Adapter tests use test doubles and do not establish compatibility with an installed Ollama runtime.

## Stronger offline 0.2 milestone

The user explicitly selected an offline milestone; no runtime or model was installed.

- All 73 tests passed, including the original suite and repeated-trial/split-integrity checks.
- Added seven policy-validated reserved cases, covering every risk slice separately from the 16 development cases.
- The three-trial negative control caught one unsafe answer in the third trial: 47/48 attempts passed, but promotion failed with 15/16 robustly passing cases.
- Semantic array-order/whitespace normalization, stably wrong outcomes, new instability with unchanged criterion counts, request budgets, transcript completeness, and invalid-baseline preflight are tested.
- Prompt v2 is implemented as a candidate, not a claimed improvement. No model has generated answers under either prompt here.
- Report format is now version 2; the runner is 0.2.0. Older baselines require regeneration.
- Final source-only copy verification passed all 73 tests, the repeated-trial negative control, all six targeted faults, the 16-case reference run, and explicit baseline comparison without installed dependencies.

Both ordinary and repeated-trial reports omit raw content. The new failure-analysis walkthrough is a synthetic negative control, not an attributed model incident.

## Not yet verified

- Independent runtime API attestation and model comparisons across different settings/hardware.
- Downloaded CI-report artifact review (the source archive has been reviewed separately).
- Held-out evaluation, natural-language claim scoring, tool-use safety, or independent security review.

## Publication-safety milestone

After the user confirmed no hosted API account was available, strengthened the local execution and publication path without creating an account or making paid calls.

- 92 tests pass locally, including explicit live-call permission, CI network blocking, failed-request budget consumption, zero-call planning, and publication export checks.
- Known-pattern source scanning passed. The real project has no Git repository, so its history is unavailable and is not claimed clean.
- A temporary test repository verified detection of a synthetic token removed from current files but still reachable in history. Matched values were not printed.
- The allowlisted summary export passed an explicit artifact scan. It omits raw/private fields and model names; identifiers and fingerprints still require human review.
- The README now describes the task directly, without promotional claims. No model accuracy or prompt improvement was invented.

No hosted adapter/account, local runtime, or real-model evaluation is available yet. CI is configured but remains unexecuted for this unpublished project. Guardrails are not a comprehensive security audit or a provider-side spending cap.

## Local runtime setup — 16 October 2026

The user installed Ollama 0.40.5 and started it through the local-only launcher. A read-only listener check observed `127.0.0.1:11434`, not a wildcard/network-interface bind. The launcher requests cloud disablement and a small environment; this is not a claim that all runtime behavior has been independently audited.

The user downloaded `qwen3:4b`. All six model-manifest blobs were present, had their expected sizes, and passed SHA-256 checks against the manifest. The downloaded manifest's SHA-256 is `31d9857b5705086d352d4d6db04e86c5d0f6a2b5d59a4dc7ce5cdb271ccf9141`. The principal weights blob is `sha256:3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f`. File verification is not evidence that inference works or that a model is safe.

The adapter now rejects `:cloud` names and requests non-thinking mode for Qwen3, with both behaviors tested. All 94 tests pass locally. The agent's localhost requests are denied by its environment (errno 1), and Terminal access is unavailable. A user-run local evaluation helper was prepared with 48 requests, private report permissions, and a fresh report directory per run. No live evaluation result is claimed until those files are actually produced and reviewed.

## First real-model baseline

The user-run helper produced a private report for Qwen3 4B, three trials across 16 development cases. The report's structure and input fingerprints were checked; its totals were independently recomputed: 24/48 passing attempts, 8/16 robust passes, 18 unsafe-ready attempts, zero provider errors, and zero unstable cases. All 48 outputs satisfied the schema. The quality gate failed.

See [the baseline study](experiments/001-qwen3-baseline.md) for configuration, case-level findings, fingerprints, and limitations. The source report is preserved unchanged with SHA-256 `a950bb5701eeb50f925643322a7fb5415cee2a78b4575142f8fbb120d8ce816f`. No raw responses were retained, so exact wrong reason/citation sets and complete root causes cannot be reconstructed. Prompt v2 and reserved-set performance remain unmeasured. No claim of improvement, exfiltration, or production reliability is made.

## Actual prompt comparison

Prompt v2 completed with 15/48 passing attempts, 5/16 robust passes, 24 unsafe-ready attempts, zero provider errors, and zero semantic instability. All outputs satisfied the schema. The report's fingerprints matched current inputs, and an independently recomputed comparison matched the saved comparison: four case regressions and one improvement. V2 was rejected. The baseline and downloaded model-manifest checksums remained unchanged.

The comparison report SHA-256 is `fbe979bb7f6a09ee93f6c901436f65e4e0b98aa0bc0ca129f653a292b14f0767`. See [the comparison study](experiments/002-prompt-comparison.md). The v2 review-summary known-pattern scan passed; no upload occurred. Raw answers and a complete root cause remain unavailable, and reserved-set performance is still unmeasured.

## Before publishing

1. Review all 23 expected labels against the policy, not just the oracle; keep reserved-case use separate from tuning.
2. Repeat the clean source-only verification in the configured CI environments; the local copy check is complete.
3. Publish to a review branch and require the CI matrix to pass.
4. Inspect artifacts for synthetic-only metadata and update this record with run links.
5. Keep any profile claim within the documented synthetic development results; do not claim production readiness or improved model accuracy.

## Next experiment

Do not continue blind prompt iteration after the rejected candidates. If further inference is authorized, make one controlled change and state its hypothesis first. Record model/runtime identity, settings, and input fingerprints. Use the repeated-trial runner without silently retrying failures. Preserve the reserved split for a separate check and retire it once its failures inform tuning. Keep raw model outcomes separate from guard outcomes and keep failures visible in the final case study.
