#!/usr/bin/env python3
"""Install and verify the public PDC Skill across supported agent hosts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_NAME = "product-development-controller"
USER_TARGETS = {
    "claude-code": Path(".claude") / "skills" / SKILL_NAME,
    "cursor": Path(".cursor") / "skills" / SKILL_NAME,
    "copilot": Path(".copilot") / "skills" / SKILL_NAME,
}
PROJECT_TARGETS = {
    "claude-code": Path(".claude") / "skills" / SKILL_NAME,
    "cursor": Path(".cursor") / "skills" / SKILL_NAME,
    "copilot": Path(".github") / "skills" / SKILL_NAME,
}
NATIVE_TARGETS = ("codex", *USER_TARGETS.keys())


def release_root() -> Path:
    return Path(__file__).resolve().parent.parent


def skill_source() -> Path:
    return release_root() / "skills" / SKILL_NAME


def resolve_home(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else Path.home().resolve()


def validate_source() -> None:
    source = skill_source()
    skill_file = source / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError("当前发行包缺少 PDC Skill。")
    text = skill_file.read_text(encoding="utf-8")
    if f"name: {SKILL_NAME}" not in text:
        raise ValueError("PDC SKILL.md 的 name 与技能目录不一致。")
    if not (source / "references").is_dir() or not (source / "scripts").is_dir():
        raise ValueError("PDC Skill 缺少 references 或 scripts。")


def copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__", ".pytest_cache", ".venv", "venv", ".git"}
    return {name for name in names if name in ignored or name.endswith(".pyc")}


def backup_existing(destination: Path, home: Path, target: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = home / ".pdc-backups" / timestamp / target / SKILL_NAME
    backup.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_dir():
        shutil.copytree(destination, backup)
    else:
        shutil.copy2(destination, backup)
    return backup


def destination_for(
    target: str,
    scope: str,
    *,
    home: Path,
    project_root: str | None,
) -> Path:
    if target == "codex":
        if scope != "user":
            raise ValueError("Codex 当前公开安装路径只支持 user scope。")
        return home / "plugins" / "pdc"
    if scope == "user":
        return home / USER_TARGETS[target]
    if not project_root:
        raise ValueError("project scope 需要 --project-root。")
    return Path(project_root).expanduser().resolve() / PROJECT_TARGETS[target]


def run_codex(command: str, args: argparse.Namespace) -> int:
    if args.scope != "user":
        print("PDC 安装失败：Codex 当前公开安装路径只支持 user scope。", file=sys.stderr)
        return 2
    script = release_root() / "scripts" / "pdc_first_run.py"
    cmd = [sys.executable, "-B", str(script), command]
    if args.home:
        cmd += ["--home", str(args.home)]
    if command == "install" and args.replace:
        cmd.append("--replace")
    if command == "doctor" and args.json:
        cmd.append("--json")
    result = subprocess.run(cmd, cwd=str(release_root()), check=False)
    return int(result.returncode)


def install(args: argparse.Namespace) -> int:
    if args.target == "codex":
        return run_codex("install", args)

    home = resolve_home(args.home)
    try:
        validate_source()
        destination = destination_for(
            args.target,
            args.scope,
            home=home,
            project_root=args.project_root,
        )
        backup: Path | None = None
        if destination.exists():
            if not args.replace:
                raise ValueError(
                    f"PDC 已存在于 {destination}。如需更新，请加上 --replace。"
                )
            backup = backup_existing(destination, home, args.target)
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_source(), destination, ignore=copy_ignore)
        print(f"PDC 已安装到 {args.target}：{destination}")
        doctor_cmd = (
            "python scripts/pdc_install.py doctor "
            f"--target {args.target} --scope {args.scope}"
        )
        if args.scope == "project":
            project = Path(args.project_root).expanduser().resolve()
            doctor_cmd += f' --project-root "{project}"'
        print(f"下一步：运行 `{doctor_cmd}`。")
        if backup is not None:
            print(f"旧安装已备份到：{backup}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"PDC 安装失败：{exc}", file=sys.stderr)
        return 2


def audit_installed(destination: Path) -> tuple[bool, str | None]:
    audit = destination / "scripts" / "audit_skill_package.py"
    if not audit.is_file():
        return False, "安装包缺少 audit_skill_package.py。"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", str(audit)],
        cwd=str(destination),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stdout.strip() or "技能包审计失败。"
        return False, detail
    return True, None


def doctor(args: argparse.Namespace) -> int:
    if args.target == "codex":
        return run_codex("doctor", args)

    home = resolve_home(args.home)
    checks: list[dict[str, Any]] = []
    try:
        destination = destination_for(
            args.target,
            args.scope,
            home=home,
            project_root=args.project_root,
        )
    except ValueError as exc:
        print(f"PDC 检查失败：{exc}", file=sys.stderr)
        return 2

    checks.append(
        {
            "name": "Python",
            "passed": sys.version_info >= (3, 11),
            "fix": None if sys.version_info >= (3, 11) else "需要 Python 3.11 或更高版本。",
        }
    )
    skill_file = destination / "SKILL.md"
    skill_ok = skill_file.is_file()
    checks.append(
        {
            "name": "PDC Skill",
            "passed": skill_ok,
            "fix": None if skill_ok else f"请先安装 PDC 到 {destination}。",
        }
    )
    if skill_ok:
        try:
            text = skill_file.read_text(encoding="utf-8")
            metadata_ok = f"name: {SKILL_NAME}" in text
        except OSError:
            metadata_ok = False
        checks.append(
            {
                "name": "Skill metadata",
                "passed": metadata_ok,
                "fix": None if metadata_ok else "SKILL.md 元数据无效，请使用 --replace 重新安装。",
            }
        )
        audit_ok, audit_fix = audit_installed(destination)
        checks.append(
            {
                "name": "Package audit",
                "passed": audit_ok,
                "fix": audit_fix,
            }
        )

    failed = [item for item in checks if not item["passed"]]
    payload = {
        "ready": not failed,
        "target": args.target,
        "scope": args.scope,
        "destination": str(destination),
        "checks": checks,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not failed:
        print(f"PDC 已准备好在 {args.target} 中使用：{destination}")
    else:
        print(f"{args.target} 的 PDC 安装还需要处理：")
        for item in failed:
            print(f"- {item['name']}：{item['fix']}")
    return 0 if not failed else 1


def targets(_args: argparse.Namespace) -> int:
    print("PDC 原生本地安装目标：")
    print("- codex: Codex Desktop plugin（user scope）")
    print("- claude-code: Agent Skill（user / project scope）")
    print("- cursor: Agent Skill（user / project scope）")
    print("- copilot: GitHub Copilot Agent Skill（user / project scope）")
    print()
    print("ChatGPT：请按 docs/INSTALLATION.md 使用原生 Skills / GitHub marketplace；个人账户使用有限 Project 兼容路径。")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subs = root.add_subparsers(dest="command", required=True)

    for command, handler in (("install", install), ("doctor", doctor)):
        p = subs.add_parser(command)
        p.add_argument("--target", choices=NATIVE_TARGETS, required=True)
        p.add_argument("--scope", choices=("user", "project"), default="user")
        p.add_argument("--home", help="替代用户目录；主要用于验证或隔离安装")
        p.add_argument("--project-root", help="project scope 的项目根目录")
        if command == "install":
            p.add_argument("--replace", action="store_true", help="备份并替换已有安装")
        else:
            p.add_argument("--json", action="store_true")
        p.set_defaults(handler=handler)

    p = subs.add_parser("targets")
    p.set_defaults(handler=targets)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
