# Security Policy

## 支持范围

安全修复优先针对最新公开 Beta / Release。历史版本可能不会获得回补。

## 重要安全边界

PDC 的 repository/worktree 隔离用于保证**审查目标一致性**，不是恶意代码安全沙箱。

特别是冻结 Engineering contract 中的测试命令可能执行项目代码。只有在你信任项目和测试命令来源时才运行它们。不要把 PDC 当作容器、虚拟机、权限隔离器或恶意代码执行环境。

PDC 也不会替代宿主平台（Codex、GitHub、操作系统等）的权限、网络和数据安全策略。

## 报告漏洞

优先使用 GitHub 仓库 Security 页面中的 **Report a vulnerability / Private vulnerability reporting**。

如果该入口不可用，请不要把漏洞利用细节、凭证或敏感数据放进公开 Issue。可以只创建一个不含技术细节的 Issue，标题写明 `Security contact requested`，由维护者建立私下沟通渠道。

请尽量包含：

- 受影响版本；
- 风险影响；
- 最小复现；
- 是否需要特殊权限；
- 建议修复方向（如果有）。

## 不属于安全漏洞的情况

普通功能 Bug、文档问题和非敏感兼容性问题请使用普通 Issue。
