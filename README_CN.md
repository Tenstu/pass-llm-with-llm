# Pass-LLM-with-LLM

> 用 LLM 备考 LLM 笔试 — 基于 Claude Code Skills + MCP 的 AI 笔试备考引擎

[English](README.md)

## 这是什么

一个**执行型备考框架**，不是知识库。它通过 Claude Code 的 Skill 机制，将算法骨架生成、解题诊断、代码标注、错题回流、选择题训练串联成自动化闭环。

默认面向 AI/算法岗位笔试，核心 Skill Pipeline 与考试无关，可适配任意笔试目标。

## 核心特性

- **Skill Pipeline**：solve-skeleton → solve-analyze → algo-annotation，从题目到标注解法的完整链路
- **错题反馈闭环**：WA/TLE 自动记录，下次刷题自动标注 `# [防错]` 标记
- **选择题引擎**：定向出题 → 交互答题 → 即时评分 → 弱点分析
- **MCP 经验沉淀**（可选）：自定义 MCP Server 实现跨会话错误模式持久化 + 用户画像
- **进度追踪**：就绪度评分、知识点覆盖缺口、每日必做清单

## 快速开始

### 前置条件

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI 或 VS Code 扩展
- Python 3.10+（仅 MCP Server 需要）

### 环境支持

| 组件 | 说明 |
|------|------|
| IDE | VS Code（**推荐** — 交互答题模式需要 VS Code 扩展）或终端 |
| Claude Code | VS Code 扩展（**推荐**）或 CLI（`npm install -g @anthropic-ai/claude-code`） |
| Model Provider | 支持 Claude Code 接入的任意 provider（Claude API、第三方、本地模型） |
| Python | 3.10+（仅 exam-memory MCP Server 需要） |

本项目基于 **Claude Code VS Code 扩展**开发，使用第三方 model provider（小米 mimo-v2.5-pro、阶跃星辰 step-3.7-flash）。Skill Pipeline 与底层模型无关，任意可用模型均可运行。详见[环境支持文档](docs/environment-support.md)。

### 安装

```bash
git clone https://github.com/Tenstu/Pass-LLM-with-LLM.git
cd Pass-LLM-with-LLM
```

### 使用

1. 在 Claude Code 中打开项目目录
2. **首次使用？** 说 "init" 或 "初始化" — init-guide 会收集你的备考目标、日期和每日可投入时间，自动配置 `HANDOFF.md`、`sources/`、`AGENTS.md` 和用户画像
3. 日常使用：阅读 `START_HERE.md` 了解 session 启动流程
4. 遇到算法题：`Skill(skill="solve-skeleton")`
5. 需要诊断：`Skill(skill="solve-analyze")`
6. 练习选择题：`Skill(skill="choice-q-create")` → `Skill(skill="choice-q-drill")`

### 启动顺序

```
git clone → cd Pass-LLM-with-LLM
  │
  ├── pip install mcp               # 可选：安装 exam-memory MCP Server 依赖
  │
  ├── 编辑 .mcp.json                # 注册 exam-memory（见 docs/mcp-setup-guide.md）
  │
  ├── 在 Claude Code 中打开项目
  │     │
  │     ├── 首次使用 → 说 "init" → init-guide 自动完成全部配置
  │     │     （HANDOFF.md、sources/、AGENTS.md、用户画像）
  │     │
  │     └── 日常使用 → 读 START_HERE.md → Skill Pipeline
  │
  └── （可选）配置环境级 MCP：ChatMem、mempalace、onefind
        这些是外部工具，不由项目自带
        参考 docs/mcp-setup-guide.md
```

### MCP 依赖说明

本项目**自带一个 MCP Server**（`exam-memory`），**引用外部 MCP** 需单独安装：

| MCP Server | 是否自带 | 用途 | 配置方式 |
|------------|:---:|------|---------|
| `exam-memory` | 是 | 跨会话经验持久化 + 用户画像 | `pip install mcp` + 编辑 `.mcp.json` |
| ChatMem | 否 | 跨会话对话记忆 | [外部安装](https://github.com/Rimagination/ChatMem/releases) |
| mempalace | 否 | 结构化知识存储 | [外部安装](https://github.com/MemPalace/mempalace) |
| onefind | 否 | 本地知识库检索 | [外部安装](https://github.com/iawnfoanaowt/OneFind) |

所有 Skill 在 MCP 不可用时自动降级为纯本地模式。详见 [MCP 配置指南](docs/mcp-setup-guide.md)。

## Skill 一览

| Skill | 功能 | MCP 依赖 |
|-------|------|:---:|
| init-guide | 首次使用导引：备考目标、日期、范围、用户画像 | 可选 |
| solve-skeleton | 算法题骨架生成（8 模板 + 6 模式） | 无 |
| solve-analyze | 解题诊断：代码对比 + 根因标签 | 可选 |
| algo-annotation | 中文注释 + `# [防错]` 标记 | 无 |
| choice-q-create | 定向选择题生成 | 可选 |
| choice-q-drill | 交互答题 + 即时评分 | 可选 |
| exam-assistant | 考试助手（经验检索 + 用户画像） | 核心 |
| review-tracker | 进度汇总 + 就绪度趋势 | 无 |

标记"可选"的 Skill 在 MCP 不可用时自动降级为纯本地模式。

### ChatMem 增强（推荐）

[ChatMem](https://github.com/Rimagination/ChatMem/releases) 提供跨会话对话记忆。非必需，但能显著提升以下 Skill 的体验：

| Skill | ChatMem 增强效果 |
|-------|-----------------|
| review-tracker | 存储历史进度报告，实现跨会话趋势对比 |
| exam-assistant | 回溯之前的答题会话和错题讨论，保持学习连续性 |
| init-guide | 记忆上次配置过程，避免重复收集已知信息 |
| solve-analyze | 跨会话关联诊断历史，识别反复出现的错误模式 |

安装 ChatMem 并在 Claude Code 全局配置中注册。详见 [MCP 配置指南](docs/mcp-setup-guide.md)。

### MemPalace 增强（可选）

[MemPalace](https://github.com/MemPalace/mempalace) 提供结构化知识存储与跨 wing 知识图谱。适合长期知识管理，超越单次备考周期：

| 使用场景 | 增强效果 |
|---------|---------|
| 知识图谱 | 建模知识点前置关系（如 DP ← 背包问题，二分 ← 有序数组），实现定向复习 |
| Agent 日记 | 每次 session 记录学习观察，构建可搜索的"我学到了什么"历史 |
| 跨项目知识 | 将备考笔记与项目实战、面试准备、研究笔记关联 |

适合与 review-tracker（知识图谱查覆盖缺口）和 exam-assistant（结构化检索历史洞察）配合使用。项目内 Skill 不直接调用 MemPalace，通过 Claude Code 手动使用其工具。

### OneFind 增强（可选）

[OneFind](https://github.com/iawnfoanaowt/OneFind) 从本地知识库（Obsidian 笔记库、Zotero 文献库、本地文件夹）检索内容。适合已有外部学习笔记的用户：

| 使用场景 | 增强效果 |
|---------|---------|
| Obsidian 笔记 | 练习时搜索已有的 ML/算法笔记，关联相关概念 |
| Zotero 文献库 | 为 `llm/` 速记资料中的 Transformer、GNN、Diffusion 主题检索参考论文 |
| 混合检索 | 跨所有本地源执行词法 + 语义联合搜索 |

适合与 choice-q-create（从笔记中搜索出题素材）、exam-assistant（解答时检索参考资料）和 review-tracker（检查笔记是否覆盖考试知识点）配合使用。项目内 Skill 不直接调用 OneFind，通过 Claude Code 手动使用其工具。

#### OneFind + exam-memory：互补检索层

OneFind 的 **folder source** 可以索引 `exam_memory/experiences/` 目录，提供语义搜索能力。但 OneFind 是**只读检索**层设计，无法替代 exam-memory 的写入链路（保存经验 → 向量化 → 原子存储）。推荐组合方案：

| 层级 | 角色 | 写入 | 读取 |
|------|------|:----:|:----:|
| `exam-memory` MCP | 经验 CRUD + 错误计数 + 用户画像 | 是（save, update） | 是（list, 按类型过滤） |
| OneFind folder source | 经验文件的语义搜索覆盖层 | 否（仅索引刷新） | 是（语义 + 关键词） |

**配置方式**：将 OneFind 的 `folder_library` 指向 `exam_memory/experiences/`，然后使用 `onefind_search`（`target="folder"`）对历史经验做语义检索。通过 MCP 保存新经验后，调用 `onefind_index_refresh` 触发索引更新。

## 路线图

### V1（当前）— 稳定版

- Skill Pipeline：solve-skeleton / solve-analyze / algo-annotation
- 选择题引擎：出题 / 答题 / 评分
- exam-memory MCP V1：本地文件式经验 CRUD + 用户画像
- 进度追踪与错题反馈闭环

### V2 — RAG + 语义检索

将 `exam-memory` 从关键词匹配升级为语义检索：

| 阶段 | 特性 | 依赖 |
|------|------|------|
| 1 | 经验文件自动向量化 → numpy 存储 | `sentence-transformers`（bge-m3） |
| 2 | `list_experiences` 支持语义检索 | 阶段 1 |
| 3 | LLM 自动推断用户画像 | LLM API |
| 4 | 知识图谱关联推荐前置知识点 | 阶段 1 |

### V3 — 远期方向

- **多模态**：截图题目 OCR → 自动识别题型并检索经验
- **间隔重复**：基于 SM-2 算法自动安排复习
- **跨设备同步**：Git 或 WebDAV 同步经验文件
- **可视化仪表盘**：强弱项热力图、错误趋势、复习计划

### 开源改进

- GitHub Issue & PR 模板（`.github/`）
- `CHANGELOG.md`

## 目录结构

```
Pass-LLM-with-LLM/
  AGENTS.md                    # 项目规则、Component Map、Skill Pipeline
  START_HERE.md                # Session 启动引导 + Skill 调用指南
  HANDOFF.md                   # Session 交接模板
  README.md                    # 英文文档
  README_CN.md                 # 本文件（中文）

  skills/                      # Claude Code Skill 定义
    init-guide.md              # 首次使用导引（备考目标、日期、范围）
    solve-skeleton/            # 算法骨架模板
    solve-analyze/             # 解题诊断引擎
    algo-annotation.md         # 代码标注 + 防错标记
    choice-q-create.md         # 选择题生成器
    choice-q-drill.md          # 交互答题模式
    exam-assistant.md          # MCP 考试助手
    review-tracker.md          # 进度汇总

  algorithms/                  # OJ 代码资产
    python_oj_template.py      # 工具函数库
    solutions_batch.py         # 考试真题解答集
    practice/                  # 按专题分类的练习题
    mistake_log.md             # WA/TLE 错误模式记录
    topic_checklist.md         # 知识点覆盖追踪

  llm/                         # AI/ML 速记资料
    llm_core_cheatsheet.md     # Transformer, SFT/LoRA, RLHF, RAG, KV cache
    gnn_diffusion_cheatsheet.md
    math_fundamentals.md
    ai_lab_context.md          # 目标公司/实验室背景

  exam_memory/                 # 自定义 MCP Server（可选）
    server.py                  # 6 个 MCP 工具，经验持久化
    experiences/               # 经验文件（YAML frontmatter + Markdown）
    user_profile.json          # 用户画像（强弱项、偏好）

  daily/                       # 每日计划（YYYY-MM-DD.md）
  progress/                    # 按主题分类的进度追踪
  sources/                     # 外部参考材料
  prompts/                     # Prompt 模板
  docs/                        # 设计文档、配置指南与许可证
    mcp-setup-guide.md         # MCP 配置指南：exam-memory 注册 + 外部 MCP 引用
```

## 适配其他考试

默认配置针对 AI Lab 笔试，但核心机制可复用：

1. 替换 `sources/ai_lab_history_problems.md` 为目标考试的题型分析
2. 调整 `skills/choice-q-create.md` 中的出题参数
3. 更新 `llm/` 下的速记资料为目标领域知识
4. 修改 `AGENTS.md` 中的 Exam Format 表格

## Contributing

见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE)
