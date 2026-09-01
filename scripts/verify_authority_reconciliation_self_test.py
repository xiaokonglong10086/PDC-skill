#!/usr/bin/env python3
"""Owner-first reconciliation tests: 7 disagreement families, read-only proof, progression separation."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from verify_authority_reconciliation import reconcile  # noqa: E402
from common import digest_record  # noqa: E402
from multi_change import (  # noqa: E402
    apply_workflow_transition,
    archive_legacy_focus_records,
    build_focus_selection_record,
)


def _tree_digest(control: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(control.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(control)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _structured_ref(control: Path) -> dict[str, Any]:
    facts = control / "project-facts.md"
    return {
        "path": ".ai-product/project-facts.md",
        "sha256": hashlib.sha256(facts.read_bytes()).hexdigest(),
        "owner_domain": "Learning",
    }


def _base_projection(control: Path, reason: str = "r") -> dict[str, Any]:
    return {
        "route": "Route",
        "active_waypoint": "W1",
        "major_waypoints": ["W1"],
        "revision_reason": reason,
        "source_authority_references": [_structured_ref(control)],
    }


def _setup(tmp: Path, *, focus: str | None = None, status: str = "unfocused") -> tuple[Path, Path]:
    root = tmp
    control = root / ".ai-product"
    (control / "changes").mkdir(parents=True)
    (control / "workpaths" / "revisions").mkdir(parents=True)
    (control / "handoffs").mkdir(parents=True, exist_ok=True)
    (control / "project-facts.md").write_text("# facts\n", encoding="utf-8")
    (control / "roadmap.md").write_text("# roadmap\n", encoding="utf-8")
    if focus is not None:
        change_dir = control / "changes" / focus
        change_dir.mkdir(parents=True, exist_ok=True)
        workflow = {
            "status": "ready_for_implementation",
            "task_id": focus,
            "contract_version": None,
            "contract_digest": None,
            "history": [],
        }
        transition, _ = apply_workflow_transition(
            workflow,
            to_status=status,
            contract_digest=None,
            actor="controller",
            reason="fixture owner",
            created_at="2026-08-31T00:00:00Z",
        )
        (change_dir / "workflow-state.json").write_text(
            json.dumps(workflow), encoding="utf-8"
        )
        owner = build_focus_selection_record(
            selected_change=focus,
            prior_focus_selection_id=None,
            owner_event_identity="tr:" + transition["transition_id"],
            authority_commit_sha="b" * 40,
            control_decision_ref=None,
            actor="controller",
            reason="fixture focus",
            created_at="2026-08-31T00:00:01Z",
        )
        history = [owner]
    else:
        history = []
    state = {"current_change": focus, "current_task_status": status, "history": history}
    (control / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
    revision = {
        "revision_format_version": 2,
        "revision_id": "wp-001",
        **_base_projection(control),
        "ordering_rationale": "",
        "advancement_exit_conditions": "",
        "provisional_future": None,
        "route_uncertainty": "",
        "prior_revision_id": None,
        "superseded_by": None,
        "stale": False,
        "stale_reason": None,
        "created_at": "2026-08-31T00:00:00Z",
    }
    revision["revision_digest"] = digest_record(revision, "revision_digest")
    (control / "workpaths" / "revisions" / "wp-001.json").write_text(
        json.dumps(revision), encoding="utf-8"
    )
    (control / "workpaths" / "current.json").write_text(
        json.dumps({"revision_id": "wp-001"}), encoding="utf-8"
    )
    return root, control


def test_stale_roadmap() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        # roadmap projection is stale (roadmap file references old waypoint) — non-blocking
        (control / "roadmap.md").write_text("# roadmap old-route\n", encoding="utf-8")
        result = reconcile(root, control)
        assert result["result"] in ("PASS", "FINDINGS"), result
        assert result["progression_allowed"] is True, result
    print("STALE ROADMAP PASS")


def test_conflicting_handoff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        (control / "handoffs" / "latest.md").write_text("Current focus is C2\n", encoding="utf-8")
        result = reconcile(root, control)
        assert any(f["family"] == "conflicting_handoff" for f in result["findings"]), result
        assert result["progression_allowed"] is True, result
    print("CONFLICTING HANDOFF PASS")


def test_capsule_only_claim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus=None, status="unfocused")
        (control / "handoffs" / "latest.md").write_text("Current focus is C9\n", encoding="utf-8")
        result = reconcile(root, control)
        # capsule-only claim is not followed as truth; repository authority (unfocused) wins
        assert result["result"] in ("PASS", "FINDINGS"), result
        assert result["progression_allowed"] is True, result
    print("CAPSULE ONLY CLAIM PASS")


def test_missing_workpath_authority_ref() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp))
        cur = json.loads((control / "workpaths" / "revisions" / "wp-001.json").read_text(encoding="utf-8"))
        cur["source_authority_references"] = [{"path": ".ai-product/nope.md", "sha256": "0" * 64, "owner_domain": "Intent"}]
        cur["revision_digest"] = _digest(cur)
        (control / "workpaths" / "revisions" / "wp-001.json").write_text(json.dumps(cur), encoding="utf-8")
        result = reconcile(root, control)
        assert any(f["family"] == "missing_workpath_authority_ref" for f in result["findings"]), result
        # A missing/changed Workpath projection reference makes the projection unverifiable but is
        # NOT automatically decision_required: the owner truth (Intent/Learning valid, Work-control
        # unambiguous) still uniquely decides the safe action. This yields FINDINGS, not FAIL_CLOSED.
        assert result["result"] in ("FINDINGS", "PASS"), result
        assert result["progression_allowed"] is True, result
        assert result["unique_safe_control_decision"] is True, result
        assert not any(f["family"] == "missing_workpath_authority_ref" and f["decision_required"] for f in result["findings"]), result
    print("MISSING WORKPATH AUTHORITY REF PROPORTIONAL PASS")


def test_changed_workpath_authority_ref() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp))
        (control / "project-facts.md").write_text("# changed facts\n", encoding="utf-8")
        result = reconcile(root, control)
        # bound source changed -> conflicting projection finding; owner truth still valid/unambiguous
        assert result["result"] in ("FINDINGS", "PASS"), result
        assert result["progression_allowed"] is True, result
        assert result["unique_safe_control_decision"] is True, result
        assert not any(f["family"] == "changed_workpath_authority_ref" and f["decision_required"] for f in result["findings"]), result
    print("CHANGED WORKPATH AUTHORITY REF PROPORTIONAL PASS")


def test_focus_waypoint_mismatch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        # Remove the C1 change authority so the project Focus points at nothing real.
        import shutil as _sh
        _sh.rmtree(control / "changes" / "C1")
        result = reconcile(root, control)
        wc = next(o for o in result["owners"] if o["owner"] == "Work-control")
        assert wc["truth_valid"] is False, result
        assert result["result"] == "FAIL_CLOSED", result
    print("FOCUS WAYPOINT MISMATCH PASS")


def test_old_revision_current() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp))
        old = json.loads((control / "workpaths" / "revisions" / "wp-001.json").read_text())
        successor = dict(old)
        successor.update(_base_projection(control, "r2"))
        successor["revision_id"] = "wp-002"
        successor["prior_revision_id"] = "wp-001"
        successor["revision_digest"] = digest_record(successor, "revision_digest")
        (control / "workpaths" / "revisions" / "wp-002.json").write_text(
            json.dumps(successor), encoding="utf-8"
        )
        # pointer back to old revision (simulate interrupted pointer move)
        (control / "workpaths" / "current.json").write_text(json.dumps({"revision_id": "wp-001"}), encoding="utf-8")
        # dangling wp-002 exists outside lineage -> conflicting
        result = reconcile(root, control)
        assert any("dangling" in str(f.get("evidence", "")) or f["family"] == "workpath" for f in result["findings"]), result
    print("OLD REVISION CURRENT PASS")


def test_owner_clear_stale_projection_nonblocking() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        (control / "handoffs" / "latest.md").write_text("Current focus is C2\n", encoding="utf-8")
        result = reconcile(root, control)
        # Owner truth valid+unambiguous and uniquely decides the safe action despite a conflicting
        # capsule projection -> FINDINGS with progression allowed and unique_safe_control_decision=true.
        assert result["result"] == "FINDINGS", result
        assert result["progression_allowed"] is True, result
        assert result["owner_truth_valid"] is True, result
        assert result["owner_truth_unambiguous"] is True, result
        assert result["unique_safe_control_decision"] is True, result
    print("OWNER-CLEAR STALE PROJECTION NON-BLOCKING PASS")


def test_owner_ambiguity_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        # Introduce ambiguity: two non-parked changes claim execution (focus C1 but C2 also non-parked)
        c2 = control / "changes" / "C2"
        c2.mkdir(parents=True)
        (c2 / "workflow-state.json").write_text(json.dumps({"status": "implementing", "task_id": "C2"}), encoding="utf-8")
        result = reconcile(root, control)
        wc = next(o for o in result["owners"] if o["owner"] == "Work-control")
        assert wc["truth_valid"] is False or wc["truth_unambiguous"] is False, result
        assert result["result"] == "FAIL_CLOSED", result
        assert result["progression_allowed"] is False, result
    print("OWNER AMBIGUITY FAIL CLOSED PASS")


def test_clean_aligned_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus=None, status="unfocused")
        result = reconcile(root, control)
        assert result["result"] == "PASS", result
        assert result["progression_allowed"] is True, result
        assert result["findings"] == [], result
    print("CLEAN ALIGNED PASS")


def test_readonly_no_mutation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus=None, status="unfocused")
        before = _tree_digest(control)
        reconcile(root, control)
        reconcile(root, control)
        after = _tree_digest(control)
        assert before == after, "verifier must be read-only"
    print("READ-ONLY PROOF PASS")


def _frozen_baseline_legacy_focus_history() -> list[dict[str, Any]]:
    legacy: list[dict[str, Any]] = []
    previous_change: str | None = None
    for index in range(1, 15):
        change = f"PDC-SELFTEST-LEGACY-{index:02d}"
        legacy.append(
            {
                "at": f"2026-01-01T00:00:{index:02d}Z",
                "event": "focused_change_selected",
                "from_change": previous_change,
                "change": change,
                "actor": "synthetic-self-test-controller",
                "reason": "deterministic public legacy-focus fixture",
            }
        )
        previous_change = change
    expected_keys = {"at", "event", "from_change", "change", "actor", "reason"}
    assert len(legacy) == 14, len(legacy)
    assert all(set(record) == expected_keys for record in legacy), legacy
    return legacy


def test_legacy_focus_audit_strict_pass_and_fail_closed_guards() -> None:
    legacy = _frozen_baseline_legacy_focus_history()

    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        state_path = control / "project-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["history"] = json.loads(json.dumps(legacy)) + state["history"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = reconcile(root, control)
        assert result["result"] == "PASS", result
        assert result["findings"] == [], result

    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        state_path = control / "project-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["history"] = [
            json.loads(json.dumps(legacy[0])),
            *state["history"],
            json.loads(json.dumps(legacy[1])),
        ]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = reconcile(root, control)
        assert result["result"] != "PASS", result
        archivable = json.loads(json.dumps(state))
        before_archive = json.loads(json.dumps(archivable))
        try:
            archive_legacy_focus_records(archivable)
        except ValueError:
            pass
        else:
            raise AssertionError("schema-v1 Focus record after schema-v2 owner was laundered")
        assert archivable == before_archive, "failed legacy archive must be atomic"

    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        state_path = control / "project-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        boolean_version = dict(legacy[0])
        boolean_version["record_schema_version"] = True
        state["history"].insert(0, boolean_version)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = reconcile(root, control)
        assert result["result"] != "PASS", result
        archivable = {"history": [dict(boolean_version)]}
        before_archive = json.loads(json.dumps(archivable))
        try:
            archive_legacy_focus_records(archivable)
        except ValueError:
            pass
        else:
            raise AssertionError("boolean schema version was accepted as integer schema-v1")
        assert archivable == before_archive, "rejected schema version must not mutate history"

    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        state_path = control / "project-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        malformed = dict(legacy[0])
        malformed.pop("reason")
        archivable = {"history": [json.loads(json.dumps(legacy[1])), malformed]}
        before_archive = json.loads(json.dumps(archivable))
        try:
            archive_legacy_focus_records(archivable)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed schema-v1 Focus record was laundered into audit history")
        assert archivable == before_archive, "malformed legacy archive failure must be atomic"
        state["history"].insert(0, malformed)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = reconcile(root, control)
        assert result["result"] != "PASS", result

    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        state_path = control / "project-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        competing = build_focus_selection_record(
            selected_change="C1",
            prior_focus_selection_id=None,
            owner_event_identity="tr:tr-" + "2" * 64,
            authority_commit_sha="c" * 40,
            control_decision_ref=None,
            actor="controller",
            reason="competing owner fixture",
            created_at="2026-08-31T00:00:02Z",
        )
        state["history"].append(competing)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = reconcile(root, control)
        assert result["result"] == "FAIL_CLOSED", result

    with tempfile.TemporaryDirectory() as tmp:
        root, control = _setup(Path(tmp), focus="C1", status="implementing")
        state_path = control / "project-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        head = state["history"][-1]
        winner_affecting = build_focus_selection_record(
            selected_change="C1",
            prior_focus_selection_id=head["focus_selection_id"],
            owner_event_identity="tr:tr-" + "3" * 64,
            authority_commit_sha="d" * 40,
            control_decision_ref=None,
            actor="controller",
            reason="winner-affecting invalid fixture",
            created_at="2026-08-31T00:00:03Z",
        )
        winner_affecting["record_digest"] = "0" * 64
        state["history"].append(winner_affecting)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = reconcile(root, control)
        assert result["result"] == "FAIL_CLOSED", result
    print("LEGACY FOCUS AUDIT STRICT PASS + FAIL-CLOSED GUARDS PASS")


def _digest(rec: dict[str, Any]) -> str:
    import hashlib as _h
    payload = {k: v for k, v in rec.items() if k != "revision_digest"}
    return _h.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    test_stale_roadmap()
    test_conflicting_handoff()
    test_capsule_only_claim()
    test_missing_workpath_authority_ref()
    test_changed_workpath_authority_ref()
    test_focus_waypoint_mismatch()
    test_old_revision_current()
    test_owner_clear_stale_projection_nonblocking()
    test_owner_ambiguity_fail_closed()
    test_clean_aligned_pass()
    test_readonly_no_mutation()
    test_legacy_focus_audit_strict_pass_and_fail_closed_guards()
    print("AUTHORITY RECONCILIATION SELF TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
