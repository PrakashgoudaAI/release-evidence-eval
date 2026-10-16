# Reject unsupported recommendations; do not repair them

The model produces a recommendation. `guard_recommendation(packet, response)`
independently checks it against the fixed release policy. It accepts only a packet
with revision and evidence fields; expected labels, case categories, and benchmark
IDs are not guard inputs. The guard does not import or call the benchmark oracle.
It shares strict contract validation with the evaluator, so shared validator defects
remain a possible common failure mode.

```python
from release_eval.guard import guard_recommendation

result = guard_recommendation(evidence_packet, model_response_text)
if not result["accepted"]:
    # Stop this recommendation path and route to review; never silently replace it.
    pass
```

The caller must enforce rejection. This library has no deployment integration and
does not stop an external system on its own. Every result includes
`authorizes_release: false`, including accepted ready recommendations.

Invalid packets and invalid responses are rejected. For valid input, the guard
groups current-revision records by required check, derives failures, absence, and
contradictions, and compares all four response fields. Missing citations, invented
IDs, wrong reasons, and incorrect decisions each cause rejection. It never rewrites
the response, retries the model, follows log instructions, or fetches URLs. Returned
diagnostics contain field-level violation codes, not supplied log or response text.

## Verification

Run `python3 -m tools.verify_guard` for authored development answers and 32 deliberate
wrong-decision mutations. Unit tests additionally enumerate all 27 combinations of
missing, passing, and failing required checks, rejecting both wrong decisions in
each combination. They cover contradictory results, combined failure/missing
reasons, stale and unrelated records, log instructions, wrong arrays, malformed
input, duplicate IDs, and non-authorization. These are targeted checks, not exhaustive
testing of every possible input.

An offline replay of the existing private six-case diagnostics (two prompts,
12 previously captured model responses) accepted four correct answers and rejected
eight incorrect answers. No new model requests were made. This sample was selected
for diagnosis and is not a held-out safety benchmark. It does not demonstrate a
general false-accept rate. Reserved cases remain unused.

Model quality remains unchanged: v1 passed 24/48 full development attempts; v2 and
v3 were rejected after regressions. Guard rejection is not a corrected model answer
and must never be included in model passing-attempt counts.

## Trust boundary

The guard cannot authenticate CI producers, establish that tests are meaningful,
detect forged passing evidence, or assess risks outside this explicit policy. A
forged but policy-consistent packet can pass. Production use would also need trusted
evidence collection, authenticated provenance, independently reviewed policy,
enforced review routing, and deployment-specific controls. Here the guard is a
tested reference component, not a production security certification.
