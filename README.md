# PDC 中文首次用户 Preview

> **这是首次用户可用性测试版，不是稳定发行版。**

PDC（Product Development Controller，产品开发控制器）不是另一个写代码的 Agent。它负责在长期 AI 产品开发里控制：现在该做什么、哪些证据才算够、什么时候才算真正完成、谁来验证、什么时候需要产品负责人验收，以及中断后如何继续。

这次 Preview 只测试一个问题：**第一次接触 PDC 的人，能不能在约 10 分钟内独立完成一次有意义的 PDC 流程。**

## 参加测试

你需要：

- Codex Desktop；
- Python 3.11 或更高版本；
- Git；
- 以前没有使用或研究过 PDC。

先把这个 Preview 分支下载到本地：

```bash
git clone --branch preview/first-user-v1-zh --single-branch https://github.com/xiaokonglong10086/PDC-skill.git pdc-preview
cd pdc-preview
```

然后**开始计时**，打开 [`START_HERE.md`](START_HERE.md)，严格按照里面的中文说明独立完成任务。

请不要提前阅读 `skills/` 目录里的 PDC 内部实现文档；这次测试要观察的是首次使用体验，而不是文档学习能力。

## 这次测试不会要求你

- 提供私有仓库；
- 使用真实公司或客户数据；
- 提供密码、Token 或其他凭证；
- 理解 Git 哈希、内部 Schema 或 PDC 的私有开发历史；
- 手工修改 `.ai-product` 内部状态。

## 测试边界

这是一个有限范围的公开 Preview：

- 当前只验证 Codex Desktop 的首次使用路径；
- 不代表多平台已经达到相同支持水平；
- 不代表正式稳定版已经发布；
- 不授予开源许可证；
- 不会自动从私有 PDC 同步更新。

测试隐私说明见 [`PREVIEW_PRIVACY.md`](PREVIEW_PRIVACY.md)，测试使用边界见 [`PREVIEW_TERMS.md`](PREVIEW_TERMS.md)。

如果你是公开招募的参与者，请从招募 Issue 进入，并在完成后按 [`FEEDBACK_TEMPLATE.md`](FEEDBACK_TEMPLATE.md) 提交结果。
