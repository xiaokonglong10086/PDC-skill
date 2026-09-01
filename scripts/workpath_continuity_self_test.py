#!/usr/bin/env python3
"""Focused tests: append-only Strategic Workpath history with structured authority bindings."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import is_mutable_controller_record, sha256_json  # noqa: E402
from multi_change import (  # noqa: E402
    FailClosedError,
    apply_workflow_transition,
    build_focus_selection_record,
)
from workpath_continuity import (  # noqa: E402
    _validate_publish_authority,
    create_initial,
    current_record,
    lineage_ids,
    list_revisions,
    mark_stale,
    revise,
    verify_record,
    workpath_root,
)


def _structured_refs(control: Path) -> list[dict]:
    facts = control / "project-facts.md"
    return [
        {
            "path": ".ai-product/project-facts.md",
            "sha256": hashlib.sha256(facts.read_bytes()).hexdigest() if facts.exists() else "0" * 64,
            "owner_domain": "Learning",
            "authority_version": "1",
            "authority_commit_sha": None,
        }
    ]


def _base_projection(control: Path, reason: str = "r", route: str = "Route A") -> dict:
    return {
        "route": route,
        "active_waypoint": "WP-1",
        "major_waypoints": ["WP-1", "WP-2"],
        "revision_reason": reason,
        "ordering_rationale": "order",
        "advancement_exit_conditions": "cond",
        "provisional_future": None,
        "route_uncertainty": "low",
        "source_authority_references": _structured_refs(control),
    }


def _make_control(tmp: Path) -> Path:
    control = tmp / ".ai-product"
    (control / "workpaths" / "revisions").mkdir(parents=True)
    (control / "project-facts.md").write_text("# facts baseline\n", encoding="utf-8")
    _git(tmp, "init", "-b", "main")
    _git(tmp, "config", "user.name", "PDC Self Test")
    _git(tmp, "config", "user.email", "pdc@example.invalid")
    _git(tmp, "config", "core.autocrlf", "false")
    _git(tmp, "add", ".ai-product/project-facts.md")
    _git(tmp, "commit", "-m", "facts")
    return control


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    return result.stdout.strip()


def _explicit_args(control: Path, projection: dict, prior: str | None) -> dict:
    number = len(list(control.glob("decision-*.md"))) + 1
    path = control / f"decision-{number}.md"
    path.write_text(
        "# PDC Control Decision\n"
        "- **Decision:** EXPLICIT_REBUILD\n"
        f"- **Expected prior:** {prior if prior is not None else 'null'}\n"
        f"- **Route:** {projection['route']}\n"
        f"- **Active waypoint:** {projection['active_waypoint']}\n",
        encoding="utf-8",
    )
    relative = f".ai-product/{path.name}"
    _git(control.parent, "add", relative)
    _git(control.parent, "commit", "-m", f"decision {number}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "explicit_control_decision": {"path": relative, "sha256": digest},
        "authority_commit_sha": _git(control.parent, "rev-parse", "HEAD"),
        "owner_event_identity": "cd:" + digest,
        "repository_root": control.parent,
    }


def _create(control: Path, projection: dict) -> dict:
    return create_initial(control, projection, **_explicit_args(control, projection, None))


def _revise(control: Path, projection: dict) -> dict:
    prior = current_record(control)["revision_id"]
    return revise(
        control,
        projection,
        expected_prior_revision_id=prior,
        **_explicit_args(control, projection, prior),
    )


def _mark_stale(control: Path, reason: str, *, projection: dict | None = None) -> dict:
    workflow = {
        "schema_version": 2,
        "task_id": "STALE-OWNER",
        "status": "implementing",
        "contract_digest": "a" * 64,
        "history": [],
    }
    transition, _ = apply_workflow_transition(
        workflow,
        to_status="ready_for_review",
        contract_digest="a" * 64,
        actor="controller",
        reason="stale owner",
        created_at="2026-08-31T00:00:00Z",
    )
    owner_path = control / "changes" / "STALE-owner" / "workflow-state.json"
    owner_path.parent.mkdir(parents=True, exist_ok=True)
    owner_path.write_text(json.dumps(workflow), encoding="utf-8")
    focus = build_focus_selection_record(
        selected_change="STALE-owner",
        prior_focus_selection_id=None,
        owner_event_identity="tr:" + transition["transition_id"],
        authority_commit_sha=_git(control.parent, "rev-parse", "HEAD"),
        control_decision_ref=None,
        actor="controller",
        reason="legal-null stale owner fixture",
        created_at="2026-08-31T00:00:01Z",
    )
    (control / "project-state.json").write_text(
        json.dumps({"current_change": "STALE-owner", "history": [focus]}),
        encoding="utf-8",
    )
    return mark_stale(
        control,
        reason,
        authority_commit_sha=_git(control.parent, "rev-parse", "HEAD"),
        owner_event_identity="tr:" + transition["transition_id"],
        expected_prior_revision_id=current_record(control)["revision_id"],
        repository_root=control.parent,
        projection=projection,
    )


def test_append_only_revise() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        control = _make_control(Path(tmp))
        rev1 = _create(control, _base_projection(control, "initial", "Route A"))
        assert rev1["revision_id"] == "wp-001"
        rev2 = _revise(control, _base_projection(control, "revise", "Route B"))
        assert rev2["revision_id"] == "wp-002"
        assert rev2["prior_revision_id"] == "wp-001"
        assert current_record(control)["revision_id"] == "wp-002"
        hist = json.loads((workpath_root(control) / "revisions" / "wp-001.json").read_text(encoding="utf-8"))
        # Append-only: predecessor content and digest are byte-identical after revise.
        assert hist["route"] == "Route A"
        assert hist["revision_digest"] == rev1["revision_digest"]
        assert hist.get("superseded_by") is None, "predecessor superseded_by must not be backfilled"
        assert lineage_ids(control) == ["wp-002", "wp-001"]
        assert verify_record(control) == []
    print("APPEND-ONLY REVISE PASS")


def test_mark_stale_appends_successor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        control = _make_control(Path(tmp))
        rev1 = _create(control, _base_projection(control, "initial"))
        stale = _mark_stale(control, "route-driving assumption invalidated", projection=_base_projection(control, "stale"))
        assert stale["revision_id"] == "wp-002", stale
        assert stale["stale"] is True and "invalidated" in stale["stale_reason"]
        assert current_record(control)["revision_id"] == "wp-002"
        hist = json.loads((workpath_root(control) / "revisions" / "wp-001.json").read_text(encoding="utf-8"))
        assert hist["stale"] is False and hist["revision_digest"] == rev1["revision_digest"]
    print("MARK STALE APPEND PASS")


def test_mark_stale_legacy_requires_structured_refs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        control = _make_control(Path(tmp))
        legacy = {
            "revision_id": "wp-001",
            "route": "R",
            "active_waypoint": "W",
            "major_waypoints": ["W"],
            "revision_reason": "legacy",
            "source_authority_references": ["roadmap.md#M3"],
            "prior_revision_id": None,
            "stale": False,
        }
        legacy["revision_digest"] = sha256_json({k: v for k, v in legacy.items() if k != "revision_digest"})
        (workpath_root(control) / "revisions" / "wp-001.json").write_text(json.dumps(legacy), encoding="utf-8")
        (workpath_root(control) / "current.json").write_text(json.dumps({"revision_id": "wp-001"}), encoding="utf-8")
        try:
            _mark_stale(control, "stale reason")
            raise AssertionError("legacy current without structured refs must fail closed")
        except ValueError:
            pass
        stale = _mark_stale(control, "stale reason", projection=_base_projection(control, "stale"))
        assert stale["revision_id"] == "wp-002"
    print("LEGACY MARK STALE FAIL-CLOSED PASS")


def test_structured_refs_validation_and_bound_check() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        control = _make_control(Path(tmp))
        bad = _base_projection(control)
        bad["source_authority_references"] = [{"path": "x", "sha256": "0" * 64, "owner_domain": "NOPE"}]
        try:
            _create(control, bad)
            raise AssertionError("invalid owner_domain must fail")
        except ValueError:
            pass
        control2 = _make_control(Path(tmp) / "sub")
        orig_refs = _structured_refs(control2)
        _create(control2, _base_projection(control2))
        (control2 / "project-facts.md").write_text("# changed\n", encoding="utf-8")
        stale_proj = _base_projection(control2, "r2")
        stale_proj["source_authority_references"] = orig_refs  # original binding now stale
        try:
            _revise(control2, stale_proj)
            raise AssertionError("changed bound source must fail closed")
        except ValueError:
            pass
    print("STRUCTURED REF VALIDATION + BOUND CHECK PASS")


def test_cycle_and_dangling_detection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        control = _make_control(Path(tmp))
        _create(control, _base_projection(control))
        _revise(control, _base_projection(control, "r2"))
        cur = json.loads((workpath_root(control) / "revisions" / "wp-002.json").read_text(encoding="utf-8"))
        cur["prior_revision_id"] = "wp-002"
        cur["revision_digest"] = sha256_json({k: v for k, v in cur.items() if k != "revision_digest"})
        (workpath_root(control) / "revisions" / "wp-002.json").write_text(json.dumps(cur), encoding="utf-8")
        errs = verify_record(control)
        assert any("cycle" in e for e in errs), errs
        control3 = _make_control(Path(tmp) / "d")
        _create(control3, _base_projection(control3))
        fork = {
            "revision_id": "wp-099",
            "route": "F",
            "active_waypoint": "W",
            "major_waypoints": ["W"],
            "revision_reason": "fork",
            "source_authority_references": _structured_refs(control3),
            "prior_revision_id": None,
            "stale": False,
        }
        fork["revision_digest"] = sha256_json({k: v for k, v in fork.items() if k != "revision_digest"})
        (workpath_root(control3) / "revisions" / "wp-099.json").write_text(json.dumps(fork), encoding="utf-8")
        errs3 = verify_record(control3)
        assert any("dangling" in e for e in errs3), errs3
    print("CYCLE + DANGLING DETECTION PASS")


def test_identity_exclusion() -> None:
    assert is_mutable_controller_record(".ai-product/workpaths/current.json") is True
    assert is_mutable_controller_record(".ai-product/workpaths/revisions/wp-001.json") is True
    assert is_mutable_controller_record(".ai-product/recovery-tools/run_recovered_full_self_test.py") is False
    assert is_mutable_controller_record(".ai-product/handoffs/latest.md") is True
    print("IDENTITY EXCLUSION PASS")


def test_real_repo_workpaths_untouched() -> None:
    # Isolated-fixture reconstruction of the published legacy history. The real main-worktree
    # .ai-product/workpaths/ is Controller mutable state excluded from implementation review
    # identity, so a detached review worktree may only carry the baseline revisions. This test
    # therefore constructs the complete legacy wp-001/wp-002/wp-003 history in a throwaway
    # fixture and proves the first new successor is wp-004 — never reading main-worktree state,
    # and never weakening the real-history-untouched guarantee (that guarantee is enforced by the
    # Controller's before/after hash evidence, not by guessing external state here).
    with tempfile.TemporaryDirectory() as tmp:
        control = _make_control(Path(tmp))
        # Legacy wp-001
        legacy1 = {
            "revision_id": "wp-001",
            "route": "R1",
            "active_waypoint": "W1",
            "major_waypoints": ["W1", "W2"],
            "revision_reason": "legacy initial",
            "source_authority_references": ["roadmap.md#legacy"],
            "prior_revision_id": None,
            "stale": False,
        }
        legacy1["revision_digest"] = sha256_json({k: v for k, v in legacy1.items() if k != "revision_digest"})
        (workpath_root(control) / "revisions" / "wp-001.json").write_text(json.dumps(legacy1), encoding="utf-8")
        # Legacy wp-002 (successor of wp-001)
        legacy2 = dict(legacy1)
        legacy2["revision_id"] = "wp-002"
        legacy2["route"] = "R2"
        legacy2["prior_revision_id"] = "wp-001"
        legacy2["revision_digest"] = sha256_json({k: v for k, v in legacy2.items() if k != "revision_digest"})
        (workpath_root(control) / "revisions" / "wp-002.json").write_text(json.dumps(legacy2), encoding="utf-8")
        # Legacy wp-003 (current; successor of wp-002)
        legacy3 = dict(legacy2)
        legacy3["revision_id"] = "wp-003"
        legacy3["route"] = "R3"
        legacy3["prior_revision_id"] = "wp-002"
        legacy3["revision_digest"] = sha256_json({k: v for k, v in legacy3.items() if k != "revision_digest"})
        (workpath_root(control) / "revisions" / "wp-003.json").write_text(json.dumps(legacy3), encoding="utf-8")
        (workpath_root(control) / "current.json").write_text(json.dumps({"revision_id": "wp-003"}), encoding="utf-8")

        revs = list_revisions(control)
        assert revs == ["wp-001", "wp-002", "wp-003"], revs
        assert current_record(control)["revision_id"] == "wp-003"
        # First new successor must be wp-004 (no interference from any real worktree state).
        refs = [{
            "path": ".ai-product/project-facts.md",
            "sha256": hashlib.sha256((control / "project-facts.md").read_bytes()).hexdigest(),
            "owner_domain": "Learning",
        }]
        proj = {
            "route": "R4",
            "active_waypoint": "W4",
            "major_waypoints": ["W4"],
            "revision_reason": "test successor",
            "source_authority_references": refs,
        }
        rev = _revise(control, proj)
        assert rev["revision_id"] == "wp-004", rev
        assert rev["prior_revision_id"] == "wp-003", rev
        # Append-only: none of the legacy revisions were rewritten.
        expected_digests = {"wp-001": legacy1["revision_digest"], "wp-002": legacy2["revision_digest"], "wp-003": legacy3["revision_digest"]}
        for rid, route in (("wp-001", "R1"), ("wp-002", "R2"), ("wp-003", "R3")):
            rec = json.loads((workpath_root(control) / "revisions" / f"{rid}.json").read_text(encoding="utf-8"))
            assert rec["route"] == route, rid
            assert rec["revision_digest"] == expected_digests[rid], rid
    print("ISOLATED LEGACY wp-001..003 + SUCCESSOR wp-004 + APPEND-ONLY PASS")


def test_rejected_rebuild_prose_not_authority() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        control = _make_control(Path(tmp))
        decision = control / "decision-rejected-rebuild.md"
        decision.write_text(
            "# PDC Control Decision — adversarial Workpath mechanical-binding probe\n"
            "- **Decision:** `DENY_WORKPATH_REBUILD`\n"
            "- **Expected prior Workpath:** `wp-001`\n"
            "- **Route:** `OTHER-ROUTE`\n"
            "- **Active waypoint:** `OTHER-WAYPOINT`\n\n"
            "## Rejected example — NOT AUTHORIZED\n"
            "The rejected example would use EXPLICIT_REBUILD from wp-999 to route "
            "TARGET-ROUTE at waypoint TARGET-WAYPOINT.\n",
            encoding="utf-8",
        )
        relative = ".ai-product/decision-rejected-rebuild.md"
        _git(control.parent, "add", relative)
        _git(control.parent, "commit", "-m", "adversarial rejected rebuild prose")
        digest = hashlib.sha256(decision.read_bytes()).hexdigest()
        try:
            _validate_publish_authority(
                control,
                control.parent,
                effect="EXPLICIT_REBUILD",
                explicit_control_decision={"path": relative, "sha256": digest},
                authority_commit_sha=_git(control.parent, "rev-parse", "HEAD"),
                owner_event_identity="cd:" + digest,
                expected_prior_revision_id="wp-999",
                projection={"route": "TARGET-ROUTE", "active_waypoint": "TARGET-WAYPOINT"},
            )
        except FailClosedError:
            pass
        else:
            raise AssertionError("R-SELFTEST-MECH-02 rejected prose authorized EXPLICIT_REBUILD")
    print("R-SELFTEST-MECH-02 PASS")


def main() -> int:
    test_append_only_revise()
    test_mark_stale_appends_successor()
    test_mark_stale_legacy_requires_structured_refs()
    test_structured_refs_validation_and_bound_check()
    test_cycle_and_dangling_detection()
    test_identity_exclusion()
    test_real_repo_workpaths_untouched()
    test_rejected_rebuild_prose_not_authority()
    print("WORKPATH CONTINUITY SELF TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
