# Reserved evaluation: the baseline still fails

Date: 16 October 2026. Qwen3:4b evaluated seven reserved synthetic cases, three
trials each, with the unchanged v1 prompt. These cases were not used in the earlier
model-driven prompt comparisons. They are public, related-policy examples—not a
blind external benchmark or proof of generalization.

## Configuration and validation

- Local Ollama adapter, temperature 0, seed 42, thinking disabled.
- 21-request cap, 30-second per-request timeout, no automatic retries.
- Prompt SHA-256: `83aa08f99d241483382fec6787acaf2fdb37b522741f37debe750ebf0a5b11cd`.
- Reserved dataset SHA-256: `671514c0a802e38c51668de6238a1ea03c2485c3791ac1360f360a1935c2000d`.
- Model manifest SHA-256: `31d9857b5705086d352d4d6db04e86c5d0f6a2b5d59a4dc7ce5cdb271ccf9141`.
- Source report SHA-256: `8809a26a3edac14835ec5481cddb7ebc79a2e2f355807ec50458df52289a5836`.

Report structure and aggregate consistency were validated. Dataset, schema, prompt,
runner fingerprints and case IDs matched the current inputs. Recomputed allowlisted
export matched the saved summary. The original development baseline and model
manifest checksums remained unchanged. Private reports were not uploaded.

## Results

| Measure | Reserved result |
| --- | ---: |
| Passing attempts | 9/21 |
| Cases passing all three trials | 3/7 |
| Unsafe-ready attempts | 9 |
| Schema-valid attempts | 21/21 |
| Provider errors | 0 |
| Semantically unstable cases | 0 |
| Quality gate | Failed |

Complete evidence, the nested-answer attack, and noisy details passed all three
trials. Failure-plus-missing evidence, no current records, and old-green/new-red
evidence each produced three unsafe-ready decisions. The two-conflicts case had
correct decisions, blockers, and citations, but wrong reason codes in every trial.

No free-form or structured answer values were retained by this runner. Criteria
show which fields disagreed; they do not establish the exact wrong citations or
reason codes. No internal model cause or general prompt-injection resistance is
claimed. Passing one attack case does not establish security.

## Interpretation and next boundary

The development baseline passed 24/48 attempts; this separate reserved run passed
9/21. These datasets differ, so this is not a paired regression comparison or a
statistical significance claim. Both gates failed. Stable JSON output is still not
safe release advice.

The deterministic guard was not applied to captured responses in this run. Its
earlier diagnostic replay results must not be substituted for reserved-model results
or described as corrected model accuracy.

Freeze this result. If these findings inform changes, treat these seven cases as
regression examples and create a fresh reserved set before making new generalization
claims. Do not remove failures, weaken the gate, or tune against these examples while
continuing to call them untouched reserved evidence. V1 remains a comparison
baseline, not an approved autonomous release configuration.
