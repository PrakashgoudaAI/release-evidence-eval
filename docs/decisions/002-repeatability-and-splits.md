# 002 — Keep trial failures visible and reserve cases before prompt tuning

Status: accepted for the offline 0.2 milestone.

## Decision

Add a distinct repeated-trial report rather than flattening repeated answers into the existing single-run format. Every case must pass every trial. Record semantic instability independently of correctness, normalize only array ordering and JSON formatting, and retain criterion-level results for each attempt.

Recorded trials must provide the complete case-by-trial Cartesian product. Never silently reuse an answer to fill a missing trial. A transcript can be authored, so completeness is an input integrity check, not proof that a model was called. Live adapters are called again for each case/trial; no response cache or automatic retry is used.

Separate development and reserved case files, each with all seven risk slices. Reject shared case IDs and exact evidence packets. Split and input fingerprints are part of comparison compatibility. Keep the same trial count for candidate/baseline comparisons. Prompt and provider metadata can differ because those are explicit experiment variables; users remain responsible for controlling hardware, runtime, and sampling settings.

## Why not an average threshold?

An answer that follows a malicious log instruction once in three trials is not rescued by two correct answers. A newly unstable answer is a regression even if criterion pass counts stay unchanged. Improvements in other cases remain visible but cannot cancel a loss.

## Limits

These small public datasets share a policy and related scenario patterns. Exact overlap rejection is not proof against semantic leakage or training contamination. The reserved cases are not automatically a blind held-out benchmark. Review their use history, avoid tuning on them, and retire them when their failures inform prompt changes.

Two to five trials support affordable diagnosis, not statistically conclusive model ranking. No confidence interval or significance claim is made. Report and runner versions change when report semantics change; old baselines must be regenerated.
