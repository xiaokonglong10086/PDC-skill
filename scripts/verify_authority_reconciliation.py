#!/usr/bin/env python3
"""Owner-first read-only recovery-time authority reconciliation (M3)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    load_json_object,
    safe_child,
    validate_change_name,
)
from capture_implementation_snapshot import load_frozen_contract
from multi_change import (
    FailClosedError,
    derive_active_changes,
    evaluate_focus_owner_truth,
    validate_control_decision_ref_at_commit,
)
from workpath_continuity import current_record, list_revisions, verify_record


def _owner_verdict(owner: str, errors: list[str]) -> dict[str, Any]:
    return {
        "owner": owner,
        "truth_valid": not errors,
        "truth_unambiguous": not errors,
        "findings": errors,
    }


def reconcile(root: Path, control_root: Path) -> dict[str, Any]:
    """Owner-first reconciliation. Read-only. Returns a structured verdict dict.

    Owners: Intent, Learning, Deliverable Reality, Work-control (no fifth domain).
    Projections/references: project-state Focus, roadmap, handoff/capsule, Strategic Workpath.
    Result: PASS (exit 0) / FINDINGS (exit 0, progression allowed) / FAIL_CLOSED (exit 1).
    """
    findings: list[dict[str, Any]] = []
    owners: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []

    project_path = control_root / "project-state.json"
    if not project_path.is_file():
        owners.append(_owner_verdict("Work-control", ["project-state.json missing"]))
        return _result(owners, projections, findings, "FAIL_CLOSED")
    project = load_json_object(project_path)
    active = derive_active_changes(control_root)

    # --- Work-control owner ---
    wc_errors: list[str] = []
    focus = project.get("current_change")
    focus_workflows = dict(active)
    if isinstance(focus, str) and focus not in focus_workflows:
        historical_workflow = safe_child(control_root, "changes", focus, "workflow-state.json")
        if historical_workflow.is_file():
            focus_workflows[focus] = load_json_object(historical_workflow)
    focus_owner = evaluate_focus_owner_truth(project, focus_workflows)
    wc_errors.extend(focus_owner["errors"])
    for evidence in focus_owner["findings"]:
        findings.append(
            {
                "family": "focus_owner_projection",
                "reference": ".ai-product/project-state.json",
                "status": "stale",
                "evidence": evidence,
                "owner_winner": "Work-control",
                "decision_required": False,
                "deterministic_repairable": focus_owner.get("repair") is not None,
                "progression_impact": "old_action_non_executable",
            }
        )
    head = focus_owner.get("head")
    if focus_owner.get("schema_errors"):
        owners.append(_owner_verdict("Work-control", wc_errors))
        return _result(owners, projections, findings, "ERROR")
    if isinstance(head, dict) and head.get("control_decision_ref") is not None:
        try:
            validate_control_decision_ref_at_commit(
                root,
                str(head.get("authority_commit_sha", "")),
                head.get("control_decision_ref"),
                selected_change=str(head.get("selected_change", "")),
            )
        except FailClosedError as exc:
            wc_errors.append(f"Focus Control Decision binding failed: {exc}")
    owners.append(_owner_verdict("Work-control", wc_errors))

    # --- Intent owner: frozen contracts per active change ---
    intent_errors: list[str] = []
    for name, wf in active.items():
        change_path = safe_child(control_root, "changes", name)
        workflow_path = change_path / "workflow-state.json"
        if not workflow_path.is_file():
            intent_errors.append(f"{name}: workflow-state.json missing")
            continue
        workflow = load_json_object(workflow_path)
        if workflow.get("contract_version") is None:
            continue
        try:
            contract, contract_digest = load_frozen_contract(change_path, workflow)
        except ValueError as exc:
            intent_errors.append(f"{name}: frozen contract binding failed: {exc}")
            continue
        if contract.get("task_id") != workflow.get("task_id"):
            intent_errors.append(f"{name}: contract task_id mismatch")
    owners.append(_owner_verdict("Intent", intent_errors))

    # --- Deliverable Reality owner: snapshot/review/execution bindings ---
    dr_errors: list[str] = []
    for name, wf in active.items():
        change_path = safe_child(control_root, "changes", name)
        workflow = wf
        snapshot_path = change_path / "implementation-snapshot.json"
        if workflow.get("implementation_snapshot_digest") is not None:
            if not snapshot_path.is_file():
                dr_errors.append(f"{name}: workflow references snapshot but file missing")
            else:
                snapshot = load_json_object(snapshot_path)
                if snapshot.get("snapshot_digest") != workflow.get("implementation_snapshot_digest"):
                    dr_errors.append(f"{name}: snapshot digest mismatch")
                if snapshot.get("review_commit_sha") != workflow.get("review_commit_sha"):
                    dr_errors.append(f"{name}: review commit binding mismatch")
        exec_path = change_path / "test-execution-record.json"
        if workflow.get("test_execution_record_digest") is not None:
            if not exec_path.is_file():
                dr_errors.append(f"{name}: workflow references execution record but file missing")
            else:
                record = load_json_object(exec_path)
                if record.get("record_digest") != workflow.get("test_execution_record_digest"):
                    dr_errors.append(f"{name}: execution record digest mismatch")
    owners.append(_owner_verdict("Deliverable Reality", dr_errors))

    # --- Learning owner: location only; never silently treated as Intent ---
    learning_roots = [
        control_root / "learning",
        control_root / "backlog.md",
        control_root / "project-facts.md",
        control_root / "codebase-facts.md",
    ]
    learning_errors: list[str] = []
    if not any(p.exists() for p in learning_roots):
        learning_errors.append("Learning authority: no learning/backlog/facts artifact located")
    owners.append(_owner_verdict("Learning", learning_errors))

    # --- Projections/references (not owners) ---
    wp_errors = verify_record(control_root)
    wp_status = "current"
    if wp_errors:
        wp_status = "conflicting"
        for e in wp_errors:
            findings.append({"family": "workpath", "reference": ".ai-product/workpaths/", "status": "conflicting",
                             "evidence": e, "owner_winner": None, "decision_required": False,
                             "deterministic_repairable": False, "progression_impact": "block"})
    current = current_record(control_root)
    if current is not None:
        if current.get("stale"):
            wp_status = "stale"
            findings.append({"family": "workpath_stale", "reference": ".ai-product/workpaths/",
                             "status": "stale", "evidence": current.get("stale_reason") or "stale",
                             "owner_winner": "Work-control", "decision_required": False,
                             "deterministic_repairable": True, "progression_impact": "block_until_replan"})
        for ref in current.get("source_authority_references", []):
            if isinstance(ref, dict):
                rel = str(ref.get("path", "")).replace("\\", "/")
                bound = safe_child(root, *rel.split("/"))
                if not bound.is_file():
                    findings.append({"family": "missing_workpath_authority_ref", "reference": rel,
                                     "status": "conflicting", "evidence": "bound source missing",
                                     "owner_winner": ref.get("owner_domain"), "decision_required": False,
                                     "deterministic_repairable": False, "progression_impact": "unverifiable_projection"})
                else:
                    from common import sha256_file as _sha_file
                    actual = _sha_file(bound)
                    if actual != ref.get("sha256"):
                        findings.append({"family": "changed_workpath_authority_ref", "reference": rel,
                                         "status": "conflicting",
                                         "evidence": f"bound source sha256 changed ({actual[:12]} != {str(ref.get('sha256'))[:12]})",
                                         "owner_winner": ref.get("owner_domain"), "decision_required": False,
                                         "deterministic_repairable": False, "progression_impact": "unverifiable_projection"})
    projections.append({"projection": "workpath", "status": wp_status})

    capsule = control_root / "handoffs" / "latest.md"
    if capsule.is_file():
        text = capsule.read_text(encoding="utf-8", errors="replace")
        capsule_focus_claim = None
        for line in text.splitlines():
            if re.match(
                r"^\s*(?:[-*]\s*)?(?:current[_ ]change|current focus|focused change)\s*(?::|=|is)\s*\S+",
                line,
                flags=re.IGNORECASE,
            ):
                capsule_focus_claim = line.strip()
                break
        if capsule_focus_claim and focus is not None and focus not in capsule_focus_claim:
            findings.append({"family": "conflicting_handoff", "reference": ".ai-product/handoffs/latest.md",
                             "status": "conflicting", "evidence": f"capsule claims a different Focus: {capsule_focus_claim}",
                             "owner_winner": "Work-control", "decision_required": False,
                             "deterministic_repairable": True, "progression_impact": "none"})
            projections.append({"projection": "handoff", "status": "conflicting"})
        else:
            projections.append({"projection": "handoff", "status": "current"})
    else:
        projections.append({"projection": "handoff", "status": "unverifiable"})

    # Roadmap projection is navigation; repository authority (frozen roadmap file) wins by construction.
    roadmap = control_root.parent / ".ai-product" / "roadmap.md"
    if not roadmap.is_file():
        findings.append({"family": "missing_roadmap", "reference": ".ai-product/roadmap.md",
                         "status": "unverifiable", "evidence": "roadmap file missing",
                         "owner_winner": None, "decision_required": False,
                         "deterministic_repairable": False, "progression_impact": "none"})
        projections.append({"projection": "roadmap", "status": "unverifiable"})
    else:
        projections.append({"projection": "roadmap", "status": "current"})

    return _result(owners, projections, findings, _overall(owners, findings))


def _overall(owners: list[dict[str, Any]], findings: list[dict[str, Any]]) -> str:
    owner_invalid = any(not o["truth_valid"] for o in owners)
    owner_ambiguous = any(not o["truth_unambiguous"] for o in owners)
    # decision_required is set only for a disputed reference that is genuinely required for the
    # unique safe control decision (i.e., its absence leaves the decision undecidable).
    decision_required = any(f.get("decision_required") for f in findings)
    if owner_invalid or owner_ambiguous:
        return "FAIL_CLOSED"
    if decision_required:
        return "FAIL_CLOSED"
    if findings:
        return "FINDINGS"
    return "PASS"


def _result(owners: list[dict[str, Any]], projections: list[dict[str, Any]],
            findings: list[dict[str, Any]], overall: str) -> dict[str, Any]:
    progression_allowed = overall == "PASS" or overall == "FINDINGS"
    # Owner truth is valid, unambiguous, and uniquely decides the safe control action even when
    # non-blocking stale/unverifiable projections exist — unique_safe_control_decision stays true
    # unless an owner is invalid/ambiguous or a genuinely-required decision input is missing.
    owner_invalid = any(not o["truth_valid"] for o in owners)
    owner_ambiguous = any(not o["truth_unambiguous"] for o in owners)
    decision_required = any(f.get("decision_required") for f in findings)
    unique_safe = not (owner_invalid or owner_ambiguous or decision_required)
    workpath_status = next(
        (p.get("status") for p in projections if p.get("projection") == "workpath"),
        "unverifiable",
    )
    return {
        "result": overall,
        "owner_truth_valid": all(o["truth_valid"] for o in owners),
        "owner_truth_unambiguous": all(o["truth_unambiguous"] for o in owners),
        "unique_safe_control_decision": unique_safe,
        "progression_allowed": progression_allowed,
        "workpath_projection_status": workpath_status,
        "owner_winner": "Work-control" if unique_safe else None,
        "old_workpath_next_action_executable": overall == "PASS" and workpath_status == "current",
        "allowed_continuation": (
            "CURRENT_WORKPATH_ACTION_ONLY"
            if overall == "PASS"
            else "DETERMINISTIC_PROJECTION_REPAIR_ONLY"
            if overall == "FINDINGS"
            else "NONE"
        ),
        "owners": owners,
        "projections": projections,
        "findings": findings,
    }


def result_exit_code(result: str) -> int:
    mapping = {"PASS": 0, "FINDINGS": 0, "FAIL_CLOSED": 1, "ERROR": 2}
    if result not in mapping:
        raise ValueError(f"unknown authority reconciliation result {result!r}")
    return mapping[result]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change name (validated when provided)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        if args.change:
            validate_change_name(args.change)
        result = reconcile(root, control_root)
        if args.json:
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result["result"] == "PASS":
            print("AUTHORITY RECONCILIATION PASS")
        else:
            print(f"AUTHORITY RECONCILIATION {result['result']}")
            for finding in result["findings"]:
                print(f"- [{finding['family']}] {finding['reference']}: {finding['evidence']}")
        return result_exit_code(str(result["result"]))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
