#!/usr/bin/env python3
"""Create a new draft contract version from the current immutable contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from capture_implementation_snapshot import load_frozen_contract
from common import (
    CONTROLLER_VERSION,
    atomic_write_json,
    controller_lock,
    load_json_object,
    now_iso,
    safe_child,
    validate_change_name,
)
from multi_change import apply_workflow_transition, assert_focused_change, terminal_transition
from validate_task_contract import BASE_FIELDS

ALLOWED_FROM = {
    "ready_for_implementation",
    "implementing",
    "ready_for_review",
    "changes_requested",
    "evidence_missing",
    "ready_for_acceptance",
    "blocked",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change directory name; defaults to current_change")
    parser.add_argument("--actor", required=True, help="Product owner or controller identity")
    parser.add_argument("--reason", required=True, help="Why the frozen completion boundary must change")
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
            terminal = terminal_transition(workflow)
            if (
                current == "draft"
                and terminal is not None
                and terminal.get("to") == "draft"
                and terminal.get("from") in ALLOWED_FROM
            ):
                draft = load_json_object(safe_child(change_path, "task-contract.draft.json"))
                if draft.get("contract_version") != terminal.get("new_contract_version"):
                    raise ValueError("revised draft version differs from terminal transition")
                project_before = dict(project)
                project["current_change"] = change_name
                project["current_stage"] = "task_contracting"
                project["current_task_status"] = "draft"
                project["next_required_action"] = "edit_and_freeze_revised_contract"
                project["blocked_by"] = []
                project["requires_user_decision"] = True
                if project != project_before:
                    atomic_write_json(project_path, project)
                    print(f"Recovered revised draft projection for {change_name}")
                else:
                    print(f"Replayed revised draft transition for {change_name}")
                return 0
            if current not in ALLOWED_FROM:
                raise ValueError(f"contract revision is not allowed from status {current}")
            frozen, old_digest = load_frozen_contract(change_path, workflow)
            new_draft = {key: frozen[key] for key in BASE_FIELDS}
            new_draft["contract_version"] = int(frozen["contract_version"]) + 1
            draft_path = safe_child(change_path, "task-contract.draft.json")
            atomic_write_json(draft_path, new_draft)

            changed_at = now_iso()
            apply_workflow_transition(
                workflow,
                to_status="draft",
                contract_digest=old_digest,
                actor=args.actor,
                reason=args.reason,
                created_at=changed_at,
                record_fields={
                    "superseded_contract_digest": old_digest,
                    "new_contract_version": new_draft["contract_version"],
                    "tool_version": CONTROLLER_VERSION,
                },
            )
            workflow["contract_version"] = None
            workflow["contract_digest"] = None
            workflow["implementation_snapshot_digest"] = None
            workflow["review_commit_sha"] = None
            workflow["test_execution_record_digest"] = None
            workflow["blocked_from"] = None
            workflow["blocked_reason"] = None
            workflow["blocked_at"] = None
            workflow["blocked_by"] = None
            atomic_write_json(workflow_path, workflow)

            project["current_stage"] = "task_contracting"
            project["current_change"] = change_name
            project["current_task_status"] = "draft"
            project["next_required_action"] = "edit_and_freeze_revised_contract"
            project["blocked_by"] = []
            project["requires_user_decision"] = True
            atomic_write_json(project_path, project)

        print(
            f"Created draft contract v{new_draft['contract_version']} from immutable v{frozen['contract_version']}"
        )
        print(f"Superseded digest remains preserved: {old_digest}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
