#!/usr/bin/env python3
"""Check and narrowly repair project Focus projection from per-change workflow authority."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from capture_implementation_snapshot import load_frozen_contract
from common import (
    atomic_write_json,
    controller_lock,
    git_output,
    load_json_object,
    safe_child,
    validate_change_name,
)
from multi_change import (
    FailClosedError,
    WORKFLOW_STATUSES,
    append_focus_selection_record,
    build_focus_selection_record,
    evaluate_focus_owner_truth,
    focus_selection_lineage,
    non_parked_changes,
    project_focus_projection,
    unfocused_projection,
    validate_null_focus_selection,
)


def inspect(control_root: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    active: dict[str, dict[str, Any]] = {}
    changes_root = safe_child(control_root, "changes")
    if not changes_root.exists():
        return errors, active
    for path in sorted(changes_root.iterdir(), key=lambda item: item.name):
        if not path.is_dir():
            continue
        try:
            validate_change_name(path.name)
            workflow = load_json_object(safe_child(path, "workflow-state.json"))
            status = workflow.get("status")
            if status not in WORKFLOW_STATUSES:
                raise ValueError(f"invalid workflow status {status!r}")
            if status != "draft":
                load_frozen_contract(path, workflow)
            if status != "closed":
                active[path.name] = workflow
        except ValueError as exc:
            errors.append(f"{path.name}: {exc}")
    return errors, active


def _empty_projection(project: dict[str, Any]) -> dict[str, Any]:
    result = dict(project)
    result["current_change"] = None
    if project.get("last_closed_change"):
        result["current_task_status"] = "closed"
        result["current_stage"] = "observation"
    else:
        result["current_task_status"] = "uninitialized"
        result["current_stage"] = "intake"
    result["next_required_action"] = "select_next_backlog_change" if project.get("last_closed_change") else "establish_project_facts"
    result["blocked_by"] = []
    result["requires_user_decision"] = False
    return result


def _projection_differences(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "current_change", "current_task_status", "current_stage", "next_required_action", "blocked_by", "requires_user_decision"
    ):
        if actual.get(key) != expected.get(key):
            errors.append(f"project {key}={actual.get(key)!r} but workflow/focus truth={expected.get(key)!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--repair", action="store_true", help="Repair project Focus/projection only when authority is deterministic")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    project_path = safe_child(control_root, "project-state.json")
    try:
        with controller_lock(control_root):
            project = load_json_object(project_path)
            validation_errors, active = inspect(control_root)
            non_parked = non_parked_changes(active)
            focus = project.get("current_change")
            workflows = dict(active)
            if isinstance(focus, str) and focus not in workflows:
                historical = safe_child(control_root, "changes", focus, "workflow-state.json")
                if historical.is_file():
                    workflows[focus] = load_json_object(historical)

            lineage = focus_selection_lineage(project)
            if lineage.get("schema_errors"):
                raise ValueError(
                    "Focus owner schema is malformed: " + "; ".join(lineage["schema_errors"])
                )
            owner = evaluate_focus_owner_truth(project, workflows)
            fatal_errors = list(validation_errors)
            findings = list(owner["findings"])
            persistent_findings = [
                finding
                for finding in owner["findings"]
                if finding != "Focus projection is stale relative to owner head"
            ]
            owner_record: dict[str, Any] | None = None
            recovered_change: str | None = None

            if len(non_parked) > 1:
                fatal_errors.append("multiple_non_parked: " + ", ".join(non_parked))

            head = lineage.get("head")
            selected_by_head = head.get("selected_change") if isinstance(head, dict) else None
            selected_head_workflow = workflows.get(selected_by_head) if isinstance(selected_by_head, str) else None
            missing_selected_head = isinstance(head, dict) and selected_head_workflow is None

            if len(non_parked) == 1 and not missing_selected_head and not lineage["errors"]:
                recovered_change = non_parked[0]
                if selected_by_head != recovered_change:
                    prior_id = head.get("focus_selection_id") if isinstance(head, dict) else None
                    owner_identity = validate_null_focus_selection(
                        active,
                        selected_change=recovered_change,
                        prior_focus_selection_id=prior_id,
                        lineage=lineage,
                        actor="controller",
                    )
                    owner_record = build_focus_selection_record(
                        selected_change=recovered_change,
                        prior_focus_selection_id=prior_id,
                        owner_event_identity=owner_identity,
                        authority_commit_sha=git_output(root, "rev-parse", "HEAD").lower(),
                        control_decision_ref=None,
                        actor="controller",
                        reason="Reconcile unique recorded non-parked workflow owner truth",
                    )
                    findings.append("schema-v2 Focus owner propagation is pending")

            if owner_record is None and owner["errors"]:
                fatal_errors.extend(owner["errors"])
            elif owner_record is not None:
                recoverable = {
                    "Focused project has no unique valid schema-v2 Focus owner head",
                    "Focus owner head differs from the unique non-parked workflow owner",
                }
                fatal_errors.extend(error for error in owner["errors"] if error not in recoverable)

            projection_source = copy.deepcopy(project)
            if owner_record is not None:
                append_focus_selection_record(projection_source, owner_record)

            effective_lineage = focus_selection_lineage(projection_source)
            effective_head = effective_lineage.get("head")
            expected: dict[str, Any]
            if isinstance(effective_head, dict):
                selected = effective_head.get("selected_change")
                workflow = workflows.get(selected) if isinstance(selected, str) else None
                if workflow is None:
                    fatal_errors.append("selected Work is missing or unverifiable")
                    expected = dict(projection_source)
                elif workflow.get("status") == "closed":
                    findings.append("selected Work is verifiably closed; deterministic unfocus is pending")
                    expected = (
                        unfocused_projection(projection_source, active)
                        if active
                        else _empty_projection(projection_source)
                    )
                else:
                    expected = project_focus_projection(projection_source, selected, workflow)
            elif active and not non_parked:
                expected = unfocused_projection(projection_source, active)
            elif not active:
                expected = _empty_projection(projection_source)
            else:
                expected = dict(projection_source)

            projection_errors = _projection_differences(projection_source, expected)
            findings.extend(projection_errors)

            repaired = False
            if args.repair and not fatal_errors:
                if owner_record is not None:
                    # Owner truth is durably written before its navigation projection. A retry
                    # after this write observes the same owner ID and completes projection only.
                    atomic_write_json(project_path, projection_source)
                    project = projection_source
                    repaired = True
                if _projection_differences(project, expected):
                    atomic_write_json(project_path, expected)
                    project = expected
                    repaired = True
                findings = persistent_findings

            result_name = "FAIL_CLOSED" if fatal_errors else "FINDINGS" if findings else "PASS"
            errors = fatal_errors if fatal_errors else findings

        result = {
            "result": result_name,
            "valid": result_name == "PASS",
            "owner_truth_valid": not fatal_errors,
            "owner_truth_unambiguous": not fatal_errors,
            "errors": errors,
            "active_changes": sorted(active),
            "non_parked_changes": non_parked,
            "focused_change": project.get("current_change"),
            "repaired": repaired,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result_name != "PASS":
            print(f"PROJECT STATE {result_name}")
            for error in errors:
                print(f"- {error}")
        else:
            print("CONSISTENT project state")
            if repaired:
                print("Project Focus/projection repaired from workflow authority")
        return 0 if result_name in {"PASS", "FINDINGS"} else 1
    except FailClosedError as exc:
        print(f"PROJECT STATE FAIL_CLOSED\n- {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
