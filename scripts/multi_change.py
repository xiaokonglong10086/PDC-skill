#!/usr/bin/env python3
"""Shared multi-change coordination primitives with one Focused Change."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from common import (
    actual_repository_identity,
    digest_record,
    git_is_ancestor,
    git_output,
    git_path_exists,
    git_show_bytes,
    is_mutable_controller_record,
    load_json_object,
    non_control_git_status,
    normalize_repo_path,
    now_iso,
    path_allowed,
    run_command,
    safe_child,
    sha256_bytes,
    sha256_json,
    validate_change_name,
    verify_git_branch,
)

WORKFLOW_STATUSES = {
    "draft",
    "ready_for_implementation",
    "implementing",
    "ready_for_review",
    "changes_requested",
    "evidence_missing",
    "ready_for_acceptance",
    "accepted",
    "integration_ready",
    "blocked",
    "closed",
}
PARKED_STATUSES = {"draft", "blocked"}
POST_SNAPSHOT_STATUSES = {
    "ready_for_review",
    "changes_requested",
    "evidence_missing",
    "ready_for_acceptance",
    "accepted",
    "integration_ready",
}

STAGE_BY_STATUS = {
    "draft": "task_contracting",
    "ready_for_implementation": "implementation",
    "implementing": "implementation",
    "ready_for_review": "independent_review",
    "changes_requested": "implementation",
    "evidence_missing": "implementation",
    "ready_for_acceptance": "product_acceptance",
    "accepted": "integration",
    "integration_ready": "integration",
    "closed": "observation",
    "blocked": "blocked",
}

NEXT_ACTION_BY_STATUS = {
    "draft": "freeze_task_contract",
    "ready_for_implementation": "coding_agent_implement",
    "implementing": "complete_implementation_and_capture_snapshot",
    "ready_for_review": "controller_independent_review",
    "changes_requested": "coding_agent_fix_failed_items_only",
    "evidence_missing": "coding_agent_supply_contracted_evidence_only",
    "ready_for_acceptance": "product_owner_manual_acceptance",
    "accepted": "prepare_integration",
    "integration_ready": "execute_post_merge_verification_and_close",
    "closed": "select_next_backlog_change",
    "blocked": "resolve_recorded_blocker_then_resume",
}

HEX_40_OR_64 = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_PRIOR_UNSET = object()


class FailClosedError(ValueError):
    """A well-formed authority request that cannot legally select or advance an owner."""


_DECLARATION_LINE = re.compile(r"^-\s+\*\*([^*\r\n]+?):\*\*\s*(.*?)\s*$")
_FENCED_DECLARATION_LABEL = re.compile(r"^([A-Za-z][A-Za-z0-9 /+_.-]{1,80}):[ \t]*$")
_DECLARED_CONTROL_FIELDS = {
    "decision",
    "authorized effect",
    "exact target",
    "exact runtime change",
    "single focus",
    "expected prior focus head",
    "current owner basis",
    "bounded scope",
    "expected prior",
    "expected prior workpath",
    "route",
    "active waypoint",
    "expected prior main",
    "current workpath",
    "authorized successor",
}


def _normalize_declaration_label(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _unwrap_declaration_value(value: str) -> str:
    unwrapped = value.strip()
    if len(unwrapped) >= 2 and unwrapped.startswith("`") and unwrapped.endswith("`"):
        unwrapped = unwrapped[1:-1].strip()
    return unwrapped


def _store_declaration(fields: dict[str, str], label: str, value: str) -> None:
    normalized = _normalize_declaration_label(label)
    if normalized not in _DECLARED_CONTROL_FIELDS:
        return
    declared = _unwrap_declaration_value(value)
    if not declared:
        raise FailClosedError(f"Control Decision declaration {label!r} is empty")
    if normalized in fields:
        raise FailClosedError(f"Control Decision declaration {label!r} is duplicated")
    fields[normalized] = declared


def _markdown_structure(lines: list[str]) -> tuple[list[tuple[str, int, int]], list[bool]]:
    outside_fence = [False] * len(lines)
    fence_character: str | None = None
    fence_width = 0
    for index, line in enumerate(lines):
        if fence_character is not None:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence_character) + "{" + str(fence_width) + r",}[ \t]*",
                line,
            ):
                fence_character = None
                fence_width = 0
            continue
        opener = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opener:
            marker = opener.group(1)
            fence_character = marker[0]
            fence_width = len(marker)
            continue
        outside_fence[index] = True
    if fence_character is not None:
        raise FailClosedError("Control Decision contains an unterminated Markdown fence")

    headings = [
        (index, line[3:].strip())
        for index, line in enumerate(lines)
        if outside_fence[index] and line.startswith("## ")
    ]
    sections = [
        (heading, index + 1, headings[position + 1][0] if position + 1 < len(headings) else len(lines))
        for position, (index, heading) in enumerate(headings)
    ]
    return sections, outside_fence


def _markdown_sections(lines: list[str]) -> list[tuple[str, int, int]]:
    return _markdown_structure(lines)[0]


def parse_control_decision_declarations(text: str) -> dict[str, str]:
    """Parse only explicitly declared authority fields, never explanatory body prose."""
    if not isinstance(text, str):
        raise ValueError("Control Decision text must be a string")
    lines = text.splitlines()
    title_index = next((index for index, line in enumerate(lines) if line.strip()), None)
    first_nonempty = lines[title_index].lstrip("\ufeff") if title_index is not None else ""
    if not re.fullmatch(
        r"# PDC Control Decision(?:[ \t]+(?:—|-)[ \t]+[^\r\n]+)?[ \t]*",
        first_nonempty,
    ):
        raise FailClosedError("referenced file is not an activated PDC Control Decision")

    fields: dict[str, str] = {}
    sections, outside_fence = _markdown_structure(lines)
    metadata_end = sections[0][1] - 1 if sections else len(lines)
    metadata_started = False
    metadata_closed = False
    for index in range((title_index or 0) + 1, metadata_end):
        line = lines[index]
        if metadata_closed:
            continue
        if not outside_fence[index]:
            if line.strip():
                metadata_closed = True
            continue
        if not line.strip():
            if metadata_started:
                metadata_closed = True
            continue
        match = _DECLARATION_LINE.fullmatch(line)
        if not match:
            metadata_closed = True
            continue
        _store_declaration(fields, match.group(1), match.group(2))
        metadata_started = True

    for heading, start, end in sections:
        if _normalize_declaration_label(heading) != "authorized engineering work":
            continue
        index = start
        declaration_count = 0
        while index < end:
            if outside_fence[index] and not lines[index].strip():
                index += 1
                continue
            if not outside_fence[index]:
                raise FailClosedError(
                    "Authorized Engineering Work contains an unbound fenced block"
                )
            label_match = _FENCED_DECLARATION_LABEL.fullmatch(lines[index])
            if not label_match:
                raise FailClosedError(
                    "Authorized Engineering Work contains prose or a nested section"
                )
            fence_index = index + 1
            while (
                fence_index < end
                and outside_fence[fence_index]
                and not lines[fence_index].strip()
            ):
                fence_index += 1
            if (
                fence_index >= end
                or outside_fence[fence_index]
                or not re.fullmatch(r"```(?:text)?", lines[fence_index])
            ):
                raise FailClosedError(
                    "Authorized Engineering Work declaration is missing its exact value fence"
                )
            close_index = fence_index + 1
            while close_index < end and not (
                not outside_fence[close_index] and lines[close_index] == "```"
            ):
                close_index += 1
            if close_index >= end:
                raise FailClosedError("Control Decision fenced declaration is unterminated")
            if any(outside_fence[value_index] for value_index in range(fence_index, close_index + 1)):
                raise FailClosedError("Control Decision declaration value is not a Markdown fence")
            values = [line.strip() for line in lines[fence_index + 1 : close_index] if line.strip()]
            if len(values) != 1:
                raise FailClosedError("Control Decision fenced declaration must contain one exact value")
            _store_declaration(fields, label_match.group(1), values[0])
            declaration_count += 1
            index = close_index + 1
        if declaration_count == 0:
            raise FailClosedError("Authorized Engineering Work contains no declarations")

    if "decision" not in fields:
        raise FailClosedError("Control Decision is missing the declared Decision field")
    exact_targets = {
        fields[label]
        for label in ("exact target", "exact runtime change")
        if label in fields
    }
    if len(exact_targets) > 1:
        raise FailClosedError("Control Decision has conflicting exact target declarations")
    prior_workpaths = {
        fields[label]
        for label in ("expected prior", "expected prior workpath")
        if label in fields
    }
    if len(prior_workpaths) > 1:
        raise FailClosedError("Control Decision has conflicting expected prior Workpath declarations")
    return fields


def _activation_section(text: str) -> tuple[list[str], list[bool]] | None:
    lines = text.splitlines()
    markdown_sections, outside_fence = _markdown_structure(lines)
    sections = [
        (lines[start:end], outside_fence[start:end])
        for heading, start, end in markdown_sections
        if _normalize_declaration_label(heading) == "activation"
    ]
    if len(sections) > 1:
        raise FailClosedError("Control Decision has duplicate Activation sections")
    return sections[0] if sections else None


def _validate_control_decision_activation(
    root: Path,
    authority_commit_sha: str,
    ref: dict[str, str],
    text: str,
    fields: dict[str, str],
) -> None:
    activation = _activation_section(text)
    if activation is None:
        if "expected prior main" in fields:
            raise FailClosedError("Control Decision declares Expected prior main without Activation")
        return
    section, outside_fence = activation
    expected_parent = fields.get("expected prior main")
    if expected_parent is None or not HEX_40_OR_64.fullmatch(expected_parent):
        raise FailClosedError("activated Control Decision is missing a valid Expected prior main")
    activation_prefix = (
        r"(?:This decision becomes authoritative|This decision activates) "
        r"only through one non-forced fast-forward commit to `main`, "
    )
    inline_parent = re.compile(
        r"^"
        + activation_prefix
        + r"with sole parent `([0-9a-f]{40}(?:[0-9a-f]{24})?)`, changing exactly:[ \t]*$"
    )
    fenced_parent = re.compile(
        r"^" + activation_prefix + r"with sole parent:[ \t]*$"
    )
    intro_index = 0
    while (
        intro_index < len(section)
        and outside_fence[intro_index]
        and not section[intro_index].strip()
    ):
        intro_index += 1
    if intro_index >= len(section) or not outside_fence[intro_index]:
        raise FailClosedError("Control Decision Activation must begin with its exact declaration")
    intro_line = section[intro_index]
    inline_match = inline_parent.fullmatch(intro_line)
    if inline_match:
        parent_binding = (inline_match.group(1), intro_index)
    elif fenced_parent.fullmatch(intro_line):
        fence_index = intro_index + 1
        while (
            fence_index < len(section)
            and outside_fence[fence_index]
            and not section[fence_index].strip()
        ):
            fence_index += 1
        if (
            fence_index + 2 >= len(section)
            or section[fence_index].strip() != "```text"
            or outside_fence[fence_index]
            or not HEX_40_OR_64.fullmatch(section[fence_index + 1].strip())
            or outside_fence[fence_index + 1]
            or section[fence_index + 2].strip() != "```"
            or outside_fence[fence_index + 2]
        ):
            raise FailClosedError("Control Decision Activation parent fence is malformed")
        marker_index = fence_index + 3
        while (
            marker_index < len(section)
            and outside_fence[marker_index]
            and not section[marker_index].strip()
        ):
            marker_index += 1
        if (
            marker_index >= len(section)
            or not outside_fence[marker_index]
            or section[marker_index] != "and changing exactly:"
        ):
            raise FailClosedError("Control Decision Activation parent fence lacks its path marker")
        parent_binding = (section[fence_index + 1].strip(), marker_index)
    else:
        raise FailClosedError("Control Decision Activation must begin with its exact declaration")
    if parent_binding[0] != expected_parent:
        raise FailClosedError("Control Decision Activation does not bind its exact sole parent")

    marker_indexes = [
        index
        for index, line in enumerate(section)
        if outside_fence[index] and "changing exactly:" in line.casefold()
    ]
    if marker_indexes != [parent_binding[1]]:
        raise FailClosedError("Control Decision Activation must declare one exact changed-path set")
    declared_paths: list[str] = []
    declared_numbers: list[int] = []
    path_list_finished = False
    for index in range(marker_indexes[0] + 1, len(section)):
        line = section[index]
        if not outside_fence[index]:
            if not declared_paths:
                raise FailClosedError("Control Decision Activation changed paths must be outside fences")
            path_list_finished = True
            continue
        if not line.strip():
            continue
        match = re.fullmatch(r"(\d+)\.[ \t]+`([^`\r\n]+)`[.;]?[ \t]*", line)
        if not match:
            if not declared_paths:
                raise FailClosedError("Control Decision Activation changed-path list is missing")
            path_list_finished = True
            continue
        if path_list_finished:
            raise FailClosedError("Control Decision Activation changed-path list is non-contiguous")
        declared_numbers.append(int(match.group(1)))
        path = match.group(2)
        if (
            not path
            or "\\" in path
            or path.startswith("/")
            or re.match(r"^[A-Za-z]:/", path)
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or normalize_repo_path(path) != path
        ):
            raise FailClosedError("Control Decision Activation contains an unsafe changed path")
        declared_paths.append(path)
    if not declared_paths or declared_numbers != list(range(1, len(declared_paths) + 1)):
        raise FailClosedError("Control Decision Activation changed-path list is missing or non-sequential")
    if len(set(declared_paths)) != len(declared_paths):
        raise FailClosedError("Control Decision Activation changed-path set contains duplicates")

    parents = git_output(root, "show", "-s", "--format=%P", authority_commit_sha).split()
    if parents != [expected_parent]:
        raise FailClosedError("Control Decision authority commit does not have the declared sole parent")
    actual_paths = [
        path
        for path in git_output(
            root,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            authority_commit_sha,
        ).splitlines()
        if path
    ]
    if sorted(actual_paths) != sorted(declared_paths):
        raise FailClosedError("Control Decision authority commit changed paths differ from Activation")
    if ref["path"] not in declared_paths:
        raise FailClosedError("Control Decision path is absent from its declared Activation set")
    try:
        git_output(root, "rev-parse", "--verify", "refs/heads/main^{commit}")
    except ValueError as exc:
        raise FailClosedError("current main lineage is unavailable for Activation proof") from exc
    if not git_is_ancestor(root, authority_commit_sha, "refs/heads/main"):
        raise FailClosedError("Control Decision authority commit is outside current main lineage")

    successor = fields.get("authorized successor")
    if successor is None:
        raise FailClosedError("activated Control Decision is missing Authorized successor")
    if not re.fullmatch(r"wp-[0-9]{3,}", successor):
        raise FailClosedError("Control Decision Authorized successor is malformed")
    revision_path = f".ai-product/workpaths/revisions/{successor}.json"
    pointer_path = ".ai-product/workpaths/current.json"
    if revision_path not in declared_paths or pointer_path not in declared_paths:
        raise FailClosedError("Control Decision Activation omits its declared Workpath successor binding")
    try:
        revision = json.loads(git_show_bytes(root, authority_commit_sha, revision_path))
        pointer = json.loads(git_show_bytes(root, authority_commit_sha, pointer_path))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FailClosedError("Control Decision activated Workpath successor is unreadable") from exc
    if not isinstance(revision, dict) or revision.get("revision_id") != successor:
        raise FailClosedError("activated Workpath revision does not match Authorized successor")
    if not isinstance(pointer, dict) or pointer.get("revision_id") != successor:
        raise FailClosedError("activated Workpath pointer does not match Authorized successor")
    current_workpath = fields.get("current workpath")
    if current_workpath is None or not re.fullmatch(r"wp-[0-9]{3,}", current_workpath):
        raise FailClosedError("activated Control Decision is missing a valid Current Workpath")
    if revision.get("prior_revision_id") != current_workpath:
        raise FailClosedError("activated Workpath successor does not bind Current Workpath")
    single_focus = fields.get("single focus")
    if single_focus is None:
        raise FailClosedError("activated Control Decision is missing Single Focus")
    if revision.get("active_waypoint") != single_focus:
        raise FailClosedError("activated Workpath successor does not bind Single Focus waypoint")
    references = revision.get("source_authority_references")
    if not isinstance(references, list) or not any(
        isinstance(item, dict)
        and item.get("path") == ref["path"]
        and item.get("sha256") == ref["sha256"]
        for item in references
    ):
        raise FailClosedError("activated Workpath successor does not bind exact decision bytes")


def _canonical_control_decision_ref(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError("control_decision_ref must be null or exactly {path, sha256}")
    path = value.get("path")
    digest = value.get("sha256")
    if (
        not isinstance(path, str)
        or not path
        or "\\" in path
        or path.startswith("/")
        or re.match(r"^[A-Za-z]:/", path)
    ):
        raise ValueError("control_decision_ref.path must be canonical repository-relative POSIX path")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        raise ValueError("control_decision_ref.path must be traversal-safe")
    if normalize_repo_path(path) != path:
        raise ValueError("control_decision_ref.path must be canonical")
    if not isinstance(digest, str) or not HEX_64.fullmatch(digest):
        raise ValueError("control_decision_ref.sha256 must be lowercase 64-hex")
    return {"path": path, "sha256": digest}


def validate_control_decision_ref_at_commit(
    root: Path,
    authority_commit_sha: str,
    control_decision_ref: Any,
    *,
    selected_change: str | None = None,
    required_effect: str | None = None,
    expected_prior_focus_selection_id: str | None | object = _EXPECTED_PRIOR_UNSET,
) -> dict[str, str]:
    """Bind an explicit decision to exact activated bytes at an ancestor commit."""
    ref = _canonical_control_decision_ref(control_decision_ref)
    if ref is None:
        raise ValueError("an explicit Control Decision reference is required")
    if not isinstance(authority_commit_sha, str) or not HEX_40_OR_64.fullmatch(authority_commit_sha):
        raise ValueError("authority_commit_sha must be a full lowercase object id")
    resolved = git_output(root, "rev-parse", "--verify", f"{authority_commit_sha}^{{commit}}").lower()
    if resolved != authority_commit_sha:
        raise FailClosedError("authority_commit_sha differs from the resolved commit SHA")
    if not git_is_ancestor(root, authority_commit_sha, "HEAD"):
        raise FailClosedError("Control Decision authority commit is not activated in current history")
    try:
        content = git_show_bytes(root, authority_commit_sha, ref["path"])
    except ValueError as exc:
        raise FailClosedError("Control Decision path is absent at the authority commit") from exc
    if sha256_bytes(content) != ref["sha256"]:
        raise FailClosedError("Control Decision exact bytes do not match control_decision_ref.sha256")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Control Decision bytes are not valid UTF-8") from exc
    fields = parse_control_decision_declarations(text)
    _validate_control_decision_activation(root, authority_commit_sha, ref, text, fields)

    exact_target_values = {
        fields[label]
        for label in ("exact runtime change", "exact target")
        if label in fields
    }
    exact_target = next(iter(exact_target_values), None)
    declared_target = exact_target if exact_target is not None else fields.get("single focus")
    if selected_change is not None:
        if declared_target is None:
            raise FailClosedError("Control Decision is missing an exact selected-change declaration")
        if declared_target != selected_change:
            raise FailClosedError("Control Decision does not bind the exact selected change")
    if required_effect == "FOCUS_SELECTION":
        if fields.get("decision") != "FOCUS_SELECTION":
            raise FailClosedError("Control Decision does not bind the FOCUS_SELECTION effect")
        if (
            "authorized effect" in fields
            and fields["authorized effect"] != "FOCUS_SELECTION"
        ):
            raise FailClosedError("Control Decision has a conflicting Authorized effect")
        if "bounded scope" not in fields:
            raise FailClosedError("Control Decision does not bind a bounded Focus scope")
        if expected_prior_focus_selection_id is not _EXPECTED_PRIOR_UNSET:
            if expected_prior_focus_selection_id is not None and not isinstance(
                expected_prior_focus_selection_id, str
            ):
                raise ValueError("expected prior Focus head must be a string or null")
            prior_declarations = [
                fields[label]
                for label in ("expected prior focus head", "current owner basis")
                if label in fields
            ]
            if not prior_declarations:
                raise FailClosedError("Control Decision is missing the expected prior Focus binding")
            if expected_prior_focus_selection_id is None:
                null_states = {"null", "none", "unfocused"}
                matches = all(value.casefold() in null_states for value in prior_declarations)
            else:
                matches = all(
                    value == expected_prior_focus_selection_id for value in prior_declarations
                )
            if not matches:
                raise FailClosedError("Control Decision does not bind the expected prior Focus head")
    return ref


def _valid_transition_record(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    required = {
        "task_id", "pre_transition_workflow_digest", "from", "to",
        "contract_digest", "transition_id", "transition_record_digest",
    }
    if not required.issubset(record):
        return False
    if not isinstance(record["task_id"], str) or not record["task_id"]:
        return False
    if record.get("from") not in WORKFLOW_STATUSES or record.get("to") not in WORKFLOW_STATUSES:
        return False
    if not HEX_64.fullmatch(str(record["pre_transition_workflow_digest"])):
        return False
    contract_digest = record.get("contract_digest")
    if contract_digest is not None and not HEX_64.fullmatch(str(contract_digest)):
        return False
    expected_id = "tr-" + sha256_json(
        [
            record["task_id"],
            record["pre_transition_workflow_digest"],
            record["from"],
            record["to"],
            contract_digest,
        ]
    )
    return (
        record.get("transition_id") == expected_id
        and record.get("transition_record_digest")
        == digest_record(record, "transition_record_digest")
    )


def terminal_transition(workflow: dict[str, Any]) -> dict[str, Any] | None:
    history = workflow.get("history")
    if not isinstance(history, list) or not history:
        return None
    record = history[-1]
    return (
        record
        if _valid_transition_record(record)
        and record.get("task_id") == workflow.get("task_id")
        and record.get("to") == workflow.get("status")
        else None
    )


def workflow_transition_record(
    workflow: dict[str, Any], transition_id: str
) -> dict[str, Any] | None:
    history = workflow.get("history")
    if not isinstance(history, list):
        return None
    for record in history:
        if (
            isinstance(record, dict)
            and record.get("transition_id") == transition_id
            and _valid_transition_record(record)
        ):
            return record
    return None


def apply_workflow_transition(
    workflow: dict[str, Any],
    *,
    to_status: str,
    contract_digest: str | None,
    actor: str,
    reason: str,
    created_at: str | None = None,
    record_fields: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Apply one stable owner transition, or identify a completed replay."""
    task_id = workflow.get("task_id")
    from_status = workflow.get("status")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("workflow task_id is required for stable transition identity")
    if from_status not in WORKFLOW_STATUSES or to_status not in WORKFLOW_STATUSES:
        raise ValueError("workflow transition status is invalid")
    if contract_digest is not None and not HEX_64.fullmatch(contract_digest):
        raise ValueError("contract_digest must be null or lowercase 64-hex")
    existing = terminal_transition(workflow)
    if (
        from_status == to_status
        and existing is not None
        and existing.get("task_id") == task_id
        and existing.get("to") == to_status
        and existing.get("contract_digest") == contract_digest
    ):
        return existing, False
    before = copy.deepcopy(workflow)
    pre_digest = sha256_json(before)
    transition_id = "tr-" + sha256_json(
        [task_id, pre_digest, from_status, to_status, contract_digest]
    )
    record: dict[str, Any] = {
        "at": created_at or now_iso(),
        "task_id": task_id,
        "from": from_status,
        "to": to_status,
        "actor": actor,
        "reason": reason,
        "contract_digest": contract_digest,
        "pre_transition_workflow_digest": pre_digest,
        "transition_id": transition_id,
    }
    if record_fields:
        reserved = {
            "at",
            "task_id",
            "from",
            "to",
            "actor",
            "reason",
            "contract_digest",
            "pre_transition_workflow_digest",
            "transition_id",
            "transition_record_digest",
        }
        overlap = reserved.intersection(record_fields)
        if overlap:
            raise ValueError(
                "transition record_fields cannot override owner fields: " + ", ".join(sorted(overlap))
            )
        record.update(record_fields)
    record["transition_record_digest"] = digest_record(record, "transition_record_digest")
    workflow["status"] = to_status
    workflow["updated_at"] = record["at"]
    workflow.setdefault("history", []).append(record)
    return record, True


def build_focus_selection_record(
    *,
    selected_change: str,
    prior_focus_selection_id: str | None,
    owner_event_identity: str,
    authority_commit_sha: str,
    control_decision_ref: Any,
    actor: str,
    reason: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    ref = _canonical_control_decision_ref(control_decision_ref)
    if not isinstance(selected_change, str) or not selected_change:
        raise ValueError("selected_change must be non-empty")
    if prior_focus_selection_id is not None and not re.fullmatch(r"fs-[0-9a-f]{64}", prior_focus_selection_id):
        raise ValueError("prior_focus_selection_id is invalid")
    if not isinstance(authority_commit_sha, str) or not HEX_40_OR_64.fullmatch(authority_commit_sha):
        raise ValueError("authority_commit_sha must be a full lowercase object id")
    if actor not in {"controller", "product-owner"}:
        raise ValueError("Focus owner actor must be controller or product-owner")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Focus selection reason must be non-empty")
    timestamp = created_at or now_iso()
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("Focus created_at must be ISO-8601") from exc
    expected_identity = (
        "cd:" + ref["sha256"] if ref is not None else owner_event_identity
    )
    if ref is None:
        if not re.fullmatch(r"tr:tr-[0-9a-f]{64}", owner_event_identity):
            raise ValueError("null Focus authority requires typed transition owner identity")
    elif owner_event_identity != expected_identity:
        raise ValueError("explicit Focus owner identity must bind Control Decision SHA-256")
    focus_id = "fs-" + sha256_json(
        [
            selected_change,
            prior_focus_selection_id,
            owner_event_identity,
            ref["sha256"] if ref is not None else None,
        ]
    )
    record: dict[str, Any] = {
        "event": "focused_change_selected",
        "record_schema_version": 2,
        "focus_selection_id": focus_id,
        "selected_change": selected_change,
        "prior_focus_selection_id": prior_focus_selection_id,
        "owner_event_identity": owner_event_identity,
        "authority_commit_sha": authority_commit_sha,
        "control_decision_ref": ref,
        "actor": actor,
        "reason": reason,
        "created_at": timestamp,
    }
    record["record_digest"] = digest_record(record, "record_digest")
    return record


_LEGACY_FOCUS_REQUIRED_FIELDS = {"at", "event", "change", "actor", "reason"}
_LEGACY_FOCUS_ALLOWED_FIELDS = _LEGACY_FOCUS_REQUIRED_FIELDS | {
    "from_change",
    "record_schema_version",
}


def _legacy_focus_record_error(record: Any) -> str | None:
    if not isinstance(record, dict) or record.get("event") != "focused_change_selected":
        return "not a legacy Focus audit record"
    version = record.get("record_schema_version")
    if version is not None and not (type(version) is int and version == 1):
        return "legacy Focus record_schema_version must be absent or 1"
    missing = sorted(_LEGACY_FOCUS_REQUIRED_FIELDS - set(record))
    if missing:
        return "legacy Focus record is missing fields: " + ", ".join(missing)
    extras = sorted(set(record) - _LEGACY_FOCUS_ALLOWED_FIELDS)
    if extras:
        return "legacy Focus record contains owner or unknown fields: " + ", ".join(extras)
    for field in ("at", "change", "actor", "reason"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            return f"legacy Focus {field} must be a non-empty string"
    try:
        validate_change_name(record["change"])
    except ValueError as exc:
        return f"legacy Focus change is malformed: {exc}"
    from_change = record.get("from_change")
    if from_change is not None:
        if not isinstance(from_change, str) or not from_change.strip():
            return "legacy Focus from_change must be a non-empty string or null"
        try:
            validate_change_name(from_change)
        except ValueError as exc:
            return f"legacy Focus from_change is malformed: {exc}"
    return None


def _focus_record_error(record: Any) -> tuple[str | None, bool]:
    if not isinstance(record, dict) or record.get("event") != "focused_change_selected":
        return "not a Focus owner record", True
    version = record.get("record_schema_version")
    if type(version) is not int or version != 2:
        return "Focus owner record_schema_version must be 2", True
    try:
        rebuilt = build_focus_selection_record(
            selected_change=record.get("selected_change"),
            prior_focus_selection_id=record.get("prior_focus_selection_id"),
            owner_event_identity=record.get("owner_event_identity"),
            authority_commit_sha=record.get("authority_commit_sha"),
            control_decision_ref=record.get("control_decision_ref"),
            actor=record.get("actor"),
            reason=record.get("reason"),
            created_at=record.get("created_at"),
        )
    except (TypeError, ValueError) as exc:
        return str(exc), True
    if rebuilt["focus_selection_id"] != record.get("focus_selection_id"):
        return "focus_selection_id mismatch", False
    if digest_record(record, "record_digest") != record.get("record_digest"):
        return "Focus owner record_digest mismatch", False
    return None, False


def focus_selection_lineage(project: dict[str, Any]) -> dict[str, Any]:
    history = project.get("history")
    if not isinstance(history, list):
        return {
            "head": None,
            "valid_records": [],
            "findings": [],
            "errors": ["project history is invalid"],
            "schema_errors": ["project history is invalid"],
        }
    candidates = [item for item in history if isinstance(item, dict) and item.get("event") == "focused_change_selected"]
    valid: list[dict[str, Any]] = []
    invalid: list[tuple[dict[str, Any], str]] = []
    by_id: dict[str, dict[str, Any]] = {}
    findings: list[str] = []
    errors: list[str] = []
    schema_errors: list[str] = []
    schema_v2_seen = False
    for item in candidates:
        version = item.get("record_schema_version")
        if version is None or (type(version) is int and version == 1):
            legacy_error = _legacy_focus_record_error(item)
            if legacy_error:
                invalid.append((item, legacy_error))
                schema_errors.append(legacy_error)
            elif schema_v2_seen:
                legacy_error = "legacy Focus record appears after schema-v2 owner truth"
                invalid.append((item, legacy_error))
                schema_errors.append(legacy_error)
            continue
        if type(version) is int and version == 2:
            schema_v2_seen = True
        error, schema_error = _focus_record_error(item)
        if error:
            invalid.append((item, error))
            if schema_error:
                schema_errors.append(error)
            continue
        focus_id = item["focus_selection_id"]
        if focus_id in by_id:
            if by_id[focus_id] == item:
                findings.append(f"duplicate Focus owner record {focus_id}")
            else:
                errors.append(f"conflicting records share Focus owner ID {focus_id}")
            continue
        by_id[focus_id] = item
        valid.append(item)
    prior_ids = {item.get("prior_focus_selection_id") for item in valid if item.get("prior_focus_selection_id")}
    heads = [item for item in valid if item["focus_selection_id"] not in prior_ids]
    if len(heads) > 1:
        errors.append("competing valid Focus owner heads")
    head = heads[0] if len(heads) == 1 else None
    for item, error in invalid:
        prior = item.get("prior_focus_selection_id")
        claimed_id = item.get("focus_selection_id")
        if head is not None and (
            prior == head.get("focus_selection_id")
            or claimed_id == head.get("focus_selection_id")
        ):
            errors.append(f"invalid Focus record affects winner: {error}")
        else:
            findings.append(f"invalid non-head Focus history: {error}")
    if head is not None:
        seen: set[str] = set()
        cursor: dict[str, Any] | None = head
        while cursor is not None:
            focus_id = cursor["focus_selection_id"]
            if focus_id in seen:
                errors.append("Focus selection lineage cycle")
                break
            seen.add(focus_id)
            prior = cursor.get("prior_focus_selection_id")
            if prior is None:
                break
            cursor = by_id.get(prior)
            if cursor is None:
                errors.append(f"Focus lineage references missing prior head {prior}")
                break
    return {
        "head": head,
        "valid_records": valid,
        "findings": findings,
        "errors": errors,
        "schema_errors": schema_errors,
    }


def append_focus_selection_record(project: dict[str, Any], record: dict[str, Any]) -> bool:
    error, _ = _focus_record_error(record)
    if error:
        raise ValueError(error)
    history = project.setdefault("history", [])
    for existing in history:
        if isinstance(existing, dict) and existing.get("focus_selection_id") == record["focus_selection_id"]:
            return False
    lineage = focus_selection_lineage(project)
    if lineage["errors"]:
        raise FailClosedError("; ".join(lineage["errors"]))
    head = lineage["head"]
    expected_prior = head.get("focus_selection_id") if head is not None else None
    if record.get("prior_focus_selection_id") != expected_prior:
        raise FailClosedError("Focus selection prior head does not match current lineage")
    history.append(record)
    return True


def archive_legacy_focus_records(project: dict[str, Any]) -> int:
    """Preserve pre-schema-v2 selections as explicit non-owner audit entries."""
    history = project.get("history")
    if not isinstance(history, list):
        raise ValueError("project history is invalid")
    legacy_records: list[dict[str, Any]] = []
    schema_v2_seen = False
    for record in history:
        if not isinstance(record, dict) or record.get("event") != "focused_change_selected":
            continue
        version = record.get("record_schema_version")
        if type(version) is int and version == 2:
            schema_v2_seen = True
            continue
        legacy_error = _legacy_focus_record_error(record)
        if legacy_error:
            raise ValueError("cannot archive malformed legacy Focus record: " + legacy_error)
        if schema_v2_seen:
            raise ValueError("cannot archive legacy Focus record after schema-v2 owner truth")
        legacy_records.append(record)
    for record in legacy_records:
        record["legacy_event"] = "focused_change_selected"
        record["event"] = "legacy_focus_selection_audit"
        record["owner_authority"] = False
    return len(legacy_records)


def validate_null_focus_selection(
    active: dict[str, dict[str, Any]],
    *,
    selected_change: str,
    prior_focus_selection_id: str | None,
    lineage: dict[str, Any],
    actor: str,
) -> str:
    if actor != "controller":
        raise FailClosedError("null Focus reconciliation requires actor=controller")
    if lineage.get("errors"):
        raise FailClosedError("Focus lineage is ambiguous")
    head = lineage.get("head")
    actual_prior = head.get("focus_selection_id") if isinstance(head, dict) else None
    if actual_prior != prior_focus_selection_id:
        raise FailClosedError("null Focus prior head mismatch")
    non_parked = non_parked_changes(active)
    if non_parked != [selected_change]:
        raise FailClosedError("null Focus is legal only for exactly one recorded non-parked workflow")
    workflow = active.get(selected_change)
    if workflow is None:
        raise FailClosedError("selected workflow is missing")
    transition = terminal_transition(workflow)
    if transition is None:
        raise FailClosedError("null Focus requires a verified stable terminal transition")
    return "tr:" + transition["transition_id"]


def evaluate_focus_owner_truth(
    project: dict[str, Any], active: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    lineage = focus_selection_lineage(project)
    findings = list(lineage["findings"])
    errors = list(lineage["errors"])
    schema_errors = list(lineage.get("schema_errors", []))
    errors.extend(error for error in schema_errors if error not in errors)
    repair = None
    focus = project.get("current_change")
    head = lineage.get("head")
    non_parked = non_parked_changes(
        {name: workflow for name, workflow in active.items() if workflow.get("status") != "closed"}
    )
    if focus is not None and not isinstance(focus, str):
        errors.append("project current_change must be a string or null")
    if head is None:
        if isinstance(focus, str):
            errors.append("Focused project has no unique valid schema-v2 Focus owner head")
    else:
        selected = head.get("selected_change")
        workflow = active.get(selected) if isinstance(selected, str) else None
        if workflow is None:
            errors.append("selected Work is missing or unverifiable")
        elif workflow.get("status") == "closed":
            findings.append("selected Work is verifiably closed")
            repair = "UNFOCUS_AND_MARK_STALE"
        if focus != selected:
            findings.append("Focus projection is stale relative to owner head")
            if repair is None:
                repair = "PROJECT_OWNER_HEAD"
    if len(non_parked) > 1:
        errors.append("multiple non-parked workflow owners")
    elif len(non_parked) == 1 and (
        head is None or head.get("selected_change") != non_parked[0]
    ):
        errors.append("Focus owner head differs from the unique non-parked workflow owner")
    return {
        "truth_valid": not errors,
        "truth_unambiguous": not errors,
        "head": head,
        "findings": findings,
        "errors": errors,
        "schema_errors": schema_errors,
        "repair": repair,
    }


def _workflow_path(control_root: Path, change_name: str) -> Path:
    validate_change_name(change_name)
    return safe_child(control_root, "changes", change_name, "workflow-state.json")


def derive_active_changes(control_root: Path) -> dict[str, dict[str, Any]]:
    """Derive unfinished work only from per-change workflow authority."""
    changes_root = safe_child(control_root, "changes")
    if not changes_root.exists():
        return {}
    active: dict[str, dict[str, Any]] = {}
    for path in sorted(changes_root.iterdir(), key=lambda item: item.name):
        if not path.is_dir():
            continue
        validate_change_name(path.name)
        workflow_path = safe_child(path, "workflow-state.json")
        if not workflow_path.is_file():
            continue
        workflow = load_json_object(workflow_path)
        status = workflow.get("status")
        if status not in WORKFLOW_STATUSES:
            raise ValueError(f"{path.name}: invalid workflow status {status!r}")
        if status != "closed":
            active[path.name] = workflow
    return active


def non_parked_changes(active: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(name for name, workflow in active.items() if workflow.get("status") not in PARKED_STATUSES)


def assert_focused_change(
    control_root: Path,
    change_name: str,
    *,
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail before mutation unless the named unfinished change is the one Focused Change."""
    validate_change_name(change_name)
    if project is None:
        project = load_json_object(safe_child(control_root, "project-state.json"))
    focus = project.get("current_change")
    if focus != change_name:
        raise ValueError(
            f"focus_required: requested change {change_name} is not the Focused Change; current focus is {focus!r}"
        )
    active = derive_active_changes(control_root)
    if change_name not in active:
        raise ValueError(f"focus_required: Focused Change {change_name} is not unfinished workflow authority")
    non_parked = non_parked_changes(active)
    if len(non_parked) > 1:
        raise ValueError("multiple_non_parked: " + ", ".join(non_parked))
    if non_parked and non_parked[0] != change_name:
        raise ValueError(
            f"focus_conflict: Focused Change {change_name} differs from non-parked execution change {non_parked[0]}"
        )
    return active[change_name]


def project_focus_projection(project: dict[str, Any], change_name: str, workflow: dict[str, Any]) -> dict[str, Any]:
    result = dict(project)
    status = str(workflow.get("status"))
    if status not in STAGE_BY_STATUS or status == "closed":
        raise ValueError(f"cannot project Focused Change with status {status}")
    result["current_change"] = change_name
    result["current_task_status"] = status
    result["current_stage"] = STAGE_BY_STATUS[status]
    result["next_required_action"] = NEXT_ACTION_BY_STATUS[status]
    reason = workflow.get("blocked_reason")
    result["blocked_by"] = [reason] if status == "blocked" and isinstance(reason, str) and reason else []
    result["requires_user_decision"] = status == "ready_for_acceptance"
    return result


def unfocused_projection(project: dict[str, Any], active_names: Iterable[str]) -> dict[str, Any]:
    names = sorted(set(active_names))
    if not names:
        raise ValueError("unfocused projection requires at least one unfinished parked change")
    result = dict(project)
    result["current_change"] = None
    result["current_task_status"] = "unfocused"
    result["current_stage"] = "coordination"
    result["blocked_by"] = []
    if len(names) == 1:
        result["next_required_action"] = "select_focused_change"
        result["requires_user_decision"] = False
    else:
        result["next_required_action"] = "resolve_next_product_priority"
        result["requires_user_decision"] = True
    return result


def project_after_closure(control_root: Path, project: dict[str, Any], closed_change: str) -> dict[str, Any]:
    """Project navigation after a focused closure without auto-refocusing parked work."""
    active = derive_active_changes(control_root)
    active.pop(closed_change, None)
    if active:
        if non_parked_changes(active):
            raise ValueError("closure left a non-parked execution change; reconcile before continuing")
        return unfocused_projection(project, active)
    result = dict(project)
    result["current_change"] = None
    result["current_task_status"] = "closed"
    result["current_stage"] = "observation"
    result["next_required_action"] = "select_next_backlog_change"
    result["blocked_by"] = []
    result["requires_user_decision"] = False
    return result


def validate_baseline_freshness(root: Path, contract: dict[str, Any]) -> str:
    actual_identity = actual_repository_identity(root)
    expected_identity = contract.get("repository_identity") or contract.get("baseline", {}).get("repository")
    if actual_identity != expected_identity:
        raise ValueError(
            f"execution_base_mismatch: repository identity {actual_identity} differs from frozen {expected_identity}"
        )
    recorded_root = contract.get("repository_root")
    if recorded_root and Path(str(recorded_root)).expanduser().resolve() != root.resolve():
        raise ValueError("execution_base_mismatch: repository root differs from frozen contract")
    branch = str(contract.get("baseline", {}).get("branch", ""))
    current_tip = verify_git_branch(root, branch)
    frozen_tip = str(contract.get("baseline_branch_tip_sha", "")).lower()
    if not frozen_tip or current_tip != frozen_tip:
        raise ValueError(
            f"stale_baseline: frozen baseline branch tip {frozen_tip or '<missing>'} differs from current {current_tip}"
        )
    return current_tip


def validate_post_snapshot_resume_base(root: Path, contract: dict[str, Any], snapshot: dict[str, Any]) -> str:
    """Post-snapshot resume freshness for a blocked Work whose frozen branch tip has
    legitimately advanced past the frozen baseline tip (reviewed source integration +
    Controller control commits). The current tip must be a descendant of the frozen tip
    (no history rewrite or unrelated divergence); the exact current product-content
    identity against the snapshot manifest is validated separately by the caller.
    Pre-snapshot exact-tip freshness (validate_baseline_freshness) is unchanged.
    """
    actual_identity = actual_repository_identity(root)
    expected_identity = contract.get("repository_identity") or contract.get("baseline", {}).get("repository")
    if actual_identity != expected_identity:
        raise ValueError(
            "execution_base_mismatch: repository identity differs from frozen contract"
        )
    recorded_root = contract.get("repository_root")
    if recorded_root and Path(str(recorded_root)).expanduser().resolve() != root.resolve():
        raise ValueError("execution_base_mismatch: repository root differs from frozen contract")
    branch = str(contract.get("baseline", {}).get("branch", ""))
    current_branch = git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if current_branch != branch:
        raise ValueError(
            f"execution_base_mismatch: checked-out branch {current_branch!r} differs from frozen baseline branch {branch!r}"
        )
    current_tip = verify_git_branch(root, branch)
    if git_output(root, "rev-parse", "HEAD").lower() != current_tip:
        raise ValueError("execution_base_mismatch: HEAD differs from current baseline branch tip")
    frozen_tip = str(contract.get("baseline_branch_tip_sha", "")).lower()
    if not frozen_tip:
        raise ValueError("frozen baseline branch tip is missing")
    if current_tip != frozen_tip and not git_is_ancestor(root, frozen_tip, current_tip):
        raise ValueError(
            f"stale_baseline: current branch tip {current_tip[:12]} diverged or was rewritten from the frozen baseline tip {frozen_tip[:12]}"
        )
    return current_tip


def validate_clean_execution_base(root: Path, contract: dict[str, Any]) -> str:
    tip = validate_baseline_freshness(root, contract)
    branch = str(contract["baseline"]["branch"])
    current_branch = git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if current_branch != branch:
        raise ValueError(
            f"execution_base_mismatch: checked-out branch {current_branch!r} differs from frozen baseline branch {branch!r}"
        )
    head = git_output(root, "rev-parse", "HEAD").lower()
    if head != tip:
        raise ValueError(
            f"execution_base_mismatch: HEAD {head} differs from validated execution base {tip}"
        )
    dirty = non_control_git_status(root)
    if dirty:
        raise ValueError("execution_base_mismatch: non-controller working-tree/index changes are present")
    return tip


def changed_paths_from_revision(root: Path, revision: str) -> list[str]:
    tracked = git_output(root, "diff", "--name-only", "--diff-filter=ACDMRTUXB", revision, "--")
    untracked = git_output(root, "ls-files", "--others", "--exclude-standard")
    paths: set[str] = set()
    for text in (tracked, untracked):
        for raw in text.splitlines():
            normalized = raw.strip().replace("\\", "/")
            if normalized and not is_mutable_controller_record(normalized):
                paths.add(normalize_repo_path(normalized))
    return sorted(paths)


def validate_focused_partial_worktree(root: Path, contract: dict[str, Any]) -> list[str]:
    """Allow unfinished focused implementation only when every changed path stays in frozen scope."""
    validate_baseline_freshness(root, contract)
    branch = str(contract["baseline"]["branch"])
    current_branch = git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if current_branch != branch:
        raise ValueError("execution_base_mismatch: focused partial implementation is on the wrong branch")
    expected_tip = str(contract["baseline_branch_tip_sha"]).lower()
    head = git_output(root, "rev-parse", "HEAD").lower()
    if head != expected_tip:
        raise ValueError("execution_base_mismatch: focused partial implementation HEAD is not the validated base")
    paths = changed_paths_from_revision(root, str(contract["baseline"]["sha"]))
    disallowed = [path for path in paths if not path_allowed(path, contract.get("allowed_files", []))]
    if disallowed:
        raise ValueError("execution_base_mismatch: partial implementation contains out-of-scope paths: " + ", ".join(disallowed))
    return paths


def restore_paths_to_revision(root: Path, paths: Iterable[str], revision: str) -> None:
    """Restore only already-verified change-owned paths; never clean/reset unrelated work."""
    for relative in sorted(set(paths)):
        normalized = normalize_repo_path(relative)
        path = safe_child(root, *normalized.split("/"))
        if git_path_exists(root, revision, normalized):
            result = run_command(
                ("git", "restore", f"--source={revision}", "--staged", "--worktree", "--", normalized), cwd=root
            )
            if result.returncode != 0:
                raise ValueError(f"failed to restore verified path {normalized}:\n{result.stdout}")
        else:
            result = run_command(("git", "rm", "-f", "--cached", "--ignore-unmatch", "--", normalized), cwd=root)
            if result.returncode != 0:
                raise ValueError(f"failed to unstage verified added path {normalized}:\n{result.stdout}")
            if path.exists():
                if not path.is_file() or path.is_symlink():
                    raise ValueError(f"refusing to remove non-regular verified path {normalized}")
                path.unlink()


def materialize_snapshot(root: Path, snapshot: dict[str, Any]) -> None:
    """Restore the exact durable review content into worktree/index for the snapshot-owned paths."""
    review_commit = str(snapshot.get("review_commit_sha", ""))
    manifest = snapshot.get("file_manifest")
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("snapshot manifest is missing")
    for item in manifest:
        if not isinstance(item, dict):
            raise ValueError("snapshot manifest contains a non-object entry")
        relative = normalize_repo_path(str(item.get("path", "")))
        path = safe_child(root, *relative.split("/"))
        state = item.get("state")
        if state == "deleted":
            if path.exists():
                if not path.is_file() or path.is_symlink():
                    raise ValueError(f"refusing to delete non-regular snapshot path {relative}")
                path.unlink()
            result = run_command(("git", "rm", "-f", "--cached", "--ignore-unmatch", "--", relative), cwd=root)
            if result.returncode != 0:
                raise ValueError(f"failed to materialize deletion {relative}:\n{result.stdout}")
            continue
        if state != "present":
            raise ValueError(f"snapshot path {relative} has invalid state {state!r}")
        content = git_show_bytes(root, review_commit, relative)
        if sha256_bytes(content) != item.get("sha256") or len(content) != item.get("size"):
            raise ValueError(f"durable review content differs from snapshot manifest for {relative}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        result = run_command(("git", "add", "--", relative), cwd=root)
        if result.returncode != 0:
            raise ValueError(f"failed to stage materialized snapshot path {relative}:\n{result.stdout}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--change", required=True)
    parser.add_argument("--assert-focus", action="store_true", help="Preflight a change-specific source/evidence/Git mutation")
    args = parser.parse_args()
    if not args.assert_focus:
        print("ERROR: no operation selected; use --assert-focus", file=sys.stderr)
        return 2
    root = Path(args.root).expanduser().resolve()
    control_root = safe_child(root, ".ai-product")
    try:
        assert_focused_change(control_root, args.change)
        print(f"FOCUS OK: {args.change}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
