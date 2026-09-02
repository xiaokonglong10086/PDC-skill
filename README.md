# PDC — Product Development Controller

> **AI can build fast. PDC keeps the product in control.**

[![Public CI](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/codeql.yml/badge.svg)](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/codeql.yml)

PDC（Product Development Controller，产品开发控制器）是长期 AI 产品开发的**控制层**。它不替代 Codex、Claude Code、Cursor 等执行工具，而是负责控制：当前应该推进什么、什么证据才算够、正式开发的完成边界、独立验证、Product Owner 验收，以及跨会话恢复。

当前公开版本：**v0.1.0-beta.1**。这是可公开安装和使用的 Beta；公开技术验证已经自动化，但真实首次用户可用性验证仍在继续，因此不会把 Beta 描述成已经完成外部验证的稳定版。

## 5 分钟开始

需要：

- Git；
- Python 3.11+；
- Codex Desktop（当前公开安装路径）。

```bash
git clone https://github.com/xiaokonglong10086/PDC-skill.git
cd PDC-skill
python scripts/pdc_first_run.py install
python scripts/pdc_first_run.py doctor
python scripts/pdc_first_run.py demo
```

Windows 如果 `python` 不可用，可以把上面的 `python` 换成 `py`。

更完整的首次使用说明见 [`START_HERE.md`](START_HERE.md)。

## PDC 解决什么问题

长期 AI 开发最容易失控的不是“代码写不出来”，而是：

- 会话切换后重复讨论已经决定的问题；
- 新 Bug / 新点子把当前工作带偏；
- Preview 看起来能用，就被误当成生产就绪；
- 实现者自己测试、自己宣布完成；
- 技术 PASS 被误当成 Product Owner 已经验收；
- 恢复时要求 Product Owner 自己读 Git、日志和内部状态；
- 完成标准在实现过程中被悄悄改变。

PDC 用一个持续控制模型处理这些问题：

```text
Outcome
  ↓
一个正在推进的 Work Focus
  ↓
Explore / Preview / Engineering
  ↓
成本最低但可信的下一步
  ↓
证据或实现
  ↓
独立验证
  ↓
需要时由 Product Owner 验收可见行为
  ↓
交付、关闭、可恢复连续性
```

## 三种工作模式

| Mode | 什么时候使用 | 优化目标 |
| --- | --- | --- |
| **Explore** | 方向或关键假设仍不确定 | 用最低成本减少会改变决策的不确定性 |
| **Preview** | 需要真实使用证据 | 用最小完整体验回答一个明确的现实问题 |
| **Engineering** | 行为已经理解并批准 | 冻结完成边界，可靠构建、验证和交付 |

## 公开能力边界

PDC 的控制模型可用于软件、Skills、Agents、自动化/工作流、原型、内部工具和混合数字交付物。

当前完整实现的严格正式 Engineering Profile 是仓库型 **Software/PDC**。其他交付类型可以使用 Explore、Preview、控制、证据和委派模型，但本项目不会声称它们已经拥有同等级的正式 Engineering 保证。

另外，PDC 的 Git/worktree 隔离**不是安全沙箱**。不要用冻结测试命令执行不可信代码。安全边界见 [`SECURITY.md`](SECURITY.md)。

## 公开验证

每个 PR 和 `main` 更新都会运行公开 CI：

- Linux / Windows / macOS；
- Python 3.11 / 3.12 / 3.13；
- 公开包边界审计；
- 11 项确定性自测；
- 安装、doctor、虚构 demo；
- Python 编译检查；
- Release 包构建。

详细范围见 [`PUBLIC_VERIFICATION.md`](PUBLIC_VERIFICATION.md)。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| [`skills/product-development-controller/SKILL.md`](skills/product-development-controller/SKILL.md) | PDC Skill 主入口 |
| [`skills/product-development-controller/references/`](skills/product-development-controller/references/) | 架构、权威、模式、评审、验收与恢复规则 |
| [`skills/product-development-controller/scripts/`](skills/product-development-controller/scripts/) | 生命周期、证据、验证和恢复工具 |
| [`scripts/`](scripts/) | 公开安装、首次运行、CI 与发行工具 |
| [`examples/`](examples/) | 完全使用虚构数据的示例 |
| [`PUBLIC_VERIFICATION.md`](PUBLIC_VERIFICATION.md) | 可重复的公开验证范围 |
| [`PUBLIC_RELEASE_SCOPE.md`](PUBLIC_RELEASE_SCOPE.md) | Public / Private 边界 |

## 参与项目

欢迎 Bug、文档改进、兼容性修复、测试、可复现案例和经过边界说明的新能力。

开始前请阅读：

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- [`SECURITY.md`](SECURITY.md)
- [`GOVERNANCE.md`](GOVERNANCE.md)

公开 Issue 不要包含密码、Token、私有仓库地址、客户数据或其他敏感信息。

## 发布与版本

- `v0.1.0-beta.1`：首个正式开源 Beta；
- 标签发行必须先通过与 PR 相同的公开验证矩阵；
- GitHub Release 会附带可下载 ZIP 和 SHA-256；
- 变更记录见 [`CHANGELOG.md`](CHANGELOG.md)；
- 后续方向见 [`ROADMAP.md`](ROADMAP.md)。

## Public / Private Boundary

这个仓库是 PDC 的公开发行源，不包含私有项目状态、私有 Git 历史、真实项目运行记录、私有回归基础设施、个人数据或凭证。

公开仓库不会自动从私有 PDC 同步。每次公开更新都必须经过单独评审、公开 CI 和版本化发行。

## License

PDC-skill 使用 [MIT License](LICENSE) 开源。
