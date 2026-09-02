# Support

## 使用问题

优先顺序：

1. [`START_HERE.md`](START_HERE.md)
2. [`docs/INSTALLATION.md`](docs/INSTALLATION.md)
3. [`README.md`](README.md)
4. [`PUBLIC_VERIFICATION.md`](PUBLIC_VERIFICATION.md)
5. GitHub Issues

本地 Agent 宿主提交 Bug 前请先运行对应检查：

```bash
python scripts/pdc_install.py doctor --target <codex|claude-code|cursor|copilot> --json
```

原 Codex 检查命令继续有效：

```bash
python scripts/pdc_first_run.py doctor --json
```

可以提供操作系统、Python 版本、Git 版本、PDC 版本、宿主名称和去敏后的错误信息。

ChatGPT 问题请同时说明：账户/工作区类型、使用的是原生 Skills、GitHub plugin marketplace 还是 Project 兼容模式。不要假定不同 ChatGPT 计划和工作区具有相同功能。

## 不要公开提交

- 密码、Token、API Key；
- 私有仓库内容或地址；
- 客户、公司或个人敏感数据；
- 内部日志中不必要的秘密；
- 漏洞利用细节（见 [`SECURITY.md`](SECURITY.md)）。

## 支持边界

这是开源项目，不承诺响应时间或 SLA。最新公开版本优先获得维护。

当前公开支持矩阵见 [`docs/INSTALLATION.md`](docs/INSTALLATION.md)。原生 Skill/plugin、portable Agent Skill 和 ChatGPT Project 兼容模式具有不同能力边界；只有进入明确支持矩阵与验证范围的路径，才属于当前声明支持范围。
