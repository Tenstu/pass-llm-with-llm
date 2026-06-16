"""NumpyVectorStore — 基于 numpy 的向量存储（exam-memory V2 核心层）。

文件布局 (exam_memory/vectorstore/):
    embeddings.npy   — float32 (N, 1024) 行优先矩阵
    metadata.json    — list[dict]，每条与 embeddings 行一一对应

用法:
    from exam_memory.vector_store import NumpyVectorStore, VECTOR_DIR
    store = NumpyVectorStore()
    store.rebuild()                        # 全量重建
    results = store.search("双指针", top_k=3)
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

import numpy as np

from exam_memory.embedding import encode_safe, EmbeddingError

# ── 路径 ─────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
VECTOR_DIR = BASE_DIR / "vectorstore"
EMB_PATH = VECTOR_DIR / "embeddings.npy"
META_PATH = VECTOR_DIR / "metadata.json"

VECTOR_DIR.mkdir(parents=True, exist_ok=True)

# ── 类型别名 ─────────────────────────────────────────────────

_TextOrMeta = tuple[str, dict[str, Any]]   # (full_text, metadata)

# ── 辅助 ─────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict[str, Any]:
    """解析 Markdown YAML frontmatter，将 date 转为 str 以保证 JSON 序列化。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        import yaml
        meta = yaml.safe_load(parts[1]) or {}
        # YAML 的 2026-06-15 会被解析为 date 对象 → 转 str
        for k, v in meta.items():
            if hasattr(v, "isoformat"):
                meta[k] = v.isoformat()
        return meta
    except Exception:
        return {}


def _extract_text(content: str) -> str:
    """从 Markdown 提取正文（去掉 frontmatter）。"""
    if content.startswith("---"):
        parts = content.split("---", 2)
        return parts[2].strip() if len(parts) >= 3 else content
    return content


def _load_full_text(filename: str, exp_dir: Path) -> str:
    """按文件名从 experiences/ 加载完整 Markdown。找不到返回空串。"""
    if not filename:
        return ""
    target = exp_dir / filename
    if not target.exists():
        return ""
    try:
        return target.read_text(encoding="utf-8")
    except Exception:
        return ""


def _load_experiences(type_filter: str | None = None) -> list[_TextOrMeta]:
    """扫描 experiences/ 目录，返回 [(full_text, meta_with_filename), ...]。"""
    exp_dir = BASE_DIR / "experiences"
    pattern = str(exp_dir / "*.md")
    items: list[_TextOrMeta] = []
    for fp in glob.glob(pattern):
        text = Path(fp).read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        if type_filter and meta.get("type") != type_filter:
            continue
        meta["file_name"] = Path(fp).name
        body = _extract_text(text)
        items.append((body, meta))
    return items


# ── NumpyVectorStore ─────────────────────────────────────────

class NumpyVectorStore:
    """纯 numpy 向量存储，零外部数据库依赖。"""

    def __init__(self):
        self._embs: np.ndarray | None = None   # (N, D) float32
        self._meta: list[dict[str, Any]] = []   # len == N

    # ── 持久化 ──────────────────────────────────────────────

    def save(self) -> None:
        if self._embs is not None and self._meta:
            np.save(str(EMB_PATH), self._embs)
            META_PATH.write_text(
                json.dumps(self._meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load(self) -> bool:
        if not EMB_PATH.exists() or not META_PATH.exists():
            return False
        try:
            self._embs = np.load(str(EMB_PATH))
            self._meta = json.loads(META_PATH.read_text(encoding="utf-8"))
            return True
        except Exception:
            return False

    def clear(self) -> None:
        self._embs = None
        self._meta = []
        for p in (EMB_PATH, META_PATH):
            if p.exists():
                p.unlink()

    # ── 索引 ────────────────────────────────────────────────

    def rebuild(self, *, verbose: bool = False) -> int:
        """全量重建：扫描 experiences/ 并重新向量化。返回入库条数。"""
        items = _load_experiences()
        texts = [t for t, _ in items]
        metas = [m for _, m in items]

        embeddings = encode_safe(texts)
        if embeddings is None:
            if verbose:
                print("[vector_store] embedding 不可用，重建跳过")
            self.clear()
            return 0

        self._embs = embeddings.astype(np.float32)
        self._meta = []
        for i, meta in enumerate(metas):
            meta["id"] = meta.get("file_name", f"{meta.get('type', '?')}_{meta.get('knowledge', '?')}_{i:03d}.md")
            self._meta.append(meta)

        self.save()
        if verbose:
            print(f"[vector_store] 已重建: {len(metas)} 条经验, "
                  f"向量维度 {self._embs.shape}")
        return len(metas)

    # ── 搜索 ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        type_filter: str | None = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """语义搜索。

        Args:
            query: 查询文本。
            top_k: 最多返回条数。
            type_filter: 题型过滤（单选题/多选题/算法），None 不过滤。
            min_score: 最低余弦相似度阈值（0~1）。

        Returns:
            按相似度降序排列的 dict 列表，每条含:
             - score: float cosine similarity
             - text: str 正文
             - metadata: dict
        """
        if self._embs is None or len(self._meta) == 0:
            if not self.load():
                return []

        q_vec = encode_safe(query)
        if q_vec is None or self._embs is None:
            return []

        if q_vec.ndim == 1:
            q_vec = q_vec.reshape(1, -1)

        scores = (self._embs @ q_vec.T).flatten()

        candidates = list(range(len(self._meta)))
        if type_filter:
            candidates = [
                i for i in candidates
                if self._meta[i].get("type") == type_filter
            ]

        candidates.sort(key=lambda i: scores[i], reverse=True)
        top = candidates[:top_k]

        exp_dir = BASE_DIR / "experiences"
        results = []
        for idx in top:
            s = float(scores[idx])
            if s < min_score:
                break
            meta = self._meta[idx]
            full_text = _load_full_text(
                meta.get("file_name", meta.get("id", "")), exp_dir
            )
            results.append({
                "score": round(s, 4),
                "text": full_text,
                "metadata": meta,
            })
        return results

    # ── 单条 upsert ─────────────────────────────────────────

    def upsert(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """插入或更新单条经验。保存到磁盘。"""
        vec = encode_safe(text)
        if vec is None:
            return

        vec = vec.astype(np.float32).reshape(1, -1)
        metadata["text"] = text

        if self._embs is None or len(self._meta) == 0:
            self._embs = vec
            self._meta = [metadata]
        else:
            existing = next(
                (i for i, m in enumerate(self._meta)
                 if m.get("id") == doc_id or m.get("file_name") == doc_id),
                None,
            )
            if existing is not None:
                self._embs[existing] = vec[0]
                self._meta[existing] = metadata
            else:
                self._embs = np.vstack([self._embs, vec])  # type: ignore[arg-type]
                self._meta.append(metadata)

        self.save()

    @property
    def count(self) -> int:
        return len(self._meta)

    @property
    def is_available(self) -> bool:
        return self._embs is not None and len(self._meta) > 0
