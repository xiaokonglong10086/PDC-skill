#!/usr/bin/env python3
"""A1 owner-first Focus and stable workflow transition self-test."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import digest_record, sha256_json  # noqa: E402
from multi_change import (  # noqa: E402
    append_focus_selection_record,
    apply_workflow_transition,
    build_focus_selection_record,
    evaluate_focus_owner_truth,
    focus_selection_lineage,
    validate_null_focus_selection,
)


def workflow(status: str = "ready_for_implementation") -> dict:
    return {
        "schema_version": 2,
        "task_id": "TASK-1",
        "status": status,
        "contract_digest": "a" * 64,
        "updated_at": None,
        "history": [],
    }


def main() -> int:
    before = workflow()
    expected_pre_digest = sha256_json(before)
    transition, appended = apply_workflow_transition(
        before,
        to_status="implementing",
        contract_digest="a" * 64,
        actor="coding-agent",
        reason="start",
        created_at="2026-08-31T00:00:00Z",
    )
    assert appended is True
    assert before["status"] == "implementing"
    assert transition["pre_transition_workflow_digest"] == expected_pre_digest
    assert transition["transition_id"].startswith("tr-")
    assert transition["transition_record_digest"] == digest_record(
        transition, "transition_record_digest"
    )

    replay, appended = apply_workflow_transition(
        before,
        to_status="implementing",
        contract_digest="a" * 64,
        actor="coding-agent",
        reason="different prose cannot manufacture an event",
        created_at="2026-08-31T00:01:00Z",
    )
    assert appended is False
    assert replay == transition
    assert len(before["history"]) == 1
    replay_three, appended = apply_workflow_transition(
        before,
        to_status="implementing",
        contract_digest="a" * 64,
        actor="coding-agent",
        reason="third replay",
        created_at="2026-08-31T00:01:01Z",
    )
    assert appended is False and replay_three == transition

    blocked = workflow("blocked")
    refreshed, appended = apply_workflow_transition(
        blocked,
        to_status="blocked",
        contract_digest="b" * 64,
        actor="controller",
        reason="technical refresh",
        created_at="2026-08-31T00:02:00Z",
    )
    assert appended is True
    assert refreshed["from"] == refreshed["to"] == "blocked"

    explicit_ref = {"path": ".ai-product/decision.md", "sha256": "c" * 64}
    project = {"current_change": None, "history": []}
    explicit = build_focus_selection_record(
        selected_change="TASK-1-change",
        prior_focus_selection_id=None,
        owner_event_identity="cd:" + "c" * 64,
        authority_commit_sha="d" * 40,
        control_decision_ref=explicit_ref,
        actor="controller",
        reason="explicit selection",
        created_at="2026-08-31T00:03:00Z",
    )
    first_id = explicit["focus_selection_id"]
    reordered_ref = {"sha256": "c" * 64, "path": ".ai-product/decision.md"}
    same = build_focus_selection_record(
        selected_change="TASK-1-change",
        prior_focus_selection_id=None,
        owner_event_identity="cd:" + "c" * 64,
        authority_commit_sha="d" * 40,
        control_decision_ref=reordered_ref,
        actor="controller",
        reason="changed prose",
        created_at="2026-08-31T00:04:00Z",
    )
    assert same["focus_selection_id"] == first_id
    changed_tuple = build_focus_selection_record(
        selected_change="TASK-1-change-2",
        prior_focus_selection_id=None,
        owner_event_identity="cd:" + "c" * 64,
        authority_commit_sha="d" * 40,
        control_decision_ref=reordered_ref,
        actor="controller",
        reason="same prose",
        created_at="2026-08-31T00:04:00Z",
    )
    assert changed_tuple["focus_selection_id"] != first_id
    assert append_focus_selection_record(project, explicit) is True
    assert append_focus_selection_record(project, same) is False
    assert focus_selection_lineage(project)["head"]["focus_selection_id"] == first_id

    invalid_non_head = copy.deepcopy(explicit)
    invalid_non_head["focus_selection_id"] = "fs-" + "e" * 64
    invalid_non_head["record_digest"] = "f" * 64
    project["history"].insert(0, invalid_non_head)
    lineage = focus_selection_lineage(project)
    assert lineage["head"]["focus_selection_id"] == first_id
    assert lineage["errors"] == []
    assert lineage["findings"]

    competing = build_focus_selection_record(
        selected_change="TASK-2-change",
        prior_focus_selection_id=None,
        owner_event_identity="cd:" + "1" * 64,
        authority_commit_sha="2" * 40,
        control_decision_ref={"path": ".ai-product/decision-2.md", "sha256": "1" * 64},
        actor="controller",
        reason="competing head",
        created_at="2026-08-31T00:05:00Z",
    )
    project["history"].append(competing)
    assert focus_selection_lineage(project)["errors"]

    running = workflow("implementing")
    apply_workflow_transition(
        running,
        to_status="ready_for_review",
        contract_digest="a" * 64,
        actor="coding-agent",
        reason="complete",
        created_at="2026-08-31T00:06:00Z",
    )
    active = {"TASK-1-change": running}
    owner_identity = validate_null_focus_selection(
        active,
        selected_change="TASK-1-change",
        prior_focus_selection_id=None,
        lineage={"head": None, "errors": [], "findings": []},
        actor="controller",
    )
    assert owner_identity == "tr:" + running["history"][-1]["transition_id"]

    null_project = {"current_change": None, "history": []}
    null_record = build_focus_selection_record(
        selected_change="TASK-1-change",
        prior_focus_selection_id=None,
        owner_event_identity=owner_identity,
        authority_commit_sha="d" * 40,
        control_decision_ref=None,
        actor="controller",
        reason="legal null reconciliation",
        created_at="2026-08-31T00:06:01Z",
    )
    assert append_focus_selection_record(null_project, null_record) is True
    for replay_index in range(2):
        head = focus_selection_lineage(null_project)["head"]
        assert head is not None
        replay_record = build_focus_selection_record(
            selected_change="TASK-1-change",
            prior_focus_selection_id=head["prior_focus_selection_id"],
            owner_event_identity=owner_identity,
            authority_commit_sha="d" * 40,
            control_decision_ref=None,
            actor="controller",
            reason=f"legal null replay {replay_index}",
            created_at=f"2026-08-31T00:06:0{replay_index + 2}Z",
        )
        assert replay_record["focus_selection_id"] == null_record["focus_selection_id"]
        assert append_focus_selection_record(null_project, replay_record) is False
    assert len(
        [
            item
            for item in null_project["history"]
            if item.get("event") == "focused_change_selected"
        ]
    ) == 1

    for illegal in (
        {"TASK-1-change": workflow("draft")},
        {"TASK-1-change": workflow("implementing"), "TASK-2-change": workflow("implementing")},
        {"TASK-1-change": {**workflow("implementing"), "history": [{"event": "legacy"}]}},
    ):
        try:
            validate_null_focus_selection(
                illegal,
                selected_change="TASK-1-change",
                prior_focus_selection_id=None,
                lineage={"head": None, "errors": [], "findings": []},
                actor="controller",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("illegal null Focus selection was accepted")

    for malformed_ref in (
        {"path": "../escape", "sha256": "c" * 64},
        {"path": "C:/absolute", "sha256": "c" * 64},
        {"path": "/absolute", "sha256": "c" * 64},
    ):
        try:
            build_focus_selection_record(
                selected_change="TASK-1-change",
                prior_focus_selection_id=None,
                owner_event_identity="cd:" + "c" * 64,
                authority_commit_sha="d" * 40,
                control_decision_ref=malformed_ref,
                actor="controller",
                reason="malformed",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("malformed ControlDecisionRefV1 was accepted")

    direct_writers = {
        "init_project.py",
        "freeze_contract.py",
        "transition_task.py",
        "resume_task.py",
        "revise_contract.py",
        "refresh_change_baseline.py",
        "focus_change.py",
        "reconcile_project_state.py",
        "workpath_continuity.py",
        "multi_change.py",
    }
    discovered: set[str] = set()
    for path in SCRIPT_DIR.glob("*.py"):
        if path.name == "self_test.py" or path.name.endswith("_self_test.py"):
            continue
        source = path.read_text(encoding="utf-8")
        if (
            re.search(r"\[[\"']status[\"']\]\s*=", source)
            or "focused_change_selected" in source
            or "CURRENT_POINTER" in source
        ):
            discovered.add(path.name)
    assert discovered <= direct_writers, sorted(discovered - direct_writers)
    for name in (
        "freeze_contract.py",
        "transition_task.py",
        "resume_task.py",
        "revise_contract.py",
        "refresh_change_baseline.py",
    ):
        assert "apply_workflow_transition" in (SCRIPT_DIR / name).read_text(encoding="utf-8")
    assert "append_focus_selection_record" in (SCRIPT_DIR / "focus_change.py").read_text(encoding="utf-8")
    assert "append_focus_selection_record" in (SCRIPT_DIR / "reconcile_project_state.py").read_text(encoding="utf-8")
    assert "publish_workpath_update" in (SCRIPT_DIR / "workpath_continuity.py").read_text(encoding="utf-8")
    status_assigners = []
    for name in direct_writers:
        source = (SCRIPT_DIR / name).read_text(encoding="utf-8")
        if re.search(r"workflow\[[\"']status[\"']\]\s*=", source):
            status_assigners.append(name)
    assert status_assigners == ["multi_change.py"], status_assigners

    owner = evaluate_focus_owner_truth(
        {"current_change": "TASK-1-change", "history": [explicit]},
        {"TASK-1-change": running},
    )
    assert owner["truth_valid"] is True
    assert owner["truth_unambiguous"] is True
    assert owner["errors"] == []
    print("RECONCILE PROJECT STATE SELF TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
