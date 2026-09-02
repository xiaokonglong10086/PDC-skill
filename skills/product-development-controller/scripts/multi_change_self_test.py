#!/usr/bin/env python3
"""Deterministic MC-01..MC-35 coverage for the multi-change coordination kernel."""

from __future__ import annotations

import argparse
import copy
import concurrent.futures
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import actual_repository_identity, digest_record, now_iso, sha256_json  # noqa: E402
from multi_change import (  # noqa: E402
    FailClosedError,
    build_focus_selection_record,
    focus_selection_lineage,
    validate_control_decision_ref_at_commit,
)

INIT = SCRIPT_DIR / "init_project.py"
FREEZE = SCRIPT_DIR / "freeze_contract.py"
TRANSITION = SCRIPT_DIR / "transition_task.py"
RESUME = SCRIPT_DIR / "resume_task.py"
CAPTURE = SCRIPT_DIR / "capture_implementation_snapshot.py"
RECONCILE = SCRIPT_DIR / "reconcile_project_state.py"
FOCUS = SCRIPT_DIR / "focus_change.py"
REFRESH = SCRIPT_DIR / "refresh_change_baseline.py"
REVISE = SCRIPT_DIR / "revise_contract.py"
VALIDATE_CONTRACT = SCRIPT_DIR / "validate_task_contract.py"
MULTI = SCRIPT_DIR / "multi_change.py"


def _focus_decision_material(target: str, prior_id: str | None) -> tuple[str, str]:
    prior_text = prior_id or "null"
    token = hashlib.sha256(f"{target}\0{prior_text}".encode("utf-8")).hexdigest()[:16]
    relative = f".ai-product/workpaths/control-decisions/self-test-focus-{token}.md"
    content = (
        "# PDC Control Decision\n"
        "- **Decision:** `FOCUS_SELECTION`\n"
        "- **Authorized effect:** `FOCUS_SELECTION`\n"
        f"- **Exact target:** `{target}`\n"
        f"- **Expected prior Focus head:** `{prior_text}`\n"
        f"- **Current owner basis:** `{prior_text if prior_id else 'UNFOCUSED'}`\n"
        "- **Bounded scope:** `SELF_TEST_ONLY`\n"
    )
    return relative, content


def prepare_focus_decision_chain(root: Path, targets: list[str]) -> None:
    """Activate future exact Focus decisions before a frozen baseline is established."""
    project_path = root / ".ai-product" / "project-state.json"
    project = read_json(project_path) if project_path.is_file() else {"history": []}
    lineage = focus_selection_lineage(project)
    if lineage["errors"] or lineage.get("schema_errors"):
        raise AssertionError("self-test Focus owner lineage is invalid")
    head = lineage.get("head")
    prior_id = head.get("focus_selection_id") if isinstance(head, dict) else None
    staged: list[str] = []
    for target in targets:
        relative, content = _focus_decision_material(target, prior_id)
        decision = root / relative
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(content, encoding="utf-8")
        digest = hashlib.sha256(decision.read_bytes()).hexdigest()
        simulated = build_focus_selection_record(
            selected_change=target,
            prior_focus_selection_id=prior_id,
            owner_event_identity="cd:" + digest,
            authority_commit_sha="0" * 40,
            control_decision_ref={"path": relative, "sha256": digest},
            actor="controller",
            reason="pre-activated self-test decision",
            created_at="2026-08-31T00:00:00Z",
        )
        prior_id = simulated["focus_selection_id"]
        staged.append(relative)
    if staged:
        git(root, "add", *staged)
        git(root, "commit", "-m", "pre-activate exact test Focus decisions")


def focus_authority_args(root: Path, target: str) -> tuple[str, ...]:
    project_path = root / ".ai-product" / "project-state.json"
    project = read_json(project_path) if project_path.is_file() else {"history": []}
    lineage = focus_selection_lineage(project)
    if lineage["errors"] or lineage.get("schema_errors"):
        raise AssertionError("self-test Focus owner lineage is invalid")
    head = lineage.get("head")
    if (
        isinstance(head, dict)
        and head.get("selected_change") == target
        and isinstance(head.get("control_decision_ref"), dict)
        and isinstance(head.get("authority_commit_sha"), str)
    ):
        ref = head["control_decision_ref"]
        return (
            "--authority-commit", head["authority_commit_sha"],
            "--control-decision-path", ref["path"],
            "--control-decision-sha256", ref["sha256"],
        )

    prior_id = head.get("focus_selection_id") if isinstance(head, dict) else None
    relative, content = _focus_decision_material(target, prior_id)
    decision = root / relative
    if decision.is_file():
        if decision.read_text(encoding="utf-8") != content:
            raise AssertionError("pre-activated Focus decision bytes differ")
        authority_commit = git(root, "rev-list", "-1", "HEAD", "--", relative)
        if not authority_commit:
            raise AssertionError("pre-activated Focus decision is not committed")
    else:
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(content, encoding="utf-8")
        git(root, "add", relative)
        git(root, "commit", "-m", f"test Focus decision {Path(relative).stem}")
        authority_commit = git(root, "rev-parse", "HEAD")
    return (
        "--authority-commit", authority_commit,
        "--control-decision-path", relative,
        "--control-decision-sha256", hashlib.sha256(decision.read_bytes()).hexdigest(),
    )


def run_script(path: Path, *args: str, expect: int | None = 0, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    if path == FOCUS and "--authority-commit" not in args:
        root = Path(args[args.index("--root") + 1])
        target = args[args.index("--change") + 1]
        args = (*args, *focus_authority_args(root, target))
    result = subprocess.run(
        [sys.executable, "-B", str(path), *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect is not None and result.returncode != expect:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expect}: {path.name} {' '.join(args)}\n{result.stdout}"
        )
    return result


def run_python(code: str, *args: str, expect: int = 0, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != expect:
        raise AssertionError(f"python probe returned {result.returncode}, expected {expect}\n{result.stdout}")
    return result


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(root), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed:\n{result.stdout}")
    return result.stdout.strip()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def workflow(name: str, task_id: str, status: str = "draft") -> dict:
    return {
        "schema_version": 2,
        "task_id": task_id,
        "status": status,
        "blocked_from": None,
        "blocked_reason": None,
        "blocked_at": None,
        "blocked_by": None,
        "contract_version": None,
        "contract_digest": None,
        "implementation_snapshot_digest": None,
        "review_commit_sha": None,
        "test_execution_record_digest": None,
        "updated_at": None,
        "history": [],
    }


def valid_contract(root: Path, baseline: str, task_id: str, slug: str, *, version: int = 1) -> dict:
    return {
        "schema_version": 3,
        "contract_version": version,
        "task_id": task_id,
        "title": f"Change {task_id}",
        "slug": slug,
        "baseline": {
            "repository": actual_repository_identity(root),
            "branch": "main",
            "sha": baseline,
        },
        "user_result": f"User-visible result for {task_id} remains deterministic and bounded.",
        "in_scope": ["change-owned source behavior"],
        "out_of_scope": ["parallel execution"],
        "allowed_files": ["src/app.txt", "src/extra.txt"],
        "forbidden_changes": ["no unrelated cleanup"],
        "acceptance_criteria": [
            {
                "id": "AC-1",
                "statement": "The bounded change result is present without unrelated behavior changes.",
                "test_ids": ["TEST-1"],
                "evidence_ids": ["EV-1"],
            }
        ],
        "required_tests": [
            {
                "id": "TEST-1",
                "type": "unit",
                "command": f'"{sys.executable}" -c "print(\'ok\')"',
                "expected": "exit code 0",
            }
        ],
        "required_evidence": [
            {"id": "EV-1", "type": "command_output", "description": "Focused passing output."}
        ],
        "manual_acceptance": [
            {
                "id": "UA-1",
                "criterion_ids": ["AC-1"],
                "setup": "Open the bounded feature.",
                "action": "Exercise the change.",
                "expected": "The bounded result is visible.",
            }
        ],
        "post_merge_checks": [
            {"id": "PM-1", "command": f'"{sys.executable}" -c "print(\'ok\')"', "expected_exit_code": 0}
        ],
        "global_stop_conditions": [
            "security_vulnerability", "authorization_or_tenant_bypass", "data_loss_or_corruption",
            "privacy_or_secret_exposure", "irreversible_migration_risk", "required_build_failure",
            "existing_core_flow_regression",
        ],
        "non_blocking_findings_policy": "Record optional work separately; it cannot change this boundary.",
        "test_first_exception": None,
    }


def new_repo(prefix: str = "pdc-mc-") -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
    temp = tempfile.TemporaryDirectory(prefix=prefix)
    root = Path(temp.name) / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "PDC Multi Change Test")
    git(root, "config", "user.email", "pdc-multi@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    (root / "src").mkdir()
    (root / "src" / "app.txt").write_text("baseline\n", encoding="utf-8")
    # Project scaffolding is tracked at baseline (Candidate paths), mirroring a real repo so
    # clean-base checks and v3 captures are not polluted by init-created untracked templates.
    (root / ".ai-product").mkdir(parents=True)
    for name in ("roadmap.md", "backlog.md", "project-facts.md", "codebase-facts.md"):
        (root / ".ai-product" / name).write_text("# baseline\n", encoding="utf-8")
    focus_targets = [
        f"{prefix}{index}-{slug}"
        for index in range(1, 36)
        for prefix, slug in (("A", "alpha"), ("B", "beta"), ("C", "gamma"))
    ] + ["A1TW-alpha", "RI-ai-product"]
    (root / ".ai-product" / "test-focus-control-decision.md").write_text(
        "# PDC Control Decision\n"
        "- **Decision:** authorize deterministic self-test Focus selections\n"
        + "\n".join(f"- {target}" for target in focus_targets)
        + "\n",
        encoding="utf-8",
    )
    git(root, "add", "src/app.txt", ".ai-product/roadmap.md", ".ai-product/backlog.md", ".ai-product/project-facts.md", ".ai-product/codebase-facts.md", ".ai-product/test-focus-control-decision.md")
    git(root, "commit", "-m", "baseline")
    return temp, root, git(root, "rev-parse", "HEAD")


def init_change(root: Path, task_id: str, slug: str) -> str:
    state_before = root / ".ai-product" / "project-state.json"
    had_focus = state_before.is_file() and read_json(state_before).get("current_change") is not None
    result = run_script(
        INIT, "--root", str(root), "--task-id", task_id, "--slug", slug,
        "--title", f"Change {task_id}", expect=0,
    )
    name = f"{task_id}-{slug}"
    if name not in result.stdout:
        raise AssertionError(f"init output did not identify {name}:\n{result.stdout}")
    project_path = root / ".ai-product" / "project-state.json"
    project = read_json(project_path)
    for key in project.get("capabilities", {}):
        project["capabilities"][key] = True
    write_json(project_path, project)
    if not had_focus:
        run_script(
            FOCUS,
            "--root", str(root),
            "--change", name,
            "--actor", "controller",
            "--reason", "Explicit self-test parked-Work selection",
        )
    return name


def change_path(root: Path, name: str) -> Path:
    return root / ".ai-product" / "changes" / name


def manual_change(root: Path, name: str, task_id: str, *, status: str = "draft", baseline: str | None = None) -> Path:
    path = change_path(root, name)
    path.mkdir(parents=True, exist_ok=True)
    wf = workflow(name, task_id, status=status)
    if baseline is not None:
        draft = valid_contract(root, baseline, task_id, name.split("-", 1)[1])
        write_json(path / "task-contract.draft.json", draft)
    if status != "draft":
        if baseline is None:
            baseline = git(root, "rev-parse", "main")
            draft = valid_contract(root, baseline, task_id, name.split("-", 1)[1])
            write_json(path / "task-contract.draft.json", draft)
        frozen = dict(draft)
        frozen.update(
            {
                "frozen_at": "2026-08-08T00:00:00Z",
                "approved_by": "controller-test",
                "source_draft_digest": sha256_json(draft),
                "repository_identity": actual_repository_identity(root),
                "repository_root": str(root.resolve()),
                "baseline_branch_tip_sha": git(root, "rev-parse", "main"),
            }
        )
        digest = sha256_json(frozen)
        write_json(path / "task-contract.draft.json", draft)
        write_json(path / "contracts" / "task-contract.v1.json", frozen)
        (path / "contracts" / "task-contract.v1.sha256").write_text(digest + "\n", encoding="utf-8")
        wf["contract_version"] = 1
        wf["contract_digest"] = digest
    write_json(path / "workflow-state.json", wf)
    return path


def freeze_named(root: Path, name: str, task_id: str, slug: str, baseline: str) -> dict:
    path = change_path(root, name)
    write_json(path / "task-contract.draft.json", valid_contract(root, baseline, task_id, slug))
    run_script(FREEZE, "--root", str(root), "--change", name, "--approved-by", "product-owner")
    return read_json(path / "contracts" / "task-contract.v1.json")


def set_project_focus(root: Path, name: str | None) -> None:
    project_path = root / ".ai-product" / "project-state.json"
    project = read_json(project_path)
    project["current_change"] = name
    if name is None:
        project["current_task_status"] = "unfocused"
        project["current_stage"] = "coordination"
        project["next_required_action"] = "resolve_next_product_priority"
        project["blocked_by"] = []
        project["requires_user_decision"] = True
    else:
        wf = read_json(change_path(root, name) / "workflow-state.json")
        project["current_task_status"] = wf["status"]
    write_json(project_path, project)


def set_status(root: Path, name: str, status: str, *, blocked_from: str | None = None, reason: str | None = None) -> None:
    path = change_path(root, name) / "workflow-state.json"
    wf = read_json(path)
    wf["status"] = status
    wf["blocked_from"] = blocked_from
    wf["blocked_reason"] = reason
    wf["blocked_at"] = "2026-08-08T00:00:00Z" if status == "blocked" else None
    wf["blocked_by"] = "external" if status == "blocked" else None
    write_json(path, wf)


def assert_unchanged(path: Path, before: bytes) -> None:
    after = path.read_bytes()
    if after != before:
        raise AssertionError(f"file changed unexpectedly: {path}")


def mc01() -> None:
    temp, root, _ = new_repo("mc01-")
    try:
        a = init_change(root, "A1", "alpha")
        project_path = root / ".ai-product" / "project-state.json"
        workflow_path = change_path(root, a) / "workflow-state.json"
        project_before = project_path.read_bytes()
        workflow_before = workflow_path.read_bytes()
        b = init_change(root, "B1", "beta")
        project = read_json(project_path)
        assert project["current_change"] == a
        assert change_path(root, b).is_dir()
        assert_unchanged(workflow_path, workflow_before)
        # Only navigation-neutral metadata may differ; Focus and focused projection must not.
        before = json.loads(project_before)
        for key in ("current_change", "current_task_status", "current_stage", "next_required_action", "blocked_by", "requires_user_decision"):
            assert project[key] == before[key]
    finally:
        temp.cleanup()


def mc02() -> None:
    temp, root, baseline = new_repo("mc02-")
    try:
        a = init_change(root, "A2", "alpha")
        freeze_named(root, a, "A2", "alpha", baseline)
        b = "B2-beta"
        manual_change(root, b, "B2", status="draft", baseline=baseline)
        b_workflow = change_path(root, b) / "workflow-state.json"
        before = b_workflow.read_bytes()
        result = run_script(FREEZE, "--root", str(root), "--change", b, "--approved-by", "controller", expect=None)
        assert result.returncode != 0 and "focus" in result.stdout.lower()
        assert_unchanged(b_workflow, before)
    finally:
        temp.cleanup()


def mc03() -> None:
    temp, root, _ = new_repo("mc03-")
    try:
        a = init_change(root, "A3", "alpha")
        b = "B3-beta"
        manual_change(root, b, "B3")
        code = (
            "import sys; from pathlib import Path; "
            f"sys.path.insert(0, {str(SCRIPT_DIR)!r}); "
            "from multi_change import assert_focused_change; "
            "assert_focused_change(Path(sys.argv[1]) / '.ai-product', sys.argv[2])"
        )
        result = run_python(code, str(root), b, expect=1)
        assert "focus" in result.stdout.lower()
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == a
    finally:
        temp.cleanup()


def mc04() -> None:
    temp, root, baseline = new_repo("mc04-")
    try:
        a = init_change(root, "A4", "alpha")
        prepare_focus_decision_chain(root, ["B4-beta"])
        freeze_named(root, a, "A4", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "agent")
        b = "B4-beta"
        manual_change(root, b, "B4")
        result = run_script(FOCUS, "--root", str(root), "--change", b, "--actor", "controller", expect=None)
        assert result.returncode != 0 and "park" in result.stdout.lower()
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == a
    finally:
        temp.cleanup()


def mc05() -> None:
    temp, root, baseline = new_repo("mc05-")
    try:
        a = init_change(root, "A5", "alpha")
        prepare_focus_decision_chain(root, ["B5-beta"])
        freeze_named(root, a, "A5", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external wait")
        b = "B5-beta"
        manual_change(root, b, "B5")
        run_script(FOCUS, "--root", str(root), "--change", b, "--actor", "controller")
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == b
    finally:
        temp.cleanup()


def mc06() -> None:
    temp, root, baseline = new_repo("mc06-")
    try:
        a = init_change(root, "A6", "alpha")
        prepare_focus_decision_chain(root, ["B6-beta"])
        freeze_named(root, a, "A6", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "agent")
        (root / "src" / "app.txt").write_text("partial A\n", encoding="utf-8")
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external wait")
        b = "B6-beta"
        manual_change(root, b, "B6")
        before = (root / "src" / "app.txt").read_text(encoding="utf-8")
        result = run_script(FOCUS, "--root", str(root), "--change", b, "--actor", "controller", expect=None)
        assert result.returncode != 0 and "snapshot" in result.stdout.lower()
        assert (root / "src" / "app.txt").read_text(encoding="utf-8") == before
    finally:
        temp.cleanup()


def _snapshot_blocked_repo(
    prefix: str,
    task: str,
    *,
    focus_chain: list[str] | None = None,
) -> tuple[tempfile.TemporaryDirectory[str], Path, str, str, str]:
    temp, root, baseline = new_repo(prefix)
    a = init_change(root, task, "alpha")
    prepare_focus_decision_chain(root, focus_chain or [])
    freeze_named(root, a, task, "alpha", baseline)
    run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "agent")
    content = f"implementation {task}\n"
    (root / "src" / "app.txt").write_text(content, encoding="utf-8")
    run_script(CAPTURE, "--root", str(root), "--change", a)
    run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external wait")
    return temp, root, baseline, a, content


def mc07() -> None:
    temp, root, _, a, content = _snapshot_blocked_repo(
        "mc07-", "A7", focus_chain=["B7-beta", "A7-alpha"]
    )
    try:
        b = "B7-beta"
        manual_change(root, b, "B7")
        run_script(FOCUS, "--root", str(root), "--change", b, "--actor", "controller")
        assert (root / "src" / "app.txt").read_text(encoding="utf-8") == "baseline\n"
        run_script(FOCUS, "--root", str(root), "--change", a, "--actor", "controller")
        assert (root / "src" / "app.txt").read_text(encoding="utf-8") == "baseline\n"
        run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "dependency resolved")
        assert (root / "src" / "app.txt").read_text(encoding="utf-8") == content
        assert read_json(change_path(root, a) / "workflow-state.json")["status"] == "implementing"
    finally:
        temp.cleanup()


def mc08() -> None:
    temp, root, baseline = new_repo("mc08-")
    try:
        a = init_change(root, "A8", "alpha")
        prepare_focus_decision_chain(root, ["B8-beta"])
        freeze_named(root, a, "A8", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external wait")
        b = "B8-beta"
        manual_change(root, b, "B8")
        unrelated = root / "src" / "unrelated.txt"
        unrelated.write_text("user work\n", encoding="utf-8")
        result = run_script(FOCUS, "--root", str(root), "--change", b, "--actor", "controller", expect=None)
        assert result.returncode != 0
        assert unrelated.read_text(encoding="utf-8") == "user work\n"
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == a
    finally:
        temp.cleanup()


def mc09() -> None:
    temp, root, baseline = new_repo("mc09-")
    try:
        a = init_change(root, "A9", "alpha")
        prepare_focus_decision_chain(root, ["B9-beta"])
        freeze_named(root, a, "A9", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external wait")
        (root / "src" / "app.txt").write_text("committed unfinished A\n", encoding="utf-8")
        git(root, "add", "src/app.txt")
        git(root, "commit", "-m", "unfinished A side effect")
        b = "B9-beta"
        manual_change(root, b, "B9")
        result = run_script(FOCUS, "--root", str(root), "--change", b, "--actor", "controller", expect=None)
        assert result.returncode != 0
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == a
    finally:
        temp.cleanup()


def mc10() -> None:
    temp, root, baseline = new_repo("mc10-")
    try:
        a = init_change(root, "A10", "alpha")
        freeze_named(root, a, "A10", "alpha", baseline)
        git(root, "checkout", "-b", "side")
        (root / "src" / "app.txt").write_text("side branch\n", encoding="utf-8")
        git(root, "add", "src/app.txt")
        git(root, "commit", "-m", "side branch")
        result = run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "agent", expect=None)
        assert result.returncode != 0 and ("execution" in result.stdout.lower() or "branch" in result.stdout.lower())
        assert read_json(change_path(root, a) / "workflow-state.json")["status"] == "ready_for_implementation"
    finally:
        temp.cleanup()


def mc11() -> None:
    temp, root, baseline = new_repo("mc11-")
    try:
        a = init_change(root, "A11", "alpha")
        freeze_named(root, a, "A11", "alpha", baseline)
        project_path = root / ".ai-product" / "project-state.json"
        project = read_json(project_path)
        project["current_change"] = None
        project["current_task_status"] = "unfocused"
        write_json(project_path, project)
        run_script(RECONCILE, "--root", str(root), "--repair")
        assert read_json(project_path)["current_change"] == a
    finally:
        temp.cleanup()


def mc12() -> None:
    temp, root, baseline = new_repo("mc12-")
    try:
        a = init_change(root, "A12", "alpha")
        freeze_named(root, a, "A12", "alpha", baseline)
        set_status(root, a, "blocked", blocked_from="ready_for_implementation", reason="wait")
        b = "B12-beta"
        manual_change(root, b, "B12", status="ready_for_implementation", baseline=baseline)
        set_project_focus(root, a)
        before = (root / ".ai-product" / "project-state.json").read_bytes()
        result = run_script(RECONCILE, "--root", str(root), "--repair", expect=None)
        assert result.returncode != 0 and "focus" in result.stdout.lower()
        assert_unchanged(root / ".ai-product" / "project-state.json", before)
    finally:
        temp.cleanup()


def mc13() -> None:
    temp, root, baseline = new_repo("mc13-")
    try:
        a = init_change(root, "A13", "alpha")
        freeze_named(root, a, "A13", "alpha", baseline)
        b = "B13-beta"
        manual_change(root, b, "B13", status="ready_for_implementation", baseline=baseline)
        result = run_script(RECONCILE, "--root", str(root), "--repair", expect=None)
        assert result.returncode != 0 and "multiple" in result.stdout.lower()
    finally:
        temp.cleanup()


def mc14() -> None:
    temp, root, c1 = new_repo("mc14-")
    try:
        (root / "src" / "extra.txt").write_text("branch tip advance before freeze\n", encoding="utf-8")
        git(root, "add", "src/extra.txt")
        git(root, "commit", "-m", "pre-freeze branch tip")
        c2 = git(root, "rev-parse", "HEAD")
        a = init_change(root, "A14", "alpha")
        frozen = freeze_named(root, a, "A14", "alpha", c1)
        assert frozen["baseline_branch_tip_sha"] == git(root, "rev-parse", "main")
        assert frozen["baseline"]["sha"] == c1
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "wait")
        run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resume")
        assert read_json(change_path(root, a) / "workflow-state.json")["status"] == "ready_for_implementation"
    finally:
        temp.cleanup()


def mc15() -> None:
    temp, root, baseline = new_repo("mc15-")
    try:
        a = init_change(root, "A15", "alpha")
        freeze_named(root, a, "A15", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "wait")
        (root / "src" / "extra.txt").write_text("new base\n", encoding="utf-8")
        git(root, "add", "src/extra.txt")
        git(root, "commit", "-m", "advance main")
        result = run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resume", expect=None)
        assert result.returncode != 0 and "stale" in result.stdout.lower()
        assert read_json(change_path(root, a) / "workflow-state.json")["status"] == "blocked"
    finally:
        temp.cleanup()


def mc16() -> None:
    temp, root, baseline = new_repo("mc16-")
    try:
        a = init_change(root, "A16", "alpha")
        freeze_named(root, a, "A16", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "wait")
        git(root, "checkout", "-b", "rewrite", baseline)
        (root / "src" / "app.txt").write_text("divergent rewrite\n", encoding="utf-8")
        git(root, "add", "src/app.txt")
        git(root, "commit", "-m", "rewrite")
        rewritten = git(root, "rev-parse", "HEAD")
        git(root, "branch", "-f", "main", rewritten)
        git(root, "checkout", "main")
        result = run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resume", expect=None)
        assert result.returncode != 0 and "stale" in result.stdout.lower()
    finally:
        temp.cleanup()


def _stale_blocked(root: Path, baseline: str, task: str) -> str:
    a = init_change(root, task, "alpha")
    freeze_named(root, a, task, "alpha", baseline)
    run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external dependency")
    (root / "src" / "extra.txt").write_text(f"new base {task}\n", encoding="utf-8")
    git(root, "add", "src/extra.txt")
    git(root, "commit", "-m", f"advance base {task}")
    return a


def mc17() -> None:
    temp, root, baseline = new_repo("mc17-")
    try:
        a = _stale_blocked(root, baseline, "A17")
        p = change_path(root, a)
        old_bytes = (p / "contracts" / "task-contract.v1.json").read_bytes()
        old = read_json(p / "contracts" / "task-contract.v1.json")
        run_script(REFRESH, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "baseline changed", "--blocker-resolved")
        assert_unchanged(p / "contracts" / "task-contract.v1.json", old_bytes)
        new = read_json(p / "contracts" / "task-contract.v2.json")
        preserved = [
            "task_id", "title", "slug", "user_result", "in_scope", "out_of_scope", "allowed_files",
            "forbidden_changes", "acceptance_criteria", "required_tests", "required_evidence", "manual_acceptance",
            "post_merge_checks", "global_stop_conditions", "non_blocking_findings_policy", "test_first_exception",
        ]
        for key in preserved:
            assert new[key] == old[key], key
        assert new["contract_version"] == 2
        assert new["baseline"]["sha"] == git(root, "rev-parse", "main")
    finally:
        temp.cleanup()


def mc18() -> None:
    temp, root, baseline = new_repo("mc18-")
    try:
        a = _stale_blocked(root, baseline, "A18")
        wf_path = change_path(root, a) / "workflow-state.json"
        wf = read_json(wf_path)
        wf["implementation_snapshot_digest"] = "a" * 64
        wf["review_commit_sha"] = "b" * 40
        wf["test_execution_record_digest"] = "c" * 64
        write_json(wf_path, wf)
        run_script(REFRESH, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "baseline changed", "--blocker-resolved")
        wf = read_json(wf_path)
        assert wf["implementation_snapshot_digest"] is None
        assert wf["review_commit_sha"] is None
        assert wf["test_execution_record_digest"] is None
        assert wf["contract_version"] == 2
    finally:
        temp.cleanup()


def mc19() -> None:
    temp, root, baseline = new_repo("mc19-")
    try:
        a = _stale_blocked(root, baseline, "A19")
        run_script(REFRESH, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "baseline changed")
        wf = read_json(change_path(root, a) / "workflow-state.json")
        assert wf["status"] == "blocked"
        assert wf["blocked_from"] == "ready_for_implementation"
        assert wf["blocked_reason"] == "external dependency"
    finally:
        temp.cleanup()


def mc20() -> None:
    temp, root, baseline = new_repo("mc20-")
    try:
        a = _stale_blocked(root, baseline, "A20")
        run_script(REFRESH, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "technical revalidation", "--blocker-resolved")
        project = read_json(root / ".ai-product" / "project-state.json")
        assert project["requires_user_decision"] is False
        assert project["next_required_action"] == "coding_agent_implement"
    finally:
        temp.cleanup()


def mc21() -> None:
    temp, root, _ = new_repo("mc21-")
    try:
        a = init_change(root, "A21", "alpha")
        b = "B21-beta"
        c = "C21-gamma"
        manual_change(root, b, "B21")
        manual_change(root, c, "C21")
        code = (
            "import json,sys; from pathlib import Path; "
            f"sys.path.insert(0, {str(SCRIPT_DIR)!r}); "
            "from multi_change import project_after_closure; "
            "p=json.load(open(Path(sys.argv[1])/'.ai-product/project-state.json')); "
            "a=project_after_closure(Path(sys.argv[1])/'.ai-product', p, sys.argv[2]); "
            "print(json.dumps(a))"
        )
        result = run_python(code, str(root), a)
        projected = json.loads(result.stdout.strip())
        assert projected["current_change"] is None
        assert projected["current_task_status"] == "unfocused"
        assert projected["current_stage"] == "coordination"
    finally:
        temp.cleanup()


def mc22() -> None:
    temp, root, _ = new_repo("mc22-")
    try:
        a = init_change(root, "A22", "alpha")
        b = "B22-beta"
        manual_change(root, b, "B22")
        set_project_focus(root, None)
        run_script(FOCUS, "--root", str(root), "--change", b, "--actor", "controller")
        project = read_json(root / ".ai-product" / "project-state.json")
        assert project["current_change"] == b
        assert project["requires_user_decision"] is False
        assert change_path(root, a).is_dir()
    finally:
        temp.cleanup()


def mc23() -> None:
    temp, root, _ = new_repo("mc23-")
    try:
        a = init_change(root, "A23", "alpha")
        b = "B23-beta"
        c = "C23-gamma"
        manual_change(root, b, "B23")
        manual_change(root, c, "C23")
        set_project_focus(root, None)
        run_script(RECONCILE, "--root", str(root), "--repair")
        project = read_json(root / ".ai-product" / "project-state.json")
        assert project["current_change"] == a
        assert project["current_task_status"] == "draft"
        assert project["requires_user_decision"] is False
        run_script(FOCUS, "--root", str(root), "--change", c, "--actor", "controller")
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == c
        assert change_path(root, a).is_dir()
    finally:
        temp.cleanup()


def mc24() -> None:
    temp, root, _ = new_repo("mc24-")
    try:
        a = init_change(root, "A24", "alpha")
        b = init_change(root, "B24", "beta")
        project_path = root / ".ai-product" / "project-state.json"
        before_project = project_path.read_bytes()
        before_b = (change_path(root, b) / "workflow-state.json").read_bytes()
        result = run_script(
            INIT, "--root", str(root), "--task-id", "B24", "--slug", "beta", "--title", "Replacement",
            "--replace-existing", "--confirm-replace", "REPLACE_AI_PRODUCT_TEMPLATES", expect=None,
        )
        assert result.returncode != 0
        assert_unchanged(project_path, before_project)
        assert_unchanged(change_path(root, b) / "workflow-state.json", before_b)
        assert read_json(project_path)["current_change"] == a
    finally:
        temp.cleanup()


def mc25() -> None:
    temp, root, baseline = new_repo("mc25-")
    try:
        a = init_change(root, "A25", "alpha")
        b = "B25-beta"
        p = manual_change(root, b, "B25", status="ready_for_implementation", baseline=baseline)
        before_project = (root / ".ai-product" / "project-state.json").read_bytes()
        before_b = (p / "workflow-state.json").read_bytes()
        run_script(VALIDATE_CONTRACT, str(p / "contracts" / "task-contract.v1.json"), "--frozen")
        assert_unchanged(root / ".ai-product" / "project-state.json", before_project)
        assert_unchanged(p / "workflow-state.json", before_b)
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == a
    finally:
        temp.cleanup()


def mc26() -> None:
    temp, root, baseline = new_repo("mc26-")
    try:
        a = init_change(root, "A26", "alpha")
        freeze_named(root, a, "A26", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "agent")
        (root / "src" / "app.txt").write_text("single-change implementation\n", encoding="utf-8")
        run_script(CAPTURE, "--root", str(root), "--change", a)
        assert read_json(change_path(root, a) / "workflow-state.json")["review_commit_sha"]
        assert read_json(root / ".ai-product" / "project-state.json")["current_change"] == a
    finally:
        temp.cleanup()


def mc27() -> None:
    interface_text = (SCRIPT_DIR.parent / "references" / "product-owner-interface.md").read_text(encoding="utf-8").lower()
    assert "one" in interface_text and "next action" in interface_text
    assert "parked" in interface_text or "停" in interface_text
    assert "git" in interface_text  # Git is discussed only as hidden technical detail in the authority text.
    code = (
        "import json,sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(SCRIPT_DIR)!r}); "
        "from multi_change import unfocused_projection; "
        "print(json.dumps(unfocused_projection({}, ['a','b'])))"
    )
    result = run_python(code)
    projected = json.loads(result.stdout.strip())
    assert projected["current_task_status"] == "unfocused"
    assert projected["requires_user_decision"] is True


def _post_snapshot_advanced_blocked(root: Path, task_id: str) -> tuple[str, str, Path, str]:
    """Build the real post-snapshot blocked scenario: freeze -> implementing -> capture an
    exact snapshot -> blocked(blocked_from=integration_ready) -> reviewed source committed to
    the frozen branch -> Controller-only .ai-product commit. Returns (frozen_tip, current_tip,
    change_path, change_name)."""
    a = init_change(root, task_id, "alpha")
    baseline = git(root, "rev-parse", "main")
    freeze_named(root, a, task_id, "alpha", baseline)
    run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "agent")
    content = f"implementation {task_id}\n"
    (root / "src" / "app.txt").write_text(content, encoding="utf-8")
    run_script(CAPTURE, "--root", str(root), "--change", a)
    frozen = read_json(change_path(root, a) / "contracts" / "task-contract.v1.json")
    frozen_tip = frozen["baseline_branch_tip_sha"]
    set_status(root, a, "blocked", blocked_from="integration_ready", reason="external wait")
    git(root, "add", "src/app.txt")
    git(root, "commit", "-m", "integrate reviewed source")
    # Controller lifecycle bookkeeping lives in a reserved namespace so it does not appear as an
    # un-scoped Candidate change under identity-policy v1 (MC-28 simulates a Controller-only commit).
    (root / ".ai-product" / "transactions").mkdir(parents=True, exist_ok=True)
    (root / ".ai-product" / "transactions" / "control-note.txt").write_text("controller lifecycle record\n", encoding="utf-8")
    git(root, "add", ".ai-product/transactions/control-note.txt")
    git(root, "commit", "-m", "controller lifecycle record")
    current_tip = git(root, "rev-parse", "HEAD")
    return frozen_tip, current_tip, change_path(root, a), a


def _write_complete_integration_evidence(root: Path, path: Path) -> None:
    """Write a self-consistent integration-evidence chain for the fixture's real
    CAPTURE-produced snapshot and frozen v1 contract (v3 semantics): test-execution-record +
    review-tests log, PASS review, accepted acceptance, and a valid integration record whose
    merge commit is the fixture's "integrate reviewed source" commit (HEAD~1 at helper time,
    after the Controller-only lifecycle commit). Mirrors the recovery self-test Fixture so the
    exclusive resume branch accepts the Work and reaches its history checks."""
    contract = read_json(path / "contracts" / "task-contract.v1.json")
    contract_digest = (path / "contracts" / "task-contract.v1.sha256").read_text(encoding="utf-8").strip()
    snapshot = read_json(path / "implementation-snapshot.json")
    task_id = contract["task_id"]
    baseline = contract["baseline"]["sha"]
    review_commit = snapshot["review_commit_sha"]
    merge_sha = git(root, "rev-parse", "HEAD~1")
    tip = git(root, "rev-parse", "HEAD")
    identity = actual_repository_identity(root)
    branch = "main"
    frozen_test = contract["required_tests"][0]
    test_id = frozen_test["id"]

    run_dir = "evidence/review-tests/run-1"
    ter_log = b"ok\n"
    status_text = git(root, "status", "--porcelain").encode()
    index_bytes = (root / ".git" / "index").read_bytes()
    started = now_iso()
    t_start = now_iso()
    t_end = now_iso()
    completed = now_iso()
    ter = {
        "schema_version": 1,
        "task_id": task_id,
        "contract_version": 1,
        "contract_digest": contract_digest,
        "implementation_snapshot_digest": snapshot["snapshot_digest"],
        "review_commit_sha": review_commit,
        "baseline_sha": baseline,
        "executor": "test-executor",
        "started_at": started,
        "completed_at": completed,
        "timeout_seconds": 60,
        "isolation": {
            "strategy": "detached_temporary_git_worktree",
            "review_commit_sha": review_commit,
            "cleanup": "removed",
            "security_boundary": "git_isolation_not_security_sandbox",
        },
        "main_worktree": {
            "branch_before": branch,
            "branch_after": branch,
            "head_before": review_commit,
            "head_after": review_commit,
            "status_before_sha256": hashlib.sha256(status_text).hexdigest(),
            "status_after_sha256": hashlib.sha256(status_text).hexdigest(),
            "index_before_sha256": hashlib.sha256(index_bytes).hexdigest(),
            "index_after_sha256": hashlib.sha256(index_bytes).hexdigest(),
            "preserved": True,
        },
        "tests": [{
            "id": test_id,
            "type": frozen_test["type"],
            "command": frozen_test["command"],
            "expected": frozen_test["expected"],
            "expected_exit_code": 0,
            "started_at": t_start,
            "completed_at": t_end,
            "actual_exit_code": 0,
            "result": "passed",
            "blocked_reason": None,
            "log_path": f"{run_dir}/{test_id}.log",
            "log_size": len(ter_log),
            "log_sha256": hashlib.sha256(ter_log).hexdigest(),
        }],
        "runner_blockers": [],
        "overall_status": "passed",
    }
    ter["record_digest"] = digest_record(ter, "record_digest")

    review = {
        "schema_version": 4,
        "task_id": task_id,
        "contract_version": 1,
        "contract_digest": contract_digest,
        "implementation_snapshot_digest": snapshot["snapshot_digest"],
        "review_commit_sha": review_commit,
        "baseline_sha": baseline,
        "test_execution_record_digest": ter["record_digest"],
        "reviewed_at": now_iso(),
        "reviewer": "controller",
        "verdict": "PASS",
        "checked_criteria": [{"id": "AC-1", "result": "satisfied", "evidence": "test fixture"}],
        "tests_checked": [test_id],
        "evidence_checked": ["EV-1"],
        "blocking_findings": [],
        "evidence_missing": [],
        "non_blocking_findings": [],
    }
    acceptance = {
        "schema_version": 2,
        "task_id": task_id,
        "contract_version": 1,
        "contract_digest": contract_digest,
        "implementation_snapshot_digest": snapshot["snapshot_digest"],
        "review_commit_sha": review_commit,
        "decision": "accepted",
        "recorded_at": now_iso(),
        "tester": "product-owner",
        "environment": "test fixture",
        "scenarios": [{"id": "UA-1", "result": "passed", "notes": "test"}],
        "notes": "test fixture",
    }
    pm_log = b"ok\n"
    record = {
        "schema_version": 3,
        "task_id": task_id,
        "contract_version": 1,
        "contract_digest": contract_digest,
        "implementation_snapshot_digest": snapshot["snapshot_digest"],
        "review_commit_sha": review_commit,
        "review_report_digest": sha256_json(review),
        "acceptance_record_digest": sha256_json(acceptance),
        "repository_identity": identity,
        "repository_root": str(root),
        "base_branch": branch,
        "base_branch_tip_sha": tip,
        "merge_commit_sha": merge_sha,
        "pull_request": {"provider": None, "url": None, "number": None},
        "ci": {"status": "success", "verification": "controller_executed", "provider": "local",
               "workflow": "test", "url": None, "run_id": None, "verified_by": "controller",
               "verified_at": now_iso()},
        "post_merge_verification": [{
            "id": "PM-1", "command": contract["post_merge_checks"][0]["command"],
            "expected_exit_code": 0, "actual_exit_code": 0,
            "stdout_sha256": hashlib.sha256(pm_log).hexdigest(),
            "log_path": "evidence/post-merge/PM-1.log",
            "executed_at": now_iso(), "executor": "controller",
        }],
        "release": {"reference": None, "rollback": "git revert " + merge_sha},
        "closure_assurance": "local_verified",
        "local_reviewed_content_reconstructed": True,
        "local_identity_evidence": {
            "reviewed_changed_file_set_reconstructed": True,
            "review_tree_sha_reconstructed": True,
            "canonical_identity_digest_reconstructed": True,
        },
        "remote_durability_verified": False,
        "remote_durability_evidence": {"status": "unverified", "reason": "test fixture"},
        "recorded_at": now_iso(),
    }
    record["record_digest"] = digest_record(record, "record_digest")

    write_json(path / "test-execution-record.json", ter)
    write_json(path / "review-report.json", review)
    write_json(path / "acceptance-record.json", acceptance)
    write_json(path / "integration-record.json", record)
    (path / "evidence" / "review-tests" / "run-1").mkdir(parents=True, exist_ok=True)
    (path / "evidence" / "review-tests" / "run-1" / f"{test_id}.log").write_bytes(ter_log)
    (path / "evidence" / "post-merge").mkdir(parents=True, exist_ok=True)
    (path / "evidence" / "post-merge" / "PM-1.log").write_bytes(pm_log)
    wf = read_json(path / "workflow-state.json")
    wf["test_execution_record_digest"] = ter["record_digest"]
    write_json(path / "workflow-state.json", wf)


def mc28_post_snapshot_advanced_resume() -> None:
    """MC-28 (v3 GREEN): a blocked post-snapshot Work with COMPLETE integration evidence
    (PASS review, accepted acceptance, valid integration record) resumes through the
    EXCLUSIVE evidence-based branch to integration_ready after main legitimately advanced
    past the frozen baseline tip (reviewed source integration + Controller control commits),
    preserving all assurance bindings and creating no new contract version. Incomplete
    evidence FAILS CLOSED (recovery CASE-5 A-D / MC-32)."""
    temp, root, _ = new_repo("mc28-")
    try:
        frozen_tip, current_tip, path, a = _post_snapshot_advanced_blocked(root, "A28")
        assert current_tip != frozen_tip
        _write_complete_integration_evidence(root, path)
        wf_before = read_json(path / "workflow-state.json")
        snapshot_before = read_json(path / "implementation-snapshot.json")
        run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "blocker resolved")
        wf = read_json(path / "workflow-state.json")
        assert wf["status"] == "integration_ready"
        assert wf["blocked_from"] is None
        assert wf["implementation_snapshot_digest"] == wf_before["implementation_snapshot_digest"]
        assert wf["review_commit_sha"] == wf_before["review_commit_sha"]
        assert wf["contract_version"] == 1
        assert not (path / "contracts" / "task-contract.v2.json").exists()
        assert read_json(path / "implementation-snapshot.json")["snapshot_digest"] == snapshot_before["snapshot_digest"]
        assert (root / "src" / "app.txt").read_text(encoding="utf-8") == f"implementation A28\n"
    finally:
        temp.cleanup()


def mc29_r1_worktree_irrelevant_on_evidence_resume() -> None:
    """R1 (v3 semantics): integration_ready resume validates MAIN HISTORY evidence, not the
    worktree. A later commit touching only an unrelated source file cannot block an
    evidence-complete resume; the reviewed bytes already live in main history and the
    current-tip preservation check tolerates unrelated-file evolution (recovery H)."""
    temp, root, _ = new_repo("mc29-")
    try:
        _, _, path, a = _post_snapshot_advanced_blocked(root, "A29")
        _write_complete_integration_evidence(root, path)
        (root / "src" / "extra.txt").write_text("extra source\n", encoding="utf-8")
        git(root, "add", "src/extra.txt")
        git(root, "commit", "-m", "unrelated source beyond reviewed scope")
        run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resolve")
        assert read_json(path / "workflow-state.json")["status"] == "integration_ready"
    finally:
        temp.cleanup()


def mc30_r2_reviewed_main_tamper_fails_closed() -> None:
    """R2 (v3 semantics): a later commit on main that MUTATES a reviewed file FAILS CLOSED —
    the current base-branch tip preservation check rejects it and the Work stays blocked.
    This is the integration_ready equivalent of the old worktree-mutation rejection."""
    temp, root, _ = new_repo("mc30-")
    try:
        _, _, path, a = _post_snapshot_advanced_blocked(root, "A30")
        _write_complete_integration_evidence(root, path)
        (root / "src" / "app.txt").write_text("mutated implementation A30\n", encoding="utf-8")
        git(root, "add", "src/app.txt")
        git(root, "commit", "-m", "mutate reviewed bytes in main history")
        result = run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resolve", expect=None)
        assert result.returncode != 0
        assert "differs from reviewed identity" in result.stdout
        assert read_json(path / "workflow-state.json")["status"] == "blocked"
    finally:
        temp.cleanup()


def mc31_r3_diverged_history_rejected() -> None:
    """R3 (v3 semantics): a branch tip that is not a descendant of the frozen baseline tip
    (history rewrite/divergence) must be rejected on evidence resume, even when the reviewed
    content bytes are intact."""
    temp, root, _ = new_repo("mc31-")
    try:
        _, _, path, a = _post_snapshot_advanced_blocked(root, "A31")
        _write_complete_integration_evidence(root, path)
        tree = git(root, "rev-parse", "HEAD^{tree}")
        rewritten = git(root, "commit-tree", tree, "-m", "rewritten root commit")
        git(root, "update-ref", "refs/heads/main", rewritten)
        git(root, "reset", "--hard")
        result = run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resolve", expect=None)
        assert result.returncode != 0
        assert "not a descendant of the frozen baseline tip" in result.stdout
        assert read_json(path / "workflow-state.json")["status"] == "blocked"
    finally:
        temp.cleanup()


def mc32_r4_broken_binding_rejected() -> None:
    """R4: a broken workflow snapshot binding must be rejected on resume even with complete
    integration evidence (the evidence gate passes, the snapshot binding check fails closed)."""
    temp, root, _ = new_repo("mc32-")
    try:
        _, _, path, a = _post_snapshot_advanced_blocked(root, "A32")
        _write_complete_integration_evidence(root, path)
        wf = read_json(path / "workflow-state.json")
        wf["implementation_snapshot_digest"] = "f" * 64
        write_json(path / "workflow-state.json", wf)
        result = run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resolve", expect=None)
        assert result.returncode != 0
        assert "workflow implementation snapshot digest mismatch" in result.stdout
        assert read_json(path / "workflow-state.json")["status"] == "blocked"
    finally:
        temp.cleanup()


def mc33_r5_pre_snapshot_stale_rejected() -> None:
    """R5: a pre-snapshot stale baseline (blocked_from=ready_for_implementation, no snapshot
    assurance) must still be rejected, preserving the existing technical baseline refresh path."""
    temp, root, baseline = new_repo("mc33-")
    try:
        a = _stale_blocked(root, baseline, "A33")
        result = run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resolve", expect=None)
        assert result.returncode != 0
        assert "stale_baseline" in result.stdout
    finally:
        temp.cleanup()


def mc34_r6_exact_tip_resume() -> None:
    """R6: an ordinary exact-tip post-snapshot resume without branch advancement continues to pass."""
    temp, root, _ = new_repo("mc34-")
    try:
        a = init_change(root, "A34", "alpha")
        baseline = git(root, "rev-parse", "main")
        freeze_named(root, a, "A34", "alpha", baseline)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "agent")
        (root / "src" / "app.txt").write_text("implementation A34\n", encoding="utf-8")
        run_script(CAPTURE, "--root", str(root), "--change", a)
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external wait")
        run_script(RESUME, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "resolved")
        wf = read_json(change_path(root, a) / "workflow-state.json")
        assert wf["status"] == "implementing"
        assert wf["implementation_snapshot_digest"] is not None
    finally:
        temp.cleanup()


def mc35_ri_ai_product() -> None:
    """Reviewable identity policy v1: a frozen-allowed .ai-product executable is a Candidate
    deliverable in partial-worktree scope and the v3 snapshot; a hidden out-of-scope .ai-product
    sibling fails closed; technical baseline refresh must not misjudge an unsaved .ai-product
    implementation as clean."""
    temp, root, baseline = new_repo("mc35-")
    try:
        a = init_change(root, "RI", "ai-product")
        path = change_path(root, a)
        draft = valid_contract(root, baseline, "RI", "ai-product")
        draft["allowed_files"] = [".ai-product/recovery-tools/probe.py", "src/app.txt"]
        write_json(path / "task-contract.draft.json", draft)
        run_script(FREEZE, "--root", str(root), "--change", a, "--approved-by", "controller")
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "implementing", "--actor", "controller")
        (root / ".ai-product" / "recovery-tools").mkdir(parents=True)
        (root / ".ai-product" / "recovery-tools" / "probe.py").write_text("PROBE='impl'\n", encoding="utf-8")
        (root / "src" / "app.txt").write_text("impl\n", encoding="utf-8")
        (path / "implementation-report.md").write_text("evidence\n", encoding="utf-8")
        # Hidden out-of-scope .ai-product sibling fails closed (path role, not directory name).
        (root / ".ai-product" / "recovery-tools" / "other.py").write_text("HIDDEN=1\n", encoding="utf-8")
        result = run_script(CAPTURE, "--root", str(root), "--change", a, expect=None)
        assert result.returncode == 2, result.stdout
        assert "out-of-scope" in result.stdout, result.stdout
        (root / ".ai-product" / "recovery-tools" / "other.py").unlink()
        # The allowed .ai-product deliverable enters the v3 snapshot identity chain.
        run_script(CAPTURE, "--root", str(root), "--change", a)
        snapshot = read_json(path / "implementation-snapshot.json")
        assert snapshot["schema_version"] == 3, snapshot
        assert snapshot.get("identity_policy") == "reviewable-control-infrastructure-v1", snapshot
        assert ".ai-product/recovery-tools/probe.py" in snapshot["changed_files"], snapshot["changed_files"]
        # Technical baseline refresh must not misjudge an unsaved .ai-product implementation as clean.
        run_script(TRANSITION, "--root", str(root), "--change", a, "--to", "blocked", "--actor", "controller", "--reason", "external dependency")
        (root / ".ai-product" / "recovery-tools" / "probe.py").write_text("PROBE='unsaved'\n", encoding="utf-8")
        (root / "src" / "extra.txt").write_text("advance\n", encoding="utf-8")
        git(root, "add", "src/extra.txt")
        git(root, "commit", "-m", "advance base")
        result = run_script(REFRESH, "--root", str(root), "--change", a, "--actor", "controller", "--reason", "baseline changed", expect=None)
        assert result.returncode == 2, result.stdout
        assert "clean" in result.stdout, result.stdout
    finally:
        temp.cleanup()


def a1_transition_writer_replays() -> None:
    """A1-8: every lifecycle transition writer converges under completed replay."""
    temp, root, baseline = new_repo("a1-transition-replay-")
    try:
        change = init_change(root, "A1TW", "alpha")
        path = change_path(root, change)

        freeze_named(root, change, "A1TW", "alpha", baseline)
        frozen_history = copy.deepcopy(read_json(path / "workflow-state.json")["history"])
        for _ in range(2):
            run_script(
                FREEZE,
                "--root",
                str(root),
                "--change",
                change,
                "--approved-by",
                "controller",
            )
        assert read_json(path / "workflow-state.json")["history"] == frozen_history

        run_script(
            TRANSITION,
            "--root",
            str(root),
            "--change",
            change,
            "--to",
            "implementing",
            "--actor",
            "coding-agent",
        )
        implementing_history = copy.deepcopy(read_json(path / "workflow-state.json")["history"])
        for _ in range(2):
            run_script(
                TRANSITION,
                "--root",
                str(root),
                "--change",
                change,
                "--to",
                "implementing",
                "--actor",
                "coding-agent",
            )
        assert read_json(path / "workflow-state.json")["history"] == implementing_history

        run_script(
            TRANSITION,
            "--root",
            str(root),
            "--change",
            change,
            "--to",
            "blocked",
            "--actor",
            "controller",
            "--reason",
            "wait",
        )
        run_script(
            RESUME,
            "--root",
            str(root),
            "--change",
            change,
            "--actor",
            "controller",
            "--reason",
            "resume",
        )
        resumed_history = copy.deepcopy(read_json(path / "workflow-state.json")["history"])
        for _ in range(2):
            run_script(
                RESUME,
                "--root",
                str(root),
                "--change",
                change,
                "--actor",
                "controller",
                "--reason",
                "resume replay",
            )
        assert read_json(path / "workflow-state.json")["history"] == resumed_history

        run_script(
            REVISE,
            "--root",
            str(root),
            "--change",
            change,
            "--actor",
            "controller",
            "--reason",
            "revise",
        )
        revised_history = copy.deepcopy(read_json(path / "workflow-state.json")["history"])
        for _ in range(2):
            run_script(
                REVISE,
                "--root",
                str(root),
                "--change",
                change,
                "--actor",
                "controller",
                "--reason",
                "revise replay",
            )
        assert read_json(path / "workflow-state.json")["history"] == revised_history

        run_script(
            FREEZE,
            "--root",
            str(root),
            "--change",
            change,
            "--approved-by",
            "controller",
        )
        run_script(
            TRANSITION,
            "--root",
            str(root),
            "--change",
            change,
            "--to",
            "blocked",
            "--actor",
            "controller",
            "--reason",
            "baseline stale",
        )
        (root / "src" / "replay-base.txt").write_text("advance\n", encoding="utf-8")
        git(root, "add", "src/replay-base.txt")
        git(root, "commit", "-m", "advance replay base")
        run_script(
            REFRESH,
            "--root",
            str(root),
            "--change",
            change,
            "--actor",
            "controller",
            "--reason",
            "refresh",
            "--blocker-resolved",
        )
        refreshed_history = copy.deepcopy(read_json(path / "workflow-state.json")["history"])
        for _ in range(2):
            run_script(
                REFRESH,
                "--root",
                str(root),
                "--change",
                change,
                "--actor",
                "controller",
                "--reason",
                "refresh replay",
                "--blocker-resolved",
            )
        assert read_json(path / "workflow-state.json")["history"] == refreshed_history
    finally:
        temp.cleanup()


def r_selftest_mech_01_rejected_prose_not_authority() -> None:
    temp, root, _ = new_repo("pdc-r-selftest-mech-01-")
    try:
        decision = root / "rejected-focus-decision.md"
        decision.write_text(
            "# PDC Control Decision — adversarial mechanical-binding probe\n"
            "- **Decision:** `DENY_FOCUS_SELECTION`\n"
            "- **Single Focus:** `other-change`\n"
            "- **Expected prior Focus head:** `fs-" + "0" * 64 + "`\n"
            "- **Bounded scope:** `other-change only`\n\n"
            "## Rejected example — NOT AUTHORIZED\n"
            "The rejected example would use FOCUS_SELECTION to select exactly target-change\n"
            "from fs-" + "1" * 64 + ".\n"
            "That rejected example is discussed as bounded behavior only.\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "adversarial rejected Focus prose")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(
                root,
                authority_commit,
                ref,
                selected_change="target-change",
                required_effect="FOCUS_SELECTION",
                expected_prior_focus_selection_id="fs-" + "1" * 64,
            )
        except FailClosedError:
            return
        raise AssertionError("R-SELFTEST-MECH-01 rejected prose authorized Focus selection")
    finally:
        temp.cleanup()


def r_selftest_act_01_historical_ancestor_not_activated() -> None:
    temp, root, _ = _new_synthetic_decision_repo("pdc-self-test-unactivated-")
    try:
        git(root, "checkout", "-b", "synthetic-unactivated")
        decision_path = "control-decisions/synthetic-unactivated.md"
        decision = root / decision_path
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Decision:** `SYNTHETIC_UNACTIVATED_HISTORY`\n",
            encoding="utf-8",
        )
        git(root, "add", decision_path)
        git(root, "commit", "-m", "add unactivated synthetic decision")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision_path,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        git(root, "checkout", "main")
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError(
            "R-SELFTEST-ACT-01 ancestral candidate was accepted without exact activation"
        )
    finally:
        temp.cleanup()


def _new_synthetic_decision_repo(
    prefix: str,
) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
    temp = tempfile.TemporaryDirectory(prefix=prefix)
    root = Path(temp.name) / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "PDC Synthetic Self Test")
    git(root, "config", "user.email", "pdc-synthetic@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    (root / "baseline.txt").write_text("synthetic baseline\n", encoding="utf-8")
    git(root, "add", "baseline.txt")
    git(root, "commit", "-m", "create synthetic baseline")
    return temp, root, git(root, "rev-parse", "HEAD")


def _validate_synthetic_activated_decision(
    activation_style: str,
    *,
    selected_change: str | None = None,
) -> None:
    temp, root, parent = _new_synthetic_decision_repo(
        f"pdc-self-test-{activation_style}-activation-"
    )
    try:
        decision_path = (
            ".ai-product/workpaths/control-decisions/"
            f"synthetic-{activation_style}-activation.md"
        )
        successor = "wp-902"
        revision_path = f".ai-product/workpaths/revisions/{successor}.json"
        pointer_path = ".ai-product/workpaths/current.json"
        declarations = (
            "# PDC Control Decision\n"
            "- **Decision:** `AUTHORIZE_SYNTHETIC_ENGINEERING`\n"
            "- **Current Workpath:** `wp-901`\n"
            f"- **Authorized successor:** `{successor}`\n"
            "- **Single Focus:** `PDC-SELFTEST-FOCUS`\n"
            f"- **Expected prior main:** `{parent}`\n"
        )
        if selected_change is not None:
            declarations += f"- **Exact target:** `{selected_change}`\n"
        if activation_style == "fenced":
            activation = (
                "\n## Activation\n\n"
                "This decision becomes authoritative only through one non-forced "
                "fast-forward commit to `main`, with sole parent:\n\n"
                "```text\n"
                f"{parent}\n"
                "```\n\n"
                "and changing exactly:\n\n"
            )
        elif activation_style == "inline":
            activation = (
                "\n## Activation\n\n"
                "This decision becomes authoritative only through one non-forced "
                f"fast-forward commit to `main`, with sole parent `{parent}`, "
                "changing exactly:\n\n"
            )
        else:
            raise AssertionError(f"unsupported synthetic activation style: {activation_style}")
        decision = root / decision_path
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(
            declarations
            + activation
            + f"1. `{decision_path}`\n"
            + f"2. `{revision_path}`\n"
            + f"3. `{pointer_path}`\n",
            encoding="utf-8",
        )
        decision_digest = hashlib.sha256(decision.read_bytes()).hexdigest()
        write_json(
            root / revision_path,
            {
                "revision_id": successor,
                "prior_revision_id": "wp-901",
                "active_waypoint": "PDC-SELFTEST-FOCUS",
                "source_authority_references": [
                    {"path": decision_path, "sha256": decision_digest}
                ],
            },
        )
        write_json(root / pointer_path, {"revision_id": successor})
        git(root, "add", decision_path, revision_path, pointer_path)
        git(root, "commit", "-m", f"activate synthetic {activation_style} decision")
        authority_commit = git(root, "rev-parse", "HEAD")
        validate_control_decision_ref_at_commit(
            root,
            authority_commit,
            {
                "path": decision_path,
                "sha256": decision_digest,
            },
            selected_change=selected_change,
        )
    finally:
        temp.cleanup()


def r_selftest_wp020_fenced_activation_valid() -> None:
    _validate_synthetic_activated_decision("fenced")


def r_selftest_inline_authorized_engineering_valid() -> None:
    _validate_synthetic_activated_decision(
        "inline",
        selected_change="PDC-SELFTEST-operational-coherence",
    )


def r_selftest_act_rejected_prefix_not_activation() -> None:
    temp, root, parent = new_repo("pdc-r-selftest-act-rejected-prefix-")
    try:
        decision = root / "rejected-activation-decision.md"
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Decision:** `NO_ACTIVATION`\n"
            f"- **Expected prior main:** `{parent}`\n\n"
            "## Activation\n\n"
            f"Rejected example: candidate with sole parent `{parent}`, changing exactly:\n\n"
            "1. `rejected-activation-decision.md`.\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "rejected Activation prose fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError("rejected-prefix Activation prose was treated as authority")
    finally:
        temp.cleanup()


def r_selftest_mech_fenced_authorized_section_not_authority() -> None:
    temp, root, _ = new_repo("pdc-r-selftest-fenced-authorized-")
    try:
        decision = root / "fenced-authorized-example.md"
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Decision:** `FOCUS_SELECTION`\n"
            "- **Expected prior Focus head:** `null`\n"
            "- **Current owner basis:** `UNFOCUSED`\n"
            "- **Bounded scope:** `SELF_TEST_ONLY`\n\n"
            "## Rejected example\n\n"
            "````markdown\n"
            "## Authorized Engineering Work\n\n"
            "Exact target:\n\n"
            "```text\n"
            "target-change\n"
            "```\n"
            "````\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "fenced rejected authority fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(
                root,
                authority_commit,
                ref,
                selected_change="target-change",
                required_effect="FOCUS_SELECTION",
                expected_prior_focus_selection_id=None,
            )
        except FailClosedError:
            return
        raise AssertionError("fenced rejected Authorized Engineering Work supplied authority")
    finally:
        temp.cleanup()


def r_selftest_act_fenced_section_not_activation() -> None:
    temp, root, parent = new_repo("pdc-r-selftest-fenced-activation-")
    try:
        decision = root / "fenced-activation-example.md"
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Decision:** `NO_ACTIVATION`\n"
            f"- **Expected prior main:** `{parent}`\n\n"
            "## Rejected example\n\n"
            "````markdown\n"
            "## Activation\n\n"
            "This decision activates only through one non-forced fast-forward commit to "
            f"`main`, with sole parent `{parent}`, changing exactly:\n\n"
            "1. `fenced-activation-example.md`.\n"
            "````\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "fenced rejected Activation fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError("fenced rejected Activation section was treated as authority")
    finally:
        temp.cleanup()


def r_selftest_mech_nested_rejected_label_not_authority() -> None:
    temp, root, _ = new_repo("pdc-r-selftest-nested-rejected-label-")
    try:
        decision = root / "nested-rejected-label.md"
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Decision:** `FOCUS_SELECTION`\n"
            "- **Expected prior Focus head:** `null`\n"
            "- **Current owner basis:** `UNFOCUSED`\n"
            "- **Bounded scope:** `SELF_TEST_ONLY`\n\n"
            "## Authorized Engineering Work\n\n"
            "### Rejected example\n\n"
            "Exact target:\n\n"
            "```text\n"
            "target-change\n"
            "```\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "nested rejected label fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(
                root,
                authority_commit,
                ref,
                selected_change="target-change",
                required_effect="FOCUS_SELECTION",
                expected_prior_focus_selection_id=None,
            )
        except FailClosedError:
            return
        raise AssertionError("nested rejected label supplied an exact target")
    finally:
        temp.cleanup()


def r_selftest_act_fenced_body_not_activation() -> None:
    temp, root, parent = new_repo("pdc-r-selftest-fenced-activation-body-")
    try:
        decision = root / "fenced-activation-body.md"
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Decision:** `NO_ACTIVATION`\n"
            f"- **Expected prior main:** `{parent}`\n\n"
            "## Activation\n\n"
            "````markdown\n"
            "This decision activates only through one non-forced fast-forward commit to "
            f"`main`, with sole parent `{parent}`, changing exactly:\n\n"
            "1. `fenced-activation-body.md`.\n"
            "````\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "fenced Activation body fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError("fenced content inside real Activation supplied authority")
    finally:
        temp.cleanup()


def _activated_decision_fixture(
    root: Path,
    parent: str,
    *,
    decision_name: str,
    rejected_h3_prefix: bool,
    include_successor: bool,
    indent_paths_after_first: bool = False,
    fenced_parent: bool = False,
    indent_fenced_marker: bool = False,
) -> tuple[str, dict[str, str]]:
    decision_path = decision_name
    revision_path = ".ai-product/workpaths/revisions/wp-002.json"
    pointer_path = ".ai-product/workpaths/current.json"
    paths = [decision_path]
    metadata = (
        "# PDC Control Decision\n"
        "- **Decision:** `ACTIVATION_FIXTURE`\n"
        f"- **Expected prior main:** `{parent}`\n"
        "- **Current Workpath:** `wp-001`\n"
        "- **Single Focus:** `ACTIVATION-FIXTURE`\n"
    )
    if include_successor:
        metadata += "- **Authorized successor:** `wp-002`\n"
        paths.extend([revision_path, pointer_path])
    prefix = "### Rejected example\n\n" if rejected_h3_prefix else ""
    path_lines = "".join(
        ("    " if indent_paths_after_first and index > 1 else "")
        + f"{index}. `{path}`.\n"
        for index, path in enumerate(paths, start=1)
    )
    if fenced_parent:
        activation_binding = (
            "This decision activates only through one non-forced fast-forward commit to "
            "`main`, with sole parent:\n\n"
            "```text\n"
            f"{parent}\n"
            "```\n\n"
            + ("    " if indent_fenced_marker else "")
            + "and changing exactly:\n\n"
        )
    else:
        activation_binding = (
            "This decision activates only through one non-forced fast-forward commit to "
            f"`main`, with sole parent `{parent}`, changing exactly:\n\n"
        )
    decision = root / decision_path
    decision.write_text(
        metadata
        + "\n## Activation\n\n"
        + prefix
        + activation_binding
        + path_lines,
        encoding="utf-8",
    )
    digest = hashlib.sha256(decision.read_bytes()).hexdigest()
    if include_successor:
        write_json(
            root / revision_path,
            {
                "revision_id": "wp-002",
                "prior_revision_id": "wp-001",
                "active_waypoint": "ACTIVATION-FIXTURE",
                "source_authority_references": [
                    {"path": decision_path, "sha256": digest}
                ],
            },
        )
        write_json(root / pointer_path, {"revision_id": "wp-002"})
    git(root, "add", *paths)
    git(root, "commit", "-m", "activated decision adversarial fixture")
    return git(root, "rev-parse", "HEAD"), {"path": decision_path, "sha256": digest}


def r_selftest_mech_nested_metadata_not_authority() -> None:
    temp, root, _ = new_repo("pdc-r-selftest-nested-metadata-")
    try:
        decision = root / "nested-metadata-example.md"
        decision.write_text(
            "# PDC Control Decision\n\n"
            "### Rejected example\n\n"
            "- **Decision:** `FOCUS_SELECTION`\n"
            "- **Exact target:** `target-change`\n"
            "- **Expected prior Focus head:** `null`\n"
            "- **Current owner basis:** `UNFOCUSED`\n"
            "- **Bounded scope:** `SELF_TEST_ONLY`\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "nested rejected metadata fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(
                root,
                authority_commit,
                ref,
                selected_change="target-change",
                required_effect="FOCUS_SELECTION",
                expected_prior_focus_selection_id=None,
            )
        except FailClosedError:
            return
        raise AssertionError("nested rejected metadata supplied Focus authority")
    finally:
        temp.cleanup()


def r_selftest_act_nested_rejected_not_activation() -> None:
    temp, root, parent = new_repo("pdc-r-selftest-nested-activation-")
    try:
        authority_commit, ref = _activated_decision_fixture(
            root,
            parent,
            decision_name="nested-activation-example.md",
            rejected_h3_prefix=True,
            include_successor=True,
        )
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError("nested rejected Activation supplied authority")
    finally:
        temp.cleanup()


def r_selftest_act_missing_successor_rejected() -> None:
    temp, root, parent = new_repo("pdc-r-selftest-missing-successor-")
    try:
        authority_commit, ref = _activated_decision_fixture(
            root,
            parent,
            decision_name="missing-successor-example.md",
            rejected_h3_prefix=False,
            include_successor=False,
        )
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError("Activation without Authorized successor was accepted")
    finally:
        temp.cleanup()


def r_selftest_mech_nested_list_metadata_not_authority() -> None:
    temp, root, _ = new_repo("pdc-r-selftest-nested-list-metadata-")
    try:
        decision = root / "nested-list-metadata.md"
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Rejected example:** `NOT AUTHORIZED`\n"
            "  - **Decision:** `FOCUS_SELECTION`\n"
            "  - **Exact target:** `target-change`\n"
            "  - **Expected prior Focus head:** `null`\n"
            "  - **Current owner basis:** `UNFOCUSED`\n"
            "  - **Bounded scope:** `SELF_TEST_ONLY`\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "nested list metadata fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(
                root,
                authority_commit,
                ref,
                selected_change="target-change",
                required_effect="FOCUS_SELECTION",
                expected_prior_focus_selection_id=None,
            )
        except FailClosedError:
            return
        raise AssertionError("nested list metadata supplied Focus authority")
    finally:
        temp.cleanup()


def r_selftest_mech_indented_authorized_code_not_authority() -> None:
    temp, root, _ = new_repo("pdc-r-selftest-indented-authorized-")
    try:
        decision = root / "indented-authorized-code.md"
        decision.write_text(
            "# PDC Control Decision\n"
            "- **Decision:** `FOCUS_SELECTION`\n"
            "- **Expected prior Focus head:** `null`\n"
            "- **Current owner basis:** `UNFOCUSED`\n"
            "- **Bounded scope:** `SELF_TEST_ONLY`\n\n"
            "## Authorized Engineering Work\n"
            "    Exact target:\n"
            "    ```text\n"
            "    target-change\n"
            "    ```\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "indented Authorized code fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(
                root,
                authority_commit,
                ref,
                selected_change="target-change",
                required_effect="FOCUS_SELECTION",
                expected_prior_focus_selection_id=None,
            )
        except FailClosedError:
            return
        raise AssertionError("indented code supplied Authorized Engineering authority")
    finally:
        temp.cleanup()


def r_selftest_act_indented_paths_rejected() -> None:
    temp, root, parent = new_repo("pdc-r-selftest-indented-paths-")
    try:
        authority_commit, ref = _activated_decision_fixture(
            root,
            parent,
            decision_name="indented-activation-paths.md",
            rejected_h3_prefix=False,
            include_successor=True,
            indent_paths_after_first=True,
        )
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError("indented Activation paths were flattened into the changed-path set")
    finally:
        temp.cleanup()


def r_selftest_act_indented_fenced_marker_rejected() -> None:
    temp, root, parent = new_repo("pdc-r-selftest-indented-marker-")
    try:
        authority_commit, ref = _activated_decision_fixture(
            root,
            parent,
            decision_name="indented-activation-marker.md",
            rejected_h3_prefix=False,
            include_successor=True,
            fenced_parent=True,
            indent_fenced_marker=True,
        )
        try:
            validate_control_decision_ref_at_commit(root, authority_commit, ref)
        except FailClosedError:
            return
        raise AssertionError("indented fenced-parent marker was treated as authority")
    finally:
        temp.cleanup()


def r_selftest_mech_disclaimed_title_not_authority() -> None:
    temp, root, _ = new_repo("pdc-r-selftest-disclaimed-title-")
    try:
        decision = root / "disclaimed-control-decision.md"
        decision.write_text(
            "# This is not a PDC Control Decision\n"
            "- **Decision:** `FOCUS_SELECTION`\n"
            "- **Exact target:** `target-change`\n"
            "- **Expected prior Focus head:** `null`\n"
            "- **Current owner basis:** `UNFOCUSED`\n"
            "- **Bounded scope:** `SELF_TEST_ONLY`\n",
            encoding="utf-8",
        )
        git(root, "add", decision.name)
        git(root, "commit", "-m", "disclaimed title fixture")
        authority_commit = git(root, "rev-parse", "HEAD")
        ref = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        }
        try:
            validate_control_decision_ref_at_commit(
                root,
                authority_commit,
                ref,
                selected_change="target-change",
                required_effect="FOCUS_SELECTION",
                expected_prior_focus_selection_id=None,
            )
        except FailClosedError:
            return
        raise AssertionError("disclaimed title was treated as a PDC Control Decision")
    finally:
        temp.cleanup()


CASES: list[tuple[str, Callable[[], None]]] = [
    ("MC-01", mc01), ("MC-02", mc02), ("MC-03", mc03), ("MC-04", mc04), ("MC-05", mc05),
    ("MC-06", mc06), ("MC-07", mc07), ("MC-08", mc08), ("MC-09", mc09), ("MC-10", mc10),
    ("MC-11", mc11), ("MC-12", mc12), ("MC-13", mc13), ("MC-14", mc14), ("MC-15", mc15),
    ("MC-16", mc16), ("MC-17", mc17), ("MC-18", mc18), ("MC-19", mc19), ("MC-20", mc20),
    ("MC-21", mc21), ("MC-22", mc22), ("MC-23", mc23), ("MC-24", mc24), ("MC-25", mc25),
    ("MC-26", mc26), ("MC-27", mc27),
    ("MC-28", mc28_post_snapshot_advanced_resume),
    ("MC-29", mc29_r1_worktree_irrelevant_on_evidence_resume), ("MC-30", mc30_r2_reviewed_main_tamper_fails_closed),
    ("MC-31", mc31_r3_diverged_history_rejected), ("MC-32", mc32_r4_broken_binding_rejected),
    ("MC-33", mc33_r5_pre_snapshot_stale_rejected), ("MC-34", mc34_r6_exact_tip_resume),
    ("MC-35", mc35_ri_ai_product),
    ("A1-TW-REPLAY", a1_transition_writer_replays),
    ("R-SELFTEST-MECH-01", r_selftest_mech_01_rejected_prose_not_authority),
    ("R-SELFTEST-ACT-01", r_selftest_act_01_historical_ancestor_not_activated),
    ("R-SELFTEST-WP020-ACTIVATION", r_selftest_wp020_fenced_activation_valid),
    ("R-SELFTEST-INLINE-AUTHORIZED", r_selftest_inline_authorized_engineering_valid),
    ("R-SELFTEST-ACT-REJECTED-PREFIX", r_selftest_act_rejected_prefix_not_activation),
    ("R-SELFTEST-MECH-FENCED-SECTION", r_selftest_mech_fenced_authorized_section_not_authority),
    ("R-SELFTEST-ACT-FENCED-SECTION", r_selftest_act_fenced_section_not_activation),
    ("R-SELFTEST-MECH-NESTED-REJECTED", r_selftest_mech_nested_rejected_label_not_authority),
    ("R-SELFTEST-ACT-FENCED-BODY", r_selftest_act_fenced_body_not_activation),
    ("R-SELFTEST-MECH-NESTED-METADATA", r_selftest_mech_nested_metadata_not_authority),
    ("R-SELFTEST-ACT-NESTED-REJECTED", r_selftest_act_nested_rejected_not_activation),
    ("R-SELFTEST-ACT-MISSING-SUCCESSOR", r_selftest_act_missing_successor_rejected),
    ("R-SELFTEST-MECH-NESTED-LIST", r_selftest_mech_nested_list_metadata_not_authority),
    ("R-SELFTEST-MECH-INDENTED-CODE", r_selftest_mech_indented_authorized_code_not_authority),
    ("R-SELFTEST-ACT-INDENTED-PATHS", r_selftest_act_indented_paths_rejected),
    ("R-SELFTEST-ACT-INDENTED-MARKER", r_selftest_act_indented_fenced_marker_rejected),
    ("R-SELFTEST-MECH-DISCLAIMED-TITLE", r_selftest_mech_disclaimed_title_not_authority),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Run the complete deterministic suite; retained for parity with other self-tests")
    args = parser.parse_args()
    del args
    failures: list[str] = []
    # Cases use isolated temporary repositories. Run them concurrently so the complete frozen
    # command remains inside constrained agent execution windows without reducing coverage.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(CASES))) as pool:
        futures = [(case_id, pool.submit(case)) for case_id, case in CASES]
        for case_id, future in futures:
            try:
                future.result()
                print(f"{case_id} PASS")
            except Exception as exc:  # deterministic self-test should report every scenario in one run
                failures.append(case_id)
                print(f"{case_id} FAIL: {type(exc).__name__}: {exc}")
    if failures:
        print("MULTI CHANGE SELF TEST FAILED: " + ", ".join(failures))
        return 1
    print(
        "MULTI CHANGE SELF TEST PASSED: MC-01..MC-35 + A1-TW-REPLAY + "
        "R-SELFTEST-MECH-01 + R-SELFTEST-ACT-01 + R-SELFTEST-WP020-ACTIVATION + "
        "R-SELFTEST-INLINE-AUTHORIZED + "
        "R-SELFTEST-ACT-REJECTED-PREFIX + R-SELFTEST-MECH-FENCED-SECTION + "
        "R-SELFTEST-ACT-FENCED-SECTION + R-SELFTEST-MECH-NESTED-REJECTED + "
        "R-SELFTEST-ACT-FENCED-BODY + R-SELFTEST-MECH-NESTED-METADATA + "
        "R-SELFTEST-ACT-NESTED-REJECTED + R-SELFTEST-ACT-MISSING-SUCCESSOR + "
        "R-SELFTEST-MECH-NESTED-LIST + R-SELFTEST-MECH-INDENTED-CODE + "
        "R-SELFTEST-ACT-INDENTED-PATHS + R-SELFTEST-ACT-INDENTED-MARKER + "
        "R-SELFTEST-MECH-DISCLAIMED-TITLE"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
