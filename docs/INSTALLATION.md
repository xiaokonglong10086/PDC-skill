# PDC 安装与宿主支持

PDC 的核心是同一份 `product-development-controller` Agent Skill。不同宿主只改变**安装入口和可用工具**，不复制一套新的 PDC 规则。

## 支持矩阵

| 宿主 | 当前支持级别 | 推荐安装方式 | 重要边界 |
| --- | --- | --- | --- |
| ChatGPT Business / Enterprise / Healthcare / Edu | 原生 Skill / skill-only plugin | Skills 上传，或由工作区管理员从 GitHub 导入 PDC marketplace | 受工作区权限与产品可用性控制 |
| ChatGPT Free / Go / Plus / Pro | **有限 Project 兼容** | ChatGPT Project + PDC Project instructions + PDC 文件 | 不是原生 Skill；不能宣称与 repository-backed Engineering 等价 |
| Codex Desktop | 原生 plugin | `pdc_install.py --target codex` | 保留原 `pdc_first_run.py` 安装方式 |
| Claude Code | 原生 Agent Skill | `pdc_install.py --target claude-code` | 可装 user 或 project scope |
| Cursor | 原生 Agent Skill | `pdc_install.py --target cursor` | 可装 user 或 project scope |
| GitHub Copilot | 原生 Agent Skill | `pdc_install.py --target copilot` | 可装 user 或 project scope |
| 其他 Agent Skills 兼容宿主 | 未单独资格验证 | 使用 Release 中的 portable Agent Skill 包并按宿主文档安装 | 不把“符合开放格式”自动升级成“已验证支持” |

查看本地可安装目标：

```bash
python scripts/pdc_install.py targets
```

---

## ChatGPT

### 方式 A：原生 Skills 上传

适用于当前提供 Skills 的 ChatGPT Business、Enterprise、Healthcare、Edu 工作区，并且工作区设置允许创建/上传 Skills。

1. 从 GitHub Release 下载 `pdc-agent-skill-<version>.zip`。
2. 在 ChatGPT 侧边栏打开 **Plugins**。
3. 进入 **Skills**。
4. 选择 **Create** → **Upload from your computer**。
5. 选择 PDC portable Agent Skill 包并完成 ChatGPT 的安全扫描/审核流程。
6. 安装后可让 ChatGPT 自动选择 PDC，或在界面支持时显式选择/提及该 Skill。

OpenAI 当前官方说明：<https://help.openai.com/en/articles/20001066-skills-in-chatgpt>

> ChatGPT 的 Skills 可用性取决于计划、工作区设置、角色与产品 rollout。PDC 仓库不会把“文件格式可上传”写成“任何 ChatGPT 账户都能原生安装”。

### 方式 B：工作区管理员从 GitHub 导入 PDC plugin marketplace

PDC 是 skill-only plugin，不需要外部 app 连接。仓库根目录提供 `.agents/plugins/marketplace.json`。

管理员：

1. 打开 **Workspace settings** → **Plugins**。
2. 选择 **Add** → **Import marketplace**。
3. Source 填入：`https://github.com/xiaokonglong10086/PDC-skill`
4. Path 留空，因为 marketplace 位于仓库根目录约定位置。
5. Branch 可留空跟随默认 `main`，或固定到某个 release tag。
6. 导入后检查 PDC plugin，并按工作区策略设置为 Available 或 Installed。

OpenAI 官方说明：<https://help.openai.com/en/articles/20001504>

这种方式的优势是：GitHub 可以成为工作区 PDC plugin 的可同步来源，不需要每次手工重新上传。

### 方式 C：个人 ChatGPT 账户的 Project 兼容模式

OpenAI 当前没有向 Free / Go / Plus / Pro 个人账户普遍提供原生 Skills 创建/上传能力。因此这里明确叫**兼容模式**，不是“安装 PDC Skill”。

1. 新建一个 ChatGPT Project。
2. 打开 Project settings，把 `compat/chatgpt-project/PROJECT_INSTRUCTIONS.md` 的内容放入 Project instructions。
3. 把 `skills/product-development-controller/SKILL.md` 作为 Project 文件加入。
4. 当某个工作需要更完整规则时，再加入 `SKILL.md` 指向的相关 reference 文件。
5. 在这个 Project 中进行持续产品开发。

ChatGPT Projects 当前支持项目级 instructions 与文件上下文：<https://help.openai.com/en/articles/10169521-projects-in-chatgpt>

**能力边界：**普通 ChatGPT Project 可以承载 PDC 的 Outcome / Focus / Explore / Preview / 路线控制和 Product Owner 协作规则，但如果没有真实 repository/runtime 工具，不得声称已经获得 Software/PDC strict Engineering 的 Git、测试、独立验证、集成与关闭保证。

---

## Codex Desktop

推荐统一入口：

```bash
python scripts/pdc_install.py install --target codex
python scripts/pdc_install.py doctor --target codex
```

原有命令继续有效：

```bash
python scripts/pdc_first_run.py install
python scripts/pdc_first_run.py doctor
python scripts/pdc_first_run.py demo
```

已有旧安装时使用 `--replace`。

---

## Claude Code

Claude Code 原生使用 `SKILL.md`，个人技能目录为 `~/.claude/skills/`，项目技能目录为 `.claude/skills/`。

全局安装：

```bash
python scripts/pdc_install.py install --target claude-code
python scripts/pdc_install.py doctor --target claude-code
```

项目内安装：

```bash
python scripts/pdc_install.py install --target claude-code --scope project --project-root /path/to/project
python scripts/pdc_install.py doctor --target claude-code --scope project --project-root /path/to/project
```

官方文档：<https://code.claude.com/docs/en/skills>

---

## Cursor

Cursor 原生支持 Agent Skills，个人目录包括 `~/.cursor/skills/`，项目目录包括 `.cursor/skills/`。

全局安装：

```bash
python scripts/pdc_install.py install --target cursor
python scripts/pdc_install.py doctor --target cursor
```

项目内安装：

```bash
python scripts/pdc_install.py install --target cursor --scope project --project-root /path/to/project
python scripts/pdc_install.py doctor --target cursor --scope project --project-root /path/to/project
```

官方文档：<https://cursor.com/docs/skills>

---

## GitHub Copilot

GitHub Copilot 的 Agent Skills 支持个人 `~/.copilot/skills/` 与项目 `.github/skills/`。

全局安装：

```bash
python scripts/pdc_install.py install --target copilot
python scripts/pdc_install.py doctor --target copilot
```

项目内安装：

```bash
python scripts/pdc_install.py install --target copilot --scope project --project-root /path/to/project
python scripts/pdc_install.py doctor --target copilot --scope project --project-root /path/to/project
```

官方文档：<https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills>

---

## 更新与替换

对于 Claude Code、Cursor、Copilot：

```bash
python scripts/pdc_install.py install --target <target> --replace
python scripts/pdc_install.py doctor --target <target>
```

替换前会把旧技能备份到 `~/.pdc-backups/`。

Codex 继续使用相同的 `--replace` 语义。

## Portable Agent Skill 包

每个 GitHub Release 除完整 PDC plugin ZIP 外，还发布：

```text
pdc-agent-skill-<version>.zip
pdc-agent-skill-<version>.zip.sha256
```

该包只包含 `product-development-controller/` Skill 目录，适合 ChatGPT Skill 上传和其他支持 Agent Skills 开放格式的宿主。

**portable ≠ qualified。**只有本页支持矩阵中列为原生并进入 PDC 公共 CI/官方宿主文档核对的路径，才属于当前声明支持范围。
