# START_HERE

## 首次使用？

如果本地 `HANDOFF.md` 不存在，先从 `HANDOFF.example.md` 复制一份。若 `HANDOFF.md` 中仍为模板占位符（`<考试名称>`、`YYYY-MM-DD`），说明尚未初始化：

```
Skill(skill="init-guide")
```

触发词："初始化"、"init"、"第一次用"、"开始配置"、"换一个考试目标"

init-guide 会引导你填写备考目标、考试范围、目标日期，并自动更新配置文件。

> **MCP 配置**：如需启用跨会话经验持久化，在 `.mcp.json` 中注册 stdio 命令运行 `shared/exam_memory/server.py`。所有 Skill 在 MCP 不可用时自动降级为 Local Markdown 或 Stateless Lite，不中断主流程。

## 运行模式速查

| Mode | 什么时候用 | 记录方式 |
|------|------------|----------|
| **Full MCP Mode** | `exam-memory` MCP 可用，且仓库可写 | Markdown + MCP 双写 |
| **Local Markdown Mode** | MCP / ChatMem / 本地索引不可用，但仓库可写 | `HANDOFF.md`、daily log、`mistake_log.md`、choice round 文件 |
| **Stateless Lite Mode** | 仓库不可写、只能聊天继续，或交互式 quiz 工具不可用 | 最终返回 `[MISTAKE_LOG_APPEND]`、`[DAILY_PROBLEM_LOG_APPEND]`、`[CHOICE_ROUND_SUMMARY]`、`[HANDOFF_UPDATE]` |

ChatMem、MemPalace、OneFind 是外部可选的 recall/search 增强，不是 session 启动条件。OneFind 只用于外部知识库的只读检索，不替代 `mistake_log.md` 或 `exam-memory`。

内部降级不阻塞练习；最终报告必须提醒：当前能力已降级、跨会话语义检索/错误频率合并/画像更新不可用、append blocks 需要落到 Markdown。Lite/Portable Mode 只适合临时环境、新用户启动和故障恢复，不建议长期作为唯一工作流。

## 新 Session 先读

1. `AGENTS.md`：确认目标、优先级、运行模式和关键边界。
2. `HANDOFF.md`：了解上次完成了什么。
3. 今天对应的 `shared/daily/YYYY-MM-DD.md`：直接执行当天任务，底部 Problem Log 记录每题结果。
4. `targets/{target}/progress/task-board/task-board.md` 或 `shared/progress/task-board/task-board.md`：更新任务状态。
5. `targets/{target}/mistake_log.md` 和 `targets/{target}/mock_exam_log.md`：复盘最近错误。
6. `Skill(skill="review-tracker")`：快速查看跨维度进度报告和今日必做清单（含到期复习项）。

## 今天开始前

如果在使用中积累了错题，`review-cli` 是可选增强，可用来构建复习队列：

```bash
cd shared
python -m exam_memory.review_cli --project-root .. build --target pdd-algo
```

没有 Python 环境、review-cli 或 MCP 时，直接检查 Markdown：`targets/{target}/progress/reviews/review-queue.md`、`targets/{target}/mistake_log.md`、今天的 `shared/daily/YYYY-MM-DD.md`。若文件缺失，按下方手动启动路径返回 append block，不要中断 session。

## 无 MCP / 无 Skill 手动启动

当没有 exam-memory MCP、本地数据库/索引、ChatMem 或交互式 quiz 工具时，仍按这个最小闭环启动：

1. 读取或填写 `HANDOFF.md`：当前目标、考试日期、今日可投入时间、下一步任务。
2. 创建今天的 `shared/daily/YYYY-MM-DD.md`；若不能写文件，在最终输出给出 `[DAILY_PROBLEM_LOG_APPEND]`。
3. 从 `targets/{target}/exam_config.md` 读取题型、分值和时间；若目标未确定，先使用 `HANDOFF.md` 中的 target。
4. 使用 `targets/{target}/mistake_log.md` 作为本地反馈状态；若文件不存在，把历史弱点标为"暂无数据"，不要编造错题。
5. 选择题出题时用 `exam_config.md` + 默认高频主题兜底；答题可用聊天格式提交，例如 `1A 2BD 3C`。
6. 结束时返回或写入 `[MISTAKE_LOG_APPEND]`、`[CHOICE_ROUND_SUMMARY]`、`[DAILY_PROBLEM_LOG_APPEND]`、`[HANDOFF_UPDATE]`。

## Skill Pipeline（必须遵守）

### 每道 OJ 题的标准流程

```
Solve Skeleton → Fill TODOs → Anti-pattern check → Test → [solve-analyze] → Algo-Annotation → Log
```

1. **solve-skeleton** — 遇到任何 OJ 题，先调用 `Skill(skill="solve-skeleton")`。
   - 读题 → 匹配关键词 → 选择 I/O 模板 + 算法骨架 → 输出 solve() 框架
   - 通过 `references/` 下的三个文件获取具体模板

2. **solve-analyze** — solve() 写完并测试后，如需诊断错误，调用 `Skill(skill="solve-analyze")`。
   - 并行运行两条路径：Agent A 静态分析用户代码 + Agent B 生成标准解法
   - 输出结构化对比报告：差异表格、根因标签（从 `root-cause-tags.md` 匹配）、建议修正
   - 自动追加到 `targets/{target}/mistake_log.md`（去重）
   - **可选 MCP**：`update_user_profile` + `save_experience` / `inc_error_count`（MCP 不可用时跳过）
   - 触发词："分析一下我的代码"、"帮我看看哪里错了"、"为什么WA"、"为什么超时"、"解法对比"
   - **何时调用**：WA/TLE 时必须调用；AC 时可选（仅做规范差异检查）

3. **algo-annotation** — solve() 写完后（或 solve-analyze 诊断后），调用 `Skill(skill="algo-annotation")`。
   - 添加中文行级注释
   - 标注 `# [防错]`（引用 `targets/{target}/mistake_log.md`）和 `# [双重角色]`
   - 一句话总结核心不变量

### 选择题标准流程

```
choice-q-create → choice-q-drill → mistake_log → (回到 choice-q-create)
```

3. **solve-analyze** — 需要诊断解法错误时，调用 `Skill(skill="solve-analyze")`。
   - 对比用户代码 vs 标准解法，提取根因标签，生成结构化报告
   - 自动追加到 `targets/{target}/mistake_log.md`（去重）
   - 可选 MCP：画像更新 + 经验持久化（MCP 不可用时跳过）
   - 触发词："分析一下我的代码"、"为什么WA"、"解法对比"、"代码诊断"

4. **choice-q-create** — 需要生成选择题组时，调用 `Skill(skill="choice-q-create")`。
   - 根据指定主题（数学/AI/LLM/算法）生成一组定向多选题
   - 从 `targets/{target}/mistake_log.md` 读取高频错误模式，重点出易错考点
   - **可选 MCP 增强**：调用 `mcp__exam-memory__list_experiences()` 获取跨会话错误模式
   - 输出结构化题集：题干 + 4 选项 + 正确答案 + 解析
   - 触发词："出几道选择题"、"生成选择题"、"choice question"、"帮我出题"

5. **choice-q-drill** — 拿到题集后，调用 `Skill(skill="choice-q-drill")` 进入交互答题。
   - AskUserQuestion 可用时逐题呈现；不可用时接受聊天答案，如 `1A 2BD 3C`
   - 即时反馈对错并给出解析
   - 仓库可写时，答错题目自动追加到 `targets/{target}/mistake_log.md`（标记 `# [选择题错题]`）和 daily log
   - 仓库不可写时，返回 `[CHOICE_ROUND_SUMMARY]`、`[MISTAKE_LOG_APPEND]`、`[DAILY_PROBLEM_LOG_APPEND]`、`[HANDOFF_UPDATE]`
   - **可选 MCP 双写**：同时调用 `mcp__exam-memory__save_experience()` 或 `mcp__exam-memory__inc_error_count()`
   - 答题完成后输出得分、错题汇总、薄弱主题建议
   - 触发词："开始答题"、"开始练习"、"drill"、"做选择题"、"quiz"

6. **review-tracker** — 跨维度进度汇总时，调用 `Skill(skill="review-tracker")`。
   - 聚合 task-board、study-planning/readiness-score、mistake_log、topic_checklist、daily logs、choice-questions 文件
   - 输出就绪度趋势、错题待修复清单、知识点覆盖缺口、今日必做清单
   - 支持"自评打分"更新 study-planning/readiness-score.md
   - 考前 ≤ 1 天自动切换"考前速查模式"
   - 触发词："复习进度"、"进度报告"、"还差什么"、"今天复习什么"、"自评打分"

> **MCP 降级规则**：exam-memory MCP 不可用时，所有 skill 自动降级为 Local Markdown Mode；如果仓库不可写，则进入 Stateless Lite Mode 并返回 append blocks。不影响主流程，但最终报告必须说明降级能力和长期使用风险。

### 调用示例

```python
# 第一步：获取骨架
Skill(skill="solve-skeleton")

# 第二步：填充逻辑后，如需诊断（WA/TLE）调用
Skill(skill="solve-analyze")

# 第三步：测试通过后，获取注释
Skill(skill="algo-annotation")

# 第四步：生成一组选择题（按主题或错题薄弱点）
Skill(skill="choice-q-create")

# 第五步：交互式答题，错题自动写入 mistake_log
Skill(skill="choice-q-drill")

# 第六步：查看跨维度进度报告和今日必做清单
Skill(skill="review-tracker")
```

## 今天怎么开始

每天开始时：

1. 调用 `Skill(skill="solve-skeleton")` 熟悉 ACM 输入输出骨架。
2. 做 3-4 道数组/哈希/排序/二分基础题。
3. 每题限时 25-40 分钟，做完调用 `Skill(skill="algo-annotation")` 加注释。
4. 把卡住原因同时写进 `targets/{target}/mistake_log.md` 和当天 Problem Log。
5. 用 30-45 分钟读 `shared/cheatsheets/llm_core_cheatsheet.md` 或目标目录下的对应速记资料。

## 每日最低闭环

- 算法：至少 3 道题，至少 1 道计时独立完成。
  - 每道题走 solve-skeleton → solve-analyze（WA/TLE时） → algo-annotation 完整流程。
  - WA/TLE 必须记录到 `targets/{target}/mistake_log.md`（错误模式会回流到 annotation 的 `# [防错]`）。
- 选择题：每天花 20-30 分钟做一个主题的数学/AI 选择题练习（AI 实验室题型）。
  - 走 `choice-q-create` → `choice-q-drill` 完整流程，错题自动写入 `mistake_log.md`。
- 记录：每做完一题，立即填写当天 `shared/daily/YYYY-MM-DD.md` 底部的 **Problem Log**（题名、模式、解法、AC/错因、复杂度）。
- LLM：至少复习 1 个核心主题（Transformer/GNN/扩散模型/LLaMA3/数学基础），并能口头讲 2 分钟。
- 复盘：写 3 条今天最容易再犯的错误。
- 交接：更新 `HANDOFF.md` 的下一步动作。

## 反馈回路

```
targets/{target}/mistake_log.md    targets/{target}/topic_checklist.md
  ▲          ▲                             ▲
  │          │                             │
  │          │  choice-q-drill             │  P0/P1 优先级调整
  │          │  答错题目自动追加            │
  │          │                             │
  │          │  algo-annotation            │
  │          │  reads # [防错]             │
  │          │                             │
  └──────────┼─── targets/{target}/solutions_batch.py (exam solution reference)
             │
             │
  choice-q-create ◄──────┐
   读取 mistake_log.md   │
   调整出题重点           │
          │               │
          ▼               │
  choice-q-drill ────────┘
   交互答题 → 错题回流
          │
          └──► (MCP 可用时) exam-memory 双写
               mcp__exam-memory__save_experience() / inc_error_count()
               跨会话持久化，下次 choice-q-create 可读取
```

`mistake_log.md` 是默认且权威的 Markdown 错误反馈源。每道题的错因必须录入，annotation skill 会自动引用。
`exam-memory MCP` 是可选增强——提供跨会话经验检索和错误频率追踪。MCP 不可用时不影响核心闭环。

## 如果时间只剩 1 小时

只做算法：

- 15 分钟复习 `skills/solve-skeleton/` 骨架模板。
- 35 分钟做 1 道中等题（走完整 solve-skeleton → annotation 流程）。
- 10 分钟记录错因到当天 Problem Log 和 `mistake_log.md`。
