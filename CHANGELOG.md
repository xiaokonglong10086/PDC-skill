# Changelog

本项目遵循语义化版本方向；Beta 阶段仍可能出现兼容性调整。

## [0.1.0-beta.3] - 2026-09-02

把 PDC 从“公开安装入口只有 Codex Desktop”扩展为一套有明确能力边界的多宿主安装方案。

### Added

- `scripts/pdc_install.py`：统一安装/检查 Codex、Claude Code、Cursor、GitHub Copilot；
- Claude Code、Cursor、GitHub Copilot 的 user / project Agent Skill 安装路径；
- ChatGPT Business / Enterprise / Healthcare / Edu 原生 Skills 上传说明；
- ChatGPT 托管工作区从 GitHub 导入 PDC skill-only plugin marketplace 的说明与 `.agents/plugins/marketplace.json`；
- 没有原生 Skills 的个人 ChatGPT 账户 Project 兼容适配，并明确其能力低于 fully-tooled repository-backed Engineering；
- `pdc-agent-skill-<version>.zip` portable Agent Skill Release 包及 SHA-256；
- 多宿主安装器、marketplace 结构和 portable package 的公开确定性验证。

### Changed

- `START_HERE.md` 和 README 不再把 Codex Desktop 写成唯一公开入口；
- 保留原 `pdc_first_run.py install / doctor / demo`，避免破坏既有 Codex 用户路径；
- 完整 Release ZIP 现在包含 ChatGPT marketplace、兼容适配与多宿主安装文档；
- 对“格式兼容”和“已经资格验证支持”进行明确区分。

### Known limits

- ChatGPT 原生 Skills 与 plugin marketplace 可用性由账户计划、工作区设置、角色和产品 rollout 决定；
- 个人 ChatGPT Project 兼容模式不是原生 Skill，也不提供 Software/PDC 同等级 repository-backed Engineering 保证；
- Claude Code / Cursor / Copilot 的 CI 验证覆盖安装落点和 PDC 包完整性，不冒充真实宿主交互行为验证；
- 其他 Agent Skills 兼容宿主没有自动获得 PDC 的资格验证声明。

## [0.1.0-beta.2] - 2026-09-02

恢复完整、面向 Product Owner 的 PDC 产品叙事，并加入“整体 Outcome 优先于局部完美”的非协商控制原则。

### Added

- 全局 Outcome 检查：当前位置、路线贡献、决策充分阈值、可接受缺陷和停止/换路条件；
- means-end inversion（手段替代目标）和实验标准无因升级检测；
- Preview 的决策充分实验规则，明确允许有边界的粗略、人工、近似实验；
- Writer Brain 实验室过度优化、测试体系替代产品目标、必要弯路和反复询问“做什么/到哪/为什么”四类针对性回归场景。

### Changed

- 恢复旧版 README 中更有吸引力的产品介绍、失控案例、Product Owner/PDC 分工、Coding Agent 区别、完整示例和适用人群；
- 保留并整合现有五分钟快速开始、公开 CI、安全边界、贡献指南、发行说明、Public/Private 边界和 MIT License；
- Strategic Workpath 不再把局部质量提升自动视为路线进展；
- Preview 在达到决策充分证据后应停止完善实验室，而不是追求论文级或生产级完美。

### Known limits

- 本次行为回归新增的是显式针对性 delta，不冒充冻结完整行为目录的全套外部独立 PASS；
- 真实首次用户、外部采用和社区成熟度证据仍在积累；
- 当前严格正式 Engineering Profile 主要是 repository-backed Software/PDC；
- Git/worktree 隔离不是恶意代码安全沙箱。

## [0.1.0-beta.1] - 2026-09-02

首个正式开源 Beta。

### Added

- MIT 开源许可证；
- Codex Desktop 本地安装、doctor 和虚构 demo 路径；
- Linux / Windows / macOS × Python 3.11 / 3.12 / 3.13 公共 CI；
- 11 项公开确定性自测；
- CodeQL 安全扫描；
- GitHub Actions Dependabot；
- Issue / PR 模板、贡献指南、安全政策、治理与支持说明；
- 标签驱动的 GitHub Release 自动化；
- 可下载 Release ZIP 与 SHA-256。

### Changed

- 将首次用户中文 Preview 的插件化结构提升为公开发行结构；
- 将公开仓库定位从 curated portfolio snapshot 调整为可安装、可贡献、可版本化发行的开源项目；
- 保留首次用户真实证据收集，但不再把招募三人作为公开发行的前置条件。

### Known limits

- 真实首次用户可用性证据仍在收集中；
- 当前严格正式 Engineering Profile 主要是 repository-backed Software/PDC；
- Git/worktree 隔离不是恶意代码安全沙箱。
