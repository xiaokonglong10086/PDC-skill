# Public Verification

This repository uses a curated standalone public verification suite. It is not the private development repository's complete historical regression suite. Regression harnesses that depend on private history, private authority, or private execution state are intentionally not distributed.

Mature runtime production code remains derived from the frozen mature PDC source. Privacy, provenance, package-boundary, and fresh-clone checks are release controls; they are not runtime product features.

## Retained standalone self-tests

The following tests were each executed directly from the clean public package and observed to PASS:

- `scripts/architecture_v2_control_plane_self_test.py` — PASS
- `scripts/assurance_routing_self_test.py` — PASS
- `scripts/authority_projection_coherence_self_test.py` — PASS
- `scripts/integration_closure_recovery_self_test.py` — PASS
- `scripts/integration_runner_self_test.py` — PASS
- `scripts/multi_change_self_test.py` — PASS
- `scripts/owner_action_activation_self_test.py` — PASS
- `scripts/reconcile_project_state_self_test.py` — PASS
- `scripts/verify_authority_reconciliation_self_test.py` — PASS
- `scripts/workpath_continuity_self_test.py` — PASS
- `scripts/workpath_publish_recovery_self_test.py` — PASS

## How to run

First audit the package boundary:

```text
python scripts/audit_skill_package.py
```

Then run each retained self-test directly:

```text
python scripts/architecture_v2_control_plane_self_test.py
python scripts/assurance_routing_self_test.py
python scripts/authority_projection_coherence_self_test.py
python scripts/integration_closure_recovery_self_test.py
python scripts/integration_runner_self_test.py
python scripts/multi_change_self_test.py
python scripts/owner_action_activation_self_test.py
python scripts/reconcile_project_state_self_test.py
python scripts/verify_authority_reconciliation_self_test.py
python scripts/workpath_continuity_self_test.py
python scripts/workpath_publish_recovery_self_test.py
```

