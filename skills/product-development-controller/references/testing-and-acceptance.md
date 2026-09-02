# Testing and Product Acceptance

## Test Design

Map risk to the cheapest reliable layer:

- pure rules and transforms: unit tests;
- module boundaries and adapters: integration tests;
- critical user journeys: E2E;
- layout and interaction: browser or visual checks;
- security, performance, migration, and recovery: dedicated non-functional tests when relevant.

Do not require every layer for every task. Freeze required layers before implementation.

## Acceptance Criterion Mapping

Every criterion must reference at least one contracted test or evidence ID. Every contracted test and evidence item must be referenced by at least one criterion. Unknown IDs, unreferenced tests, and unreferenced evidence are invalid.

## Controller-Run Frozen Tests

The coding agent's test report is implementation evidence, not the gate. After the Controller captures the immutable review commit, the Controller runs `run_review_checks.py`. The command executes every frozen required test exactly once in a detached temporary worktree and generates the execution record and logs automatically.

Review semantics:

- all tests passed: a schema-v3 PASS review may proceed if all other criteria and evidence are satisfied;
- any executed test failed and no execution was blocked: the report must be FAIL when the failed test maps to a violated criterion or required-build global blocker;
- any test or runner step blocked: the report must be EVIDENCE_MISSING;
- missing, stale, altered, duplicated, or mismatched evidence: PASS and FAIL are rejected.

Capturing a new implementation snapshot or revising the contract clears the workflow execution-record digest. Re-run the frozen tests before review can advance. The execution record uses preserved Git porcelain columns and a semantic staged-index digest, not raw `.git/index` bytes. Once PASS advances to product acceptance, normal controller-owned lifecycle record writes do not invalidate unchanged review evidence; source or staged-content changes still do.

## Verification promise is not evidence

A plan, promise, or intention to verify later is not verification evidence and cannot support PASS while a required exact value is mismatched or a required evidence item remains unresolved. If the required value is wrong or required evidence is missing, keep the mapped criterion non-PASS and state the missing or failed evidence plainly, regardless of how honest or clear the prose is. "Will verify later" resolves the claim only after the verification actually happens and its result is recorded.

## Technical PASS terminates technical review

Once every frozen technical criterion and required evidence is satisfied, technical review stops: the single next stage/action is the contracted product-visible acceptance. Do not open another technical audit or evaluation workstream after technical PASS unless new material evidence creates a valid blocker or a separate change is explicitly opened.

## Manual Scenario Format

Use observable Given/When/Then semantics but record each scenario as:

- ID;
- mapped criterion IDs;
- setup;
- user action;
- expected visible result.

Avoid asking the product owner to inspect Git internals, architecture, database rows, or testing framework output unless those are themselves product-visible results.

## Acceptance Record Rules

Record every contracted manual scenario exactly once.

- `accepted`: all scenarios passed;
- `rejected`: at least one scenario failed;
- `blocked`: at least one scenario blocked and none failed.

The record must include tester, environment, timezone-aware timestamp, contract version/digest, reviewed implementation snapshot digest, and per-scenario notes.

A new product request discovered during acceptance becomes a new change. It does not expand the current contract.
