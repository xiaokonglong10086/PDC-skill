#!/usr/bin/env python3
"""运行 PDC 首次用户 Preview 的完整确定性验证。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SELF_TESTS = [
    "architecture_v2_control_plane_self_test.py",
    "assurance_routing_self_test.py",
    "authority_projection_coherence_self_test.py",
    "integration_closure_recovery_self_test.py",
    "integration_runner_self_test.py",
    "multi_change_self_test.py",
    "owner_action_activation_self_test.py",
    "reconcile_project_state_self_test.py",
    "verify_authority_reconciliation_self_test.py",
    "workpath_continuity_self_test.py",
    "workpath_publish_recovery_self_test.py",
]


def run(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(args, cwd=str(cwd), env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"命令失败（退出码 {result.returncode}）：{' '.join(args)}")


def clear_bytecode(root: Path) -> None:
    for cache in sorted(root.rglob("__pycache__"), reverse=True):
        if cache.is_dir():
            shutil.rmtree(cache)
    for pyc in root.rglob("*.pyc"):
        if pyc.is_file():
            pyc.unlink()


def main() -> int:
    candidate = Path(__file__).resolve().parent.parent
    skill = candidate / "skills" / "product-development-controller"
    first_run = candidate / "scripts" / "pdc_first_run.py"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        run([sys.executable, "-B", "scripts/audit_skill_package.py"], skill, env)
        for name in SELF_TESTS:
            run([sys.executable, "-B", f"scripts/{name}"], skill, env)

        with tempfile.TemporaryDirectory(prefix="pdc-preview-ci-") as temp_name:
            temporary = Path(temp_name)
            home = temporary / "home"
            demo = temporary / "demo"
            home.mkdir()
            run([sys.executable, "-B", str(first_run), "install", "--home", str(home)], candidate, env)
            run([sys.executable, "-B", str(first_run), "doctor", "--home", str(home), "--json"], candidate, env)
            run(
                [
                    sys.executable,
                    "-B",
                    str(first_run),
                    "demo",
                    "--home",
                    str(home),
                    "--destination",
                    str(demo),
                ],
                candidate,
                env,
            )
            if not (demo / ".ai-product" / "project-state.json").is_file():
                raise RuntimeError("首次用户示例没有创建 PDC 项目状态。")

        run([sys.executable, "-m", "compileall", "-q", "scripts"], skill, env)
        clear_bytecode(candidate)
        if any(candidate.rglob("*.pyc")) or any(candidate.rglob("__pycache__")):
            raise RuntimeError("清理后仍残留 Python 字节码缓存。")
        run([sys.executable, "-B", "scripts/audit_skill_package.py"], skill, env)
        print("PDC 首次用户 Preview 验证通过。")
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
