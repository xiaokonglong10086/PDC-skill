#!/usr/bin/env python3
"""Initialize safe .ai-product controls and optionally scaffold an unfinished change."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from common import atomic_write_json, atomic_write_text, controller_lock, load_json_object, now_iso, safe_child, validate_change_name, validate_task_id
from multi_change import derive_active_changes, project_focus_projection, unfocused_projection

REPLACE_CONFIRMATION = "REPLACE_AI_PRODUCT_TEMPLATES"
PROJECT_TEMPLATES = (
    "project-state.json", "project-facts.md", "codebase-facts.md", "roadmap.md", "backlog.md"
)
CHANGE_TEMPLATES = (
    "workflow-state.json", "task-contract.draft.json", "product-spec.md", "engineering-plan.md",
    "test-plan.md", "coding-agent-prompt.md", "implementation-report.md", "review-report.json",
    "acceptance-record.json", "integration-record.json",
)


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    if not slug:
        raise ValueError("slug must contain at least one letter or number")
    return validate_change_name(slug)


def replace_tokens(value: Any, tokens: dict[str, str]) -> Any:
    if isinstance(value, str):
        result = value
        for key, replacement in tokens.items():
            result = result.replace("{{" + key + "}}", replacement)
        return result
    if isinstance(value, list):
        return [replace_tokens(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: replace_tokens(item, tokens) for key, item in value.items()}
    return value


def backup_file(path: Path, backup_root: Path, relative: Path) -> None:
    if not path.exists():
        return
    destination = backup_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def copy_template(source: Path, destination: Path, tokens: dict[str, str], *, replace_existing: bool, backup_root: Path | None, backup_relative: Path) -> None:
    if not source.is_file():
        raise ValueError(f"required template is missing: {source}")
    if destination.exists() and not replace_existing:
        return
    if destination.exists() and backup_root is not None:
        backup_file(destination, backup_root, backup_relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix == ".json":
        data = json.loads(source.read_text(encoding="utf-8"))
        atomic_write_json(destination, replace_tokens(data, tokens))
    else:
        atomic_write_text(destination, replace_tokens(source.read_text(encoding="utf-8"), tokens))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--project-name", help="Project display name; defaults to directory name")
    parser.add_argument("--coding-agent", default="other", choices=("claude-code", "codex", "cursor", "other"))
    parser.add_argument("--task-id")
    parser.add_argument("--slug")
    parser.add_argument("--title")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--confirm-replace", help=f"Required value: {REPLACE_CONFIRMATION}")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: repository root does not exist: {root}", file=sys.stderr)
        return 2
    if args.replace_existing and args.confirm_replace != REPLACE_CONFIRMATION:
        print(f"ERROR: --replace-existing requires --confirm-replace {REPLACE_CONFIRMATION}", file=sys.stderr)
        return 2
    try:
        task_id = validate_task_id(args.task_id) if args.task_id else None
        slug = safe_slug(args.slug) if args.slug else None
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if any((task_id, slug, args.title)) and not all((task_id, slug, args.title)):
        print("ERROR: --task-id, --slug, and --title must be provided together", file=sys.stderr)
        return 2

    skill_root = Path(__file__).resolve().parent.parent
    skeleton = skill_root / "assets" / "project-skeleton"
    change_templates = skill_root / "assets" / "change-templates"
    control_root = safe_child(root, ".ai-product")
    project_name = args.project_name if args.project_name is not None else root.name
    project_tokens = {"PROJECT_NAME": project_name, "REPOSITORY_ROOT": str(root)}
    backup_root = control_root / "backups" / now_iso().replace(":", "-") if args.replace_existing else None

    try:
        control_root.mkdir(parents=True, exist_ok=True)
        with controller_lock(control_root):
            state_path = safe_child(control_root, "project-state.json")
            # Project navigation is authority and must never be reset by template replacement.
            for name in PROJECT_TEMPLATES:
                source = skeleton / name
                destination = safe_child(control_root, name)
                replace = args.replace_existing and name != "project-state.json"
                copy_template(
                    source, destination, project_tokens,
                    replace_existing=replace, backup_root=backup_root,
                    backup_relative=Path("project") / name,
                )
            for directory in ("decisions", "architecture", "changes", "backups", "transactions"):
                safe_child(control_root, directory).mkdir(parents=True, exist_ok=True)

            state = load_json_object(state_path)
            state["project_name"] = project_name
            state["repository_root"] = str(root)
            state["coding_agent"] = args.coding_agent
            state.pop("single_active_change_only", None)

            active_before = derive_active_changes(control_root)
            focus_before = state.get("current_change")
            if focus_before is not None and focus_before not in active_before:
                raise ValueError("project Focused Change is not unfinished workflow authority; reconcile first")

            change_path = None
            if task_id and slug and args.title:
                change_name = validate_change_name(f"{task_id}-{slug}")
                change_path = safe_child(control_root, "changes", change_name)
                existing_unfinished = change_name in active_before
                if change_path.exists() and any(change_path.iterdir()):
                    if not args.replace_existing:
                        raise ValueError(f"change already exists: {change_name}")
                    if existing_unfinished and focus_before != change_name:
                        raise ValueError(
                            f"--replace-existing cannot overwrite non-focused unfinished change {change_name}"
                        )
                change_path.mkdir(parents=True, exist_ok=True)
                tokens = {**project_tokens, "TASK_ID": task_id, "SLUG": slug, "TITLE": args.title}
                for name in CHANGE_TEMPLATES:
                    source = change_templates / name
                    copy_template(
                        source, safe_child(change_path, name), tokens,
                        replace_existing=args.replace_existing, backup_root=backup_root,
                        backup_relative=Path("changes") / change_name / name,
                    )
                safe_child(change_path, "contracts").mkdir(parents=True, exist_ok=True)
                safe_child(change_path, "evidence").mkdir(parents=True, exist_ok=True)

                active_after = derive_active_changes(control_root)
                if focus_before == change_name:
                    state = project_focus_projection(state, change_name, active_after[change_name])
                elif focus_before is not None:
                    # Additional draft persists without stealing or mutating the focused projection.
                    state = project_focus_projection(state, focus_before, active_after[focus_before])
                else:
                    # New parked drafts have no stable owner transition and never silently
                    # manufacture initial Focus authority. Explicit selection is separate.
                    state = unfocused_projection(state, active_after)
            atomic_write_json(state_path, state)
        print(f"Initialized project controls: {control_root}")
        if task_id and slug and args.title:
            print(f"Scaffolded change: {change_path}")
        if backup_root is not None:
            print(f"Backed up replaced templates under: {backup_root}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
