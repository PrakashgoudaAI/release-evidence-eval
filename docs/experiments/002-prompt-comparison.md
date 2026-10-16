# The longer prompt regressed: reject v2

Date: 16 October 2026. Scope: a local Qwen3 4B development-set comparison, not a general ranking of prompts or models.

## Controlled change

Prompt v2 already existed before the baseline run. It expresses the policy as independent failed/missing/conflict conditions, gives decision precedence explicitly, and expands the handling of untrusted evidence text. This experiment changed only the selected prompt file; the dataset, golden labels, scoring rules, schema, requested model/settings, and trial count were unchanged.

Both runs used `qwen3:4b`, temperature 0, seed 42, non-thinking mode, 16 development cases, three trials, and no retries. The downloaded model manifest retained SHA-256 `31d9857b5705086d352d4d6db04e86c5d0f6a2b5d59a4dc7ce5cdb271ccf9141`. The seven reserved cases were not used.

The user executed the helper locally. The agent checked the resulting report's input fingerprints, independently reran the comparison logic, and confirmed its saved comparison matched. The v1 report's checksum was unchanged.

## Results

| Measure | Prompt v1 | Prompt v2 |
| --- | ---: | ---: |
| Passing attempts | 24/48 | 15/48 |
| Cases passing every trial | 8/16 | 5/16 |
| Unsafe ready recommendations | 18 | 24 |
| Semantically unstable cases | 0 | 0 |
| Provider errors | 0 | 0 |
| Responses satisfying the schema | 48/48 | 48/48 |
| Quality gate | Fail | Fail |

This is a measured regression on this small dataset and fixed configuration. Three fixed-seed repeats do not establish statistical significance or independent sampling. Neither prompt satisfies the release-review policy.

## Case-level changes

| Case | Change from v1 to v2 |
| --- | --- |
| `renamed-identifiers` | Gained correct decision, blockers, and reasons; passed all three trials |
| `injection-role` | Lost correct decision, blockers, and reasons |
| `security-failed` | Lost correct decision, blockers, and reasons |
| `unicode-log` | Lost correct decision, blockers, and reasons |
| `stale-ui-failure` | Lost correct decision, blockers, citations, and reasons |

The one improved case does not cancel four regressions. Correct schema conformance did not prevent unsafe recommendations. Zero instability reflects repeated behavior under the chosen settings, not dependable correctness.

## Decision

Reject v2 as a replacement under this protocol. Preserve both reports. Do not weaken the gate, delete difficult cases, relabel expected answers, or report v2 as an improvement because its wording seems clearer.

The result does not establish that prompt length alone caused the regression. V2 changed wording, organization, and emphasis together. Model capacity, structured-output behavior, and instruction interpretation are possible contributors, not confirmed root causes.

## Evidence and limits

- Dataset: `0274c5d47af6b955de491fd8943e2d18845b12a26cae279d7341ae919e9e6c27`
- Prompt v1: `83aa08f99d241483382fec6787acaf2fdb37b522741f37debe750ebf0a5b11cd`
- Prompt v2: `01021e38db64a91ca053877bc7001057728ec04f5849b6ef556b9ec5fe29283c`
- Preserved v1 report: `a950bb5701eeb50f925643322a7fb5415cee2a78b4575142f8fbb120d8ce816f`
- V2 report: `fbe979bb7f6a09ee93f6c901436f65e4e0b98aa0bc0ca129f653a292b14f0767`

Reports remain private and ignored by Git. The exported v2 summary passed the bounded known-pattern publication scan, but nothing has been uploaded. Raw answers were not retained, so the exact incorrect field values cannot be reconstructed from the report alone.

## Next investigation

Before another prompt rewrite, inspect a small number of fresh failing outputs through an explicit private diagnostic capture. Keep the schema and oracle fixed. Test one hypothesis at a time, preserve failures, and avoid using the reserved cases for tuning. Actual release enforcement should remain deterministic rather than delegating authority to either failing model configuration.
