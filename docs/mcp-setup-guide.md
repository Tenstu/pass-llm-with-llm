# MCP 配置指南

> 本指南帮助你配置项目所需的 MCP Server，让 Skill Pipeline 完整运行。

## 概览

本项目涉及两类 MCP Server：

| 类型 | Server | 是否必需 | 说明 |
|------|--------|---------|------|
| **项目自带** | `exam-memory` | 可选 | 跨会话经验持久化 + 用户画像 |
| **环境级**（外部） | ChatMem | 可选 | 跨会话对话记忆 |
| **环境级**（外部） | mempalace | 可选 | 结构化知识存储 |
| **环境级**（外部） | onefind | 可选 | 本地知识库检索 |

**重要**：`exam-memory` 是本项目唯一自带的 MCP Server，其余均为外部工具，需单独安装和配置。

---

## 1. exam-memory（项目自带）

### 1.1 安装依赖

```bash
cd Pass-LLM-with-LLM

# 基础安装（V1：MCP + 文件存储）
pip install mcp pyyaml

# V2 语义检索（可选：sentence-transformers + numpy）
pip install "exam_memory[embed]"   # 或 pip install sentence-transformers numpy

# V2 全部增强（可选：含 LangChain）
pip install "exam_memory[full]"    # 或 pip install sentence-transformers numpy langchain-core langchain-community
```

或使用 uv（推荐）：

```bash
uv pip install mcp pyyaml
uv pip install "exam_memory[embed]"   # 可选：语义检索
```

### 1.2 注册到 Claude Code

在项目根目录的 `.mcp.json` 中注册 server：

```json
{
  "mcpServers": {
    "exam-memory": {
      "command": "python",
      "args": ["exam_memory/server.py"],
      "env": {}
    }
  }
}
```

> 如果使用 `uv`，将 `command` 改为 `"uv"`，`args` 改为 `["run", "python", "exam_memory/server.py"]`。

### 1.3 验证

启动 Claude Code 后，执行以下任一操作确认 MCP 已注册：

- 输入 `/mcp` 查看已注册的 server 列表
- 尝试调用 `mcp__exam-memory__get_user_profile()` —— 应返回用户画像 JSON

如果 MCP 未启动，所有标记为"可选"的 Skill 会自动降级为纯本地模式，不影响核心流程。

### 1.4 工具一览

| 工具 | 功能 | 调用格式 |
|------|------|---------|
| `list_experiences` | 按题型检索经验（error_count 降序） | `mcp__exam-memory__list_experiences(type="单选题", limit=5)` |
| `save_experience` | 保存新经验条目（自动编号） | `mcp__exam-memory__save_experience(title="...", content="...", type="算法", knowledge="双指针")` |
| `inc_error_count` | 经验错误计数 +1 | `mcp__exam-memory__inc_error_count(file_path="算法_双指针_001.md")` |
| `get_user_profile` | 读取用户画像 JSON | `mcp__exam-memory__get_user_profile()` |
| `update_user_profile` | 增量合并画像字段 | `mcp__exam-memory__update_user_profile(diff={"weaknesses": {"DP": 5}})` |

> `search_web` 工具已废弃 —— 请使用 Claude Code 内置的 `WebSearch` 工具。

---

## 2. 环境级 MCP（外部工具）

以下 MCP Server 不由本项目管理，需根据各自文档单独安装。它们在特定场景下增强备考体验，但**完全可选**。

### 2.1 ChatMem

**用途**：跨会话项目记忆、对话历史检索、session handoff。

**典型场景**：
- "之前做过什么" / "上次练到哪了"
- 项目历史回顾、session 继续

**安装**：参考 [ChatMem 项目文档](https://github.com/Rimagination/ChatMem/releases) 在 Claude Code 全局配置中注册。

**与 exam-memory 的区分**：
- `exam-memory`：项目专用，结构化题目经验（错题模式、知识点、错误频率）
- `ChatMem`：通用项目记忆，存储对话级上下文（决策历史、handoff、startup rules）

### 2.2 mempalace

**用途**：结构化知识存储、跨 wing 知识图谱、agent 日记。

**典型场景**：
- 长期备考知识管理
- 跨项目知识关联

**安装**：参考 [mempalace 文档](https://github.com/MemPalace/mempalace) 在 Claude Code 全局配置中注册。

**与本项目的适配**：
- **知识图谱**：建模算法知识点的前置关系（如 DP ← 背包问题、二分 ← 有序数组），当用户在某知识点反复出错时，自动推荐关联的前置知识点复习。
- **Agent 日记**：每次练习 session 结束后记录学习观察（哪些模式掌握了、哪些还有盲区），构建可搜索的长期学习历史。
- **跨 wing 关联**：将备考知识与项目实战、面试准备笔记关联，形成完整的知识网络。
- **适合配合的 Skill**：review-tracker（知识图谱查覆盖缺口）、exam-assistant（结构化检索历史洞察）。
- 项目内 Skill 不直接调用 MemPalace 工具，通过 Claude Code 手动使用。

### 2.3 onefind

**用途**：本地知识库检索（Obsidian、Zotero 等）。

**典型场景**：
- 检索已有笔记中的知识点
- 文献库中的参考论文

**安装**：参考 [onefind 文档](https://github.com/iawnfoanaowt/OneFind) 在 Claude Code 全局配置中注册。

**与本项目的适配**：
- **Obsidian 笔记检索**：练习时搜索已有的 ML/算法笔记，将外部学习记录与项目内的 `llm/` 速记资料互补。
- **Zotero 文献检索**：为 Transformer、GNN、Diffusion 等主题速记资料检索参考论文，补充深度理解。
- **混合检索**：对所有本地源执行词法 + 语义联合搜索，适合查找"之前在哪里看过这个知识点"。
- **适合配合的 Skill**：choice-q-create（从笔记中搜索出题素材）、exam-assistant（解答时检索参考资料）、review-tracker（检查笔记是否覆盖考试知识点）。
- 项目内 Skill 不直接调用 OneFind 工具，通过 Claude Code 手动使用。

### 2.4 OneFind + exam-memory 互补配置

OneFind 的 **folder source** 可以索引 `exam_memory/experiences/` 目录，为经验文件提供语义搜索能力。但 OneFind 是只读检索层，无法替代 exam-memory 的写入链路（save → vectorize → store）。

**推荐配置步骤**：

1. 在 OneFind 中设置 `folder_library` 指向 `exam_memory/experiences/`：
   ```
   onefind_config_update(folder_library="<项目绝对路径>/exam_memory/experiences")
   ```

2. 通过 exam-memory MCP 保存新经验后，触发 OneFind 索引刷新：
   ```
   onefind_index_refresh(sources=["folder"])
   ```

3. 使用 OneFind 语义检索经验（比 MCP 的 `list_experiences` 关键词匹配更智能）：
   ```
   onefind_search(query="背包问题 动态规划", target="folder", limit=5)
   ```

**适用场景**：经验条目积累到 10+ 条后，关键词匹配的 `list_experiences` 可能遗漏语义相关但措辞不同的条目，此时 OneFind 的语义检索价值凸显。

---

## 3. 启动顺序

首次使用本项目的完整流程：

```
1. git clone → cd Pass-LLM-with-LLM
2. pip install mcp                # exam-memory 依赖
3. 编辑 .mcp.json                 # 注册 exam-memory（见上文模板）
4. 打开 Claude Code（CLI 或 VS Code 扩展）
5. 首次使用：对话中说"初始化"或"init"
   → 触发 init-guide Skill，引导填写备考目标
6. 日常使用：阅读 START_HERE.md 按 Skill Pipeline 开始练习
```

### 最低可用配置（零 MCP）

如果不想配置任何 MCP Server：

```
1. git clone → cd Pass-LLM-with-LLM
2. 直接打开 Claude Code
3. 从 START_HERE.md 开始，按 Skill Pipeline 使用
```

所有 Skill 在无 MCP 时均降级为纯本地模式，核心闭环（solve-skeleton → solve-analyze → algo-annotation → mistake_log）完全可用。

---

## 4. 常见问题

**Q：`.mcp.json` 已配置但 MCP 未启动？**
A：检查 `exam_memory/server.py` 路径是否正确。在 Claude Code 中输入 `/mcp` 查看状态。

**Q：MCP 调用失败会报错吗？**
A：不会。所有 MCP 调用都有 graceful degradation，失败时静默跳过，不影响主流程。

**Q：可以只用 exam-memory 不用其他 MCP 吗？**
A：可以。exam-memory 是唯一项目级 MCP，其余均为独立工具，按需配置。

**Q：Python 版本要求？**
A：Python 3.10+（`mcp` 库要求）。
