# Public Verification

公开验证用于证明**当前公开候选本身**满足已声明的技术边界。它不是私有开发仓库完整历史回归套件，也不是第三方采用证据。

## CI matrix

每个 Pull Request 和 `main` 更新运行：

- ubuntu-latest × Python 3.11 / 3.12 / 3.13
- windows-latest × Python 3.11 / 3.12 / 3.13
- macos-latest × Python 3.11 / 3.12 / 3.13

Tag Release 会再次运行相同矩阵。

## 验证内容

公开验证流程覆盖：

1. Skill package boundary audit；
2. 11 项 retained standalone self-tests；
3. Python 编译检查；
4. Codex Desktop 本地安装到隔离测试 home；
5. Codex `doctor --json`；
6. 完全虚构 Codex demo 创建；
7. `.ai-product/project-state.json` 生成；
8. Claude Code user / project Agent Skill 安装与 doctor；
9. Cursor user / project Agent Skill 安装与 doctor；
10. GitHub Copilot user / project Agent Skill 安装与 doctor；
11. ChatGPT / Codex 共用 plugin marketplace 的结构、skill-only 边界与根目录 source 校验；
12. 完整 PDC Release ZIP 构建；
13. portable `product-development-controller` Agent Skill ZIP 构建及 SHA-256。

ChatGPT 原生 Skills 上传、工作区 GitHub marketplace 导入和个人 Project 兼容模式依赖真实 ChatGPT 账户/工作区能力，因此 CI 只验证可发布的 Skill/plugin 载体与静态契约，不伪造线上安装成功证据。

## 11 项 retained self-tests

- `architecture_v2_control_plane_self_test.py`
- `assurance_routing_self_test.py`
- `authority_projection_coherence_self_test.py`
- `integration_closure_recovery_self_test.py`
- `integration_runner_self_test.py`
- `multi_change_self_test.py`
- `owner_action_activation_self_test.py`
- `reconcile_project_state_self_test.py`
- `verify_authority_reconciliation_self_test.py`
- `workpath_continuity_self_test.py`
- `workpath_publish_recovery_self_test.py`

## 本地运行

```bash
python skills/product-development-controller/scripts/audit_skill_package.py
python scripts/public_ci.py
python scripts/build_release.py --output-dir dist
```

`public_preview_ci.py` 作为早期 Preview 的兼容入口暂时保留；新的公开接口是 `public_ci.py`。

## 证据边界

- CI PASS 证明公开候选在声明矩阵上通过当前确定性验证；
- CI PASS 证明 Claude Code / Cursor / Copilot 的声明文件落点能够被当前安装器正确生成并通过 PDC 包审计，但不替代真实宿主运行证据；
- CI PASS 不证明 ChatGPT 工作区一定向某个账户开放 Skills 或 plugin import；
- CI PASS 不证明首次用户一定能理解或顺利使用；
- CI PASS 不证明恶意代码可以安全执行；
- CI PASS 不等于 Product Owner 对某个具体产品项目的验收；
- 私有回归套件和真实项目运行证据不会因为公开仓库存在而自动公开。
