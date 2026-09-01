#!/usr/bin/env python3
"""Resume a blocked Focused Change only to its exact recorded state and safe source identity."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

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
    git_is_ancestor,
    load_json_object,
    now_iso,
    safe_child,
    validate_change_name,
)
from multi_change import (
    NEXT_ACTION_BY_STATUS,
    POST_SNAPSHOT_STATUSES,
    STAGE_BY_STATUS,
    apply_workflow_transition,
    assert_focused_change,
    materialize_snapshot,
    terminal_transition,
    validate_baseline_freshness,
    validate_clean_execution_base,
    validate_focused_partial_worktree,
    validate_post_snapshot_resume_base,
)


def _has_complete_integration_evidence(change_path: Path) -> bool:
    """True only when the change carries real (non-placeholder) integration evidence:
    a PASS review, an accepted acceptance record, and an integration record with a digest."""
    try:
        review = load_json_object(safe_child(change_path, "review-report.json"))
        acceptance = load_json_object(safe_child(change_path, "acceptance-record.json"))
        record = load_json_object(safe_child(change_path, "integration-record.json"))
    except (OSError, ValueError):
        return False
    return (review.get("verdict") == "PASS"
            and acceptance.get("decision") == "accepted"
            and bool(record.get("record_digest")))


def _resume_integration_ready(root: Path, change_path: Path, workflow: dict[str, Any],
                              contract: dict[str, Any], contract_digest: str) -> None:
    """Strict special case (Controller G): resume a blocked_from=integration_ready Work from its
    integration evidence, not from the old exact-snapshot working-tree rule.

    The reviewed bytes are already integrated into main; the old snapshot is never re-materialized.
    Recovery requires: (1) current main is a legal descendant of the frozen baseline tip; (2) the
    original integration merge commit is still contained in current main; (3) the fixed validator
    returns VALID for the original integration record (which also enforces review/acceptance/
    integration digest binding and exact reviewed-content reconstruction in the merge — including
    the no-tamper condition for the reviewed product files); (4-7) those same checks. Any failure
    FAILS CLOSED."""
    snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
    errors = validate_snapshot(snapshot, contract, contract_digest)
    errors += validate_snapshot_git(root, snapshot, contract)
    if snapshot.get("snapshot_digest") != workflow.get("implementation_snapshot_digest"):
        errors.append("workflow implementation snapshot digest mismatch")
    if snapshot.get("review_commit_sha") != workflow.get("review_commit_sha"):
        errors.append("workflow review commit mismatch")
    if errors:
        raise ValueError("implementation snapshot is invalid: " + "; ".join(errors))
    frozen_tip = str(contract.get("baseline_branch_tip_sha", "")).lower()
    if not frozen_tip or not git_is_ancestor(root, frozen_tip, "HEAD"):
        raise ValueError("cannot resume integration_ready: current main is not a descendant of the frozen baseline tip")
    review = load_json_object(safe_child(change_path, "review-report.json"))
    acceptance = load_json_object(safe_child(change_path, "acceptance-record.json"))
    record_path = safe_child(change_path, "integration-record.json")
    if not record_path.is_file():
        raise ValueError("cannot resume integration_ready: integration record missing")
    if review.get("verdict") != "PASS":
        raise ValueError("cannot resume integration_ready: review is not PASS")
    if acceptance.get("decision") != "accepted":
        raise ValueError("cannot resume integration_ready: acceptance is not accepted")
    record = load_json_object(record_path)
    from validate_integration_record import validate_integration
    errors = validate_integration(record, root, contract, contract_digest, snapshot, review,
                                  acceptance, change_path=change_path)
    if errors:
        raise ValueError("cannot resume integration_ready: integration record is invalid: "
                         + "; ".join(errors))
    merge_sha = str(record.get("merge_commit_sha", ""))
    if not git_is_ancestor(root, merge_sha, "HEAD"):
        raise ValueError("cannot resume integration_ready: integration merge commit is not in current main")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--change")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
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
            current_status = workflow.get("status")
            terminal = terminal_transition(workflow)
            replay = (
                current_status != "blocked"
                and terminal is not None
                and terminal.get("from") == "blocked"
                and terminal.get("to") == current_status
            )
            if current_status != "blocked" and not replay:
                raise ValueError("task is not blocked")
            target = current_status if replay else workflow.get("blocked_from")
            if not isinstance(target, str) or target not in STAGE_BY_STATUS or target in {"blocked", "closed", "draft"}:
                raise ValueError("blocked_from is missing or invalid")
            contract, contract_digest = load_frozen_contract(change_path, workflow)
            if replay and terminal.get("contract_digest") != contract_digest:
                raise ValueError("terminal resume transition contract binding differs from frozen contract")

            snapshot_bound = bool(workflow.get("implementation_snapshot_digest") or workflow.get("review_commit_sha"))
            if target == "integration_ready":
                # EXCLUSIVE branch (Controller v3): incomplete integration evidence must FAIL
                # CLOSED immediately — never fall through to generic snapshot recovery and never
                # materialize the old snapshot as a fallback for a missing evidence chain.
                if not _has_complete_integration_evidence(change_path):
                    raise ValueError(
                        "cannot resume integration_ready: incomplete integration evidence "
                        "(integration record / review report / acceptance record missing, "
                        "unparseable, or invalid)")
                _resume_integration_ready(root, change_path, workflow, contract, contract_digest)
            elif target == "ready_for_implementation":
                # Pre-snapshot freshness stays strict: the current tip must equal the frozen
                # baseline tip, otherwise the existing technical baseline refresh path applies.
                validate_baseline_freshness(root, contract)
                validate_clean_execution_base(root, contract)
            elif snapshot_bound:
                snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
                errors = validate_snapshot(snapshot, contract, contract_digest)
                errors += validate_snapshot_git(root, snapshot, contract)
                if snapshot.get("snapshot_digest") != workflow.get("implementation_snapshot_digest"):
                    errors.append("workflow implementation snapshot digest mismatch")
                if snapshot.get("review_commit_sha") != workflow.get("review_commit_sha"):
                    errors.append("workflow review commit mismatch")
                if errors:
                    raise ValueError("implementation snapshot is invalid: " + "; ".join(errors))

                # Post-snapshot resume freshness: the branch may legitimately have advanced past
                # the frozen tip (reviewed source + Controller control commits). Accept only when
                # the current tip is a descendant of the frozen tip and the current product content
                # is still the exact reviewed snapshot (validated below). Pre-snapshot exact-tip
                # freshness above is unchanged.
                current_tip = validate_post_snapshot_resume_base(root, contract, snapshot)
                current_errors = validate_current_worktree(root, snapshot)
                if current_errors:
                    frozen_tip = str(contract.get("baseline_branch_tip_sha", "")).lower()
                    if current_tip == frozen_tip:
                        # A parked snapshot must be absent from the clean shared base before exact
                        # restoration. This applies only when the branch is still at the frozen tip
                        # (the focus-switch parking case); an advanced tip has no clean shared base
                        # to restore from, so a worktree that is not the exact reviewed snapshot is
                        # a hard rejection rather than a materialization case.
                        validate_clean_execution_base(root, contract)
                        materialize_snapshot(root, snapshot)
                        current_errors = validate_current_worktree(root, snapshot)
                    if current_errors:
                        raise ValueError("snapshot materialization failed: " + "; ".join(current_errors))
            elif target == "implementing":
                # Focus never left this change: partial work may remain, but every path must stay in frozen scope.
                validate_focused_partial_worktree(root, contract)
            elif target in POST_SNAPSHOT_STATUSES:
                raise ValueError("blocked post-snapshot state cannot resume without an exact implementation snapshot binding")
            else:
                validate_focused_partial_worktree(root, contract)

            timestamp = now_iso()
            _, transition_appended = apply_workflow_transition(
                workflow,
                to_status=target,
                contract_digest=contract_digest,
                actor=args.actor,
                reason=args.reason,
                created_at=timestamp,
                record_fields={
                    "implementation_snapshot_digest": workflow.get("implementation_snapshot_digest"),
                    "review_commit_sha": workflow.get("review_commit_sha"),
                    "test_execution_record_digest": workflow.get("test_execution_record_digest"),
                    "tool_version": CONTROLLER_VERSION,
                },
            )
            workflow["blocked_from"] = None
            workflow["blocked_reason"] = None
            workflow["blocked_at"] = None
            workflow["blocked_by"] = None
            if transition_appended:
                atomic_write_json(workflow_path, workflow)
            project_before = copy.deepcopy(project)
            project["current_change"] = change_name
            project["current_task_status"] = target
            project["current_stage"] = STAGE_BY_STATUS[target]
            project["next_required_action"] = NEXT_ACTION_BY_STATUS[target]
            project["blocked_by"] = []
            project["requires_user_decision"] = target == "ready_for_acceptance"
            if transition_appended or project != project_before:
                project.setdefault("history", []).append(
                    {"at": timestamp, "change": change_name, "from": "blocked", "to": target, "actor": args.actor, "reason": args.reason}
                )
                atomic_write_json(project_path, project)
        print(f"Resumed {change_name}: blocked -> {target}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
