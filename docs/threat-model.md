# Threat model

## Assets and trust boundaries

The assets are evaluation integrity, synthetic input contents, local files, and honest reporting of model behavior. The trusted boundary contains the written policy, input validator, scorer, and reviewed golden labels. Model output and evidence details are untrusted. The optional model runtime is a separate process, even when reached through loopback.

| Failure or threat | Implemented control | Remaining limitation |
| --- | --- | --- |
| Log text overrides policy | System policy, role separation, four development attack cases and one reserved attack case | A few cases cannot establish general instruction resistance |
| Old or invented evidence | Exact current-revision citation sets | Only this structured policy is evaluated |
| Missing or conflicting checks | Explicit missing/conflict reasons; no inferred pass | Evidence authenticity/signatures are not verified |
| Malformed output | Strict fields, enums, unique arrays, JSON parsing without repair | No evaluation of free-form factual claims |
| Label leakage | Provider packet excludes expected values and case categories | The public case set is not a held-out benchmark |
| Provider outage looks like quality success | Separate provider-error count and exit code 2 | Per-case timeouts can make a live run slow |
| Transport forwards prompts unexpectedly | Literal loopback address, proxies disabled, redirects rejected | Local model runtime could itself relay to the cloud |
| Report reveals inputs or credentials | No raw content or exception bodies in routine report | IDs, model names, hashes, and filenames still require review |
| Changed dataset makes comparison misleading | Dataset/rubric/schema/runner compatibility checks | Reports are not signed or tamper-proof |
| One lucky answer hides an intermittent failure | Every-trial gates, semantic instability, complete trial transcripts | Small trial counts do not establish statistical reliability |
| Reserved examples accidentally reused during tuning | Disjoint IDs and order-normalized evidence-packet checks | Related templates can still leak; public cases are not blind |
| Evaluation overwrites an input | Resolved-path checks and atomic report replacement | Arbitrary report destinations remain the caller's responsibility |

## Deliberately excluded

No web browsing, tool execution, deployment authority, production access, RAG ingestion, credential storage, or external judge is implemented. The forged-link case checks the resulting recommendation; it does not test a browsing agent's exfiltration defenses because this model has no tools.

Only synthetic inputs are approved for this milestone. Production adoption needs a separate threat review, access controls, evidence provenance, model inventory, runtime logging policy, and incident process.
