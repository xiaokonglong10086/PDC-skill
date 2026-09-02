#!/usr/bin/env python3
"""Stable public CI entrypoint for PDC releases."""

from __future__ import annotations

import json
import sys
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
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/release.yml",
    ".github/dependabot.yml",
    ".github/CODEOWNERS",
)
FORBIDDEN_RELEASE_MARKERS = (
    "UNLICENSED",
    "未授予任何开源许可证",
    "no open-source license is granted",
)


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


def main() -> int:
    try:
        verify_open_source_release_contract()
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"公开发行契约检查失败：{exc}", file=sys.stderr)
        return 1
    return int(run_deterministic_verification())


if __name__ == "__main__":
    raise SystemExit(main())
