#!/usr/bin/env python3
"""Durable Strategic Workpath Controller state (M3: NEED-15 durability)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    atomic_write_json,
    controller_lock,
    digest_record,
    git_is_ancestor,
    git_output,
    git_show_bytes,
    load_json_object,
    now_iso,
    safe_child,
    sha256_file,
    sha256_json,
    validate_change_name,
)
from multi_change import (
    FailClosedError,
    focus_selection_lineage,
    parse_control_decision_declarations,
    terminal_transition,
    validate_control_decision_ref_at_commit,
)

WORKPATHS_NS = ".ai-product/workpaths"
CURRENT_POINTER = "current.json"
REVISIONS_DIR = "revisions"
WORKPATH_BINDING_VERSION = 1
WORKPATH_EFFECTS = {"MARK_STALE", "EXPLICIT_REBUILD"}
WORKPATH_JOURNAL_PHASES = {"PREPARED", "CANDIDATE_MATERIALIZED", "POINTER_PUBLISHED"}


def workpath_root(control_root: Path) -> Path:
    return safe_child(control_root, "workpaths")


def current_record(control_root: Path) -> dict[str, Any] | None:
    root = workpath_root(control_root)
    pointer = root / CURRENT_POINTER
    if not pointer.is_file():
        return None
    data = load_json_object(pointer)
    if not isinstance(data, dict) or not isinstance(data.get("revision_id"), str):
        raise ValueError("invalid Workpath current pointer")
    revision = root / REVISIONS_DIR / f"{data['revision_id']}.json"
    if not revision.is_file():
        raise ValueError(f"Workpath current pointer references missing revision {data['revision_id']}")
    return load_json_object(revision)


def list_revisions(control_root: Path) -> list[str]:
    root = workpath_root(control_root)
    rev_dir = root / REVISIONS_DIR
    if not rev_dir.is_dir():
        return []
    return sorted(p.stem for p in rev_dir.glob("*.json"))


WORKPATH_REVISION_FORMAT_VERSION = 2
OWNER_DOMAINS = ("Intent", "Learning", "Deliverable Reality", "Work-control")


def _validate_reference(ref: Any, errors: list[str], *, require_structured: bool) -> None:
    if not isinstance(ref, dict):
        if require_structured:
            errors.append("source_authority_references must be structured objects for new revisions")
        return
    path = ref.get("path")
    if not isinstance(path, str) or not path.strip() or ".." in path.replace("\\", "/").split("/"):
        errors.append("reference.path must be a traversal-safe repository-relative path")
    sha = ref.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        errors.append("reference.sha256 must be a 64-character SHA-256")
    owner = ref.get("owner_domain")
    if owner not in OWNER_DOMAINS:
        errors.append(f"reference.owner_domain must be one of {OWNER_DOMAINS}")
    version = ref.get("authority_version")
    if version is not None and not isinstance(version, str):
        errors.append("reference.authority_version must be a string or null")
    commit = ref.get("authority_commit_sha")
    if commit is not None and (not isinstance(commit, str) or len(commit) not in (40, 64)):
        errors.append("reference.authority_commit_sha must be a 40- or 64-character object id or null")


def _validate_projection(projection: dict[str, Any], errors: list[str], *, require_structured_refs: bool = False) -> None:
    if not isinstance(projection.get("route"), str) or not projection["route"].strip():
        errors.append("projection.route must be a non-empty string")
    if not isinstance(projection.get("active_waypoint"), str) or not projection["active_waypoint"].strip():
        errors.append("projection.active_waypoint must be a non-empty string")
    if not isinstance(projection.get("major_waypoints"), list) or not projection["major_waypoints"]:
        errors.append("projection.major_waypoints must be a non-empty list")
    if not isinstance(projection.get("revision_reason"), str) or not projection["revision_reason"].strip():
        errors.append("projection.revision_reason must be a non-empty string")
    refs = projection.get("source_authority_references")
    if not isinstance(refs, list):
        errors.append("projection.source_authority_references must be a list")
        return
    for ref in refs:
        _validate_reference(ref, errors, require_structured=require_structured_refs)
    if projection.get("provisional_future") is not None and not isinstance(projection["provisional_future"], str):
        errors.append("projection.provisional_future must be a string or null")


def _check_bound_source(root: Path, ref: dict[str, Any], errors: list[str]) -> None:
    """Verify the bound source file still exists with the recorded SHA-256.

    `root` is the repository root; reference paths are repository-relative, so a
    `.ai-product/...` reference resolves under <root>/.ai-product/... .
    """
    path = ref.get("path")
    if not isinstance(path, str):
        return
    safe = safe_child(root, *path.replace("\\", "/").split("/"))
    if not safe.is_file():
        errors.append(f"bound source missing: {path}")
        return
    actual = sha256_file(safe)
    if actual != ref.get("sha256"):
        errors.append(f"bound source changed: {path} (sha256 {actual[:12]} != {ref['sha256'][:12]})")


def _new_revision_id(control_root: Path) -> str:
    existing = set(list_revisions(control_root))
    index = 1
    while f"wp-{index:03d}" in existing:
        index += 1
    return f"wp-{index:03d}"


def validate_effect_pair(effect: str, explicit_control_decision: Any) -> None:
    if effect not in WORKPATH_EFFECTS:
        raise ValueError("Workpath effect must be MARK_STALE or EXPLICIT_REBUILD")
    if effect == "MARK_STALE" and explicit_control_decision is not None:
        raise FailClosedError("MARK_STALE requires explicit_control_decision=null")
    if effect == "EXPLICIT_REBUILD" and not isinstance(explicit_control_decision, dict):
        raise FailClosedError("EXPLICIT_REBUILD requires an explicit ControlDecisionRefV1 object")
    if isinstance(explicit_control_decision, dict):
        if set(explicit_control_decision) != {"path", "sha256"}:
            raise ValueError("explicit_control_decision must contain exactly path and sha256")
        path = explicit_control_decision.get("path")
        digest = explicit_control_decision.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or re.match(r"^[A-Za-z]:/", path)
            or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
        ):
            raise ValueError("explicit_control_decision.path is unsafe or non-canonical")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or digest.lower() != digest
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError("explicit_control_decision.sha256 must be lowercase 64-hex")


def projection_update_identity(
    owner_event_identity: str,
    expected_prior_revision_id: str | None,
    binding_version: int,
    effect: str,
    explicit_control_decision: dict[str, Any] | None,
) -> str:
    validate_effect_pair(effect, explicit_control_decision)
    if not isinstance(owner_event_identity, str) or not re.fullmatch(
        r"(?:tr:tr-|cd:)[0-9a-f]{64}", owner_event_identity
    ):
        raise ValueError("owner_event_identity must be typed tr:<transition_id> or cd:<decision-sha256>")
    if not isinstance(binding_version, int) or binding_version < 1:
        raise ValueError("binding_version must be a positive integer")
    decision_digest = (
        explicit_control_decision["sha256"] if explicit_control_decision is not None else None
    )
    return "pu-" + sha256_json(
        [
            owner_event_identity,
            expected_prior_revision_id,
            binding_version,
            effect,
            decision_digest,
        ]
    )


def _workpath_journal_path(control_root: Path, update_id: str) -> Path:
    return safe_child(control_root, "transactions", f"workpath-{update_id}.json")


def _candidate_revision(
    control_root: Path,
    *,
    prior: dict[str, Any] | None,
    projection: dict[str, Any],
    effect: str,
    explicit_control_decision: dict[str, Any] | None,
    authority_commit_sha: str,
    owner_event_identity: str,
    projection_update_id: str,
    binding_version: int,
    stale_reason: str | None,
) -> dict[str, Any]:
    revision = {
        "revision_format_version": WORKPATH_REVISION_FORMAT_VERSION,
        "revision_id": _new_revision_id(control_root),
        "route": projection["route"],
        "active_waypoint": projection["active_waypoint"],
        "major_waypoints": list(projection["major_waypoints"]),
        "ordering_rationale": projection.get("ordering_rationale") or "",
        "advancement_exit_conditions": projection.get("advancement_exit_conditions") or "",
        "provisional_future": projection.get("provisional_future"),
        "route_uncertainty": projection.get("route_uncertainty") or "",
        "source_authority_references": list(projection.get("source_authority_references", [])),
        "revision_reason": projection["revision_reason"],
        "prior_revision_id": prior["revision_id"] if prior is not None else None,
        "superseded_by": None,
        "stale": effect == "MARK_STALE",
        "stale_reason": stale_reason if effect == "MARK_STALE" else None,
        "created_at": now_iso(),
        "effect": effect,
        "explicit_control_decision": explicit_control_decision,
        "authority_commit_sha": authority_commit_sha,
        "owner_event_identity": owner_event_identity,
        "binding_version": binding_version,
        "projection_update_id": projection_update_id,
    }
    revision["revision_digest"] = digest_record(revision, "revision_digest")
    return revision


def _validate_publish_authority(
    control_root: Path,
    repository_root: Path,
    *,
    effect: str,
    explicit_control_decision: dict[str, Any] | None,
    authority_commit_sha: str,
    owner_event_identity: str,
    expected_prior_revision_id: str | None,
    projection: dict[str, Any],
) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", authority_commit_sha):
        raise ValueError("authority_commit_sha must be a full lowercase object id")
    resolved = git_output(
        repository_root, "rev-parse", "--verify", f"{authority_commit_sha}^{{commit}}"
    ).lower()
    if resolved != authority_commit_sha:
        raise FailClosedError("authority commit differs from the resolved commit")
    if not git_is_ancestor(repository_root, authority_commit_sha, "HEAD"):
        raise FailClosedError("authority commit is not activated in current history")

    if effect == "EXPLICIT_REBUILD":
        ref = validate_control_decision_ref_at_commit(
            repository_root,
            authority_commit_sha,
            explicit_control_decision,
        )
        if owner_event_identity != "cd:" + ref["sha256"]:
            raise FailClosedError("EXPLICIT_REBUILD owner identity differs from Control Decision")
        text = git_show_bytes(repository_root, authority_commit_sha, ref["path"]).decode("utf-8")
        fields = parse_control_decision_declarations(text)
        if fields.get("decision") != "EXPLICIT_REBUILD":
            raise FailClosedError("Control Decision does not declare EXPLICIT_REBUILD")
        if (
            "authorized effect" in fields
            and fields["authorized effect"] != "EXPLICIT_REBUILD"
        ):
            raise FailClosedError("Control Decision has a conflicting Authorized effect")
        prior_values = {
            fields[label]
            for label in ("expected prior", "expected prior workpath")
            if label in fields
        }
        if len(prior_values) != 1:
            raise FailClosedError("Control Decision is missing an unambiguous expected prior Workpath")
        declared_prior = next(iter(prior_values))
        if expected_prior_revision_id is None:
            prior_matches = declared_prior.casefold() in {"null", "none"}
        else:
            prior_matches = declared_prior == expected_prior_revision_id
        if not prior_matches:
            raise FailClosedError("Control Decision does not bind the expected prior Workpath")
        route = projection.get("route")
        waypoint = projection.get("active_waypoint")
        if not isinstance(route, str) or not isinstance(waypoint, str):
            raise ValueError("Workpath projection route and active_waypoint must be strings")
        if fields.get("route") != route:
            raise FailClosedError("Control Decision does not bind the exact Workpath route")
        if fields.get("active waypoint") != waypoint:
            raise FailClosedError("Control Decision does not bind the exact active waypoint")
        return

    project_path = safe_child(control_root, "project-state.json")
    if not project_path.is_file():
        raise FailClosedError("MARK_STALE requires a current Focus owner head")
    lineage = focus_selection_lineage(load_json_object(project_path))
    if lineage.get("schema_errors"):
        raise ValueError("Focus owner schema is malformed")
    if lineage["errors"]:
        raise FailClosedError("MARK_STALE Focus owner lineage is ambiguous")
    head = lineage.get("head")
    if not isinstance(head, dict):
        raise FailClosedError("MARK_STALE requires a current Focus owner head")

    if owner_event_identity.startswith("tr:"):
        selected_change = head.get("selected_change")
        if not isinstance(selected_change, str):
            raise ValueError("Focus owner selected_change is malformed")
        validate_change_name(selected_change)
        workflow_path = safe_child(
            control_root, "changes", selected_change, "workflow-state.json"
        )
        if workflow_path.is_file():
            terminal = terminal_transition(load_json_object(workflow_path))
            if (
                terminal is not None
                and owner_event_identity == "tr:" + terminal["transition_id"]
            ):
                return
        raise FailClosedError(
            "MARK_STALE transition owner is not the Focus-selected Work terminal event"
        )

    if head.get("owner_event_identity") == owner_event_identity:
        return
    raise FailClosedError("MARK_STALE Control Decision owner is not the current Focus owner head")


def publish_workpath_update(
    control_root: Path,
    projection: dict[str, Any],
    *,
    effect: str,
    explicit_control_decision: dict[str, Any] | None,
    authority_commit_sha: str,
    owner_event_identity: str,
    expected_prior_revision_id: str | None,
    repository_root: Path,
    binding_version: int = WORKPATH_BINDING_VERSION,
    stale_reason: str | None = None,
    bound_roots: list[Path] | None = None,
    fault_after_phase: str | None = None,
) -> dict[str, Any]:
    """Publish one journaled append-only Workpath successor with CAS recovery."""
    errors: list[str] = []
    _validate_projection(projection, errors, require_structured_refs=True)
    if errors:
        raise ValueError("invalid Workpath projection: " + "; ".join(errors))
    validate_effect_pair(effect, explicit_control_decision)
    if effect == "MARK_STALE" and (not isinstance(stale_reason, str) or not stale_reason.strip()):
        raise ValueError("MARK_STALE requires a non-empty stale_reason")
    if effect == "EXPLICIT_REBUILD" and stale_reason is not None:
        raise ValueError("EXPLICIT_REBUILD cannot carry stale_reason")
    repository_root = repository_root.expanduser().resolve()
    _validate_publish_authority(
        control_root,
        repository_root,
        effect=effect,
        explicit_control_decision=explicit_control_decision,
        authority_commit_sha=authority_commit_sha,
        owner_event_identity=owner_event_identity,
        expected_prior_revision_id=expected_prior_revision_id,
        projection=projection,
    )
    update_id = projection_update_identity(
        owner_event_identity,
        expected_prior_revision_id,
        binding_version,
        effect,
        explicit_control_decision,
    )
    request = {
        "projection": projection,
        "effect": effect,
        "explicit_control_decision": explicit_control_decision,
        "authority_commit_sha": authority_commit_sha,
        "owner_event_identity": owner_event_identity,
        "expected_prior_revision_id": expected_prior_revision_id,
        "binding_version": binding_version,
        "stale_reason": stale_reason,
    }
    request_digest = sha256_json(request)
    journal_path = _workpath_journal_path(control_root, update_id)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    root = workpath_root(control_root)
    revision_dir = root / REVISIONS_DIR
    revision_dir.mkdir(parents=True, exist_ok=True)
    roots = bound_roots if bound_roots is not None else [control_root.parent]

    if journal_path.is_file():
        journal = load_json_object(journal_path)
        if journal.get("request_digest") != request_digest:
            raise ValueError("existing Workpath journal request digest mismatch")
        phase = journal.get("phase")
        if phase not in WORKPATH_JOURNAL_PHASES:
            raise ValueError("existing Workpath journal phase is invalid")
        candidate = journal.get("candidate_revision")
        if not isinstance(candidate, dict):
            raise ValueError("existing Workpath journal candidate is invalid")
    else:
        prior = current_record(control_root)
        prior_id = prior.get("revision_id") if prior is not None else None
        if prior_id != expected_prior_revision_id:
            raise FailClosedError("CAS_A: current Workpath revision differs from expected prior")
        for ref in projection.get("source_authority_references", []):
            if isinstance(ref, dict):
                for bound_root in roots:
                    _check_bound_source(bound_root, ref, errors)
        if errors:
            raise ValueError("invalid Workpath bound references: " + "; ".join(errors))
        candidate = _candidate_revision(
            control_root,
            prior=prior,
            projection=projection,
            effect=effect,
            explicit_control_decision=explicit_control_decision,
            authority_commit_sha=authority_commit_sha,
            owner_event_identity=owner_event_identity,
            projection_update_id=update_id,
            binding_version=binding_version,
            stale_reason=stale_reason,
        )
        journal = {
            "schema_version": 1,
            "operation": "workpath_projection_publish",
            "projection_update_id": update_id,
            "request_digest": request_digest,
            "request": request,
            "expected_prior_revision_id": expected_prior_revision_id,
            "candidate_revision": candidate,
            "phase": "PREPARED",
            "started_at": now_iso(),
        }
        atomic_write_json(journal_path, journal)
        phase = "PREPARED"
        if fault_after_phase == phase:
            raise RuntimeError(f"injected fault after {phase}")

    candidate_path = revision_dir / f"{candidate['revision_id']}.json"
    if phase == "PREPARED":
        current = current_record(control_root)
        current_id = current.get("revision_id") if current is not None else None
        if current_id != expected_prior_revision_id:
            if candidate_path.is_file() and load_json_object(candidate_path) == candidate:
                candidate_path.unlink()
            journal_path.unlink()
            raise FailClosedError("CAS_B: newer Workpath owner route wins over prepared update")
        if candidate_path.exists():
            if load_json_object(candidate_path) != candidate:
                raise ValueError("candidate revision path is occupied by different bytes")
        else:
            atomic_write_json(candidate_path, candidate)
        journal["phase"] = "CANDIDATE_MATERIALIZED"
        atomic_write_json(journal_path, journal)
        phase = "CANDIDATE_MATERIALIZED"
        if fault_after_phase == phase:
            raise RuntimeError(f"injected fault after {phase}")

    if phase == "CANDIDATE_MATERIALIZED":
        if not candidate_path.is_file() or load_json_object(candidate_path) != candidate:
            raise ValueError("materialized Workpath candidate does not match journal")
        current = current_record(control_root)
        current_id = current.get("revision_id") if current is not None else None
        if current_id == candidate["revision_id"]:
            pass
        elif current_id != expected_prior_revision_id:
            if load_json_object(candidate_path) == candidate:
                candidate_path.unlink()
            journal_path.unlink()
            raise FailClosedError("CAS_C: newer explicit decision-bound route wins; pointer not overwritten")
        else:
            _validate_publish_authority(
                control_root,
                repository_root,
                effect=effect,
                explicit_control_decision=explicit_control_decision,
                authority_commit_sha=authority_commit_sha,
                owner_event_identity=owner_event_identity,
                expected_prior_revision_id=expected_prior_revision_id,
                projection=projection,
            )
            atomic_write_json(
                root / CURRENT_POINTER,
                {"revision_id": candidate["revision_id"], "updated_at": now_iso()},
            )
        journal["phase"] = "POINTER_PUBLISHED"
        atomic_write_json(journal_path, journal)
        phase = "POINTER_PUBLISHED"
        if fault_after_phase == phase:
            raise RuntimeError(f"injected fault after {phase}")

    current = current_record(control_root)
    if current is None or current.get("revision_id") != candidate["revision_id"]:
        raise FailClosedError("CAS_D: published Workpath pointer did not converge to candidate")
    if current.get("revision_digest") != digest_record(current, "revision_digest"):
        raise ValueError("published Workpath candidate digest mismatch")
    journal_path.unlink()
    return current


def create_initial(
    control_root: Path,
    projection: dict[str, Any],
    *,
    explicit_control_decision: dict[str, Any],
    authority_commit_sha: str,
    owner_event_identity: str,
    repository_root: Path,
) -> dict[str, Any]:
    """Create the first route only from an activated explicit Control Decision."""
    return publish_workpath_update(
        control_root,
        projection,
        effect="EXPLICIT_REBUILD",
        explicit_control_decision=explicit_control_decision,
        authority_commit_sha=authority_commit_sha,
        owner_event_identity=owner_event_identity,
        expected_prior_revision_id=None,
        repository_root=repository_root,
    )


def revise(
    control_root: Path,
    projection: dict[str, Any],
    *,
    explicit_control_decision: dict[str, Any],
    authority_commit_sha: str,
    owner_event_identity: str,
    expected_prior_revision_id: str,
    repository_root: Path,
    bound_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Create an append-only non-stale successor from explicit route authority."""
    return publish_workpath_update(
        control_root,
        projection,
        effect="EXPLICIT_REBUILD",
        explicit_control_decision=explicit_control_decision,
        authority_commit_sha=authority_commit_sha,
        owner_event_identity=owner_event_identity,
        expected_prior_revision_id=expected_prior_revision_id,
        repository_root=repository_root,
        bound_roots=bound_roots,
    )


def mark_stale(
    control_root: Path,
    reason: str,
    *,
    authority_commit_sha: str,
    owner_event_identity: str,
    expected_prior_revision_id: str,
    repository_root: Path,
    projection: dict[str, Any] | None = None,
    bound_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Append a stale successor revision and advance the pointer; never mutates the current revision in place."""
    current = current_record(control_root)
    if current is None:
        raise ValueError("no Workpath exists; cannot mark stale")
    if not reason.strip():
        raise ValueError("stale reason must be non-empty")
    update_id = projection_update_identity(
        owner_event_identity,
        expected_prior_revision_id,
        WORKPATH_BINDING_VERSION,
        "MARK_STALE",
        None,
    )
    journal_path = _workpath_journal_path(control_root, update_id)
    journal_projection = None
    if journal_path.is_file():
        journal = load_json_object(journal_path)
        request = journal.get("request")
        if isinstance(request, dict) and isinstance(request.get("projection"), dict):
            journal_projection = request["projection"]
    if journal_projection is not None:
        base = journal_projection
    elif projection is not None:
        base = dict(projection)
    else:
        if current.get("revision_format_version") is None:
            raise ValueError(
                "current revision is legacy format; caller must supply structured source_authority_references"
            )
        base = {
            "route": current["route"],
            "active_waypoint": current["active_waypoint"],
            "major_waypoints": list(current["major_waypoints"]),
            "ordering_rationale": current.get("ordering_rationale") or "",
            "advancement_exit_conditions": current.get("advancement_exit_conditions") or "",
            "provisional_future": current.get("provisional_future"),
            "route_uncertainty": current.get("route_uncertainty") or "",
            "source_authority_references": list(current.get("source_authority_references", [])),
            "revision_reason": f"Marked stale: {reason}",
        }
    return publish_workpath_update(
        control_root,
        base,
        effect="MARK_STALE",
        explicit_control_decision=None,
        authority_commit_sha=authority_commit_sha,
        owner_event_identity=owner_event_identity,
        expected_prior_revision_id=expected_prior_revision_id,
        repository_root=repository_root,
        stale_reason=reason,
        bound_roots=bound_roots,
    )


def is_stale(control_root: Path) -> tuple[bool, str | None]:
    current = current_record(control_root)
    if current is None:
        return False, None
    return bool(current.get("stale")), current.get("stale_reason")


def lineage_ids(control_root: Path) -> list[str]:
    """Walk the current pointer backward via prior_revision_id only."""
    ids: list[str] = []
    seen: set[str] = set()
    current = current_record(control_root)
    while current is not None:
        rev_id = current["revision_id"]
        if rev_id in seen:
            raise ValueError(f"Workpath lineage cycle detected at {rev_id}")
        seen.add(rev_id)
        ids.append(rev_id)
        prior_id = current.get("prior_revision_id")
        if prior_id is None:
            break
        rev_path = workpath_root(control_root) / REVISIONS_DIR / f"{prior_id}.json"
        if not rev_path.is_file():
            raise ValueError(f"unknown predecessor {prior_id} of {rev_id}")
        current = load_json_object(rev_path)
    return ids


def verify_record(control_root: Path) -> list[str]:
    errors: list[str] = []
    root = workpath_root(control_root)
    pointer = root / CURRENT_POINTER
    if not pointer.is_file():
        errors.append("Workpath current pointer missing")
        return errors
    data = load_json_object(pointer)
    rev_id = data.get("revision_id")
    revision_path = root / REVISIONS_DIR / f"{rev_id}.json"
    if not revision_path.is_file():
        errors.append(f"current revision {rev_id} missing")
        return errors
    revision = load_json_object(revision_path)
    if revision.get("revision_digest") != digest_record(revision, "revision_digest"):
        errors.append(f"revision {rev_id} digest mismatch")
    if revision.get("superseded_by") is not None:
        errors.append(f"current revision {rev_id} is marked superseded")
    # Lineage integrity: cycle / unknown predecessor / fork ambiguity / dangling revisions.
    try:
        lineage = lineage_ids(control_root)
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    for lineage_id in lineage:
        lineage_path = root / REVISIONS_DIR / f"{lineage_id}.json"
        record = load_json_object(lineage_path)
        if record.get("revision_digest") != digest_record(record, "revision_digest"):
            errors.append(f"revision {lineage_id} digest mismatch")
        if "binding_version" in record or "projection_update_id" in record:
            required = {
                "effect",
                "explicit_control_decision",
                "authority_commit_sha",
                "owner_event_identity",
                "binding_version",
                "projection_update_id",
            }
            missing = sorted(required - set(record))
            if missing:
                errors.append(
                    f"revision {lineage_id} missing A1 publication fields: " + ", ".join(missing)
                )
                continue
            try:
                expected_update_id = projection_update_identity(
                    record["owner_event_identity"],
                    record.get("prior_revision_id"),
                    record["binding_version"],
                    record["effect"],
                    record["explicit_control_decision"],
                )
            except ValueError as exc:
                errors.append(f"revision {lineage_id} A1 publication binding invalid: {exc}")
            else:
                if record.get("projection_update_id") != expected_update_id:
                    errors.append(f"revision {lineage_id} projection_update_id mismatch")
    for other in root.glob(f"{REVISIONS_DIR}/*.json"):
        rec = load_json_object(other)
        rid = rec.get("revision_id")
        if rid in lineage:
            continue
        # A revision outside the current lineage is allowed only as a historical leaf that was
        # superseded (its successor is in the lineage). Anything else is a dangling fork.
        successor = rec.get("superseded_by")
        if successor not in lineage and rid not in lineage:
            errors.append(f"dangling revision outside current lineage: {rid}")
    transaction_root = safe_child(control_root, "transactions")
    if transaction_root.is_dir():
        for journal in sorted(transaction_root.glob("workpath-*.json")):
            errors.append(f"residual Workpath publication journal: {journal.name}")
    # Fork ambiguity: every non-current revision must have exactly one lineage path; we detect by
    # verifying that each revision's prior chain cannot reach two different heads. Simplest robust
    # check: the lineage set is exactly the set reachable from current; a fork would produce a
    # revision whose successor pointer is missing from the lineage while also not being current.
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--control-root", help="Explicit .ai-product control root (default <root>/.ai-product)")
    parser.add_argument("--change", help="Change name (validated when provided)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show", help="Show current Workpath record")
    init_p = sub.add_parser("init", help="Create initial Workpath record")
    init_p.add_argument("--route", required=True)
    init_p.add_argument("--waypoint", required=True)
    init_p.add_argument("--waypoints", action="append", required=True)
    init_p.add_argument("--reason", required=True)
    init_p.add_argument("--rationale", default="")
    init_p.add_argument("--conditions", default="")
    init_p.add_argument("--future", default=None)
    init_p.add_argument("--uncertainty", default="")
    init_p.add_argument("--reference-json", action="append", default=[])
    init_p.add_argument("--authority-commit", required=True)
    init_p.add_argument("--owner-event-identity", required=True)
    init_p.add_argument("--control-decision-path", required=True)
    init_p.add_argument("--control-decision-sha256", required=True)
    rev_p = sub.add_parser("revise", help="Create a new current revision (append-only)")
    rev_p.add_argument("--route", required=True)
    rev_p.add_argument("--waypoint", required=True)
    rev_p.add_argument("--waypoints", action="append", required=True)
    rev_p.add_argument("--reason", required=True)
    rev_p.add_argument("--rationale", default="")
    rev_p.add_argument("--conditions", default="")
    rev_p.add_argument("--future", default=None)
    rev_p.add_argument("--uncertainty", default="")
    rev_p.add_argument("--reference-json", action="append", default=[])
    rev_p.add_argument("--authority-commit", required=True)
    rev_p.add_argument("--owner-event-identity", required=True)
    rev_p.add_argument("--control-decision-path", required=True)
    rev_p.add_argument("--control-decision-sha256", required=True)
    rev_p.add_argument("--expected-prior-revision-id", required=True)
    stale_p = sub.add_parser("mark-stale", help="Append a stale successor revision")
    stale_p.add_argument("--reason", required=True)
    stale_p.add_argument("--reference-json", action="append", default=[])
    stale_p.add_argument("--authority-commit", required=True)
    stale_p.add_argument("--owner-event-identity", required=True)
    stale_p.add_argument("--expected-prior-revision-id", required=True)
    sub.add_parser("verify", help="Verify Workpath record integrity")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    control_root = Path(args.control_root).expanduser().resolve() if args.control_root else safe_child(root, ".ai-product")
    try:
        if args.change:
            validate_change_name(args.change)
        with controller_lock(control_root):
            if args.command == "show":
                current = current_record(control_root)
                print(json.dumps(current, ensure_ascii=False, indent=2) if current else "NO WORKPATH")
                return 0
            if args.command in ("init", "revise", "mark-stale"):
                refs = []
                for raw in args.reference_json:
                    try:
                        ref = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"invalid --reference-json: {exc}") from exc
                    refs.append(ref)
                if args.command == "init":
                    projection = {
                        "route": args.route,
                        "active_waypoint": args.waypoint,
                        "major_waypoints": list(args.waypoints),
                        "revision_reason": args.reason,
                        "ordering_rationale": args.rationale,
                        "advancement_exit_conditions": args.conditions,
                        "provisional_future": args.future,
                        "route_uncertainty": args.uncertainty,
                        "source_authority_references": refs,
                    }
                    decision_ref = {
                        "path": args.control_decision_path,
                        "sha256": args.control_decision_sha256,
                    }
                    revision = create_initial(
                        control_root,
                        projection,
                        explicit_control_decision=decision_ref,
                        authority_commit_sha=args.authority_commit,
                        owner_event_identity=args.owner_event_identity,
                        repository_root=root,
                    )
                elif args.command == "revise":
                    projection = {
                        "route": args.route,
                        "active_waypoint": args.waypoint,
                        "major_waypoints": list(args.waypoints),
                        "revision_reason": args.reason,
                        "ordering_rationale": args.rationale,
                        "advancement_exit_conditions": args.conditions,
                        "provisional_future": args.future,
                        "route_uncertainty": args.uncertainty,
                        "source_authority_references": refs,
                    }
                    decision_ref = {
                        "path": args.control_decision_path,
                        "sha256": args.control_decision_sha256,
                    }
                    revision = revise(
                        control_root,
                        projection,
                        explicit_control_decision=decision_ref,
                        authority_commit_sha=args.authority_commit,
                        owner_event_identity=args.owner_event_identity,
                        expected_prior_revision_id=args.expected_prior_revision_id,
                        repository_root=root,
                    )
                else:  # mark-stale
                    if refs:
                        projection = {
                            "route": current_record(control_root)["route"],
                            "active_waypoint": current_record(control_root)["active_waypoint"],
                            "major_waypoints": list(current_record(control_root)["major_waypoints"]),
                            "revision_reason": f"Marked stale: {args.reason}",
                            "source_authority_references": refs,
                        }
                        revision = mark_stale(
                            control_root,
                            args.reason,
                            authority_commit_sha=args.authority_commit,
                            owner_event_identity=args.owner_event_identity,
                            expected_prior_revision_id=args.expected_prior_revision_id,
                            repository_root=root,
                            projection=projection,
                        )
                    else:
                        revision = mark_stale(
                            control_root,
                            args.reason,
                            authority_commit_sha=args.authority_commit,
                            owner_event_identity=args.owner_event_identity,
                            expected_prior_revision_id=args.expected_prior_revision_id,
                            repository_root=root,
                        )
            else:  # verify
                errors = verify_record(control_root)
                if errors:
                    print("WORKPATH RECORD INVALID")
                    for error in errors:
                        print(f"- {error}")
                    return 1
                print("WORKPATH RECORD VALID")
                return 0
        print(f"Workpath {args.command}: revision {revision['revision_id']} digest {revision['revision_digest']}")
        return 0
    except FailClosedError as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
