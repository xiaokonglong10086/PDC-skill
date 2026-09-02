# Releasing

公开版本从 `main` 发行，版本号以根目录 `VERSION` 和 `.codex-plugin/plugin.json` 为准。

## Release gate

发行前必须确认：

1. `VERSION` 与插件版本一致并已更新；
2. `CHANGELOG.md` 和 `RELEASE_NOTES.md` 已更新；
3. 候选 PR 的 Public CI 与 CodeQL 没有阻塞；
4. Public / Private 边界审计通过；
5. 不存在已知的发布阻塞安全问题。

## 创建版本

把新的版本号和 Release notes 作为经过验证的 PR 合并到 `main`。`release.yml` 会读取 `VERSION`：

- 如果 `v<VERSION>` 已经存在，不重复发行；
- 如果该版本尚未发行，重新运行 Linux / Windows / macOS × Python 3.11 / 3.12 / 3.13 验证；
- 验证通过后构建 Release ZIP；
- 生成 SHA-256；
- 在精确的 `main` commit 上创建 `v<VERSION>` tag；
- 创建 GitHub prerelease 并附加文件。

例如 `VERSION` 为 `0.1.0-beta.1` 时，会创建 `v0.1.0-beta.1`。

Beta / RC 保持 prerelease。只有在真实使用证据和明确稳定性决策支持后，才进入稳定版本策略。
