# PDC — Product Development Controller

> **AI can build fast. PDC keeps the product in control.**
>
> **AI 很擅长优化眼前的局部。PDC 负责确认这些局部仍然在通往真正想要的结果。**

[![Public CI](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/codeql.yml/badge.svg)](https://github.com/xiaokonglong10086/PDC-skill/actions/workflows/codeql.yml)

AI 已经很会写代码、做原型、改 Bug。  
但当一个产品真的连续开发几天、几周甚至更久，最容易失控的往往不是“代码写不出来”，而是：

**现在到底该做什么？为什么要做？什么证据才算够？谁有权说它已经完成？中断以后还能不能继续？**

还有一个更隐蔽的问题：AI 往往会把当前任务完成得越来越好，却忘记重新确认当前任务是否仍然服务最终目标。

它可能把一个用于简单预览的实验，逐步升级成近乎论文级的实验室；把测试体系、架构、流程或工具打磨得非常严密，却迟迟没有回答真正的产品问题。每一步单独看都合理，所有局部最优加在一起，却未必得到整体最优。

**PDC 不是另一个 Coding Agent。它是围绕 ChatGPT、Codex、Claude Code、Cursor 等执行工具的产品开发控制层。**

你继续负责产品：目标、用户体验、优先级、关键取舍和最终验收。  
PDC 负责把复杂的开发过程控制住：恢复上下文、选择正确路线、守住当前焦点、判断证据是否足够、冻结正式开发的完成标准、独立验证结果，并让中断后的工作可以继续，而不是把 Git、日志和恢复问题扔给 Product Owner。

当前公开版本：**v0.1.0-beta.2**。这是可公开安装和使用的 Beta；公开技术验证已经自动化，但真实首次用户和外部采用证据仍在积累，因此不会把 Beta 描述成已经完成外部验证的稳定版。

## 5 分钟开始

需要：

- Git；
- Python 3.11+；
- Codex Desktop（当前公开安装路径）。

```bash
git clone https://github.com/xiaokonglong10086/PDC-skill.git
cd PDC-skill
python scripts/pdc_first_run.py install
python scripts/pdc_first_run.py doctor
python scripts/pdc_first_run.py demo
```

Windows 如果 `python` 不可用，可以把上面的 `python` 换成 `py`。

更完整的首次使用说明见 [`START_HERE.md`](START_HERE.md)。

## AI 产品开发是怎么失控的

这些情况很常见：

- 同一个项目换了几轮会话，已经决定过的问题又被重新讨论；
- 中途来了一个 Bug 或新点子，AI 顺手就把整个开发方向带偏；
- AI 沿着当前方法持续优化，却不再检查这条路是否仍然通向最终结果；
- 为了让实验“无懈可击”，不断修实验环境、提高标准，反而没有完成原本只需粗略验证的 Preview；
- 无法达到理想实验条件，就把“实验室不够完美”误判成“这个产品方向不可行”；
- 原型“看起来能用”，于是大家默认它已经可以进正式产品；
- 负责实现的 Agent 自己跑了测试，然后自己宣布“完成”；
- 技术测试通过，被误当成 Product Owner 已经接受产品；
- 项目中断以后，Product Owner 被要求自己看 Git、读日志、判断该怎么恢复；
- 同时有好几个未完成方向，最后没人说得清现在真正推进的是哪一个；
- 完成标准在实现过程中被悄悄改变。

PDC 的价值，就是让这些问题**不再依赖某一次对话里模型是否刚好记得、谨慎或自觉。**

## PDC 在这些时候具体做什么

| 你遇到的情况 | 普通 AI 开发很容易发生什么 | PDC 怎么处理 |
| --- | --- | --- |
| 还不确定真正应该做什么 | 因为“写代码很快”，于是过早开始实现 | 进入 **Explore**，先解决真正会改变方向的不确定性 |
| 想知道用户到底会不会用 | 继续开会、研究、讨论，却没有现实证据 | 进入 **Preview**，做最小但可信的真实实验 |
| 实验只是为了看一个方向是否大致可行 | 不断提高实验室、测试和环境标准 | 先定义**决策所需的最低可信证据**，明确允许哪些缺陷和近似，达到后停止加码 |
| 当前方案越做越精致，但最终结果没有推进 | 继续优化当前局部，因为已经投入很多 | 回到 Outcome 和长期路线，判断应继续、绕路、降级、换方法还是停止 |
| 已经确定要正式开发 | 一边实现，一边不断改变“做到什么算完成” | 进入 **Engineering**，先冻结完成边界，再实现 |
| 中途冒出新需求或 Bug | AI 立刻切过去做，当前工作逐渐失焦 | 保留新问题，但继续守住**唯一正在推进的 Work Focus** |
| Agent 说“我测试通过了” | 实现者同时成为自己的裁判 | 把验证绑定到**确切交付版本**，并进行独立验证 |
| 技术上已经 PASS | 自动被当成产品已经验收 | 技术 PASS 与 **Product Owner 可见验收**明确分开 |
| Chat / Agent / 机器换了 | 上下文丢失，只能重新解释一遍 | 从持久权威恢复路线、决策、证据和交付状态，再继续 |
| 恢复过程中出现 Git / 日志问题 | Product Owner 被迫变成技术恢复人员 | PDC 在幕后处理；只有真正属于产品负责人的决定才会打断你 |

## 它和 Coding Agent 到底有什么不同？

Coding Agent 主要回答：

> **“这个东西怎么实现？”**

PDC 控制的是周围更难、也更容易失控的问题：

> **“现在最应该做什么？为什么？它怎样服务最终结果？需要做到多好才足够？什么时候才算真的完成？谁来证明？中断后还能不能可靠地继续？”**

所以 PDC 不替代 Codex、Claude Code、Cursor 或其他执行工具。  
它让这些工具可以更自主地工作，**但不会因此获得修改产品目标、批准自己、悄悄扩大范围，或者把技术复杂度转嫁给 Product Owner 的权力。**

## 整体最优优先，而不是每个局部都完美

PDC 不把“当前步骤做得最好”当成默认目标。它先判断这一步在整个路线里的作用。

在每个材料性下一步之前，PDC 应当能够回答：

1. **最终想实现的 Outcome 是什么？**
2. **当前在整条路线的什么位置？**
3. **这一步怎样推进当前位置，而不是只改善一个局部指标？**
4. **这个决策真正需要多高的质量、真实性或证据强度？**
5. **哪些缺陷、捷径、近似或绕路可以明确接受？**
6. **达到什么条件就停止继续优化这个局部？**

这并不意味着降低所有标准。安全、隐私、合规、不可逆操作和已经冻结的正式 Engineering 边界不能用“整体最优”绕过。

它意味着：标准必须服务目的。一个用于快速判断方向的 Preview，可以有很多已知缺陷，只要这些缺陷不会让结论失真；一个正式交付给用户的 Engineering 版本，则需要守住已经批准的完成线。

### 一个典型例子

假设“作家脑”当前只想粗略验证一种写作协作方式是否有潜力。

错误路线是：为了得到完美结论，先建立无懈可击的实验环境；环境不够理想就继续修实验室；仍然不完美时宣布方向不可行。此时项目真正优化的已经不是作家脑，而是实验室。

PDC 应当做的是：先冻结这次 Preview 只想回答的一个问题，选择足以回答它的最低可信实验，明确样本、环境和方法有哪些限制；当证据已经足以支持“继续、调整或停止”的下一步决定时，就停止完善实验环境。

**实验是取得决策证据的手段，不是隐藏的新产品。**

## 一个完整例子

假设你说：

> “我想做一个 AI 工具，帮助团队整理和分析客户反馈。”

PDC 不会马上让 Agent 开始写代码。

1. **先恢复已有事实**  
   项目以前做过什么、有哪些决定、是否已有原型、还有什么未完成工作——能恢复的内容不会再让你重复讲一遍。

2. **判断当前真正的问题**  
   如果最大问题是“我们还不知道用户真正需要什么”，当前工作就是 Explore，而不是 Coding。

3. **需要现实答案时做 Preview**  
   如果只有真实使用才能回答问题，就做一个最小完整体验来验证，而不是继续堆研究材料或把实验环境做成新工程项目。

4. **检查局部动作是否服务整体路线**  
   每次准备加功能、修工具或提高测试标准时，先说明它怎样改变当前产品决定；无法说明，就停止或换路线。

5. **方向明确后才进入 Engineering**  
   在正式实现前，把用户可见行为、范围和“什么算完成”冻结下来。

6. **让实现者实现，但不让实现者自我批准**  
   Agent 可以写代码、跑自己的检查；正式 PASS 则必须基于独立验证，并且绑定到确切版本。

7. **最后由 Product Owner 判断产品，而不是判断 Git**  
   你验收的是“产品是不是我想要的”，不是哈希、日志、测试框架和仓库状态。

8. **交付以后真正关闭**  
   决策、证据、版本、验收和交付状态留下持久记录，下一次会话可以从真实状态继续。

## PDC 的核心控制循环

```text
Outcome
  ↓
可信的端到端 Strategic Workpath
  ↓
一个正在推进的 Work Focus
  ↓
Explore / Preview / Engineering
  ↓
对整体路线最有价值、成本最低但可信的下一步
  ↓
证据或实现
  ↓
独立验证
  ↓
需要时由 Product Owner 验收可见产品行为
  ↓
交付、关闭、可恢复连续性
  ↺
重新检查局部进展是否仍然服务 Outcome
```

## 三种工作模式

| Mode | 什么时候使用 | 优化目标 |
| --- | --- | --- |
| **Explore** | 方向或关键假设仍不确定 | 用最低成本减少会改变决策的不确定性 |
| **Preview** | 需要真实使用证据 | 用最小完整体验和决策充分的可信度回答一个明确现实问题 |
| **Engineering** | 行为已经理解并批准 | 冻结完成边界，可靠构建、验证和交付 |

## PDC 保护的五件事

### 1. 整体路线不会被局部优化替代
- 从 Outcome 和端到端路线出发，而不是从当前实现方法出发
- 每个材料性下一步都必须说明怎样推进当前路线
- 明确“足够好”的阈值、可接受的不完美和停止条件
- 重复优化局部而路线停滞时，质疑路线而不是继续加码

### 2. 方向不会轻易漂移
- 同一时间只有一个真正推进的 Focus
- 新想法可以记录，但不会自动改写长期路线
- 可以接受为了更好结果而必要的弯路，但必须说明它在路线中的作用
- 当更多研究、实验或打磨已经没有决策价值时，会停止并进入下一步

### 3. “感觉可行”不会冒充证据
- 观察事实与解释分开
- Preview 成功不等于生产就绪
- “模型说可以”不是完成证据
- 安全、合规等专业边界不会交给 Product Owner 猜

### 4. 正式开发有清晰、稳定的完成线
- Engineering 开始前明确完成边界
- 边界冻结后不能悄悄移动
- 实现者不能成为唯一的正确性裁判
- 验证必须对应实际被审查的那个版本
- 技术 PASS 与产品验收是两件不同的事

### 5. 项目不会因为换会话就失忆
- 长期状态不依赖聊天记忆
- 可以恢复产品意图、当前工作、证据、交付版本、验收和关闭状态
- “恢复成功”不等于“原来的任务已经完成”
- Product Owner 不承担 Git / 日志 / 技术恢复工作

## 谁会需要 PDC

PDC 特别适合：

- 正在用 ChatGPT、Codex、Claude Code、Cursor 等工具做真实产品的非技术或弱技术 Product Owner；
- 已经无法靠一段 Prompt 和聊天记忆维持一致性的长期 AI 开发；
- 同时存在原型、实验、正式开发、多个新想法，开始容易混在一起的项目；
- 发现 AI 很会完成局部任务，却需要有人持续守住最终目标和整体路线的项目；
- 希望让 AI 执行得更自主，但又不愿失去**产品决策权、证据质量和清晰完成标准**的团队；
- 需要严格、可检查、可恢复的软件开发交付过程。

## 公开能力边界

PDC 的控制模型可用于软件、Skills、Agents、自动化/工作流、原型、内部工具和混合数字交付物。

当前完整实现的严格正式 Engineering Profile 是仓库型 **Software/PDC**。其他交付类型可以使用 Explore、Preview、控制、证据和委派模型，但本项目不会声称它们已经拥有同等级的正式 Engineering 保证。

另外，PDC 的 Git/worktree 隔离**不是安全沙箱**。不要用冻结测试命令执行不可信代码。安全边界见 [`SECURITY.md`](SECURITY.md)。

## 公开验证

每个 PR 和 `main` 更新都会运行公开 CI：

- Linux / Windows / macOS；
- Python 3.11 / 3.12 / 3.13；
- 公开包边界审计；
- 11 项确定性自测；
- 安装、doctor、虚构 demo；
- Python 编译检查；
- Release 包构建。

详细范围见 [`PUBLIC_VERIFICATION.md`](PUBLIC_VERIFICATION.md)。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| [`skills/product-development-controller/SKILL.md`](skills/product-development-controller/SKILL.md) | PDC Skill 主入口 |
| [`skills/product-development-controller/references/`](skills/product-development-controller/references/) | 架构、权威、模式、评审、验收与恢复规则 |
| [`skills/product-development-controller/scripts/`](skills/product-development-controller/scripts/) | 生命周期、证据、验证和恢复工具 |
| [`scripts/`](scripts/) | 公开安装、首次运行、CI 与发行工具 |
| [`examples/`](examples/) | 完全使用虚构数据的示例 |
| [`PUBLIC_VERIFICATION.md`](PUBLIC_VERIFICATION.md) | 可重复的公开验证范围 |
| [`PUBLIC_RELEASE_SCOPE.md`](PUBLIC_RELEASE_SCOPE.md) | Public / Private 边界 |

## 参与项目

欢迎 Bug、文档改进、兼容性修复、测试、可复现案例和经过边界说明的新能力。

开始前请阅读：

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- [`SECURITY.md`](SECURITY.md)
- [`GOVERNANCE.md`](GOVERNANCE.md)

公开 Issue 不要包含密码、Token、私有仓库地址、客户数据或其他敏感信息。

## 发布与版本

- `v0.1.0-beta.2`：恢复完整产品叙事，并加入“全局结果优先于局部完美”的控制原则；
- `v0.1.0-beta.1`：首个正式开源 Beta；
- 标签发行必须先通过与 PR 相同的公开验证矩阵；
- GitHub Release 会附带可下载 ZIP 和 SHA-256；
- 变更记录见 [`CHANGELOG.md`](CHANGELOG.md)；
- 后续方向见 [`ROADMAP.md`](ROADMAP.md)。

## Public / Private Boundary

这个仓库是 PDC 的公开发行源，不包含私有项目状态、私有 Git 历史、真实项目运行记录、私有回归基础设施、个人数据或凭证。

公开仓库不会自动从私有 PDC 同步。每次公开更新都必须经过单独评审、公开 CI 和版本化发行。

## License

PDC-skill 使用 [MIT License](LICENSE) 开源。
