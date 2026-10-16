# 001 — Score a narrow, auditable policy instead of asking another LLM to judge it

Status: accepted for the first milestone.

## Context

A release-review assistant can sound convincing while omitting a failed check or borrowing a passing result from an earlier revision. An average score can conceal that failure. We need a small evaluation whose failures an SDET can reproduce and explain.

## Decision

Use a three-check synthetic release policy and a strict structured response. Score schema, decision, blockers, citations, and reasons separately. Every case must pass. Record unsafe ready recommendations explicitly and compare baseline results at the criterion level, not just aggregate accuracy.

Expected labels are authored with each case. A separate oracle validates their agreement with the policy before any model call. The model sees neither expected labels nor category names. Evidence details are untrusted text; revision/check/result fields are the trusted synthetic contract.

Recorded fixtures exercise the harness offline. A separate opt-in Ollama adapter exercises a real model when a runtime is available. Reference results must never be presented as model performance. CI does not require paid services or model downloads.

## Alternatives considered

- LLM-as-judge: useful for some open-ended tasks, but unnecessary here and would introduce another nondeterministic component and cost.
- Similarity scoring: text overlap does not establish the correct blocker or current-revision citation.
- One aggregate threshold: a high average could allow a release with a missed critical failure.
- Agent framework and deployment tools: out of scope; the model has no release authority.

## Trade-offs

The rubric is intentionally task-specific. Exact citation sets penalize omission and extra evidence equally; a different application may need a different citation policy. The oracle and expected labels can share a misunderstanding, so code agreement does not replace human review of the policy. Six targeted response mutations demonstrate known fault detection, not complete code mutation coverage.

The application could make the same policy decision without an LLM. That is deliberate: deterministic software should enforce actual gates. This project tests whether an LLM assistant preserves the evidence boundary while recommending an outcome, not whether a model is necessary for the underlying rule.

## Consequences

Broader claims require additional evidence: real-model runs, repeated trials, held-out scenarios, and evaluation of free-form claims or tool behavior under their own rubrics. Do not silently extend this score to RAG, agent security, or production deployment safety.
