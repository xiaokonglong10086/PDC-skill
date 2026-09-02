# Bounded Review

## Review Inputs

Read only what is necessary:

1. immutable frozen contract and digest;
2. implementation snapshot, digest, and durable `review_commit_sha`;
3. Controller-generated `test-execution-record.json` and its raw logs;
4. implementation report;
5. contracted fresh evidence;
6. relevant existing code only to assess an acceptance criterion or a universal stop condition.

Inspect the review commit, not a later mutable working tree. If the working tree changes after capture, invalidate the review and capture a new review commit. Do not perform an open-ended audit of unrelated code.

## Verdict Algorithm

For every acceptance criterion, record exactly one result:

- `satisfied` with concrete evidence;
- `violated` with a matching blocking finding;
- `evidence_missing` only when a mapped contracted test or evidence item is absent.

Then check universal stop conditions. A universal stop may block the current task only when the review proves that the current change:

- `introduced` the condition: it was absent at the frozen baseline and is present at the review commit;
- `expanded` a pre-existing condition: the changed path increases severity, likelihood, reachability, or blast radius; or
- `made_unacceptable` a pre-existing condition: the changed path newly activates, exposes, deploys, depends on, or makes the condition unavoidable for this task.

Severity, repository proximity, or discovery during review is not causal proof. An unchanged or unrelated pre-existing issue remains visible as non-blocking work or a separate release/project decision, but cannot change the frozen task verdict.

Return:

- `FAIL` when a criterion is violated, a frozen test executes and fails a mapped criterion, or a universal stop condition is proven;
- `EVIDENCE_MISSING` when execution is blocked, no valid execution record exists, or other contracted evidence is absent;
- `PASS` when every criterion is satisfied, every frozen test is recorded as passed by the Controller, every required evidence item is checked, and no universal stop condition exists.

## Consistency Rules

- A criterion cannot be both satisfied and blocked.
- `tests_checked` must exactly equal the test IDs recorded as passed.
- A test or evidence ID cannot be both checked and missing.
- A blocking criterion must be marked violated.
- A violated criterion must have a blocking finding.
- A global blocker must reference `GLOBAL:<stop-condition-id>`.
- Every active global blocker must include `change_scope` with one permitted relationship, a consistent baseline state, baseline and review evidence, a causal explanation, and at least one unique safe path present in the implementation snapshot `changed_files`.
- Criterion blockers keep their existing shape and do not use `change_scope`.
- PASS may contain non-blocking findings, but no blocker or missing evidence.
- Non-blocking findings require a destination: backlog, issue, or future change.

The validator enforces these relationships and requires schema v4 for active reviews. Closed schema-v2 and schema-v3 reports remain inspectable only through explicit legacy validation; they are never rewritten or reusable as active evidence. For closed schema-v3 execution evidence, `validate_test_execution_record.py --allow-closed-history` skips only equality with the current later-version checkout, worktree status, and semantic index. Historical contract, snapshot, Git object and tree, review commit, execution record, command, result, raw log, size, hash, and digest checks remain mandatory.

## Controller Test Gate

Run `run_review_checks.py` only after a valid implementation snapshot exists and the task is ready for review. The runner:

1. verifies the frozen contract, workflow binding, snapshot, review commit, and current implementation content;
2. records the main branch, HEAD, non-controller status, and semantic staged-index digest;
3. creates a detached temporary worktree at `review_commit_sha`;
4. executes every frozen required-test command once in contract order with a bounded per-test timeout;
5. classifies exit code 0 as passed, an executed unexpected exit code as failed, and timeout or unavailable execution as blocked;
6. writes one raw log per test and a digested execution record;
7. removes the temporary worktree and proves the main branch, HEAD, worktree, and semantic staged-index content were preserved.

A valid blocked record can support only EVIDENCE_MISSING. A failed record can support FAIL but never PASS. Missing, stale, altered, duplicated, or mismatched records cannot be bound to PASS or FAIL. During technical review, exact branch, HEAD, non-controller status, and semantic-index fingerprints remain mandatory. After PASS, controller-owned `.ai-product` lifecycle updates are allowed, while source-content drift, staged changes, or immutable-binding changes still invalidate the evidence.

## Blocking Finding Shape

A blocking finding includes:

- criterion ID or global stop condition;
- exact location or observable symptom;
- evidence;
- why the contract is not satisfied;
- smallest required correction.

An active global blocker additionally includes:

- `relationship`: `introduced`, `expanded`, or `made_unacceptable`;
- `baseline_state`: `absent` for introduced, `present` for expanded or made-unacceptable;
- one or more `causal_change_paths` from the exact implementation snapshot;
- non-empty baseline evidence, review-commit evidence, and causal explanation.

The validator checks completeness, consistency, safe path normalization, and snapshot binding. It does not prove the semantic truth of the reviewer's causal claim; independent review remains responsible for that judgment.

## Non-blocking Findings

Use for optional polish, alternative preferences, unrelated or unchanged pre-existing debt, out-of-scope improvements, future scalability, or uncontracted documentation work. They cannot change PASS. Critical legacy risk may still trigger a separate release or project decision without moving the current task finish line.

## Forward Progress Standard

Do not seek perfect code. Approve work that satisfies the frozen contract and does not trigger a universal stop condition. Label polish explicitly as optional.

## Re-review

After FAIL or EVIDENCE_MISSING, inspect only:

- previously failed or missing items;
- lines changed since the prior review target;
- regressions reasonably caused by those changes.

Unrelated observations remain non-blocking. A universal stop can block the re-review only when the new snapshot introduced, expanded, or made the condition unacceptable with the required causal evidence.

## Re-review evidence reuse

Bounded re-review may compose fresh behavior evidence with prior PASS behavior evidence only when the frozen contract explicitly permits composition and the impact basis was declared before the first behavior run. This shortcut never applies to the first technical review and never applies to Controller frozen automated tests after a new implementation snapshot; those required tests still rerun in full.

For each prior PASS scenario considered for reuse:

1. keep the same frozen contract intent, scenario identity, evaluator rule, required assurance class, and other material execution context;
2. use the predeclared evidence-input map to compare every global and scenario-local candidate input between the prior and final review commits;
3. require the deterministic impact helper to report those declared inputs unchanged;
4. separately confirm that no changed cross-cutting rule or other causal uncertainty makes the scenario affected;
5. preserve the original run, commit, transcript, evaluator, and assurance provenance in the final review evidence.

Previously failed or missing scenarios, new or changed scenarios, global-input changes, evaluator/contract/rubric changes, material assurance-context changes, causally affected scenarios, or any uncertain scenario require fresh execution on the final review target. A missing, ambiguous, unsafe, or post-hoc impact map fails closed to broader or full fresh execution. File count, diff size, file proximity, and reviewer intuition are not equivalence proof.

The impact map must not be narrowed after seeing a failure. If a predeclared map omits a plausible cross-cutting dependency, the Controller treats the affected scenario as uncertain and reruns it rather than using the helper result as semantic proof.
