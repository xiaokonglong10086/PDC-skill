#!/usr/bin/env python3
"""Freeze a validated draft contract into a versioned, recoverable snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import (
    CONTROLLER_VERSION,
    actual_repository_identity,
    atomic_write_json,
    atomic_write_text,
    controller_lock,
    git_is_ancestor,
    git_top_level,
    load_json_object,
    normalize_repository_identity,
    now_iso,
    safe_child,
    sha256_json,
    validate_change_name,
    verify_git_branch,
    verify_git_commit,
)
from multi_change import apply_workflow_transition, assert_focused_change
from validate_task_contract import validate_contract


def update_states(
    *,
    workflow_path: Path,
    state_path: Path,
    workflow: dict,
    project_state: dict,
    change_name: str,
    version: int,
    contract_digest: str,
    actor: str,
) -> None:
    if workflow.get("status") == "draft":
        apply_workflow_transition(
            workflow,
            to_status="ready_for_implementation",
            contract_digest=contract_digest,
            actor=actor,
            reason=f"Freeze contract v{version}",
            record_fields={
                "contract_version": version,
                "tool_version": CONTROLLER_VERSION,
            },
        )
        workflow["contract_version"] = version
        workflow["contract_digest"] = contract_digest
        atomic_write_json(workflow_path, workflow)
    elif not (
        workflow.get("status") == "ready_for_implementation"
        and workflow.get("contract_version") == version
        and workflow.get("contract_digest") == contract_digest
    ):
        raise ValueError("existing workflow state is incompatible with the frozen contract")

    project_before = dict(project_state)
    project_state["current_change"] = change_name
    project_state["current_task_status"] = "ready_for_implementation"
    project_state["current_stage"] = "implementation"
    project_state["next_required_action"] = "coding_agent_implement"
    project_state["blocked_by"] = []
    project_state["requires_user_decision"] = False
    if project_state != project_before:
        atomic_write_json(state_path, project_state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change directory name; defaults to current_change")
    parser.add_argument("--approved-by", required=True, help="Product owner or approved controller identity")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    state_path = safe_child(control_root, "project-state.json")

    try:
        if git_top_level(root) != root:
            raise ValueError("--root must be the Git top-level directory")
        with controller_lock(control_root):
            project_state = load_json_object(state_path)
            recorded_root = Path(str(project_state.get("repository_root", ""))).expanduser().resolve()
            if recorded_root != root:
                raise ValueError("project-state repository_root does not match the actual Git top-level")
            change_name = args.change or project_state.get("current_change")
            if not isinstance(change_name, str):
                raise ValueError("no current change; pass --change")
            validate_change_name(change_name)
            assert_focused_change(control_root, change_name, project=project_state)
            change_path = safe_child(control_root, "changes", change_name)
            workflow_path = safe_child(change_path, "workflow-state.json")
            draft_path = safe_child(change_path, "task-contract.draft.json")
            workflow = load_json_object(workflow_path)
            if workflow.get("status") not in {"draft", "ready_for_implementation"}:
                raise ValueError("only a draft or recoverable freeze can be processed")

            draft = load_json_object(draft_path)
            errors = validate_contract(draft, frozen=False)
            if errors:
                print("ERROR: draft contract is invalid", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1

            baseline_sha = str(draft["baseline"]["sha"]).lower()
            resolved_sha = verify_git_commit(root, baseline_sha)
            if resolved_sha != baseline_sha:
                raise ValueError("baseline.sha must be the full resolved Git commit SHA")
            branch = str(draft["baseline"]["branch"])
            branch_tip = verify_git_branch(root, branch)
            if not git_is_ancestor(root, baseline_sha, branch_tip):
                raise ValueError("baseline.sha is not an ancestor of baseline.branch")
            actual_identity = actual_repository_identity(root)
            requested_identity = normalize_repository_identity(str(draft["baseline"]["repository"]))
            if requested_identity != actual_identity:
                raise ValueError(
                    f"baseline.repository does not match current repository identity: expected {actual_identity}"
                )

            version = int(draft["contract_version"])
            contracts_dir = safe_child(change_path, "contracts")
            contracts_dir.mkdir(parents=True, exist_ok=True)
            frozen_path = safe_child(contracts_dir, f"task-contract.v{version}.json")
            digest_path = safe_child(contracts_dir, f"task-contract.v{version}.sha256")
            source_digest = sha256_json(draft)
            transaction_path = safe_child(control_root, "transactions", f"freeze-{change_name}-v{version}.json")

            if frozen_path.exists() or digest_path.exists():
                if not frozen_path.exists() or not digest_path.exists():
                    raise ValueError("partial frozen contract detected; restore the missing counterpart or remove both")
                frozen = load_json_object(frozen_path)
                contract_digest = sha256_json(frozen)
                recorded_digest = digest_path.read_text(encoding="utf-8").strip()
                if frozen.get("source_draft_digest") != source_digest or contract_digest != recorded_digest:
                    raise ValueError("existing frozen version does not match the current draft; increment version")
                update_states(
                    workflow_path=workflow_path,
                    state_path=state_path,
                    workflow=workflow,
                    project_state=project_state,
                    change_name=change_name,
                    version=version,
                    contract_digest=contract_digest,
                    actor=args.approved_by,
                )
                if transaction_path.exists():
                    transaction_path.unlink()
                print(f"Recovered frozen contract v{version}: {frozen_path}")
                print(f"Contract digest: {contract_digest}")
                return 0

            frozen = dict(draft)
            frozen.update(
                {
                    "frozen_at": now_iso(),
                    "approved_by": args.approved_by,
                    "source_draft_digest": source_digest,
                    "repository_identity": actual_identity,
                    "repository_root": str(root),
                    "baseline_branch_tip_sha": branch_tip,
                }
            )
            errors = validate_contract(frozen, frozen=True)
            if errors:
                print("ERROR: frozen contract would be invalid", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1
            contract_digest = sha256_json(frozen)

            transaction_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(
                transaction_path,
                {
                    "schema_version": 1,
                    "operation": "freeze_contract",
                    "change": change_name,
                    "contract_version": version,
                    "source_draft_digest": source_digest,
                    "contract_digest": contract_digest,
                    "phase": "prepared",
                    "started_at": now_iso(),
                },
            )
            atomic_write_json(frozen_path, frozen)
            atomic_write_text(digest_path, contract_digest + "\n")
            txn = load_json_object(transaction_path)
            txn["phase"] = "contract_written"
            atomic_write_json(transaction_path, txn)
            update_states(
                workflow_path=workflow_path,
                state_path=state_path,
                workflow=workflow,
                project_state=project_state,
                change_name=change_name,
                version=version,
                contract_digest=contract_digest,
                actor=args.approved_by,
            )
            transaction_path.unlink()

        print(f"Frozen contract v{version}: {frozen_path}")
        print(f"Contract digest: {contract_digest}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
