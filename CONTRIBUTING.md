# Contributing to PDC

感谢你改进 PDC。这个项目接受外部贡献，但不会为了增加功能数量而弱化 PDC 的控制边界。

## 适合贡献的内容

- 可复现 Bug 修复；
- 安装和跨平台兼容性；
- 文档与首次使用体验；
- 确定性测试和回归案例；
- 安全修复；
- 能清楚说明产品边界的新能力。

## 开始前

1. 搜索已有 Issue；
2. Bug 请提供最小可复现步骤；
3. 大范围行为变化先开 Feature request，说明目标用户、问题和可观察结果；
4. 安全问题不要公开披露，按 [`SECURITY.md`](SECURITY.md) 处理。

## 本地验证

需要 Python 3.11+。

```bash
python skills/product-development-controller/scripts/audit_skill_package.py
python scripts/public_preview_ci.py
```

公开 CI 会在 Linux / Windows / macOS 的 Python 3.11 / 3.12 / 3.13 上重新运行完整验证。

## Pull Request 要求

PR 应当：

- 只解决一个清楚的问题；
- 说明用户可见影响；
- 给出验证方法；
- 不包含私有 PDC 状态、真实项目数据、凭证或本地绝对路径；
- 不把实现者自己的测试结果当作唯一正确性证据；
- 不在无关改动中偷偷改变现有产品边界。

## 兼容性

对 `skills/product-development-controller/` 的行为改动应尽量保持：

- 持久状态可恢复；
- 唯一 advancing Work Focus；
- Explore / Preview / Engineering 路由；
- Engineering 完成边界冻结；
- Builder 不自我批准；
- 技术 PASS 与 Product Owner acceptance 分离；
- 精确交付版本与证据绑定。

如果贡献有意改变这些控制保证，PR 必须明确说明为什么。

## 许可

提交贡献即表示你有权提交该内容，并同意贡献按仓库的 MIT License 分发。
