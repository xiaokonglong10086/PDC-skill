#!/usr/bin/env python3
"""运行 PDC 公开发行候选的完整确定性验证。"""

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

FIXTURE_OLD = '"repository_root": str(root),'
FIXTURE_NEW = '"repository_root": contract["repository_root"],'


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


def prepare_verification_copy(source_skill: Path, temporary_root: Path) -> Path:
    """在临时副本中归一化一个 Windows 敏感的合成测试夹具，不修改发布的成熟 Skill。"""
    verification_skill = temporary_root / "skill"
    shutil.copytree(source_skill, verification_skill)
    fixture_path = verification_skill / "scripts" / "multi_change_self_test.py"
    text = fixture_path.read_text(encoding="utf-8")
    count = text.count(FIXTURE_OLD)
    if count != 1:
        raise RuntimeError(
            "Windows 路径验证夹具的预期形状已经变化；为避免误改，验证已停止。"
        )
    fixture_path.write_text(
        text.replace(FIXTURE_OLD, FIXTURE_NEW, 1),
        encoding="utf-8",
        newline="\n",
    )
    return verification_skill


def main() -> int:
    candidate = Path(__file__).resolve().parent.parent
    source_skill = candidate / "skills" / "product-development-controller"
    first_run = candidate / "scripts" / "pdc_first_run.py"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        # 先确认公开候选携带的成熟 Skill 包本身仍满足包边界。
        run([sys.executable, "-B", "scripts/audit_skill_package.py"], source_skill, env)

        with tempfile.TemporaryDirectory(prefix="pdc-public-verify-") as verify_name:
            verification_skill = prepare_verification_copy(source_skill, Path(verify_name))
            print("已在临时验证副本中归一化 Windows 合成仓库路径夹具；成熟 PDC 包未被修改。")
            run([sys.executable, "-B", "scripts/audit_skill_package.py"], verification_skill, env)
            for name in SELF_TESTS:
                run([sys.executable, "-B", f"scripts/{name}"], verification_skill, env)
            run([sys.executable, "-m", "compileall", "-q", "scripts"], verification_skill, env)
            clear_bytecode(verification_skill)
            if any(verification_skill.rglob("*.pyc")) or any(verification_skill.rglob("__pycache__")):
                raise RuntimeError("临时验证副本清理后仍残留 Python 字节码缓存。")
            run([sys.executable, "-B", "scripts/audit_skill_package.py"], verification_skill, env)

        with tempfile.TemporaryDirectory(prefix="pdc-public-ci-") as temp_name:
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
                raise RuntimeError("虚构示例没有创建 PDC 项目状态。")

        clear_bytecode(candidate)
        if any(candidate.rglob("*.pyc")) or any(candidate.rglob("__pycache__")):
            raise RuntimeError("公开候选清理后仍残留 Python 字节码缓存。")
        run([sys.executable, "-B", "scripts/audit_skill_package.py"], source_skill, env)
        print("PDC 公开发行候选验证通过。")
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
