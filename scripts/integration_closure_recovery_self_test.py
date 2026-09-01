#!/usr/bin/env python3
"""Integration-closure recovery regression self-test.

Controller adjudication CASE-1..CASE-6 for PDC-MAINT-integration-validator-change-path:

CASE-1: change directory != task_id+slug; PM logs exist only in the real change directory.
        Old validator (task_id+slug derivation) RED; fixed validator (actual change path)
        must return VALID.
CASE-2: forged PM logs only under the wrong task_id+slug derived directory; real directory
        missing logs. Must be INVALID (forged path cannot pass).
CASE-3: Work A review-PASS + accepted + integrated + integration record VALID; A
        integration_ready -> blocked; main contains A's merge commit; focus_change must allow
        safe park WITHOUT restoring/removing A's already-integrated product files.
CASE-4: after A is parked and an unrelated maintenance commit advances main, re-focusing A and
        resume_task must allow blocked_from integration_ready -> integration_ready WITHOUT
        requiring the whole working tree to return to A's old snapshot delta.
CASE-5: A's integration record tampered / logs missing / merge not in main / reviewed
        integration identity broken -> park or resume must FAIL CLOSED.
CASE-6: blocked_from = ready_for_review (ordinary post-snapshot) keeps the original exact
        snapshot parking rules: a tampered working tree still fails to park; not relaxed.

All fixtures are disposable temp git repositories; the authoritative repository is never
touched. Exit 0 only when every case holds.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from capture_implementation_snapshot import CANONICAL_FORMAT_VERSION, canonical_identity_digest
from common import (
    IDENTITY_POLICY_V1,
    actual_repository_identity,
    atomic_write_json,
    digest_record,
    load_json_object,
    now_iso,
    safe_child,
    sha256_json,
)
import focus_change  # noqa: E402  (imported for _park_outgoing after sys.path setup)

PASS = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        FAILURES.append(f"{name}: {detail}")
        print(f"FAIL {name} {detail}")
    else:
        print(f"PASS {name}")


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stdout}{r.stderr}")
    return r


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, obj: dict) -> None:
    atomic_write_json(path, obj)


class Fixture:
    """One disposable repository with a complete, self-consistent integrated Work record."""

    def __init__(self, *, change: str, task_id: str, slug: str, blocked_from: str,
                 logs_in_real_dir: bool = True, forge_derived_dir: bool = False,
                 tamper_log: bool = False, drop_record: bool = False,
                 bad_merge: bool = False, tamper_worktree: bool = False,
                 advance_main: bool = False,
                 drop_required_test: bool = False, mismatch_tests_checked: bool = False,
                 missing_evidence: bool = False, missing_manual_scenario: bool = False,
                 non_passed_scenario: bool = False,
                 drop_review: bool = False, drop_acceptance: bool = False,
                 malformed_evidence: bool = False,
                 tamper_reviewed_after_integration: bool = False,
                 delete_reviewed_after_integration: bool = False) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="pdc-recovery-"))
        self.change = change
        self.task_id = task_id
        self.slug = slug
        self.blocked_from = blocked_from
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "test")
        git(self.root, "config", "user.email", "test@test")
        git(self.root, "config", "core.autocrlf", "false")
        git(self.root, "checkout", "-q", "-b", "main")
        # --- baseline ---
        (self.root / "f.txt").write_bytes(b"base\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "baseline")
        self.baseline = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.branch = git(self.root, "symbolic-ref", "--short", "HEAD").stdout.strip()
        # --- implementation / review commit (also the integration merge target) ---
        (self.root / "f.txt").write_bytes(b"impl\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "review target")
        self.review_commit = git(self.root, "rev-parse", "HEAD").stdout.strip()
        git(self.root, "update-ref", f"refs/pdc/reviews/{self.change}/latest", self.review_commit)
        # The reviewed content IS the integrated content: the merge commit is the review commit
        # itself, which remains in main history (baseline -> review/merge).
        self.merge_commit = self.review_commit
        self.control_root = safe_child(self.root, ".ai-product")
        self.change_path = safe_child(self.control_root, "changes", self.change)
        self.identity = actual_repository_identity(self.root)
        self._make_contract_and_records(
            tamper_log=tamper_log, drop_record=drop_record, bad_merge=bad_merge,
            forge_derived_dir=forge_derived_dir, logs_in_real_dir=logs_in_real_dir,
            tamper_worktree=tamper_worktree, drop_required_test=drop_required_test,
            mismatch_tests_checked=mismatch_tests_checked, missing_evidence=missing_evidence,
            missing_manual_scenario=missing_manual_scenario, non_passed_scenario=non_passed_scenario,
            drop_review=drop_review, drop_acceptance=drop_acceptance,
            malformed_evidence=malformed_evidence)
        if advance_main or tamper_reviewed_after_integration or delete_reviewed_after_integration:
            # main advances AFTER freeze. H (unrelated file), E/F (reviewed file modified),
            # G (reviewed file deleted).
            if tamper_reviewed_after_integration:
                (self.root / "f.txt").write_bytes(b"evil\n")
                git(self.root, "add", "-A")
                git(self.root, "commit", "-qm", "tamper reviewed file")
            elif delete_reviewed_after_integration:
                (self.root / "f.txt").unlink()
                git(self.root, "add", "-A")
                git(self.root, "commit", "-qm", "delete reviewed file")
            else:
                (self.root / "g.txt").write_bytes(b"unrelated\n")
                git(self.root, "add", "-A")
                git(self.root, "commit", "-qm", "unrelated maintenance")

    def _make_contract_and_records(self, *, tamper_log: bool, drop_record: bool, bad_merge: bool,
                                   forge_derived_dir: bool, logs_in_real_dir: bool,
                                   tamper_worktree: bool, drop_required_test: bool,
                                   mismatch_tests_checked: bool, missing_evidence: bool,
                                   missing_manual_scenario: bool, non_passed_scenario: bool,
                                   drop_review: bool, drop_acceptance: bool,
                                   malformed_evidence: bool) -> None:
        # --- frozen contract (freeze happens here: frozen tip == review/merge commit) ---
        self.contract = {
            "schema_version": 3,
            "contract_version": 1,
            "task_id": self.task_id,
            "title": "test fixture",
            "slug": self.slug,
            "baseline": {"repository": self.identity, "branch": self.branch, "sha": self.baseline},
            "user_result": "test",
            "in_scope": ["test"],
            "out_of_scope": ["test"],
            "allowed_files": ["f.txt"],
            "forbidden_changes": ["test"],
            "acceptance_criteria": [{
                "id": "AC-1",
                "statement": "The fixture change passes its frozen deterministic test and the reviewed behavior is unchanged.",
                "test_ids": ["TEST-1"], "evidence_ids": ["EV-1"],
            }],
            "required_tests": [{
                "id": "TEST-1", "type": "integration", "command": "true",
                "expected": "test fixture passes",
            }],
            "required_evidence": [{
                "id": "EV-1", "type": "artifact", "description": "test fixture evidence",
            }],
            "manual_acceptance": [{
                "id": "UA-1", "criterion_ids": ["AC-1"], "setup": "test",
                "action": "test", "expected": "test",
            }],
            "post_merge_checks": [{"id": "PM-1", "command": "true", "expected_exit_code": 0}],
            "global_stop_conditions": ["required_build_failure"],
            "non_blocking_findings_policy": "test-only fixture policy; unrelated debt is non-blocking.",
            "test_first_exception": {"reason": "test fixture", "approved_by": "controller"},
            "frozen_at": now_iso(),
            "approved_by": "controller",
            "source_draft_digest": "0" * 64,
            "repository_identity": self.identity,
            "repository_root": str(self.root),
            "baseline_branch_tip_sha": self.review_commit,
        }
        self.contract_digest = sha256_json(self.contract)

        tree = git(self.root, "rev-parse", f"{self.review_commit}^{{tree}}").stdout.strip()
        blob = git(self.root, "rev-parse", f"{self.review_commit}:f.txt").stdout.strip()
        content = git(self.root, "show", f"{self.review_commit}:f.txt").stdout.encode()
        manifest = [{
            "path": "f.txt", "state": "present", "mode": "100644", "blob_sha": blob,
            "canonical_size": len(content), "sha256": sha256(content), "size": len(content),
        }]
        snapshot = {
            "schema_version": 3,
            "identity_policy": IDENTITY_POLICY_V1,
            "canonical_format_version": CANONICAL_FORMAT_VERSION,
            "task_id": self.task_id,
            "contract_version": 1,
            "contract_digest": self.contract_digest,
            "baseline_sha": self.baseline,
            "review_commit_sha": self.review_commit,
            "review_tree_sha": tree,
            "canonical_identity_digest": canonical_identity_digest(self.baseline, tree, manifest),
            "review_ref": f"refs/pdc/reviews/{self.change}/latest",
            "file_manifest": manifest,
            "changed_files": ["f.txt"],
            "captured_at": now_iso(),
            "git_status": "",
        }
        self.snapshot_digest = digest_record(snapshot, "snapshot_digest")
        snapshot["snapshot_digest"] = self.snapshot_digest
        self.snapshot = snapshot

        # --- test-execution record + review-tests log ---
        run_dir = "evidence/review-tests/run-1"
        ter_log = b"ok\n"
        status_text = git(self.root, "status", "--porcelain").stdout.encode()
        index_bytes = (self.root / ".git" / "index").read_bytes() if (self.root / ".git" / "index").exists() else b""
        started = now_iso()
        t1_start = now_iso()
        t1_end = now_iso()
        completed = now_iso()
        ter = {
            "schema_version": 1,
            "task_id": self.task_id,
            "contract_version": 1,
            "contract_digest": self.contract_digest,
            "implementation_snapshot_digest": self.snapshot_digest,
            "review_commit_sha": self.review_commit,
            "baseline_sha": self.baseline,
            "executor": "test",
            "started_at": started,
            "completed_at": completed,
            "timeout_seconds": 60,
            "isolation": {
                "strategy": "detached_temporary_git_worktree",
                "review_commit_sha": self.review_commit,
                "cleanup": "removed",
                "security_boundary": "git_isolation_not_security_sandbox",
            },
            "main_worktree": {
                "branch_before": self.branch,
                "branch_after": self.branch,
                "head_before": self.review_commit,
                "head_after": self.review_commit,
                "status_before_sha256": sha256(status_text),
                "status_after_sha256": sha256(status_text),
                "index_before_sha256": sha256(index_bytes),
                "index_after_sha256": sha256(index_bytes),
                "preserved": True,
            },
            "tests": ([] if drop_required_test else [{
                "id": "TEST-1", "type": "integration", "command": "true",
                "expected": "test fixture passes",
                "expected_exit_code": 0, "started_at": t1_start, "completed_at": t1_end,
                "actual_exit_code": 0, "result": "passed", "blocked_reason": None,
                "log_path": f"{run_dir}/TEST-1.log", "log_size": len(ter_log),
                "log_sha256": sha256(ter_log),
            }]),
            "runner_blockers": [],
            "overall_status": "passed",
        }
        ter["record_digest"] = digest_record(ter, "record_digest")
        self.ter_digest = ter["record_digest"]
        self.ter = ter

        self.review = {
            "schema_version": 4,
            "task_id": self.task_id,
            "contract_version": 1,
            "contract_digest": self.contract_digest,
            "implementation_snapshot_digest": self.snapshot_digest,
            "review_commit_sha": self.review_commit,
            "baseline_sha": self.baseline,
            "test_execution_record_digest": self.ter_digest,
            "reviewed_at": now_iso(),
            "reviewer": "controller",
            "verdict": "PASS",
            "checked_criteria": [{"id": "AC-1", "result": "satisfied", "evidence": "test fixture"}],
            "tests_checked": ([] if mismatch_tests_checked else ["TEST-1"]),
            "evidence_checked": ([] if missing_evidence else ["EV-1"]),
            "blocking_findings": [],
            "evidence_missing": [],
            "non_blocking_findings": [],
        }
        self.acceptance = {
            "schema_version": 2,
            "task_id": self.task_id,
            "contract_version": 1,
            "contract_digest": self.contract_digest,
            "implementation_snapshot_digest": self.snapshot_digest,
            "review_commit_sha": self.review_commit,
            "decision": "accepted",
            "recorded_at": now_iso(),
            "tester": "product-owner",
            "environment": "test fixture",
            "scenarios": ([] if missing_manual_scenario else [{
                "id": "UA-1",
                "result": ("failed" if non_passed_scenario else "passed"),
                "notes": "test",
            }]),
            "notes": "test fixture",
        }
        log_text = "ok\n"
        tampered_text = "tampered\n"
        record = {
            "schema_version": 3,
            "task_id": self.task_id,
            "contract_version": 1,
            "contract_digest": self.contract_digest,
            "implementation_snapshot_digest": self.snapshot_digest,
            "review_commit_sha": self.review_commit,
            "review_report_digest": sha256_json(self.review),
            "acceptance_record_digest": sha256_json(self.acceptance),
            "repository_identity": self.identity,
            "repository_root": str(self.root),
            "base_branch": self.branch,
            "base_branch_tip_sha": self.review_commit,
            "merge_commit_sha": ("0" * 40 if bad_merge else self.merge_commit),
            "pull_request": {"provider": None, "url": None, "number": None},
            "ci": {"status": "success", "verification": "controller_executed", "provider": "local",
                   "workflow": "test", "url": None, "run_id": None, "verified_by": "controller",
                   "verified_at": now_iso()},
            "post_merge_verification": [{
                "id": "PM-1", "command": "true", "expected_exit_code": 0, "actual_exit_code": 0,
                "stdout_sha256": sha256(log_text.encode()),
                "log_path": "evidence/post-merge/PM-1.log",
                "executed_at": now_iso(), "executor": "controller",
            }],            "release": {"reference": None, "rollback": "git revert " + self.merge_commit},
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
        self.record = record

        # --- write the change directory records ---
        self.change_path.mkdir(parents=True, exist_ok=True)
        write_json(self.change_path / "task-contract.draft.json", self.contract)
        contracts = self.change_path / "contracts"
        contracts.mkdir(parents=True, exist_ok=True)
        write_json(contracts / "task-contract.v1.json", self.contract)
        (contracts / "task-contract.v1.sha256").write_text(self.contract_digest + "\n", encoding="utf-8")
        write_json(self.change_path / "implementation-snapshot.json", self.snapshot)
        write_json(self.change_path / "test-execution-record.json", self.ter)
        if not drop_review:
            write_json(self.change_path / "review-report.json", self.review)
        if not drop_acceptance:
            write_json(self.change_path / "acceptance-record.json", self.acceptance)
        if malformed_evidence:
            (self.change_path / "integration-record.json").write_text("{not valid json", encoding="utf-8")
        elif not drop_record:
            write_json(self.change_path / "integration-record.json", self.record)
        workflow = {
            "schema_version": 2, "task_id": self.task_id, "status": "blocked",
            "blocked_from": self.blocked_from,
            "blocked_reason": "fixture", "blocked_at": now_iso(), "blocked_by": "controller",
            "contract_version": 1, "contract_digest": self.contract_digest,
            "implementation_snapshot_digest": self.snapshot_digest,
            "review_commit_sha": self.review_commit,
            "test_execution_record_digest": self.ter_digest, "updated_at": now_iso(), "history": [],
        }
        self.workflow = workflow
        write_json(self.change_path / "workflow-state.json", workflow)

        # --- evidence dirs ---
        (self.change_path / "evidence" / "review-tests" / "run-1").mkdir(parents=True, exist_ok=True)
        (self.change_path / "evidence" / "review-tests" / "run-1" / "TEST-1.log").write_bytes(ter_log)
        if logs_in_real_dir:
            (self.change_path / "evidence" / "post-merge").mkdir(parents=True, exist_ok=True)
            # A tampered log differs from the digest recorded in the integration record.
            (self.change_path / "evidence" / "post-merge" / "PM-1.log").write_bytes(
                (tampered_text if tamper_log else log_text).encode())
        if forge_derived_dir:
            derived = safe_child(self.control_root, "changes", f"{self.task_id}-{self.slug}")
            (derived / "evidence" / "post-merge").mkdir(parents=True, exist_ok=True)
            (derived / "evidence" / "post-merge" / "PM-1.log").write_bytes(log_text.encode())
        if tamper_worktree:
            (self.root / "f.txt").write_bytes(b"evil\n")

        # --- minimal project projection so resume_task can run against the fixture ---
        project_state = {
            "schema_version": 3,
            "project_name": "fixture",
            "repository_root": str(self.root),
            "current_change": self.change,
            "current_task_status": "blocked",
            "current_stage": "integration",
            "next_required_action": "execute_post_merge_verification_and_close",
            "blocked_by": [],
            "requires_user_decision": False,
            "history": [],
        }
        write_json(self.control_root / "project-state.json", project_state)

    def validate(self) -> list[str]:
        from validate_integration_record import validate_integration
        return validate_integration(self.record, self.root, self.contract, self.contract_digest,
                                    self.snapshot, self.review, self.acceptance,
                                    change_path=self.change_path)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def run_case_1() -> None:
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b", blocked_from="integration_ready")
    errors = f.validate()
    check("CASE-1 real-dir logs VALID under fixed validator", not errors, "; ".join(errors))
    f.cleanup()


def run_case_2() -> None:
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b", blocked_from="integration_ready",
                logs_in_real_dir=False, forge_derived_dir=True)
    errors = f.validate()
    check("CASE-2 forged derived-dir logs cannot pass",
          any("post-merge log" in e or "outside evidence/post-merge" in e for e in errors),
          "; ".join(errors))
    f.cleanup()


def run_case_3() -> None:
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b", blocked_from="integration_ready")
    try:
        focus_change._park_outgoing(f.root, f.control_root, f.change, f.workflow)
        ok = (f.root / "f.txt").read_text() == "impl\n"
        check("CASE-3 safe park allowed, integrated file NOT restored", ok,
              f"f.txt = {(f.root / 'f.txt').read_text()!r}")
    except ValueError as exc:
        check("CASE-3 safe park allowed", False, str(exc))
    f.cleanup()


def run_case_4() -> None:
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b", blocked_from="integration_ready",
                advance_main=True)
    try:
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "resume_task.py"),
                            "--root", str(f.root), "--change", f.change,
                            "--actor", "controller", "--reason", "fixture resume"],
                           capture_output=True, text=True, timeout=120)
        workflow = load_json_object(f.change_path / "workflow-state.json")
        ok = r.returncode == 0 and workflow.get("status") == "integration_ready"
        check("CASE-4 resume blocked_from=integration_ready after main advanced", ok,
              f"exit={r.returncode} status={workflow.get('status')} {r.stdout[-300:]}{r.stderr[-300:]}")
        check("CASE-4 no old-snapshot materialization (f.txt stays 'impl')",
              (f.root / "f.txt").read_text() == "impl\n",
              (f.root / "f.txt").read_text())
    except Exception as exc:  # noqa: BLE001
        check("CASE-4 resume allowed", False, str(exc))
    f.cleanup()


def run_case_5() -> None:
    for name, kwargs in [
        ("tampered log", {"tamper_log": True}),
        ("missing record", {"drop_record": True}),
        ("merge not in main", {"bad_merge": True}),
    ]:
        f = Fixture(change="change-a", task_id="task-a", slug="slug-b",
                    blocked_from="integration_ready", **kwargs)
        try:
            focus_change._park_outgoing(f.root, f.control_root, f.change, f.workflow)
            check(f"CASE-5 park FAIL CLOSED ({name})", False, "park unexpectedly allowed")
        except ValueError:
            check(f"CASE-5 park FAIL CLOSED ({name})", True)
        f.cleanup()
    # Evidence-integrity regressions (Controller v2 §7): even with all digests synchronously
    # recomputed, missing/tampered evidence must FAIL CLOSED.
    for name, kwargs in [
        ("frozen required test dropped (digests recomputed)", {"drop_required_test": True}),
        ("review.tests_checked mismatch", {"mismatch_tests_checked": True}),
        ("required evidence missing from review", {"missing_evidence": True}),
        ("manual scenario missing from acceptance", {"missing_manual_scenario": True}),
        ("non-passed acceptance scenario", {"non_passed_scenario": True}),
    ]:
        f = Fixture(change="change-a", task_id="task-a", slug="slug-b",
                    blocked_from="integration_ready", **kwargs)
        try:
            focus_change._park_outgoing(f.root, f.control_root, f.change, f.workflow)
            check(f"CASE-5 FAIL CLOSED ({name})", False, "park unexpectedly allowed")
        except ValueError:
            check(f"CASE-5 FAIL CLOSED ({name})", True)
        f.cleanup()
    # Resume with incomplete integration evidence must FAIL CLOSED and stay blocked (v3 §4).
    for name, kwargs in [
        ("resume: integration-record missing", {"drop_record": True}),
        ("resume: review-report missing", {"drop_review": True}),
        ("resume: acceptance-record missing", {"drop_acceptance": True}),
        ("resume: malformed integration evidence", {"malformed_evidence": True}),
    ]:
        f = Fixture(change="change-a", task_id="task-a", slug="slug-b",
                    blocked_from="integration_ready", **kwargs)
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "resume_task.py"),
                            "--root", str(f.root), "--change", f.change,
                            "--actor", "controller", "--reason", "fixture resume"],
                           capture_output=True, text=True, timeout=120)
        workflow = load_json_object(f.change_path / "workflow-state.json")
        ok = r.returncode != 0 and workflow.get("status") == "blocked"
        check(f"CASE-5 {name}", ok,
              f"exit={r.returncode} status={workflow.get('status')} {r.stdout[-150:]}{r.stderr[-150:]}")
        f.cleanup()
    # Current-main reviewed-content preservation (v3 §5): later commits may not alter the
    # Work's reviewed paths.
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b",
                blocked_from="integration_ready", tamper_reviewed_after_integration=True)
    try:
        focus_change._park_outgoing(f.root, f.control_root, f.change, f.workflow)
        check("CASE-5 park FAIL CLOSED (later commit modified reviewed file)", False,
              "park unexpectedly allowed")
    except ValueError:
        check("CASE-5 park FAIL CLOSED (later commit modified reviewed file)", True)
    r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "resume_task.py"),
                        "--root", str(f.root), "--change", f.change,
                        "--actor", "controller", "--reason", "fixture resume"],
                       capture_output=True, text=True, timeout=120)
    workflow = load_json_object(f.change_path / "workflow-state.json")
    check("CASE-5 resume FAIL CLOSED (later commit modified reviewed file)",
          r.returncode != 0 and workflow.get("status") == "blocked",
          f"exit={r.returncode} status={workflow.get('status')}")
    f.cleanup()
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b",
                blocked_from="integration_ready", delete_reviewed_after_integration=True)
    try:
        focus_change._park_outgoing(f.root, f.control_root, f.change, f.workflow)
        check("CASE-5 park FAIL CLOSED (later commit deleted reviewed file)", False,
              "park unexpectedly allowed")
    except ValueError:
        check("CASE-5 park FAIL CLOSED (later commit deleted reviewed file)", True)
    r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "resume_task.py"),
                        "--root", str(f.root), "--change", f.change,
                        "--actor", "controller", "--reason", "fixture resume"],
                       capture_output=True, text=True, timeout=120)
    workflow = load_json_object(f.change_path / "workflow-state.json")
    check("CASE-5 resume FAIL CLOSED (later commit deleted reviewed file)",
          r.returncode != 0 and workflow.get("status") == "blocked",
          f"exit={r.returncode} status={workflow.get('status')}")
    f.cleanup()
    # H: unrelated later commits must NOT block park/resume.
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b",
                blocked_from="integration_ready", advance_main=True)
    try:
        focus_change._park_outgoing(f.root, f.control_root, f.change, f.workflow)
        check("CASE-5 park OK (later commit touched only unrelated file)", True)
    except ValueError as exc:
        check("CASE-5 park OK (later commit touched only unrelated file)", False, str(exc))
    r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "resume_task.py"),
                        "--root", str(f.root), "--change", f.change,
                        "--actor", "controller", "--reason", "fixture resume"],
                       capture_output=True, text=True, timeout=120)
    workflow = load_json_object(f.change_path / "workflow-state.json")
    check("CASE-5 resume OK (later commit touched only unrelated file)",
          r.returncode == 0 and workflow.get("status") == "integration_ready",
          f"exit={r.returncode} status={workflow.get('status')}")
    f.cleanup()


def run_case_6() -> None:
    # Tampered worktree under ordinary post-snapshot blocked_from: must still fail to park.
    f = Fixture(change="change-a", task_id="task-a", slug="slug-b",
                blocked_from="ready_for_review", tamper_worktree=True)
    try:
        focus_change._park_outgoing(f.root, f.control_root, f.change, f.workflow)
        check("CASE-6 ready_for_review keeps exact-snapshot rule (tampered worktree fails)", False,
              "park unexpectedly allowed")
    except ValueError:
        check("CASE-6 ready_for_review keeps exact-snapshot rule (tampered worktree fails)", True)
    f.cleanup()
    # Untampered worktree under ready_for_review: original parking still works.
    f2 = Fixture(change="change-b", task_id="task-b", slug="slug-c",
                 blocked_from="ready_for_review")
    try:
        focus_change._park_outgoing(f2.root, f2.control_root, f2.change, f2.workflow)
        check("CASE-6 ready_for_review original parking still succeeds (untampered)", True)
    except ValueError as exc:
        check("CASE-6 ready_for_review original parking still succeeds (untampered)", False, str(exc))
    f2.cleanup()


def main() -> int:
    run_case_1()
    run_case_2()
    run_case_3()
    run_case_4()
    run_case_5()
    run_case_6()
    print(f"\nintegration-closure-recovery self-test: {'PASS' if not FAILURES else 'FAIL'} "
          f"({len(FAILURES)} failures)")
    return PASS if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
