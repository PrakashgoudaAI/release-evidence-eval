# Contributing

Keep changes tied to an observable failure mode. Add a case and a failing test before broadening the evaluator.

Run the unittest suite, reference evaluation, targeted-fault campaign, and baseline comparison shown in the README. A case is not useful simply because it increases the total: explain the risk it adds, the expected decision, and why existing cases miss it.

Use synthetic evidence. Keep case/evidence identifiers non-sensitive. Golden labels need review against the written policy and must pass the independent oracle. Do not weaken a gate to accommodate a model's answer. Changes to the scoring rules require a rubric-version change and a new baseline; preserve old reports outside the repository for comparison history.

Reference fixtures are test inputs, not a claimed model benchmark. New model results must identify the model/runtime, date, configuration, input fingerprints, repeated-trial count, and failures. Keep raw responses out of routine CI artifacts. If you capture them for investigation, store them under an approved data-retention policy, not in the public repository.

Commit messages should describe the change, for example `test: reject stale scan citations`. Do not commit generated reports, caches, local model files, access tokens, or employer material. Include checks that could not run in the review notes.

For repeated-trial changes, also run `python3 -m tools.verify_experiment`. Do not fill absent trials by copying an earlier response. Record whether transcripts are generated or authored; completeness alone does not prove genuine inference. Keep development and reserved use distinct, and replace the reserved set once its results drive tuning. Run the same trial count and controlled runtime settings for candidate/baseline experiments; report model or prompt changes explicitly.
