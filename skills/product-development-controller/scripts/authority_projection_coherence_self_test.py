#!/usr/bin/env python3
"""A1 authority/projection coherence and exact result-law self-test."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from multi_change import (  # noqa: E402
    build_focus_selection_record,
    evaluate_focus_owner_truth,
)
from verify_authority_reconciliation import _overall, _result, result_exit_code  # noqa: E402


def focus_record(change: str = "TASK-change") -> dict:
    return build_focus_selection_record(
        selected_change=change,
        prior_focus_selection_id=None,
        owner_event_identity="cd:" + "a" * 64,
        authority_commit_sha="b" * 40,
        control_decision_ref={"path": ".ai-product/decision.md", "sha256": "a" * 64},
        actor="controller",
        reason="bounded",
        created_at="2026-08-31T00:00:00Z",
    )


def verdict(overall: str) -> dict:
    owners = [
        {"owner": owner, "truth_valid": overall not in {"FAIL_CLOSED", "ERROR"},
         "truth_unambiguous": overall not in {"FAIL_CLOSED", "ERROR"}, "findings": []}
        for owner in ("Work-control", "Intent", "Deliverable Reality", "Learning")
    ]
    findings = []
    if overall == "FINDINGS":
        findings.append({"decision_required": False, "status": "stale"})
    if overall == "FAIL_CLOSED":
        findings.append({"decision_required": True, "status": "conflicting"})
    projections = [{"projection": "workpath", "status": "current"}]
    return _result(owners, projections, findings, _overall(owners, findings))


def main() -> int:
    assert result_exit_code("PASS") == 0
    assert result_exit_code("FINDINGS") == 0
    assert result_exit_code("FAIL_CLOSED") == 1
    assert result_exit_code("ERROR") == 2
    assert verdict("PASS")["result"] == "PASS"
    assert verdict("FINDINGS")["result"] == "FINDINGS"
    assert verdict("FAIL_CLOSED")["result"] == "FAIL_CLOSED"
    pass_result = verdict("PASS")
    assert {
        key: pass_result[key]
        for key in (
            "result",
            "owner_truth_valid",
            "owner_truth_unambiguous",
            "unique_safe_control_decision",
            "progression_allowed",
            "workpath_projection_status",
            "owner_winner",
            "old_workpath_next_action_executable",
            "allowed_continuation",
        )
    } == {
        "result": "PASS",
        "owner_truth_valid": True,
        "owner_truth_unambiguous": True,
        "unique_safe_control_decision": True,
        "progression_allowed": True,
        "workpath_projection_status": "current",
        "owner_winner": "Work-control",
        "old_workpath_next_action_executable": True,
        "allowed_continuation": "CURRENT_WORKPATH_ACTION_ONLY",
    }
    finding_result = verdict("FINDINGS")
    assert finding_result["old_workpath_next_action_executable"] is False
    assert finding_result["allowed_continuation"] == "DETERMINISTIC_PROJECTION_REPAIR_ONLY"
    failed_result = verdict("FAIL_CLOSED")
    assert failed_result["progression_allowed"] is False
    assert failed_result["allowed_continuation"] == "NONE"

    record = focus_record()
    workflow = {"status": "implementing", "history": []}
    owner = evaluate_focus_owner_truth(
        {"current_change": "TASK-change", "history": [record]},
        {"TASK-change": workflow},
    )
    assert owner["truth_valid"] and owner["truth_unambiguous"]

    closed = evaluate_focus_owner_truth(
        {"current_change": "TASK-change", "history": [record]},
        {"TASK-change": {"status": "closed", "history": []}},
    )
    assert closed["truth_valid"] is True
    assert closed["truth_unambiguous"] is True
    assert closed["findings"]
    assert closed["repair"] == "UNFOCUS_AND_MARK_STALE"

    missing = evaluate_focus_owner_truth(
        {"current_change": "TASK-change", "history": [record]},
        {},
    )
    assert missing["truth_valid"] is False
    assert missing["errors"]

    malformed = copy.deepcopy(record)
    malformed["control_decision_ref"]["path"] = "../escape"
    malformed["record_digest"] = record["record_digest"]
    malformed_project = {"current_change": "TASK-change", "history": [malformed]}
    before_malformed = copy.deepcopy(malformed_project)
    bad = evaluate_focus_owner_truth(
        malformed_project,
        {"TASK-change": workflow},
    )
    assert bad["truth_valid"] is False
    assert bad["schema_errors"]
    assert malformed_project == before_malformed

    no_head = evaluate_focus_owner_truth(
        {"current_change": "TASK-change", "history": []},
        {"TASK-change": workflow},
    )
    assert no_head["truth_valid"] is False
    assert no_head["errors"]
    print("AUTHORITY PROJECTION COHERENCE SELF TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
