# Releasing

公开版本从 `main` 发行。

## Release gate

发行前必须确认：

1. 版本号已更新；
2. `CHANGELOG.md` 和 `RELEASE_NOTES.md` 已更新；
3. `main` 的 Public CI 与 CodeQL 没有阻塞；
4. Public / Private 边界审计通过；
5. 不存在已知的发布阻塞安全问题。

## 创建版本

创建形如下面的 tag：

```text
v0.1.0-beta.1
```

`release.yml` 会：

- 重新运行 Linux / Windows / macOS × Python 3.11 / 3.12 / 3.13 验证；
- 构建 Release ZIP；
- 生成 SHA-256；
- 创建 GitHub prerelease 并附加文件。

Beta / RC 标签保持 prerelease；稳定版本可在经过真实使用证据与明确稳定性决策后调整发行工作流。
