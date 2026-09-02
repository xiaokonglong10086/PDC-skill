#!/usr/bin/env python3
"""Validate Controller-run frozen-test execution evidence for an exact review commit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from capture_implementation_snapshot import (
    load_frozen_contract,
    validate_current_worktree,
    validate_snapshot,
    validate_snapshot_git,
)
from common import (
    current_branch,
    digest_record,
    ensure_known_keys,
    ensure_required_keys,
    git_output,
    load_json_object,
    non_control_git_status,
    parse_iso8601,
    require_integer,
    require_iso8601,
    require_list,
    require_object,
    require_sha,
    require_sha256,
    require_string,
    safe_child,
    semantic_index_digest,
    sha256_bytes,
    sha256_file,
)

RESULTS = {"passed", "failed", "blocked"}
OVERALL_STATUSES = {"passed", "failed", "blocked"}
RECORD_FIELDS = {
    "schema_version",
    "task_id",
    "contract_version",
    "contract_digest",
    "implementation_snapshot_digest",
    "review_commit_sha",
    "baseline_sha",
    "executor",
    "started_at",
    "completed_at",
    "timeout_seconds",
    "isolation",
    "main_worktree",
    "tests",
    "runner_blockers",
    "overall_status",
    "record_digest",
}
ISOLATION_FIELDS = {"strategy", "review_commit_sha", "cleanup", "security_boundary"}
MAIN_WORKTREE_FIELDS = {
    "branch_before",
    "branch_after",
    "head_before",
    "head_after",
    "status_before_sha256",
    "status_after_sha256",
    "index_before_sha256",
    "index_after_sha256",
    "preserved",
}
TEST_FIELDS = {
    "id",
    "type",
    "command",
    "expected",
    "expected_exit_code",
    "started_at",
    "completed_at",
    "actual_exit_code",
    "result",
    "blocked_reason",
    "log_path",
    "log_size",
    "log_sha256",
}


def _parse_time(errors: list[str], label: str, value: Any) -> datetime | None:
    text = require_iso8601(errors, label, value)
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _optional_sha256(errors: list[str], label: str, value: Any) -> str | None:
    if value is None:
        return None
    return require_sha256(errors, label, value)


def _index_digest(root: Path) -> str:
    return semantic_index_digest(root)


def capture_main_worktree_state(root: Path) -> dict[str, Any]:
    status_text = "\n".join(non_control_git_status(root))
    return {
        "branch": current_branch(root),
        "head": git_output(root, "rev-parse", "HEAD").lower(),
        "status_sha256": sha256_bytes(status_text.encode("utf-8")),
        "index_sha256": _index_digest(root),
    }


def validate_execution_record(
    record: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
    snapshot: dict[str, Any],
    workflow: dict[str, Any],
    root: Path,
    change_path: Path,
    *,
    require_workflow_binding: bool = True,
    require_current_state: bool = True,
    require_semantic_index: bool = True,
    historical_closed_record: bool = False,
    require_snapshot_worktree: bool = True,
) -> list[str]:
    errors: list[str] = []
    historical_mode = historical_closed_record and workflow.get("status") == "closed"
    if historical_closed_record and not historical_mode:
        errors.append("historical closed-record mode requires workflow status=closed")
    ensure_known_keys(errors, "test execution record", record, RECORD_FIELDS)
    ensure_required_keys(errors, "test execution record", record, RECORD_FIELDS)
    if record.get("schema_version") != 1:
        errors.append("test execution record schema_version must equal 1")
    if record.get("task_id") != contract.get("task_id"):
        errors.append("test execution record task_id does not match contract")
    if record.get("contract_version") != contract.get("contract_version"):
        errors.append("test execution record contract_version does not match contract")
    if record.get("contract_digest") != contract_digest:
        errors.append("test execution record contract_digest does not match frozen contract")
    if record.get("implementation_snapshot_digest") != snapshot.get("snapshot_digest"):
        errors.append("test execution record snapshot digest does not match implementation snapshot")
    if record.get("review_commit_sha") != snapshot.get("review_commit_sha"):
        errors.append("test execution record review commit does not match implementation snapshot")
    if record.get("baseline_sha") != contract.get("baseline", {}).get("sha"):
        errors.append("test execution record baseline does not match frozen contract")
    require_string(errors, "executor", record.get("executor"))
    timeout_seconds = record.get("timeout_seconds")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        errors.append("timeout_seconds must be a positive number")

    started_at = _parse_time(errors, "started_at", record.get("started_at"))
    completed_at = _parse_time(errors, "completed_at", record.get("completed_at"))
    snapshot_time: datetime | None = None
    try:
        snapshot_text = parse_iso8601(snapshot.get("captured_at"), "snapshot.captured_at")
        snapshot_time = datetime.fromisoformat(snapshot_text[:-1] + "+00:00" if snapshot_text.endswith("Z") else snapshot_text)
    except ValueError as exc:
        errors.append(str(exc))
    if started_at and completed_at and completed_at < started_at:
        errors.append("completed_at cannot be earlier than started_at")
    if started_at and snapshot_time and started_at < snapshot_time:
        errors.append("test execution must start after the implementation snapshot was captured")

    isolation = require_object(errors, "isolation", record.get("isolation"))
    ensure_known_keys(errors, "isolation", isolation, ISOLATION_FIELDS)
    ensure_required_keys(errors, "isolation", isolation, ISOLATION_FIELDS)
    if isolation.get("strategy") != "detached_temporary_git_worktree":
        errors.append("isolation.strategy must be detached_temporary_git_worktree")
    if isolation.get("review_commit_sha") != snapshot.get("review_commit_sha"):
        errors.append("isolation review commit does not match snapshot")
    if isolation.get("cleanup") not in {"removed", "failed"}:
        errors.append("isolation.cleanup must be removed or failed")
    if isolation.get("security_boundary") != "git_isolation_not_security_sandbox":
        errors.append("isolation.security_boundary must document the non-sandbox limitation")

    main_state = require_object(errors, "main_worktree", record.get("main_worktree"))
    ensure_known_keys(errors, "main_worktree", main_state, MAIN_WORKTREE_FIELDS)
    ensure_required_keys(errors, "main_worktree", main_state, MAIN_WORKTREE_FIELDS)
    for key in ("branch_before", "branch_after"):
        value = main_state.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"main_worktree.{key} must be a string or null")
    for key in ("head_before", "head_after"):
        require_sha(errors, f"main_worktree.{key}", main_state.get(key))
    for key in ("status_before_sha256", "status_after_sha256"):
        require_sha256(errors, f"main_worktree.{key}", main_state.get(key))
    _optional_sha256(errors, "main_worktree.index_before_sha256", main_state.get("index_before_sha256"))
    _optional_sha256(errors, "main_worktree.index_after_sha256", main_state.get("index_after_sha256"))
    preserved = (
        main_state.get("branch_before") == main_state.get("branch_after")
        and main_state.get("head_before") == main_state.get("head_after")
        and main_state.get("status_before_sha256") == main_state.get("status_after_sha256")
        and main_state.get("index_before_sha256") == main_state.get("index_after_sha256")
    )
    if main_state.get("preserved") is not preserved:
        errors.append("main_worktree.preserved does not match before/after evidence")
    if not preserved:
        errors.append("main worktree, branch, HEAD, or normal Git index changed during review checks")

    tests = require_list(errors, "tests", record.get("tests"))
    frozen_tests = [item for item in contract.get("required_tests", []) if isinstance(item, dict)]
    frozen_by_id = {str(item.get("id")): item for item in frozen_tests}
    frozen_order = [str(item.get("id")) for item in frozen_tests]
    seen: list[str] = []
    results: list[str] = []
    for index, raw in enumerate(tests, start=1):
        item = require_object(errors, f"tests[{index}]", raw)
        ensure_known_keys(errors, f"tests[{index}]", item, TEST_FIELDS)
        ensure_required_keys(errors, f"tests[{index}]", item, TEST_FIELDS)
        test_id = require_string(errors, f"tests[{index}].id", item.get("id"))
        seen.append(test_id)
        frozen = frozen_by_id.get(test_id)
        if frozen is None:
            errors.append(f"tests[{index}] references unknown required test {test_id}")
            continue
        for key in ("type", "command", "expected"):
            if item.get(key) != frozen.get(key):
                errors.append(f"tests[{index}].{key} differs from frozen contract for {test_id}")
        if item.get("expected_exit_code") != 0:
            errors.append(f"tests[{index}].expected_exit_code must equal 0")
        test_started = _parse_time(errors, f"tests[{index}].started_at", item.get("started_at"))
        test_completed = _parse_time(errors, f"tests[{index}].completed_at", item.get("completed_at"))
        if test_started and test_completed and test_completed < test_started:
            errors.append(f"tests[{index}] completed_at cannot be earlier than started_at")
        if started_at and test_started and test_started < started_at:
            errors.append(f"tests[{index}] started before the record")
        if completed_at and test_completed and test_completed > completed_at:
            errors.append(f"tests[{index}] completed after the record")
        result = require_string(errors, f"tests[{index}].result", item.get("result"))
        if result and result not in RESULTS:
            errors.append(f"tests[{index}].result must be one of {sorted(RESULTS)}")
        results.append(result)
        actual = item.get("actual_exit_code")
        blocked_reason = item.get("blocked_reason")
        if result == "passed":
            if actual != 0:
                errors.append(f"passed test {test_id} must have actual_exit_code 0")
            if blocked_reason is not None:
                errors.append(f"passed test {test_id} cannot have blocked_reason")
        elif result == "failed":
            if isinstance(actual, bool) or not isinstance(actual, int) or actual in {0, 126, 127}:
                errors.append(f"failed test {test_id} must have a nonzero executed exit code other than 126/127")
            if blocked_reason is not None:
                errors.append(f"failed test {test_id} cannot have blocked_reason")
        elif result == "blocked":
            if actual is not None and (isinstance(actual, bool) or not isinstance(actual, int) or actual not in {126, 127}):
                errors.append(f"blocked test {test_id} actual_exit_code must be null, 126, or 127")
            require_string(errors, f"tests[{index}].blocked_reason", blocked_reason)

        log_size = require_integer(errors, f"tests[{index}].log_size", item.get("log_size"), minimum=0)
        require_sha256(errors, f"tests[{index}].log_sha256", item.get("log_sha256"))
        log_rel = require_string(errors, f"tests[{index}].log_path", item.get("log_path"))
        try:
            log_path = safe_child(change_path, *log_rel.replace("\\", "/").split("/"))
            evidence_root = safe_child(change_path, "evidence", "review-tests")
            if evidence_root != log_path.parent and evidence_root not in log_path.parents:
                errors.append(f"review-test log for {test_id} is outside evidence/review-tests")
            elif not log_path.is_file():
                errors.append(f"review-test log for {test_id} is missing")
            else:
                if log_size is not None and log_path.stat().st_size != log_size:
                    errors.append(f"review-test log size for {test_id} does not match")
                if sha256_file(log_path) != item.get("log_sha256"):
                    errors.append(f"review-test log digest for {test_id} does not match")
        except ValueError as exc:
            errors.append(str(exc))

    if seen != frozen_order:
        errors.append("tests must contain every frozen required test exactly once and in frozen order")

    blockers = require_list(errors, "runner_blockers", record.get("runner_blockers"), nonempty=False)
    for index, blocker in enumerate(blockers, start=1):
        require_string(errors, f"runner_blockers[{index}]", blocker)

    if blockers or isolation.get("cleanup") == "failed" or "blocked" in results:
        derived_status = "blocked"
    elif "failed" in results:
        derived_status = "failed"
    else:
        derived_status = "passed"
    overall = require_string(errors, "overall_status", record.get("overall_status"))
    if overall and overall not in OVERALL_STATUSES:
        errors.append(f"overall_status must be one of {sorted(OVERALL_STATUSES)}")
    if overall != derived_status:
        errors.append("overall_status does not match test results and runner blockers")

    if record.get("record_digest") != digest_record(record, "record_digest"):
        errors.append("test execution record_digest does not match record content")
    if require_workflow_binding and workflow.get("test_execution_record_digest") != record.get("record_digest"):
        errors.append("workflow test_execution_record_digest does not match the record")
    if workflow.get("implementation_snapshot_digest") != snapshot.get("snapshot_digest"):
        errors.append("workflow snapshot binding differs from the reviewed snapshot")
    if workflow.get("review_commit_sha") != snapshot.get("review_commit_sha"):
        errors.append("workflow review commit differs from the reviewed snapshot")

    errors.extend(f"snapshot: {error}" for error in validate_snapshot(snapshot, contract, contract_digest))
    errors.extend(f"snapshot-git: {error}" for error in validate_snapshot_git(root, snapshot, contract))
    if not historical_mode and require_snapshot_worktree:
        errors.extend(f"working-tree: {error}" for error in validate_current_worktree(root, snapshot))
    if not historical_mode and (require_current_state or require_semantic_index):
        try:
            current = capture_main_worktree_state(root)
            if require_current_state:
                if current["branch"] != main_state.get("branch_after"):
                    errors.append("current branch differs from the post-execution branch evidence")
                if current["head"] != main_state.get("head_after"):
                    errors.append("current HEAD differs from the post-execution HEAD evidence")
                if current["status_sha256"] != main_state.get("status_after_sha256"):
                    errors.append("current non-controller worktree status differs from post-execution evidence")
            if require_semantic_index and current["index_sha256"] != main_state.get("index_after_sha256"):
                errors.append("current semantic Git index differs from post-execution evidence")
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", help="Path to test-execution-record.json")
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change directory name; defaults to current_change or last_closed_change")
    parser.add_argument(
        "--allow-closed-history",
        action="store_true",
        help=(
            "Inspect a closed historical execution record without comparing the current later-version "
            "checkout or semantic index to the historical snapshot. All immutable historical evidence "
            "checks remain required."
        ),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    errors: list[str]
    try:
        project = load_json_object(safe_child(root, ".ai-product", "project-state.json"))
        change_name = args.change or project.get("current_change") or project.get("last_closed_change")
        if not isinstance(change_name, str):
            raise ValueError("no current or last closed change; pass --change")
        change_path = safe_child(root, ".ai-product", "changes", change_name)
        workflow = load_json_object(safe_child(change_path, "workflow-state.json"))
        contract, contract_digest = load_frozen_contract(change_path, workflow)
        snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
        record = load_json_object(Path(args.record).expanduser().resolve())
        errors = validate_execution_record(
            record,
            contract,
            contract_digest,
            snapshot,
            workflow,
            root,
            change_path,
            require_current_state=workflow.get("status") in {
                "ready_for_review",
                "changes_requested",
                "evidence_missing",
            },
            require_semantic_index=workflow.get("status") in {
                "ready_for_review",
                "changes_requested",
                "evidence_missing",
                "ready_for_acceptance",
                "accepted",
            },
            historical_closed_record=args.allow_closed_history,
        )
    except ValueError as exc:
        errors = [str(exc)]

    result = {"valid": not errors, "errors": errors}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print("INVALID test execution record")
        for error in errors:
            print(f"- {error}")
    else:
        print("VALID test execution record")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
