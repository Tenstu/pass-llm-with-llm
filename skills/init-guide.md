---
name: init-guide
description: 首次使用引导 — 收集备考目标、更新个人画像、配置考试范围，判断是否需要创建新 Skill。
---

# init-guide — 项目初始化导引

> 仅在首次使用或需要重新配置备考目标时调用。

## 触发条件

- 用户说"初始化"、"init"、"开始配置"、"第一次用"
- `START_HERE.md` 检测到 `HANDOFF.md` 仍为模板状态（未填写具体考试信息）
- 用户说"换一个考试目标"

## 工作流

### Step 0: 记忆/检索增强安装引导（可选）

在收集备考信息之前，先确认用户想走哪种启动路径。默认不要求外部 MCP 工具；安装失败不能阻塞后续初始化和练习闭环。

**Q0: 是否启用记忆/检索增强？**

向用户展示选项：

| 选项 | 说明 |
|------|------|
| 继续本地 Markdown | 不安装 MCP，直接进入目标配置（默认最低门槛） |
| 启用 exam-memory | 安装并配置项目自带的 exam-memory MCP（推荐长期备考） |
| 查看外部工具 | 仅在用户已经需要 ChatMem、MemPalace 或 OneFind 时继续配置 |

#### 各工具说明

| 工具 | 用途 | 安装方式 | 已安装检测 |
|------|------|----------|------------|
| `exam-memory` | 跨会话错题经验持久化、用户画像、语义检索 | `pip install ".[embed]"` 在 `shared/exam_memory/` 下 | 检查 `.mcp.json` 是否包含 `exam-memory` |
| [ChatMem](https://github.com/Rimagination/ChatMem) | 对话级记忆，用于交接、继续、项目历史回忆 | 从 [GitHub Releases](https://github.com/Rimagination/ChatMem/releases) 下载 `ChatMem.exe`，放置于 `D:\Programe\chatmem\`，以 `ChatMem.exe --mcp` 方式运行 | 检查 `D:\Programe\chatmem\ChatMem.exe` 是否存在 |
| [MemPalace](https://github.com/MemPalace/mempalace) | 长期结构化知识存储与知识图谱工作流 | `pip install mempalace`，以 `py -3.11 -m mempalace.mcp_server` 或 `mempalace-mcp` 方式运行 | 检查 `mempalace` CLI 是否在 PATH 中 |
| [OneFind](https://github.com/iawnfoanaowt/OneFind) | 外部本地知识库只读检索（Obsidian/Zotero/文件夹等） | 从 [GitHub Releases](https://github.com/iawnfoanaowt/OneFind/releases) 下载安装包，解压到 `D:\tools\onefind\` | 检查 `D:\tools\onefind\` 是否存在 |

#### 安装执行流程

1. 用户选择"继续本地 Markdown"时，直接进入 Step 1。
2. 用户选择"启用 exam-memory"时，执行 `scripts/setup_mcp_tools.py --recommended`（等价于 `--exam-memory-only`）。
3. 用户选择"查看外部工具"时，先执行 `scripts/setup_mcp_tools.py --check`；确认用户已手动安装外部工具后，再执行 `scripts/setup_mcp_tools.py --configure-installed-external` 或 `scripts/setup_mcp_tools.py --config-only onefind`。
4. 只有用户明确要求全量尝试时，才执行 `scripts/setup_mcp_tools.py --all`。外部工具缺失只提示安装方式，不阻塞初始化。
5. 每安装或配置一个工具后，向用户报告状态：`[OK]` / `[WARN]` / `[FAIL]` + 原因。

#### 安装脚本行为

`scripts/setup_mcp_tools.py` 执行以下操作：

- **exam-memory**：检查 `shared/exam_memory/`；执行本项目内的 `pip install -e ".[embed,generate]"`；生成 stdio 命令到 `.mcp.json`。
- **ChatMem**：检查 `D:\Programe\chatmem\ChatMem.exe` 是否存在；不存在则提示用户从 GitHub Releases 下载；已安装时生成启动命令 `ChatMem.exe --mcp` 到 `.mcp.json`。
- **MemPalace**：检查 `mempalace` CLI 是否可用；按用户选择执行 `pip install mempalace` 或仅配置；生成 stdio 命令到 `.mcp.json`。
- **OneFind**：检查 `D:\tools\onefind\` 是否存在；不存在则提示用户从 GitHub Releases 下载；已安装时生成启动命令到 `.mcp.json`。OneFind 只作为外部只读检索层，不写入项目错题状态，也不共享 `shared/exam_memory/vectorstore/`。

> **注意**：`.mcp.json` 被 `.gitignore` 忽略，不会进入 git。所有 MCP 配置都是用户本地的。

### Step 1: 收集基本信息

依次使用 `AskUserQuestion` 工具收集以下信息（每组问题不超过 4 个选项）：

**Q1: 备考哪家单位/公司？**
- 互联网大厂（字节/腾讯/阿里/百度等）
- AI 实验室（智谱/月之暗面/MiniMax/商汤等）
- 国企/事业单位（运营商/银行/公务员等）
- 其他（用户自行输入）

**Q2: 目标岗位方向？**
- 大模型算法（Transformer/LLM/推理优化）
- CV/多模态（扩散模型/GNN/视觉语言）
- NLP/对话系统
- 通用算法/后端
- 其他（用户自行输入）

**Q3: 考试时间？**
- 1 周内
- 2 周内
- 1 个月内
- 3 个月以上
- 尚未确定

**Q4: 当前备考状态？**
- 零基础，刚开始准备
- 有一定基础，需要系统复习
- 已刷过一轮，需要查漏补缺
- 考前冲刺，需要速查模式

### Step 2: 确认考试范围

根据 Step 1 的回答，推断默认考试格式并展示给用户确认：

```markdown
根据你的选择，我将配置以下考试范围：

| 维度 | 配置 |
|------|------|
| 目标单位 | {用户选择} |
| 岗位方向 | {用户选择} |
| 题型 | {根据方向推断，如：单选 + 多选 + 编程} |
| 重点知识 | {根据方向推断} |
| 考试时间 | {用户选择} |
```

询问用户是否需要调整。如果用户的考试目标不在 AI 方向（如公务员行测、金融笔试），提示需要：
1. 替换 `targets/{target}/sources/` 下的考试分析文件
2. 替换 `targets/{target}/cheatsheets/` 和 `shared/cheatsheets/` 下的速记资料为目标领域
3. 可能需要创建新的 Skill 来适配目标题型

### Step 3: 更新配置文件

#### 3.1 更新 `HANDOFF.md`

将模板占位符替换为实际信息：

```markdown
# HANDOFF

> 每轮备考/学习 session 结束前更新此文件，作为下一次 session 的启动上下文。

## Current Status

- Date: {今天日期}
- Target exam: {单位名称}{岗位}笔试，{考试日期或"待定"}
- Current objective: {根据状态推断，如"基础补齐" / "系统复习" / "查漏补缺" / "考前冲刺"}
- Strategy: {根据方向推断配比}
```

#### 3.2 更新用户画像

调用 `mcp__exam-memory__update_user_profile()` 更新画像：

```json
{
  "target_company": "{单位名称}",
  "target_role": "{岗位方向}",
  "exam_date": "{考试日期}",
  "prep_status": "{备考状态}",
  "recent_focus": "{初始聚焦方向}"
}
```

如果 MCP 不可用，跳过此步（画像会在后续使用中逐步建立）。

#### 3.3 更新当前目标状态

不要为单个考试目标修改 `AGENTS.md`。当前目标、最后完成事项和下一步写入 `HANDOFF.md`；题型、分值、时间和目标专属配置写入 `targets/{target}/exam_config.md`。

#### 3.4 创建/更新 `targets/{target}/exam_config.md`

从模板 `targets/exam_config_template.md` 复制，填入目标考试的实际参数：

```markdown
# {目标名称} 考试配置

| 题型 | 题数 | 分值 | 合计 |
|------|------|------|------|
| 单选题 | {N} | {X}分 | {合计}分 |
| 不定项选择题 | {N} | {X}分 | {合计}分 |
```

`choice-q-create` 和 `choice-q-drill` 从该文件读取格式参数，不再硬编码。
如果用户不清楚具体分值，填入"待确认"，后续根据真题/mock 补全。

### Step 4: 判断是否需要新 Skill

检查当前 Skill 是否覆盖目标考试的题型：

| 目标考试类型 | 需要的 Skill | 当前状态 |
|-------------|-------------|---------|
| AI/算法笔试（单选+多选+编程） | solve-skeleton, choice-q-create/drill, review-tracker | ✅ 已有 |
| 纯编程笔试（ACM/OI） | solve-skeleton, solve-analyze, algo-annotation | ✅ 已有 |
| 行测/公务员笔试 | 需要新 Skill（言语理解、判断推理、资料分析） | ❌ 需创建 |
| 金融/银行笔试 | 需要新 Skill（金融知识、行测） | ❌ 需创建 |

如果需要创建新 Skill：
1. 告知用户："当前 Skill 集不完全覆盖 {目标考试}，建议创建以下新 Skill：{列表}"
2. 提供 Skill 创建建议（文件名、核心功能、参考现有 Skill 结构）
3. 用户确认后，在 `skills/` 下创建新 Skill 文件骨架

### Step 5: 生成初始化报告

完成后输出初始化摘要：

```markdown
## ✅ 初始化完成

**备考目标**：{单位} - {岗位}
**考试时间**：{日期}
**当前状态**：{状态}
**已配置**：
- [x] HANDOFF.md — 备考目标已填写
- [x] 用户画像 — 已更新（MCP 可用时）
- [x] exam_config.md — 考试格式参数已写入
- [x] 考试范围 — 已确认

**下一步**：
1. 阅读 `START_HERE.md` 了解 Skill Pipeline
2. 调用 `Skill(skill="review-tracker")` 查看当前准备度
3. 开始第一道练习题：`Skill(skill="solve-skeleton")`

**可选增强**：
- 启用 exam-memory MCP 获取跨会话经验持久化：在 `.mcp.json` 中注册 stdio 命令运行 `shared/exam_memory/server.py`，也可参考 `README.md` 的 MCP 配置说明。
```

## 注意事项

- 所有信息收集使用 `AskUserQuestion`，不要自行猜测
- 如果 MCP 不可用，跳过画像更新步骤，不影响其他配置
- 初始化可以重复执行（如更换考试目标），每次会覆盖之前的配置
- 如果用户选择的考试方向与 AI 无关，不要直接拒绝，而是给出适配建议
