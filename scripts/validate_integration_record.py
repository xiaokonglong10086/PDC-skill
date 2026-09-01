#!/usr/bin/env python3
"""Validate integration and closure evidence against reviewed and accepted artifacts."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from capture_implementation_snapshot import (
    canonical_identity_digest,
    git_output_bytes,
    load_frozen_contract,
    validate_snapshot,
    validate_snapshot_git,
)
from common import (
    IDENTITY_POLICY_LEGACY,
    IDENTITY_POLICY_V1,
    actual_repository_identity,
    current_branch,
    digest_record,
    ensure_known_keys,
    ensure_required_keys,
    git_is_ancestor,
    git_output,
    git_path_exists,
    git_show_bytes,
    identity_policy_of,
    load_json_object,
    non_control_git_status,
    path_allowed,
    path_included_in_identity,
    require_iso8601,
    require_list,
    require_object,
    require_sha,
    require_sha256,
    require_string,
    run_command,
    safe_child,
    sha256_bytes,
    sha256_file,
    sha256_json,
    verify_git_branch,
    verify_git_commit,
)
from validate_acceptance_record import validate_acceptance
from validate_review_report import validate_review
CLOSURE_ASSURANCE = {"local_verified", "remote_verified", "externally_attested"}
CI_VERIFICATION = {"controller_executed", "connector_verified", "external_attestation"}
FIELDS = {
    "schema_version", "task_id", "contract_version", "contract_digest",
    "implementation_snapshot_digest", "review_commit_sha", "review_report_digest",
    "acceptance_record_digest", "repository_identity", "repository_root", "base_branch",
    "base_branch_tip_sha", "merge_commit_sha", "pull_request", "ci",
    "post_merge_verification", "release", "closure_assurance", "recorded_at", "record_digest",
    # Schema v3 (contract v2): canonical reviewed-content reconstruction + remote durability facts.
    "local_reviewed_content_reconstructed", "local_identity_evidence",
    "remote_durability_verified", "remote_durability_evidence",
}


def merged_changed_paths(
    root: Path, baseline: str, merge_sha: str, *, identity_policy: str = IDENTITY_POLICY_LEGACY
) -> list[str]:
    text = git_output(root, "diff", "--name-only", "--diff-filter=ACDMRTUXB", baseline, merge_sha, "--")
    return sorted(
        path.replace("\\", "/")
        for path in text.splitlines()
        if path.strip() and path_included_in_identity(path.replace("\\", "/").strip(), identity_policy)
    )


def validate_merged_content(errors: list[str], root: Path, merge_sha: str, snapshot: dict[str, Any]) -> None:
    for index, item in enumerate(snapshot.get("file_manifest", []), start=1):
        if not isinstance(item, dict):
            errors.append(f"snapshot file_manifest[{index}] must be an object")
            continue
        path = str(item.get("path", ""))
        state = item.get("state")
        try:
            exists = git_path_exists(root, merge_sha, path)
            if state == "deleted":
                if exists:
                    errors.append(f"merged commit unexpectedly contains deleted file {path}")
            elif state == "present":
                if not exists:
                    errors.append(f"merged commit is missing reviewed file {path}")
                else:
                    actual = git_show_bytes(root, merge_sha, path)
                    if sha256_bytes(actual) != item.get("sha256") or len(actual) != item.get("size"):
                        errors.append(f"merged content for {path} differs from reviewed commit")
            else:
                errors.append(f"snapshot file_manifest[{index}].state is invalid")
        except ValueError as exc:
            errors.append(str(exc))


def _reconstruct_canonical_merge(root: Path, baseline: str, merge_sha: str,
                                 snapshot: dict[str, Any]) -> dict:
    """Merge-oriented canonical reconstruction (integration-evidence semantics).

    The reviewed changed-file set is derived from the MERGE DIFF (baseline..merge_sha), never
    from the working tree, and the canonical tree/manifest are rebuilt from the merge commit's
    tree via a temporary index. This is the correct identity basis for an already-integrated
    Work, whose working tree legitimately contains unrelated later commits."""
    policy = str(snapshot.get("identity_policy") or IDENTITY_POLICY_V1)
    paths = merged_changed_paths(root, baseline, merge_sha, identity_policy=policy)
    result: dict = {"changed_files": paths, "mismatch": []}
    fd, temp_name = tempfile.mkstemp(prefix="pdc-canonical-merge-")
    os.close(fd)
    temp_index = Path(temp_name)
    temp_index.unlink()
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(temp_index)
    try:
        r1 = run_command(("git", "read-tree", baseline), cwd=root, env=env)
        if r1.returncode != 0:
            raise ValueError(f"read-tree baseline failed:\n{r1.stdout}")
        r2 = run_command(("git", "read-tree", merge_sha), cwd=root, env=env)
        if r2.returncode != 0:
            raise ValueError(f"read-tree merge failed:\n{r2.stdout}")
        tree = run_command(("git", "write-tree"), cwd=root, env=env, check=True).stdout.strip().lower()
        entries_text = run_command(("git", "ls-files", "--stage", "--", *paths), cwd=root,
                                   env=env, check=True).stdout
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


def validate_integration(
    record: dict[str, Any],
    root: Path,
    contract: dict[str, Any],
    contract_digest: str,
    snapshot: dict[str, Any],
    review: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    allow_closed_history: bool = False,
    change_path: Path,
) -> list[str]:
    errors: list[str] = []
    ensure_known_keys(errors, "integration", record, FIELDS)
    ensure_required_keys(errors, "integration", record, FIELDS)
    schema = record.get("schema_version")
    if schema not in (2, 3):
        errors.append("integration schema_version must equal 2 or 3")
    if record.get("task_id") != contract.get("task_id"):
        errors.append("integration task_id does not match contract")
    if record.get("contract_version") != contract.get("contract_version"):
        errors.append("integration contract_version does not match contract")
    if record.get("contract_digest") != contract_digest:
        errors.append("integration contract_digest does not match frozen contract")
    if record.get("implementation_snapshot_digest") != snapshot.get("snapshot_digest"):
        errors.append("integration implementation_snapshot_digest does not match reviewed snapshot")
    if record.get("review_commit_sha") != snapshot.get("review_commit_sha"):
        errors.append("integration review_commit_sha does not match reviewed Git commit")
    if record.get("review_report_digest") != sha256_json(review):
        errors.append("integration review_report_digest does not match review report")
    if record.get("acceptance_record_digest") != sha256_json(acceptance):
        errors.append("integration acceptance_record_digest does not match acceptance record")
    if review.get("verdict") != "PASS":
        errors.append("integration requires a PASS review")
    if acceptance.get("decision") != "accepted":
        errors.append("integration requires accepted product-owner acceptance")
    if record.get("record_digest") != digest_record(record, "record_digest"):
        errors.append("integration record_digest does not match record content")
    require_iso8601(errors, "recorded_at", record.get("recorded_at"))

    # Contract-v2 schema-v3 semantics: the integration commit must reconstruct the reviewed canonical
    # identity (no ancestry requirement); the local claim must never be stronger than independently
    # re-verified evidence; remote durability only when truly verified from a fresh normal clone.
    if schema == 3:
        merge_sha = record.get("merge_commit_sha")
        if isinstance(merge_sha, str) and root is not None:
            try:
                reconstructed = _reconstruct_canonical_merge(
                    root, str(contract.get("baseline", {}).get("sha", "")), merge_sha, snapshot)
                mismatch = reconstructed.get("mismatch") or []
            except Exception as exc:  # reconstruction failure is itself a finding
                mismatch = [f"canonical reconstruction failed: {exc}"]
            if record.get("local_reviewed_content_reconstructed") is True and mismatch:
                errors.append("local reviewed-content reconstruction claim is stronger than independently re-verified evidence: " + "; ".join(mismatch))
            if record.get("local_reviewed_content_reconstructed") is True:
                evidence = record.get("local_identity_evidence") or {}
                for field in ("reviewed_changed_file_set_reconstructed", "review_tree_sha_reconstructed", "canonical_identity_digest_reconstructed"):
                    if evidence.get(field) is not True:
                        errors.append(f"local_identity_evidence.{field} must be true when local_reviewed_content_reconstructed=true")
        remote_verified = record.get("remote_durability_verified") is True
        remote_evidence = record.get("remote_durability_evidence") or {}
        if remote_verified:
            if remote_evidence.get("status") != "real_publication":
                errors.append("remote_durability_verified=true requires evidence status real_publication")
            if remote_evidence.get("ref_kind") != "heads":
                errors.append("remote_durability_verified=true requires a normal refs/heads/** remote ref")
            if not remote_evidence.get("observed_tip_verified"):
                errors.append("remote_durability_verified=true requires observed remote tip verification")
            if remote_evidence.get("standard_fetch_only") is not True:
                errors.append("remote_durability_verified=true requires standard clone/fetch without custom refspec")
            if remote_evidence.get("fresh_clone_no_hidden_refs") is not True:
                errors.append("remote_durability_verified=true requires a fresh clone without original-worktree or hidden-ref dependency")
            for field in ("baseline_recoverable", "integration_commit_recoverable", "canonical_identity_reconstructed"):
                if remote_evidence.get(field) is not True:
                    errors.append(f"remote_durability_verified=true requires {field}")
        elif remote_evidence.get("status") == "synthetic_mechanism":
            # A synthetic mechanism (e.g. local path/bare remote) may never upgrade the claim.
            if record.get("remote_durability_verified") is True:
                errors.append("synthetic remote evidence cannot set remote_durability_verified=true")


    actual_identity = actual_repository_identity(root)
    identity = require_string(errors, "repository_identity", record.get("repository_identity"))
    if identity != contract.get("repository_identity") or identity != actual_identity:
        errors.append("integration repository identity does not match frozen contract and current repository")
    repository_root = require_string(errors, "repository_root", record.get("repository_root"))
    if not allow_closed_history:
        if repository_root != contract.get("repository_root") or Path(repository_root).resolve() != root.resolve():
            errors.append("integration repository_root does not match frozen contract and current repository")
    # Closed history: repository_root is historical metadata only; do not require the absolute
    # path to match the current checkout, and do not require the original feature branch ref /
    # current HEAD / worktree to exist at the old execution site. Logical repository identity
    # (repository_identity) is still strictly matched above.

    base_branch = require_string(errors, "base_branch", record.get("base_branch"))
    if base_branch != contract.get("baseline", {}).get("branch"):
        errors.append("integration base_branch does not match frozen baseline.branch")
    branch_tip_recorded = require_sha(errors, "base_branch_tip_sha", record.get("base_branch_tip_sha"))
    merge_sha = require_sha(errors, "merge_commit_sha", record.get("merge_commit_sha"))

    pr = require_object(errors, "pull_request", record.get("pull_request"))
    ensure_known_keys(errors, "pull_request", pr, {"provider", "url", "number"})
    ensure_required_keys(errors, "pull_request", pr, {"provider", "url", "number"})
    if pr.get("provider") is not None:
        require_string(errors, "pull_request.provider", pr.get("provider"))
        require_string(errors, "pull_request.url", pr.get("url"))
        if not isinstance(pr.get("number"), int) or isinstance(pr.get("number"), bool) or pr.get("number") < 1:
            errors.append("pull_request.number must be a positive integer when a PR is recorded")
    elif pr.get("url") is not None or pr.get("number") is not None:
        errors.append("pull_request provider, url, and number must be all null or all populated")

    ci = require_object(errors, "ci", record.get("ci"))
    ensure_known_keys(errors, "ci", ci, {"status", "verification", "provider", "workflow", "url", "run_id", "verified_by", "verified_at"})
    ensure_required_keys(errors, "ci", ci, {"status", "verification", "provider", "workflow", "url", "run_id", "verified_by", "verified_at"})
    if ci.get("status") != "success":
        errors.append("ci.status must be success")
    verification = require_string(errors, "ci.verification", ci.get("verification"))
    if verification and verification not in CI_VERIFICATION:
        errors.append(f"ci.verification must be one of {sorted(CI_VERIFICATION)}")
    require_string(errors, "ci.provider", ci.get("provider"))
    require_string(errors, "ci.workflow", ci.get("workflow"))
    require_string(errors, "ci.verified_by", ci.get("verified_by"))
    require_iso8601(errors, "ci.verified_at", ci.get("verified_at"))
    if verification == "connector_verified":
        require_string(errors, "ci.url", ci.get("url"))
        require_string(errors, "ci.run_id", ci.get("run_id"))

    checks = require_list(errors, "post_merge_verification", record.get("post_merge_verification"))
    expected_checks = {str(item["id"]): item for item in contract.get("post_merge_checks", []) if isinstance(item, dict)}
    seen: set[str] = set()
    # The actual change directory is supplied by the caller (already-resolved change name); the
    # change directory is NEVER re-derived from contract task_id+slug here.
    for index, item in enumerate(checks, start=1):
        check = require_object(errors, f"post_merge_verification[{index}]", item)
        ensure_known_keys(errors, f"post_merge_verification[{index}]", check, {"id", "command", "expected_exit_code", "actual_exit_code", "stdout_sha256", "log_path", "executed_at", "executor"})
        ensure_required_keys(errors, f"post_merge_verification[{index}]", check, {"id", "command", "expected_exit_code", "actual_exit_code", "stdout_sha256", "log_path", "executed_at", "executor"})
        check_id = require_string(errors, f"post_merge_verification[{index}].id", check.get("id"))
        if check_id in seen:
            errors.append(f"post_merge_verification contains duplicate id {check_id}")
        seen.add(check_id)
        expected = expected_checks.get(check_id)
        if expected is None:
            errors.append(f"post_merge_verification references unknown check {check_id}")
            continue
        if check.get("command") != expected.get("command"):
            errors.append(f"post-merge command for {check_id} differs from frozen contract")
        if check.get("expected_exit_code") != expected.get("expected_exit_code"):
            errors.append(f"expected exit code for {check_id} differs from frozen contract")
        if check.get("actual_exit_code") != expected.get("expected_exit_code"):
            errors.append(f"post-merge check {check_id} did not return its expected exit code")
        require_sha256(errors, f"post_merge_verification[{index}].stdout_sha256", check.get("stdout_sha256"))
        require_iso8601(errors, f"post_merge_verification[{index}].executed_at", check.get("executed_at"))
        require_string(errors, f"post_merge_verification[{index}].executor", check.get("executor"))
        log_rel = require_string(errors, f"post_merge_verification[{index}].log_path", check.get("log_path"))
        try:
            log_path = safe_child(change_path, *log_rel.replace("\\", "/").split("/"))
            evidence_root = safe_child(change_path, "evidence", "post-merge")
            if evidence_root not in log_path.parents:
                errors.append(f"post-merge log for {check_id} is outside evidence/post-merge")
            elif not log_path.is_file():
                errors.append(f"post-merge log for {check_id} is missing")
            elif sha256_file(log_path) != check.get("stdout_sha256"):
                errors.append(f"post-merge log digest for {check_id} does not match")
        except ValueError as exc:
            errors.append(str(exc))
    if seen != set(expected_checks):
        missing = sorted(set(expected_checks) - seen)
        if missing:
            errors.append("post_merge_verification is missing checks: " + ", ".join(missing))

    release = require_object(errors, "release", record.get("release"))
    ensure_known_keys(errors, "release", release, {"reference", "rollback"})
    ensure_required_keys(errors, "release", release, {"reference", "rollback"})
    require_string(errors, "release.rollback", release.get("rollback"))

    assurance = require_string(errors, "closure_assurance", record.get("closure_assurance"))
    if assurance and assurance not in CLOSURE_ASSURANCE:
        errors.append(f"closure_assurance must be one of {sorted(CLOSURE_ASSURANCE)}")
    if assurance == "local_verified" and verification != "controller_executed":
        errors.append("local_verified requires controller_executed verification")
    if assurance == "remote_verified" and verification != "connector_verified":
        errors.append("remote_verified requires connector_verified CI evidence")
    if assurance == "externally_attested" and verification != "external_attestation":
        errors.append("externally_attested requires external_attestation")

    errors.extend(f"snapshot: {error}" for error in validate_snapshot(snapshot, contract, contract_digest))
    snapshot_git_errors = validate_snapshot_git(root, snapshot, contract)
    if allow_closed_history:
        # Closed history: the original review ref may legitimately be gone; its absence is not a
        # validation failure. All immutable object/tree/manifest/digest checks remain enforced.
        snapshot_git_errors = [
            e for e in snapshot_git_errors
            if "review ref" not in e and "durable review ref" not in e
        ]
    errors.extend(f"snapshot-git: {error}" for error in snapshot_git_errors)
    # Integration-evidence semantics: the reviewed bytes are already integrated into main, so the
    # current working tree legitimately differs from the old review snapshot. Review and
    # acceptance are therefore validated with the COMPLETE validators in integration-evidence
    # mode (explicit change context, require_snapshot_worktree=False): only the current-worktree
    # equality check is skipped; frozen tests existence/order/commands/results, execution-record
    # schema/timestamps/isolation/logs/digests/overall status, frozen acceptance criteria,
    # tests_checked, evidence_checked, manual scenarios, and all digest bindings stay fully
    # enforced and FAIL CLOSED on any missing, tampered, or re-wired evidence.
    try:
        ter_record = load_json_object(safe_child(change_path, "test-execution-record.json"))
    except (OSError, ValueError):
        ter_record = None
    try:
        change_workflow = load_json_object(safe_child(change_path, "workflow-state.json"))
    except (OSError, ValueError):
        change_workflow = None
    if ter_record is not None and change_workflow is not None:
        errors.extend(f"review: {error}" for error in validate_review(
            review, contract, contract_digest, snapshot, root,
            execution_record=ter_record, workflow=change_workflow, change_path=change_path,
            require_snapshot_worktree=False))
        errors.extend(f"acceptance: {error}" for error in validate_acceptance(
            acceptance, contract, contract_digest, snapshot, review, root,
            execution_record=ter_record, workflow=change_workflow, change_path=change_path,
            require_snapshot_worktree=False))
    else:
        errors.append("review: test-execution-record.json is missing or cannot be resolved")
    if review.get("verdict") != "PASS":
        errors.append("review verdict must be PASS")
    required_ac = {str(item["id"]) for item in contract.get("acceptance_criteria", []) if isinstance(item, dict)}
    checked_ac = {str(item.get("id")) for item in review.get("checked_criteria", []) if isinstance(item, dict)}
    if checked_ac != required_ac:
        errors.append("review PASS must check every acceptance criterion exactly once")
    if any(str(item.get("result")) != "satisfied"
           for item in review.get("checked_criteria", []) if isinstance(item, dict)):
        errors.append("review PASS requires every checked criterion result=satisfied")
    if acceptance.get("decision") != "accepted":
        errors.append("acceptance: decision must be accepted")
    if record.get("acceptance_record_digest") != sha256_json(acceptance):
        errors.append("acceptance: acceptance_record_digest does not match acceptance record")
    for field in ("tester", "environment", "recorded_at"):
        if not isinstance(acceptance.get(field), str) or not acceptance[field]:
            errors.append(f"acceptance: {field} must be a non-empty string")
    if not isinstance(acceptance.get("scenarios"), list) or not acceptance["scenarios"]:
        errors.append("acceptance: scenarios must be a non-empty list")
    if merge_sha:
        try:
            merge_sha = verify_git_commit(root, merge_sha)
            if not git_is_ancestor(root, str(contract.get("baseline", {}).get("sha", "")), merge_sha):
                errors.append("merge commit does not contain frozen baseline")
            if not allow_closed_history:
                branch_tip = verify_git_branch(root, base_branch)
                recorded_tip = verify_git_commit(root, branch_tip_recorded)
                if not git_is_ancestor(root, merge_sha, recorded_tip):
                    errors.append("merge commit is not contained in recorded base-branch tip")
                if not git_is_ancestor(root, merge_sha, branch_tip):
                    errors.append("merge commit is no longer contained in current base branch")
            actual_changed = merged_changed_paths(
                root,
                str(contract.get("baseline", {}).get("sha", "")),
                merge_sha,
                identity_policy=identity_policy_of(snapshot),
            )
            if actual_changed != snapshot.get("changed_files"):
                errors.append("merged changed-file set differs from reviewed snapshot")
            disallowed = [path for path in actual_changed if not path_allowed(path, contract.get("allowed_files", []))]
            if disallowed:
                errors.append("merged commit exceeds allowed scope: " + ", ".join(disallowed))
            validate_merged_content(errors, root, merge_sha, snapshot)
        except ValueError as exc:
            errors.append(str(exc))
    if not allow_closed_history:
        # Current reviewed-content preservation (Controller v3 §5): the frozen base branch's
        # CURRENT tip must still carry this Work's reviewed paths with the reviewed identity.
        # Unrelated files may legitimately be modified or added by later maintenance commits;
        # altering or deleting a reviewed path invalidates recovery and FAILS CLOSED. Closed
        # history is exempt: later legitimate Work may modify closed-history files.
        try:
            current_tip = verify_git_branch(root, base_branch)
        except ValueError as exc:
            errors.append(str(exc))
            return errors
        for item in snapshot.get("file_manifest", []):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", ""))
            state = item.get("state")
            try:
                exists = git_path_exists(root, current_tip, path)
                if state == "deleted":
                    if exists:
                        errors.append(f"current base-branch tip unexpectedly contains reviewed deleted file {path}")
                elif state == "present":
                    if not exists:
                        errors.append(f"current base-branch tip is missing reviewed file {path}")
                    else:
                        actual = git_show_bytes(root, current_tip, path)
                        expected_size = item.get("canonical_size") if item.get("canonical_size") is not None else item.get("size")
                        if sha256_bytes(actual) != item.get("sha256") or len(actual) != expected_size:
                            errors.append(f"current base-branch tip content for {path} differs from reviewed identity")
                else:
                    errors.append(f"snapshot file_manifest item {path} has invalid state")
            except ValueError as exc:
                errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("integration", help="Path to integration-record.json")
    parser.add_argument("--root", required=True)
    parser.add_argument("--change")
    parser.add_argument("--allow-closed-history", action="store_true",
                        help="Validate a closed historical record: use logical repository identity "
                             "(repository_root is metadata only), do not require the original feature "
                             "branch ref / current HEAD / worktree; immutable objects, ancestry, "
                             "manifest, and artifact digests are still strictly verified.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    errors: list[str]
    outcome_note = None
    try:
        state = load_json_object(safe_child(root, ".ai-product", "project-state.json"))
        change_name = args.change or state.get("current_change") or state.get("last_closed_change")
        if not isinstance(change_name, str):
            raise ValueError("no current or last closed change; pass --change")
        change_path = safe_child(root, ".ai-product", "changes", change_name)
        workflow = load_json_object(safe_child(change_path, "workflow-state.json"))
        contract, contract_digest = load_frozen_contract(change_path, workflow)
        snapshot = load_json_object(safe_child(change_path, "implementation-snapshot.json"))
        review = load_json_object(safe_child(change_path, "review-report.json"))
        acceptance = load_json_object(safe_child(change_path, "acceptance-record.json"))
        record = load_json_object(Path(args.integration).expanduser().resolve())
        if args.allow_closed_history:
            # Closed-history path: logical repository identity. repository_root is historical
            # metadata only; the original feature branch ref, current HEAD, and current worktree
            # are not required to match the old execution site.
            closed_root = root
            recorded_root = record.get("repository_root")
            if isinstance(recorded_root, str) and recorded_root:
                recorded_path = Path(recorded_root)
                if recorded_path.is_dir() and (recorded_path / ".git").exists():
                    closed_root = recorded_path
            # Build a closed-context contract whose repository_root is treated as metadata.
            closed_contract = dict(contract)
            closed_contract["repository_root"] = str(root)
            closed_change_path = safe_child(closed_root, ".ai-product", "changes", change_name)
            errors = validate_integration(record, closed_root, closed_contract, contract_digest,
                                          snapshot, review, acceptance, allow_closed_history=True,
                                          change_path=closed_change_path)
            if not errors and record.get("schema_version") == 2:
                review_object = record.get("review_commit_sha")
                if isinstance(review_object, str):
                    try:
                        verify_git_commit(root, review_object)
                        review_present = True
                    except ValueError:
                        review_present = False
                else:
                    review_present = False
                if not review_present:
                    # Legacy v2 review-object loss: VALID_WITH_HISTORICAL_LIMITATIONS only when the
                    # full-tree/changed-path scope is independently re-provable from an extant tree
                    # or merge diff; otherwise INVALID.
                    try:
                        merge_sha = record.get("merge_commit_sha")
                        baseline_sha = str(contract.get("baseline", {}).get("sha", ""))
                        if isinstance(merge_sha, str):
                            actual_changed = merged_changed_paths(root, baseline_sha, merge_sha,
                                                                  identity_policy=IDENTITY_POLICY_LEGACY)
                            expected = snapshot.get("changed_files", [])
                            scope_provable = sorted(actual_changed) == sorted(expected)
                        else:
                            scope_provable = False
                    except ValueError:
                        scope_provable = False
                    if scope_provable:
                        outcome_note = "VALID_WITH_HISTORICAL_LIMITATIONS: original review commit object unavailable; " \
                                       "changed-path scope independently re-proven from the extant merge diff. Missing guarantees: " \
                                       "exact review object, review-to-merge ancestry, remote durability."
                    else:
                        errors = ["INVALID: legacy v2 review object unavailable and changed-path scope cannot be independently re-proven"]
        else:
            errors = validate_integration(record, root, contract, contract_digest, snapshot, review,
                                          acceptance, change_path=change_path)
    except ValueError as exc:
        errors = [str(exc)]
    result = {"valid": not errors, "errors": errors}
    if outcome_note:
        result["outcome"] = outcome_note
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print("INVALID integration record")
        for error in errors:
            print(f"- {error}")
    else:
        print(outcome_note if outcome_note else "VALID integration record")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
