# A five-minute walkthrough

## The problem

An assistant reads CI evidence and recommends ready, hold, or escalate. A valid JSON
answer can still miss a failed check, trust an old result, or follow instructions
inside a log. This project measures those errors separately instead of treating a
well-formed response as a correct one.

The policy is deliberately small: require current-revision UI, API, and security
evidence. Any failure means hold; missing evidence without a failure means escalate.
Every qualifying record must be cited, and all applicable reasons must be reported.

## Where each responsibility lives

| Component | Responsibility |
| --- | --- |
| `contracts.py` | Reject malformed input/output; cross-check authored labels |
| `providers.py` | Send evidence and policy, never expected answers; bound local requests |
| `engine.py` | Score decision, blockers, citations, reasons, and schema independently |
| `experiments.py` | Repeat trials, compare compatible runs, expose regressions |
| `guard.py` | Reject policy-inconsistent recommendations without repairing them |
| `tools/export_summary.py` | Prepare content-minimized reports for human review |

The benchmark scorer and guard have separate policy implementations, but share
contract validation. That shared dependency is a limitation, not full independence.
Neither component authenticates CI evidence or deploys software.

## Reproduce the offline checks

From the repository root, with Python installed:

```sh
python3 -m unittest discover -s tests -v
python3 -m release_eval --responses examples/reference-responses.jsonl
python3 -m tools.verify_mutations
python3 -m tools.verify_experiment
python3 -m tools.verify_guard
```

These commands need no API key, model download, or network call. Reference answers
are authored fixtures, not a model benchmark. The repeated-trial negative control
deliberately creates one unsafe third-trial answer: 47/48 attempts pass, yet promotion
is blocked. The guard check accepts 16 authored answers and rejects 32 deliberately
wrong decisions. Unit tests cover additional malformed and policy-inconsistent cases.

## What the actual model runs showed

Qwen3:4b ran locally against 16 synthetic development cases, three trials per case,
temperature 0, seed 42, thinking disabled. Inputs, settings, and limitations are
recorded in the experiment studies.

| Prompt | Passing attempts | Unsafe ready recommendations | Outcome |
| --- | ---: | ---: | --- |
| V1 | 24/48 | 18 | Failed gate; retained as comparison baseline |
| V2 | 15/48 | 24 | Rejected |
| V3 | 12/48 | 24 | Rejected |

All responses satisfied the output schema. That did not make their decisions safe.
Longer or more procedural prompts did not improve this small development experiment;
the runs do not establish why. The project preserves rejected candidates rather
than selecting only successful examples.

The guard rejected eight incorrect and accepted four correct previously captured
diagnostic answers. This was a selected 12-response development replay, not a
held-out safety benchmark. It neither changes the table above nor proves a general
false-accept rate. The separate [reserved evaluation](experiments/005-reserved-baseline.md)
later passed 9/21 attempts with nine unsafe ready recommendations; its gate failed.
The guard was not applied to captured reserved responses.

## Why use a model for a deterministic policy?

For this policy alone, ordinary code is the simpler decision mechanism. The model
is a system under test, not a necessary replacement for rules. A bounded task makes
it possible to inspect its evidence use, instruction handling, and regression
behavior against clear expectations. It is a foundation for evaluation engineering,
not evidence that every release process needs an LLM.

An AI product could use these patterns to test structured recommendations before
adding broader inputs or workflows. That would require its own dataset, policy,
trusted evidence sources, and risk review; these scores do not transfer to it.

## What to inspect during review

1. Follow a missing-check case from evidence to authored label, model payload, and scoring.
2. Check why a correct decision with an invented citation still fails.
3. Run the third-trial negative control and inspect the failed promotion gate.
4. Confirm guard rejection never becomes a corrected model passing answer.
5. Check the threat model and verify that limitations match the implementation.

Read the [baseline study](experiments/001-qwen3-baseline.md),
[v2 comparison](experiments/002-prompt-comparison.md),
[v3 comparison](experiments/004-v3-comparison.md), and
[guard trust boundary](policy-guard.md) for the underlying evidence.
