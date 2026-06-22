"""考试经验沉淀 MCP Server

提供工具：list_experiences, save_experience, inc_error_count,
get_user_profile, update_user_profile, mount_source, list_sources, fetch_from_source
"""

import asyncio
import glob
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, ToolsCapability, Tool, TextContent

from exam_memory.knowledge_source import DirConnector
from exam_memory.source_registry import SourceRegistry
from exam_memory.frontmatter import parse_frontmatter as _parse_frontmatter

# ── 路径常量 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
EXPERIENCES_DIR = BASE_DIR / "experiences"
PROFILE_PATH = BASE_DIR / "user_profile.json"

EXPERIENCES_DIR.mkdir(parents=True, exist_ok=True)

# ── SourceRegistry（知识源生命周期管理）──────────────────────
_registry = SourceRegistry()

SOURCES_YAML_PATH = BASE_DIR / "sources.yaml"

# ── Store 实例缓存（避免每次 MCP tool call 重建）────────────────
_fts_cache: "FTSStore | None" = None
_vec_cache: "NumpyVectorStore | None" = None
_profile_lock = threading.Lock()
_experience_locks_guard = threading.Lock()
_experience_locks: dict[Path, threading.Lock] = {}


def _get_fts():
    global _fts_cache
    if _fts_cache is None:
        from exam_memory.fts_store import FTSStore
        _fts_cache = FTSStore()
    return _fts_cache


def _get_vec():
    global _vec_cache
    if _vec_cache is None:
        from exam_memory.vector_store import NumpyVectorStore
        _vec_cache = NumpyVectorStore()
    return _vec_cache


def _lock_for_path(path: Path) -> threading.Lock:
    resolved = path.resolve()
    with _experience_locks_guard:
        lock = _experience_locks.get(resolved)
        if lock is None:
            lock = threading.Lock()
            _experience_locks[resolved] = lock
        return lock


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _allowed_source_roots() -> tuple[Path, ...]:
    return (
        (REPO_ROOT / "targets").resolve(),
        (REPO_ROOT / "shared" / "cheatsheets").resolve(),
    )


def _is_allowed_source_path(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        resolved == root or resolved.is_relative_to(root)
        for root in _allowed_source_roots()
    )

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
        name="mount_source",
        description="读取 sources.yaml 配置文件，为每个 source 创建 DirConnector 并挂载到 registry。",
        inputSchema={
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "sources.yaml 路径（可选，默认 BASE_DIR/sources.yaml）",
                },
            },
        },
    ),
    Tool(
        name="list_sources",
        description="返回已挂载知识源的状态列表。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="fetch_from_source",
        description="从指定知识源检索相关内容。",
        inputSchema={
            "type": "object",
            "properties": {
                "source_name": {"type": "string", "description": "知识源名称"},
                "topic": {"type": "string", "description": "搜索关键词"},
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "最大返回 chunk 数",
                },
            },
            "required": ["source_name", "topic"],
        },
    ),
    Tool(
        name="refresh_source",
        description="刷新指定知识源或全部知识源（重新扫描目录）。",
        inputSchema={
            "type": "object",
            "properties": {
                "source_name": {
                    "type": "string",
                    "description": "知识源名称（可选，不传则刷新全部）",
                },
            },
        },
    ),
    Tool(
        name="list_due_reviews",
        description="列出项目中到期的复习项。使用 review_schedule 的 review-queue 文件。",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "目标名称（如 pdd-algo），默认扫描 project_root/targets/ 下首个目标",
                },
                "date": {
                    "type": "string",
                    "description": "检查日期 YYYY-MM-DD（可选，默认今天）",
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回条数（默认 10）",
                },
            },
        },
    ),
    Tool(
        name="mark_review_result",
        description="标记一条复习项的结果并自动更新下一次复习计划（SM-2 简化调度）。",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "目标名称（如 pdd-algo）",
                },
                "review_id": {
                    "type": "string",
                    "description": "复习项 ID（如 RQ-20260617-001）",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["again", "hard", "good", "easy"],
                    "description": "复习结果：again=遗忘, hard=困难, good=良好, easy=轻松",
                },
                "date": {
                    "type": "string",
                    "description": "复习日期 YYYY-MM-DD（可选，默认今天）",
                },
            },
            "required": ["target", "review_id", "outcome"],
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
        m = re.search(r"_(\d{3})(?:_[0-9a-f]{6})?\.md$", f)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


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
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(profile, ensure_ascii=False, indent=2)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=PROFILE_PATH.parent,
            prefix=f".{PROFILE_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, PROFILE_PATH)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _deep_merge(base: dict, overlay: dict) -> dict:
    """递归合并 overlay 到 base（overlay 优先）。"""
    merged = base.copy()
    for k, v in overlay.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


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
        store = _get_vec()
        results = store.search(
            query, top_k=limit, type_filter=exp_type, source_filter="experiences"
        )
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


def _list_experiences_hybrid(
    exp_type: str, query: str, limit: int
) -> list[TextContent]:
    """混合检索：FTS BM25 + 向量 cosine，Weighted RRF 融合。"""
    try:
        from exam_memory.hybrid_search import hybrid_search

        fts = _get_fts()
        vec = _get_vec()
        results = hybrid_search(
            query, fts, vec, limit=limit, exp_type=exp_type, source_filter="experiences"
        )
    except Exception:
        results = []

    if not results:
        return [TextContent(
            type="text",
            text=f"混合检索「{query}」在「{exp_type}」类型中未找到匹配经验。"
        )]

    parts = []
    for i, r in enumerate(results, 1):
        score = r["score"]
        fts_s = r.get("fts_score")
        vec_s = r.get("vec_score")
        detail = ""
        if fts_s is not None and vec_s is not None:
            detail = f" (FTS:{fts_s} + 向量:{vec_s})"
        parts.append(f"### 经验 {i} (相关度: {score}{detail})\n{r['text']}")
    return [TextContent(type="text", text="\n---\n".join(parts))]


def _list_experiences_fts(
    exp_type: str, query: str, limit: int
) -> list[TextContent]:
    """纯 FTS 词法检索（无需 embedding 依赖）。"""
    try:
        store = _get_fts()
        results = store.search(
            query, limit=limit, type_filter=exp_type, source_filter="experiences"
        )
    except Exception:
        results = []

    if not results:
        return [TextContent(
            type="text",
            text=f"词法检索「{query}」在「{exp_type}」类型中未找到匹配经验。"
        )]

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"### 经验 {i} (BM25: {r['score']})\n{r.get('content', '')}")
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
            return _list_experiences_hybrid(exp_type, query, limit)
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
        safe_knowledge = re.sub(r'[^\w一-鿿-]', '_', knowledge).strip("_")
        short_id = uuid.uuid4().hex[:6]
        filename = f"{prefix}_{safe_knowledge}_{seq:03d}_{short_id}.md"
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

        # 静默向量化 + FTS 入库（失败不影响保存结果）
        try:
            store = _get_vec()
            meta = dict(frontmatter)
            meta["file_name"] = filename
            meta["source_dir"] = "experiences"
            meta["canonical_key"] = f"experiences/{filename}"
            store.upsert(filename, doc, meta)
        except Exception:
            pass

        try:
            fts = _get_fts()
            fts.upsert(
                canonical_key=f"experiences/{filename}",
                title=title,
                knowledge=knowledge,
                content=content,
                type=exp_type,
            )
        except Exception:
            pass

        return [TextContent(type="text", text=f"已保存: {filename}")]

    # ── inc_error_count ──
    if name == "inc_error_count":
        fp = arguments["file_path"]
        # 始终在 EXPERIENCES_DIR 内解析，拒绝路径穿越
        target = (EXPERIENCES_DIR / fp).resolve()
        if not target.is_relative_to(EXPERIENCES_DIR.resolve()):
            return [TextContent(type="text", text=f"非法文件路径: {fp}")]

        if not target.exists():
            return [TextContent(type="text", text=f"文件不存在: {target.name}")]

        with _lock_for_path(target):
            text = target.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            old = meta.get("error_count", 0)
            meta["error_count"] = old + 1
            meta["last_review"] = datetime.now().strftime("%Y-%m-%d")

            yaml_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False)
            if text.startswith("---"):
                parts = text.split("---", 2)
                new_text = f"---\n{yaml_str}---{parts[2]}" if len(parts) >= 3 else text
            else:
                new_text = f"---\n{yaml_str}---\n{text}"

            _write_text_atomic(target, new_text)
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
        _ALLOWED_PROFILE_KEYS = {"preferences", "strengths", "weaknesses", "goals", "study_plan"}
        diff = arguments["diff"]
        invalid_keys = set(diff.keys()) - _ALLOWED_PROFILE_KEYS
        if invalid_keys:
            return [TextContent(type="text", text=f"不允许的 profile 字段: {invalid_keys}")]
        with _profile_lock:
            if PROFILE_PATH.exists():
                profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            else:
                profile = {}
            profile = _deep_merge(profile, diff)
            _save_profile(profile)
        return [TextContent(type="text", text="画像已更新。")]

    # ── mount_source ──
    if name == "mount_source":
        try:
            config_path = Path(arguments.get("config_path", "")) if arguments.get("config_path") else SOURCES_YAML_PATH
            config_path = config_path.resolve()
            if not config_path.is_relative_to(BASE_DIR.resolve()):
                return [TextContent(type="text", text=f"非法配置路径: {config_path}")]
            if not config_path.exists():
                return [TextContent(type="text", text=f"配置文件不存在: {config_path}")]
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            sources_list = config.get("sources", [])
            if not sources_list:
                return [TextContent(type="text", text="sources.yaml 中无 source 定义")]

            config_dir = config_path.parent
            mounted = []
            for src in sources_list:
                src_type = src.get("type", "")
                if src_type != "local_dir":
                    continue
                name_ = src["name"]
                src_config = src.get("config", {})
                path = (config_dir / src_config.get("path", "")).resolve()
                if not _is_allowed_source_path(path):
                    mounted.append(f"{name_}(非法 source 路径: {path})")
                    continue
                if not path.exists() or not path.is_dir():
                    mounted.append(f"{name_}(目录不存在: {path})")
                    continue
                glob_pattern = src_config.get("glob", "*.md")
                processing = src.get("processing", {})
                chunk_size = processing.get("chunk_size", 1600)
                connector = DirConnector(name=name_, path=path, glob_pattern=glob_pattern, chunk_size=chunk_size)
                if _registry.mount(connector):
                    mounted.append(name_)
                else:
                    mounted.append(f"{name_}(已存在或挂载失败)")
            return [TextContent(type="text", text=f"已挂载: {', '.join(mounted)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"mount_source 失败: {e}")]

    # ── list_sources ──
    if name == "list_sources":
        try:
            sources = _registry.list_mounted()
            if not sources:
                return [TextContent(type="text", text="暂无已挂载知识源。")]
            parts = []
            for s in sources:
                parts.append(f"- {s['name']} ({s['source_type']}) | connected={s['connected']} | topics={s['topic_count']}")
            return [TextContent(type="text", text="\n".join(parts))]
        except Exception as e:
            return [TextContent(type="text", text=f"list_sources 失败: {e}")]

    # ── fetch_from_source ──
    if name == "fetch_from_source":
        try:
            source_name = arguments["source_name"]
            topic = arguments["topic"]
            limit = arguments.get("limit", 10)
            chunks = _registry.fetch_from(source_name, topic, limit=limit)
            if not chunks:
                return [TextContent(type="text", text=f"源 '{source_name}' 未找到与 '{topic}' 相关的内容。")]
            parts = []
            for i, c in enumerate(chunks, 1):
                parts.append(f"### Chunk {i} (来源: {c['source']})\n{c['text']}")
            return [TextContent(type="text", text="\n---\n".join(parts))]
        except Exception as e:
            return [TextContent(type="text", text=f"fetch_from_source 失败: {e}")]

    # ── refresh_source ──
    if name == "refresh_source":
        try:
            source_name = arguments.get("source_name")
            if source_name:
                source = _registry.get(source_name)
                if source is None:
                    return [TextContent(type="text", text=f"知识源不存在: {source_name}")]
                added = source.refresh()
                return [TextContent(type="text", text=f"已刷新 '{source_name}'，新增 {added} 个文件。")]
            else:
                results = []
                for s in _registry.list_mounted():
                    src = _registry.get(s["name"])
                    if src:
                        added = src.refresh()
                        results.append(f"- {s['name']}: 新增 {added} 个文件")
                return [TextContent(type="text", text="全部刷新完成:\n" + "\n".join(results))]
        except Exception as e:
            return [TextContent(type="text", text=f"refresh_source 失败: {e}")]

    # ── list_due_reviews ──
    if name == "list_due_reviews":
        try:
            from exam_memory.review_cli import due as _due
            target = arguments.get("target", "")
            d = arguments.get("date", "")
            from datetime import date as _date
            today = _date.fromisoformat(d) if d else _date.today()
            limit = arguments.get("limit", 10)

            # Auto-detect target if not provided
            if not target:
                targets_dir = BASE_DIR.parent.parent / "targets"
                if targets_dir.is_dir():
                    targets = [d.name for d in targets_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
                    if targets:
                        target = targets[0]

            if not target:
                return [TextContent(type="text", text="未指定 target 且无法自动检测。")]

            items = _due(target=target, today=today, project_root=BASE_DIR.parent.parent)
            if not items:
                return [TextContent(type="text", text=f"「{target}」暂无到期复习项。")]

            parts = [f"### {target} 到期复习 ({len(items)} 项)\n"]
            for item in items[:limit]:
                parts.append(
                    f"- **{item.review_id}** [{item.priority}] {item.topic}"
                    f"\n  → {item.prompt}"
                )
            return [TextContent(type="text", text="\n".join(parts))]
        except Exception as e:
            return [TextContent(type="text", text=f"list_due_reviews 失败: {e}")]

    # ── mark_review_result ──
    if name == "mark_review_result":
        try:
            from exam_memory.review_cli import mark as _mark
            target = arguments["target"]
            review_id = arguments["review_id"]
            outcome = arguments["outcome"]
            d = arguments.get("date", "")
            from datetime import date as _date
            today = _date.fromisoformat(d) if d else _date.today()

            ok = _mark(target=target, review_id=review_id, outcome=outcome, today=today, project_root=BASE_DIR.parent.parent)
            if ok:
                return [TextContent(type="text", text=f"复习项 {review_id} 已更新，结果: {outcome}。")]
            else:
                return [TextContent(type="text", text=f"未找到复习项: {review_id}")]
        except Exception as e:
            return [TextContent(type="text", text=f"mark_review_result 失败: {e}")]

    return [TextContent(type="text", text=f"未知工具: {name}")]


# ── 入口 ──────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="exam-memory",
                server_version="2.0.0",
                capabilities=ServerCapabilities(tools=ToolsCapability()),
            ),
        )


def cli_main() -> None:
    """Synchronous console-script entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
