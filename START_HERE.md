# 10 分钟体验 PDC

这次 Preview 要验证：第一次使用 PDC 的产品负责人，能不能在不理解 Git、日志、哈希或内部状态的前提下，获得一次真正有意义的受控产品开发体验。

## 你要完成的事情

1. 安装本地 PDC 插件；
2. 检查 Codex Desktop 是否已经准备好使用 PDC；
3. 创建一个完全使用虚构数据的示例项目；
4. 在 Codex Desktop 中让 PDC 恢复项目并选择下一步最可信的行动；
5. 用自己的话说明 PDC 和 Coding Agent 有什么区别。

## 环境要求

- Codex Desktop
- Python 3.11 或更高版本
- Git

测试不会使用任何真实客户或公司数据。

## 第 1 步：安装

在当前 Preview 文件夹中运行：

```bash
python scripts/pdc_first_run.py install
```

如果你以前装过这个 Preview，再运行：

```bash
python scripts/pdc_first_run.py install --replace
```

替换前会自动备份已有文件。

## 第 2 步：检查是否准备好

运行：

```bash
python scripts/pdc_first_run.py doctor
```

只有看到下面这句话时再继续：

```text
PDC 已准备好开始首次用户示例。
```

## 第 3 步：创建示例项目

在你希望创建示例项目的文件夹中运行：

```bash
python scripts/pdc_first_run.py demo
```

这个命令会创建一个名为 `pdc-first-user-demo` 的仓库，里面只有虚构的客户反馈，并打印一段给 Codex Desktop 使用的准确提示词。

## 第 4 步：使用 PDC

在 Codex Desktop 中打开刚刚生成的示例文件夹，选择 **PDC**，然后发送 `demo` 命令打印出来的提示词。

当 PDC 做到下面这些事情时，你就完成了这次有意义的流程：

- 自动恢复项目里已经存在的信息，而不是让你重新解释一遍；
- 把示例任务保持为唯一正在推进的工作焦点；
- 判断下一步应该属于 Explore、Preview 还是 Engineering；
- 给出一个能直接理解的下一步，而不要求你判断 Git、哈希、日志、Schema 或内部生命周期状态。

## 第 5 步：回答两个问题

不要重新打开说明文档，直接回答：

1. PDC 解决了什么 Coding Agent 单独无法解决的问题？
2. 在正式实现可以被称为“完成”之前，你认为 PDC 应该先做什么？

完成后，请按照 [`FEEDBACK_TEMPLATE.md`](FEEDBACK_TEMPLATE.md) 记录结果。

## Preview 边界

这是公开的首次用户可用性测试版，不是稳定发行版。它只验证上手和首次价值，不声称所有平台具有相同支持，也不声称除仓库型 Software/PDC 之外已经存在同等级的正式 Engineering Profile。
