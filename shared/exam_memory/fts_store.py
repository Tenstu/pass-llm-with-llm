"""SQLite FTS5 词法检索层（exam-memory V2 词法通道）。

对齐 OneFind v1.7:
  - FTS5 虚拟表，按源类型独立建表（通过 type 列过滤）
  - unicode61 tokenizer，移除变音符号
  - BM25 评分
  - 零额外依赖（SQLite 标准库）

与向量存储的对齐：
  - 使用 canonical_key（file_name）作为跨层匹配标识
  - 检索结果含 canonical_key，供 hybrid_search 融合

用法:
    from exam_memory.fts_store import FTSStore
    store = FTSStore()
    store.upsert(canonical_key="算法_双指针_001.md", title="...", knowledge="...", content="...", type="算法")
    results = store.search("双指针", limit=5)
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 路径 ─────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "vectorstore" / "fts.sqlite"

_LOCK = threading.Lock()

# ── 建表 ─────────────────────────────────────────────────────

_CREATE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS experience_fts
USING fts5(
    canonical_key UNINDEXED,
    title,
    knowledge,
    content,
    type,
    tokenize='unicode61 remove_diacritics 2'
)
"""


def _init(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_SQL)
    conn.execute(
        "INSERT OR IGNORE INTO experience_fts(rowid, canonical_key, title, knowledge, content, type) "
        "VALUES (0, '', '', '', '', '')"
    )


# ── FTSStore ─────────────────────────────────────────────────

class FTSStore:
    """SQLite FTS5 词法检索。线程安全。"""

    def __init__(self, db_path: str | Path | None = None):
        self._path = str(db_path) if db_path else str(DB_PATH)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        _init(self._conn)

    # ── 写入 ────────────────────────────────────────────────

    def upsert(
        self,
        canonical_key: str,
        title: str = "",
        knowledge: str = "",
        content: str = "",
        type: str = "",
    ) -> None:
        """插入或更新单条经验（delete-then-insert）。"""
        with _LOCK:
            self._conn.execute(
                "DELETE FROM experience_fts WHERE canonical_key = ?",
                (canonical_key,),
            )
            self._conn.execute(
                "INSERT INTO experience_fts(canonical_key, title, knowledge, content, type) "
                "VALUES (?, ?, ?, ?, ?)",
                (canonical_key, title, knowledge, content, type),
            )
            self._conn.commit()

    def upsert_many(self, docs: list[dict[str, str]]) -> None:
        """批量 upsert（delete-then-insert）。每条 doc 需含 canonical_key, title, knowledge, content, type。"""
        with _LOCK:
            for doc in docs:
                key = doc.get("canonical_key", "")
                self._conn.execute(
                    "DELETE FROM experience_fts WHERE canonical_key = ?",
                    (key,),
                )
                self._conn.execute(
                    "INSERT INTO experience_fts(canonical_key, title, knowledge, content, type) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        key,
                        doc.get("title", ""),
                        doc.get("knowledge", ""),
                        doc.get("content", ""),
                        doc.get("type", ""),
                    ),
                )
            self._conn.commit()

    # ── 检索 ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        type_filter: str | None = None,
        source_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """BM25 词法检索。

        Args:
            query: 查询文本。
            limit: 最多返回条数。
            type_filter: 题型过滤（None 不过滤）。

        Returns:
            按 BM25 评分升序排列的 dict 列表，每条含:
             - canonical_key: str 与向量存储匹配的标识
             - title, knowledge, type, content, score
        """
        if not query.strip():
            return []

        sql = (
            "SELECT canonical_key, title, knowledge, content, type, "
            "       bm25(experience_fts) as score "
            "FROM experience_fts "
            "WHERE experience_fts MATCH ? "
        )
        params: list[Any] = [query]

        if type_filter:
            sql += "AND type = ? "
            params.append(type_filter)

        if source_filter and source_filter != "all":
            sql += "AND canonical_key LIKE ? "
            params.append(f"{source_filter}/%")

        sql += "ORDER BY score LIMIT ?"
        params.append(limit)

        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as e:
            logger.warning(f"[fts_store] FTS 查询失败: {e}")
            return []

        return [
            {
                "canonical_key": r["canonical_key"],
                "title": r["title"],
                "knowledge": r["knowledge"],
                "content": r["content"],
                "type": r["type"],
                "score": round(r["score"], 4),
            }
            for r in rows
        ]

    # ── 统计 ────────────────────────────────────────────────

    def count(self) -> int:
        """已索引的经验条数（排除占位行）。"""
        row = self._conn.execute(
            "SELECT COUNT(*) as n FROM experience_fts WHERE canonical_key != ''"
        ).fetchone()
        return row["n"] if row else 0

    def clear(self) -> None:
        with _LOCK:
            self._conn.execute("DELETE FROM experience_fts")
            self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
