# PDC 快速开始

这是 PDC 公开 Beta 的最短可用路径。

## 1. 选择你使用的 AI 宿主

当前有明确安装或兼容路径的宿主：

- ChatGPT；
- Codex Desktop；
- Claude Code；
- Cursor；
- GitHub Copilot。

不同宿主的能力边界并不完全相同。完整支持矩阵与 ChatGPT 说明见 [`docs/INSTALLATION.md`](docs/INSTALLATION.md)。

## 2. 下载 PDC

本地 Agent 宿主需要 Git 和 Python 3.11+：

```bash
git clone https://github.com/xiaokonglong10086/PDC-skill.git
cd PDC-skill
python scripts/pdc_install.py targets
```

如果你下载的是 GitHub Release ZIP，解压后进入该目录即可。

ChatGPT 原生 Skills 用户也可以直接从 GitHub Release 下载 `pdc-agent-skill-<version>.zip` 上传，不需要运行本地安装脚本。

## 3. 安装

### Codex Desktop

```bash
python scripts/pdc_install.py install --target codex
python scripts/pdc_install.py doctor --target codex
```

### Claude Code

```bash
python scripts/pdc_install.py install --target claude-code
python scripts/pdc_install.py doctor --target claude-code
```

### Cursor

```bash
python scripts/pdc_install.py install --target cursor
python scripts/pdc_install.py doctor --target cursor
```

### GitHub Copilot

```bash
python scripts/pdc_install.py install --target copilot
python scripts/pdc_install.py doctor --target copilot
```

这些 Agent Skills 安装默认是用户级；如果只想给单个项目安装，可以使用 `--scope project --project-root <项目目录>`。

### ChatGPT

ChatGPT 有三种不同路径，必须按账户/工作区能力选择：

1. **原生 Skills 上传**：适用于当前提供 Skills 的 Business / Enterprise / Healthcare / Edu 工作区；
2. **GitHub plugin marketplace**：适用于允许管理员从 GitHub 导入 plugin marketplace 的托管工作区；
3. **Project 兼容模式**：适用于没有原生 Skills 的个人 ChatGPT 账户，能力低于原生 Skill / fully-tooled repository host。

具体步骤见 [`docs/INSTALLATION.md`](docs/INSTALLATION.md#chatgpt)。

## 4. 更新

拉取新的公开版本后，对本地 Agent 宿主重新安装并加 `--replace`：

```bash
git pull
python scripts/pdc_install.py install --target <target> --replace
python scripts/pdc_install.py doctor --target <target>
```

Codex 原有安装入口继续兼容：

```bash
python scripts/pdc_first_run.py install --replace
python scripts/pdc_first_run.py doctor
```

## 5. Codex 虚构示例

当前自动创建完整虚构 Git 示例仓库的 `demo` 命令仍是 Codex Desktop 路径：

```bash
python scripts/pdc_first_run.py demo
```

它会创建独立 Git 示例仓库和 PDC 控制状态，不需要你的真实项目数据。

这不表示 PDC 只能在 Codex 使用；只是该自动化 demo 当前仍依赖 Codex 的 repository-backed Software/PDC 路径。

## 遇到问题

先查看 [`SUPPORT.md`](SUPPORT.md)。可复现 Bug 可以使用 GitHub Bug 模板提交。

**不要在公开 Issue 中粘贴密码、Token、私有仓库、客户数据或其他敏感信息。**
