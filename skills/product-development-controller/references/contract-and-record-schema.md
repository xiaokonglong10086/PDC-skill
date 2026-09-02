# Contract and Record Schema Guide

All control records use strict JSON. The `.json` extension is intentional; do not paste YAML syntax into these files.

## Acceptance Criterion

```json
{
  "id": "AC-1",
  "statement": "A valid DOCX file is selected and shown to the user.",
  "test_ids": ["TEST-1"],
  "evidence_ids": ["EV-1"]
}
```

Every criterion maps to at least one test or evidence item. Every required test and evidence item must be referenced by at least one criterion.

## Required Test

```json
{
  "id": "TEST-1",
  "type": "unit",
  "command": "npx vitest run tests/unit/editor/Upload.test.js",
  "expected": "all focused upload tests pass"
}
```

Supported types: unit, integration, e2e, build, lint, security, performance, other.

## Required Evidence

```json
{
  "id": "EV-1",
  "type": "command_output",
  "description": "Focused test output including exit code 0"
}
```

## Manual Acceptance Scenario

```json
{
  "id": "UA-1",
  "criterion_ids": ["AC-1"],
  "setup": "Open the upload page with material trial enabled.",
  "action": "Select one DOCX file.",
  "expected": "The filename is shown and submit is enabled."
}
```

## Test Execution Record

`run_review_checks.py` generates this record; do not hand-author it. The complete schema also contains timing, worktree-preservation evidence, runner blockers, and a digest.

```json
{
  "schema_version": 1,
  "task_id": "T1.2",
  "contract_version": 2,
  "contract_digest": "<sha256>",
  "implementation_snapshot_digest": "<sha256>",
  "review_commit_sha": "<git-sha>",
  "baseline_sha": "<git-sha>",
  "executor": "controller",
  "timeout_seconds": 1800,
  "tests": [
    {
      "id": "TEST-1",
      "type": "unit",
      "command": "npx vitest run tests/unit/editor/Upload.test.js",
      "expected": "all focused upload tests pass",
      "expected_exit_code": 0,
      "actual_exit_code": 0,
      "result": "passed",
      "blocked_reason": null,
      "log_path": "evidence/review-tests/<run-id>/TEST-1.log",
      "log_size": 418,
      "log_sha256": "<sha256>"
    }
  ],
  "runner_blockers": [],
  "overall_status": "passed",
  "record_digest": "<sha256>"
}
```

Per-test results are `passed`, `failed`, or `blocked`. Overall status is blocked if any test or runner step is blocked, failed if no step is blocked and at least one test failed, otherwise passed. Commands, types, expected text, order, and IDs must exactly match the frozen contract.

## Review Execution Binding

Active `review-report.json` uses schema version 4 and includes:

```json
{
  "schema_version": 4,
  "test_execution_record_digest": "<sha256>",
  "verdict": "PASS",
  "tests_checked": ["TEST-1"]
}
```

For PASS or FAIL, the digest must identify a valid current execution record. `tests_checked` contains only tests recorded as passed. A blocked or unavailable run uses EVIDENCE_MISSING; when no valid record exists, every frozen required test must be listed as missing and the digest remains empty.

## Review Schema Compatibility

- New and active reviews require schema v4.
- Active schema-v2 or schema-v3 reports are invalid and cannot be reused as current evidence.
- Closed schema-v2 and schema-v3 reports remain immutable and may be inspected only with `--allow-closed-legacy`.
- Explicit legacy inspection does not migrate or rewrite the historical record and does not bind it to a new active task.
- Closed schema-v3 execution evidence may use `--allow-closed-history` to ignore only the current later-version checkout and semantic-index equality. The historical contract, snapshot, review commit, Git objects and tree, execution record content and digest, frozen commands, results, logs, sizes, and hashes are still validated.

## Review Criterion Result

```json
{
  "id": "AC-1",
  "result": "satisfied",
  "evidence": "TEST-1 and EV-1 confirm the result"
}
```

Supported results: satisfied, violated, evidence_missing.

## Blocking Finding

```json
{
  "reference": "AC-1",
  "location": "src/editor/ui/createUploadScreen.js",
  "evidence": "Invalid files replace the valid selection.",
  "reason": "The frozen state-preservation criterion is violated.",
  "required_correction": "Preserve the prior valid file when validation fails."
}
```

A universal blocker uses `GLOBAL:<stop-condition-id>` as the reference and, for an active schema-v4 review, adds a current-change scope claim:

```json
{
  "reference": "GLOBAL:security_vulnerability",
  "location": "src/security/legacyGate.js",
  "evidence": "The review commit exposes an unsafe path.",
  "reason": "The current change introduces a universal stop condition.",
  "required_correction": "Remove the exposure and capture a new snapshot.",
  "change_scope": {
    "relationship": "introduced",
    "baseline_state": "absent",
    "causal_change_paths": ["src/routes/newFlow.js"],
    "baseline_evidence": "The baseline route does not reach the unsafe path.",
    "review_evidence": "The review commit routes user data through it.",
    "causal_explanation": "The changed route creates the new reachability."
  }
}
```

Rules:

- `introduced` requires `baseline_state: absent`.
- `expanded` and `made_unacceptable` require `baseline_state: present`.
- Every causal path must be unique, repository-relative, traversal-safe, and present in the implementation snapshot `changed_files`. Deleted changed paths are valid when listed by the snapshot.
- Baseline evidence, review evidence, and causal explanation must be non-empty.
- Criterion blockers do not require and must not add `change_scope`.
- Severity, discovery during review, or repository proximity is not a permitted relationship.

The validator enforces a reviewable causal claim structure; it cannot determine whether the prose or evidence is substantively true.

## Missing Evidence

```json
{
  "kind": "evidence",
  "id": "EV-1",
  "reason": "The focused test output was not supplied."
}
```

The same ID cannot appear in both checked and missing lists.

## Acceptance Scenario Result

```json
{
  "id": "UA-1",
  "result": "passed",
  "notes": "Observed in Chromium at 1366x768."
}
```

Supported results: passed, failed, blocked.

## Integration Assurance

- `local_verified`: actual local commit and post-merge commands verified.
- `remote_verified`: remote PR and CI independently checked with a connector.
- `externally_attested`: remote facts supplied by an identified external person or system.

## Post-Merge Check

Freeze every command required for local closure inside the contract:

```json
{
  "id": "PM-1",
  "command": "npm run ci:local",
  "expected_exit_code": 0
}
```

`record_integration.py` executes these commands. The integration record stores the actual exit code, execution time, executor, output-log path, and output SHA-256. A person cannot substitute `result: passed` for controller execution.

## Review Commit Binding

`implementation-snapshot.json`, `test-execution-record.json`, `review-report.json`, and `acceptance-record.json` all contain `review_commit_sha`. The review commit is created without moving the working branch and is kept under `refs/pdc/reviews/<change>/latest`. If working-tree content changes after capture, the pending review is invalid until a new snapshot is created.

## Allowed-File Rules

- `src/file.js` matches only that file.
- `src/` explicitly matches all descendants.
- `src/*.js` matches one directory level only.
- `src/**/*.js` explicitly matches nested levels.
- `.env` never matches `env`.

---

## Integration record schema v3 (portable truth gates)

New integration records use `schema_version: 3`:

- the formal integration commit must reconstruct, relative to the frozen baseline and under the snapshot identity policy, the exact canonical reviewed identity (changed-file set; canonical path/mode/blob-identity/canonical-size; canonical manifest; review_tree_sha; canonical_identity_digest) of the review snapshot; sibling topology is legal.
- `local_reviewed_content_reconstructed` + `local_identity_evidence` record the independently verifiable reconstruction of the reviewed canonical identity from the integration commit relative to the baseline; `review_commit_sha` resolvability is an independent provenance fact, not an integration-validity precondition.
- `remote_durability_verified` + `remote_durability_evidence` separate local closure from remote publication:
  - evidence status ∈ {`unverified`, `synthetic_mechanism`, `real_publication`};
  - without real remote verification the default is `unverified`, boolean false, closure stays `local_verified`;
  - `real_publication` requires a normal `refs/heads/**` remote ref, standard clone/fetch (no custom refspec), a fresh clone with no original-worktree/hidden-ref dependency, observed-tip verification, and verified baseline/integration-commit recovery with independently reconstructed canonical reviewed identity — never from a local path/bare remote (synthetic);
  - a claim must never be stronger than its evidence.
- `validate_integration_record` dispatches v2 (legacy semantics unchanged) vs v3; `--allow-closed-history` uses normalized logical repository identity (repository_root is historical metadata), does not require the original feature ref/current HEAD/worktree, and still strictly validates immutable objects, ancestry, manifest and artifact digests; logical identity mismatch fails.
- Legacy v2 review-object loss: independently re-verify contract/snapshot/review/acceptance/integration digests and remaining Git/log evidence; return `VALID_WITH_HISTORICAL_LIMITATIONS` (listing missing guarantees) only when full-tree/changed-path scope is independently re-provable from an extant tree or merge diff; otherwise `INVALID`. Never fabricate substitute objects or rewrite records.
- The `validate_integration(...)` seven-argument call signature is preserved so protected consumers need no change.
