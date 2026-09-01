#!/usr/bin/env python3
"""Validate product-owner acceptance against the frozen contract and reviewed snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from capture_implementation_snapshot import load_frozen_contract, validate_current_worktree, validate_snapshot
from common import (
    ensure_known_keys,
    ensure_required_keys,
    ensure_unique_ids,
    load_json_object,
    require_iso8601,
    require_list,
    require_string,
    safe_child,
    sha256_json,
)
from validate_review_report import validate_review

DECISIONS = {"accepted", "rejected", "blocked"}
SCENARIO_RESULTS = {"passed", "failed", "blocked"}
FIELDS = {
    "schema_version",
    "task_id",
    "contract_version",
    "contract_digest",
    "implementation_snapshot_digest",
    "review_commit_sha",
    "decision",
    "recorded_at",
    "tester",
    "environment",
    "scenarios",
    "notes",
}


def validate_acceptance(
    record: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
    snapshot: dict[str, Any],
    review: dict[str, Any],
    root: Path | None = None,
    *,
    execution_record: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    change_path: Path | None = None,
    require_snapshot_worktree: bool = True,
) -> list[str]:
    errors: list[str] = []
    ensure_known_keys(errors, "acceptance", record, FIELDS)
    ensure_required_keys(errors, "acceptance", record, FIELDS)
    if record.get("schema_version") != 2:
        errors.append("acceptance schema_version must equal 2")
    if record.get("task_id") != contract.get("task_id"):
        errors.append("acceptance task_id does not match contract")
    if record.get("contract_version") != contract.get("contract_version"):
        errors.append("acceptance contract_version does not match contract")
    if record.get("contract_digest") != contract_digest:
        errors.append("acceptance contract_digest does not match frozen contract")
    if record.get("implementation_snapshot_digest") != snapshot.get("snapshot_digest"):
        errors.append("acceptance implementation_snapshot_digest does not match reviewed snapshot")
    if record.get("review_commit_sha") != snapshot.get("review_commit_sha"):
        errors.append("acceptance review_commit_sha does not match reviewed Git commit")
    if review.get("verdict") != "PASS":
        errors.append("product acceptance requires a valid PASS review")
    require_iso8601(errors, "recorded_at", record.get("recorded_at"))
    require_string(errors, "tester", record.get("tester"))
    require_string(errors, "environment", record.get("environment"))
    require_string(errors, "notes", record.get("notes"), allow_empty=True)

    decision = require_string(errors, "decision", record.get("decision"))
    if decision and decision not in DECISIONS:
        errors.append(f"decision must be one of {sorted(DECISIONS)}")

    scenarios = require_list(errors, "scenarios", record.get("scenarios"))
    ensure_unique_ids(errors, "scenarios", scenarios)
    expected_ids = {
        str(item["id"])
        for item in contract.get("manual_acceptance", [])
        if isinstance(item, dict) and "id" in item
    }
    scenario_map: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(scenarios, start=1):
        if not isinstance(item, dict):
            continue
        ensure_known_keys(errors, f"scenarios[{index}]", item, {"id", "result", "notes"})
        ensure_required_keys(errors, f"scenarios[{index}]", item, {"id", "result", "notes"})
        item_id = str(item.get("id", ""))
        if item_id not in expected_ids:
            errors.append(f"scenarios[{index}] references unknown manual acceptance id {item_id}")
        result = require_string(errors, f"scenarios[{index}].result", item.get("result"))
        if result and result not in SCENARIO_RESULTS:
            errors.append(f"scenarios[{index}].result must be one of {sorted(SCENARIO_RESULTS)}")
        require_string(errors, f"scenarios[{index}].notes", item.get("notes"), allow_empty=True)
        scenario_map[item_id] = item

    if set(scenario_map) != expected_ids:
        missing = sorted(expected_ids - set(scenario_map))
        extra = sorted(set(scenario_map) - expected_ids)
        if missing:
            errors.append(f"acceptance is missing scenarios: {', '.join(missing)}")
        if extra:
            errors.append(f"acceptance contains extra scenarios: {', '.join(extra)}")

    results = [item.get("result") for item in scenario_map.values()]
    if decision == "accepted" and (not results or any(result != "passed" for result in results)):
        errors.append("accepted requires every contracted manual scenario to be passed")
    if decision == "rejected" and "failed" not in results:
        errors.append("rejected requires at least one failed scenario")
    if decision == "blocked":
        if "blocked" not in results:
            errors.append("blocked requires at least one blocked scenario")
        if "failed" in results:
            errors.append("blocked cannot also contain a failed scenario; use rejected")

    errors.extend(f"snapshot: {error}" for error in validate_snapshot(snapshot, contract, contract_digest))
    errors.extend(f"review: {error}" for error in validate_review(
        review, contract, contract_digest, snapshot, root,
        execution_record=execution_record, workflow=workflow, change_path=change_path,
        require_snapshot_worktree=require_snapshot_worktree))
    if root is not None and require_snapshot_worktree:
        errors.extend(f"working-tree: {error}" for error in validate_current_worktree(root, snapshot))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acceptance", help="Path to acceptance-record.json")
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change directory name; defaults to current_change")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    errors: list[str]
    record: dict[str, Any] = {}
    try:
        project_state = load_json_object(safe_child(control_root, "project-state.json"))
        change_name = args.change or project_state.get("current_change")
        if not isinstance(change_name, str):
            raise ValueError("no current change; pass --change")
        change_path = safe_child(control_root, "changes", change_name)
        workflow = load_json_object(safe_child(change_path, "workflow-state.json"))
        contract, contract_digest = load_frozen_contract(change_path, workflow)
        snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
        review = load_json_object(safe_child(change_path, "review-report.json"))
        record = load_json_object(Path(args.acceptance).expanduser().resolve())
        errors = validate_acceptance(record, contract, contract_digest, snapshot, review, root)
    except ValueError as exc:
        errors = [str(exc)]

    result = {
        "valid": not errors,
        "errors": errors,
        "record_digest": None if errors else sha256_json(record),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print("INVALID acceptance record")
        for error in errors:
            print(f"- {error}")
    else:
        print("VALID acceptance record")
        print(f"Acceptance digest: {result['record_digest']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
