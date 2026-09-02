# Support

## 使用问题

优先顺序：

1. [`START_HERE.md`](START_HERE.md)
2. [`README.md`](README.md)
3. [`PUBLIC_VERIFICATION.md`](PUBLIC_VERIFICATION.md)
4. GitHub Issues

提交 Bug 前请先运行：

```bash
python scripts/pdc_first_run.py doctor --json
```

可以提供操作系统、Python 版本、Git 版本、PDC 版本和去敏后的错误信息。

## 不要公开提交

- 密码、Token、API Key；
- 私有仓库内容或地址；
- 客户、公司或个人敏感数据；
- 内部日志中不必要的秘密；
- 漏洞利用细节（见 [`SECURITY.md`](SECURITY.md)）。

## 支持边界

这是开源项目，不承诺响应时间或 SLA。最新公开版本优先获得维护。

当前公开安装路径以 Codex Desktop 为主；其他 Agent/宿主可以使用 PDC 的 Skill 内容，但不应自动理解为已经得到相同安装和运行保证。
