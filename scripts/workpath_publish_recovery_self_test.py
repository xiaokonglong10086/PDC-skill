#!/usr/bin/env python3
"""A1 Workpath journal, recovery, CAS and explicit-route winner self-test."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import digest_record  # noqa: E402
from multi_change import (  # noqa: E402
    apply_workflow_transition,
    build_focus_selection_record,
    validate_control_decision_ref_at_commit,
)
from workpath_continuity import (  # noqa: E402
    CURRENT_POINTER,
    REVISIONS_DIR,
    projection_update_identity,
    publish_workpath_update,
    validate_effect_pair,
    verify_record,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    return result.stdout.strip()


def authority_fixture(control_root: Path) -> tuple[str, dict, str]:
    repo = control_root.parent
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "PDC Test")
    git(repo, "config", "user.email", "pdc@example.invalid")
    git(repo, "config", "core.autocrlf", "false")
    decision = control_root / "decision.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text(
        "# PDC Control Decision\n"
        "- **Decision:** EXPLICIT_REBUILD\n"
        "- **Expected prior:** wp-001\n"
        "- **Route:** explicit\n"
        "- **Active waypoint:** explicit\n",
        encoding="utf-8",
    )
    workflow = {
        "schema_version": 2,
        "task_id": "TASK-1",
        "status": "implementing",
        "contract_digest": "a" * 64,
        "history": [],
    }
    transition, _ = apply_workflow_transition(
        workflow,
        to_status="ready_for_review",
        contract_digest="a" * 64,
        actor="controller",
        reason="owner",
        created_at="2026-08-31T00:00:00Z",
    )
    write_json(control_root / "changes" / "TASK-1-change" / "workflow-state.json", workflow)
    git(repo, "add", ".ai-product/decision.md")
    git(repo, "commit", "-m", "decision")
    commit = git(repo, "rev-parse", "HEAD")
    ref = {
        "path": ".ai-product/decision.md",
        "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
    }
    focus = build_focus_selection_record(
        selected_change="TASK-1-change",
        prior_focus_selection_id=None,
        owner_event_identity="cd:" + ref["sha256"],
        authority_commit_sha=commit,
        control_decision_ref=ref,
        actor="controller",
        reason="explicit Focus owner",
        created_at="2026-08-31T00:00:01Z",
    )
    write_json(
        control_root / "project-state.json",
        {"current_change": "TASK-1-change", "history": [focus]},
    )
    return commit, ref, "tr:" + transition["transition_id"]


def initial(control_root: Path) -> None:
    root = control_root / "workpaths"
    revision = {
        "revision_format_version": 2,
        "revision_id": "wp-001",
        "route": "initial",
        "active_waypoint": "initial",
        "major_waypoints": ["initial"],
        "ordering_rationale": "",
        "advancement_exit_conditions": "",
        "provisional_future": None,
        "route_uncertainty": "",
        "source_authority_references": [],
        "revision_reason": "initial",
        "prior_revision_id": None,
        "superseded_by": None,
        "stale": False,
        "stale_reason": None,
        "created_at": "2026-08-31T00:00:00Z",
    }
    revision["revision_digest"] = digest_record(revision, "revision_digest")
    write_json(root / REVISIONS_DIR / "wp-001.json", revision)
    write_json(root / CURRENT_POINTER, {"revision_id": "wp-001", "updated_at": "2026-08-31T00:00:00Z"})


def projection(label: str) -> dict:
    return {
        "route": label,
        "active_waypoint": label,
        "major_waypoints": [label],
        "ordering_rationale": "",
        "advancement_exit_conditions": "",
        "provisional_future": None,
        "route_uncertainty": "",
        "source_authority_references": [],
        "revision_reason": label,
    }


def workpath_digest(control_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((control_root / "workpaths").rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(control_root)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pdc-focus-decision-binding-") as temp:
        repo = Path(temp)
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "PDC Test")
        git(repo, "config", "user.email", "pdc@example.invalid")
        git(repo, "config", "core.autocrlf", "false")
        decisions = {
            "good.md": (
                "# PDC Control Decision\n"
                "- **Decision:** `FOCUS_SELECTION`\n"
                "- **Exact target:** `TASK-change`\n"
                "- **Expected prior Focus head:** `null`\n"
                "- **Bounded scope:** `TEST_ONLY`\n"
            ),
            "wrong-effect.md": (
                "# PDC Control Decision\n"
                "- **Decision:** `OTHER_EFFECT`\n"
                "- **Exact target:** `TASK-change`\n"
                "- **Expected prior Focus head:** `null`\n"
                "- **Bounded scope:** `TEST_ONLY`\n"
            ),
            "wrong-target.md": (
                "# PDC Control Decision\n"
                "- **Decision:** `FOCUS_SELECTION`\n"
                "- **Exact target:** `OTHER-change`\n"
                "- **Expected prior Focus head:** `null`\n"
                "- **Bounded scope:** `TEST_ONLY`\n"
            ),
        }
        for name, content in decisions.items():
            (repo / name).write_text(content, encoding="utf-8")
        git(repo, "add", *decisions)
        git(repo, "commit", "-m", "Focus decision binding fixtures")
        commit = git(repo, "rev-parse", "HEAD")

        def decision_ref(name: str) -> dict:
            path = repo / name
            return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

        validate_control_decision_ref_at_commit(
            repo,
            commit,
            decision_ref("good.md"),
            selected_change="TASK-change",
            required_effect="FOCUS_SELECTION",
            expected_prior_focus_selection_id=None,
        )
        for name, prior in (
            ("wrong-effect.md", None),
            ("wrong-target.md", None),
            ("good.md", "fs-" + "9" * 64),
        ):
            try:
                validate_control_decision_ref_at_commit(
                    repo,
                    commit,
                    decision_ref(name),
                    selected_change="TASK-change",
                    required_effect="FOCUS_SELECTION",
                    expected_prior_focus_selection_id=prior,
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Focus decision target/prior/effect mismatch was accepted")

    transition_owner = "tr:tr-" + "1" * 64
    null_id = projection_update_identity(transition_owner, "wp-001", 1, "MARK_STALE", None)
    assert null_id == projection_update_identity(transition_owner, "wp-001", 1, "MARK_STALE", None)
    explicit = {"path": ".ai-product/decision.md", "sha256": "2" * 64}
    explicit_id = projection_update_identity(
        "cd:" + "2" * 64, "wp-001", 1, "EXPLICIT_REBUILD", explicit
    )
    assert explicit_id != null_id
    assert explicit_id == projection_update_identity(
        "cd:" + "2" * 64,
        "wp-001",
        1,
        "EXPLICIT_REBUILD",
        {"sha256": "2" * 64, "path": ".ai-product/decision.md"},
    )
    validate_effect_pair("MARK_STALE", None)
    validate_effect_pair("EXPLICIT_REBUILD", explicit)
    for effect, ref in (("MARK_STALE", explicit), ("EXPLICIT_REBUILD", None)):
        try:
            validate_effect_pair(effect, ref)
        except ValueError:
            pass
        else:
            raise AssertionError("crossed Workpath effect/ref pair was accepted")
    try:
        validate_effect_pair(
            "EXPLICIT_REBUILD", {"path": "../escape", "sha256": "2" * 64}
        )
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe explicit Workpath reference was accepted")

    with tempfile.TemporaryDirectory(prefix="pdc-workpath-no-mutation-") as temp:
        control_root = Path(temp) / ".ai-product"
        authority_commit, explicit, _ = authority_fixture(control_root)
        initial(control_root)
        before = workpath_digest(control_root)
        for bad_ref, bad_projection in (
            ({"path": explicit["path"], "sha256": "0" * 64}, projection("explicit")),
            (explicit, projection("wrong-target")),
        ):
            try:
                publish_workpath_update(
                    control_root,
                    bad_projection,
                    effect="EXPLICIT_REBUILD",
                    explicit_control_decision=bad_ref,
                    authority_commit_sha=authority_commit,
                    owner_event_identity="cd:" + bad_ref["sha256"],
                    expected_prior_revision_id="wp-001",
                    repository_root=control_root.parent,
                )
            except ValueError:
                pass
            else:
                raise AssertionError("invalid explicit route authority was published")
            assert workpath_digest(control_root) == before
            assert not list((control_root / "transactions").glob("workpath-*.json"))

        other_workflow = {
            "schema_version": 2,
            "task_id": "TASK-2",
            "status": "implementing",
            "contract_digest": "b" * 64,
            "history": [],
        }
        other_transition, _ = apply_workflow_transition(
            other_workflow,
            to_status="ready_for_review",
            contract_digest="b" * 64,
            actor="controller",
            reason="non-Focus terminal",
            created_at="2026-08-31T00:00:02Z",
        )
        write_json(
            control_root / "changes" / "TASK-2-change" / "workflow-state.json",
            other_workflow,
        )
        try:
            publish_workpath_update(
                control_root,
                projection("stale"),
                effect="MARK_STALE",
                explicit_control_decision=None,
                authority_commit_sha=authority_commit,
                owner_event_identity="tr:" + other_transition["transition_id"],
                expected_prior_revision_id="wp-001",
                repository_root=control_root.parent,
                stale_reason="non-Focus owner",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("non-Focus terminal transition advanced the Workpath")
        assert workpath_digest(control_root) == before
        assert not list((control_root / "transactions").glob("workpath-*.json"))

    for phase in ("PREPARED", "CANDIDATE_MATERIALIZED", "POINTER_PUBLISHED"):
        with tempfile.TemporaryDirectory(prefix="pdc-workpath-recovery-") as temp:
            control_root = Path(temp) / ".ai-product"
            authority_commit, explicit, transition_owner = authority_fixture(control_root)
            initial(control_root)
            try:
                publish_workpath_update(
                    control_root,
                    projection("stale"),
                    effect="MARK_STALE",
                    explicit_control_decision=None,
                    authority_commit_sha=authority_commit,
                    owner_event_identity=transition_owner,
                    expected_prior_revision_id="wp-001",
                    repository_root=control_root.parent,
                    stale_reason="owner changed",
                    fault_after_phase=phase,
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError(f"fault after {phase} did not interrupt")
            recovered = publish_workpath_update(
                control_root,
                projection("stale"),
                effect="MARK_STALE",
                explicit_control_decision=None,
                authority_commit_sha=authority_commit,
                owner_event_identity=transition_owner,
                expected_prior_revision_id="wp-001",
                repository_root=control_root.parent,
                stale_reason="owner changed",
            )
            assert recovered["revision_id"] == "wp-002"
            assert json.loads((control_root / "workpaths" / CURRENT_POINTER).read_text())["revision_id"] == "wp-002"
            assert not list((control_root / "transactions").glob("workpath-*.json"))

    with tempfile.TemporaryDirectory(prefix="pdc-workpath-race-") as temp:
        control_root = Path(temp) / ".ai-product"
        authority_commit, explicit, transition_owner = authority_fixture(control_root)
        initial(control_root)
        try:
            publish_workpath_update(
                control_root,
                projection("stale"),
                effect="MARK_STALE",
                explicit_control_decision=None,
                authority_commit_sha=authority_commit,
                owner_event_identity=transition_owner,
                expected_prior_revision_id="wp-001",
                repository_root=control_root.parent,
                stale_reason="stale repair",
                fault_after_phase="PREPARED",
            )
        except RuntimeError:
            pass
        winner = publish_workpath_update(
            control_root,
            projection("explicit"),
            effect="EXPLICIT_REBUILD",
            explicit_control_decision=explicit,
            authority_commit_sha=authority_commit,
            owner_event_identity="cd:" + explicit["sha256"],
            expected_prior_revision_id="wp-001",
            repository_root=control_root.parent,
        )
        assert winner["effect"] == "EXPLICIT_REBUILD"
        try:
            publish_workpath_update(
                control_root,
                projection("stale"),
                effect="MARK_STALE",
                explicit_control_decision=None,
                authority_commit_sha=authority_commit,
                owner_event_identity=transition_owner,
                expected_prior_revision_id="wp-001",
                repository_root=control_root.parent,
                stale_reason="stale repair",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("stale repair overwrote a newer explicit route")
        pointer = json.loads((control_root / "workpaths" / CURRENT_POINTER).read_text())
        assert pointer["revision_id"] == winner["revision_id"]
        assert verify_record(control_root) == []
        assert not list((control_root / "transactions").glob("workpath-*.json"))
    print("WORKPATH PUBLISH RECOVERY SELF TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
