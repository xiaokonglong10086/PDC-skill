#!/usr/bin/env python3
"""Capture a reviewable implementation as a durable Git commit and metadata snapshot."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from common import (
    IDENTITY_POLICY_V1,
    atomic_write_json,
    controller_lock,
    digest_record,
    git_is_ancestor,
    git_output,
    git_path_exists,
    git_show_bytes,
    identity_policy_of,
    load_json_object,
    normalize_repo_path,
    now_iso,
    path_allowed,
    path_included_in_identity,
    run_command,
    safe_child,
    sha256_bytes,
    sha256_file,
    sha256_json,
    validate_change_name,
    verify_git_commit,
)
from multi_change import assert_focused_change, validate_focused_partial_worktree
from validate_task_contract import validate_contract


def load_frozen_contract(change_path: Path, workflow: dict[str, Any]) -> tuple[dict[str, Any], str]:
    version = workflow.get("contract_version")
    digest = workflow.get("contract_digest")
    if not isinstance(version, int) or version < 1 or not isinstance(digest, str):
        raise ValueError("workflow state does not reference a frozen contract")
    contract_path = safe_child(change_path, "contracts", f"task-contract.v{version}.json")
    digest_path = safe_child(change_path, "contracts", f"task-contract.v{version}.sha256")
    contract = load_json_object(contract_path)
    errors = validate_contract(contract, frozen=True)
    if errors:
        raise ValueError("frozen contract is invalid: " + "; ".join(errors))
    actual = sha256_json(contract)
    recorded = digest_path.read_text(encoding="utf-8").strip()
    if actual != digest or actual != recorded:
        raise ValueError("frozen contract digest mismatch; contract may have been modified")
    return contract, actual


def changed_paths(root: Path, baseline: str, *, identity_policy: str = IDENTITY_POLICY_V1) -> list[str]:
    tracked_text = git_output(root, "diff", "--name-only", "--diff-filter=ACDMRTUXB", baseline, "--")
    untracked_text = git_output(root, "ls-files", "--others", "--exclude-standard")
    paths: set[str] = set()
    for text in (tracked_text, untracked_text):
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("warning:"):
                # Git may emit CRLF/LF normalization warnings to stdout; they are not paths.
                continue
            normalized = line.replace("\\", "/")
            if normalized and path_included_in_identity(normalized, identity_policy):
                paths.add(normalize_repo_path(normalized))
    return sorted(paths)


def build_worktree_manifest(root: Path, paths: list[str]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for relative in paths:
        path = safe_child(root, *relative.split("/"))
        if not path.exists():
            manifest.append({"path": relative, "state": "deleted", "sha256": None, "size": 0})
            continue
        if path.is_symlink():
            raise ValueError(f"symlink changes are not supported in implementation snapshots: {relative}")
        if not path.is_file():
            raise ValueError(f"changed path is not a regular file: {relative}")
        manifest.append(
            {"path": relative, "state": "present", "sha256": sha256_file(path), "size": path.stat().st_size}
        )
    return manifest


def _oid_length(root: Path) -> int:
    """Return the storage object-id length (40 for SHA-1, 64 for SHA-256)."""
    try:
        fmt = git_output(root, "rev-parse", "--show-object-format=storage").strip().lower()
    except ValueError:
        fmt = "sha1"
    return 64 if fmt == "sha256" else 40


def _zero_oid(root: Path) -> str:
    return "0" * _oid_length(root)


JOURNAL_SCHEMA_VERSION = 1
CAPTURE_OPERATION = "capture_implementation_snapshot"


def journal_path(control_root: Path, change_name: str) -> Path:
    return safe_child(control_root, "transactions", f"capture-{change_name}.json")


def _ref_state(root: Path, ref: str) -> str | None:
    """Return the current ref value, or None when the ref is absent."""
    try:
        return git_output(root, "rev-parse", "--verify", "--quiet", ref).lower() or None
    except ValueError:
        return None


def build_capture_journal(
    *,
    change_name: str,
    task_id: str,
    review_ref: str,
    expected_old_review_commit_sha: str | None,
    object_format: str,
    candidate_commit: str,
    review_tree: str,
    canonical_manifest: list[dict[str, Any]],
    snapshot_payload: dict[str, Any],
    snapshot_digest: str,
    workflow_payload: dict[str, Any],
) -> dict[str, Any]:
    journal = {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "operation": CAPTURE_OPERATION,
        "change": change_name,
        "task": task_id,
        "review_ref": review_ref,
        "expected_old_ref_state": "present" if expected_old_review_commit_sha is not None else "absent",
        "expected_old_review_commit_sha": expected_old_review_commit_sha,
        "repository_object_format": object_format,
        "candidate": {
            "review_commit_sha": candidate_commit,
            "review_tree_sha": review_tree,
            "canonical_manifest": canonical_manifest,
        },
        "snapshot_payload": snapshot_payload,
        "snapshot_digest": snapshot_digest,
        "workflow_payload": workflow_payload,
        "phases": [],
    }
    return journal


def journal_phase(journal: dict[str, Any], name: str) -> None:
    journal.setdefault("phases", []).append({"phase": name, "at": now_iso()})


def cas_publish_ref(root: Path, ref: str, candidate: str, expected_old: str | None) -> None:
    """Compare-and-swap the review ref: expected_old is the exact prior value (or None for absent → zero OID)."""
    zero = _zero_oid(root)
    expected = expected_old if expected_old is not None else zero
    result = run_command(("git", "update-ref", ref, candidate, expected), cwd=root)
    if result.returncode != 0:
        raise ValueError(f"review ref CAS failed:\n{result.stdout}")


def recover_capture_journal(root: Path, control_root: Path, change_path: Path, change_name: str) -> None:
    """Recover from a capture journal: idempotently converge ref/snapshot/workflow, or fail closed."""
    jpath = journal_path(control_root, change_name)
    if not jpath.is_file():
        return
    journal = load_json_object(jpath)
    if journal.get("operation") != CAPTURE_OPERATION or journal.get("change") != change_name:
        raise ValueError(f"unexpected capture journal at {jpath}")
    if journal.get("journal_digest") != digest_record(journal, "journal_digest"):
        raise ValueError("capture journal digest mismatch; refusing recovery")
    ref = str(journal["review_ref"])
    candidate = str(journal["candidate"]["review_commit_sha"])
    if "expected_old_review_commit_sha" not in journal:
        raise ValueError("capture journal missing expected_old_review_commit_sha; refusing recovery")
    expected_old = journal.get("expected_old_review_commit_sha")
    # Validate the expected_old_ref_state marker is consistent with the SHA/null expression:
    # present requires a 40/64-char object id; absent requires JSON null. Never guess from the
    # SHA field alone.
    state_marker = journal.get("expected_old_ref_state")
    if state_marker == "present" and (not isinstance(expected_old, str) or len(expected_old) not in (40, 64)):
        raise ValueError("capture journal inconsistent: expected_old_ref_state=present requires a 40/64-char object id")
    if state_marker == "absent" and expected_old is not None:
        raise ValueError("capture journal inconsistent: expected_old_ref_state=absent requires expected_old_review_commit_sha=null")
    if state_marker not in ("present", "absent"):
        raise ValueError("capture journal invalid expected_old_ref_state; refusing recovery")
    current = _ref_state(root, ref)
    if current == expected_old or (expected_old is None and current is None):
        # Ref untouched (or never existed): the journaled operation did not publish. Drop the
        # journal without touching snapshot/workflow bytes.
        try:
            jpath.unlink()
        except FileNotFoundError:
            pass
        return
    if current == candidate:
        # CAS succeeded (or an external actor created exactly the same candidate): idempotently
        # converge the two payloads, verify, then remove the journal.
        snapshot_path = safe_child(change_path, "implementation-snapshot.json")
        workflow_path = safe_child(change_path, "workflow-state.json")
        atomic_write_json(snapshot_path, journal["snapshot_payload"])
        atomic_write_json(workflow_path, journal["workflow_payload"])
        snapshot = load_json_object(snapshot_path)
        if snapshot.get("snapshot_digest") != journal["snapshot_digest"]:
            raise ValueError("recovered snapshot digest mismatch")
        workflow = load_json_object(workflow_path)
        if workflow.get("implementation_snapshot_digest") != journal["snapshot_digest"]:
            raise ValueError("recovered workflow snapshot binding mismatch")
        try:
            jpath.unlink()
        except FileNotFoundError:
            pass
        return
    raise ValueError(
        f"capture journal conflict: review ref is {current!r}, expected {expected_old!r} or candidate {candidate!r}; "
        "FAIL CLOSED — no overwrite, no rollback, no guessing"
    )


def read_capture_journal(control_root: Path, change_name: str) -> dict[str, Any] | None:
    jpath = journal_path(control_root, change_name)
    if not jpath.is_file():
        return None
    journal = load_json_object(jpath)
    if journal.get("journal_digest") != digest_record(journal, "journal_digest"):
        raise ValueError("capture journal digest mismatch")
    return journal


def git_output_bytes(root: Path, *args: str) -> bytes:
    """Run a git command in root and return raw stdout bytes (binary-safe)."""
    import subprocess as _subprocess
    result = _subprocess.run(
        ["git", *args], cwd=str(root), stdout=_subprocess.PIPE, stderr=_subprocess.STDOUT, check=False
    )
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed:\n{result.stdout.decode('utf-8', 'replace')}")
    return result.stdout


# Canonical Git clean policy for every staging command that constructs canonical identity
# and review commit trees. Explicit and machine-independent: the review identity must never
# inherit the user's core.autocrlf. core.autocrlf=input makes Git's clean conversion turn
# text CRLF deterministically into LF at add time (input direction only — no smudge side
# effects, so the review tree is identical whether the worktree was materialized CRLF by
# Windows core.autocrlf=true or LF by an LF-preserving/POSIX checkout). core.safecrlf=false
# keeps a mixed-EOL or already-LF text file from aborting the add. Git's own binary
# detection (NUL/8-bit bytes) still applies under this policy, so binary content is never
# text-normalized.
CANONICAL_GIT_CONFIG: tuple[str, ...] = (
    "-c",
    "core.autocrlf=input",
    "-c",
    "core.safecrlf=false",
)


def _canonical_git_argv(subcommand: Sequence[str]) -> tuple[str, ...]:
    """Full git argv for a canonical staging subcommand: `git -c ... -c ... <subcommand> args`."""
    return ("git", *CANONICAL_GIT_CONFIG, *subcommand)


def _build_canonical_index(root: Path, baseline: str, paths: list[str]) -> tuple[str, list[dict[str, Any]]]:
    """Build a canonical manifest from a temporary Git index (read-tree baseline, git add/rm, write-tree).

    Every command runs under the explicit machine-independent canonical policy
    (CANONICAL_GIT_CONFIG: core.autocrlf=input, core.safecrlf=false), so clean/filter
    normalization applies deterministically and the tree/manifest identity never depends on
    the machine's core.autocrlf. Object reads (cat-file) are config-independent.
    """
    fd, temp_name = tempfile.mkstemp(prefix="pdc-canonical-index-")
    os.close(fd)
    temp_index = Path(temp_name)
    temp_index.unlink()
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(temp_index)
    try:
        result = run_command(_canonical_git_argv(("read-tree", baseline)), cwd=root, env=env)
        if result.returncode != 0:
            raise ValueError(f"git read-tree failed:\n{result.stdout}")
        for relative in paths:
            path = safe_child(root, *relative.split("/"))
            if path.exists():
                result = run_command(_canonical_git_argv(("add", "--", relative)), cwd=root, env=env)
            else:
                result = run_command(
                    _canonical_git_argv(("rm", "--cached", "--ignore-unmatch", "--", relative)), cwd=root, env=env
                )
            if result.returncode != 0:
                raise ValueError(f"failed to stage canonical path {relative}:\n{result.stdout}")
        tree = run_command(_canonical_git_argv(("write-tree",)), cwd=root, env=env, check=True).stdout.strip().lower()
        entries_text = run_command(
            _canonical_git_argv(("ls-files", "--stage", "--", *paths)), cwd=root, env=env, check=True
        ).stdout
        entries: dict[str, dict[str, Any]] = {}
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
                "mode": mode,
                "blob_sha": oid,
                "canonical_size": len(blob_bytes),
                "state": "present",
                "sha256": sha256_bytes(blob_bytes),
                "size": len(blob_bytes),
            }
        for relative in paths:
            if relative not in entries:
                entries[relative] = {
                    "path": relative,
                    "state": "deleted",
                    "mode": None,
                    "blob_sha": None,
                    "canonical_size": 0,
                    "sha256": None,
                    "size": 0,
                }
        manifest = []
        for relative in sorted(entries):
            e = entries[relative]
            manifest.append({
                "path": relative,
                "state": e["state"],
                "mode": e["mode"],
                "blob_sha": e["blob_sha"],
                "canonical_size": e["canonical_size"],
                "sha256": e["sha256"],
                "size": e["size"],
            })
        return tree, manifest
    finally:
        try:
            temp_index.unlink()
        except FileNotFoundError:
            pass


CANONICAL_FORMAT_VERSION = 1


def canonical_identity_digest(baseline: str, tree: str, manifest: list[dict[str, Any]]) -> str:
    rows = []
    for item in manifest:
        rows.append((item["path"], item["mode"], item["blob_sha"], item["canonical_size"]))
    payload = {"baseline_sha": baseline, "review_tree_sha": tree, "entries": sorted(rows)}
    return sha256_json(payload)


def create_review_commit(root: Path, baseline: str, paths: list[str], change_name: str, task_id: str) -> tuple[str, str, str]:
    """Create the review commit from a temporary index under the same explicit machine-independent
    canonical Git clean policy used for the canonical manifest (CANONICAL_GIT_CONFIG), so the review
    tree and the canonical tree are built from the exact same normalized blobs.
    """
    fd, temp_name = tempfile.mkstemp(prefix="pdc-index-")
    os.close(fd)
    temp_index = Path(temp_name)
    temp_index.unlink()
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(temp_index)
    try:
        result = run_command(_canonical_git_argv(("read-tree", baseline)), cwd=root, env=env)
        if result.returncode != 0:
            raise ValueError(f"git read-tree failed:\n{result.stdout}")
        for relative in paths:
            path = safe_child(root, *relative.split("/"))
            if path.exists():
                result = run_command(_canonical_git_argv(("add", "--", relative)), cwd=root, env=env)
            else:
                result = run_command(
                    _canonical_git_argv(("rm", "--cached", "--ignore-unmatch", "--", relative)), cwd=root, env=env
                )
            if result.returncode != 0:
                raise ValueError(f"failed to stage review path {relative}:\n{result.stdout}")
        tree = run_command(_canonical_git_argv(("write-tree",)), cwd=root, env=env, check=True).stdout.strip().lower()
        commit = run_command(
            _canonical_git_argv(
                ("commit-tree", tree, "-p", baseline, "-m", f"pdc review snapshot {task_id}")
            ),
            cwd=root,
            env=env,
            check=True,
        ).stdout.strip().lower()
        ref = f"refs/pdc/reviews/{change_name}/latest"
        # Candidate creation must NOT move the review ref; publication happens later via CAS
        # after the journal is written and read back (contract AC-3).
        return commit, tree, ref
    finally:
        try:
            temp_index.unlink()
        except FileNotFoundError:
            pass


def validate_snapshot(snapshot: dict[str, Any], contract: dict[str, Any], contract_digest: str) -> list[str]:
    errors: list[str] = []
    schema = snapshot.get("schema_version")
    if schema not in (2, 3):
        errors.append(f"snapshot schema_version must be 2 or 3: {schema!r}")
    if schema == 3:
        try:
            identity_policy_of(snapshot)
        except ValueError as exc:
            errors.append(str(exc))
    if snapshot.get("task_id") != contract.get("task_id"):
        errors.append("snapshot task_id does not match contract")
    if snapshot.get("contract_version") != contract.get("contract_version"):
        errors.append("snapshot contract_version does not match contract")
    if snapshot.get("contract_digest") != contract_digest:
        errors.append("snapshot contract_digest does not match frozen contract")
    if snapshot.get("baseline_sha") != contract.get("baseline", {}).get("sha"):
        errors.append("snapshot baseline_sha does not match contract")
    for field in ("review_commit_sha", "review_tree_sha"):
        value = snapshot.get(field)
        if not isinstance(value, str) or len(value) not in (40, 64):
            errors.append(f"snapshot {field} must be a full 40- or 64-character Git object id")
    canonical = snapshot.get("canonical_format_version")
    if canonical is not None and canonical != CANONICAL_FORMAT_VERSION:
        errors.append(f"snapshot canonical_format_version must be {CANONICAL_FORMAT_VERSION}")
    if canonical is not None:
        expected_identity = canonical_identity_digest(
            snapshot.get("baseline_sha", ""), snapshot.get("review_tree_sha", ""), snapshot.get("file_manifest", [])
        )
        if snapshot.get("canonical_identity_digest") != expected_identity:
            errors.append("canonical_identity_digest does not match baseline/tree/manifest")
    if not isinstance(snapshot.get("review_ref"), str) or not snapshot.get("review_ref", "").startswith("refs/pdc/reviews/"):
        errors.append("snapshot review_ref must be a refs/pdc/reviews reference")
    manifest = snapshot.get("file_manifest")
    changed = snapshot.get("changed_files")
    if not isinstance(manifest, list) or not manifest:
        errors.append("snapshot file_manifest must be a non-empty list")
    if not isinstance(changed, list) or not changed:
        errors.append("snapshot changed_files must be a non-empty list")
    if isinstance(manifest, list) and isinstance(changed, list):
        manifest_paths = [item.get("path") for item in manifest if isinstance(item, dict)]
        if manifest_paths != changed:
            errors.append("snapshot manifest paths must exactly match changed_files in sorted order")
    expected_digest = digest_record(snapshot, "snapshot_digest")
    if snapshot.get("snapshot_digest") != expected_digest:
        errors.append("snapshot_digest does not match snapshot content")
    return errors


def validate_snapshot_git(root: Path, snapshot: dict[str, Any], contract: dict[str, Any],
                          *, require_review_ref: bool = True) -> list[str]:
    errors: list[str] = []
    try:
        review_commit = verify_git_commit(root, str(snapshot.get("review_commit_sha", "")))
        baseline = str(contract.get("baseline", {}).get("sha", ""))
        if not git_is_ancestor(root, baseline, review_commit):
            errors.append("review commit does not descend from contract baseline")
        actual_tree = git_output(root, "show", "-s", "--format=%T", review_commit).lower()
        if actual_tree != snapshot.get("review_tree_sha"):
            errors.append("review tree does not match snapshot")
        actual_changed = sorted(
            line.replace("\\", "/")
            for line in git_output(root, "diff", "--name-only", baseline, review_commit, "--").splitlines()
            if line.strip() and path_included_in_identity(line.replace("\\", "/").strip(), identity_policy_of(snapshot))
        )
        if actual_changed != snapshot.get("changed_files"):
            errors.append("review commit changed files do not match snapshot")
        allowed = contract.get("allowed_files", [])
        for path in actual_changed:
            if not path_allowed(path, allowed):
                errors.append(f"review commit contains out-of-scope file {path}")
        # Review ref must point at the snapshot review commit for active snapshots; closed-history
        # callers pass require_review_ref=False to skip this requirement.
        for item in snapshot.get("file_manifest", []):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", ""))
            exists = git_path_exists(root, review_commit, path)
            if item.get("state") == "deleted":
                if exists:
                    errors.append(f"review commit unexpectedly contains deleted file {path}")
            elif item.get("state") == "present":
                if not exists:
                    errors.append(f"review commit is missing file {path}")
                else:
                    content = git_show_bytes(root, review_commit, path)
                    expected_sha = item.get("sha256")
                    expected_size = item.get("canonical_size", item.get("size"))
                    if expected_sha is not None and sha256_bytes(content) != expected_sha:
                        errors.append(f"review commit content differs from snapshot for {path}")
                    if expected_size is not None and len(content) != expected_size:
                        errors.append(f"review commit content size differs from snapshot for {path}")
        if require_review_ref:
            try:
                ref_tip = git_output(root, "rev-parse", "--verify", str(snapshot.get("review_ref")))
                if ref_tip.lower() != str(snapshot.get("review_commit_sha", "")).lower():
                    errors.append("durable review ref no longer identifies the snapshot review commit")
            except ValueError as exc:
                errors.append(str(exc))
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def validate_current_worktree(root: Path, snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        current_paths = changed_paths(
            root, str(snapshot.get("baseline_sha", "")), identity_policy=identity_policy_of(snapshot)
        )
        if current_paths != snapshot.get("changed_files"):
            errors.append("working tree changed after implementation snapshot")
            return errors
        if snapshot.get("canonical_format_version") is not None:
            # Canonical comparison: rebuild the canonical tree/manifest from the temporary index so
            # raw CRLF/LF working-tree bytes do not matter — only normalized Git blob content does.
            try:
                current_tree, current_manifest = _build_canonical_index(
                    root, str(snapshot.get("baseline_sha", "")), current_paths
                )
            except ValueError as exc:
                errors.append(str(exc))
                return errors
            if current_tree != snapshot.get("review_tree_sha"):
                errors.append("working tree canonical tree changed after implementation snapshot")
            if current_manifest != snapshot.get("file_manifest"):
                errors.append("working tree canonical manifest changed after implementation snapshot")
        else:
            current_manifest = build_worktree_manifest(root, current_paths)
            if current_manifest != snapshot.get("file_manifest"):
                errors.append("working tree content changed after implementation snapshot")
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--change", help="Change directory name; defaults to current_change")
    parser.add_argument("--recover-only", action="store_true", help="Recover from an existing capture journal without publishing a new candidate")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        with controller_lock(control_root):
            project_state = load_json_object(safe_child(control_root, "project-state.json"))
            change_name = args.change or project_state.get("current_change")
            if not isinstance(change_name, str):
                raise ValueError("no current change; pass --change")
            validate_change_name(change_name)
            assert_focused_change(control_root, change_name, project=project_state)
            change_path = safe_child(control_root, "changes", change_name)
            workflow_path = safe_child(change_path, "workflow-state.json")
            workflow = load_json_object(workflow_path)

            if args.recover_only:
                recover_capture_journal(root, control_root, change_path, change_name)
                print(f"Recovered capture journal for {change_name}")
                return 0

            if workflow.get("status") != "implementing":
                raise ValueError("implementation snapshot can be captured only while status=implementing")
            contract, contract_digest = load_frozen_contract(change_path, workflow)
            validate_focused_partial_worktree(root, contract)
            baseline = contract["baseline"]["sha"]
            paths = changed_paths(root, baseline, identity_policy=IDENTITY_POLICY_V1)
            if not paths:
                raise ValueError("no implementation changes found")
            disallowed = [path for path in paths if not path_allowed(path, contract["allowed_files"])]
            if disallowed:
                raise ValueError("changed files exceed allowed scope: " + ", ".join(disallowed))
            canonical_tree, canonical_manifest = _build_canonical_index(root, baseline, paths)
            review_commit, review_tree, review_ref = create_review_commit(
                root, baseline, paths, change_name, str(contract["task_id"])
            )
            if canonical_tree != review_tree:
                raise ValueError("canonical tree does not match review commit tree")
            snapshot: dict[str, Any] = {
                "schema_version": 3,
                "identity_policy": IDENTITY_POLICY_V1,
                "canonical_format_version": CANONICAL_FORMAT_VERSION,
                "task_id": contract["task_id"],
                "contract_version": contract["contract_version"],
                "contract_digest": contract_digest,
                "baseline_sha": baseline,
                "review_commit_sha": review_commit,
                "review_tree_sha": review_tree,
                "review_ref": review_ref,
                "captured_at": now_iso(),
                "git_status": git_output(root, "status", "--short"),
                "changed_files": paths,
                "file_manifest": canonical_manifest,
            }
            snapshot["canonical_identity_digest"] = canonical_identity_digest(baseline, review_tree, canonical_manifest)
            snapshot["snapshot_digest"] = digest_record(snapshot, "snapshot_digest")
            errors = validate_snapshot(snapshot, contract, contract_digest)
            # Pre-CAS validation must not require the review ref (it is published by CAS later).
            errors.extend(validate_snapshot_git(root, snapshot, contract, require_review_ref=False))
            errors.extend(validate_current_worktree(root, snapshot))
            if errors:
                raise ValueError("invalid implementation snapshot: " + "; ".join(errors))

            snapshot_path = safe_child(change_path, "implementation-snapshot.json")
            workflow_payload = dict(workflow)
            workflow_payload["implementation_snapshot_digest"] = snapshot["snapshot_digest"]
            workflow_payload["review_commit_sha"] = review_commit
            workflow_payload["test_execution_record_digest"] = None
            workflow_payload["updated_at"] = now_iso()

            # 1. Expected-old for CAS: exact prior ref value, or explicit absent (None).
            prior_ref = _ref_state(root, review_ref)
            expected_old = prior_ref
            # 2. Build and write the capture journal before any publish.
            object_format = git_output(root, "rev-parse", "--show-object-format=storage").strip().lower()
            journal = build_capture_journal(
                change_name=change_name,
                task_id=str(contract["task_id"]),
                review_ref=review_ref,
                expected_old_review_commit_sha=expected_old,
                object_format=object_format,
                candidate_commit=review_commit,
                review_tree=review_tree,
                canonical_manifest=canonical_manifest,
                snapshot_payload=snapshot,
                snapshot_digest=snapshot["snapshot_digest"],
                workflow_payload=workflow_payload,
            )
            journal_phase(journal, "journal_written")
            journal["journal_digest"] = digest_record(journal, "journal_digest")
            jpath = journal_path(control_root, change_name)
            atomic_write_json(jpath, journal)
            # 3. Read back and verify the journal before publishing.
            reloaded = load_json_object(jpath)
            if reloaded.get("journal_digest") != digest_record(reloaded, "journal_digest"):
                raise ValueError("capture journal read-back verification failed")
            # 4. Publish the review ref via CAS (zero OID for first publication).
            cas_publish_ref(root, review_ref, review_commit, expected_old)
            # 5. Converge snapshot + workflow payloads.
            atomic_write_json(snapshot_path, snapshot)
            atomic_write_json(workflow_path, workflow_payload)
            # 6. Verify convergence (ref == candidate; snapshot/workflow payloads), then remove journal.
            converged_ref = _ref_state(root, review_ref)
            if converged_ref != review_commit:
                raise ValueError("review ref does not equal the published candidate after CAS")
            check_snapshot = load_json_object(snapshot_path)
            check_workflow = load_json_object(workflow_path)
            if check_snapshot.get("snapshot_digest") != snapshot["snapshot_digest"]:
                raise ValueError("snapshot convergence verification failed")
            if check_workflow.get("implementation_snapshot_digest") != snapshot["snapshot_digest"]:
                raise ValueError("workflow convergence verification failed")
            journal_phase(journal, "converged")
            try:
                jpath.unlink()
            except FileNotFoundError:
                pass
        print(f"Captured implementation snapshot: {snapshot_path}")
        print(f"Review commit: {review_commit}")
        print(f"Snapshot digest: {snapshot['snapshot_digest']}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
