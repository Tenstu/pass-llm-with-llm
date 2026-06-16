"""考试经验沉淀 MCP Server

提供工具：list_experiences, save_experience, inc_error_count,
get_user_profile, update_user_profile, search_web（废弃）
"""

import asyncio
import glob
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, ToolsCapability, Tool, TextContent

# ── 路径常量 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
EXPERIENCES_DIR = BASE_DIR / "experiences"
PROFILE_PATH = BASE_DIR / "user_profile.json"

EXPERIENCES_DIR.mkdir(parents=True, exist_ok=True)

# ── 工具 JSON Schema ─────────────────────────────────────
TOOL_SCHEMAS = [
    Tool(
        name="list_experiences",
        description="按题型列出经验条目，按 error_count 降序返回前 limit 条全文。支持 query 参数进行语义检索。",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["单选题", "多选题", "算法"],
                    "description": "题型过滤",
                },
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "description": "最多返回条数",
                },
                "query": {
                    "type": "string",
                    "description": "语义检索查询文本（可选）。为空时按 error_count 降序返回。",
                },
            },
            "required": ["type"],
        },
    ),
    Tool(
        name="save_experience",
        description="保存一条新经验到经验库。文件自动编号。",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "经验标题（简短）"},
                "content": {"type": "string", "description": "经验正文（Markdown）"},
                "type": {
                    "type": "string",
                    "enum": ["单选题", "多选题", "算法"],
                },
                "knowledge": {"type": "string", "description": "知识点标签"},
                "difficulty": {
                    "type": "string",
                    "enum": ["简单", "中等", "困难"],
                    "default": "中等",
                },
            },
            "required": ["title", "content", "type", "knowledge"],
        },
    ),
    Tool(
        name="inc_error_count",
        description="将指定经验文件的 error_count 加 1。",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "经验文件名（不含目录前缀），如 '算法_双指针_001.md'",
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="get_user_profile",
        description="读取用户画像 JSON。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="update_user_profile",
        description="增量更新用户画像（合并提供的字段）。",
        inputSchema={
            "type": "object",
            "properties": {
                "diff": {
                    "type": "object",
                    "description": "要合并的字段（递归 merge）",
                }
            },
            "required": ["diff"],
        },
    ),
    Tool(
        name="search_web",
        description="[废弃] 联网搜索已迁移至 Claude Code 内置 WebSearch 工具，此工具保留仅作向后兼容。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    ),
]


# ── 辅助函数 ──────────────────────────────────────────────

def _type_prefix(t: str) -> str:
    """题型 → 文件名前缀"""
    return t


def _next_seq(prefix: str) -> int:
    """扫描 experiences/ 目录，返回下一个序号。"""
    pattern = str(EXPERIENCES_DIR / f"{prefix}_*.md")
    existing = glob.glob(pattern)
    max_n = 0
    for f in existing:
        m = re.search(r"_(\d{3})\.md$", f)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def _parse_frontmatter(text: str) -> dict:
    """解析 Markdown frontmatter（YAML between ---）。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _load_all_experiences(type_filter: str) -> list[tuple[int, str]]:
    """加载所有匹配类型的经验，返回 (error_count, full_content) 列表。"""
    prefix = _type_prefix(type_filter)
    pattern = str(EXPERIENCES_DIR / f"{prefix}_*.md")
    items = []
    for fp in glob.glob(pattern):
        text = Path(fp).read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        items.append((meta.get("error_count", 0), text))
    items.sort(key=lambda x: x[0], reverse=True)
    return items


def _save_profile(profile: dict):
    profile["last_updated"] = datetime.now(timezone.utc).isoformat()
    PROFILE_PATH.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _deep_merge(base: dict, overlay: dict) -> dict:
    """递归合并 overlay 到 base（overlay 优先）。"""
    merged = base.copy()
    for k, v in overlay.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def _search_ddg(query: str) -> str:
    """[废弃] 请使用 Claude Code 内置 WebSearch 替代。保留仅作向后兼容。"""
    return "此工具已废弃，请使用 Claude Code 内置 WebSearch 进行联网搜索。"


def _list_experiences_legacy(
    exp_type: str, limit: int
) -> list[TextContent]:
    items = _load_all_experiences(exp_type)
    if not items:
        return [TextContent(type="text", text=f"暂无「{exp_type}」类经验。")]
    top = items[:limit]
    parts = []
    for i, (_, content) in enumerate(top, 1):
        parts.append(f"### 经验 {i}\n{content}")
    return [TextContent(type="text", text="\n---\n".join(parts))]


def _list_experiences_semantic(
    exp_type: str, query: str, limit: int
) -> list[TextContent]:
    try:
        from exam_memory.vector_store import NumpyVectorStore
        store = NumpyVectorStore()
        results = store.search(query, top_k=limit, type_filter=exp_type)
    except Exception:
        results = []

    if not results:
        return [TextContent(
            type="text",
            text=f"语义检索「{query}」在「{exp_type}」类型中未找到匹配经验。"
        )]

    parts = []
    for i, r in enumerate(results, 1):
        score = r["score"]
        parts.append(f"### 经验 {i} (相关度: {score})\n{r['text']}")
    return [TextContent(type="text", text="\n---\n".join(parts))]


# ── MCP Server ────────────────────────────────────────────

app = Server("exam-memory")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_SCHEMAS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # ── list_experiences ──
    if name == "list_experiences":
        exp_type = arguments["type"]
        limit = arguments.get("limit", 5)
        query = arguments.get("query", "")

        if query:
            return _list_experiences_semantic(exp_type, query, limit)
        else:
            return _list_experiences_legacy(exp_type, limit)

    # ── save_experience ──
    if name == "save_experience":
        title = arguments["title"]
        content = arguments["content"]
        exp_type = arguments["type"]
        knowledge = arguments["knowledge"]
        difficulty = arguments.get("difficulty", "中等")

        prefix = _type_prefix(exp_type)
        seq = _next_seq(prefix)
        filename = f"{prefix}_{knowledge}_{seq:03d}.md"
        filepath = EXPERIENCES_DIR / filename

        today = datetime.now().strftime("%Y-%m-%d")
        frontmatter = {
            "type": exp_type,
            "knowledge": knowledge,
            "difficulty": difficulty,
            "error_count": 0,
            "created": today,
            "last_review": today,
        }
        yaml_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
        doc = f"---\n{yaml_str}---\n\n## {title}\n\n{content}\n"
        filepath.write_text(doc, encoding="utf-8")

        # 静默向量化入库（失败不影响保存结果）
        try:
            from exam_memory.vector_store import NumpyVectorStore
            store = NumpyVectorStore()
            meta = dict(frontmatter)
            meta["file_name"] = filename
            store.upsert(filename, doc, meta)
        except Exception:
            pass

        return [TextContent(type="text", text=f"已保存: {filename}")]

    # ── inc_error_count ──
    if name == "inc_error_count":
        fp = arguments["file_path"]
        # 允许传入完整路径或仅文件名
        if os.sep in fp or "/" in fp:
            target = Path(fp)
        else:
            target = EXPERIENCES_DIR / fp

        if not target.exists():
            return [TextContent(type="text", text=f"文件不存在: {target.name}")]

        text = target.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        old = meta.get("error_count", 0)
        meta["error_count"] = old + 1
        meta["last_review"] = datetime.now().strftime("%Y-%m-%d")

        yaml_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False)
        # 替换 frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            new_text = f"---\n{yaml_str}---{parts[2]}" if len(parts) >= 3 else text
        else:
            new_text = f"---\n{yaml_str}---\n{text}"

        target.write_text(new_text, encoding="utf-8")
        return [TextContent(type="text", text=f"error_count: {old} → {old + 1}")]

    # ── get_user_profile ──
    if name == "get_user_profile":
        if PROFILE_PATH.exists():
            profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        else:
            profile = {}
        return [TextContent(type="text", text=json.dumps(profile, ensure_ascii=False, indent=2))]

    # ── update_user_profile ──
    if name == "update_user_profile":
        diff = arguments["diff"]
        if PROFILE_PATH.exists():
            profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        else:
            profile = {}
        profile = _deep_merge(profile, diff)
        _save_profile(profile)
        return [TextContent(type="text", text="画像已更新。")]

    # ── search_web ──
    if name == "search_web":
        query = arguments["query"]
        result = _search_ddg(query)
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"未知工具: {name}")]


# ── 入口 ──────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="exam-memory",
                server_version="1.0.0",
                capabilities=ServerCapabilities(tools=ToolsCapability()),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
