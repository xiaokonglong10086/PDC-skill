# Artifact System

## Principle

Keep product intent, implementation identity, review, acceptance, and integration state in repository files rather than chat memory. Use immutable snapshots for completion boundaries and mutable state files only for workflow position.

## Project Files

- `project-state.json`: navigation projection for the single Focused Change, or project-level `unfocused` coordination when only parked unfinished work remains.
- `project-facts.md`: approved product purpose, users, scope, and constraints.
- `codebase-facts.md`: observed stack, commands, entry points, architecture, and repository risks.
- `roadmap.md`: ordered product outcomes.
- `backlog.md`: non-blocking findings, future requests, and technical debt.
- `decisions/`: lean ADRs for consequential decisions.
- `architecture/`: only diagrams or flows needed to understand the system.
- `.ai-product/handoffs/latest.md`: optional **Session Continuity Capsule** for compact cross-session navigation. It is an index to repository authority, not authoritative project truth.
- `.ai-product/workpaths/`: **Work-control / Mutable Controller Record namespace** for the durable Strategic Workpath (M3). Holds the current Workpath projection (`current.json` pointer + versioned `revisions/` history with prior-version linkage, revision reason, and source authority references) and stale-path diagnosis. It is Controller Work-control state — never Work implementation/deliverable identity, never a replacement for Intent / Learning / Deliverable Reality authority. It is excluded from implementation changed-file identity under `reviewable-control-infrastructure-v1` (see identity policy rule 9 below).

## Change Directory

Use one independently reviewable change per directory. Several unfinished change directories may coexist. The Active Change Set is derived at runtime from valid non-closed `workflow-state.json` files; no duplicate active list, queue, or waiting authority is persisted. Exactly one change may be Focused for execution at a time, while non-focused unfinished work is limited to `draft` or independently verified-parkable `blocked` state.

### Product and engineering artifacts

- `product-spec.md`: observable product behavior, user scenarios, rules, states, errors, edge cases, data destinations, success, assumptions, dependencies, and exclusions.
- `engineering-plan.md`: codebase facts, chosen approach, file responsibilities, interfaces, data flow, recovery, risks, commands, and architecture decisions.
- `test-plan.md`: mapping from every acceptance criterion to the cheapest reliable test layer and product-owner acceptance.
- `coding-agent-prompt.md`: self-contained implementation instruction that does not depend on chat history.
- `implementation-report.md`: actual changes, RED/GREEN evidence, full checks, runtime evidence, Git state, and risks.

### Contract artifacts

- `task-contract.draft.json`: editable draft only.
- `contracts/task-contract.vN.json`: immutable frozen completion boundary.
- `contracts/task-contract.vN.sha256`: canonical SHA-256 digest of the frozen contract.
- `workflow-state.json`: authoritative task state, current contract version and digest, snapshot digest, test-execution-record digest, and transition history.

Do not store workflow status in a frozen contract. Do not edit a frozen contract. A product decision that changes the completion boundary creates a new version and preserves the previous snapshot.

### Evidence artifacts

- `implementation-snapshot.json`: changed file set, content manifest, and durable Git review commit under `refs/pdc/reviews/` for the exact review target. New captures are snapshot **schema v3** with an explicit durable `identity_policy` (`reviewable-control-infrastructure-v1`) that decides which paths participate in the changed-file identity: reserved Mutable Controller Records (`.ai-product/project-state.json`, `.ai-product/changes/**`, `.ai-product/transactions/**`, `.ai-product/backups/**`, `.ai-product/handoffs/**`, `.ai-product/workpaths/**`) are always excluded, and a frozen-allowed `.ai-product` deliverable is a reviewable deliverable. Historical snapshot **schema v2** keeps legacy semantics unchanged: every `.ai-product/**` path is excluded from implementation changed-file identity, and closed v2 snapshots/integration records are never rewritten or reinterpreted under the new policy.
- `test-execution-record.json`: Controller-generated execution metadata bound to the frozen contract, implementation snapshot, exact review commit, commands, results, logs, preserved non-controller status, semantic staged-index content, and record digest.
- `evidence/review-tests/<run-id>/*.log`: raw combined output for each frozen required test, with size and SHA-256 recorded in the execution record.
- `review-report.json`: PASS, FAIL, or EVIDENCE_MISSING bound to contract, snapshot, and active test-execution-record digests.
- `acceptance-record.json`: product-owner decision for every contracted manual scenario, bound to the reviewed snapshot.
- `evidence/post-merge/*.log`: controller-executed frozen command output with recorded SHA-256 digests.
- `integration-record.json`: repository identity, base branch, merge commit, CI assurance, executed post-merge verification, release/rollback record, and upstream artifact digests.

## Authority Rules

1. The frozen contract defines completion.
2. `workflow-state.json` defines task status.
3. `project-state.json.current_change` is the single Focused Change pointer, not proof that only one unfinished change exists. Project projection may be repaired only when Focus truth is deterministic; conflicting or multiple non-parked execution states fail closed.
4. A change-specific lifecycle, source, current-evidence, implementation-delegation, or shared-repository mutation is legal only for the Focused Change. Read-only inspection remains legal for non-focused and closed changes.
5. Review PASS is valid only when `workflow-state.json`, `test-execution-record.json`, and `review-report.json` bind the same contract, snapshot, review commit, and execution-record digest. Controller-owned lifecycle record updates after PASS do not alter that identity; reviewed source or staged-content changes do.
6. Acceptance and integration records are valid only when their digests match upstream artifacts.
7. File existence or a coding-agent claim alone never proves completion.
8. The optional `.ai-product/handoffs/latest.md` Session Continuity Capsule is not authoritative. A fresh session must reconcile it against the repository-backed authorities and prefer the repository whenever they disagree; capsule-only state is unverified.
9. Implementation changed-file identity is governed by the snapshot's durable identity policy. A path's role (Mutable Controller Record vs. reviewable deliverable) is decided by that policy, never by directory name alone or by inference from timestamps, Controller version, commit SHAs, task/branch names, or file content. Unknown snapshot schema or identity policy fails closed. A contract whose allowed_files may grant deliverable identity to a reserved Mutable Controller Record is rejected before freeze.

## Contract Revision

When implementation exposes a real product contradiction:

1. stop implementation;
2. state the contradiction and affected criteria;
3. obtain the product-owner decision;
4. run `revise_contract.py` with actor and reason;
5. edit the new draft version;
6. validate and freeze it;
7. clear the prior implementation-snapshot and test-execution bindings;
8. resume from the new boundary and generate fresh evidence.

Do not silently reinterpret a frozen contract.

## Technical Baseline Refresh

Normal blocked-task resume compares the current frozen baseline branch tip with `baseline_branch_tip_sha`; any difference is stale. Stale work is not materialized. A technical-only refresh creates the next immutable contract version from the current frozen contract, changes only the technical baseline/version metadata, preserves Product Owner-confirmed product fields, clears active snapshot/review-test bindings, and returns to `ready_for_implementation` or `blocked_from=ready_for_implementation` while retaining the real blocker. Historical artifacts remain historical and cannot satisfy the refreshed lifecycle.

---

## Portable Truth Gates (pre-M4) — canonical identity, capture journal, Workpath records

### Canonical implementation manifest

New schema-v3 captures include `canonical_format_version: 1` and `canonical_identity_digest`:

- The canonical manifest is built from a temporary Git index: baseline `read-tree`, changed paths staged via `git add` under the explicit machine-independent canonical policy (`core.autocrlf=input`, `core.safecrlf=false` — text CRLF is clean-converted to LF deterministically while Git binary detection keeps binary bytes untouched), then `write-tree` for the canonical `review_tree_sha`. The review commit tree is built by the exact same canonical policy; canonical identity never inherits the machine's `core.autocrlf`.
- Present manifest entries carry `path`, `state`, `mode`, `blob_sha`, `canonical_size`, `sha256`, `size`. `sha256`/`size` are the compatibility fields and always equal the Git blob canonical bytes; `size == canonical_size`.
- Deleted entries use explicit null/0 for mode/blob/canonical fields.
- `canonical_identity_digest = sha256(baseline_sha + review_tree_sha + sorted(path, mode, blob_sha, canonical_size))`; identical semantic content yields an identical tree and digest regardless of raw CRLF/LF working-tree bytes.
- `review_commit_sha` remains the executable carrier; repeated captures of identical content may produce different commits but stable tree/manifest/digest.
- 40- and 64-character Git object ids are both supported.
- Historical schema-v2 snapshots keep legacy semantics unchanged; older schema-v3 snapshots without the canonical marker validate read-only in the historical format.

### Capture journal and CAS recovery (`.ai-product/transactions/`)

Capture publishes through an idempotent journal under the existing `.ai-product/transactions/` namespace:

- journal fields: schema/version, operation, change, task, review ref, `expected_old_ref_state` (`present`/`absent`), the always-present `expected_old_review_commit_sha` (exact object id, or JSON `null` for absent — never an all-zero OID as a second truth), repository object format, candidate commit/tree/manifest identity, exact snapshot/workflow payloads with digests, and diagnostic phases/timestamps.
- Publication uses compare-and-swap: `git update-ref <ref> <candidate> <expected-old>` with the zero OID derived from `git rev-parse --show-object-format=storage` (40 zeros for SHA-1, 64 for SHA-256) for first publication.
- Recovery (`--recover-only`) reads only the actual ref: untouched ref → journal dropped, old bindings untouched; ref == candidate → the two payloads are converged idempotently and verified, then the journal is removed; any third value → FAIL CLOSED (no overwrite, no rollback, no guessing).
- Active readers reject a non-converged snapshot; recovery must complete before proceeding.

### Workpath records

`.ai-product/workpaths/` holds the durable Strategic Workpath as Work-control / Mutable Controller Record state: current projection + versioned revision history (append-only successors; predecessors are never mutated, `superseded_by` is read-only legacy and never backfilled) with structured `source_authority_references` (traversal-safe path, file SHA-256, `owner_domain` ∈ {Intent, Learning, Deliverable Reality, Work-control}, optional authority_version, optional 40/64-char authority_commit_sha). Diagnostic evidence status (e.g. `unverified`) is not a lifecycle state and not a new authority.
