#!/usr/bin/env python3
"""安装、检查并创建 PDC 公开 Beta 的虚构示例。"""

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

PLUGIN_NAME = "pdc"
ENTRY = {
    "name": PLUGIN_NAME,
    "source": {"source": "local", "path": "./plugins/pdc"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Developer Tools",
}


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def home_path(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else Path.home().resolve()


def run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}
        or name.endswith(".pyc")
    }


def backup_path(path: Path, backup_root: Path) -> None:
    if not path.exists():
        return
    destination = backup_root / path.name
    if path.is_dir():
        shutil.copytree(path, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def load_marketplace(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": "personal",
            "interface": {"displayName": "个人插件"},
            "plugins": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("你的个人插件市场文件不是有效的 JSON 对象。")
    plugins = payload.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError("你的个人插件市场文件中的 plugins 列表无效。")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pdc-tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def install(args: argparse.Namespace) -> int:
    home = home_path(args.home)
    source = plugin_root()
    destination = home / "plugins" / PLUGIN_NAME
    marketplace = home / ".agents" / "plugins" / "marketplace.json"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = home / ".pdc-backups" / timestamp

    try:
        if not (source / ".codex-plugin" / "plugin.json").is_file():
            raise ValueError("当前文件夹不是完整的 PDC 发行包。")
        if not (source / "skills" / "product-development-controller" / "SKILL.md").is_file():
            raise ValueError("当前 PDC 发行包缺少 Skill 文件。")

        if destination.exists() and destination.resolve() != source.resolve():
            if not args.replace:
                raise ValueError(
                    "PDC 已经安装在 ~/plugins/pdc。"
                    "如果要更新，请重新运行安装命令并加上 --replace，旧文件会先备份。"
                )
            backup_root.mkdir(parents=True, exist_ok=True)
            backup_path(destination, backup_root)
            shutil.rmtree(destination)

        payload = load_marketplace(marketplace)
        existing_index = next(
            (
                index
                for index, item in enumerate(payload["plugins"])
                if isinstance(item, dict) and item.get("name") == PLUGIN_NAME
            ),
            None,
        )
        if existing_index is not None and not args.replace:
            existing = payload["plugins"][existing_index]
            if existing != ENTRY:
                raise ValueError(
                    "插件市场里已经存在另一条 PDC 配置。"
                    "如需替换，请重新运行安装命令并加上 --replace，旧文件会先备份。"
                )
        if marketplace.exists() and args.replace:
            backup_root.mkdir(parents=True, exist_ok=True)
            backup_path(marketplace, backup_root)

        if destination.resolve() != source.resolve():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination, ignore=copy_ignore)

        if existing_index is None:
            payload["plugins"].append(ENTRY)
        else:
            payload["plugins"][existing_index] = ENTRY
        write_json(marketplace, payload)

        print("PDC 已为 Codex Desktop 安装完成。")
        print("下一步：运行 `python scripts/pdc_first_run.py doctor`。")
        if backup_root.exists():
            print(f"旧文件已备份到：{backup_root}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PDC 安装失败：{exc}", file=sys.stderr)
        return 2


def doctor(args: argparse.Namespace) -> int:
    home = home_path(args.home)
    destination = home / "plugins" / PLUGIN_NAME
    marketplace = home / ".agents" / "plugins" / "marketplace.json"
    checks: list[tuple[str, bool, str]] = []

    checks.append(("Python", sys.version_info >= (3, 11), "需要 Python 3.11 或更高版本。"))
    git = shutil.which("git")
    checks.append(("Git", git is not None, "请安装 Git，并确认它已经加入 PATH。"))
    checks.append(
        (
            "PDC 插件",
            (destination / ".codex-plugin" / "plugin.json").is_file(),
            "请在 PDC 文件夹中运行 `python scripts/pdc_first_run.py install`。",
        )
    )
    checks.append(
        (
            "PDC Skill",
            (destination / "skills" / "product-development-controller" / "SKILL.md").is_file(),
            "已安装的 PDC 不完整。请加上 --replace 重新安装。",
        )
    )

    marketplace_ok = False
    marketplace_fix = "请运行安装命令，让 Codex Desktop 注册 PDC。"
    if marketplace.is_file():
        try:
            payload = json.loads(marketplace.read_text(encoding="utf-8"))
            marketplace_ok = any(
                isinstance(item, dict) and item == ENTRY for item in payload.get("plugins", [])
            )
        except (OSError, json.JSONDecodeError, AttributeError):
            marketplace_fix = "个人插件市场文件不是有效 JSON。请先恢复或修复它，再重新安装 PDC。"
    checks.append(("Codex 注册", marketplace_ok, marketplace_fix))

    failed = [(name, fix) for name, passed, fix in checks if not passed]
    if args.json:
        print(
            json.dumps(
                {
                    "ready": not failed,
                    "checks": [
                        {"name": name, "passed": passed, "fix": None if passed else fix}
                        for name, passed, fix in checks
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif not failed:
        print("PDC 已准备好开始示例。")
        print("下一步：运行 `python scripts/pdc_first_run.py demo`。")
    else:
        print("开始示例前还需要解决下面的问题：")
        for name, fix in failed:
            print(f"- {name}：{fix}")

    return 0 if not failed else 1


def ensure_git_identity(root: Path) -> None:
    for key, value in (
        ("user.name", "PDC Demo"),
        ("user.email", "pdc-demo@example.invalid"),
    ):
        result = run(["git", "config", "--get", key], cwd=root)
        if result.returncode != 0 or not result.stdout.strip():
            configured = run(["git", "config", key, value], cwd=root)
            if configured.returncode != 0:
                raise ValueError(configured.stdout.strip() or f"无法配置 {key}。")


def demo(args: argparse.Namespace) -> int:
    home = home_path(args.home)
    installed = home / "plugins" / PLUGIN_NAME
    destination = (
        Path(args.destination).expanduser().resolve()
        if args.destination
        else (Path.cwd() / "pdc-demo").resolve()
    )
    skill = installed / "skills" / "product-development-controller"
    init_script = skill / "scripts" / "init_project.py"

    try:
        if not init_script.is_file():
            raise ValueError("PDC 尚未安装。请先完成 install 和 doctor。")
        if destination.exists():
            if any(destination.iterdir()):
                raise ValueError(f"示例目标文件夹不是空的：{destination}")
        else:
            destination.mkdir(parents=True)

        brief = """# 客户反馈导航器 — 示例产品说明

## 目标

帮助一名客服负责人把少量虚构客户反馈整理成可信的每周视图，找出最重要的三个产品问题。

## 已知事实

- 输入是一组虚构反馈文本。
- 第一个有用结果应该让没有技术背景的客服负责人也能看懂。
- 示例不能使用任何真实客户数据。

## 尚未解决

- 只有摘要是否足够，还是每个结论都必须能回到支持它的原始反馈。
- 第一步应该继续研究、做一个更真实的 Preview，还是已经适合正式 Engineering。

## 产品负责人请求

使用 PDC 选择下一步最可信的行动。不要因为可以写代码就自动开始编码。
"""
        feedback = """# 虚构客户反馈样本

1. 我不知道每周报告是不是包含了所有客户对话。
2. 摘要读起来很快，但只有看到原始反馈我才敢相信结论。
3. 团队里不同的人会用不同标签描述同一个问题。
4. 我更想看到和上周相比发生了什么变化，而不是又一张静态列表。
5. 请不要把我们的客户数据上传到来源不明的服务。
"""
        (destination / "PRODUCT_BRIEF.md").write_text(brief, encoding="utf-8", newline="\n")
        (destination / "SYNTHETIC_FEEDBACK.md").write_text(feedback, encoding="utf-8", newline="\n")
        (destination / "README.md").write_text(
            "# PDC 虚构示例\n\n请在 Codex Desktop 中打开这个文件夹，然后发送 demo 命令打印出来的提示词。\n",
            encoding="utf-8",
            newline="\n",
        )

        initialized = run(["git", "init", "-b", "main"], cwd=destination)
        if initialized.returncode != 0:
            raise ValueError(initialized.stdout.strip() or "Git 无法初始化示例仓库。")
        ensure_git_identity(destination)
        staged = run(["git", "add", "README.md", "PRODUCT_BRIEF.md", "SYNTHETIC_FEEDBACK.md"], cwd=destination)
        if staged.returncode != 0:
            raise ValueError(staged.stdout.strip())
        committed = run(["git", "commit", "-m", "创建虚构客户反馈示例"], cwd=destination)
        if committed.returncode != 0:
            raise ValueError(committed.stdout.strip())

        controls = run(
            [
                sys.executable,
                "-B",
                str(init_script),
                "--root",
                str(destination),
                "--project-name",
                "客户反馈导航器示例",
                "--coding-agent",
                "codex",
                "--task-id",
                "DEMO-001",
                "--slug",
                "first-controlled-flow",
                "--title",
                "选择并展示第一个可信的产品行动",
            ],
            cwd=destination,
        )
        if controls.returncode != 0:
            raise ValueError(controls.stdout.strip() or "PDC 无法初始化示例控制状态。")
        staged = run(["git", "add", ".ai-product"], cwd=destination)
        if staged.returncode != 0:
            raise ValueError(staged.stdout.strip())
        committed = run(["git", "commit", "-m", "初始化 PDC 示例控制状态"], cwd=destination)
        if committed.returncode != 0:
            raise ValueError(committed.stdout.strip())

        print(f"示例项目已创建：{destination}")
        print("请在 Codex Desktop 中打开这个文件夹，选择 PDC，然后发送下面这段提示词：")
        print()
        print(
            "请对这个仓库使用 PDC。恢复已经存在的项目事实，把 "
            "DEMO-001-first-controlled-flow 设为当前唯一正在推进的工作焦点，"
            "并告诉我下一步最可信的行动。除非 PDC 判断已经适合 Engineering，"
            "否则不要开始写代码。"
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"示例创建失败：{exc}", file=sys.stderr)
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="安装本地 PDC 插件")
    install_parser.add_argument("--home", help="用于验证的替代用户目录")
    install_parser.add_argument("--replace", action="store_true", help="备份并替换已有安装")
    install_parser.set_defaults(handler=install)

    doctor_parser = subparsers.add_parser("doctor", help="检查 PDC 与 Codex 是否准备好")
    doctor_parser.add_argument("--home", help="用于验证的替代用户目录")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(handler=doctor)

    demo_parser = subparsers.add_parser("demo", help="创建完全虚构的 PDC 示例")
    demo_parser.add_argument("--home", help="用于验证的替代用户目录")
    demo_parser.add_argument("--destination", help="示例仓库目标位置")
    demo_parser.set_defaults(handler=demo)

    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
