#!/usr/bin/env python3
"""Stable public CI entrypoint for PDC releases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from public_preview_ci import main as run_deterministic_verification

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_PROJECT_FILES = (
    "LICENSE",
    "README.md",
    "START_HERE.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "GOVERNANCE.md",
    "ROADMAP.md",
    "RELEASING.md",
    "PRIVACY.md",
    "TERMS.md",
    "PUBLIC_RELEASE_SCOPE.md",
    "PUBLIC_VERIFICATION.md",
    "VERSION",
    ".agents/plugins/marketplace.json",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/release.yml",
    ".github/dependabot.yml",
    ".github/CODEOWNERS",
    "docs/INSTALLATION.md",
    "compat/chatgpt-project/PROJECT_INSTRUCTIONS.md",
    "scripts/pdc_install.py",
)
FORBIDDEN_RELEASE_MARKERS = (
    "UNLICENSED",
    "未授予任何开源许可证",
    "no open-source license is granted",
)
PORTABLE_HOSTS = ("claude-code", "cursor", "copilot")


def verify_open_source_release_contract() -> None:
    missing = [relative for relative in REQUIRED_PROJECT_FILES if not (ROOT / relative).is_file()]
    if missing:
        raise RuntimeError("缺少公开项目基线文件：" + ", ".join(missing))

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if plugin.get("version") != version:
        raise RuntimeError(
            f"版本不一致：VERSION={version!r}, plugin.json={plugin.get('version')!r}"
        )
    if plugin.get("license") != "MIT":
        raise RuntimeError("公开插件元数据必须声明 MIT License。")
    if not (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License\n"):
        raise RuntimeError("LICENSE 不是预期的 MIT License 文本。")

    marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        raise RuntimeError("公开 marketplace 必须只包含一个 PDC plugin 条目。")
    entry = entries[0]
    if not isinstance(entry, dict) or entry.get("name") != "pdc":
        raise RuntimeError("公开 marketplace 的 plugin 必须命名为 pdc。")
    if entry.get("source") != {"source": "local", "path": "."}:
        raise RuntimeError("公开 marketplace 必须从仓库根目录加载 PDC plugin。")
    policy = entry.get("policy")
    if not isinstance(policy, dict):
        raise RuntimeError("公开 marketplace 的 PDC policy 无效。")
    if "products" in policy:
        raise RuntimeError("skill-only PDC marketplace 不应限制为单一产品 surface。")
    if (ROOT / "mcp.json").exists() or (ROOT / ".mcp.json").exists():
        raise RuntimeError("当前 PDC 是 skill-only plugin，不应携带根级 MCP 配置。")

    conflicts: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json"}:
            continue
        relative = path.relative_to(ROOT)
        if any(part in {".git", "dist", "__pycache__"} for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(marker in text for marker in FORBIDDEN_RELEASE_MARKERS):
            conflicts.append(relative.as_posix())
    if conflicts:
        raise RuntimeError(
            "公开候选仍包含与 MIT 发行冲突的旧许可声明：" + ", ".join(conflicts)
        )


def run_json(args: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, object]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"命令失败（退出码 {result.returncode}）：{' '.join(args)}\n{result.stdout}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"命令没有输出有效 JSON：{' '.join(args)}\n{result.stdout}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"命令 JSON 不是对象：{' '.join(args)}")
    return payload


def run_plain(args: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"命令失败（退出码 {result.returncode}）：{' '.join(args)}\n{result.stdout}"
        )


def verify_portable_host_installers() -> None:
    installer = ROOT / "scripts" / "pdc_install.py"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"

    with tempfile.TemporaryDirectory(prefix="pdc-host-install-") as temp_name:
        temporary = Path(temp_name)
        home = temporary / "home"
        home.mkdir()

        for host in PORTABLE_HOSTS:
            run_plain(
                [
                    sys.executable,
                    "-B",
                    str(installer),
                    "install",
                    "--target",
                    host,
                    "--home",
                    str(home),
                ],
                cwd=ROOT,
                env=env,
            )
            payload = run_json(
                [
                    sys.executable,
                    "-B",
                    str(installer),
                    "doctor",
                    "--target",
                    host,
                    "--home",
                    str(home),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
            )
            if payload.get("ready") is not True:
                raise RuntimeError(f"{host} user-scope doctor 未通过：{payload}")

            project = temporary / f"project-{host}"
            project.mkdir()
            run_plain(
                [
                    sys.executable,
                    "-B",
                    str(installer),
                    "install",
                    "--target",
                    host,
                    "--scope",
                    "project",
                    "--project-root",
                    str(project),
                    "--home",
                    str(home),
                ],
                cwd=ROOT,
                env=env,
            )
            project_payload = run_json(
                [
                    sys.executable,
                    "-B",
                    str(installer),
                    "doctor",
                    "--target",
                    host,
                    "--scope",
                    "project",
                    "--project-root",
                    str(project),
                    "--home",
                    str(home),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
            )
            if project_payload.get("ready") is not True:
                raise RuntimeError(f"{host} project-scope doctor 未通过：{project_payload}")


def main() -> int:
    try:
        verify_open_source_release_contract()
        verify_portable_host_installers()
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"公开发行契约检查失败：{exc}", file=sys.stderr)
        return 1
    return int(run_deterministic_verification())


if __name__ == "__main__":
    raise SystemExit(main())
