#!/usr/bin/env python3
"""Detect local controller capabilities without overwriting repository files."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import atomic_write_json, controller_lock, load_json_object, safe_child


def can_write(path: Path) -> bool:
    created: Path | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=".pdc-write-probe-", dir=str(path))
        created = Path(name)
        os.write(fd, b"probe")
        os.close(fd)
        return True
    except OSError:
        return False
    finally:
        if created is not None:
            try:
                created.unlink()
            except FileNotFoundError:
                pass


def is_git_repo(root: Path) -> bool:
    if shutil.which("git") is None:
        return False
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def tri_state(value: str) -> bool | None:
    return None if value == "unknown" else value == "true"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--update", action="store_true", help="Write detected values to project-state.json")
    parser.add_argument("--browser-access", choices=("true", "false", "unknown"), default="unknown")
    parser.add_argument("--github-connector", choices=("true", "false", "unknown"), default="unknown")
    parser.add_argument(
        "--project-test-execution",
        choices=("true", "false", "unknown"),
        default="unknown",
        help="Set only after the project test command has actually been probed or run",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: repository root does not exist: {root}", file=sys.stderr)
        return 2
    capabilities = {
        "repository_access": True,
        "shell_access": True,
        "git_access": is_git_repo(root),
        "write_access": can_write(root),
        "python_execution": shutil.which("python") is not None or shutil.which("python3") is not None,
        "project_test_execution": tri_state(args.project_test_execution),
        "browser_access": tri_state(args.browser_access),
        "github_connector": tri_state(args.github_connector),
    }
    if args.update:
        control_root = safe_child(root, ".ai-product")
        with controller_lock(control_root):
            state_path = safe_child(control_root, "project-state.json")
            state = load_json_object(state_path)
            state["capabilities"] = capabilities
            atomic_write_json(state_path, state)
    print(json.dumps(capabilities, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
