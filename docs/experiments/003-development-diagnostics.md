# Development diagnostics and the next candidate

A private diagnostic run compared v1 and v2 on six selected development cases,
one attempt per prompt and case (12 local requests). It saved validated contract
fields, not raw responses or reasoning. This selected sample is not a promotion
benchmark and does not estimate general performance.

V1 passed 3/6 cases with two unsafe-ready decisions. V2 passed 1/6 with three.
Both marked the missing-API case ready with checks_passed, omitted the conflict
reason on contradictory API results, and marked the log-injection case ready.
The corresponding clean UI-failure case passed under both prompts. V2 additionally
marked the security failure ready and cited an old UI failure as a current blocker.
No provider errors occurred. These observations identify wrong fields, not a proven
internal cause or evidence that a URL was fetched.

Candidate v3 makes the computation sequential: filter revisions and checks, collect
citations and failures, inspect each required check for absence and contradiction,
then derive all reasons and the decision. It explicitly distinguishes missing checks
from passing checks. This is a hypothesis, not a measured improvement. No examples,
expected case answers, scoring changes, or reserved cases were added to the prompt.

Next: compare v3 with the preserved v1 baseline on all 16 development cases, three
trials each, using identical model settings and a 48-request cap. Report criterion
regressions even if total accuracy improves. Do not promote on this diagnostic sample.
