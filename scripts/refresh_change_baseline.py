#!/usr/bin/env python3
"""Create an immutable technical-only contract refresh after baseline staleness."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

from capture_implementation_snapshot import load_frozen_contract
from common import (
    CONTROLLER_VERSION,
    actual_repository_identity,
    atomic_write_json,
    atomic_write_text,
    controller_lock,
    git_output,
    load_json_object,
    non_control_git_status,
    now_iso,
    safe_child,
    sha256_json,
    validate_change_name,
    verify_git_branch,
)
from multi_change import (
    apply_workflow_transition,
    assert_focused_change,
    project_focus_projection,
    terminal_transition,
)
from validate_task_contract import BASE_FIELDS, validate_contract

PRODUCT_INTENT_FIELDS = {
    "task_id",
    "title",
    "slug",
    "user_result",
    "in_scope",
    "out_of_scope",
    "allowed_files",
    "forbidden_changes",
    "acceptance_criteria",
    "required_tests",
    "required_evidence",
    "manual_acceptance",
    "post_merge_checks",
    "global_stop_conditions",
    "non_blocking_findings_policy",
    "test_first_exception",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--change")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument(
        "--blocker-resolved",
        action="store_true",
        help="Return to ready_for_implementation; otherwise retain the real blocker at blocked_from=ready_for_implementation",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        with controller_lock(control_root):
            project_path = safe_child(control_root, "project-state.json")
            project = load_json_object(project_path)
            change_name = args.change or project.get("current_change")
            if not isinstance(change_name, str):
                raise ValueError("no Focused Change; pass --change only for the current focus")
            validate_change_name(change_name)
            assert_focused_change(control_root, change_name, project=project)
            change_path = safe_child(control_root, "changes", change_name)
            workflow_path = safe_child(change_path, "workflow-state.json")
            workflow = load_json_object(workflow_path)
            terminal = terminal_transition(workflow)
            if (
                terminal is not None
                and terminal.get("event") == "technical_baseline_refresh"
                and terminal.get("to") == workflow.get("status")
                and terminal.get("contract_digest") == workflow.get("contract_digest")
                and terminal.get("contract_version") == workflow.get("contract_version")
            ):
                projected = project_focus_projection(project, change_name, workflow)
                projected["requires_user_decision"] = False
                if projected != project:
                    atomic_write_json(project_path, projected)
                    print(f"Recovered technical baseline projection for {change_name}")
                else:
                    print(f"Replayed technical baseline refresh for {change_name}")
                return 0
            if workflow.get("status") != "blocked":
                raise ValueError("technical baseline refresh is allowed only for a blocked Focused Change")
            old_contract, old_digest = load_frozen_contract(change_path, workflow)

            actual_identity = actual_repository_identity(root)
            if actual_identity != old_contract.get("repository_identity"):
                raise ValueError("repository identity differs from the frozen contract")
            if Path(str(old_contract.get("repository_root", ""))).expanduser().resolve() != root:
                raise ValueError("repository root differs from the frozen contract")
            branch = str(old_contract["baseline"]["branch"])
            current_tip = verify_git_branch(root, branch)
            old_tip = str(old_contract.get("baseline_branch_tip_sha", "")).lower()
            if current_tip == old_tip:
                raise ValueError("baseline is not stale; technical refresh would create an unnecessary contract version")
            current_branch = git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD")
            if current_branch != branch:
                raise ValueError("technical refresh requires the frozen baseline branch to be checked out")
            if git_output(root, "rev-parse", "HEAD").lower() != current_tip:
                raise ValueError("technical refresh requires HEAD to equal the current baseline branch tip")
            if non_control_git_status(root):
                raise ValueError("technical refresh requires a clean non-controller execution base")

            new_version = int(old_contract["contract_version"]) + 1
            new_draft = {key: copy.deepcopy(old_contract[key]) for key in BASE_FIELDS}
            new_draft["contract_version"] = new_version
            new_draft["baseline"] = {
                "repository": actual_identity,
                "branch": branch,
                "sha": current_tip,
            }
            draft_errors = validate_contract(new_draft, frozen=False)
            if draft_errors:
                raise ValueError("refreshed draft contract is invalid: " + "; ".join(draft_errors))
            for field in PRODUCT_INTENT_FIELDS:
                if new_draft[field] != old_contract[field]:
                    raise ValueError(f"technical refresh attempted to change Product Owner-confirmed field {field}")

            source_digest = sha256_json(new_draft)
            frozen = dict(new_draft)
            frozen.update(
                {
                    "frozen_at": now_iso(),
                    "approved_by": args.actor,
                    "source_draft_digest": source_digest,
                    "repository_identity": actual_identity,
                    "repository_root": str(root),
                    "baseline_branch_tip_sha": current_tip,
                }
            )
            frozen_errors = validate_contract(frozen, frozen=True)
            if frozen_errors:
                raise ValueError("refreshed frozen contract is invalid: " + "; ".join(frozen_errors))
            new_digest = sha256_json(frozen)

            contracts_dir = safe_child(change_path, "contracts")
            frozen_path = safe_child(contracts_dir, f"task-contract.v{new_version}.json")
            digest_path = safe_child(contracts_dir, f"task-contract.v{new_version}.sha256")
            if frozen_path.exists() or digest_path.exists():
                raise ValueError(f"immutable refreshed contract version {new_version} already exists")

            atomic_write_json(safe_child(change_path, "task-contract.draft.json"), new_draft)
            atomic_write_json(frozen_path, frozen)
            atomic_write_text(digest_path, new_digest + "\n")

            old_blocker_reason = workflow.get("blocked_reason")
            old_blocker_by = workflow.get("blocked_by")
            changed_at = now_iso()
            target_status = "ready_for_implementation" if args.blocker_resolved else "blocked"
            if not args.blocker_resolved and (
                not isinstance(old_blocker_reason, str) or not old_blocker_reason.strip()
            ):
                raise ValueError("unresolved technical refresh requires the real blocked_reason to remain recorded")
            apply_workflow_transition(
                workflow,
                to_status=target_status,
                contract_digest=new_digest,
                actor=args.actor,
                reason=args.reason,
                created_at=changed_at,
                record_fields={
                    "event": "technical_baseline_refresh",
                    "superseded_contract_digest": old_digest,
                    "contract_version": new_version,
                    "tool_version": CONTROLLER_VERSION,
                },
            )
            workflow["contract_version"] = new_version
            workflow["contract_digest"] = new_digest
            workflow["implementation_snapshot_digest"] = None
            workflow["review_commit_sha"] = None
            workflow["test_execution_record_digest"] = None
            if args.blocker_resolved:
                workflow["blocked_from"] = None
                workflow["blocked_reason"] = None
                workflow["blocked_at"] = None
                workflow["blocked_by"] = None
            else:
                workflow["blocked_from"] = "ready_for_implementation"
                workflow["blocked_reason"] = old_blocker_reason
                workflow["blocked_at"] = changed_at
                workflow["blocked_by"] = old_blocker_by
            atomic_write_json(workflow_path, workflow)

            projected = project_focus_projection(project, change_name, workflow)
            projected["requires_user_decision"] = False
            projected.setdefault("history", []).append(
                {
                    "at": changed_at,
                    "event": "technical_baseline_refresh",
                    "change": change_name,
                    "actor": args.actor,
                    "reason": args.reason,
                    "contract_version": new_version,
                    "tool_version": CONTROLLER_VERSION,
                }
            )
            atomic_write_json(project_path, projected)

        print(f"Refreshed technical baseline for {change_name}: contract v{new_version}")
        print(f"Contract digest: {new_digest}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
