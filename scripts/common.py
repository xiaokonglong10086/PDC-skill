#!/usr/bin/env python3
"""Shared deterministic helpers for product-development-controller scripts."""

from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import json
import os
import re
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import urlparse

CONTROLLER_VERSION = "3.0.0"

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
PLACEHOLDER_PATTERNS = (
    re.compile(r"\b(?:TODO|TBD|NEEDS CLARIFICATION)\b", re.IGNORECASE),
    re.compile(r"\{\{[^}]+\}\}"),
    re.compile(r"^\s*\[[^\]]+\]\s*$"),
)

# Reviewable Control-Infrastructure Identity v1: path role, not directory name, decides
# whether a path participates in exact implementation/deliverable identity.
IDENTITY_POLICY_LEGACY = "legacy"
IDENTITY_POLICY_V1 = "reviewable-control-infrastructure-v1"
SUPPORTED_IDENTITY_POLICIES = (IDENTITY_POLICY_V1,)
RESERVED_MUTABLE_RECORD_EXACT = ".ai-product/project-state.json"
# The transient Controller bookkeeping lock is always a Mutable Controller Record: it is held
# during every lifecycle operation and must never enter implementation changed-file identity.
CONTROLLER_LOCK_PATH = ".ai-product/.controller.lock"
RESERVED_MUTABLE_RECORD_PREFIXES = (
    ".ai-product/changes/",
    ".ai-product/transactions/",
    ".ai-product/backups/",
    ".ai-product/handoffs/",
    # M3: durable Strategic Workpath Controller state (Work-control records).
    ".ai-product/workpaths/",
)
RESERVED_MUTABLE_RECORD_EXACT_FILES = (
    RESERVED_MUTABLE_RECORD_EXACT,
    CONTROLLER_LOCK_PATH,
)


def is_mutable_controller_record(relative_path: str) -> bool:
    """True for reserved Mutable Controller Record paths (never Work deliverable identity)."""
    normalized = relative_path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in RESERVED_MUTABLE_RECORD_EXACT_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in RESERVED_MUTABLE_RECORD_PREFIXES)


def is_legacy_controller_path(relative_path: str) -> bool:
    """Legacy snapshot schema-v2 rule: every .ai-product path is controller-owned."""
    normalized = relative_path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized == ".ai-product" or normalized.startswith(".ai-product/")


def path_included_in_identity(relative_path: str, policy: str) -> bool:
    """Whether a repository path participates in implementation changed-file identity."""
    if policy == IDENTITY_POLICY_LEGACY:
        return not is_legacy_controller_path(relative_path)
    if policy == IDENTITY_POLICY_V1:
        return not is_mutable_controller_record(relative_path)
    raise ValueError(f"unsupported identity policy {policy!r}")


def identity_policy_of(snapshot: dict[str, Any]) -> str:
    """Return the identity policy for a snapshot; fail closed on unknown schema/policy."""
    schema = snapshot.get("schema_version")
    if schema == 2:
        return IDENTITY_POLICY_LEGACY
    if schema == 3:
        policy = snapshot.get("identity_policy")
        if policy in SUPPORTED_IDENTITY_POLICIES:
            return policy
        raise ValueError(f"unsupported identity_policy {policy!r} for snapshot schema v3")
    raise ValueError(f"unsupported snapshot schema_version {schema!r}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso8601(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty ISO 8601 string")
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be valid ISO 8601: {text}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone: {text}")
    return text


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object at the top level")
    return data


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(data: Any) -> str:
    return sha256_bytes(canonical_json_bytes(data))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        return any(pattern.search(text) for pattern in PLACEHOLDER_PATTERNS)
    return False


def require_string(errors: list[str], label: str, value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        errors.append(f"{label} must be a string")
        return ""
    text = value.strip()
    if not allow_empty and is_placeholder(text):
        errors.append(f"{label} is missing or still contains a placeholder")
    return text


def require_integer(errors: list[str], label: str, value: Any, *, minimum: int | None = None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{label} must be an integer")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{label} must be at least {minimum}")
    return value


def require_list(errors: list[str], label: str, value: Any, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    if nonempty and not value:
        errors.append(f"{label} must be a non-empty list")
    return value


def require_object(errors: list[str], label: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def require_iso8601(errors: list[str], label: str, value: Any) -> str:
    try:
        return parse_iso8601(value, label)
    except ValueError as exc:
        errors.append(str(exc))
        return ""


def require_valid_id(errors: list[str], label: str, value: Any) -> str:
    text = require_string(errors, label, value)
    if text and not ID_PATTERN.fullmatch(text):
        errors.append(
            f"{label} must match {ID_PATTERN.pattern}; path separators and traversal are forbidden"
        )
    return text


def require_sha(errors: list[str], label: str, value: Any) -> str:
    text = require_string(errors, label, value)
    if text and not SHA_PATTERN.fullmatch(text):
        errors.append(f"{label} must be a full 40- or 64-character hexadecimal commit SHA")
    return text.lower()


def require_sha256(errors: list[str], label: str, value: Any) -> str:
    text = require_string(errors, label, value)
    if text and not SHA256_PATTERN.fullmatch(text):
        errors.append(f"{label} must be a 64-character hexadecimal SHA-256 digest")
    return text.lower()


def ensure_unique_ids(errors: list[str], label: str, items: list[Any]) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        item_id = require_valid_id(errors, f"{label}[{index}].id", item.get("id"))
        if item_id:
            if item_id in seen:
                errors.append(f"{label} contains duplicate id {item_id}")
            seen.add(item_id)
    return seen


def ensure_known_keys(errors: list[str], label: str, data: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        errors.append(f"{label} contains unknown fields: {', '.join(unknown)}")


def ensure_required_keys(errors: list[str], label: str, data: dict[str, Any], required: set[str]) -> None:
    missing = sorted(required - set(data))
    for key in missing:
        errors.append(f"{label} is missing field: {key}")


def safe_child(root: Path, *parts: str) -> Path:
    resolved_root = root.expanduser().resolve()
    candidate = resolved_root.joinpath(*parts).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError(f"path escapes allowed root: {candidate}")
    return candidate


def validate_change_name(value: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"change name must match {ID_PATTERN.pattern}; path separators and traversal are forbidden"
        )
    return value


def validate_task_id(value: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"task id must match {ID_PATTERN.pattern}; path separators and traversal are forbidden"
        )
    return value


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    check: bool = False,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=env,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise ValueError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}")
    return result


def run_shell_command(
    command: str,
    *,
    cwd: Path,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )


def git_output(root: Path, *args: str) -> str:
    result = run_command(("git", *args), cwd=root)
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed:\n{result.stdout}")
    return result.stdout.strip()


def semantic_index_digest(root: Path) -> str:
    """Hash canonical staged-index entries, excluding mutable index stat-cache bytes."""
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        output = result.stderr.decode("utf-8", errors="replace")
        raise ValueError(f"git ls-files --stage failed:\n{output}")
    return sha256_bytes(result.stdout)


def verify_git_commit(root: Path, sha: str) -> str:
    require = sha.lower()
    if not SHA_PATTERN.fullmatch(require):
        raise ValueError("commit SHA must be a full 40- or 64-character hexadecimal value")
    resolved = git_output(root, "rev-parse", "--verify", f"{require}^{{commit}}")
    return resolved.lower()


def verify_git_branch(root: Path, branch: str) -> str:
    if not isinstance(branch, str) or not branch.strip():
        raise ValueError("branch must be a non-empty string")
    name = branch.strip()
    if name.startswith("-") or any(token in name for token in ("..", "~", "^", ":", "?", "*", "[", "\\")):
        raise ValueError(f"unsafe or invalid branch reference: {name}")
    return git_output(root, "rev-parse", "--verify", f"{name}^{{commit}}").lower()


def git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = run_command(("git", "merge-base", "--is-ancestor", ancestor, descendant), cwd=root)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise ValueError(f"git merge-base failed:\n{result.stdout}")


def git_top_level(root: Path) -> Path:
    return Path(git_output(root, "rev-parse", "--show-toplevel")).resolve()


def normalize_repository_identity(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("repository identity cannot be empty")
    if text.startswith("local:"):
        local_path = Path(text[6:]).expanduser().resolve().as_posix()
        return f"local:{local_path}"
    if text.startswith("git@") and ":" in text:
        host_part, path = text.split(":", 1)
        host = host_part.split("@", 1)[1].lower()
        clean = path.strip("/")
        if clean.endswith(".git"):
            clean = clean[:-4]
        return f"{host}/{clean}"
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        host = parsed.hostname.lower() if parsed.hostname else parsed.netloc.lower()
        clean = parsed.path.strip("/")
        if clean.endswith(".git"):
            clean = clean[:-4]
        return f"{host}/{clean}"
    clean = text.strip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    return clean


def actual_repository_identity(root: Path) -> str:
    top = git_top_level(root)
    result = run_command(("git", "remote", "get-url", "origin"), cwd=top)
    if result.returncode == 0 and result.stdout.strip():
        return normalize_repository_identity(result.stdout.strip())
    return f"local:{top.as_posix()}"


def current_branch(root: Path) -> str | None:
    result = run_command(("git", "symbolic-ref", "--quiet", "--short", "HEAD"), cwd=root)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def normalize_repo_path(value: str, *, allow_directory_suffix: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("repository path must be a string")
    text = value.replace("\\", "/").strip()
    if text.startswith("./"):
        text = text.removeprefix("./")
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        raise ValueError(f"path must be repository-relative: {value}")
    directory_suffix = text.endswith("/")
    parts = text[:-1].split("/") if directory_suffix else text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"path contains invalid or traversal segment: {value}")
    normalized = "/".join(parts)
    if directory_suffix:
        if not allow_directory_suffix:
            raise ValueError(f"directory suffix is not allowed here: {value}")
        normalized += "/"
    return normalized


def _slash_glob_match(path: str, pattern: str) -> bool:
    path_parts = tuple(path.split("/"))
    pattern_parts = tuple(pattern.split("/"))

    @lru_cache(maxsize=None)
    def match(pi: int, gi: int) -> bool:
        if gi == len(pattern_parts):
            return pi == len(path_parts)
        token = pattern_parts[gi]
        if token == "**":
            return match(pi, gi + 1) or (pi < len(path_parts) and match(pi + 1, gi))
        if pi >= len(path_parts):
            return False
        return fnmatch.fnmatchcase(path_parts[pi], token) and match(pi + 1, gi + 1)

    return match(0, 0)


def path_allowed(relative_path: str, allowed_patterns: list[str]) -> bool:
    try:
        normalized = normalize_repo_path(relative_path)
    except ValueError:
        return False
    for raw in allowed_patterns:
        try:
            pattern = normalize_repo_path(raw, allow_directory_suffix=True)
        except ValueError:
            continue
        if pattern.endswith("/"):
            if normalized.startswith(pattern):
                return True
            continue
        if any(char in pattern for char in "*?["):
            if _slash_glob_match(normalized, pattern):
                return True
            continue
        if normalized == pattern:
            return True
    return False


def digest_record(data: dict[str, Any], digest_field: str) -> str:
    payload = dict(data)
    payload.pop(digest_field, None)
    return sha256_json(payload)


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_lock_metadata(lock_path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@contextlib.contextmanager
def controller_lock(control_root: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    lock_path = control_root / ".controller.lock"
    control_root.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            metadata = _read_lock_metadata(lock_path)
            if (
                metadata
                and metadata.get("host") == socket.gethostname()
                and isinstance(metadata.get("pid"), int)
                and not process_alive(metadata["pid"])
            ):
                try:
                    lock_path.unlink()
                    continue
                except FileNotFoundError:
                    continue
            if time.monotonic() >= deadline:
                raise ValueError(f"controller state is locked: {lock_path}")
            time.sleep(0.1)
    try:
        metadata = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "started_at": now_iso(),
            "controller_version": CONTROLLER_VERSION,
        }
        os.write(fd, (json.dumps(metadata, ensure_ascii=False) + "\n").encode("utf-8"))
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def git_show_bytes(root: Path, revision: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative_path}"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            f"git show failed for {revision}:{relative_path}: {result.stderr.decode('utf-8', errors='replace')}"
        )
    return result.stdout


def git_path_exists(root: Path, revision: str, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}:{relative_path}"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 128:
        return False
    raise ValueError(
        f"git cat-file failed for {revision}:{relative_path}: {result.stderr.decode('utf-8', errors='replace')}"
    )


def non_control_git_status(root: Path) -> list[str]:
    """Return porcelain status lines excluding reserved Mutable Controller Record paths.

    Identity-policy-v1 semantics: reserved mutable records (project-state, changes/**,
    transactions/**, backups/**, handoffs/**) are excluded; every other path, including
    non-record .ai-product files, is visible so reviewable deliverables are never silently
    treated as clean.
    """
    status = run_command(("git", "status", "--porcelain=v1", "--untracked-files=all"), cwd=root)
    if status.returncode != 0:
        raise ValueError(f"git status --porcelain failed:\n{status.stdout}")
    result: list[str] = []
    for line in status.stdout.splitlines():
        if not line:
            continue
        payload = line[3:] if len(line) >= 3 else ""
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        normalized = payload.strip().strip('"').replace("\\", "/")
        if is_mutable_controller_record(normalized):
            continue
        result.append(line)
    return result
