# Model Behavior Evaluation Baseline

PDC uses this evaluation layer to detect model-behavior regressions against an approved baseline. It is provider-neutral and does not require model APIs, hidden sub-agents, or automatic orchestration.

## Authority and scope

- Frozen Product Operating Model v1: `.ai-product/operating-model/product-operating-model.v1.md`
- Frozen SHA-256: `60657356693d610ede67a12aa8bc564c5791338ca23fa1474d22a02dc5aba82a`
- Versioned catalog: `assets/evals/model-behavior-scenarios.v1.json`
- Stable suites: `operating-model-v1` (G-01..G-19) and `stable-v4.2` (S-01..S-24)

The catalog is the scoring baseline. A run may record a proposed improvement in `suggested_delta`, but may not redefine expected behavior. Changing approved behavior requires a separately approved versioned Baseline + Delta.

## Execution topology

There are three distinct responsibilities:

1. **Packet generator** prepares content-addressed subject material and scenario inputs for an exact Git commit. It does not execute or judge a model.
2. **Semantic evaluator** is the Controller, a fresh external session/agent, or a human. It judges natural-language behavior and cites transcript evidence.
3. **Deterministic validator** checks catalog/run/packet structure, hashes, bindings, coverage, contradictions, and assurance declarations. It does not claim to understand prose semantics or cryptographically prove session independence.

Do not collapse these responsibilities into a false claim of independent review.

## Generate a packet

```bash
python scripts/create_model_behavior_eval_packet.py \
  --root <repository-root> \
  --ref <exact-commit-or-ref> \
  --output <empty-output-directory> \
  --profile full-v1
```

Supported full profiles are `full-v1`, `operating-model-v1`, and `stable-v4.2`.

For a targeted run, repeat `--scenario` instead of using `--profile`:

```bash
python scripts/create_model_behavior_eval_packet.py \
  --root <repository-root> \
  --ref <exact-commit> \
  --output <empty-output-directory> \
  --scenario G-03 --scenario S-09
```

The packet contains:

- `manifest.json`: exact repository/commit/Skill/Operating Model/catalog bindings;
- `subject/`: exact Skill and Product Operating Model content from the selected commit;
- `execution/scenario-inputs.json`: inputs only, without expected behavior or evaluator checklist;
- `evaluator/evaluation-rubric.json`: expected behavior, failure condition, and checklist;
- `run-template.json`: evidence record template;
- `SHA256SUMS.txt`: checksums for packet files.

For blind execution, give the tested session the subject material and `execution/` inputs first. Do not expose the evaluator rubric until responses have been captured.

## Assurance classes

### `controller_self_check`

Use when the same PDC Controller evaluates its own behavior. It is valid regression evidence but is **not independent review**. The run must declare `independent_review: false` and must not carry an external attestation.

### `external_fresh_session_attested`

Use when a fresh external session/agent or human context executes/evaluates the packet. The record must declare a fresh execution context and include an explicit attestation. Validation checks that declaration and its evidence binding; it does not claim cryptographic proof that the session was genuinely independent.

When the current runtime has no delegation tool, generate the packet and hand it to another fresh session manually. Do not claim hidden automatic sub-agent capability.

## Run status rules

Per scenario, record exactly one of `PASS`, `FAIL`, or `EVIDENCE_MISSING`.

- A declared full profile is `PASS` only when every required scenario is present and PASS.
- Any required FAIL yields overall `FAIL`.
- Missing scenarios, missing evidence, or a required `EVIDENCE_MISSING` yields overall `EVIDENCE_MISSING`.
- A targeted packet with all selected scenarios passing is `PARTIAL`, never full `PASS`.
- Transcript bytes are bound by SHA-256; edited transcripts invalidate the record.
- Duplicate scenario IDs, wrong subject/catalog bindings, contradictory status, false independence, or unsupported fields are invalid.
- A shared transcript across multiple scenarios requires an explicit reuse reason.

Validate with:

```bash
python scripts/validate_model_behavior_eval.py catalog assets/evals/model-behavior-scenarios.v1.json --root <repository-root>
python scripts/validate_model_behavior_eval.py packet <packet-directory>
python scripts/validate_model_behavior_eval.py run <run.json> --packet <packet-directory>
```

## Relationship to Engineering governance

This harness is an additional PDC self-development evaluation layer. It does not replace frozen Engineering contracts, Controller-run required tests, bounded review, product-owner acceptance, integration verification, universal-stop causality rules, or closure assurance.

A model-behavior run cannot create hidden Engineering completion criteria. Any later automation must preserve the same evidence semantics rather than silently redefining assurance.

## Evidence-unit equivalence

When a frozen contract explicitly permits bounded re-review composition, it may predeclare candidate inputs for each behavior scenario before the first execution. Candidate inputs consist of global inputs plus scenario-local inputs and use only repository-relative whole-file selectors or exact named Markdown-section selectors.

`behavior_evidence_impact.py` compares those declared inputs between two Git commits and reports only `changed` or `unchanged` byte impact. For Markdown sections, the selected bytes include the exact heading and its body through the next heading of equal or higher level. Missing files, missing or duplicate headings, unsafe paths, malformed maps, unsupported selectors, or invalid Git refs fail closed.

An unchanged helper result is necessary but not sufficient for evidence reuse. The helper does not prove semantic causality, evaluator equivalence, execution-context equivalence, freshness, assurance equivalence, or a behavior verdict. Global input changes invalidate every scenario that includes them. Failed, new, changed, causally affected, materially context-changed, or uncertain scenarios must run fresh.

## Evidence provenance

Reused behavior evidence retains its original review commit, run ID, transcript binding, evaluator identity, and assurance class. It must be described as reused prior PASS evidence after equivalence proof, never as freshly executed on the final review commit. Reuse cannot upgrade `controller_self_check` to `external_fresh_session_attested` or otherwise strengthen the original assurance claim.

Fresh final-target evidence and reused prior evidence must remain distinguishable in the Controller's review reasoning. Closed historical evidence is immutable; later reuse references it rather than rewriting it.

## Bounded re-review evidence reuse

Initial review still executes the full behavior set required by its frozen contract. After a bounded repair, final technical review may compose reuse-eligible prior PASS scenarios with freshly executed final-target scenarios only when the frozen contract explicitly permits that composition and a pre-frozen evidence-input map proves candidate-input equivalence.

A targeted final-target model-behavior run remains `PARTIAL`; it does not become a full-suite `PASS` merely because all targeted scenarios passed. Any final technical PASS is a Controller judgment over the complete permitted evidence composition, including preserved prior provenance and fresh execution for every failed, missing, new, changed, causally affected, materially context-changed, or uncertain scenario.

A new implementation snapshot still invalidates the prior Controller automated test-execution record and reruns every frozen required test. This behavior-evidence reuse rule applies only to model/fresh-context behavior evidence and is not a deterministic test cache.
