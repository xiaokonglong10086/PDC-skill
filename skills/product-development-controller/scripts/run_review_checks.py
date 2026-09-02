#!/usr/bin/env python3
"""Run every frozen required test once against the exact immutable review commit."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capture_implementation_snapshot import (
    load_frozen_contract,
    validate_current_worktree,
    validate_snapshot,
    validate_snapshot_git,
)
from common import (
    atomic_write_json,
    controller_lock,
    digest_record,
    git_output,
    load_json_object,
    now_iso,
    run_command,
    safe_child,
    sha256_file,
    validate_change_name,
)
from multi_change import assert_focused_change
from validate_test_execution_record import (
    capture_main_worktree_state,
    validate_execution_record,
)

ALLOWED_STATUSES = {"ready_for_review", "changes_requested", "evidence_missing"}


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _execute(command: str, *, cwd: Path, timeout: float) -> tuple[int | None, bytes, str | None]:
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output or b"", None
    except subprocess.TimeoutExpired as exc:
        partial = exc.output or b""
        if isinstance(partial, str):
            partial = partial.encode("utf-8", errors="replace")
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, _ = process.communicate()
            if output:
                partial += output
        return None, partial, f"command timed out after {timeout:g} seconds"
    except OSError as exc:
        return None, str(exc).encode("utf-8", errors="replace"), f"command could not start: {exc}"


def _blocked_test_record(
    frozen: dict[str, Any],
    *,
    reason: str,
    log_path: Path,
    change_path: Path,
) -> dict[str, Any]:
    timestamp = now_iso()
    _atomic_write_bytes(log_path, ("BLOCKED: " + reason + "\n").encode("utf-8"))
    return {
        "id": frozen["id"],
        "type": frozen["type"],
        "command": frozen["command"],
        "expected": frozen["expected"],
        "expected_exit_code": 0,
        "started_at": timestamp,
        "completed_at": timestamp,
        "actual_exit_code": None,
        "result": "blocked",
        "blocked_reason": reason,
        "log_path": log_path.relative_to(change_path).as_posix(),
        "log_size": log_path.stat().st_size,
        "log_sha256": sha256_file(log_path),
    }


def _run_test(
    frozen: dict[str, Any],
    *,
    worktree: Path,
    timeout: float,
    log_path: Path,
    change_path: Path,
) -> dict[str, Any]:
    started = now_iso()
    actual_exit, output, execution_error = _execute(str(frozen["command"]), cwd=worktree, timeout=timeout)
    completed = now_iso()
    _atomic_write_bytes(log_path, output)
    blocked_reason: str | None = None
    if execution_error is not None:
        result = "blocked"
        blocked_reason = execution_error
    elif actual_exit in {126, 127}:
        result = "blocked"
        blocked_reason = f"command or interpreter unavailable (exit code {actual_exit})"
    elif actual_exit == 0:
        result = "passed"
    else:
        result = "failed"
    return {
        "id": frozen["id"],
        "type": frozen["type"],
        "command": frozen["command"],
        "expected": frozen["expected"],
        "expected_exit_code": 0,
        "started_at": started,
        "completed_at": completed,
        "actual_exit_code": actual_exit,
        "result": result,
        "blocked_reason": blocked_reason,
        "log_path": log_path.relative_to(change_path).as_posix(),
        "log_size": log_path.stat().st_size,
        "log_sha256": sha256_file(log_path),
    }


def _run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_hex(4)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change directory name; defaults to current_change")
    parser.add_argument("--executor", required=True, help="Controller identity executing the frozen tests")
    parser.add_argument("--timeout", type=float, default=1800.0, help="Per-test timeout in seconds")
    args = parser.parse_args()

    if args.timeout <= 0:
        print("ERROR: --timeout must be positive", file=sys.stderr)
        return 2

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        with controller_lock(control_root):
            project = load_json_object(safe_child(control_root, "project-state.json"))
            change_name = args.change or project.get("current_change")
            if not isinstance(change_name, str):
                raise ValueError("no current change; pass --change")
            validate_change_name(change_name)
            assert_focused_change(control_root, change_name, project=project)
            change_path = safe_child(control_root, "changes", change_name)
            workflow_path = safe_child(change_path, "workflow-state.json")
            workflow = load_json_object(workflow_path)
            if workflow.get("status") not in ALLOWED_STATUSES:
                raise ValueError(
                    "review checks require status ready_for_review, changes_requested, or evidence_missing"
                )
            contract, contract_digest = load_frozen_contract(change_path, workflow)
            snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
            preflight = validate_snapshot(snapshot, contract, contract_digest)
            preflight += validate_snapshot_git(root, snapshot, contract)
            preflight += validate_current_worktree(root, snapshot)
            if preflight:
                raise ValueError("review target is invalid: " + "; ".join(preflight))
            if workflow.get("implementation_snapshot_digest") != snapshot.get("snapshot_digest"):
                raise ValueError("workflow implementation snapshot digest mismatch")
            if workflow.get("review_commit_sha") != snapshot.get("review_commit_sha"):
                raise ValueError("workflow review commit mismatch")

            frozen_tests = [item for item in contract.get("required_tests", []) if isinstance(item, dict)]
            if not frozen_tests:
                raise ValueError("frozen contract contains no required tests")

            before = capture_main_worktree_state(root)
            record_started = now_iso()
            run_id = _run_id()
            evidence_dir = safe_child(change_path, "evidence", "review-tests", run_id)
            evidence_dir.mkdir(parents=True, exist_ok=False)
            temp_parent = Path(tempfile.mkdtemp(prefix="pdc-review-checks-"))
            worktree = temp_parent / "worktree"
            records: list[dict[str, Any]] = []
            blockers: list[str] = []
            cleanup = "removed"
            setup_ready = False
            setup_error: str | None = None
            try:
                add = run_command(
                    ("git", "worktree", "add", "--detach", str(worktree), str(snapshot["review_commit_sha"])),
                    cwd=root,
                )
                if add.returncode != 0:
                    setup_error = f"temporary worktree setup failed: {add.stdout.strip()}"
                    blockers.append(setup_error)
                else:
                    actual_commit = git_output(worktree, "rev-parse", "HEAD").lower()
                    if actual_commit != snapshot.get("review_commit_sha"):
                        setup_error = "temporary worktree resolved to a commit other than review_commit_sha"
                        blockers.append(setup_error)
                    else:
                        setup_ready = True

                for frozen in frozen_tests:
                    log_path = safe_child(evidence_dir, f"{frozen['id']}.log")
                    if setup_ready:
                        records.append(
                            _run_test(
                                frozen,
                                worktree=worktree,
                                timeout=args.timeout,
                                log_path=log_path,
                                change_path=change_path,
                            )
                        )
                    else:
                        records.append(
                            _blocked_test_record(
                                frozen,
                                reason=setup_error or "temporary worktree was unavailable",
                                log_path=log_path,
                                change_path=change_path,
                            )
                        )
            finally:
                if worktree.exists():
                    remove = run_command(("git", "worktree", "remove", "--force", str(worktree)), cwd=root)
                    if remove.returncode != 0:
                        cleanup = "failed"
                        blockers.append(f"temporary worktree cleanup failed: {remove.stdout.strip()}")
                prune = run_command(("git", "worktree", "prune"), cwd=root)
                if prune.returncode != 0:
                    cleanup = "failed"
                    blockers.append(f"git worktree prune failed: {prune.stdout.strip()}")
                try:
                    shutil.rmtree(temp_parent)
                except OSError as exc:
                    cleanup = "failed"
                    blockers.append(f"temporary directory cleanup failed: {exc}")

            after = capture_main_worktree_state(root)
            preserved = before == after
            if not preserved:
                blockers.append("main worktree, branch, HEAD, or normal Git index changed during review checks")

            results = [item["result"] for item in records]
            if blockers or cleanup == "failed" or "blocked" in results:
                overall = "blocked"
            elif "failed" in results:
                overall = "failed"
            else:
                overall = "passed"
            record: dict[str, Any] = {
                "schema_version": 1,
                "task_id": contract["task_id"],
                "contract_version": contract["contract_version"],
                "contract_digest": contract_digest,
                "implementation_snapshot_digest": snapshot["snapshot_digest"],
                "review_commit_sha": snapshot["review_commit_sha"],
                "baseline_sha": contract["baseline"]["sha"],
                "executor": args.executor,
                "started_at": record_started,
                "completed_at": now_iso(),
                "timeout_seconds": args.timeout,
                "isolation": {
                    "strategy": "detached_temporary_git_worktree",
                    "review_commit_sha": snapshot["review_commit_sha"],
                    "cleanup": cleanup,
                    "security_boundary": "git_isolation_not_security_sandbox",
                },
                "main_worktree": {
                    "branch_before": before["branch"],
                    "branch_after": after["branch"],
                    "head_before": before["head"],
                    "head_after": after["head"],
                    "status_before_sha256": before["status_sha256"],
                    "status_after_sha256": after["status_sha256"],
                    "index_before_sha256": before["index_sha256"],
                    "index_after_sha256": after["index_sha256"],
                    "preserved": preserved,
                },
                "tests": records,
                "runner_blockers": blockers,
                "overall_status": overall,
            }
            record["record_digest"] = digest_record(record, "record_digest")

            pre_write_errors = validate_execution_record(
                record,
                contract,
                contract_digest,
                snapshot,
                workflow,
                root,
                change_path,
                require_workflow_binding=False,
            )
            if pre_write_errors:
                raise ValueError("generated execution record is invalid: " + "; ".join(pre_write_errors))

            record_path = safe_child(change_path, "test-execution-record.json")
            atomic_write_json(record_path, record)
            workflow["test_execution_record_digest"] = record["record_digest"]
            workflow["updated_at"] = now_iso()
            atomic_write_json(workflow_path, workflow)
            final_errors = validate_execution_record(
                record, contract, contract_digest, snapshot, workflow, root, change_path
            )
            if final_errors:
                workflow["test_execution_record_digest"] = None
                workflow["updated_at"] = now_iso()
                atomic_write_json(workflow_path, workflow)
                raise ValueError("persisted execution record is invalid: " + "; ".join(final_errors))
            capabilities = project.setdefault("capabilities", {})
            capabilities["project_test_execution"] = True
            atomic_write_json(safe_child(control_root, "project-state.json"), project)

        print(json.dumps(record, ensure_ascii=False, indent=2))
        if record["overall_status"] == "passed":
            return 0
        if record["overall_status"] == "failed":
            return 1
        return 2
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
