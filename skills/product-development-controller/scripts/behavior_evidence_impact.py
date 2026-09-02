#!/usr/bin/env python3
"""Compare predeclared behavior-evidence inputs across two Git commits.

This tool proves only byte-level impact for frozen evidence-unit selectors. It does
not decide behavior verdicts, semantic causality, freshness, or assurance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


class ImpactError(Exception):
    pass


def git(root: Path, *args: str, text: bool = True) -> str | bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() if text else proc.stderr.decode("utf-8", "replace").strip()
        raise ImpactError(f"git {' '.join(args)} failed: {err}")
    return proc.stdout


def resolve_commit(root: Path, ref: str) -> str:
    value = str(git(root, "rev-parse", "--verify", f"{ref}^{{commit}}" )).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ImpactError(f"Git ref did not resolve to a full commit: {ref}")
    return value


def safe_repo_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ImpactError("input path must be a non-empty repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ImpactError(f"unsafe repository path: {value}")
    return path.as_posix()


def blob_at(root: Path, commit: str, path: str) -> bytes:
    spec = f"{commit}:{path}"
    proc = subprocess.run(
        ["git", "show", spec],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ImpactError(f"missing or unreadable file at {commit[:12]}: {path}")
    return proc.stdout


_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*(?:\r?\n)?$")


def markdown_section(blob: bytes, heading: str, path: str, commit: str) -> bytes:
    if not isinstance(heading, str) or not heading.strip():
        raise ImpactError("markdown_section heading must be a non-empty string")
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImpactError(f"Markdown selector requires UTF-8 text: {path}") from exc
    lines = text.splitlines(keepends=True)
    matches: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match and match.group(2).strip() == heading:
            matches.append((index, len(match.group(1))))
    if len(matches) != 1:
        state = "missing" if not matches else "duplicate"
        raise ImpactError(f"{state} Markdown heading {heading!r} at {commit[:12]}:{path}")
    start, level = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = _HEADING_RE.match(lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "".join(lines[start:end]).encode("utf-8")


def validate_selector(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ImpactError("selector must be an object")
    selector_type = value.get("type")
    if selector_type == "whole_file":
        if set(value) != {"type"}:
            raise ImpactError("whole_file selector supports only the type field")
        return {"type": "whole_file"}
    if selector_type == "markdown_section":
        if set(value) != {"type", "heading"}:
            raise ImpactError("markdown_section selector requires only type and heading")
        heading = value.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            raise ImpactError("markdown_section heading must be a non-empty string")
        return {"type": "markdown_section", "heading": heading}
    raise ImpactError(f"unsupported selector type: {selector_type!r}")


def validate_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"path", "selector"}:
        raise ImpactError("each evidence input must contain exactly path and selector")
    return {"path": safe_repo_path(value["path"]), "selector": validate_selector(value["selector"])}


def input_key(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def validate_input_list(value: Any, *, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ImpactError(f"{context} must be a list")
    items = [validate_input(item) for item in value]
    keys = [input_key(item) for item in items]
    if len(keys) != len(set(keys)):
        raise ImpactError(f"duplicate evidence input in {context}")
    return items


def load_map(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImpactError(f"malformed impact map: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "global_inputs", "scenarios"}:
        raise ImpactError("impact map must contain exactly schema_version, global_inputs, and scenarios")
    if data.get("schema_version") != 1:
        raise ImpactError("unsupported impact-map schema_version")
    global_inputs = validate_input_list(data.get("global_inputs"), context="global_inputs")
    scenarios_raw = data.get("scenarios")
    if not isinstance(scenarios_raw, dict) or not scenarios_raw:
        raise ImpactError("scenarios must be a non-empty object")
    scenarios: dict[str, list[dict[str, Any]]] = {}
    for scenario_id, raw_inputs in scenarios_raw.items():
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ImpactError("scenario IDs must be non-empty strings")
        local = validate_input_list(raw_inputs, context=f"scenario {scenario_id}")
        combined_keys = [input_key(item) for item in global_inputs + local]
        if len(combined_keys) != len(set(combined_keys)):
            raise ImpactError(f"duplicate global/local evidence input for scenario {scenario_id}")
        scenarios[scenario_id] = local
    return global_inputs, scenarios


def selected_bytes(root: Path, commit: str, item: dict[str, Any]) -> bytes:
    blob = blob_at(root, commit, item["path"])
    selector = item["selector"]
    if selector["type"] == "whole_file":
        return blob
    return markdown_section(blob, selector["heading"], item["path"], commit)


def fingerprint(root: Path, commit: str, item: dict[str, Any]) -> str:
    return hashlib.sha256(selected_bytes(root, commit, item)).hexdigest()


def compare(root: Path, base: str, head: str, map_path: Path) -> dict[str, Any]:
    root = root.resolve()
    if not (root / ".git").exists():
        # Worktrees may use a .git file, so also accept git rev-parse success below.
        try:
            git(root, "rev-parse", "--git-dir")
        except ImpactError as exc:
            raise ImpactError(f"not a Git worktree: {root}") from exc
    base_commit = resolve_commit(root, base)
    head_commit = resolve_commit(root, head)
    global_inputs, scenarios = load_map(map_path)

    cache: dict[tuple[str, str], str] = {}

    def fp(commit: str, item: dict[str, Any]) -> str:
        key = (commit, input_key(item))
        if key not in cache:
            cache[key] = fingerprint(root, commit, item)
        return cache[key]

    scenario_reports: dict[str, Any] = {}
    for scenario_id, local_inputs in scenarios.items():
        inputs = global_inputs + local_inputs
        compared: list[dict[str, Any]] = []
        changed_inputs: list[dict[str, Any]] = []
        for item in inputs:
            base_sha = fp(base_commit, item)
            head_sha = fp(head_commit, item)
            status = "unchanged" if base_sha == head_sha else "changed"
            record = {
                "path": item["path"],
                "selector": item["selector"],
                "base_sha256": base_sha,
                "head_sha256": head_sha,
                "status": status,
            }
            compared.append(record)
            if status == "changed":
                changed_inputs.append(record)
        scenario_reports[scenario_id] = {
            "status": "changed" if changed_inputs else "unchanged",
            "inputs": compared,
            "changed_inputs": changed_inputs,
        }

    return {
        "schema_version": 1,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "scenarios": scenario_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--map", required=True, dest="map_path")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        report = compare(Path(args.root), args.base, args.head, Path(args.map_path))
        rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except ImpactError as exc:
        print(f"BEHAVIOR EVIDENCE IMPACT BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
