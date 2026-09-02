# PDC v0.1.0-beta.3

这个版本解决一个直接影响采用的问题：PDC 的公开仓库虽然把自己描述为围绕 ChatGPT、Codex、Claude Code、Cursor 等工具工作的控制层，但实际快速开始此前只提供 Codex Desktop 安装路径。

v0.1.0-beta.3 把**同一份 PDC Agent Skill**扩展到多个宿主的真实安装入口，同时严格区分“原生支持、有限兼容、格式可移植”和“已经资格验证”的含义。

## 主要变化

- 新增统一的 `pdc_install.py`，可安装/检查 Codex Desktop、Claude Code、Cursor、GitHub Copilot；
- Claude Code、Cursor、GitHub Copilot 支持用户级和项目级 Agent Skill 安装；
- ChatGPT Business / Enterprise / Healthcare / Edu 提供原生 Skills 上传路径；
- ChatGPT 托管工作区可以从 GitHub 导入 PDC skill-only plugin marketplace；
- 对没有原生 Skills 的个人 ChatGPT 账户提供明确标注的 Project 兼容模式，而不是伪装成原生安装；
- 每个 Release 新增独立 `pdc-agent-skill-<version>.zip` 与 SHA-256，便于 ChatGPT Skills 上传和 Agent Skills 兼容宿主安装；
- 公共 CI 新增 Claude Code / Cursor / Copilot user + project 安装与 doctor，以及 marketplace / portable package 契约检查；
- 原有 Codex `pdc_first_run.py install / doctor / demo` 全部保留。

## 为什么不是“一套脚本假装支持所有 AI”

宿主能力不同。PDC 因此只复用同一核心 Skill，不强行把所有平台说成同等级：

- 有原生 Agent Skills / plugin 能力的宿主，使用其原生入口；
- ChatGPT 个人账户没有原生 Skills 时，只提供 Project 兼容模式；
- 没有真实 repository/runtime 工具时，不声称获得 strict Software/PDC Engineering 的 Git、独立验证、集成与关闭保证；
- 对其他遵循 Agent Skills 格式的宿主，只提供 portable artifact，不自动宣称已资格验证。

## 当前不宣称

- 不宣称所有 ChatGPT 账户都能创建或上传原生 Skills；
- 不宣称普通 ChatGPT Project 与 fully-tooled repository-backed PDC host 等价；
- 不把静态 CI 安装落点验证冒充真实 Claude Code / Cursor / Copilot 交互行为验证；
- 不宣称所有 Agent Skills 兼容宿主都有相同支持等级；
- 不宣称已经完成真实首次用户、外部采用或社区成熟度验证。
