# 开源方案 — Pass-LLM-with-LLM

> 创建日期：2026-06-16 | 状态：P0 基本完成，P1 待执行
> 分支：`feat/open-source`（从 `ai-lab-0616-prep` 切出）

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-16 | 初始方案：项目改名、README、.gitignore、AGENTS.md 泛化 |
| 2026-06-16 | 新增：MCP 配置指南、init-guide Skill、README Startup Order、新人引导流程 |
| 2026-06-16 | 新增：环境支持文档（environment-support.md）、model provider 说明、IDE 推荐 |
| 2026-06-16 | 清理：PDD 真题文件重命名、AGENTS.md 项目名更新 |

## 1. 项目定位

**新名称**：`Pass-LLM-with-LLM`
**Slogan**：用 LLM 备考 LLM 笔试 — Claude Code Skills 驱动的 AI 笔试备考引擎

**核心卖点**：
- 完整的 Skill Pipeline：骨架生成 → 解题诊断 → 标注 → 错题回流
- 自定义 MCP Server 实现跨会话经验持久化
- 选择题生成/交互答题/即时评分闭环
- 纯本地文件存储，零外部依赖（MCP 为可选增强）

**目标受众**：
- 准备 AI/算法岗位笔试的候选人
- 对 Claude Code Skills + MCP 开发模式感兴趣的开发者
- 想搭建个人 AI 学习助手的技术人员

## 2. 仓库命名与远程地址

```
GitHub: github.com/Tenstu/Pass-LLM-with-LLM
```

## 3. 开源前必须完成的改动

### 3.1 P0 — 必须完成

| 序号 | 改动 | 说明 | 状态 |
|------|------|------|------|
| 1 | `git mv docs/LICENSE LICENSE` | GitHub 需要根目录 LICENSE 才能自动识别 | **已完成** |
| 2 | 更新 `.gitignore` | 移除 `docs/`，加入个人数据目录忽略规则，保留目录框架 | **已完成** |
| 3 | 重写 `README.md` | 中英文双版（README.md 英文 + README_CN.md 中文） | **已完成** |
| 4 | `git mv docs/contributing-guide.md CONTRIBUTING.md` | GitHub 自动识别 PR 提示 | **已完成** |
| 5 | 重命名项目目录 | `pdd-llm-algo-exam-harness` → `Pass-LLM-with-LLM` | 可选（仅影响本地目录名，GitHub 仓库已正确命名） |
| 6 | 清理 git 中已跟踪的敏感文件 | `git rm --cached` 移除 `.claude/settings.json`、daily/、progress/ 个人数据 | **已完成** |

### 3.2 P1 — 建议完成

| 序号 | 改动 | 说明 | 状态 |
|------|------|------|------|
| 7 | 精简 `AGENTS.md` | 移除个人色彩内容（具体日期、岗位 JD），保留技术架构 | **已完成** |
| 8 | 更新 `.mcp.json` | 当前为空 `{}`，可加注释说明配置方式 | **已完成**（在 docs/mcp-setup-guide.md 中提供模板） |
| 9 | 添加 `.github/ISSUE_TEMPLATE/` | Bug report + Feature request 模板 | **已完成** |
| 10 | 添加 `.github/PULL_REQUEST_TEMPLATE.md` | PR 模板 | **已完成** |
| 11 | MCP 配置指南 | `docs/mcp-setup-guide.md`：exam-memory 注册 + 外部 MCP 引用 + 启动顺序 | **已完成** |
| 12 | init-guide Skill | `skills/init-guide.md`：首次使用导引，收集备考目标，更新画像 | **已完成** |
| 13 | README Startup Order | README.md + README_CN.md 新增启动顺序图、MCP 依赖说明表 | **已完成** |
| 14 | START_HERE 首次使用分支 | 检测 HANDOFF.md 模板状态，引导调用 init-guide | **已完成** |
| 15 | AGENTS.md 注册 init-guide | Component Map + Skill Invocation Protocol 新增 init-guide | **已完成** |
| 16 | 环境支持文档 | `docs/environment-support.md`：model provider、IDE 集成、开发环境记录 | **已完成** |
| 17 | README 环境支持章节 | README.md + README_CN.md 新增 Supported Environments | **已完成** |
| 18 | 清理 PDD 真题文件 | 重命名 `p1_letter_ring_substring.md` → `example_ring_substring.md` | **已完成** |
| 19 | AGENTS.md 项目名修正 | Component Map 中 `pdd-llm-algo-exam-harness` → `Pass-LLM-with-LLM` | **已完成** |

### 3.3 P2 — 可选

| 序号 | 改动 | 说明 | 状态 |
|------|------|------|------|
| 20 | 添加 `CHANGELOG.md` | 版本记录 | 待执行 |
| 21 | GitHub Topics 标签 | `llm`、`exam-prep`、`claude-code`、`mcp`、`algorithm` | 发布时设置 |
| 22 | GitHub About 描述 | 一句话项目描述 + 网站链接 | 发布时设置 |

## 4. README.md 重写方案

**已完成**，采用中英文双版：
- `README.md` — 英文版（GitHub 默认展示）
- `README_CN.md` — 中文版（顶部互链切换）

结构覆盖：项目定位、核心特性、快速开始、Skill 一览、目录结构、适配指南、Contributing、License。

## 5. `.gitignore` 更新方案

新增以下条目（追加到现有 .gitignore）：

```gitignore
# 个人备考数据（开源后不需要）
HANDOFF.md
daily/
progress/

# 考试经验沉淀系统 - 运行时数据（已在现有 .gitignore 中，确认无遗漏）
exam_memory/
docs/
```

> 注：`docs/` 已在现有 .gitignore 中，但设计文档有开源参考价值。
> 建议将开源相关的 docs（LICENSE、contributing-guide）移至根目录后，docs/ 继续 gitignore。

**已完成**。最终策略：

- `docs/` 从 `.gitignore` 移除（设计文档有开源参考价值）
- `HANDOFF.md` 保留跟踪（作为模板，每轮备考填写后提交前应清空个人数据）
- `daily/*` 忽略数据文件，保留 `daily/README.md`（目录说明 + 文件模板）
- `progress/{subdir}/*` 忽略数据文件，保留 `.gitkeep`（目录框架）
- `exam_memory/` 继续忽略（运行时数据）
- `.claude/` 继续忽略（个人配置，已从 git index 移除）

## 6. AGENTS.md 精简方向

**已完成**。已泛化的部分：
- Project Goal：移除具体考试/日期/岗位，改为"可按需配置"
- Exam Format：改为"默认配置"表格，注明按目标考试调整
- Priority Split：移除"AI 实验室独有题型"限定
- AI Lab Role Requirements → Target Role Requirements（示例化）
- LLM Review Rules：移除 InternLM/书生系列等具体引用
- Mini-Project Rule：移除 RTX 5060 8G 具体设备

保留完整的技术架构：Component Map、MCP Integration、Skill Pipeline、Data Flow、Operating Rules、Skill Invocation Protocol。

## 7. 分支策略

```
main              ← 开源发布分支（稳定版本）
  └── feat/open-source  ← 当前分支，完成所有改动后合并到 main
  └── feat/xxx          ← 后续功能分支
  └── fix/xxx           ← 修复分支
```

合并到 main 后，在 GitHub 上：
1. 创建 Release v1.0.0
2. 设置 Topics 标签
3. 编写 About 描述
4. 考虑 Star → Fork → PR 的社区引导

## 8. 执行顺序

```
Step 1: 更新 .gitignore（移除 docs/，加入个人数据忽略规则）    ✅ 已完成
Step 2: git rm --cached 个人数据文件（.claude/settings.json, daily/, progress/）  ✅ 已完成
Step 3: 创建目录框架模板（HANDOFF.md 模板, daily/README.md, progress/.gitkeep）  ✅ 已完成
Step 4: 泛化 AGENTS.md（移除具体日期/岗位/设备引用）            ✅ 已完成
Step 5: 重写 README.md（英文）+ 创建 README_CN.md（中文）      ✅ 已完成
Step 5.1: README 新增 Startup Order + MCP 依赖说明 + init-guide  ✅ 已完成
Step 5.2: 创建 docs/mcp-setup-guide.md（MCP 注册指南）           ✅ 已完成
Step 5.3: 创建 skills/init-guide.md（首次使用导引 Skill）         ✅ 已完成
Step 5.4: 更新 START_HERE.md（首次使用分支）                      ✅ 已完成
Step 5.5: 更新 AGENTS.md（Component Map + Skill Protocol）       ✅ 已完成
Step 5.6: 更新 docs/INDEX.md + docs/open-source-plan.md          ✅ 已完成
Step 5.7: 创建 docs/environment-support.md（环境支持文档）        ✅ 已完成
Step 5.8: README 新增 Supported Environments 章节                 ✅ 已完成
Step 5.9: 重命名 PDD 真题文件为通用示例                           ✅ 已完成
Step 5.10: AGENTS.md 项目名修正                                   ✅ 已完成
Step 6: git mv docs/LICENSE LICENSE                             ✅ 已完成
Step 7: git mv docs/contributing-guide.md CONTRIBUTING.md       ✅ 已完成
Step 8: 添加 .github/ 模板（可选，P1）                          待执行
Step 9: 提交到 feat/open-source 分支                            待执行
Step 10: 合并到 main，推送 GitHub                               待执行
```

## 9. 风险与注意事项

| 风险 | 应对 |
|------|------|
| git history 中有个人数据 | 使用 `git filter-branch` 或 `git filter-repo` 清理（如需要） |
| exam_memory/ 被意外提交 | .gitignore 已覆盖，执行 Step 4 确保 |
| AGENTS.md 包含具体日期 | 精简时泛化为"短期冲刺备考" |
| 项目名含 "pdd" | 重命名为 Pass-LLM-with-LLM |
| MCP Server 依赖未声明 | 添加 `exam_memory/pyproject.toml` 依赖说明到 README |
