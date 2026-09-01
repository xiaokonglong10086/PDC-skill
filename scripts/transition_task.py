#!/usr/bin/env python3
"""Advance a change through legal gated states without modifying the frozen contract."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

from capture_implementation_snapshot import (
    load_frozen_contract,
    validate_current_worktree,
    validate_snapshot,
    validate_snapshot_git,
)
from common import (
    CONTROLLER_VERSION,
    atomic_write_json,
    controller_lock,
    load_json_object,
    now_iso,
    safe_child,
    validate_change_name,
)
from multi_change import (
    apply_workflow_transition,
    assert_focused_change,
    project_after_closure,
    terminal_transition,
    validate_baseline_freshness,
    validate_clean_execution_base,
    validate_focused_partial_worktree,
)
from validate_acceptance_record import validate_acceptance
from validate_integration_record import validate_integration
from validate_review_report import validate_review

TRANSITIONS = {
    "ready_for_implementation": {"implementing", "blocked"},
    "implementing": {"ready_for_review", "blocked"},
    "ready_for_review": {"ready_for_acceptance", "changes_requested", "evidence_missing", "blocked"},
    "changes_requested": {"implementing", "blocked"},
    "evidence_missing": {"implementing", "blocked"},
    "ready_for_acceptance": {"accepted", "changes_requested", "blocked"},
    "accepted": {"integration_ready", "blocked"},
    "integration_ready": {"closed", "blocked"},
    "blocked": set(),
    "closed": set(),
}

STAGE_BY_STATUS = {
    "draft": "task_contracting",
    "ready_for_implementation": "implementation",
    "implementing": "implementation",
    "ready_for_review": "independent_review",
    "changes_requested": "implementation",
    "evidence_missing": "implementation",
    "ready_for_acceptance": "product_acceptance",
    "accepted": "integration",
    "integration_ready": "integration",
    "closed": "observation",
    "blocked": "blocked",
}

NEXT_ACTION_BY_STATUS = {
    "draft": "freeze_task_contract",
    "ready_for_implementation": "coding_agent_implement",
    "implementing": "complete_implementation_and_capture_snapshot",
    "ready_for_review": "controller_independent_review",
    "changes_requested": "coding_agent_fix_failed_items_only",
    "evidence_missing": "coding_agent_supply_contracted_evidence_only",
    "ready_for_acceptance": "product_owner_manual_acceptance",
    "accepted": "prepare_integration",
    "integration_ready": "execute_post_merge_verification_and_close",
    "closed": "select_next_backlog_change",
    "blocked": "resolve_recorded_blocker_then_resume",
}

CAPABILITY_REQUIREMENTS = {
    "implementing": {"repository_access", "shell_access", "git_access", "write_access"},
    "ready_for_review": {"repository_access", "shell_access", "git_access"},
    "ready_for_acceptance": {"repository_access", "shell_access", "git_access", "project_test_execution"},
    "accepted": {"repository_access", "git_access"},
    "integration_ready": {"repository_access", "shell_access", "git_access", "write_access"},
    "closed": {"repository_access", "shell_access", "git_access", "project_test_execution"},
}


def require_capabilities(project: dict[str, Any], target: str) -> None:
    capabilities = project.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError("project capabilities are missing; run check_capabilities.py --update")
    missing = sorted(key for key in CAPABILITY_REQUIREMENTS.get(target, set()) if capabilities.get(key) is not True)
    if missing:
        raise ValueError(
            "required capabilities are unknown or unavailable for this transition: " + ", ".join(missing)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--to", required=True, dest="target")
    parser.add_argument("--change", help="Change directory name; defaults to current_change")
    parser.add_argument("--actor", required=True, help="Identity performing the transition")
    parser.add_argument("--reason")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        with controller_lock(control_root):
            project_path = safe_child(control_root, "project-state.json")
            project = load_json_object(project_path)
            change_name = args.change or project.get("current_change")
            if not isinstance(change_name, str):
                raise ValueError("no current change; pass --change")
            validate_change_name(change_name)
            assert_focused_change(control_root, change_name, project=project)
            change_path = safe_child(control_root, "changes", change_name)
            workflow_path = safe_child(change_path, "workflow-state.json")
            workflow = load_json_object(workflow_path)
            current = str(workflow.get("status"))
            target = args.target
            if current == "blocked":
                raise ValueError("blocked tasks can only be resumed with resume_task.py")
            terminal = terminal_transition(workflow)
            replay = (
                current == target
                and terminal is not None
                and terminal.get("to") == target
                and terminal.get("task_id") == workflow.get("task_id")
            )
            if not replay and target not in TRANSITIONS.get(current, set()):
                raise ValueError(f"illegal transition {current} -> {target}")
            if project.get("current_change") not in (change_name, None):
                raise ValueError("project-state current_change conflicts with requested change; reconcile first")
            if (
                not replay
                and project.get("current_change") == change_name
                and project.get("current_task_status") != current
            ):
                raise ValueError("project-state and workflow-state disagree; run reconcile_project_state.py")
            require_capabilities(project, target)

            contract, contract_digest = load_frozen_contract(change_path, workflow)
            if replay and terminal.get("contract_digest") != contract_digest:
                raise ValueError("terminal transition contract binding differs from frozen contract")
            if target == "implementing":
                validate_baseline_freshness(root, contract)
                if current == "ready_for_implementation":
                    validate_clean_execution_base(root, contract)
                else:
                    validate_focused_partial_worktree(root, contract)
            snapshot: dict[str, Any] | None = None
            review: dict[str, Any] | None = None
            acceptance: dict[str, Any] | None = None
            integration: dict[str, Any] | None = None

            if target == "ready_for_review":
                report_path = safe_child(change_path, "implementation-report.md")
                if not report_path.exists() or not report_path.read_text(encoding="utf-8").strip():
                    raise ValueError("implementation-report.md is required before review")
                snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
                snapshot_errors = validate_snapshot(snapshot, contract, contract_digest)
                snapshot_errors += validate_snapshot_git(root, snapshot, contract)
                snapshot_errors += validate_current_worktree(root, snapshot)
                if snapshot_errors:
                    raise ValueError("implementation snapshot is invalid: " + "; ".join(snapshot_errors))
                if snapshot.get("snapshot_digest") != workflow.get("implementation_snapshot_digest"):
                    raise ValueError("workflow implementation snapshot digest mismatch")
                if snapshot.get("review_commit_sha") != workflow.get("review_commit_sha"):
                    raise ValueError("workflow review commit mismatch")

            if target in {"ready_for_acceptance", "changes_requested", "evidence_missing"} and current == "ready_for_review":
                snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
                review = load_json_object(safe_child(change_path, "review-report.json"))
                review_errors = validate_review(
                    review,
                    contract,
                    contract_digest,
                    snapshot,
                    root,
                    workflow=workflow,
                    change_path=change_path,
                )
                if review_errors:
                    raise ValueError("review report is invalid: " + "; ".join(review_errors))
                required_verdict = {
                    "ready_for_acceptance": "PASS",
                    "changes_requested": "FAIL",
                    "evidence_missing": "EVIDENCE_MISSING",
                }[target]
                if review.get("verdict") != required_verdict:
                    raise ValueError(f"{target} requires verdict {required_verdict}")

            if current == "ready_for_acceptance" and target in {"accepted", "changes_requested"}:
                snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
                worktree_errors = validate_current_worktree(root, snapshot)
                if worktree_errors:
                    raise ValueError("working tree no longer matches accepted review target: " + "; ".join(worktree_errors))
                review = load_json_object(safe_child(change_path, "review-report.json"))
                acceptance = load_json_object(safe_child(change_path, "acceptance-record.json"))
                acceptance_errors = validate_acceptance(acceptance, contract, contract_digest, snapshot, review)
                if acceptance_errors:
                    raise ValueError("acceptance record is invalid: " + "; ".join(acceptance_errors))
                expected = "accepted" if target == "accepted" else "rejected"
                if acceptance.get("decision") != expected:
                    raise ValueError(f"{target} requires acceptance decision {expected}")

            if target == "closed":
                snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
                review = load_json_object(safe_child(change_path, "review-report.json"))
                acceptance = load_json_object(safe_child(change_path, "acceptance-record.json"))
                integration = load_json_object(safe_child(change_path, "integration-record.json"))
                integration_errors = validate_integration(
                    integration, root, contract, contract_digest, snapshot, review, acceptance,
                    change_path=change_path,
                )
                if integration_errors:
                    raise ValueError("integration record is invalid: " + "; ".join(integration_errors))

            if target == "blocked" and not args.reason:
                raise ValueError("blocked transition requires --reason")

            changed_at = now_iso()
            _, transition_appended = apply_workflow_transition(
                workflow,
                to_status=target,
                contract_digest=contract_digest,
                actor=args.actor,
                reason=args.reason or "",
                created_at=changed_at,
                record_fields={
                    "implementation_snapshot_digest": workflow.get("implementation_snapshot_digest"),
                    "review_commit_sha": workflow.get("review_commit_sha"),
                    "test_execution_record_digest": workflow.get("test_execution_record_digest"),
                    "tool_version": CONTROLLER_VERSION,
                },
            )
            if target == "blocked":
                workflow["blocked_from"] = current
                workflow["blocked_reason"] = args.reason
                workflow["blocked_at"] = changed_at
                workflow["blocked_by"] = args.actor
            if transition_appended:
                atomic_write_json(workflow_path, workflow)

            project_before = copy.deepcopy(project)
            if target == "closed":
                project = project_after_closure(control_root, project, change_name)
            else:
                project["current_change"] = change_name
                project["current_task_status"] = target
                project["current_stage"] = STAGE_BY_STATUS[target]
                project["next_required_action"] = NEXT_ACTION_BY_STATUS[target]
                project["blocked_by"] = [args.reason] if target == "blocked" else []
                project["requires_user_decision"] = target == "ready_for_acceptance"
            if target == "closed" and integration is not None:
                project["last_closed_change"] = change_name
                project["last_closed_ref"] = integration.get("merge_commit_sha")
                project["last_closure_assurance"] = integration.get("closure_assurance")
            if transition_appended or project != project_before:
                project.setdefault("history", []).append(
                    {
                        "at": changed_at,
                        "change": change_name,
                        "from": current if transition_appended else terminal.get("from"),
                        "to": target,
                        "actor": args.actor,
                        "reason": args.reason,
                        "tool_version": CONTROLLER_VERSION,
                    }
                )
                atomic_write_json(project_path, project)

        print(f"Transitioned {change_name}: {current} -> {target}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
