#!/usr/bin/env python3
"""Validate a bounded review report against immutable snapshots and Controller-run tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from capture_implementation_snapshot import (
    load_frozen_contract,
    validate_current_worktree,
    validate_snapshot,
    validate_snapshot_git,
)
from common import (
    ensure_known_keys,
    ensure_required_keys,
    ensure_unique_ids,
    load_json_object,
    normalize_repo_path,
    require_iso8601,
    require_list,
    require_sha256,
    require_string,
    safe_child,
)
from validate_test_execution_record import validate_execution_record

VERDICTS = {"PASS", "FAIL", "EVIDENCE_MISSING"}
CRITERION_RESULTS = {"satisfied", "violated", "evidence_missing"}
REPORT_FIELDS_V2 = {
    "schema_version",
    "task_id",
    "contract_version",
    "contract_digest",
    "implementation_snapshot_digest",
    "review_commit_sha",
    "baseline_sha",
    "reviewed_at",
    "reviewer",
    "verdict",
    "checked_criteria",
    "tests_checked",
    "evidence_checked",
    "blocking_findings",
    "evidence_missing",
    "non_blocking_findings",
}
REPORT_FIELDS_V3 = REPORT_FIELDS_V2 | {"test_execution_record_digest"}
REPORT_FIELDS_V4 = REPORT_FIELDS_V3
BLOCKING_FINDING_FIELDS = {"reference", "location", "evidence", "reason", "required_correction"}
CHANGE_SCOPE_FIELDS = {
    "relationship",
    "baseline_state",
    "causal_change_paths",
    "baseline_evidence",
    "review_evidence",
    "causal_explanation",
}
GLOBAL_RELATIONSHIPS = {"introduced", "expanded", "made_unacceptable"}
BASELINE_STATES = {"absent", "present"}


def _validate_global_change_scope(
    errors: list[str],
    label: str,
    value: Any,
    snapshot: dict[str, Any],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    ensure_known_keys(errors, label, value, CHANGE_SCOPE_FIELDS)
    ensure_required_keys(errors, label, value, CHANGE_SCOPE_FIELDS)

    relationship = require_string(errors, f"{label}.relationship", value.get("relationship"))
    if relationship and relationship not in GLOBAL_RELATIONSHIPS:
        errors.append(
            f"{label}.relationship must be introduced, expanded, or made_unacceptable"
        )
    baseline_state = require_string(errors, f"{label}.baseline_state", value.get("baseline_state"))
    if baseline_state and baseline_state not in BASELINE_STATES:
        errors.append(f"{label}.baseline_state must be absent or present")
    if relationship == "introduced" and baseline_state != "absent":
        errors.append(f"{label} relationship=introduced requires baseline_state=absent")
    if relationship in {"expanded", "made_unacceptable"} and baseline_state != "present":
        errors.append(f"{label} relationship={relationship} requires baseline_state=present")

    causal_paths = require_list(
        errors, f"{label}.causal_change_paths", value.get("causal_change_paths")
    )
    normalized_paths: list[str] = []
    changed_files = {
        str(item) for item in snapshot.get("changed_files", []) if isinstance(item, str)
    }
    for index, raw in enumerate(causal_paths, start=1):
        raw_text = require_string(errors, f"{label}.causal_change_paths[{index}]", raw)
        if not raw_text:
            continue
        try:
            normalized = normalize_repo_path(raw_text)
        except ValueError as exc:
            errors.append(
                f"{label}.causal_change_paths[{index}] must be a safe repository-relative path: {exc}"
            )
            continue
        normalized_paths.append(normalized)
        if normalized not in changed_files:
            errors.append(
                f"{label}.causal_change_paths[{index}] must appear in implementation snapshot changed_files"
            )
    if len(set(normalized_paths)) != len(normalized_paths):
        errors.append(f"{label}.causal_change_paths contains duplicate normalized paths")

    for field in ("baseline_evidence", "review_evidence", "causal_explanation"):
        require_string(errors, f"{label}.{field}", value.get(field))



def _infer_context(
    root: Path | None,
    contract: dict[str, Any],
) -> tuple[Path | None, Path | None, dict[str, Any] | None, dict[str, Any] | None, str | None]:
    candidate_root = root
    if candidate_root is None:
        recorded = contract.get("repository_root")
        if isinstance(recorded, str) and recorded:
            path = Path(recorded).expanduser().resolve()
            if path.is_dir():
                candidate_root = path
    if candidate_root is None:
        return None, None, None, None, None
    try:
        expected_name = f"{contract.get('task_id')}-{contract.get('slug')}"
        expected_path = safe_child(candidate_root, ".ai-product", "changes", expected_name)
        if expected_path.is_dir():
            change_path = expected_path
        else:
            project = load_json_object(safe_child(candidate_root, ".ai-product", "project-state.json"))
            change_name = project.get("current_change") or project.get("last_closed_change")
            if not isinstance(change_name, str):
                change_name = expected_name
            change_path = safe_child(candidate_root, ".ai-product", "changes", change_name)
        workflow = load_json_object(safe_child(change_path, "workflow-state.json"))
        record_path = safe_child(change_path, "test-execution-record.json")
        record = load_json_object(record_path) if record_path.is_file() else None
        return candidate_root, change_path, workflow, record, None
    except ValueError as exc:
        return candidate_root, None, None, None, str(exc)


def validate_review(
    report: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
    snapshot: dict[str, Any],
    root: Path | None = None,
    *,
    execution_record: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    change_path: Path | None = None,
    allow_closed_legacy: bool = False,
    require_snapshot_worktree: bool = True,
) -> list[str]:
    errors: list[str] = []
    inferred_error: str | None = None
    if workflow is None or change_path is None or (execution_record is None and report.get("schema_version") in {3, 4}):
        inferred_root, inferred_change, inferred_workflow, inferred_record, inferred_error = _infer_context(root, contract)
        if root is None and inferred_root is not None:
            root = inferred_root
        if change_path is None:
            change_path = inferred_change
        if workflow is None:
            workflow = inferred_workflow
        if execution_record is None:
            execution_record = inferred_record

    schema = report.get("schema_version")
    workflow_status = workflow.get("status") if isinstance(workflow, dict) else None
    closed_legacy = workflow_status == "closed" and allow_closed_legacy
    if schema == 2:
        if not closed_legacy:
            return [
                "active schema-v2 review cannot satisfy the current review gate; "
                "closed schema-v2 history requires --allow-closed-legacy"
            ]
        report_fields = REPORT_FIELDS_V2
    elif schema == 3:
        if not closed_legacy:
            return [
                "active schema-v3 review cannot satisfy the current review gate; "
                "create a schema-v4 report or use --allow-closed-legacy for closed history"
            ]
        report_fields = REPORT_FIELDS_V3
    elif schema == 4:
        report_fields = REPORT_FIELDS_V4
    else:
        return [
            "review schema_version must equal 4 for active work; "
            "closed schema-v2 or schema-v3 history requires --allow-closed-legacy"
        ]

    ensure_known_keys(errors, "review", report, report_fields)
    ensure_required_keys(errors, "review", report, report_fields)
    if report.get("task_id") != contract.get("task_id"):
        errors.append("review task_id does not match contract")
    if report.get("contract_version") != contract.get("contract_version"):
        errors.append("review contract_version does not match contract")
    if report.get("contract_digest") != contract_digest:
        errors.append("review contract_digest does not match frozen contract")
    snapshot_digest = snapshot.get("snapshot_digest")
    if report.get("implementation_snapshot_digest") != snapshot_digest:
        errors.append("review implementation_snapshot_digest does not match implementation snapshot")
    if report.get("review_commit_sha") != snapshot.get("review_commit_sha"):
        errors.append("review review_commit_sha does not match reviewable Git commit")
    if report.get("baseline_sha") != contract.get("baseline", {}).get("sha"):
        errors.append("review baseline_sha does not match frozen contract")
    require_iso8601(errors, "reviewed_at", report.get("reviewed_at"))
    require_string(errors, "reviewer", report.get("reviewer"))

    verdict = require_string(errors, "verdict", report.get("verdict"))
    if verdict and verdict not in VERDICTS:
        errors.append(f"verdict must be one of {sorted(VERDICTS)}")

    criteria = contract.get("acceptance_criteria", [])
    criterion_map = {str(item["id"]): item for item in criteria if isinstance(item, dict) and "id" in item}
    criterion_ids = set(criterion_map)
    checked = require_list(errors, "checked_criteria", report.get("checked_criteria"), nonempty=False)
    ensure_unique_ids(errors, "checked_criteria", checked)
    checked_map: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(checked, start=1):
        if not isinstance(item, dict):
            continue
        ensure_known_keys(errors, f"checked_criteria[{index}]", item, {"id", "result", "evidence"})
        ensure_required_keys(errors, f"checked_criteria[{index}]", item, {"id", "result", "evidence"})
        item_id = str(item.get("id", ""))
        if item_id not in criterion_ids:
            errors.append(f"checked_criteria[{index}] references unknown criterion {item_id}")
        result = require_string(errors, f"checked_criteria[{index}].result", item.get("result"))
        if result and result not in CRITERION_RESULTS:
            errors.append(f"checked_criteria[{index}].result must be one of {sorted(CRITERION_RESULTS)}")
        require_string(errors, f"checked_criteria[{index}].evidence", item.get("evidence"))
        checked_map[item_id] = item

    required_test_ids = {
        str(item["id"])
        for item in contract.get("required_tests", [])
        if isinstance(item, dict) and "id" in item
    }
    required_evidence_ids = {
        str(item["id"])
        for item in contract.get("required_evidence", [])
        if isinstance(item, dict) and "id" in item
    }
    tests_checked = require_list(errors, "tests_checked", report.get("tests_checked"), nonempty=False)
    evidence_checked = require_list(errors, "evidence_checked", report.get("evidence_checked"), nonempty=False)
    tests_checked_set = {str(item) for item in tests_checked}
    evidence_checked_set = {str(item) for item in evidence_checked}
    if len(tests_checked_set) != len(tests_checked):
        errors.append("tests_checked contains duplicates")
    if len(evidence_checked_set) != len(evidence_checked):
        errors.append("evidence_checked contains duplicates")
    unknown_tests = sorted(tests_checked_set - required_test_ids)
    if unknown_tests:
        errors.append(f"tests_checked contains unknown ids: {', '.join(unknown_tests)}")
    unknown_evidence = sorted(evidence_checked_set - required_evidence_ids)
    if unknown_evidence:
        errors.append(f"evidence_checked contains unknown ids: {', '.join(unknown_evidence)}")

    blocking = require_list(errors, "blocking_findings", report.get("blocking_findings"), nonempty=False)
    missing = require_list(errors, "evidence_missing", report.get("evidence_missing"), nonempty=False)
    non_blocking = require_list(
        errors, "non_blocking_findings", report.get("non_blocking_findings"), nonempty=False
    )

    allowed_global = {f"GLOBAL:{item}" for item in contract.get("global_stop_conditions", [])}
    blocked_criteria: set[str] = set()
    global_blockers: set[str] = set()
    for index, finding in enumerate(blocking, start=1):
        if not isinstance(finding, dict):
            errors.append(f"blocking_findings[{index}] must be an object")
            continue
        finding_fields = BLOCKING_FINDING_FIELDS | ({"change_scope"} if schema == 4 else set())
        ensure_known_keys(errors, f"blocking_findings[{index}]", finding, finding_fields)
        ensure_required_keys(
            errors, f"blocking_findings[{index}]", finding, BLOCKING_FINDING_FIELDS
        )
        reference = require_string(errors, f"blocking_findings[{index}].reference", finding.get("reference"))
        if reference not in criterion_ids and reference not in allowed_global:
            errors.append(
                f"blocking_findings[{index}].reference must be a criterion id or allowed GLOBAL stop condition"
            )
        if reference in criterion_ids:
            blocked_criteria.add(reference)
            if schema == 4 and "change_scope" in finding:
                errors.append(
                    f"blocking_findings[{index}].change_scope is allowed only for GLOBAL blockers"
                )
        if reference in allowed_global:
            global_blockers.add(reference)
            if schema == 4:
                if "change_scope" not in finding:
                    errors.append(
                        f"blocking_findings[{index}].change_scope is required for active GLOBAL blockers"
                    )
                else:
                    _validate_global_change_scope(
                        errors,
                        f"blocking_findings[{index}].change_scope",
                        finding.get("change_scope"),
                        snapshot,
                    )
        for key in ("location", "evidence", "reason", "required_correction"):
            require_string(errors, f"blocking_findings[{index}].{key}", finding.get(key))

    missing_tests: set[str] = set()
    missing_evidence: set[str] = set()
    for index, item in enumerate(missing, start=1):
        if not isinstance(item, dict):
            errors.append(f"evidence_missing[{index}] must be an object")
            continue
        ensure_known_keys(errors, f"evidence_missing[{index}]", item, {"kind", "id", "reason"})
        ensure_required_keys(errors, f"evidence_missing[{index}]", item, {"kind", "id", "reason"})
        kind = require_string(errors, f"evidence_missing[{index}].kind", item.get("kind"))
        item_id = require_string(errors, f"evidence_missing[{index}].id", item.get("id"))
        require_string(errors, f"evidence_missing[{index}].reason", item.get("reason"))
        if kind == "test":
            if item_id not in required_test_ids:
                errors.append(f"evidence_missing[{index}] references unknown required test {item_id}")
            missing_tests.add(item_id)
        elif kind == "evidence":
            if item_id not in required_evidence_ids:
                errors.append(f"evidence_missing[{index}] references unknown required evidence {item_id}")
            missing_evidence.add(item_id)
        else:
            errors.append(f"evidence_missing[{index}].kind must be test or evidence")

    if tests_checked_set & missing_tests:
        errors.append("the same required test cannot be both checked and missing")
    if evidence_checked_set & missing_evidence:
        errors.append("the same required evidence cannot be both checked and missing")

    for index, item in enumerate(non_blocking, start=1):
        if not isinstance(item, dict):
            errors.append(f"non_blocking_findings[{index}] must be an object")
            continue
        ensure_known_keys(errors, f"non_blocking_findings[{index}]", item, {"description", "destination"})
        ensure_required_keys(errors, f"non_blocking_findings[{index}]", item, {"description", "destination"})
        require_string(errors, f"non_blocking_findings[{index}].description", item.get("description"))
        destination = require_string(errors, f"non_blocking_findings[{index}].destination", item.get("destination"))
        if destination and destination not in {"backlog", "issue", "future_change"}:
            errors.append(
                f"non_blocking_findings[{index}].destination must be backlog, issue, or future_change"
            )

    execution_valid = False
    execution_status: str | None = None
    passed_test_ids: set[str] = set()
    failed_test_ids: set[str] = set()
    blocked_test_ids: set[str] = set()
    execution_errors: list[str] = []
    if schema in {3, 4}:
        report_record_digest = report.get("test_execution_record_digest")
        if report_record_digest not in (None, ""):
            require_sha256(errors, "test_execution_record_digest", report_record_digest)
        if execution_record is not None and workflow is not None and change_path is not None and root is not None:
            execution_errors = validate_execution_record(
                execution_record,
                contract,
                contract_digest,
                snapshot,
                workflow,
                root,
                change_path,
                require_current_state=workflow_status in {
                    "ready_for_review",
                    "changes_requested",
                    "evidence_missing",
                },
                require_semantic_index=workflow_status in {
                    "ready_for_review",
                    "changes_requested",
                    "evidence_missing",
                    "ready_for_acceptance",
                    "accepted",
                },
                historical_closed_record=closed_legacy,
                require_snapshot_worktree=require_snapshot_worktree,
            )
            execution_valid = not execution_errors
        elif inferred_error:
            execution_errors = [inferred_error]
        else:
            execution_errors = ["test-execution-record.json is missing or cannot be resolved"]

        if execution_valid and execution_record is not None:
            if report_record_digest != execution_record.get("record_digest"):
                errors.append("review test_execution_record_digest does not match the validated record")
            execution_status = str(execution_record.get("overall_status"))
            for item in execution_record.get("tests", []):
                if not isinstance(item, dict):
                    continue
                test_id = str(item.get("id"))
                result = item.get("result")
                if result == "passed":
                    passed_test_ids.add(test_id)
                elif result == "failed":
                    failed_test_ids.add(test_id)
                elif result == "blocked":
                    blocked_test_ids.add(test_id)
            if tests_checked_set != passed_test_ids:
                errors.append("tests_checked must exactly match tests recorded as passed")
        else:
            if verdict in {"PASS", "FAIL"}:
                errors.extend(f"test execution: {error}" for error in execution_errors)
            if report_record_digest not in (None, ""):
                errors.append("an invalid or missing execution record cannot be bound by the review")

    for criterion_id, item in checked_map.items():
        result = item.get("result")
        criterion = criterion_map.get(criterion_id, {})
        if result == "satisfied":
            missing_mapped_tests = set(criterion.get("test_ids", [])) - tests_checked_set
            missing_mapped_evidence = set(criterion.get("evidence_ids", [])) - evidence_checked_set
            if missing_mapped_tests or missing_mapped_evidence:
                errors.append(
                    f"criterion {criterion_id} cannot be satisfied before all mapped tests and evidence are checked"
                )
        if result == "violated" and criterion_id not in blocked_criteria:
            errors.append(f"violated criterion {criterion_id} requires a matching blocking finding")
        if criterion_id in blocked_criteria and result != "violated":
            errors.append(f"blocking finding for {criterion_id} requires result=violated")

    if verdict == "PASS":
        if blocking:
            errors.append("PASS cannot contain blocking_findings")
        if missing:
            errors.append("PASS cannot contain evidence_missing")
        if set(checked_map) != criterion_ids:
            errors.append("PASS must check every acceptance criterion exactly once")
        for criterion_id in criterion_ids:
            if checked_map.get(criterion_id, {}).get("result") != "satisfied":
                errors.append(f"PASS requires {criterion_id} result=satisfied")
        if tests_checked_set != required_test_ids:
            errors.append("PASS must confirm every required test id")
        if evidence_checked_set != required_evidence_ids:
            errors.append("PASS must confirm every required evidence id")
        if schema in {3, 4} and execution_status != "passed":
            errors.append("PASS requires a valid Controller execution record with overall_status=passed")
    elif verdict == "FAIL":
        if not blocking:
            errors.append("FAIL requires at least one blocking finding")
        if not any(
            item.get("result") == "violated" for item in checked_map.values()
        ) and not global_blockers:
            errors.append("FAIL requires a violated criterion or a GLOBAL stop condition")
        if schema in {3, 4}:
            if execution_status == "blocked" or blocked_test_ids:
                errors.append("blocked test execution requires EVIDENCE_MISSING, not FAIL")
            for test_id in failed_test_ids:
                mapped = {
                    criterion_id
                    for criterion_id, criterion in criterion_map.items()
                    if test_id in set(criterion.get("test_ids", []))
                }
                if not (mapped & blocked_criteria) and "GLOBAL:required_build_failure" not in global_blockers:
                    errors.append(f"failed test {test_id} requires a mapped violated criterion or GLOBAL:required_build_failure")
    elif verdict == "EVIDENCE_MISSING":
        if blocking:
            errors.append("EVIDENCE_MISSING cannot contain blocking findings")
        if not missing:
            errors.append("EVIDENCE_MISSING requires at least one missing item")
        if any(item.get("result") == "violated" for item in checked_map.values()):
            errors.append("EVIDENCE_MISSING cannot mark a criterion as violated")
        if schema in {3, 4}:
            if execution_valid:
                if execution_status != "blocked":
                    errors.append("EVIDENCE_MISSING requires blocked execution or no valid execution record")
                expected_missing_tests = required_test_ids - passed_test_ids
                if missing_tests != expected_missing_tests:
                    errors.append("EVIDENCE_MISSING must list every required test not recorded as passed")
            else:
                if tests_checked_set:
                    errors.append("tests cannot be checked without a valid execution record")
                if missing_tests != required_test_ids:
                    errors.append("without a valid execution record, every required test must be listed as missing")

    snapshot_errors = validate_snapshot(snapshot, contract, contract_digest)
    errors.extend(f"snapshot: {error}" for error in snapshot_errors)
    if root is not None:
        errors.extend(f"snapshot-git: {error}" for error in validate_snapshot_git(root, snapshot, contract))
        if not closed_legacy and require_snapshot_worktree:
            errors.extend(f"working-tree: {error}" for error in validate_current_worktree(root, snapshot))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", help="Path to review-report.json")
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change directory name; defaults to current_change or last_closed_change")
    parser.add_argument("--allow-closed-legacy", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    errors: list[str]
    try:
        state = load_json_object(safe_child(root, ".ai-product", "project-state.json"))
        change_name = args.change or state.get("current_change") or state.get("last_closed_change")
        if not isinstance(change_name, str):
            raise ValueError("no current or last closed change; pass --change")
        change_path = safe_child(root, ".ai-product", "changes", change_name)
        workflow = load_json_object(safe_child(change_path, "workflow-state.json"))
        contract, contract_digest = load_frozen_contract(change_path, workflow)
        snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
        report = load_json_object(Path(args.review).expanduser().resolve())
        record_path = safe_child(change_path, "test-execution-record.json")
        execution_record = load_json_object(record_path) if record_path.is_file() else None
        errors = validate_review(
            report,
            contract,
            contract_digest,
            snapshot,
            root,
            execution_record=execution_record,
            workflow=workflow,
            change_path=change_path,
            allow_closed_legacy=args.allow_closed_legacy,
        )
    except ValueError as exc:
        errors = [str(exc)]

    result = {"valid": not errors, "errors": errors}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print("INVALID review report")
        for error in errors:
            print(f"- {error}")
    else:
        print("VALID review report")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
