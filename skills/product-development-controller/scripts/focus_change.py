#!/usr/bin/env python3
"""Switch the single Focused Change only after deterministic parking checks."""

from __future__ import annotations

import argparse
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
    atomic_write_json,
    controller_lock,
    git_is_ancestor,
    git_output,
    load_json_object,
    non_control_git_status,
    safe_child,
    validate_change_name,
)
from multi_change import (
    FailClosedError,
    PARKED_STATUSES,
    POST_SNAPSHOT_STATUSES,
    append_focus_selection_record,
    archive_legacy_focus_records,
    build_focus_selection_record,
    derive_active_changes,
    focus_selection_lineage,
    non_parked_changes,
    project_focus_projection,
    restore_paths_to_revision,
    terminal_transition,
    validate_control_decision_ref_at_commit,
    validate_baseline_freshness,
    validate_clean_execution_base,
    validate_null_focus_selection,
)


def _validate_snapshot_binding(
    root: Path,
    change_path: Path,
    workflow: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
) -> dict[str, Any]:
    snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
    errors = validate_snapshot(snapshot, contract, contract_digest)
    errors += validate_snapshot_git(root, snapshot, contract)
    errors += validate_current_worktree(root, snapshot)
    if snapshot.get("snapshot_digest") != workflow.get("implementation_snapshot_digest"):
        errors.append("workflow implementation snapshot digest mismatch")
    if snapshot.get("review_commit_sha") != workflow.get("review_commit_sha"):
        errors.append("workflow review commit mismatch")
    try:
        ref_tip = git_output(root, "rev-parse", "--verify", str(snapshot.get("review_ref")))
        if ref_tip.lower() != str(snapshot.get("review_commit_sha", "")).lower():
            errors.append("durable review ref no longer identifies the snapshot review commit")
    except ValueError as exc:
        errors.append(str(exc))
    if errors:
        raise ValueError("not_parkable: implementation snapshot is invalid: " + "; ".join(errors))
    return snapshot


def _validate_head_on_execution_base(root: Path, contract: dict[str, Any]) -> str:
    tip = validate_baseline_freshness(root, contract)
    branch = str(contract["baseline"]["branch"])
    current_branch = git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if current_branch != branch:
        raise ValueError("execution_base_mismatch: outgoing change is not on its frozen baseline branch")
    head = git_output(root, "rev-parse", "HEAD").lower()
    if head != tip:
        raise ValueError("execution_base_mismatch: shared HEAD contains an unfinished committed side effect")
    return tip


def _park_integration_ready(root: Path, control_root: Path, name: str, workflow: dict[str, Any]) -> None:
    """Strict special case (Controller F): a blocked_from=integration_ready Work with a valid
    integration record may yield the Focus.

    Integration evidence, not the working-tree delta, is authoritative: the reviewed bytes are
    already integrated into main, so already-integrated product files are NEVER restored to the
    old baseline, integration evidence is untouched, and the snapshot is not rewritten. Park is
    allowed ONLY when every condition holds; otherwise FAIL CLOSED (still not parkable)."""
    change_path = safe_child(control_root, "changes", name)
    contract, contract_digest = load_frozen_contract(change_path, workflow)
    snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
    errors = validate_snapshot(snapshot, contract, contract_digest)
    errors += validate_snapshot_git(root, snapshot, contract)
    if snapshot.get("snapshot_digest") != workflow.get("implementation_snapshot_digest"):
        errors.append("workflow implementation snapshot digest mismatch")
    if snapshot.get("review_commit_sha") != workflow.get("review_commit_sha"):
        errors.append("workflow review commit mismatch")
    if errors:
        raise ValueError("not_parkable: implementation snapshot is invalid: " + "; ".join(errors))
    review = load_json_object(safe_child(change_path, "review-report.json"))
    acceptance = load_json_object(safe_child(change_path, "acceptance-record.json"))
    record_path = safe_child(change_path, "integration-record.json")
    if not record_path.is_file():
        raise ValueError("not_parkable: integration record missing for blocked_from=integration_ready")
    if review.get("verdict") != "PASS":
        raise ValueError("not_parkable: review is not PASS")
    if acceptance.get("decision") != "accepted":
        raise ValueError("not_parkable: acceptance is not accepted")
    record = load_json_object(record_path)
    from validate_integration_record import validate_integration
    errors = validate_integration(record, root, contract, contract_digest, snapshot, review,
                                  acceptance, change_path=change_path)
    if errors:
        raise ValueError("not_parkable: integration record is invalid: " + "; ".join(errors))
    merge_sha = str(record.get("merge_commit_sha", ""))
    if not git_is_ancestor(root, merge_sha, "HEAD"):
        raise ValueError("not_parkable: integration merge commit is not in current main history")
    # All conditions satisfied: Focus may leave the blocked Work. No restore, no record rewrite.


def _park_outgoing(root: Path, control_root: Path, name: str, workflow: dict[str, Any]) -> None:
    status = workflow.get("status")
    if status == "draft":
        if non_control_git_status(root):
            raise ValueError("not_parkable: unrelated/non-controller working-tree or staged work is present")
        return
    if status != "blocked":
        raise ValueError(f"not_parkable: outgoing Focused Change is {status}, not draft or verified blocked")
    blocked_from = workflow.get("blocked_from")
    if blocked_from == "integration_ready":
        _park_integration_ready(root, control_root, name, workflow)
        return
    if blocked_from == "ready_for_implementation":
        change_path = safe_child(control_root, "changes", name)
        contract, _ = load_frozen_contract(change_path, workflow)
        validate_clean_execution_base(root, contract)
        return
    if blocked_from not in ({"implementing"} | POST_SNAPSHOT_STATUSES):
        raise ValueError(f"not_parkable: blocked_from={blocked_from!r} is not a valid parkable execution state")

    change_path = safe_child(control_root, "changes", name)
    contract, contract_digest = load_frozen_contract(change_path, workflow)
    base_tip = _validate_head_on_execution_base(root, contract)
    snapshot = _validate_snapshot_binding(root, change_path, workflow, contract, contract_digest)
    # validate_current_worktree above proves every non-control difference is the exact snapshot;
    # only those verified snapshot paths may now be restored to the validated shared base.
    restore_paths_to_revision(root, snapshot["changed_files"], base_tip)
    validate_clean_execution_base(root, contract)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--change", required=True, help="Target unfinished change to focus")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", default="focus coordination")
    parser.add_argument("--authority-commit", required=True)
    parser.add_argument("--control-decision-path")
    parser.add_argument("--control-decision-sha256")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        target = validate_change_name(args.change)
        with controller_lock(control_root):
            project_path = safe_child(control_root, "project-state.json")
            project = load_json_object(project_path)
            active = derive_active_changes(control_root)
            if target not in active:
                raise ValueError(f"target Focused Change is not unfinished: {target}")
            target_status = active[target].get("status")
            outgoing = project.get("current_change")
            if bool(args.control_decision_path) != bool(args.control_decision_sha256):
                raise ValueError("Control Decision path and SHA-256 must be supplied together")
            lineage = focus_selection_lineage(project)
            if lineage.get("schema_errors"):
                raise ValueError("Focus owner schema is malformed: " + "; ".join(lineage["schema_errors"]))
            if lineage["errors"]:
                raise FailClosedError("Focus owner lineage is ambiguous: " + "; ".join(lineage["errors"]))
            prior_head = lineage["head"]
            prior_id = prior_head.get("focus_selection_id") if isinstance(prior_head, dict) else None
            archived_legacy = 0
            if args.control_decision_path:
                control_decision_ref = {
                    "path": args.control_decision_path,
                    "sha256": args.control_decision_sha256,
                }
                replay_candidate = (
                    isinstance(prior_head, dict)
                    and prior_head.get("selected_change") == target
                    and prior_head.get("control_decision_ref") == control_decision_ref
                    and prior_head.get("authority_commit_sha") == args.authority_commit
                )
                expected_prior_id = (
                    prior_head.get("prior_focus_selection_id")
                    if replay_candidate
                    else prior_id
                )
                control_decision_ref = validate_control_decision_ref_at_commit(
                    root,
                    args.authority_commit,
                    control_decision_ref,
                    selected_change=target,
                    required_effect="FOCUS_SELECTION",
                    expected_prior_focus_selection_id=expected_prior_id,
                )
                owner_event_identity = "cd:" + control_decision_ref["sha256"]
                archived_legacy = archive_legacy_focus_records(project)
            else:
                control_decision_ref = None
                stable = terminal_transition(active[target])
                owner_event_identity = (
                    "tr:" + stable["transition_id"] if stable is not None else ""
                )

            replay = (
                isinstance(prior_head, dict)
                and prior_head.get("selected_change") == target
                and prior_head.get("owner_event_identity") == owner_event_identity
                and prior_head.get("control_decision_ref") == control_decision_ref
                and prior_head.get("authority_commit_sha") == args.authority_commit
            )
            if replay:
                projected = project_focus_projection(project, target, active[target])
                if archived_legacy or projected != project:
                    atomic_write_json(project_path, projected)
                print(f"Focus already selected: {target}")
                return 0

            if control_decision_ref is None:
                owner_event_identity = validate_null_focus_selection(
                    active,
                    selected_change=target,
                    prior_focus_selection_id=prior_id,
                    lineage=lineage,
                    actor=args.actor,
                )
            owner_record = build_focus_selection_record(
                selected_change=target,
                prior_focus_selection_id=prior_id,
                owner_event_identity=owner_event_identity,
                authority_commit_sha=args.authority_commit,
                control_decision_ref=control_decision_ref,
                actor=args.actor,
                reason=args.reason,
            )
            if outgoing == target:
                projected = project_focus_projection(project, target, active[target])
                appended = append_focus_selection_record(projected, owner_record)
                atomic_write_json(project_path, projected)
                print(
                    f"Focus {'owner-bound' if appended else 'already selected'}: {target}"
                )
                return 0
            if target_status not in PARKED_STATUSES:
                raise ValueError(
                    f"target change {target} is {target_status}; only draft or blocked parked work can be selected"
                )

            non_parked = non_parked_changes(active)
            if len(non_parked) > 1:
                raise ValueError("multiple_non_parked: " + ", ".join(non_parked))
            if non_parked and non_parked[0] != outgoing:
                raise ValueError(
                    f"focus_conflict: non-parked change {non_parked[0]} differs from outgoing focus {outgoing!r}"
                )

            if outgoing is not None:
                if not isinstance(outgoing, str) or outgoing not in active:
                    raise ValueError("focus_conflict: current focus is not valid unfinished workflow authority")
                _park_outgoing(root, control_root, outgoing, active[outgoing])

            projected = project_focus_projection(project, target, active[target])
            append_focus_selection_record(projected, owner_record)
            atomic_write_json(project_path, projected)

        print(f"Focused change: {target}")
        return 0
    except FailClosedError as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
