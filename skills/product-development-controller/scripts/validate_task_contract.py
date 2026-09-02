#!/usr/bin/env python3
"""Strictly validate a draft or frozen task contract."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
from typing import Any

from common import (
    CONTROLLER_LOCK_PATH,
    RESERVED_MUTABLE_RECORD_EXACT,
    ensure_known_keys,
    ensure_required_keys,
    ensure_unique_ids,
    load_json_object,
    normalize_repository_identity,
    normalize_repo_path,
    path_allowed,
    require_integer,
    require_iso8601,
    require_list,
    require_object,
    require_sha,
    require_sha256,
    require_string,
    require_valid_id,
)

SCHEMA_VERSION = 3
TEST_TYPES = {"unit", "integration", "e2e", "build", "lint", "security", "performance", "other"}
EVIDENCE_TYPES = {
    "command_output", "diff", "browser", "screenshot", "log", "artifact", "manual_observation", "other"
}
BASE_FIELDS = {
    "schema_version", "contract_version", "task_id", "title", "slug", "baseline", "user_result",
    "in_scope", "out_of_scope", "allowed_files", "forbidden_changes", "acceptance_criteria",
    "required_tests", "required_evidence", "manual_acceptance", "post_merge_checks",
    "global_stop_conditions", "non_blocking_findings_policy", "test_first_exception",
}
FROZEN_FIELDS = BASE_FIELDS | {
    "frozen_at", "approved_by", "source_draft_digest", "repository_identity", "repository_root",
    "baseline_branch_tip_sha",
}


def validate_scope_pattern(errors: list[str], label: str, value: Any) -> None:
    text = require_string(errors, label, value)
    if not text:
        return
    try:
        normalize_repo_path(text, allow_directory_suffix=True)
    except ValueError as exc:
        errors.append(f"{label}: {exc}")


# Reserved Mutable Controller Record directory namespaces under identity-policy v1.
RESERVED_DIR_PREFIXES = (
    ("changes", (".ai-product", "changes")),
    ("transactions", (".ai-product", "transactions")),
    ("backups", (".ai-product", "backups")),
    ("handoffs", (".ai-product", "handoffs")),
)


def _pattern_segments(pattern: str) -> list[str]:
    normalized = normalize_repo_path(pattern, allow_directory_suffix=True)
    if normalized.endswith("/"):
        return normalized.rstrip("/").split("/") + ["**"]
    return normalized.split("/")


def _glob_may_match_reserved(pattern: str, prefix: list[str]) -> bool:
    """True if `pattern` can match a repository path whose leading segments equal `prefix`
    followed by at least one more segment (a member of a reserved directory namespace).

    Fail-closed behavior: an overlap exists if the pattern's automaton can consume the
    reserved prefix and at least one additional segment; `**` may absorb arbitrary segments.
    """
    pattern_segments = _pattern_segments(pattern)
    max_pi = len(pattern_segments) + len(prefix) + 2
    seen: set[tuple[int, int]] = set()

    def can(pi: int, gi: int) -> bool:
        if (pi, gi) in seen:
            return False
        seen.add((pi, gi))
        if gi == len(pattern_segments):
            return pi > len(prefix)
        token = pattern_segments[gi]
        if token == "**":
            if can(pi, gi + 1):
                return True
            if pi < max_pi:
                return can(pi + 1, gi)
            return False
        if pi >= max_pi:
            return False
        if pi < len(prefix):
            if not fnmatch.fnmatchcase(prefix[pi], token):
                return False
            return can(pi + 1, gi + 1)
        # Free segment after the reserved prefix: some string matches any fnmatch token.
        return can(pi + 1, gi + 1)

    return can(0, 0)


def reserved_pattern_errors(allowed_files: list[Any]) -> list[str]:
    """Fail closed when an allowed_files pattern may grant deliverable identity to a
    reserved Mutable Controller Record (exact .ai-product/project-state.json or a member
    of changes/**, transactions/**, backups/**, handoffs/**)."""
    errors: list[str] = []
    for index, item in enumerate(allowed_files, start=1):
        if not isinstance(item, str):
            continue
        try:
            pattern = normalize_repo_path(item, allow_directory_suffix=True)
        except ValueError:
            continue
        try:
            if path_allowed(RESERVED_MUTABLE_RECORD_EXACT, [pattern]) or path_allowed(CONTROLLER_LOCK_PATH, [pattern]):
                errors.append(
                    f"allowed_files[{index}] overlaps a reserved Mutable Controller Record ({pattern})"
                )
        except ValueError:
            pass
        for name, segments in RESERVED_DIR_PREFIXES:
            try:
                if _glob_may_match_reserved(pattern, list(segments)):
                    errors.append(
                        f"allowed_files[{index}] overlaps the reserved {name}/ namespace ({pattern})"
                    )
            except ValueError:
                pass
    return errors


def validate_contract(data: dict[str, Any], *, frozen: bool | None = None) -> list[str]:
    errors: list[str] = []
    if frozen is None:
        frozen = any(key in data for key in ("frozen_at", "approved_by", "source_draft_digest"))
    allowed_fields = FROZEN_FIELDS if frozen else BASE_FIELDS
    ensure_known_keys(errors, "contract", data, allowed_fields)
    ensure_required_keys(errors, "contract", data, allowed_fields)

    schema = require_integer(errors, "schema_version", data.get("schema_version"), minimum=1)
    if schema is not None and schema != SCHEMA_VERSION:
        errors.append(f"schema_version must equal supported version {SCHEMA_VERSION}")
    require_integer(errors, "contract_version", data.get("contract_version"), minimum=1)
    require_valid_id(errors, "task_id", data.get("task_id"))
    require_string(errors, "title", data.get("title"))
    require_valid_id(errors, "slug", data.get("slug"))
    require_string(errors, "user_result", data.get("user_result"))
    require_string(errors, "non_blocking_findings_policy", data.get("non_blocking_findings_policy"))

    baseline = require_object(errors, "baseline", data.get("baseline"))
    ensure_known_keys(errors, "baseline", baseline, {"repository", "branch", "sha"})
    ensure_required_keys(errors, "baseline", baseline, {"repository", "branch", "sha"})
    repository = require_string(errors, "baseline.repository", baseline.get("repository"))
    if repository:
        try:
            normalize_repository_identity(repository)
        except ValueError as exc:
            errors.append(f"baseline.repository: {exc}")
    branch = require_string(errors, "baseline.branch", baseline.get("branch"))
    if branch and (branch.startswith("-") or any(token in branch for token in ("..", "~", "^", ":", "?", "*", "[", "\\"))):
        errors.append("baseline.branch contains an unsafe Git ref expression")
    require_sha(errors, "baseline.sha", baseline.get("sha"))

    for label in ("in_scope", "out_of_scope", "forbidden_changes"):
        items = require_list(errors, label, data.get(label))
        for index, item in enumerate(items, start=1):
            require_string(errors, f"{label}[{index}]", item)

    allowed_files = require_list(errors, "allowed_files", data.get("allowed_files"))
    normalized_patterns: set[str] = set()
    for index, item in enumerate(allowed_files, start=1):
        validate_scope_pattern(errors, f"allowed_files[{index}]", item)
        if isinstance(item, str):
            try:
                normalized = normalize_repo_path(item, allow_directory_suffix=True)
                if normalized in normalized_patterns:
                    errors.append(f"allowed_files contains duplicate pattern {normalized}")
                normalized_patterns.add(normalized)
            except ValueError:
                pass
    errors.extend(reserved_pattern_errors(allowed_files))

    stop_conditions = require_list(errors, "global_stop_conditions", data.get("global_stop_conditions"))
    seen_stops: set[str] = set()
    for index, item in enumerate(stop_conditions, start=1):
        stop_id = require_valid_id(errors, f"global_stop_conditions[{index}]", item)
        if stop_id in seen_stops:
            errors.append(f"global_stop_conditions contains duplicate id {stop_id}")
        seen_stops.add(stop_id)

    tests = require_list(errors, "required_tests", data.get("required_tests"))
    test_ids = ensure_unique_ids(errors, "required_tests", tests)
    for index, item in enumerate(tests, start=1):
        if not isinstance(item, dict):
            continue
        ensure_known_keys(errors, f"required_tests[{index}]", item, {"id", "type", "command", "expected"})
        ensure_required_keys(errors, f"required_tests[{index}]", item, {"id", "type", "command", "expected"})
        test_type = require_string(errors, f"required_tests[{index}].type", item.get("type"))
        if test_type and test_type not in TEST_TYPES:
            errors.append(f"required_tests[{index}].type must be one of {sorted(TEST_TYPES)}")
        require_string(errors, f"required_tests[{index}].command", item.get("command"))
        require_string(errors, f"required_tests[{index}].expected", item.get("expected"))

    evidence = require_list(errors, "required_evidence", data.get("required_evidence"))
    evidence_ids = ensure_unique_ids(errors, "required_evidence", evidence)
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            continue
        ensure_known_keys(errors, f"required_evidence[{index}]", item, {"id", "type", "description"})
        ensure_required_keys(errors, f"required_evidence[{index}]", item, {"id", "type", "description"})
        evidence_type = require_string(errors, f"required_evidence[{index}].type", item.get("type"))
        if evidence_type and evidence_type not in EVIDENCE_TYPES:
            errors.append(f"required_evidence[{index}].type must be one of {sorted(EVIDENCE_TYPES)}")
        require_string(errors, f"required_evidence[{index}].description", item.get("description"))

    criteria = require_list(errors, "acceptance_criteria", data.get("acceptance_criteria"))
    criterion_ids = ensure_unique_ids(errors, "acceptance_criteria", criteria)
    referenced_tests: set[str] = set()
    referenced_evidence: set[str] = set()
    for index, item in enumerate(criteria, start=1):
        if not isinstance(item, dict):
            continue
        ensure_known_keys(errors, f"acceptance_criteria[{index}]", item, {"id", "statement", "test_ids", "evidence_ids"})
        ensure_required_keys(errors, f"acceptance_criteria[{index}]", item, {"id", "statement", "test_ids", "evidence_ids"})
        statement = require_string(errors, f"acceptance_criteria[{index}].statement", item.get("statement"))
        if statement and len(statement) < 10:
            errors.append(f"acceptance_criteria[{index}].statement is too vague to be reviewable")
        item_tests = require_list(errors, f"acceptance_criteria[{index}].test_ids", item.get("test_ids"), nonempty=False)
        item_evidence = require_list(errors, f"acceptance_criteria[{index}].evidence_ids", item.get("evidence_ids"), nonempty=False)
        if not item_tests and not item_evidence:
            errors.append(f"acceptance_criteria[{index}] must map to at least one test or evidence item")
        for ref in item_tests:
            ref_id = require_valid_id(errors, f"acceptance_criteria[{index}].test_ids", ref)
            if ref_id and ref_id not in test_ids:
                errors.append(f"acceptance_criteria[{index}] references unknown test id {ref_id}")
            if ref_id:
                referenced_tests.add(ref_id)
        for ref in item_evidence:
            ref_id = require_valid_id(errors, f"acceptance_criteria[{index}].evidence_ids", ref)
            if ref_id and ref_id not in evidence_ids:
                errors.append(f"acceptance_criteria[{index}] references unknown evidence id {ref_id}")
            if ref_id:
                referenced_evidence.add(ref_id)

    unreferenced_tests = sorted(test_ids - referenced_tests)
    if unreferenced_tests:
        errors.append(f"required_tests are not mapped to acceptance criteria: {', '.join(unreferenced_tests)}")
    unreferenced_evidence = sorted(evidence_ids - referenced_evidence)
    if unreferenced_evidence:
        errors.append(f"required_evidence items are not mapped to acceptance criteria: {', '.join(unreferenced_evidence)}")

    manual = require_list(errors, "manual_acceptance", data.get("manual_acceptance"))
    ensure_unique_ids(errors, "manual_acceptance", manual)
    mapped_manual_criteria: set[str] = set()
    for index, item in enumerate(manual, start=1):
        if not isinstance(item, dict):
            continue
        ensure_known_keys(errors, f"manual_acceptance[{index}]", item, {"id", "criterion_ids", "setup", "action", "expected"})
        ensure_required_keys(errors, f"manual_acceptance[{index}]", item, {"id", "criterion_ids", "setup", "action", "expected"})
        refs = require_list(errors, f"manual_acceptance[{index}].criterion_ids", item.get("criterion_ids"))
        for ref in refs:
            ref_id = require_valid_id(errors, f"manual_acceptance[{index}].criterion_ids", ref)
            if ref_id and ref_id not in criterion_ids:
                errors.append(f"manual_acceptance[{index}] references unknown criterion id {ref_id}")
            if ref_id:
                mapped_manual_criteria.add(ref_id)
        for key in ("setup", "action", "expected"):
            require_string(errors, f"manual_acceptance[{index}].{key}", item.get(key))
    missing_manual = sorted(criterion_ids - mapped_manual_criteria)
    if missing_manual:
        errors.append(f"acceptance criteria lack manual acceptance coverage: {', '.join(missing_manual)}")

    post_checks = require_list(errors, "post_merge_checks", data.get("post_merge_checks"))
    ensure_unique_ids(errors, "post_merge_checks", post_checks)
    for index, item in enumerate(post_checks, start=1):
        check = require_object(errors, f"post_merge_checks[{index}]", item)
        ensure_known_keys(errors, f"post_merge_checks[{index}]", check, {"id", "command", "expected_exit_code"})
        ensure_required_keys(errors, f"post_merge_checks[{index}]", check, {"id", "command", "expected_exit_code"})
        require_string(errors, f"post_merge_checks[{index}].command", check.get("command"))
        require_integer(errors, f"post_merge_checks[{index}].expected_exit_code", check.get("expected_exit_code"), minimum=0)

    exception = data.get("test_first_exception")
    if exception is not None:
        exception_obj = require_object(errors, "test_first_exception", exception)
        ensure_known_keys(errors, "test_first_exception", exception_obj, {"reason", "approved_by"})
        ensure_required_keys(errors, "test_first_exception", exception_obj, {"reason", "approved_by"})
        require_string(errors, "test_first_exception.reason", exception_obj.get("reason"))
        require_string(errors, "test_first_exception.approved_by", exception_obj.get("approved_by"))

    if frozen:
        require_iso8601(errors, "frozen_at", data.get("frozen_at"))
        require_string(errors, "approved_by", data.get("approved_by"))
        require_sha256(errors, "source_draft_digest", data.get("source_draft_digest"))
        identity = require_string(errors, "repository_identity", data.get("repository_identity"))
        if identity:
            try:
                normalize_repository_identity(identity)
            except ValueError as exc:
                errors.append(f"repository_identity: {exc}")
        require_string(errors, "repository_root", data.get("repository_root"))
        require_sha(errors, "baseline_branch_tip_sha", data.get("baseline_branch_tip_sha"))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", help="Path to task-contract.draft.json or frozen contract JSON")
    parser.add_argument("--frozen", action="store_true", help="Require frozen metadata")
    parser.add_argument("--json", action="store_true", help="Output machine-readable result")
    args = parser.parse_args()
    path = Path(args.contract)
    try:
        data = load_json_object(path)
        errors = validate_contract(data, frozen=True if args.frozen else None)
    except ValueError as exc:
        errors = [str(exc)]
    result = {"valid": not errors, "errors": errors, "path": str(path)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print("INVALID task contract")
        for error in errors:
            print(f"- {error}")
    else:
        print("VALID task contract")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
