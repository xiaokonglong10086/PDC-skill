# Software/PDC Development Profile

## Purpose

This Profile adapts the Architecture v2 kernel to the current fully implemented repository-backed Software/PDC Engineering runtime.

It is an **adapter to existing proven authorities**, not a replacement Engineering framework.

Use it when the focused Work is sufficiently understood/approved for strict repository-backed software/PDC Engineering, or when recovering/reviewing an existing Software/PDC Engineering change.

## Builder

The current default Builder is a Coding Agent such as Claude Code, Codex, Cursor, or another repository-capable implementation agent.

`Coding Agent` is a valid Builder type inside this Profile. It is not the universal PDC execution role.

The Coding Agent:

- implements only frozen work;
- runs implementation-side checks and captures requested implementation evidence;
- reports contradictions/risks;
- cannot redefine product intent;
- cannot silently expand frozen scope;
- cannot approve its own work;
- cannot replace Controller-owned exact-target verification.

Use `references/coding-agent-prompt.md` for the self-contained Software/PDC Builder task format.

## Deliverable Reality authority

For this Profile, repository/Git identity is the authoritative implementation mechanism.

Use the current repository-backed artifact and evidence system rather than inventing a second representation:

- `references/artifact-system.md`
- `references/contract-and-record-schema.md`
- `references/lifecycle-navigation.md` for current workflow recovery/navigation
- current `.ai-product/project-state.json` and per-change `workflow-state.json`
- immutable frozen contracts and digests
- implementation snapshot + durable review commit
- Controller test-execution record + raw logs
- review / acceptance / integration records

Git/worktree/SHA mechanics are Profile-specific. The **independent exact-target guarantee** is the product-level invariant.

## Current Work / Focus realization

The current Software/PDC runtime represents unfinished Engineering Work through per-change directories and workflow authority.

`project-state.json.current_change` is the current Focus pointer.

Use the existing Focus/multi-change machinery. Do not create a parallel Work queue or second focus system for this Profile.

Current implementation rules include:

- several unfinished changes may exist;
- exactly one non-parked/advancing change may execute;
- mutation/delegation/current evidence production is Focus-bound;
- parked/non-Focus work does not silently advance;
- baseline freshness is checked before resume/materialization.

The underlying current implementation lives in `scripts/multi_change.py` and related lifecycle scripts.

## Engineering lifecycle

Preserve the existing strict lifecycle:

1. recover repository/change state and capabilities — **run the authority reconciliation surface** (`scripts/verify_authority_reconciliation.py`, read-only) when: a new session/provider recovery begins; any authority/projection ambiguity exists before progression; or a session capsule conflicts with repository authority. Repository authority always wins over capsule content; capsule-only claims are treated as **unverified** and never followed as truth. When material, recover the durable Strategic Workpath from `.ai-product/workpaths/` (current route, active waypoint, revision lineage; stale routes enter explicit replan/revision per `references/strategic-workpath.md`). Never ask the Product Owner to repeat project history that repository authority already records;
2. specify observable behavior and codebase-aware architecture when needed;
3. draft and validate one bounded task contract;
4. freeze an immutable versioned contract and digest;
5. delegate only frozen work to the Coding Agent Builder;
6. capture the exact implementation snapshot and durable review commit;
7. Controller independently runs every frozen required test against that exact review commit;
8. bounded review returns PASS / FAIL / EVIDENCE_MISSING only from contracted evidence and causally applicable stop conditions;
9. technical PASS advances to Product Owner product-visible acceptance;
10. accepted work advances to integration/delivery or an explicit blocker;
11. execute frozen post-merge verification and close durably.

Detailed authorities remain:

- specification / architecture: `references/architecture-and-decisions.md`
- task contract and records: `references/contract-and-record-schema.md`
- implementation discipline: `references/implementation-discipline.md`
- Builder handoff: `references/coding-agent-prompt.md`
- bounded review: `references/bounded-review.md`
- testing and acceptance: `references/testing-and-acceptance.md`
- review-assurance routing: `references/review-assurance-routing.md`

## Frozen completion boundary

Use the existing deterministic contract system:

- `scripts/validate_task_contract.py`
- `scripts/freeze_contract.py`
- `scripts/revise_contract.py`

A frozen contract owns the current Engineering completion boundary for this Profile. It is versioned and immutable.

Do not silently reinterpret or edit it. Product-intent changes use the explicit revision path.

## Exact-target Controller verification

This is a normative guarantee and must not be weakened.

After the Builder returns:

1. capture the exact candidate through `scripts/capture_implementation_snapshot.py`;
2. bind changed-file content to the durable review commit;
3. execute `scripts/run_review_checks.py` so every frozen required test runs against a detached worktree at the exact `review_commit_sha`;
4. preserve the generated execution record and logs;
5. review only against the frozen contract, exact snapshot/review commit, Controller execution evidence, contracted fresh evidence, and causal universal-stop rules.

Builder-produced test output is useful implementation evidence but cannot substitute for this gate.

## Review law

Use `references/bounded-review.md` unchanged for the current Profile.

Do not reopen unrelated repository debt during a bounded task review.

A universal stop condition blocks only with evidence that the current change introduced, expanded, or made the condition unacceptable through a causal changed path.

Optional improvements and unrelated legacy findings remain non-blocking for the current frozen finish line.

## Product Owner acceptance

Use `references/testing-and-acceptance.md`.

The Product Owner judges the contracted visible behavior, not Git internals, test frameworks, hashes, or implementation architecture.

Technical PASS does not equal Product Owner acceptance.

## Capability limits

Before claiming repository inspection, Git state, test execution, CI, browser behavior, integration, or deployment evidence, establish the actual capability.

If the current Controller environment lacks a required capability, degrade explicitly and transfer only the minimum technical package/action needed. Never fabricate repository/test evidence.

## Existing scripts are protected assets in the Greenfield Preview

During the Architecture v2 Greenfield control-plane Preview, do not rewrite the current deterministic Software/PDC scripts merely to align names or file organization.

They are reuse assets.

A later bounded change may adapt an implementation detail only when a demonstrated Architecture v2 requirement cannot be met through this adapter/profile boundary.

---

## Recovery-before-use and owner-first reconciliation (pre-M4 portable truth gates)

- New sessions run `verify_authority_reconciliation.py` before any progression: repository authority wins over capsule content; capsule-only claims are unverified and never followed as truth; the durable Strategic Workpath is recovered from `.ai-product/workpaths/` when material (stale routes enter explicit replan/revision per `references/strategic-workpath.md`).
- The reconciliation surface is owner-first: the four owner domains (Intent — frozen contracts and their digests; Learning — learning/backlog/facts authority; Deliverable Reality — lifecycle-required snapshot/execution/review/integration bindings; Work-control — per-change workflow execution truth) are each validated for truth validity and unambiguity; project-state Focus, roadmap, handoff/capsule and the Strategic Workpath are projections/references, not owners.
- Machine output separates `result` (PASS / FINDINGS / FAIL_CLOSED), `owner_truth_valid`, `owner_truth_unambiguous`, `unique_safe_control_decision`, `progression_allowed`, owners, projections and per-finding family/status/evidence/owner-winner/decision-required/deterministic-repairability/progression-impact.
- Rules: fully aligned → PASS (exit 0); owner-clear with only non-authoritative, non-decision-required stale/unverifiable projections → FINDINGS with `progression_allowed=true` (exit 0); owner invalid/ambiguous or a decision-required input missing → FAIL_CLOSED (exit 1); input/script errors → exit 2.
- Only documented capsule fields and structured bindings are parsed — never heuristic truth from roadmap/handoff natural language. The verifier writes nothing and never auto-repairs.


---

## Recoverable operation continuity

Recovery completion and original-operation completion are two distinct events. Successfully recovering an interrupted Software/PDC Engineering operation is only a substep: after a recoverable substep succeeds, re-evaluate whether the user's original goal is already satisfied before reporting completion.

- If the original target is not yet met and no real stop condition applies, continue the original operation and verify it to genuine completion; only then report completion. A real stop condition means an actual contract/scope/safety/baseline/capability stop - not a transient recovery result.
- For implementation snapshot capture specifically:
  - pre-CAS with the review ref still equal to the expected-old value: the journaled capture was never published. After cleaning the journal, if Focus/contract/baseline remain valid and no real stop condition applies, continue with a normal capture; report "capture complete" only when a new published review ref, snapshot/workflow bindings converge, the journal is cleared, and verification passes.
  - post-CAS with the ref equal to the candidate: recovery converged and verified - the capture is complete; do not re-capture without reason.
  - a third ref, or a real contract/scope/safety/baseline/capability stop condition: stay fail closed - do not overwrite, roll back, guess, or blindly retry.
- The rule generalizes to ordinary recoverable Engineering operations: continue while the original task is unfinished; stop only on a real stop condition.
- The Product Owner is never made the recovery operator and is never asked to judge logs or technical state.

## Owner-first authority and projection coherence

Owner truth is durable before navigation projection:

- a Focus owner is a schema-v2 `focused_change_selected` record bound to either `tr:<transition_id>` or `cd:<control_decision_sha256>`;
- a newly scaffolded parked draft remains unfocused until an activated explicit Control Decision selects it;
- the only null-decision Focus recovery is the unique non-parked workflow whose verified terminal stable transition already owns execution;
- every workflow status/history writer uses the shared stable transition identity and supports projection-only replay without a duplicate owner event;
- stale project navigation is repaired only after the owner record is durable; missing or ambiguous owner truth fails closed;
- authority reconciliation exposes exactly `PASS`, `FINDINGS`, `FAIL_CLOSED`, or `ERROR` with exits `0`, `0`, `1`, and `2` respectively.

These are technical control mechanics. They do not move the frozen completion boundary, create a new Mode or router, or transfer hashes, logs, Git recovery, or correctness judgments to the Product Owner.
