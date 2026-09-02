#!/usr/bin/env python3
"""Execute frozen post-merge checks and create a verifiable integration record."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from capture_implementation_snapshot import (
    _build_canonical_index,
    canonical_identity_digest,
    changed_paths,
    git_output_bytes,
    load_frozen_contract,
)
from common import (
    actual_repository_identity,
    atomic_write_json,
    atomic_write_text,
    controller_lock,
    current_branch,
    digest_record,
    git_is_ancestor,
    git_output,
    load_json_object,
    now_iso,
    non_control_git_status,
    run_command,
    safe_child,
    sha256_bytes,
    sha256_json,
    verify_git_branch,
    verify_git_commit,
    validate_change_name,
)

from multi_change import assert_focused_change


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _cleanup_process_group(pgid: int, *, grace_seconds: float = 0.2) -> None:
    """Terminate residual processes from one isolated post-merge invocation (POSIX)."""
    if not _process_group_exists(pgid):
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not _process_group_exists(pgid):
            return
        time.sleep(0.02)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return


# ---------------------------------------------------------------------------
# Platform-dispatched execution-tree cleanup (PDC-MAINT windows-integration-runner).
# POSIX uses the original process-group semantics. Windows uses a Job Object with
# KILL_ON_JOB_CLOSE: closing the job terminates every process still in the tree,
# including descendants leaked after the direct child exits. This reproduces the
# POSIX observable guarantee without a third-party dependency and without touching
# the POSIX path.
# ---------------------------------------------------------------------------

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _create_windows_job_object() -> int:
    """Create a Job Object that kills its process tree when the handle is closed."""
    kernel32 = ctypes.windll.kernel32
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return 0
    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    result = kernel32.SetInformationJobObject(
        job,
        9,  # JobObjectExtendedLimitInformation
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not result:
        kernel32.CloseHandle(job)
        return 0
    return job


def _assign_process_to_windows_job(job: int, pid: int) -> None:
    """Best-effort assignment of a child to the Job Object immediately after spawn."""
    if not job:
        return
    kernel32 = ctypes.windll.kernel32
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_TERMINATE = 0x0001
    handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
    if not handle:
        return
    try:
        kernel32.AssignProcessToJobObject(job, handle)
    finally:
        kernel32.CloseHandle(handle)


def _close_windows_job(job: int) -> None:
    if job:
        ctypes.windll.kernel32.CloseHandle(job)


def _execution_tree_exists(process: subprocess.Popen) -> bool:
    """Whether residual execution-tree processes may still exist for this invocation."""
    if os.name == "posix":
        return _process_group_exists(process.pid)
    return process.poll() is None


def _cleanup_execution_tree(
    process: subprocess.Popen,
    *,
    windows_job: int = 0,
    grace_seconds: float = 0.2,
) -> None:
    """Terminate residual processes from one isolated post-merge invocation.

    POSIX: original process-group SIGTERM -> grace -> SIGKILL.
    Windows: close the Job Object handle (KILL_ON_JOB_CLOSE terminates the whole tree).
    The direct child, if still running, is also reaped best-effort.
    """
    if os.name == "posix":
        _cleanup_process_group(process.pid, grace_seconds=grace_seconds)
        return
    _close_windows_job(windows_job)
    if process.poll() is None:
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            process.wait(timeout=grace_seconds)


def run_post_merge_command(
    command: str,
    *,
    cwd: Path,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one frozen command without coupling completion to descendant pipe EOF."""
    popen_kwargs: dict = {}
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    windows_job = 0
    with tempfile.TemporaryFile(mode="w+b") as output_file:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            shell=True,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
        if os.name != "posix":
            windows_job = _create_windows_job_object()
            _assign_process_to_windows_job(windows_job, process.pid)
        timed_out = False
        try:
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _cleanup_execution_tree(process, windows_job=windows_job)
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    process.wait()
                returncode = process.returncode
            else:
                _cleanup_execution_tree(process, windows_job=windows_job)
        finally:
            _close_windows_job(windows_job)

        output_file.flush()
        output_file.seek(0)
        output = output_file.read().decode("utf-8", errors="replace")
        if timed_out:
            detail = output.rstrip()
            suffix = f"\n{detail}" if detail else ""
            raise TimeoutError(f"post-merge command timed out after {timeout} seconds{suffix}")
        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout=output,
            stderr=None,
        )


def _reconstruct_canonical_identity(root: Path, baseline: str, merge_sha: str, snapshot: dict) -> dict:
    """Reconstruct the canonical reviewed identity of the integration commit relative to the baseline.

    The reconstruction reads the MERGE COMMIT's tree (not the worktree): read-tree baseline into a
    temporary index, overlay the merge commit's tree for the reviewed paths, and derive
    tree/manifest/canonical digest under the snapshot identity policy. Sibling topology is fine;
    only content identity must match the review snapshot.
    """
    policy = snapshot.get("identity_policy", "reviewable-control-infrastructure-v1")
    paths = changed_paths(root, baseline, identity_policy=policy)
    result: dict = {"changed_files": paths, "mismatch": []}
    fd, temp_name = tempfile.mkstemp(prefix="pdc-canonical-merge-")
    os.close(fd)
    temp_index = Path(temp_name)
    temp_index.unlink()
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(temp_index)
    try:
        # Read baseline, then read the merge commit's tree on top so the index reflects the merge.
        r1 = run_command(("git", "read-tree", baseline), cwd=root, env=env)
        if r1.returncode != 0:
            raise ValueError(f"read-tree baseline failed:\n{r1.stdout}")
        r2 = run_command(("git", "read-tree", merge_sha), cwd=root, env=env)
        if r2.returncode != 0:
            raise ValueError(f"read-tree merge failed:\n{r2.stdout}")
        tree = run_command(("git", "write-tree"), cwd=root, env=env, check=True).stdout.strip().lower()
        entries_text = run_command(("git", "ls-files", "--stage", "--", *paths), cwd=root, env=env, check=True).stdout
        entries: dict[str, dict] = {}
        for line in entries_text.splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            meta = parts[0].split()
            if len(meta) < 3:
                continue
            mode, oid, _stage = meta[0], meta[1], meta[2]
            rel = parts[1].replace("\\", "/")
            blob_bytes = git_output_bytes(root, "cat-file", "blob", oid)
            entries[rel] = {
                "mode": mode, "blob_sha": oid, "canonical_size": len(blob_bytes),
                "state": "present", "sha256": sha256_bytes(blob_bytes), "size": len(blob_bytes),
            }
        for relative in paths:
            if relative not in entries:
                entries[relative] = {
                    "path": relative, "state": "deleted", "mode": None, "blob_sha": None,
                    "canonical_size": 0, "sha256": None, "size": 0,
                }
        manifest = []
        for relative in sorted(entries):
            e = entries[relative]
            manifest.append({
                "path": relative, "state": e["state"], "mode": e["mode"], "blob_sha": e["blob_sha"],
                "canonical_size": e["canonical_size"], "sha256": e["sha256"], "size": e["size"],
            })
        result["tree"] = tree
        result["manifest"] = manifest
        result["canonical_identity_digest"] = canonical_identity_digest(baseline, tree, manifest)
        if paths != snapshot.get("changed_files"):
            result["mismatch"].append("reconstructed changed-file set differs from review snapshot")
        if tree != snapshot.get("review_tree_sha"):
            result["mismatch"].append("reconstructed tree differs from review snapshot review_tree_sha")
        if result["canonical_identity_digest"] != snapshot.get("canonical_identity_digest"):
            result["mismatch"].append("reconstructed canonical identity digest differs from review snapshot")
        expected_manifest = snapshot.get("file_manifest")
        if expected_manifest is not None and manifest != expected_manifest:
            result["mismatch"].append("reconstructed canonical manifest differs from review snapshot")
    except ValueError as exc:
        result["mismatch"].append(f"canonical reconstruction failed: {exc}")
    finally:
        try:
            temp_index.unlink()
        except FileNotFoundError:
            pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--change")
    parser.add_argument("--merge-sha", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--rollback", required=True)
    parser.add_argument("--release-reference")
    parser.add_argument("--pr-provider")
    parser.add_argument("--pr-url")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        with controller_lock(control_root):
            project_path = safe_child(control_root, "project-state.json")
            project = load_json_object(project_path)
            change_name = args.change or project.get("current_change")
            if not isinstance(change_name, str):
                raise ValueError("no current change; pass --change")
            validate_change_name(change_name)
            assert_focused_change(control_root, change_name, project=project)
            change_path = safe_child(control_root, "changes", change_name)
            workflow = load_json_object(safe_child(change_path, "workflow-state.json"))
            if workflow.get("status") != "integration_ready":
                raise ValueError("integration can be recorded only while status=integration_ready")
            contract, contract_digest = load_frozen_contract(change_path, workflow)
            snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
            review = load_json_object(safe_child(change_path, "review-report.json"))
            acceptance = load_json_object(safe_child(change_path, "acceptance-record.json"))

            actual_identity = actual_repository_identity(root)
            if actual_identity != contract.get("repository_identity"):
                raise ValueError("current repository identity differs from frozen contract")
            if str(root) != contract.get("repository_root"):
                raise ValueError("current repository root differs from frozen contract")
            base_branch = str(contract["baseline"]["branch"])
            branch_tip = verify_git_branch(root, base_branch)
            merge_sha = verify_git_commit(root, args.merge_sha)
            if not git_is_ancestor(root, str(contract["baseline"]["sha"]), merge_sha):
                raise ValueError("merge commit does not descend from baseline")
            if not git_is_ancestor(root, merge_sha, branch_tip):
                raise ValueError("merge commit is not contained in the frozen base branch")
            # Schema v3 (contract v2): reject an integration commit whose canonical reviewed
            # identity does not reconstruct from the merge tree — before any local-verification
            # gates, so identity failure is reported first and precisely.
            baseline_sha = str(contract["baseline"]["sha"])
            reconstructed = _reconstruct_canonical_identity(root, baseline_sha, merge_sha, snapshot)
            canonical_mismatch = reconstructed.get("mismatch") or []
            if canonical_mismatch:
                raise ValueError("integration commit does not reconstruct the reviewed canonical identity: " + "; ".join(canonical_mismatch))
            if current_branch(root) != base_branch:
                raise ValueError("local verification requires the frozen base branch to be checked out")
            if git_output(root, "rev-parse", "HEAD").lower() != merge_sha:
                raise ValueError("local verification requires HEAD to equal merge commit")
            if non_control_git_status(root):
                raise ValueError("local verification requires no non-controller working-tree changes")

            evidence_dir = safe_child(change_path, "evidence", "post-merge")
            evidence_dir.mkdir(parents=True, exist_ok=True)
            check_records = []
            for check in contract.get("post_merge_checks", []):
                check_id = str(check["id"])
                command = str(check["command"])
                expected = int(check["expected_exit_code"])
                started = now_iso()
                result = run_post_merge_command(command, cwd=root, timeout=args.timeout)
                log_text = result.stdout
                log_path = safe_child(evidence_dir, f"{check_id}.log")
                atomic_write_text(log_path, log_text)
                record = {
                    "id": check_id,
                    "command": command,
                    "expected_exit_code": expected,
                    "actual_exit_code": result.returncode,
                    "stdout_sha256": sha256_bytes(log_text.encode("utf-8")),
                    "log_path": log_path.relative_to(change_path).as_posix(),
                    "executed_at": started,
                    "executor": args.actor,
                }
                check_records.append(record)
                if result.returncode != expected:
                    raise ValueError(
                        f"post-merge check {check_id} failed with {result.returncode}; expected {expected}"
                    )

            pr_populated = any((args.pr_provider, args.pr_url, args.pr_number))
            if pr_populated and not all((args.pr_provider, args.pr_url, args.pr_number)):
                raise ValueError("PR provider, URL, and number must be supplied together")
            recorded_at = now_iso()
            # Schema v3 (contract v2): the formal integration commit must reconstruct, relative to the
            # frozen baseline and under the snapshot identity policy, the exact canonical reviewed
            # identity of the review snapshot. Sibling topology is legal — no ancestry requirement.
            # review_commit_sha remains the provenance carrier; its resolvability is an independent fact.
            # (The reconstruction check already ran at the top of the integration gate; reuse it.)
            review_commit_sha = str(snapshot["review_commit_sha"])
            baseline = str(contract["baseline"]["sha"])
            review_object_present = True
            try:
                verify_git_commit(root, review_commit_sha)
            except ValueError:
                review_object_present = False
            local_identity_evidence = {
                "review_commit_sha": review_commit_sha,
                "review_object_resolvable_locally": review_object_present,
                "merge_commit_sha": merge_sha,
                "baseline_sha": baseline,
                "reviewed_changed_file_set_reconstructed": reconstructed.get("changed_files") == snapshot.get("changed_files"),
                "review_tree_sha_reconstructed": reconstructed.get("tree") == snapshot.get("review_tree_sha"),
                "canonical_identity_digest_reconstructed": reconstructed.get("canonical_identity_digest") == snapshot.get("canonical_identity_digest"),
            }
            integration = {
                "schema_version": 3,
                "task_id": contract["task_id"],
                "contract_version": contract["contract_version"],
                "contract_digest": contract_digest,
                "implementation_snapshot_digest": snapshot["snapshot_digest"],
                "review_commit_sha": review_commit_sha,
                "review_report_digest": sha256_json(review),
                "acceptance_record_digest": sha256_json(acceptance),
                "repository_identity": actual_identity,
                "repository_root": str(root),
                "base_branch": base_branch,
                "base_branch_tip_sha": branch_tip,
                "merge_commit_sha": merge_sha,
                "pull_request": {
                    "provider": args.pr_provider if pr_populated else None,
                    "url": args.pr_url if pr_populated else None,
                    "number": args.pr_number if pr_populated else None,
                },
                "ci": {
                    "status": "success",
                    "verification": "controller_executed",
                    "provider": "local",
                    "workflow": "contract_post_merge_checks",
                    "url": None,
                    "run_id": None,
                    "verified_by": args.actor,
                    "verified_at": recorded_at,
                },
                "post_merge_verification": check_records,
                "release": {"reference": args.release_reference, "rollback": args.rollback},
                "closure_assurance": "local_verified",
                # Schema v3 (contract v2): local canonical-identity reconstruction + independent
                # review-object resolvability; remote durability is separated and never assumed.
                "local_reviewed_content_reconstructed": not canonical_mismatch,
                "local_identity_evidence": local_identity_evidence,
                "remote_durability_verified": False,
                "remote_durability_evidence": {
                    "status": "unverified",
                    "reason": "no remote publication verification requested for this integration",
                },
                "recorded_at": recorded_at,
            }
            integration["record_digest"] = digest_record(integration, "record_digest")
            atomic_write_json(safe_child(change_path, "integration-record.json"), integration)
            capabilities = project.setdefault("capabilities", {})
            capabilities["project_test_execution"] = True
            atomic_write_json(project_path, project)
        print(json.dumps(integration, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TimeoutError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
